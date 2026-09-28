package dev.aiengg.potholereporter.security

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.UUID
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NativeSecretStoreInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val alias = "sec001-test-${UUID.randomUUID()}"
    private val preferencesName = "sec001-test-${UUID.randomUUID()}"
    private val keyProvider = AndroidKeystoreSecretKeyProvider(alias)
    private val preferences by lazy {
        context.getSharedPreferences(preferencesName, android.content.Context.MODE_PRIVATE)
    }
    private val store by lazy {
        NativeSecretStore(keyProvider, SharedPreferencesSecretCiphertextPersistence(preferences))
    }

    @Before
    fun prepare() {
        keyProvider.delete()
        preferences.edit().clear().commit()
    }

    @After
    fun cleanUp() {
        keyProvider.delete()
        preferences.edit().clear().commit()
    }

    @Test
    fun androidKeystoreFirstRunMigrationCorruptionAndResetLifecycle() {
        val openAi = "instrumented-openai-credential-123"
        val rtsp = "rtsp://instrumented:credential@192.0.2.2/live"
        val migrated = store.migrateLegacy(openAi, rtsp)
        assertTrue(migrated.openAiMigrated)
        assertTrue(migrated.dashcamRtspMigrated)
        assertEquals(openAi, store.readForNativeUse(NativeSecret.OPENAI))
        assertNull(keyProvider.getOrCreate().encoded)
        val restarted = NativeSecretStore(keyProvider, SharedPreferencesSecretCiphertextPersistence(preferences))
        assertEquals(rtsp, restarted.readForNativeUse(NativeSecret.DASHCAM_RTSP))
        assertTrue(preferences.all.values.none { it.toString().contains(openAi) || it.toString().contains(rtsp) })

        val firstCiphertext = preferences.getString(NativeSecret.OPENAI.persistenceKey, null)
        store.clearAll()
        assertFalse(store.status().openAiConfigured)
        assertTrue(preferences.all.isEmpty())

        store.put(openAi = "instrumented-replacement-credential-456")
        assertNotEquals(firstCiphertext, preferences.getString(NativeSecret.OPENAI.persistenceKey, null))
        preferences.edit().putString(NativeSecret.OPENAI.persistenceKey, "corrupt").commit()
        assertFalse(store.status().openAiConfigured)
        assertFalse(preferences.contains(NativeSecret.OPENAI.persistenceKey))
    }

    @Test
    fun missingKeystoreKeyMakesRetainedCiphertextsUnavailable() {
        store.put("instrumented-openai-credential-123", "rtsp://instrumented:credential@192.0.2.2/live")
        keyProvider.delete()
        assertFalse(store.status().openAiConfigured)
        assertFalse(store.status().dashcamRtspConfigured)
        assertTrue(preferences.all.isEmpty())
    }
}
