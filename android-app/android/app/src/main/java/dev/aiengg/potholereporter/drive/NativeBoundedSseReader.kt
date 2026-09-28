package dev.aiengg.potholereporter.drive

import java.io.IOException
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction

internal data class NativeSseLimits(
    val responseBytes: Int = 64 * 1024,
    val lineBytes: Int = 32 * 1024,
    val eventBytes: Int = 48 * 1024,
    val events: Int = 512,
    val deadlineMs: Long = 35_000L
) {
    init {
        require(responseBytes in 1..64 * 1024 && lineBytes in 1..32 * 1024 &&
            eventBytes in 1..48 * 1024 && events in 1..512 && deadlineMs in 1..35_000L)
    }
}

internal class NativeSseSafetyException : IOException("Inference stream violated its safety budget or protocol")

/** Fixed-size byte framing before UTF-8 or JSON allocation. Owns and closes its input. */
internal class NativeBoundedSseReader(
    private val limits: NativeSseLimits = NativeSseLimits(),
    private val nanoTime: () -> Long = System::nanoTime
) {
    fun read(
        input: InputStream,
        cancelled: () -> Boolean = { false },
        onEvent: (String) -> Boolean
    ) {
        input.use { stream ->
            val started = nanoTime()
            val deadlineNs = limits.deadlineMs * 1_000_000L
            fun checkActive() {
                if (cancelled()) throw IOException("Inference stream cancelled")
                if (nanoTime() - started >= deadlineNs) throw IOException("Inference stream deadline exceeded")
            }
            val chunk = ByteArray(4 * 1024)
            val line = ByteArray(limits.lineBytes)
            val event = ByteArray(limits.eventBytes)
            var lineSize = 0
            var eventSize = 0
            var hasData = false
            var eventCount = 0
            var total = 0
            var skipLf = false
            fun decode(bytes: ByteArray, length: Int): String = try {
                Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes, 0, length)).toString()
            } catch (_: Exception) { throw NativeSseSafetyException() }
            fun processLine(): Boolean {
                if (lineSize == 0) {
                    if (!hasData) return false
                    if (eventCount >= limits.events) throw NativeSseSafetyException()
                    eventCount++
                    val payload = decode(event, eventSize)
                    eventSize = 0
                    hasData = false
                    checkActive()
                    val terminal = onEvent(payload)
                    checkActive()
                    return terminal
                }
                // Decode only a bounded complete line, including ignored fields/comments.
                val value = decode(line, lineSize)
                lineSize = 0
                if (value.startsWith(':')) return false
                val colon = value.indexOf(':')
                if (colon < 0) throw NativeSseSafetyException()
                val field = value.substring(0, colon)
                val dataStart = colon + 1 + if (value.getOrNull(colon + 1) == ' ') 1 else 0
                when (field) {
                    "data" -> {
                        val size = value.substring(dataStart).toByteArray(Charsets.UTF_8)
                        val separator = if (hasData) 1 else 0
                        if (separator > limits.eventBytes - eventSize ||
                            size.size > limits.eventBytes - eventSize - separator) throw NativeSseSafetyException()
                        if (hasData) event[eventSize++] = 10
                        size.copyInto(event, eventSize)
                        eventSize += size.size
                        hasData = true
                    }
                    "event" -> if (value.substring(dataStart).isEmpty()) throw NativeSseSafetyException()
                    "id" -> if (value.substring(dataStart).contains('\u0000')) throw NativeSseSafetyException()
                    "retry" -> if (!value.substring(dataStart).matches(Regex("[0-9]+"))) throw NativeSseSafetyException()
                    else -> throw NativeSseSafetyException()
                }
                return false
            }
            while (true) {
                checkActive()
                // At most one overflow byte is read, never buffered as a line/event.
                val count = stream.read(chunk, 0, minOf(chunk.size, limits.responseBytes - total + 1))
                checkActive()
                if (count == -1) {
                    if (lineSize != 0 || hasData) throw NativeSseSafetyException()
                    return
                }
                if (count <= 0 || count > limits.responseBytes - total) throw NativeSseSafetyException()
                total += count
                for (index in 0 until count) {
                    checkActive()
                    val byte = chunk[index]
                    when (byte.toInt() and 255) {
                        13 -> { if (processLine()) return; skipLf = true }
                        10 -> { if (!skipLf && processLine()) return; skipLf = false }
                        else -> {
                            skipLf = false
                            if (lineSize >= limits.lineBytes) throw NativeSseSafetyException()
                            line[lineSize++] = byte
                        }
                    }
                }
            }
        }
    }
}
