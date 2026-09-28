package dev.aiengg.potholereporter.media

import android.os.Environment
import android.system.Os
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.content.FileProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.UUID
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Run on an isolated test installation: clearAll deliberately wipes that app's media. */
@RunWith(AndroidJUnit4::class)
class AppMediaCleanupInstrumentedTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private fun seed(parent: File): File = File(parent, "sec002-${UUID.randomUUID()}.jpg").apply {
        parentFile.mkdirs(); writeBytes("Exif\u0000\u0000GPS-synthetic-test-only".toByteArray())
    }

    @Test fun nativeSweepDeletesKnownRootsAcrossRestartAndIsIdempotent() {
        val roots = AndroidAppMediaCleanup.privateMediaChildren.map { File(context.filesDir, it) } +
            listOf(context.cacheDir) + context.getExternalFilesDirs(null).filterNotNull() +
            context.externalCacheDirs.filterNotNull() + context.externalMediaDirs.filterNotNull() +
            listOf(File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS), "pothole-frames"))
        val artifacts = roots.map { seed(File(it, "sec002-test")) } +
            seed(context.getExternalFilesDir(Environment.DIRECTORY_PICTURES)!!) +
            context.externalCacheDirs.filterNotNull().map { seed(File(it, "email_composer")) }
        AndroidAppMediaCleanup(context).rememberLocations()
        assertTrue(context.getSharedPreferences("owned_media_locations", 0).all.isNotEmpty())
        assertTrue(AndroidAppMediaCleanup(context).clearAll().cleared)
        artifacts.forEach { assertFalse(it.exists()) }
        assertTrue(context.getSharedPreferences("owned_media_locations", 0).all.isEmpty())
        assertTrue(AndroidAppMediaCleanup(context).clearAll().cleared)
    }

    @Test fun cameraAndEmailFinallyCleanupPreservesExistingCameraFiles() {
        listOf("camera", "email").forEach { kind ->
            listOf("success", "cancel", "failure").forEach { _ ->
                val parent = if (kind == "camera") context.getExternalFilesDir(Environment.DIRECTORY_PICTURES)!!
                    else File(context.externalCacheDir!!, "email_composer")
                val prior = if (kind == "camera") seed(parent) else null
                val cleanup = AndroidAppMediaCleanup(context)
                val snapshot = cleanup.snapshot(kind)
                val original = seed(parent)
                try { assertTrue(cleanup.finish(snapshot).cleared); assertFalse(original.exists()); prior?.let { assertTrue(it.exists()) } }
                finally { prior?.delete(); original.delete() }
            }
        }
    }

    @Test fun androidLstatUnlinksSymlinkWithoutDeletingUserSelectedTarget() {
        val unrelated = seed(File(context.filesDir, "sec002-unrelated-test"))
        val link = File(context.cacheDir, "sec002-link-${UUID.randomUUID()}")
        try {
            Os.symlink(unrelated.parentFile!!.path, link.path)
            assertTrue(AndroidAppMediaCleanup(context).clearAll().cleared)
            assertTrue(unrelated.exists())
            assertFalse(link.exists())
        } finally { link.delete(); unrelated.delete(); unrelated.parentFile!!.delete() }
    }

    @Test fun wipeRevokesBothProvidersTemporaryRecipientGrants() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val recipient = instrumentation.context.packageName
        val uid = instrumentation.context.applicationInfo.uid
        // SEC-014 narrowed the app FileProvider cache alias to the share directory.
        val file = seed(File(context.cacheDir, "pothole-reporter-shares"))
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        val uris = listOf(".fileprovider", ".camera.provider").map {
            FileProvider.getUriForFile(context, context.packageName + it, file)
        }
        try {
            uris.forEach {
                context.grantUriPermission(recipient, it, flags)
                assertEquals(PackageManager.PERMISSION_GRANTED, context.checkUriPermission(it, -1, uid, flags))
            }
            assertTrue(AndroidAppMediaCleanup(context).clearAll().cleared)
            uris.forEach { assertEquals(PackageManager.PERMISSION_DENIED, context.checkUriPermission(it, -1, uid, flags)) }
            assertFalse(file.exists())
        } finally { uris.forEach { context.revokeUriPermission(it, flags) }; file.delete() }
    }
}
