package dev.aiengg.potholereporter.security

import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile
import java.util.concurrent.ConcurrentHashMap

internal class AiUsageLimitException : IOException("AI usage limit reached.")

internal interface AiBudgetAuthenticator {
    fun initialized(): Boolean
    fun initialize()
    fun open(envelope: ByteArray): ByteArray
    fun sealNext(payload: ByteArray): ByteArray
}

internal data class AiRequestIdentity(
    val provider: String,
    val endpoint: String,
    val model: String,
    val purpose: String,
    val outputTokens: Long
)

/** Native-owned identities and ceilings; no caller can configure these maxima. */
internal object AiOutputPolicy {
    const val ENDPOINT = "https://api.openai.com/v1/responses"
    private val models = setOf("gpt-5-mini", "gpt-5.6")
    fun ceiling(purpose: String): Long = when (purpose) {
        "pothole_binary_assessment" -> 1536L
        "road_repair_assessment", "road_repair_verification" -> 768L
        "tender_match", "general" -> 512L
        else -> throw AiUsageLimitException()
    }

    fun outputLimit(purpose: String, requested: Long?): Long {
        val maximum = ceiling(purpose)
        if (requested == null) return maximum
        if (requested !in 1..Int.MAX_VALUE.toLong()) throw AiUsageLimitException()
        return minOf(requested, maximum)
    }

    fun validate(identity: AiRequestIdentity) {
        if (identity.provider != "openai" || identity.endpoint != ENDPOINT || identity.model !in models ||
            identity.outputTokens !in 1..ceiling(identity.purpose)) throw AiUsageLimitException()
    }
}

/**
 * Lifetime reservation ledger. Every attempted transmission is charged its full output ceiling;
 * failure, cancellation and untrusted usage reports never refund it. No reset/refill API exists.
 */
internal class PersistentAiUsageBudget(
    private val directory: File,
    private val authenticator: AiBudgetAuthenticator,
    private val sync: (RandomAccessFile) -> Unit = { it.channel.force(true) }
) {
    companion object {
        const val MAX_REQUESTS = 32L
        const val MAX_OUTPUT_TOKENS = 32_768L
        private const val MAGIC = 0x41494236
        private const val VERSION = 1
        private const val RECORD_BYTES = 53L // Version + 12-byte IV + 24-byte payload + 16-byte GCM tag.
        private val locks = ConcurrentHashMap<String, Any>()
    }

    private data class State(val requests: Long, val output: Long)

    fun reserve(identity: AiRequestIdentity) {
        AiOutputPolicy.validate(identity)
        try {
            val absolute = directory.absoluteFile
            // The Android adapter supplies a canonical native-private anchor.
            if (absolute.canonicalFile != absolute) throw AiUsageLimitException()
            synchronized(locks.computeIfAbsent(absolute.path) { Any() }) {
                val firstRun = if (!absolute.exists()) absolute.mkdir() else false
                if (!absolute.isDirectory || absolute.canonicalFile != absolute) throw AiUsageLimitException()
                // A permanent Keystore marker survives filesystem deletion. Never bootstrap
                // a replacement allowance after the WebView removes the whole directory.
                if (firstRun && authenticator.initialized()) throw AiUsageLimitException()
                if (!firstRun && !authenticator.initialized()) throw AiUsageLimitException()
                val ledger = File(absolute, "usage.bin")
                // A missing file in an existing directory is corruption, never a fresh allowance.
                if (!firstRun && (!ledger.isFile || ledger.canonicalFile != ledger.absoluteFile)) {
                    throw AiUsageLimitException()
                }
                RandomAccessFile(ledger, "rw").use { file ->
                    file.channel.lock().use {
                        val state = if (firstRun) {
                            if (file.length() != 0L) throw AiUsageLimitException()
                            authenticator.initialize()
                            State(0, 0)
                        } else read(file)
                        if (state.requests >= MAX_REQUESTS || identity.outputTokens > MAX_OUTPUT_TOKENS - state.output) {
                            throw AiUsageLimitException()
                        }
                        // Small validated counters and subtraction-based checks preclude overflow.
                        val next = State(state.requests + 1, state.output + identity.outputTokens)
                        write(file, next)
                    }
                }
            }
        } catch (_: Exception) {
            // Do not propagate paths, state contents, credentials or arbitrary persistence errors.
            throw AiUsageLimitException()
        }
    }

    private fun read(file: RandomAccessFile): State {
        if (file.length() != RECORD_BYTES) throw AiUsageLimitException()
        val record = ByteArray(RECORD_BYTES.toInt())
        file.seek(0); file.readFully(record)
        val payload = authenticator.open(record)
        if (payload.size != 24) throw AiUsageLimitException()
        DataInputStream(payload.inputStream()).use { input ->
            if (input.readInt() != MAGIC || input.readInt() != VERSION) throw AiUsageLimitException()
            val state = State(input.readLong(), input.readLong())
            if (state.requests !in 0..MAX_REQUESTS || state.output !in 0..MAX_OUTPUT_TOKENS ||
                (state.requests == 0L && state.output != 0L) || state.output < state.requests) throw AiUsageLimitException()
            return state
        }
    }

    private fun write(file: RandomAccessFile, state: State) {
        val bytes = ByteArrayOutputStream(24)
        DataOutputStream(bytes).use { out ->
            out.writeInt(MAGIC); out.writeInt(VERSION); out.writeLong(state.requests); out.writeLong(state.output)
        }
        val payload = bytes.toByteArray()
        // Replace the native encryption key BEFORE writing. Old valid records then become
        // invalid, including after a crash/failure; never send before durable completion.
        val record = authenticator.sealNext(payload)
        if (record.size.toLong() != RECORD_BYTES) throw AiUsageLimitException()
        file.seek(0)
        file.write(record)
        file.setLength(RECORD_BYTES)
        sync(file) // Durable reservation MUST succeed before any network transmission.
    }
}
