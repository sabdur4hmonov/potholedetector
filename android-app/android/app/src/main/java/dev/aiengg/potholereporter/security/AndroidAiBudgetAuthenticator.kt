package dev.aiengg.potholereporter.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.KeyGenerator
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Non-exportable native keys; separate from retained credentials, never exposed by a bridge. */
internal class AndroidAiBudgetAuthenticator(
    private val markerAlias: String = "pothole_reporter_ai_budget_marker_v1",
    private val currentAlias: String = "pothole_reporter_ai_budget_record_v1"
) : AiBudgetAuthenticator {
    private fun store() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    override fun initialized(): Boolean = store().let { it.containsAlias(markerAlias) || it.containsAlias(currentAlias) }
    override fun initialize() {
        if (initialized()) throw AiUsageLimitException()
        generate(markerAlias) // Permanent initialization marker; never rotated/deleted by app.
    }
    override fun open(envelope: ByteArray): ByteArray {
        try {
            if (!store().containsAlias(markerAlias) || envelope.size != 53 || envelope[0] != 1.toByte()) throw AiUsageLimitException()
            val key = store().getKey(currentAlias, null) as? SecretKey ?: throw AiUsageLimitException()
            return Cipher.getInstance("AES/GCM/NoPadding").run {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, envelope.copyOfRange(1,13)))
                updateAAD(aad()); doFinal(envelope.copyOfRange(13,53))
            }
        } catch (_: Exception) { throw AiUsageLimitException() }
    }
    override fun sealNext(payload: ByteArray): ByteArray {
        if (!store().containsAlias(markerAlias)) throw AiUsageLimitException()
        // AndroidKeyStore replaces an existing key at this alias. Destroying its old
        // material invalidates every earlier ledger, rather than trusting file counters.
        return Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.ENCRYPT_MODE, generate(currentAlias)); updateAAD(aad())
            val encrypted=doFinal(payload)
            if (iv.size != 12 || encrypted.size != 40) throw AiUsageLimitException()
            byteArrayOf(1) + iv + encrypted
        }
    }
    private fun generate(alias: String): SecretKey {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }
    private fun aad() = "pothole-reporter:ai-budget:v1".toByteArray(Charsets.UTF_8)
}
