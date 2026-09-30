package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.EventSightingEntity
import dev.aiengg.potholereporter.db.ReportEntity
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

class NativeRoadEventMatcherParityTest {
    private fun JSONObject.string(key: String, fallback: String? = null): String? =
        if (!has(key)) fallback else if (isNull(key)) null else getString(key)

    private fun JSONObject.number(key: String, fallback: Double? = null): Double? =
        if (!has(key)) fallback else if (isNull(key)) null else getDouble(key)

    private fun JSONObject.long(key: String, fallback: Long? = null): Long? =
        if (!has(key)) fallback else if (isNull(key)) null else getLong(key)

    private fun report(patch: JSONObject, prior: Boolean) = ReportEntity(
        createdAt = patch.long("created_at", 1_800_000_000L)!!,
        lat = patch.number("lat", 0.0), lng = patch.number("lng", 0.0),
        status = patch.string("status", "draft")!!,
        decision = patch.string("decision", "accept"),
        driveId = patch.string("drive_id", if (prior) "drive-a" else "drive-b"),
        captureSource = patch.string("capture_source", "drive_live")!!,
        sourceEventKey = patch.string("source_event_key"),
        capturedAt = patch.long("captured_at", 1_800_000_000L),
        sourceOffsetS = patch.number("source_offset_s", 100.0),
        gpsAccuracy = patch.number("gps_accuracy", 5.0)?.toFloat(),
        speedMps = patch.number("speed_mps", 8.0)?.toFloat(),
        heading = patch.number("heading", 90.0)?.toFloat(),
        damageType = patch.string("damage_type", "pothole_cavity"),
        size = patch.string("size", "medium"),
        lastSeenAt = patch.long("last_seen_at"),
        debugCapture = patch.optBoolean("debug_capture", false),
        dedupeEligible = patch.optBoolean("dedupe_eligible", true)
    )

    private fun sighting(patch: JSONObject) = EventSightingEntity(
        reportId = 1,
        driveId = patch.string("drive_id"),
        lat = patch.number("lat"), lng = patch.number("lng"),
        sourceOffsetS = patch.number("source_offset_s"),
        capturedAt = patch.long("captured_at"),
        gpsAccuracy = patch.number("gps_accuracy")?.toFloat(),
        speedMps = patch.number("speed_mps")?.toFloat(),
        heading = patch.number("heading")?.toFloat(),
        sourceEventKey = patch.string("source_event_key")
    )

    @Test fun sharedRoadEventCases() {
        val stream = requireNotNull(javaClass.classLoader?.getResourceAsStream("road-event-match-v1.json"))
        val fixture = JSONObject(stream.bufferedReader().use { it.readText() })
        assertEquals(1, fixture.getInt("version"))
        val cases = fixture.getJSONArray("cases")
        assertEquals(20, cases.length())
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val sightingsJson = case.optJSONArray("sightings")
            val sightings = (0 until (sightingsJson?.length() ?: 0)).map {
                sighting(sightingsJson!!.getJSONObject(it))
            }
            val keysJson = case.optJSONArray("prior_keys")
            val keys = (0 until (keysJson?.length() ?: 0)).map { keysJson!!.getString(it) }
            val expected = if (case.isNull("expect")) null else case.getString("expect")
            assertEquals(case.getString("name"), expected, NativeRoadEventMatcher.match(
                report(case.optJSONObject("candidate") ?: JSONObject(), false),
                report(case.optJSONObject("prior") ?: JSONObject(), true), sightings, keys
            ))
        }
    }
}
