package dev.aiengg.potholereporter.security

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.nio.ByteBuffer
import java.net.URI
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal enum class NativeSecret(val persistenceKey: String) {
    OPENAI("openai_ciphertext"),
    DASHCAM_RTSP("dashcam_rtsp_ciphertext")
}

internal class SecretUnavailableException : Exception("Stored credential is unavailable")

internal object NativeSecretValidation {
    private val controlCharacter = Regex("[\\u0000-\\u001f\\u007f]")

    fun openAi(value: String): String {
        val normalized = value.trim()
        require(normalized.length in 8..512 && !controlCharacter.containsMatchIn(normalized) &&
            normalized.all { it in '!'..'~' }) { "Invalid OpenAI credential" }
        return normalized
    }

    fun dashcamRtsp(value: String): String {
        val normalized = value.trim()
        require(normalized.length in 8..2_048 && !controlCharacter.containsMatchIn(normalized) &&
            normalized.none(Char::isWhitespace)) { "Invalid dashcam credential" }
        val address = runCatching { URI(normalized) }.getOrNull()
            ?: throw IllegalArgumentException("Invalid dashcam credential")
        require(address.scheme.equals("rtsp", ignoreCase = true) &&
            !address.host.isNullOrBlank() && (address.port == -1 || address.port in 1..65_535) &&
            address.fragment == null) { "Invalid dashcam credential" }
        return normalized
    }

    fun normalize(secret: NativeSecret, value: String): String = when (secret) {
        NativeSecret.OPENAI -> openAi(value)
        NativeSecret.DASHCAM_RTSP -> dashcamRtsp(value)
    }
}

internal interface SecretKeyProvider {
    fun getOrCreate(): SecretKey
    fun delete()
}

internal interface SecretCiphertextPersistence {
    fun read(name: String): String?
    fun writeAll(values: Map<String, String>): Boolean
    fun remove(name: String): Boolean
    fun clear(): Boolean
}

internal class AuthenticatedSecretCipher {
    fun encrypt(key: SecretKey, secret: NativeSecret, plaintext: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key)
        cipher.updateAAD(aad(secret))
        val encrypted = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        val iv = cipher.iv
        require(iv.size in 12..32) { "Credential encryption failed" }
        return hex(ByteBuffer.allocate(2 + iv.size + encrypted.size)
            .put(FORMAT_VERSION)
            .put(iv.size.toByte())
            .put(iv)
            .put(encrypted)
            .array())
    }

    fun decrypt(key: SecretKey, secret: NativeSecret, envelope: String): String {
        try {
            val bytes = unhex(envelope)
            require(bytes.size >= 2 + 12 + 16)
            val buffer = ByteBuffer.wrap(bytes)
            require(buffer.get() == FORMAT_VERSION)
            val ivLength = buffer.get().toInt() and 0xff
            require(ivLength in 12..32 && buffer.remaining() > ivLength + 15)
            val iv = ByteArray(ivLength).also(buffer::get)
            val encrypted = ByteArray(buffer.remaining()).also(buffer::get)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
            cipher.updateAAD(aad(secret))
            return cipher.doFinal(encrypted).toString(Charsets.UTF_8)
        } catch (_: Exception) {
            throw SecretUnavailableException()
        }
    }

    private fun aad(secret: NativeSecret): ByteArray =
        "pothole-reporter:${secret.persistenceKey}:v1".toByteArray(Charsets.UTF_8)

    private fun hex(bytes: ByteArray): String = buildString(bytes.size * 2) {
        for (byte in bytes) append("%02x".format(byte.toInt() and 0xff))
    }

    private fun unhex(value: String): ByteArray {
        require(value.length % 2 == 0 && value.length <= MAX_ENVELOPE_HEX_LENGTH)
        return ByteArray(value.length / 2) { index ->
            value.substring(index * 2, index * 2 + 2).toInt(16).toByte()
        }
    }

    private companion object {
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        // Allow the maximum RTSP input even when its path contains multibyte UTF-8.
        const val MAX_ENVELOPE_HEX_LENGTH = 16_512
        const val FORMAT_VERSION: Byte = 1
    }
}

internal data class SecretStatus(
    val openAiConfigured: Boolean,
    val dashcamRtspConfigured: Boolean
)

internal data class SecretMigrationResult(
    val openAiMigrated: Boolean,
    val dashcamRtspMigrated: Boolean,
    val status: SecretStatus
)

internal class NativeSecretStore(
    private val keyProvider: SecretKeyProvider,
    private val persistence: SecretCiphertextPersistence,
    private val cipher: AuthenticatedSecretCipher = AuthenticatedSecretCipher()
) {
    @Synchronized
    fun status(): SecretStatus = SecretStatus(
        openAiConfigured = readable(NativeSecret.OPENAI),
        dashcamRtspConfigured = readable(NativeSecret.DASHCAM_RTSP)
    )

    @Synchronized
    fun put(openAi: String? = null, dashcamRtsp: String? = null): SecretStatus {
        val values = linkedMapOf<NativeSecret, String>()
        if (openAi != null) values[NativeSecret.OPENAI] = NativeSecretValidation.openAi(openAi)
        if (dashcamRtsp != null) {
            values[NativeSecret.DASHCAM_RTSP] = NativeSecretValidation.dashcamRtsp(dashcamRtsp)
        }
        if (values.isNotEmpty()) {
            val key = keyProvider.getOrCreate()
            val encrypted = values.mapKeys { it.key.persistenceKey }
                .mapValues { (name, plaintext) ->
                    cipher.encrypt(key, NativeSecret.entries.first { it.persistenceKey == name }, plaintext)
                }
            if (!persistence.writeAll(encrypted)) throw SecretUnavailableException()
        }
        return status()
    }

    @Synchronized
    fun migrateLegacy(openAi: String? = null, dashcamRtsp: String? = null): SecretMigrationResult {
        val current = status()
        val migrateOpenAi = !current.openAiConfigured && !openAi.isNullOrBlank()
        val migrateDashcam = !current.dashcamRtspConfigured && !dashcamRtsp.isNullOrBlank()
        val updated = put(
            openAi = if (migrateOpenAi) openAi else null,
            dashcamRtsp = if (migrateDashcam) dashcamRtsp else null
        )
        return SecretMigrationResult(migrateOpenAi, migrateDashcam, updated)
    }

    @Synchronized
    fun readForNativeUse(secret: NativeSecret): String? {
        return try {
            val envelope = persistence.read(secret.persistenceKey) ?: return null
            val plaintext = cipher.decrypt(keyProvider.getOrCreate(), secret, envelope)
            NativeSecretValidation.normalize(secret, plaintext)
        } catch (_: Exception) {
            persistence.remove(secret.persistenceKey)
            throw SecretUnavailableException()
        }
    }

    @Synchronized
    fun clearAll() {
        try {
            // Deleting the Keystore key first makes every retained ciphertext unusable
            // even if a later preferences write is interrupted.
            keyProvider.delete()
        } catch (_: Exception) {
            throw SecretUnavailableException()
        }
        if (!persistence.clear()) throw SecretUnavailableException()
    }

    private fun readable(secret: NativeSecret): Boolean = try {
        readForNativeUse(secret) != null
    } catch (_: SecretUnavailableException) {
        false
    }

    companion object {
        private var instance: NativeSecretStore? = null

        // All bridge/service callers share the same store lock for key lifecycle,
        // preference writes, and reset, including requests on background threads.
        @Synchronized
        fun create(context: Context): NativeSecretStore = instance ?: NativeSecretStore(
            AndroidKeystoreSecretKeyProvider(KEY_ALIAS),
            SharedPreferencesSecretCiphertextPersistence(
                context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
            )
        ).also { instance = it }

        internal const val KEY_ALIAS = "pothole_reporter_retained_secrets_v1"
        internal const val PREFERENCES_NAME = "retained_secret_ciphertexts_v1"
    }
}

internal class AndroidKeystoreSecretKeyProvider(private val alias: String) : SecretKeyProvider {
    override fun getOrCreate(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    override fun delete() {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        if (keyStore.containsAlias(alias)) keyStore.deleteEntry(alias)
    }

    private companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
    }
}

internal class SharedPreferencesSecretCiphertextPersistence(
    private val preferences: SharedPreferences
) : SecretCiphertextPersistence {
    override fun read(name: String): String? = preferences.getString(name, null)

    override fun writeAll(values: Map<String, String>): Boolean {
        val editor = preferences.edit()
        values.forEach(editor::putString)
        return editor.commit()
    }

    override fun remove(name: String): Boolean = preferences.edit().remove(name).commit()

    override fun clear(): Boolean = preferences.edit().clear().commit()
}
