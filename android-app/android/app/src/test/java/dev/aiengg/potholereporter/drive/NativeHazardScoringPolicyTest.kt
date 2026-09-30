package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.ReportEntity
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeHazardScoringPolicyTest {
    private fun value(defaults: JSONObject, patch: JSONObject, key: String): Any? {
        val source = if (patch.has(key)) patch else defaults
        return if (source.isNull(key)) null else source.get(key)
    }

    private fun report(defaults: JSONObject, patch: JSONObject) = ReportEntity(
        decision = value(defaults, patch, "decision") as String?,
        isPothole = (value(defaults, patch, "is_pothole") as Number).toInt(),
        isReportable = (value(defaults, patch, "is_reportable") as Number).toInt(),
        debugCapture = value(defaults, patch, "debug_capture") as Boolean,
        driveId = value(defaults, patch, "drive_id") as String?,
        sightingDriveIdsJson = (value(defaults, patch, "sighting_drive_ids") as JSONArray).toString(),
        seenCount = (value(defaults, patch, "seen_count") as Number).toInt(),
        lastSeenAt = (value(defaults, patch, "last_seen_at") as? Number)?.toLong(),
        size = value(defaults, patch, "size") as String?
    )

    @Test fun sharedScoreCasesAndRepeatedExecution() {
        val stream = requireNotNull(javaClass.classLoader?.getResourceAsStream("hazard-scoring-v1.json"))
        val fixture = JSONObject(stream.bufferedReader().use { it.readText() })
        assertEquals(1, fixture.getInt("version"))
        val windowJson = fixture.getJSONObject("window")
        val window = HazardFreshnessWindow(
            windowJson.getLong("fresh_through_s"), windowJson.getLong("stale_after_s")
        )
        val defaults = fixture.getJSONObject("defaults")
        val cases = fixture.getJSONArray("cases")
        assertEquals(18, cases.length())
        for (index in 0 until cases.length()) {
            val row = cases.getJSONObject(index)
            val patch = row.optJSONObject("report") ?: JSONObject()
            val input = report(defaults, patch)
            val conditionStatus = value(defaults, patch, "condition_status") as String?
            val first = NativeHazardScoringPolicy.score(
                input, fixture.getLong("reference_at_s"), window, conditionStatus)
            val second = NativeHazardScoringPolicy.score(
                input, fixture.getLong("reference_at_s"), window, conditionStatus)
            val expected = row.getJSONObject("expect")
            val id = row.getString("id")
            assertEquals(id, expected.getString("confidence"), first.confidence.name.lowercase())
            assertEquals(id, expected.getInt("confidence_rank"), first.confidence.rank)
            assertEquals(id, expected.getString("freshness"), first.freshness.name.lowercase())
            assertEquals(id, expected.getInt("freshness_rank"), first.freshness.rank)
            assertEquals(id, expected.getString("severity"), first.severity.name.lowercase())
            assertEquals(id, expected.getInt("severity_rank"), first.severity.rank)
            assertEquals(id, expected.getInt("independent_drive_count"), first.independentDriveCount)
            assertEquals(id, if (expected.isNull("is_fixed")) null else expected.getBoolean("is_fixed"), first.isFixed)
            assertEquals(id, first, second)
            assertTrue(id, first.confidence.rank in 0..2)
            assertTrue(id, first.freshness.rank in 0..2)
            assertTrue(id, first.severity.rank in 0..3)
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun freshnessWindowMustBeExplicitAndOrdered() {
        HazardFreshnessWindow(10, 10)
    }
}
