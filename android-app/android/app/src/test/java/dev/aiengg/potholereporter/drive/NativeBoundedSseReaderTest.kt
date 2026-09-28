package dev.aiengg.potholereporter.drive

import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import org.junit.Assert.*
import org.junit.Test

class NativeBoundedSseReaderTest {
    private class Tracked(bytes: ByteArray, private val singleByte: Boolean = false) : ByteArrayInputStream(bytes) {
        var closed = false
        var reads = 0
        override fun read(b: ByteArray, off: Int, len: Int): Int {
            reads++
            return super.read(b, off, if (singleByte) minOf(1, len) else len)
        }
        override fun close() { closed = true; super.close() }
    }
    private fun stream(value: String) = Tracked(value.toByteArray(Charsets.UTF_8))
    private fun rejected(value: String, limits: NativeSseLimits = NativeSseLimits()) {
        val input = stream(value)
        assertThrows(NativeSseSafetyException::class.java) { NativeBoundedSseReader(limits).read(input) { false } }
        assertTrue(input.closed)
    }

    @Test fun normalEventsAndTerminalCloseInput() {
        val input = stream("event: response.created\ndata: {}\n\ndata: [DONE]\n\n")
        val events = mutableListOf<String>()
        NativeBoundedSseReader().read(input) { events.add(it); it == "[DONE]" }
        assertEquals(listOf("{}", "[DONE]"), events); assertTrue(input.closed)
    }
    @Test fun crlfAndBareCrAreValidFraming() {
        for (sep in listOf("\r\n", "\r", "\n")) {
            val input = stream("data: {}$sep$sep")
            var count = 0
            NativeBoundedSseReader().read(input) { count++; true }
            assertEquals(1, count); assertTrue(input.closed)
        }
    }
    @Test fun splitUtf8AndMultilineEventDecodeStrictly() {
        val input = Tracked("data: {\"text\":\"道路\",\ndata: \"ok\":true}\n\n".toByteArray(), true)
        var value = ""
        NativeBoundedSseReader().read(input) { value = it; true }
        assertEquals("{\"text\":\"道路\",\n\"ok\":true}", value); assertTrue(input.closed)
    }
    @Test fun hugeUnterminatedLineNeverMaterializesAsString() {
        var readBytes = 0; var closed = false; var largestRead = 0
        val generated = object : InputStream() {
            override fun read(): Int = 'a'.code
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                largestRead = maxOf(largestRead, len); readBytes += len
                java.util.Arrays.fill(b, off, off + len, 'a'.code.toByte()); return len
            }
            override fun close() { closed = true }
        }
        assertThrows(NativeSseSafetyException::class.java) {
            NativeBoundedSseReader(NativeSseLimits(lineBytes = 32)).read(generated) { fail("No event may materialize"); false }
        }
        assertTrue(closed); assertTrue(readBytes <= 4096); assertTrue(largestRead <= 4096)
    }
    @Test fun cumulativeBytesIncludeIgnoredCommentsAndUtf8() {
        rejected(": " + "界".repeat(20) + "\n\n", NativeSseLimits(responseBytes = 32))
        rejected(": a\n".repeat(20), NativeSseLimits(responseBytes = 32))
    }
    @Test fun cumulativeLimitReadsAtMostOneOverflowByte() {
        val input = stream(": a\n".repeat(20000))
        assertThrows(NativeSseSafetyException::class.java) {
            NativeBoundedSseReader().read(input) { false }
        }
        assertEquals(80000 - 65537, input.available()); assertTrue(input.closed)
    }
    @Test fun exactCumulativeAndLineBoundaryAreInclusive() {
        val input = stream("data: {}\n\n")
        var count = 0
        NativeBoundedSseReader(NativeSseLimits(responseBytes = 10, lineBytes = 8, eventBytes = 2)).read(input) { count++; false }
        assertEquals(1, count); assertTrue(input.closed)
    }
    @Test fun manyTinyEventsHitCountBeforeByteCeiling() {
        rejected("data: {}\n\n".repeat(513))
    }
    @Test fun eventLimitCannotBeBypassedWithMultipleDataLines() {
        rejected("data: 12345\ndata: 67890\n\n", NativeSseLimits(eventBytes = 10))
    }
    @Test fun malformedFramingAndPartialEventFailClosed() {
        for (value in listOf("garbage\n", "unknown: x\n", "data: {}\n", "data: {}", "retry: -1\n", "event:\n", "id: \u0000\n")) rejected(value)
    }
    @Test fun malformedUtf8FailsBeforeDispatch() {
        val input = Tracked(byteArrayOf(100, 97, 116, 97, 58, 32, 0xc3.toByte(), 0x28, 10, 10))
        assertThrows(NativeSseSafetyException::class.java) { NativeBoundedSseReader().read(input) { fail(); false } }
        assertTrue(input.closed)
    }
    @Test fun cancellationStopsEventsAndClosesInput() {
        val input = stream("data: {}\n\ndata: {}\n\n")
        var cancel = false; var count = 0
        assertThrows(IOException::class.java) {
            NativeBoundedSseReader().read(input, { cancel }) { count++; cancel = true; false }
        }
        assertEquals(1, count); assertTrue(input.closed)
    }
    @Test fun deadlineIncludesEventProcessing() {
        val input = stream("data: {}\n\n")
        var time = 0L
        assertThrows(IOException::class.java) {
            NativeBoundedSseReader(NativeSseLimits(deadlineMs = 1), { time }).read(input) { time = 1_000_000L; true }
        }
        assertTrue(input.closed)
    }
    @Test fun activeChunksCannotExtendDeadline() {
        val input = Tracked(":a\n".repeat(100).toByteArray(), true)
        var time = 0L
        assertThrows(IOException::class.java) {
            NativeBoundedSseReader(NativeSseLimits(deadlineMs = 2), { time += 100_000L; time }).read(input) { false }
        }
        assertTrue(input.closed); assertTrue(input.available() > 0)
    }
    @Test fun terminalStopsWithoutReadingTrailingHostileData() {
        val input = stream("data: [DONE]\n\n" + "x".repeat(100000))
        NativeBoundedSseReader().read(input) { true }
        assertEquals(1, input.reads); assertTrue(input.closed); assertTrue(input.available() > 0)
    }
    @Test fun interruptedInputAlwaysCloses() {
        var closed = false
        val input = object : InputStream() {
            override fun read(): Int = throw IOException("Synthetic interruption")
            override fun close() { closed = true }
        }
        assertThrows(IOException::class.java) { NativeBoundedSseReader().read(input) { false } }
        assertTrue(closed)
    }
    @Test fun integerOverflowAndLimitRelaxationRejectedBeforeAllocation() {
        assertThrows(IllegalArgumentException::class.java) { NativeSseLimits(responseBytes = Int.MAX_VALUE) }
        assertThrows(IllegalArgumentException::class.java) { NativeSseLimits(lineBytes = -1) }
        assertThrows(IllegalArgumentException::class.java) { NativeSseLimits(eventBytes = Int.MAX_VALUE) }
        assertThrows(IllegalArgumentException::class.java) { NativeSseLimits(events = Int.MAX_VALUE) }
        assertThrows(IllegalArgumentException::class.java) { NativeSseLimits(deadlineMs = Long.MAX_VALUE) }
    }
    @Test fun strictJsonGrammarAcceptsNormalBoundedObjects() {
        for (value in listOf("{}", "{\"type\":\"response.created\"}",
            "{\"output\":[null,true,false,-1.2e+3,{\"value\":\"道路\\n\\u0041\"}]}")) {
            NativeInferenceJsonSyntax.requireObject(value)
        }
    }
    @Test fun permissiveOrMalformedJsonCannotReachJSONObject() {
        for (value in listOf("[]", "{'type':'response.created'}", "{type:1}", "{} garbage", "{\"a\":01}",
            "{\"a\":true,}", "{\"a\":1.}", "{\"a\":1e}", "{\"a\":\"\\x01\"}", "{\"a\":\"\\u12\"}")) {
            assertThrows(NativeSseSafetyException::class.java) { NativeInferenceJsonSyntax.requireObject(value) }
        }
    }
    @Test fun deeplyNestedProtocolJsonCannotOverflowTheStack() {
        val value = "{\"a\":" + "[".repeat(1000) + "0" + "]".repeat(1000) + "}"
        assertThrows(NativeSseSafetyException::class.java) { NativeInferenceJsonSyntax.requireObject(value) }
    }
}
