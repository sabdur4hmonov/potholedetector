package dev.aiengg.potholereporter.drive

import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files
import java.nio.file.StandardCopyOption.*

class NativeHazardStoreTest {
    private val good = NativeHazard("web:1", 41.0, 69.0, "confirmed")
    @Test fun rejectsOversizeInvalidNumbersCoordinatesIdsKindsAndDuplicateIds() {
        val invalid = listOf(List(5001) { good.copy(id = "$it") }, listOf(good.copy(lat = Double.NaN)),
            listOf(good.copy(lng = 181.0)), listOf(good.copy(id = "x".repeat(65))),
            listOf(good.copy(id = "")), listOf(good.copy(kind = "verified")), listOf(good, good))
        for (values in invalid) {
            try { NativeHazardStore.validate(values); fail("must reject invalid batch") }
            catch (_: IllegalArgumentException) { }
        }
        NativeHazardStore.validate(List(5000) { good.copy(id = "$it") })
    }
    @Test fun strictJsonVersionAndTypes() {
        val valid = """{"version":1,"hazards":[{"id":"web:1","lat":41,"lng":69,"kind":"confirmed"}]}"""
        assertEquals(listOf(good), NativeHazardStore.parse(valid))
        for (bad in listOf(valid.replace("\"version\":1", "\"version\":2"),
            valid.replace("\"lat\":41", "\"lat\":\"41\""), valid.replace("confirmed", "bad"),
            valid.replace("\"lat\":41", "\"lat\":null"))) {
            try { NativeHazardStore.parse(bad); fail("must reject JSON") } catch (_: Exception) { }
        }
    }
    @Test fun atomicPersistenceReloadAndFailedReplacementKeepOldSnapshot() {
        val root = Files.createTempDirectory("hazards-test").toFile()
        try {
            val file = root.resolve("hazards/hazards-v1.json")
            val store = NativeHazardStore(file) { from, to -> Files.move(from.toPath(), to.toPath(), ATOMIC_MOVE, REPLACE_EXISTING); Unit }
            assertTrue(store.load().isEmpty())
            store.save(listOf(good)); assertEquals(listOf(good), store.load())
            val next = good.copy(kind = "unconfirmed")
            store.save(listOf(next)); assertEquals(listOf(next), store.load())
            val failing = NativeHazardStore(file) { _, _ -> error("synthetic rename failure") }
            try { failing.save(emptyList()); fail("must fail") } catch (_: IllegalStateException) { }
            assertEquals(listOf(next), store.load())
            assertEquals(listOf("hazards-v1.json"), file.parentFile!!.list()!!.toList())
            try { store.save(listOf(good.copy(lat = Double.NaN))); fail("must reject") }
            catch (_: IllegalArgumentException) { }
            assertEquals(listOf(next), store.load())
        } finally { root.deleteRecursively() }
    }
    @Test fun corruptOrOversizeDiskSnapshotFailsClosed() {
        val root = Files.createTempDirectory("hazards-corrupt").toFile()
        try {
            val file = root.resolve("hazards-v1.json")
            val store = NativeHazardStore(file) { _, _ -> Unit }
            for (raw in listOf("not json", "x".repeat(NativeHazardStore.MAX_BYTES + 1))) {
                file.writeText(raw)
                try { store.load(); fail("corrupt snapshot must fail") } catch (_: Exception) { }
            }
        } finally { root.deleteRecursively() }
    }
}
