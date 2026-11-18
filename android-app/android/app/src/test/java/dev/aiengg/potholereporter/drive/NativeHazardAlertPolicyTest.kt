package dev.aiengg.potholereporter.drive

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.*

class NativeHazardAlertPolicyTest {
    private fun hazard(id: String = "a", meters: Double = 250.0, bearing: Double = 0.0,
                       kind: String = "confirmed"): NativeHazard {
        val angular = meters / 6_371_000.0; val angle = Math.toRadians(bearing)
        return NativeHazard(id, Math.toDegrees(asin(sin(angular) * cos(angle))),
            Math.toDegrees(atan2(sin(angle) * sin(angular), cos(angular))), kind)
    }
    private fun fix(ms: Long = 0, speed: Double = 50.0 / 3.6, heading: Double = 0.0,
                    accuracy: Double = 5.0, lat: Double = 0.0, lng: Double = 0.0) =
        NativeHazardAlertPolicy.Fix(lat, lng, accuracy, speed, heading, ms)
    @Test fun leadDistanceAtRequestedSpeedsAndSettings() {
        for ((kmh, expected) in listOf(50 to 277.7778, 20 to 111.1111, 120 to 666.6667, 140 to 700.0, 12 to 80.0)) {
            assertEquals(expected, NativeHazardAlertPolicy.leadDistance(kmh / 3.6), 0.001)
            val policy = NativeHazardAlertPolicy()
            policy.replace(listOf(hazard(meters = expected - 0.01)))
            assertNotNull(policy.evaluate(fix(speed = kmh / 3.6)))
            assertNull(policy.evaluate(fix(ms = 4_000, speed = kmh / 3.6)))
        }
        assertEquals(100.0, NativeHazardAlertPolicy.leadDistance(10.0, 10), 0.001)
        assertEquals(300.0, NativeHazardAlertPolicy.leadDistance(10.0, 30), 0.001)
    }
    @Test fun outsideLeadDistanceDoesNotFire() {
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard(meters = 279.0)))
        assertNull(p.evaluate(fix()))
    }
    @Test fun behindAndOffHeadingExcludedButCurveExceptionIncluded() {
        for (bearing in listOf(180.0, 40.0)) {
            val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard(meters = 200.0, bearing = bearing)))
            assertNull(p.evaluate(fix()))
        }
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard(meters = 35.0, bearing = 180.0)))
        assertNotNull(p.evaluate(fix()))
    }
    @Test fun headingWrapAndEitherDirection() {
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard(bearing = 5.0)))
        assertNotNull(p.evaluate(fix(heading = 355.0)))
        val back = NativeHazardAlertPolicy(); back.replace(listOf(hazard(bearing = 180.0)))
        assertNotNull(back.evaluate(fix(heading = 180.0)))
    }
    @Test fun speedAccuracyAndInvalidFixesIgnored() {
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard()))
        for (f in listOf(fix(speed = 2.99), fix(accuracy = 30.01), fix(accuracy = -1.0),
            fix(speed = Double.NaN), fix(heading = Double.NaN), fix(lat = 91.0), fix(lng = Double.POSITIVE_INFINITY))) {
            assertNull(p.evaluate(f))
        }
        assertNotNull(p.evaluate(fix(accuracy = 30.0)))
    }
    @Test fun rearmOnlyAfterLeavingRadiusAndReturning() {
        val p = NativeHazardAlertPolicy(); val h = hazard(); p.replace(listOf(h))
        assertNotNull(p.evaluate(fix()))
        assertNull(p.evaluate(fix(ms = 5_000)))
        p.replace(listOf(h)) // WebView resync must not reset one-shot state.
        assertNull(p.evaluate(fix(ms = 10_000)))
        assertNull(p.evaluate(fix(ms = 15_000, lat = -0.01)))
        assertNotNull(p.evaluate(fix(ms = 20_000)))
    }
    @Test fun minimumRearmRadiusIs300Meters() {
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard(meters = 50.0)))
        assertNotNull(p.evaluate(fix(speed = 3.0)))
        assertNull(p.evaluate(fix(ms = 5_000, speed = 3.0, lat = -0.001)))
        assertNull(p.evaluate(fix(ms = 10_000, speed = 3.0)))
        p.evaluate(fix(ms = 15_000, speed = 3.0, lat = -0.004))
        assertNotNull(p.evaluate(fix(ms = 20_000, speed = 3.0)))
    }
    @Test fun groupCloseHazardsAndQueueInDistanceOrder() {
        val p = NativeHazardAlertPolicy()
        p.replace(listOf(hazard("far", 250.0), hazard("near", 100.0), hazard("near2", 120.0, kind = "unconfirmed")))
        val first = p.evaluate(fix())!!
        assertEquals(listOf("near", "near2"), first.ids); assertTrue(first.possible)
        assertEquals(1, p.pendingCount)
        assertNull(p.evaluate(fix(ms = 3_999)))
        assertEquals(listOf("far"), p.evaluate(fix(ms = 4_000))!!.ids)
        assertNull(p.evaluate(fix(ms = 8_000)))
    }
    @Test fun queuedHazardThatIsPassedIsNotSpoken() {
        val p = NativeHazardAlertPolicy(); p.replace(listOf(hazard("a", 100.0), hazard("b", 250.0)))
        assertNotNull(p.evaluate(fix()))
        assertNull(p.evaluate(fix(ms = 4_000, lat = 0.005)))
    }
    @Test fun unconfirmedSettingAndDeletion() {
        val p = NativeHazardAlertPolicy(includeUnconfirmed = false)
        p.replace(listOf(hazard(kind = "unconfirmed")))
        assertEquals(0, p.loadedCount); assertNull(p.evaluate(fix()))
        p.replace(emptyList()); assertNull(p.evaluate(fix(ms = 5_000)))
    }
    @Test fun fiveThousandHazardsUseSpatialIndex() {
        val p = NativeHazardAlertPolicy()
        p.replace((0 until 4_999).map { NativeHazard("$it", 10.0 + it / 100.0, 20.0, "confirmed") } + hazard())
        assertNotNull(p.evaluate(fix()))
        assertTrue("GPS fix must not examine the entire hazard list", p.examinedLastFix < 10)
        repeat(100) { assertNull(p.evaluate(fix(ms = (it + 1) * 5000L))) }
    }
    @Test fun antimeridianAndPolarBucketsRemainBounded() {
        val p = NativeHazardAlertPolicy()
        p.replace(listOf(NativeHazard("date", 0.0, -179.999, "confirmed")))
        assertNotNull(p.evaluate(fix(lng = 179.999, heading = 90.0)))
        val polar = NativeHazardAlertPolicy()
        polar.replace(listOf(NativeHazard("pole", 89.9999, 180.0, "confirmed")))
        assertNotNull(polar.evaluate(fix(lat = 89.9999, lng = 0.0, heading = 0.0)))
        assertTrue(polar.examinedLastFix <= 1)
    }
}
