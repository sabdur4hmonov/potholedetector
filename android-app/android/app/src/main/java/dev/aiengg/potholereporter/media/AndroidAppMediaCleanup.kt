package dev.aiengg.potholereporter.media

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import androidx.core.content.FileProvider
import java.io.File

/** Central inventory for app/plugin writers. Keep its contract test updated with writers. */
internal class AndroidAppMediaCleanup(private val context: Context) {
    companion object {
        val privateMediaChildren = listOf("reports", "footage", "repair_targets", "ion_android_camera_videos")
        const val DEBUG_FRAMES = "pothole-frames"
        const val EMAIL_TEMP = "email_composer"
        private const val JOURNAL = "owned_media_locations"
        private val providerRoots = mapOf(
            ".fileprovider" to listOf("drive_footage", "my_images", "my_cache_images", "email_composer_attachments"),
            ".camera.provider" to listOf("files", "cache", "external-files", "external-cache", "external-media")
        )
    }

    private val permissions = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
    private val cleanup = OwnedMediaCleanup(revoke = ::revokeFile, isLink = ::isSymbolicLink)

    private fun isSymbolicLink(file: File): Boolean {
        // lstat is available on minSdk 24 and does not follow symlinks (including dangling ones).
        return try { OsConstants.S_ISLNK(Os.lstat(file.path).st_mode) }
        catch (error: ErrnoException) { if (error.errno == OsConstants.ENOENT) false else throw error }
    }

    private fun externalRoots(): List<File> =
        (context.getExternalFilesDirs(null).filterNotNull() + context.externalCacheDirs.filterNotNull() +
            context.externalMediaDirs.filterNotNull()).distinctBy { it.absolutePath }

    private fun validExternal(file: File): Boolean {
        val path = file.absolutePath
        val pkg = context.packageName
        val suffix = listOf("/Android/data/$pkg/files", "/Android/data/$pkg/cache", "/Android/media/$pkg")
            .firstOrNull { path.endsWith(it) } ?: return false
        // Android may alias mount/data parents. Validate ownership after resolving those
        // parents, but reject a symlink at the app-specific root itself.
        return file.canonicalPath.endsWith(suffix) && !isSymbolicLink(file)
    }

    /** Remember Context-owned volumes across restart; unavailable removable volumes fail closed. */
    fun rememberLocations() {
        val prefs = context.getSharedPreferences(JOURNAL, Context.MODE_PRIVATE)
        val previous = prefs.getStringSet("roots", emptySet()).orEmpty()
        val paths = externalRoots().onEach { check(validExternal(it)) }.map { it.absolutePath }
        check(prefs.edit().putStringSet("roots", previous + paths).commit()) { "Media inventory unavailable" }
    }

    fun clearAll(): MediaCleanupResult {
        var failures = 0
        val advertised = runCatching { externalRoots() }.getOrElse { failures++; emptyList() }
        val current = advertised.filter {
            if (runCatching { validExternal(it) }.getOrDefault(false)) true else { failures++; false }
        }
        val externalAvailable = runCatching {
            current.isNotEmpty() && context.externalCacheDir != null && context.getExternalFilesDir(null) != null &&
                context.getExternalFilesDirs(null).none { it == null } && context.externalCacheDirs.none { it == null } &&
                context.externalMediaDirs.none { it == null } &&
                Environment.getExternalStorageState() == Environment.MEDIA_MOUNTED
        }.getOrDefault(false)
        if (!externalAvailable) failures++
        val roots = privateMediaChildren.map { OwnedMediaRoot(context.filesDir, it) }.toMutableList()
        roots += OwnedMediaRoot(context.cacheDir)
        roots += OwnedMediaRoot(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS), DEBUG_FRAMES)
        roots += current.map { OwnedMediaRoot(it) }
        try {
            val prefs = context.getSharedPreferences(JOURNAL, Context.MODE_PRIVATE)
            val known = prefs.getStringSet("roots", emptySet()).orEmpty().map(::File)
            known.forEach {
                try {
                    if (!validExternal(it)) failures++
                    else if (current.none { root -> root.absolutePath == it.absolutePath }) {
                        // A missing unmounted volume is not evidence that its contents were deleted.
                        failures++
                        if (it.exists()) roots += OwnedMediaRoot(it)
                    }
                } catch (_: Exception) { failures++ }
            }
            rememberLocations()
        } catch (_: Exception) { failures++ }
        // Prefix revocation also covers a previously unlinked file whose grant survived.
        providerRoots.forEach { (authority, aliases) -> aliases.forEach { alias ->
            try {
                context.revokeUriPermission(Uri.parse("content://${context.packageName}$authority/$alias/"), permissions)
            } catch (_: Exception) { failures++ }
        } }
        try {
            // The modern camera provider also maps shared storage. Revoke only our
            // documented debug subtree, including grants to already-deleted files.
            context.revokeUriPermission(Uri.parse("content://${context.packageName}.camera.provider/external/${Environment.DIRECTORY_DOCUMENTS}/$DEBUG_FRAMES/"), permissions)
        } catch (_: Exception) { failures++ }
        failures += cleanup.clear(roots).failures
        try {
            // IonCamera persists an edit URI here. It must not point at a deleted original.
            val cameraStore = context.getSharedPreferences("CameraStore", Context.MODE_PRIVATE)
            if (!cameraStore.edit().clear().commit() || cameraStore.all.isNotEmpty()) failures++
        } catch (_: Exception) { failures++ }
        if (failures == 0) {
            try {
                val journal = context.getSharedPreferences(JOURNAL, Context.MODE_PRIVATE)
                if (!journal.edit().clear().commit() || journal.all.isNotEmpty()) failures++
            } catch (_: Exception) { failures++ }
        }
        return MediaCleanupResult(failures)
    }

    private fun revokeFile(file: File) {
        providerRoots.keys.forEach { suffix ->
            val uri = try { FileProvider.getUriForFile(context, context.packageName + suffix, file) }
                catch (_: IllegalArgumentException) { null } // Not mapped by this provider.
            if (uri != null) context.revokeUriPermission(uri, permissions)
        }
    }

    data class Snapshot(val kind: String, val before: Set<String>)

    private fun temporaryFiles(kind: String): List<File> {
        if (kind == "email") {
            return context.externalCacheDirs.filterNotNull().flatMap {
                val folder = File(it, EMAIL_TEMP)
                check(!isSymbolicLink(folder)) { "Media cleanup incomplete" }
                if (!folder.exists()) emptyList() else folder.listFiles()?.toList()
                    ?: throw IllegalStateException("Media cleanup incomplete")
            }
        }
        if (kind != "camera") return emptyList()
        val pictures = context.getExternalFilesDirs(Environment.DIRECTORY_PICTURES).filterNotNull()
        return (pictures + context.cacheDir).flatMap {
            check(!isSymbolicLink(it)) { "Media cleanup incomplete" }
            if (!it.exists()) emptyList() else it.listFiles()?.filter { file -> !file.isDirectory }
                ?: throw IllegalStateException("Media cleanup incomplete")
        }
    }

    fun snapshot(kind: String): Snapshot {
        rememberLocations()
        return Snapshot(kind, temporaryFiles(kind).map { it.absolutePath }.toSet())
    }

    fun finish(snapshot: Snapshot): MediaCleanupResult {
        // The composer callback happens after the recipient activity closes. Share-sheet
        // return does not establish that a recipient finished reading: share files wait for wipe.
        if (snapshot.kind == "share") return MediaCleanupResult(0)
        val files = temporaryFiles(snapshot.kind).filter {
            snapshot.kind == "email" || it.absolutePath !in snapshot.before
        }
        return cleanup.clear(files.map { OwnedMediaRoot(it.parentFile!!, it.name) })
    }
}
