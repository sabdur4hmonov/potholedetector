package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.security.*
import java.io.File
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class NativeAiBudgetTransportTest {
    @get:Rule val storage = TemporaryFolder()
    private fun images()= mutableListOf("data:image/jpeg;base64,dGVzdA==")

    @Test fun budgetExhaustionRejectsBeforeAnotherHttpTransmission() {
        val server=MockWebServer(); server.start()
        val dir=File(storage.root.canonicalFile,"budget")
        val transport=NativeInferenceTransport("dummy-not-a-production-key","gpt-5.6","high",false,
            endpoint=server.url("/v1/responses").toString(),budgetGate={
                testAiBudget(dir).reserve(it.copy(endpoint=AiOutputPolicy.ENDPOINT))
            })
        try {
            repeat(21) {
                server.enqueue(MockResponse().setResponseCode(401))
                assertThrows(NativeInferenceException::class.java) {transport.detect(images(),"synthetic",false)}
                val request=JSONObject(server.takeRequest().body.readUtf8())
                assertEquals(1536,request.getInt("max_output_tokens"))
            }
            val error=assertThrows(NativeInferenceException::class.java) {transport.detect(images(),"synthetic",false)}
            assertEquals("AI usage limit reached.",error.message)
            assertTrue(error.suspendInference); assertEquals(21,server.requestCount)
        } finally {transport.close();server.shutdown()}
    }

    @Test fun transportWithoutAuthoritativeGateFailsClosed() {
        val server=MockWebServer(); server.start()
        val transport=NativeInferenceTransport("dummy-not-a-production-key","gpt-5.6","high",false,
            endpoint=server.url("/v1/responses").toString())
        try {
            val error=assertThrows(NativeInferenceException::class.java) {transport.detect(images(),"synthetic",false)}
            assertTrue(error.suspendInference); assertEquals(0,server.requestCount)
        } finally {transport.close();server.shutdown()}
    }

    @Test fun wrongProviderEndpointFailsBeforeHttp() {
        val server=MockWebServer();server.start()
        val transport=NativeInferenceTransport("dummy-not-a-production-key","gpt-5.6","high",false,
            endpoint=server.url("/v1/responses").toString(),budgetGate={
                testAiBudget(File(storage.root.canonicalFile,"budget")).reserve(it)
            })
        try {
            assertThrows(NativeInferenceException::class.java) {transport.detect(images(),"synthetic",false)}
            assertEquals(0,server.requestCount)
        } finally {transport.close();server.shutdown()}
    }

    @Test fun serviceUnavailableCannotCauseAnUngatedImplicitFollowUp() {
        val server=MockWebServer();server.start();var reservations=0
        val transport=NativeInferenceTransport("dummy-not-a-production-key","gpt-5.6","high",false,
            endpoint=server.url("/v1/responses").toString(),budgetGate={
                testAiBudget(File(storage.root.canonicalFile,"budget")).reserve(it.copy(endpoint=AiOutputPolicy.ENDPOINT))
                reservations++
            })
        try {
            server.enqueue(MockResponse().setResponseCode(503).setHeader("Retry-After","0"))
            server.enqueue(MockResponse().setResponseCode(401))
            assertThrows(NativeInferenceException::class.java) {transport.detect(images(),"synthetic",false)}
            assertEquals(1,reservations);assertEquals(1,server.requestCount)
        } finally {transport.close();server.shutdown()}
    }
}
