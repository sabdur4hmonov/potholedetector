package dev.aiengg.potholereporter.security

import android.content.Context
import java.io.File
import android.system.Os
import android.system.OsConstants

/** Both Drive and the credential bridge use this same native-private ledger. */
internal object NativeAiUsageBudget {
    fun reserve(context: Context, identity: AiRequestIdentity) {
        try {
            val anchor = context.applicationContext.noBackupFilesDir.canonicalFile
            val directory = File(anchor, "ai_usage_budget")
            PersistentAiUsageBudget(directory, AndroidAiBudgetAuthenticator()).reserve(identity)
            // First-run directory/file creation must also be durable before transmission.
            for (path in listOf(directory, anchor)) {
                val descriptor = Os.open(path.path, OsConstants.O_RDONLY, 0)
                try { Os.fsync(descriptor) } finally { Os.close(descriptor) }
            }
        } catch (_: Exception) {
            throw AiUsageLimitException()
        }
    }
}
