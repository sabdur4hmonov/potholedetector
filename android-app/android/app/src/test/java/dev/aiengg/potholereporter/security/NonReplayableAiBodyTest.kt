package dev.aiengg.potholereporter.security

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test

class NonReplayableAiBodyTest {
    @Test fun oneTransmissionPreservesBodyMetadataAndContent() {
        val delegate="synthetic input".toRequestBody("application/json".toMediaType())
        val body=NonReplayableAiBody(delegate)
        assertTrue(body.isOneShot()); assertEquals(delegate.contentType(),body.contentType())
        assertEquals(delegate.contentLength(),body.contentLength())
        val sink=Buffer(); body.writeTo(sink); assertEquals("synthetic input",sink.readUtf8())
    }
    @Test fun accidentalSecondTransmissionStopsBeforeWritingAnyInput() {
        val body=NonReplayableAiBody("synthetic input".toRequestBody())
        body.writeTo(Buffer()); val second=Buffer()
        assertThrows(AiUsageLimitException::class.java) {body.writeTo(second)}
        assertEquals(0L,second.size)
    }
}
