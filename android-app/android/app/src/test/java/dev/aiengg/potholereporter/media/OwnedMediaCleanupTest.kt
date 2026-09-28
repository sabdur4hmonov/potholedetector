package dev.aiengg.potholereporter.media

import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class OwnedMediaCleanupTest {
    @get:Rule val temp = TemporaryFolder()
    private fun artifact(parent: File, name: String = "original.jpg"): File = File(parent, name).apply {
        parentFile!!.mkdirs()
        writeBytes(byteArrayOf(0xff.toByte(), 0xd8.toByte()) + "Exif\u0000\u0000GPS-synthetic-test-only".toByteArray())
    }

    @Test fun allRegisteredLocationsIncludingStaleExifAreRemoved() {
        val files = temp.newFolder("files")
        val cache = temp.newFolder("cache")
        val externalFiles = temp.newFolder("externalFiles")
        val externalCache = temp.newFolder("externalCache")
        val externalMedia = temp.newFolder("externalMedia")
        val documents = temp.newFolder("Documents")
        val roots = AndroidAppMediaCleanup.privateMediaChildren.map { OwnedMediaRoot(files, it) } +
            listOf(OwnedMediaRoot(cache), OwnedMediaRoot(externalFiles), OwnedMediaRoot(externalCache),
                OwnedMediaRoot(externalMedia), OwnedMediaRoot(documents, AndroidAppMediaCleanup.DEBUG_FRAMES))
        val originals = roots.map { artifact(File(it.file, "stale")) } +
            listOf(artifact(File(externalFiles, "Pictures")), artifact(File(externalCache, "email_composer")))
        val unrelated = artifact(documents, "user-photo.jpg")
        val preferences = artifact(files, "unrelated-private-state")
        assertTrue(OwnedMediaCleanup().clear(roots).cleared)
        originals.forEach { assertFalse(it.exists()) }
        assertTrue(unrelated.exists())
        assertTrue(preferences.exists())
        assertTrue(cache.isDirectory)
        assertTrue(externalFiles.isDirectory)
    }

    @Test fun firstRunAndAlreadyMissingAreSuccessful() {
        val anchor = temp.newFolder()
        assertEquals(MediaCleanupResult(0), OwnedMediaCleanup().clear(listOf(OwnedMediaRoot(anchor, "missing"))))
        assertTrue(OwnedMediaCleanup().clear(listOf(OwnedMediaRoot(File(anchor, "missing-anchor")))).cleared)
    }

    @Test fun repeatedDeletionAndNewProcessSweepAreIdempotent() {
        val anchor = temp.newFolder()
        val root = OwnedMediaRoot(anchor, "media")
        artifact(root.file)
        assertTrue(OwnedMediaCleanup().clear(listOf(root)).cleared)
        assertTrue(OwnedMediaCleanup().clear(listOf(root)).cleared)
        artifact(root.file, "interrupted-original.jpg")
        assertTrue(OwnedMediaCleanup().clear(listOf(root)).cleared)
        assertFalse(root.file.exists())
    }

    @Test fun partialFailureContinuesOtherChildrenAndRootsThenRetrySucceeds() {
        val anchor = temp.newFolder()
        val a = OwnedMediaRoot(anchor, "a")
        val b = OwnedMediaRoot(anchor, "b")
        val blocked = artifact(a.file, "blocked.jpg")
        val sibling = artifact(a.file, "sibling.jpg")
        val other = artifact(b.file)
        val result = OwnedMediaCleanup(delete = { it != blocked && it.delete() }).clear(listOf(a,b))
        assertFalse(result.cleared)
        assertTrue(blocked.exists())
        assertFalse(sibling.exists())
        assertFalse(other.exists())
        assertTrue(OwnedMediaCleanup().clear(listOf(a,b)).cleared)
    }

    @Test fun thrownFailureHasNoPathsAndStillContinues() {
        val anchor = temp.newFolder()
        val a = artifact(anchor, "fail.jpg")
        val b = artifact(anchor, "other.jpg")
        val result = OwnedMediaCleanup(delete = { if (it == a) error("private-path-sentinel") else it.delete() })
            .clear(listOf(OwnedMediaRoot(anchor)))
        assertFalse(result.cleared)
        assertFalse(b.exists())
        assertFalse(result.toString().contains("private-path-sentinel"))
        assertFalse(result.toString().contains(anchor.path))
    }

    @Test fun revokesBeforeUnlinkAndRevocationFailureDoesNotSkipDeletion() {
        val anchor = temp.newFolder()
        val file = artifact(anchor)
        var revoked = false
        val result = OwnedMediaCleanup(revoke = {
            assertTrue(it.exists()); revoked = true; throw SecurityException("grant-test")
        }).clear(listOf(OwnedMediaRoot(anchor)))
        assertTrue(revoked)
        assertFalse(file.exists())
        assertFalse(result.cleared)
    }

    @Test fun validGrantRevocationAllowsSuccess() {
        val anchor = temp.newFolder()
        artifact(anchor)
        val grants = mutableListOf<File>()
        assertTrue(OwnedMediaCleanup(revoke = { grants += it }).clear(listOf(OwnedMediaRoot(anchor))).cleared)
        assertEquals(1, grants.size)
    }

    @Test fun refusesTraversalAndAbsoluteChildren() {
        listOf("..", ".", "../user", "user/file", "user\\file", "", "/outside").forEach {
            try { OwnedMediaRoot(temp.root, it); fail("Invalid root accepted") }
            catch (_: IllegalArgumentException) { }
        }
    }

    @Test fun symlinkDirectoryIsUnlinkedWithoutTouchingUnrelatedTarget() {
        val own = temp.newFolder("own")
        val outside = temp.newFolder("outside")
        val untouched = artifact(outside)
        val link = File(own, "link")
        val windows = System.getProperty("os.name").orEmpty().startsWith("Windows")
        if (windows) {
            // A directory junction needs no administrator symlink privilege.
            val process = ProcessBuilder("cmd.exe", "/c", "mklink", "/J", link.path, outside.path).start()
            process.inputStream.readBytes()
            assertEquals(0, process.waitFor())
        } else Files.createSymbolicLink(link.toPath(), outside.toPath())
        // Supply the lstat outcome for this known link; Android detection has its
        // own instrumentation test. The Windows sandbox may refuse junction unlink.
        var mappedGrants = 0
        val cleanup = OwnedMediaCleanup(delete = { Files.deleteIfExists(it.toPath()) }, revoke = { mappedGrants++ },
            isLink = { it == link && it.exists() })
        val result = cleanup.clear(listOf(OwnedMediaRoot(own)))
        assertTrue(untouched.exists())
        assertEquals(0, mappedGrants)
        if (!windows) assertFalse(link.exists())
        assertEquals(!link.exists(), result.cleared)
    }

    @Test fun captureAndComposerOutcomesAlwaysReleaseWriterAndBlockConcurrentWipe() {
        listOf("camera", "email", "share").forEach { kind ->
            listOf("success", "cancel", "failure").forEach { outcome ->
                val gate = MediaOperationGate()
                val token = gate.begin(kind)
                assertFalse(gate.beginClear())
                try { if (outcome != "success") throw IllegalStateException("synthetic-outcome") }
                catch (_: IllegalStateException) { }
                finally { gate.end(token) }
                assertTrue(gate.beginClear())
                gate.endClear()
            }
        }
    }

    @Test fun invalidTokenCannotReleaseAnotherOperation() {
        val gate = MediaOperationGate()
        val token = gate.begin("email")
        try { gate.end("wrong-token"); fail("Wrong token accepted") } catch (_: IllegalStateException) { }
        assertTrue(gate.owns(token))
        assertFalse(gate.beginClear())
        gate.end(token)
        assertTrue(gate.beginClear())
        try { gate.begin("camera"); fail("Writer during wipe") } catch (_: IllegalStateException) { }
        gate.endClear()
        assertTrue(gate.beginClear())
    }

    @Test fun invalidOperationKindCannotCreateLease() {
        val gate = MediaOperationGate()
        try { gate.begin("../delete"); fail("Invalid kind") } catch (_: IllegalArgumentException) { }
        assertTrue(gate.beginClear())
    }

    @Test fun linkedAnchorFailsClosedWithoutVisitingTarget() {
        val anchor = temp.newFolder()
        val original = artifact(anchor)
        val result = OwnedMediaCleanup(isLink = { it == anchor }).clear(listOf(OwnedMediaRoot(anchor)))
        assertFalse(result.cleared)
        assertTrue(original.exists())
    }

    @Test fun simultaneousWriterAndWipeHaveExactlyOneWinner() {
        val pool = Executors.newFixedThreadPool(2)
        try {
            repeat(32) {
                val gate = MediaOperationGate()
                val start = CountDownLatch(1)
                val writer = pool.submit<Boolean> { start.await(); runCatching { gate.begin("camera") }.isSuccess }
                val wipe = pool.submit<Boolean> { start.await(); gate.beginClear() }
                start.countDown()
                assertEquals(1, listOf(writer.get(), wipe.get()).count { it })
            }
        } finally { pool.shutdownNow() }
    }
}
