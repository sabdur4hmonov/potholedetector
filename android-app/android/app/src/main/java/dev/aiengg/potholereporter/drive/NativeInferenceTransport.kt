package dev.aiengg.potholereporter.drive

import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.ResponseBody
import org.json.JSONObject
import org.json.JSONTokener
import java.io.IOException
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.TimeUnit
import dev.aiengg.potholereporter.security.AiRequestIdentity
import dev.aiengg.potholereporter.security.AiUsageLimitException
import dev.aiengg.potholereporter.security.NonReplayableAiBody

internal class NativeInferenceException(
    message: String,
    val suspendInference: Boolean = false,
    val retryAfterMs: Long? = null,
    cause: Throwable? = null
) : IOException(message, cause)

/** Owns OpenAI HTTP/SSE lifecycle; camera, storage, and report logic stay elsewhere. */
internal class NativeInferenceTransport(
    private val apiKey: String,
    private val model: String,
    private val detail: String,
    private val debug: Boolean,
    private val endpoint: String = OAI_URL,
    private val okHttpClient: OkHttpClient = defaultClient(),
    private val sseLimits: NativeSseLimits = NativeSseLimits(),
    private val budgetGate: (AiRequestIdentity) -> Unit = { throw AiUsageLimitException() }
) {
    // Live Drive can issue two bounded requests concurrently. Backoff state is shared by
    // that transport, so increments/resets must not race or lose updates.
    private val consecutiveRetryableFailures = AtomicInteger(0)
    private val activeCalls = mutableSetOf<Call>()
    private val activeCallsLock = Any()
    @Volatile private var closed = false

    fun detect(
        imageUrls: MutableList<String>,
        prompt: String,
        allowEarlyReject: Boolean
    ): AssessmentResult {
        val body = try {
            buildDetectionRequest(model, detail, imageUrls, prompt)
                .toString()
                .toRequestBody(JSON_MEDIA_TYPE)
        } finally {
            // RequestBody owns encoded bytes now; release duplicate Base64 strings before I/O.
            imageUrls.clear()
        }

        return withTrackedCall(authorizedRequest(body), AiRequestIdentity(
            "openai", endpoint, model, "pothole_binary_assessment", NativeDetectionContract.MAX_OUTPUT_TOKENS.toLong()
        )) { call ->
            val response = try {
                call.execute()
            } catch (error: IOException) {
                throw retryableFailure("OpenAI detection connection failed", error)
            }
            response.use {
                if (!response.isSuccessful) {
                    throw httpFailure(
                        response.code,
                        response.header("Retry-After"),
                        RequestKind.DETECTION
                    )
                }
                val responseBody = response.body
                    ?: throw retryableFailure("Empty response body from OpenAI")
                var earlyRejection: DetectionRejectionReason? = null
                val stream = try {
                    readSse(call, responseBody, "OpenAI detection response") { text ->
                        if (!allowEarlyReject || debug) return@readSse false
                        findEarlyRejection(text)?.let {
                            earlyRejection = it
                            true
                        } ?: false
                    }
                } catch (error: NativeInferenceException) {
                    throw error
                } catch (error: IOException) {
                    throw retryableFailure("OpenAI detection stream was interrupted", error)
                }

                val assessment = try {
                    completeDetectionAssessment(
                        text = stream.text,
                        streamCompleted = stream.completed,
                        earlyRejection = earlyRejection
                    )
                } catch (error: Exception) {
                    throw normalizeRetryableFailure(
                        error,
                        "OpenAI detection response was incomplete"
                    )
                }
                consecutiveRetryableFailures.set(0)
                assessment
            }
        }
    }

    fun verifyRepair(imageUrls: MutableList<String>, prompt: String): RepairModelAssessment {
        val body = try {
            buildRepairRequest(model, detail, imageUrls, prompt)
                .toString()
                .toRequestBody(JSON_MEDIA_TYPE)
        } finally {
            imageUrls.clear()
        }

        return withTrackedCall(authorizedRequest(body), AiRequestIdentity(
            "openai", endpoint, model, "road_repair_assessment", NativeRepairContract.MAX_OUTPUT_TOKENS.toLong()
        )) { call ->
            val response = try {
                call.execute()
            } catch (error: IOException) {
                throw retryableFailure("OpenAI repair-check connection failed", error)
            }
            response.use {
                if (!response.isSuccessful) {
                    throw httpFailure(
                        response.code,
                        response.header("Retry-After"),
                        RequestKind.REPAIR
                    )
                }
                val responseBody = response.body
                    ?: throw retryableFailure("Empty repair-check response from OpenAI")
                val stream = try {
                    readSse(call, responseBody, "OpenAI repair-check response")
                } catch (error: NativeInferenceException) {
                    throw error
                } catch (error: IOException) {
                    throw retryableFailure("OpenAI repair-check stream was interrupted", error)
                }

                val assessment = try {
                    if (!stream.completed) {
                        throw NativeInferenceException("OpenAI repair-check stream was interrupted")
                    }
                    NativeRepairContract.parseAssessment(stream.text)
                } catch (error: Exception) {
                    throw normalizeRetryableFailure(
                        error,
                        "OpenAI repair-check response was incomplete"
                    )
                }
                consecutiveRetryableFailures.set(0)
                assessment
            }
        }
    }

    private fun readSse(
        call: Call,
        responseBody: ResponseBody,
        responseName: String,
        stopWhen: ((String) -> Boolean)? = null
    ): StreamText {
        val output = NativeSseTextAccumulator()
        var completed = false
        try {
            NativeBoundedSseReader(sseLimits).read(responseBody.byteStream(), call::isCanceled) { payload ->
                if (payload.trim() == "[DONE]") {
                    completed = true
                    return@read true
                }
                val event = try {
                    NativeInferenceJsonSyntax.requireObject(payload)
                    val tokens = JSONTokener(payload)
                    val value = tokens.nextValue()
                    if (value !is JSONObject || tokens.nextClean() != '\u0000') throw NativeSseSafetyException()
                    value
                } catch (_: Exception) { throw NativeSseSafetyException() }
                val type = event.opt("type")
                if (type !is String || !type.startsWith("response.") || type.length > 128) {
                    throw NativeSseSafetyException()
                }
                if (type == "response.failed" || type == "response.incomplete") throw NativeSseSafetyException()
                if (type == "response.completed") {
                    completed = true
                    return@read true
                }
                if (type != "response.output_text.delta") return@read false
                val delta = event.opt("delta")
                if (delta !is String || !Charsets.UTF_8.newEncoder().canEncode(delta)) throw NativeSseSafetyException()
                if (!output.append(delta)) {
                    throw NativeInferenceException(
                        "$responseName exceeded the 64 KiB safety limit", suspendInference = true
                    )
                }
                stopWhen?.invoke(output.snapshot()) == true
            }
            if (completed) NativeInferenceJsonSyntax.requireObject(output.snapshot())
        } catch (_: NativeSseSafetyException) {
            throw NativeInferenceException(
                "$responseName violated the byte, line, event or protocol safety limit",
                suspendInference = true
            )
        } finally {
            // Terminal, early-negative, malformed, limit, deadline and cancellation paths
            // all end the HTTP operation. Never read indefinitely after a terminal marker.
            call.cancel()
            responseBody.close()
        }
        return StreamText(output.snapshot(), completed)
    }

    private fun authorizedRequest(body: okhttp3.RequestBody): Request = Request.Builder()
        .url(endpoint)
        .addHeader("Authorization", "Bearer $apiKey")
        .addHeader("Content-Type", "application/json")
        .post(NonReplayableAiBody(body))
        .build()

    private inline fun <T> withTrackedCall(request: Request, identity: AiRequestIdentity, block: (Call) -> T): T {
        if (closed) throw IOException("Detection engine is closed")
        try {
            budgetGate(identity)
        } catch (_: AiUsageLimitException) {
            throw NativeInferenceException("AI usage limit reached.", suspendInference = true)
        }
        val call = okHttpClient.newCall(request)
        call.timeout().timeout(sseLimits.deadlineMs, TimeUnit.MILLISECONDS)
        synchronized(activeCallsLock) {
            if (closed) throw IOException("Detection engine is closed")
            activeCalls.add(call)
        }
        return try {
            block(call)
        } finally {
            synchronized(activeCallsLock) { activeCalls.remove(call) }
        }
    }

    private fun httpFailure(
        code: Int,
        retryAfter: String?,
        kind: RequestKind
    ): NativeInferenceException {
        val repair = kind == RequestKind.REPAIR
        val message = when (code) {
            401 -> "OpenAI rejected the API key"
            403 -> "This API key cannot use the selected model"
            400 -> if (repair) {
                "OpenAI rejected the repair model or structured-output request (400)"
            } else {
                "OpenAI rejected the model or structured-output request (400)"
            }
            404 -> if (repair) {
                "The selected OpenAI repair model or endpoint was not found (404)"
            } else {
                "The selected OpenAI model or endpoint was not found (404)"
            }
            429 -> "OpenAI rate limit or credit exhausted"
            in 500..599 -> "OpenAI is temporarily unavailable"
            else -> if (repair) {
                "OpenAI rejected the repair check ($code)"
            } else {
                "OpenAI rejected the detection request ($code)"
            }
        }
        val retryDelay = if (isTransientInferenceFailure(code)) {
            inferenceRetryDelay(code, retryAfter, consecutiveRetryableFailures.getAndIncrement())
        } else {
            null
        }
        return NativeInferenceException(
            message,
            suspendInference = !isTransientInferenceFailure(code),
            retryAfterMs = retryDelay
        )
    }

    private fun retryableFailure(
        message: String,
        cause: Throwable? = null
    ): NativeInferenceException = NativeInferenceException(
        message,
        retryAfterMs = inferenceRetryDelay(
            0,
            null,
            consecutiveRetryableFailures.getAndIncrement()
        ),
        cause = cause
    )

    private fun normalizeRetryableFailure(
        error: Throwable,
        fallbackMessage: String
    ): NativeInferenceException {
        if (error is NativeInferenceException &&
            (error.suspendInference || error.retryAfterMs != null)
        ) return error
        return retryableFailure(error.message?.takeIf(String::isNotBlank) ?: fallbackMessage, error)
    }

    fun close() {
        val calls = synchronized(activeCallsLock) {
            closed = true
            activeCalls.toList()
        }
        var firstFailure: Throwable? = null
        fun attempt(block: () -> Unit) {
            runCatching(block).onFailure { error ->
                if (firstFailure == null) firstFailure = error
            }
        }
        calls.forEach { call -> attempt(call::cancel) }
        attempt(okHttpClient.dispatcher::cancelAll)
        attempt(okHttpClient.connectionPool::evictAll)
        firstFailure?.let { throw it }
    }

    private enum class RequestKind { DETECTION, REPAIR }

    companion object {
        private const val OAI_URL = "https://api.openai.com/v1/responses"
        private val JSON_MEDIA_TYPE = "application/json".toMediaType()

        private fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .retryOnConnectionFailure(false)
            .followRedirects(false)
            .followSslRedirects(false)
            .callTimeout(35, TimeUnit.SECONDS)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }
}

private data class StreamText(val text: String, val completed: Boolean)

/** Bounded text buffer for untrusted streamed model output. */
internal class NativeSseTextAccumulator(
    private val maxUtf8Bytes: Int = MAX_UTF8_BYTES
) {
    private val text = StringBuilder(minOf(maxUtf8Bytes.coerceAtLeast(1), 4 * 1024))
    private var utf8Bytes = 0

    init {
        require(maxUtf8Bytes > 0) { "SSE text limit must be positive" }
    }

    fun append(delta: String): Boolean {
        val deltaBytes = delta.toByteArray(Charsets.UTF_8).size
        if (deltaBytes > maxUtf8Bytes - utf8Bytes) return false
        text.append(delta)
        utf8Bytes += deltaBytes
        return true
    }

    fun snapshot(): String = text.toString()

    companion object {
        const val MAX_UTF8_BYTES = 64 * 1024
    }
}

internal fun isTransientInferenceFailure(code: Int): Boolean =
    code == 0 || code in setOf(408, 409, 425, 429) || code in 500..599

internal fun inferenceRetryDelay(
    code: Int,
    retryAfterHeader: String?,
    consecutiveFailure: Int
): Long? {
    if (!isTransientInferenceFailure(code)) return null
    val maxDelayMs = 60_000L
    val headerDelay = retryAfterHeader?.trim()?.toLongOrNull()
        ?.takeIf { it >= 0L }
        ?.let { seconds ->
            if (seconds > maxDelayMs / 1_000L) maxDelayMs else seconds * 1_000L
        }
    val baseDelay = when (code) {
        429 -> 5_000L
        0 -> 10_000L
        else -> 2_000L
    }
    val exponentialDelay = (baseDelay * (1L shl consecutiveFailure.coerceIn(0, 5)))
        .coerceAtMost(maxDelayMs)
    return maxOf(headerDelay ?: 0L, exponentialDelay)
}
