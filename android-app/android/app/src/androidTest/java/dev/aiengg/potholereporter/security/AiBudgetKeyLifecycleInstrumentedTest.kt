package dev.aiengg.potholereporter.security

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.KeyStore
import java.util.UUID
import javax.crypto.SecretKey
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real Keystore lifecycle verification; requires a device, never performs network inference. */
@RunWith(AndroidJUnit4::class)
class AiBudgetKeyLifecycleInstrumentedTest {
    private fun runWithTestKeys(action: (AndroidAiBudgetAuthenticator, String, String) -> Unit) {
        val suffix=UUID.randomUUID().toString()
        val marker="sec006_test_marker_$suffix"; val current="sec006_test_current_$suffix"
        try { action(AndroidAiBudgetAuthenticator(marker,current),marker,current) }
        finally {
            val store=KeyStore.getInstance("AndroidKeyStore").apply {load(null)}
            for (alias in listOf(marker,current)) if (store.containsAlias(alias)) store.deleteEntry(alias)
        }
    }

    @Test fun realKeyRotationInvalidatesOldTagsAndSurvivesReinstantiation() = runWithTestKeys { auth, marker, current ->
        auth.initialize()
        val payload=ByteArray(24) {1}; val first=auth.sealNext(payload)
        assertArrayEquals(payload,auth.open(first))
        val second=auth.sealNext(payload)
        assertThrows(AiUsageLimitException::class.java) {auth.open(first)}
        assertArrayEquals(payload,auth.open(second))
        val restarted=AndroidAiBudgetAuthenticator(marker,current)
        assertTrue(restarted.initialized()); assertArrayEquals(payload,restarted.open(second))
        val key=KeyStore.getInstance("AndroidKeyStore").apply {load(null)}.getKey(current,null) as SecretKey
        check(key.encoded == null) {"Budget key must be non-exportable"}
    }

    @Test fun fileRollbackAndDirectoryDeletionDoNotResetRealKeystoreBudget() = runWithTestKeys { auth, _, _ ->
        val anchor=InstrumentationRegistry.getInstrumentation().targetContext.noBackupFilesDir.canonicalFile
        val dir=File(anchor,"sec006_test_budget_${UUID.randomUUID()}")
        val request=AiRequestIdentity("openai",AiOutputPolicy.ENDPOINT,"gpt-5-mini","general",512)
        try {
            val budget=PersistentAiUsageBudget(dir,auth)
            budget.reserve(request); val old=File(dir,"usage.bin").readBytes()
            budget.reserve(request); File(dir,"usage.bin").writeBytes(old)
            assertThrows(AiUsageLimitException::class.java) {budget.reserve(request)}
            assertTrue(File(dir,"usage.bin").delete()); assertTrue(dir.delete())
            assertThrows(AiUsageLimitException::class.java) {budget.reserve(request)}
        } finally {File(dir,"usage.bin").delete();dir.delete()}
    }
}
