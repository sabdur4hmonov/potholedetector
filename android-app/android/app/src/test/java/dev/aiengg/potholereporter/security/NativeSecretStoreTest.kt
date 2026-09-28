package dev.aiengg.potholereporter.security

import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import java.io.ByteArrayOutputStream
import java.io.PrintStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeSecretStoreTest {
    @Test
    fun firstWriteStoresOnlyAuthenticatedCiphertextAndDecryptsForNativeUse() {
        val keys = MemoryKeyProvider()
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(keys, persistence)
        val openAi = "unit-openai-credential-123"
        val rtsp = "rtsp://unit-user:unit-password@192.0.2.1/live"

        val status = store.put(openAi, rtsp)

        assertTrue(status.openAiConfigured)
        assertTrue(status.dashcamRtspConfigured)
        assertEquals(openAi, store.readForNativeUse(NativeSecret.OPENAI))
        assertEquals(rtsp, store.readForNativeUse(NativeSecret.DASHCAM_RTSP))
        assertTrue(persistence.values.values.none { it.contains(openAi) || it.contains(rtsp) })
        assertEquals(1, keys.generation)
    }

    @Test
    fun legacyMigrationIsOneWayAndNeverOverwritesAnExistingNativeSecret() {
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(MemoryKeyProvider(), persistence)
        val retained = "unit-retained-credential-123"
        store.put(openAi = retained)

        val result = store.migrateLegacy(
            openAi = "unit-stale-browser-value-123",
            dashcamRtsp = "rtsp://unit-user:unit-password@198.51.100.2/live"
        )

        assertFalse(result.openAiMigrated)
        assertTrue(result.dashcamRtspMigrated)
        assertEquals(retained, store.readForNativeUse(NativeSecret.OPENAI))
    }

    @Test
    fun clearDeletesCiphertextAndKeyAndANewWriteGetsANewKey() {
        val keys = MemoryKeyProvider()
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(keys, persistence)
        store.put(openAi = "unit-openai-credential-123")
        val firstKey = keys.current

        store.clearAll()

        assertTrue(persistence.values.isEmpty())
        assertNull(keys.current)
        assertEquals(1, keys.deletions)
        assertFalse(store.status().openAiConfigured)

        store.put(openAi = "unit-replacement-credential-456")
        assertNotEquals(firstKey, keys.current)
        assertEquals(2, keys.generation)
    }

    @Test
    fun corruptedOrSwappedCiphertextFailsClosedWithoutSecretBearingErrors() {
        val keys = MemoryKeyProvider()
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(keys, persistence)
        val secret = "unit-openai-credential-123"
        store.put(openAi = secret)
        val valid = persistence.values.getValue(NativeSecret.OPENAI.persistenceKey)
        persistence.values[NativeSecret.OPENAI.persistenceKey] = valid.dropLast(1) +
            if (valid.last() == '0') "1" else "0"

        val corrupt = assertThrows(SecretUnavailableException::class.java) {
            store.readForNativeUse(NativeSecret.OPENAI)
        }
        assertFalse(corrupt.message.orEmpty().contains(secret))
        assertNull(persistence.values[NativeSecret.OPENAI.persistenceKey])

        store.put(openAi = secret)
        persistence.values[NativeSecret.DASHCAM_RTSP.persistenceKey] =
            persistence.values.getValue(NativeSecret.OPENAI.persistenceKey)
        assertThrows(SecretUnavailableException::class.java) {
            store.readForNativeUse(NativeSecret.DASHCAM_RTSP)
        }
    }

    @Test
    fun validatorsAndBridgePolicyRejectUntrustedOrOverbroadInput() {
        assertThrows(IllegalArgumentException::class.java) {
            NativeSecretValidation.openAi("short")
        }
        assertThrows(IllegalArgumentException::class.java) {
            NativeSecretValidation.dashcamRtsp("https://example.test/live")
        }
        assertTrue(NativeBridgeAuthorization.isTrustedMainDocument("https://localhost/"))
        assertFalse(NativeBridgeAuthorization.isTrustedMainDocument("https://localhost.evil.test/"))
        assertFalse(NativeBridgeAuthorization.isTrustedMainDocument("https://user@localhost/"))
        assertFalse(NativeBridgeAuthorization.isTrustedMainDocument("http://localhost/"))
        assertFalse(NativeBridgeAuthorization.isTrustedMainDocument("https://localhost:444/"))
        assertFalse(NativeBridgeAuthorization.isTrustedMainDocument(null))
        assertThrows(IllegalArgumentException::class.java) { NativeSecretValidation.openAi("") }
        assertThrows(IllegalArgumentException::class.java) {
            NativeSecretValidation.openAi("unit-credential\nwith-control")
        }
        assertThrows(IllegalArgumentException::class.java) { NativeSecretValidation.dashcamRtsp("") }
        assertThrows(IllegalArgumentException::class.java) {
            NativeSecretValidation.dashcamRtsp("rtsp://:bad-port/live")
        }
    }

    @Test
    fun missingKeyAndMalformedCiphertextRequireReentryAndNeverRestorePlaintext() {
        val keys = MemoryKeyProvider()
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(keys, persistence)
        store.put("unit-openai-credential-123", "rtsp://unit-user:unit-password@192.0.2.1/live")
        keys.delete()
        assertFalse(store.status().openAiConfigured)
        assertFalse(store.status().dashcamRtspConfigured)
        assertTrue(persistence.values.isEmpty())
        persistence.values[NativeSecret.OPENAI.persistenceKey] = "malformed-ciphertext"
        assertFalse(store.status().openAiConfigured)
        assertTrue(persistence.values.isEmpty())
    }

    @Test
    fun restartingStoreRetainsOnlyCiphertextAndEncryptionUsesFreshIvs() {
        val keys = MemoryKeyProvider()
        val persistence = MemoryPersistence()
        val secret = "unit-openai-credential-123"
        NativeSecretStore(keys, persistence).put(openAi = secret)
        val first = persistence.values.getValue(NativeSecret.OPENAI.persistenceKey)
        val restarted = NativeSecretStore(keys, persistence)
        assertEquals(secret, restarted.readForNativeUse(NativeSecret.OPENAI))
        restarted.put(openAi = secret)
        assertNotEquals(first, persistence.values.getValue(NativeSecret.OPENAI.persistenceKey))
    }

    @Test
    fun invalidMigrationDoesNotWritePlaintextAndReplacementCanBeSaved() {
        val persistence = MemoryPersistence()
        val store = NativeSecretStore(MemoryKeyProvider(), persistence)
        assertThrows(IllegalArgumentException::class.java) {
            store.migrateLegacy(openAi = "short")
        }
        assertTrue(persistence.values.isEmpty())
        assertTrue(store.put(openAi = "unit-replacement-credential-123").openAiConfigured)
    }

    @Test
    fun credentialOperationsEmitNoStdoutOrStderrIncludingFailurePaths() {
        val previousOut = System.out
        val previousErr = System.err
        val captured = ByteArrayOutputStream()
        try {
            System.setOut(PrintStream(captured))
            System.setErr(PrintStream(captured))
            val persistence = MemoryPersistence()
            val store = NativeSecretStore(MemoryKeyProvider(), persistence)
            store.put(openAi = "unit-log-sentinel-credential-123")
            persistence.values[NativeSecret.OPENAI.persistenceKey] = "corrupt"
            assertFalse(store.status().openAiConfigured)
            store.clearAll()
            assertEquals("", captured.toString())
        } finally {
            System.setOut(previousOut)
            System.setErr(previousErr)
        }
    }

    private class MemoryKeyProvider : SecretKeyProvider {
        var current: SecretKey? = null
        var generation = 0
        var deletions = 0

        override fun getOrCreate(): SecretKey = current ?: KeyGenerator.getInstance("AES").apply {
            init(256)
        }.generateKey().also {
            current = it
            generation++
        }

        override fun delete() {
            current = null
            deletions++
        }
    }

    private class MemoryPersistence : SecretCiphertextPersistence {
        val values = linkedMapOf<String, String>()

        override fun read(name: String): String? = values[name]
        override fun writeAll(values: Map<String, String>): Boolean {
            this.values.putAll(values)
            return true
        }
        override fun remove(name: String): Boolean {
            values.remove(name)
            return true
        }
        override fun clear(): Boolean {
            values.clear()
            return true
        }
    }
}
