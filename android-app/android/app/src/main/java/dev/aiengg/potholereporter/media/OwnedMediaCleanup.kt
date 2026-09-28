package dev.aiengg.potholereporter.media

import java.io.File
import java.util.UUID

/** Anchors come from Android Context, never from JavaScript or an imported URI. */
internal data class OwnedMediaRoot(val anchor: File, val child: String? = null) {
    init { require(child == null || (child.isNotBlank() && '/' !in child && '\\' !in child && child != "." && child != "..")) }
    val file: File get() = child?.let { File(anchor, it) } ?: anchor
}

internal data class MediaCleanupResult(val failures: Int) {
    val cleared: Boolean get() = failures == 0
}

/** No recursive File.deleteRecursively: it follows directory symlinks on some runtimes. */
internal class OwnedMediaCleanup(
    private val delete: (File) -> Boolean = { it.delete() },
    private val revoke: (File) -> Unit = {},
    private val isLink: (File) -> Boolean = { it.canonicalFile != it.absoluteFile }
) {
    fun clear(roots: List<OwnedMediaRoot>): MediaCleanupResult {
        var failures = 0
        roots.forEach { root ->
            try {
                check(!isLink(root.anchor)) { "Media cleanup incomplete" }
                val anchor = root.anchor.canonicalFile
                if (root.child == null) {
                    if (anchor.exists()) {
                        val children = anchor.listFiles() ?: throw IllegalStateException("Media cleanup incomplete")
                        children.forEach { failures += remove(it, anchor) }
                        if (anchor.listFiles()?.isEmpty() != true) failures++
                    }
                } else {
                    failures += remove(File(anchor, root.child), anchor)
                }
            } catch (_: Exception) { failures++ }
        }
        return MediaCleanupResult(failures)
    }

    private fun remove(file: File, anchor: File): Int {
        var failures = 0
        try {
            // Check the parent before touching the entry. A symlink itself may be
            // unlinked, but its target (even another app-owned directory) is never visited.
            val parent = file.parentFile!!.canonicalFile
            require(parent == anchor || parent.path.startsWith(anchor.path + File.separator))
            val entry = File(parent, file.name)
            val link = isLink(entry)
            if (!entry.exists() && !link) return 0
            // FileProvider canonicalizes paths. Do not map a link into its unrelated
            // target's URI; the Android registry revokes our own URI prefixes separately.
            if (!link) try { revoke(entry) } catch (_: Exception) { failures++ }
            if (!link && entry.isDirectory) {
                val children = entry.listFiles()
                if (children == null) failures++
                else children.forEach { failures += remove(it, anchor) }
            }
            if (!delete(entry) || entry.exists() || isLink(entry)) failures++
        } catch (_: Exception) { failures++ }
        return failures
    }
}

/** A wipe cannot report success while a camera/composer/share can still create files. */
internal class MediaOperationGate {
    private var token: String? = null
    private var clearing = false
    @Synchronized fun begin(kind: String): String {
        require(kind in setOf("camera", "email", "share")) { "Invalid media operation" }
        check(!clearing && token == null) { "Finish the active media operation before deleting data" }
        return UUID.randomUUID().toString().also { token = it }
    }
    @Synchronized fun owns(value: String): Boolean = token == value
    @Synchronized fun end(value: String) { check(token == value) { "Invalid media operation" }; token = null }
    @Synchronized fun beginClear(): Boolean {
        if (clearing || token != null) return false
        clearing = true
        return true
    }
    @Synchronized fun endClear() { clearing = false }
}

internal object AppMediaOperations { val gate = MediaOperationGate() }
