package dev.aiengg.potholereporter.security

import java.io.File
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.KeyGenerator
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import java.io.RandomAccessFile

internal fun testAiBudget(directory: File, sync: (RandomAccessFile) -> Unit = { it.channel.force(true) }) =
    PersistentAiUsageBudget(directory, AiBudgetTestKeys.forDirectory(directory), sync)

/** JVM simulated Keystore: retained across budget instances, inaccessible to ledger-file writes. */
internal object AiBudgetTestKeys {
    private val keys = ConcurrentHashMap<String, TestAiBudgetAuthenticator>()
    fun forDirectory(directory: File): TestAiBudgetAuthenticator =
        keys.computeIfAbsent(directory.absolutePath) { TestAiBudgetAuthenticator() }
}

internal class TestAiBudgetAuthenticator : AiBudgetAuthenticator {
    private var marker = false
    private var key: SecretKey? = null
    override fun initialized() = marker
    override fun initialize() { check(!marker); marker = true }
    override fun sealNext(payload: ByteArray): ByteArray {
        check(marker)
        key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        return Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.ENCRYPT_MODE,key); updateAAD(aad()); byteArrayOf(1) + iv + doFinal(payload)
        }
    }
    override fun open(envelope: ByteArray): ByteArray = Cipher.getInstance("AES/GCM/NoPadding").run {
        if (!marker || envelope.size != 53 || envelope[0] != 1.toByte()) throw AiUsageLimitException()
        init(Cipher.DECRYPT_MODE,key ?: throw AiUsageLimitException(),GCMParameterSpec(128,envelope.copyOfRange(1,13)))
        updateAAD(aad()); doFinal(envelope.copyOfRange(13,53))
    }
    private fun aad() = "pothole-reporter:ai-budget:v1".toByteArray(Charsets.UTF_8)
    fun loseCurrentKey() { key = null }
}
