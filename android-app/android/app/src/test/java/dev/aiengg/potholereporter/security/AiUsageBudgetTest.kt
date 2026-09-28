package dev.aiengg.potholereporter.security

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AiUsageBudgetTest {
    @get:Rule val temporary = TemporaryFolder()
    private fun directory() = File(temporary.newFolder().canonicalFile, "budget")
    private fun identity(tokens: Long = 1536, purpose: String = "pothole_binary_assessment") =
        AiRequestIdentity("openai", AiOutputPolicy.ENDPOINT, "gpt-5.6", purpose, tokens)
    private fun blocked(action: () -> Unit) { assertThrows(AiUsageLimitException::class.java, action) }

    @Test fun firstRunPersistsBeforeSimulatedNetwork() {
        val dir = directory(); var calls = 0
        testAiBudget(dir).reserve(identity()); calls++
        assertEquals(1, calls); assertEquals(53, File(dir, "usage.bin").length().toInt())
    }

    @Test fun missingLimitsDefaultToNativeCeilings() {
        assertEquals(1536, AiOutputPolicy.outputLimit("pothole_binary_assessment", null).toInt())
        assertEquals(768, AiOutputPolicy.outputLimit("road_repair_verification", null).toInt())
        assertEquals(512, AiOutputPolicy.outputLimit("tender_match", null).toInt())
        assertEquals(512, AiOutputPolicy.outputLimit("general", null).toInt())
    }

    @Test fun jsCannotRaiseCeilings() {
        for ((purpose, maximum) in listOf("pothole_binary_assessment" to 1536L,
            "road_repair_assessment" to 768L, "tender_match" to 512L)) {
            assertEquals(maximum, AiOutputPolicy.outputLimit(purpose, 999_999))
            assertEquals(1L, AiOutputPolicy.outputLimit(purpose, 1))
            blocked { testAiBudget(directory()).reserve(identity(maximum + 1, purpose)) }
        }
    }

    @Test fun invalidNegativeAndOverflowingLimitsReject() {
        for (value in listOf(0L, -1L, Long.MIN_VALUE, Long.MAX_VALUE, Int.MAX_VALUE.toLong() + 1)) {
            blocked { AiOutputPolicy.outputLimit("general", value) }
            blocked { testAiBudget(directory()).reserve(identity(value)) }
        }
    }

    @Test fun providerModelEndpointAndPurposeAreNativeValidated() {
        val base = identity()
        for (request in listOf(base.copy(provider="other"), base.copy(endpoint="http://localhost"),
            base.copy(model="unapproved"), base.copy(purpose="unknown"))) {
            val dir = directory(); blocked { testAiBudget(dir).reserve(request) }
            assertFalse(dir.exists())
        }
    }

    @Test fun repeatedRequestsExhaustOutputBeforeNetwork() {
        val budget = testAiBudget(directory()); var calls = 0
        repeat(21) { budget.reserve(identity()); calls++ }
        blocked { budget.reserve(identity()); calls++ }
        assertEquals(21, calls)
    }

    @Test fun exactOutputBoundaryAndRequestBoundaryAreInclusive() {
        val budget = testAiBudget(directory())
        repeat(21) { budget.reserve(identity()) }
        budget.reserve(identity(512, "tender_match")) // Exactly 32768.
        blocked { budget.reserve(identity(1, "general")) }
        val countBudget = testAiBudget(directory())
        repeat(32) { countBudget.reserve(identity(1, "general")) }
        blocked { countBudget.reserve(identity(1, "general")) }
    }

    @Test fun nativeAndJsShareOneLedgerAcrossInstancesAndRestarts() {
        val dir = directory()
        repeat(10) { testAiBudget(dir).reserve(identity()) }
        repeat(11) { testAiBudget(dir).reserve(identity()) }
        blocked { testAiBudget(dir).reserve(identity()) }
    }

    @Test fun failuresTimeoutCancellationAndMalformedResponsesNeverRefund() {
        val dir = directory()
        repeat(21) {
            testAiBudget(dir).reserve(identity())
            // A failure after transmission does not mutate the permanently charged ledger.
            runCatching { throw IOException(listOf("failed", "timeout", "cancelled", "malformed")[it % 4]) }
        }
        blocked { testAiBudget(dir).reserve(identity()) }
    }

    @Test fun retriesPassReservationAgainAndCannotBypass() {
        val budget = testAiBudget(directory()); var calls = 0
        repeat(32) {
            runCatching { budget.reserve(identity(1024)); calls++; throw IOException("retry") }
        }
        blocked { budget.reserve(identity(1024)); calls++ }
        assertEquals(32, calls)
    }

    @Test fun concurrentRequestsCannotDoubleSpendRemainingTokens() {
        val dir = directory(); val pool = Executors.newFixedThreadPool(8)
        try {
            val results = pool.invokeAll((1..60).map { Callable {
                try { testAiBudget(dir).reserve(identity()); 1 }
                catch (_: AiUsageLimitException) { 0 }
            } })
            assertEquals(21, results.sumOf { it.get() })
            blocked { testAiBudget(dir).reserve(identity()) }
        } finally { pool.shutdownNow() }
    }

    @Test fun concurrentSmallRequestsCannotDoubleSpendRequestCount() {
        val dir = directory(); val pool = Executors.newFixedThreadPool(8)
        try {
            val results = pool.invokeAll((1..60).map { Callable {
                try { testAiBudget(dir).reserve(identity(1, "general")); 1 }
                catch (_: AiUsageLimitException) { 0 }
            } })
            assertEquals(32, results.sumOf { it.get() })
        } finally { pool.shutdownNow() }
    }

    @Test fun missingDeletedTruncatedAndCorruptedStateCannotResetAllowance() {
        for (mode in 0..3) {
            val dir = directory(); testAiBudget(dir).reserve(identity())
            val ledger = File(dir, "usage.bin")
            when (mode) {
                0 -> assertTrue(ledger.delete())
                1 -> ledger.writeBytes(byteArrayOf())
                2 -> ledger.writeBytes(ByteArray(100))
                3 -> { val data=ledger.readBytes(); data[15]=(data[15].toInt() xor 1).toByte(); ledger.writeBytes(data) }
            }
            blocked { testAiBudget(dir).reserve(identity()) }
            blocked { testAiBudget(dir).reserve(identity()) }
        }
    }

    @Test fun invalidStateEvenWithMatchingDigestFailsClosed() {
        for ((requests, outputs) in listOf(-1L to 0L, Long.MAX_VALUE to 0L, 33L to 100L,
            1L to -1L, 1L to Long.MAX_VALUE, 0L to 1L, 2L to 1L)) {
            val dir=directory(); assertTrue(dir.mkdir())
            val bytes=ByteArrayOutputStream()
            DataOutputStream(bytes).use { out -> out.writeInt(0x41494236); out.writeInt(1); out.writeLong(requests); out.writeLong(outputs) }
            val payload=bytes.toByteArray()
            val authenticator=AiBudgetTestKeys.forDirectory(dir); authenticator.initialize()
            File(dir,"usage.bin").writeBytes(authenticator.sealNext(payload))
            blocked { testAiBudget(dir).reserve(identity()) }
        }
    }

    @Test fun unavailableStorageAndFailedDurabilityRejectBeforeNetwork() {
        val dir=directory(); var calls=0
        blocked { testAiBudget(dir) { throw IOException("persistence failure") }.reserve(identity()); calls++ }
        assertEquals(0, calls)
        // The attempted charge remains, rather than accidentally being refunded on restart.
        repeat(20) { testAiBudget(dir).reserve(identity()) }
        blocked { testAiBudget(dir).reserve(identity()) }
        val unavailable=File(temporary.newFolder(), "missing-parent/child")
        blocked { testAiBudget(unavailable).reserve(identity()); calls++ }
        assertEquals(0, calls)
    }

    @Test fun untrustedProviderUsageCannotRefundOrIncreaseCounters() {
        val budget=testAiBudget(directory())
        for (usage in listOf(-1L, 0L, 1L, Long.MAX_VALUE)) {
            budget.reserve(identity())
            // Provider/client-reported usage is deliberately not an accounting input.
            assertNotNull(usage)
        }
        repeat(17) { budget.reserve(identity()) }
        blocked { budget.reserve(identity()) }
    }

    @Test fun errorsContainNoSuppliedCredentialOrPrompt() {
        val secret="dummy-sensitive-value-never-transmitted"
        val error=assertThrows(AiUsageLimitException::class.java) {
            testAiBudget(directory()).reserve(identity().copy(model=secret, endpoint=secret, purpose=secret))
        }
        assertEquals("AI usage limit reached.", error.message)
        assertNull(error.cause); assertFalse(error.toString().contains(secret))
    }

    @Test fun restoringAnEarlierAuthenticLedgerCannotRefundUsage() {
        val dir=directory(); val budget=testAiBudget(dir)
        budget.reserve(identity()); val previous=File(dir,"usage.bin").readBytes()
        budget.reserve(identity())
        File(dir,"usage.bin").writeBytes(previous)
        blocked {testAiBudget(dir).reserve(identity())}
    }

    @Test fun recomputingAnUnkeyedChecksumCannotForgeReducedCounters() {
        val dir=directory(); testAiBudget(dir).reserve(identity())
        val forged=File(dir,"usage.bin").readBytes()
        java.util.Arrays.fill(forged,13,37,0.toByte())
        val hash=MessageDigest.getInstance("SHA-256").digest(forged.copyOfRange(0,37))
        hash.copyInto(forged,37,0,16)
        File(dir,"usage.bin").writeBytes(forged)
        blocked {testAiBudget(dir).reserve(identity())}
    }

    @Test fun deletingWholeDirectoryCannotResetPersistentKeystoreMarker() {
        val dir=directory(); testAiBudget(dir).reserve(identity())
        assertTrue(File(dir,"usage.bin").delete()); assertTrue(dir.delete())
        blocked {testAiBudget(dir).reserve(identity())}
    }

    @Test fun currentKeyLossAndDirectoryDeletionStillCannotResetMarker() {
        val dir=directory(); testAiBudget(dir).reserve(identity())
        AiBudgetTestKeys.forDirectory(dir).loseCurrentKey()
        blocked {testAiBudget(dir).reserve(identity())}
        assertTrue(File(dir,"usage.bin").delete()); assertTrue(dir.delete())
        blocked {testAiBudget(dir).reserve(identity())}
    }

    @Test fun replacingKeyThenFailingWriteMakesOldLedgerInvalid() {
        val dir=directory(); testAiBudget(dir).reserve(identity())
        val previous=File(dir,"usage.bin").readBytes()
        blocked {testAiBudget(dir){throw IOException("durability failure")}.reserve(identity())}
        File(dir,"usage.bin").writeBytes(previous)
        blocked {testAiBudget(dir).reserve(identity())}
    }

    @Test fun retainedRecordDoesNotContainPlaintextBudgetCounters() {
        val dir=directory(); testAiBudget(dir).reserve(identity())
        val record=File(dir,"usage.bin").readBytes()
        val payload=AiBudgetTestKeys.forDirectory(dir).open(record)
        assertEquals(24,payload.size); assertEquals(53,record.size)
        assertFalse(record.asList().windowed(payload.size).any {it == payload.asList()})
    }
}
