package dev.aiengg.potholereporter.security

import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test

class NativeOpenAiRequestPolicyTest {
    @Test
    fun acceptsOnlyBoundedNonRetainedRequestsForExistingApplicationModels() {
        val valid = NativeOpenAiRequestPolicy.validate(
            """{"model":"gpt-5-mini","input":"unit input","store":false,"stream":false}""",
            false
        )
        assertFalse(valid.stream)
        val rejected = listOf(
            "",
            "not-json",
            """{"model":"unapproved-model","input":"unit input","store":false}""",
            """{"model":"gpt-5-mini","input":"unit input","store":true}""",
            """{"model":"gpt-5-mini","store":false}""",
            """{"model":"gpt-5-mini","input":"unit input","store":false,"stream":true}""",
            " ".repeat(40 * 1024 * 1024 + 1)
        )
        for (body in rejected) {
            assertThrows(IllegalArgumentException::class.java) {
                NativeOpenAiRequestPolicy.validate(body, false)
            }
        }
    }
}
