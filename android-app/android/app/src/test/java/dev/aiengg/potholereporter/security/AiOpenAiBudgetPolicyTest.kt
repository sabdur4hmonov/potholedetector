package dev.aiengg.potholereporter.security

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AiOpenAiBudgetPolicyTest {
    @get:Rule val temporary = TemporaryFolder()
    private fun body(tokens: Any? = null, purpose: String = "pothole_binary_assessment"): JSONObject = JSONObject().apply {
        put("model", "gpt-5-mini"); put("input", "synthetic test input"); put("store", false); put("stream", false)
        put("text", JSONObject().put("format", JSONObject().put("name", purpose)))
        if (tokens != null) put("max_output_tokens", tokens)
    }

    @Test fun missingTokensAreDefaultedAndHighJsTokensAreClampedNatively() {
        for ((purpose, maximum) in listOf("pothole_binary_assessment" to 1536L,
            "road_repair_verification" to 768L, "tender_match" to 512L)) {
            for (request in listOf(body(purpose=purpose), body(999999, purpose))) {
                val result=NativeOpenAiRequestPolicy.validate(request.toString(), false)
                assertEquals(maximum, JSONObject(result.body).getLong("max_output_tokens"))
                assertEquals(maximum, result.identity.outputTokens)
                AiOutputPolicy.validate(result.identity)
            }
        }
    }

    @Test fun malformedTokenTypesNegativeValuesAndOverflowReject() {
        for (token in listOf(-1, 0, 1.5, "1536", true, JSONObject.NULL, Long.MAX_VALUE)) {
            assertThrows(IllegalArgumentException::class.java) { NativeOpenAiRequestPolicy.validate(body(token).toString(), false) }
        }
    }

    @Test fun paidToolsContinuationsAndClientUsageAreNotApplicationRequests() {
        for (field in listOf("tools", "tool_choice", "previous_response_id", "conversation", "background", "service_tier", "usage")) {
            val request=body(1536).put(field, "untrusted")
            assertThrows(IllegalArgumentException::class.java) { NativeOpenAiRequestPolicy.validate(request.toString(), false) }
        }
        assertThrows(IllegalArgumentException::class.java) { NativeOpenAiRequestPolicy.validate(body(purpose="unknown").toString(), false) }
    }

    @Test fun nativeAndValidatedJsRequestsShareAccountingIncludingRetries() {
        val dir=File(temporary.newFolder().canonicalFile,"budget"); var sent=0
        repeat(10) { testAiBudget(dir).reserve(AiRequestIdentity("openai", AiOutputPolicy.ENDPOINT,
            "gpt-5.6", "pothole_binary_assessment", 1536)); sent++ }
        repeat(11) {
            val request=NativeOpenAiRequestPolicy.validate(body(999999).toString(),false)
            testAiBudget(dir).reserve(request.identity); sent++
        }
        val retry=NativeOpenAiRequestPolicy.validate(body(999999).toString(),false)
        assertThrows(AiUsageLimitException::class.java) { testAiBudget(dir).reserve(retry.identity); sent++ }
        assertEquals(21,sent)
    }

    @Test fun hostileClientUsageCannotRefundReservation() {
        val dir=File(temporary.newFolder().canonicalFile,"budget")
        repeat(21) { testAiBudget(dir).reserve(NativeOpenAiRequestPolicy.validate(body().toString(),false).identity) }
        assertThrows(IllegalArgumentException::class.java) {
            NativeOpenAiRequestPolicy.validate(body().put("usage", JSONObject().put("output_tokens", -1536)).toString(),false)
        }
        assertThrows(AiUsageLimitException::class.java) {
            testAiBudget(dir).reserve(NativeOpenAiRequestPolicy.validate(body().toString(),false).identity)
        }
    }
}
