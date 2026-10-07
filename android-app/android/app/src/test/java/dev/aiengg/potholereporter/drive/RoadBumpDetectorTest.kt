package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.cos
import kotlin.math.sin
import kotlin.random.Random

class RoadBumpDetectorTest {
    /** A phone tilted in its holder: gravity is spread across all three axes. */
    private val up = doubleArrayOf(0.30, 0.80, 0.52).let { v ->
        val n = kotlin.math.sqrt(v.sumOf { it * it }); DoubleArray(3) { v[it] / n }
    }
    private val sideways = doubleArrayOf(0.94, -0.34, 0.0)

    private class Drive(val detector: RoadBumpDetector) {
        var t = 1_000L
        val events = mutableListOf<RoadBumpEvent>()
    }

    private fun drive(
        sensitivity: BumpSensitivity = BumpSensitivity.MEDIUM,
        speed: Float? = 10f
    ) = Drive(RoadBumpDetector(sensitivity)).also { it.detector.updateSpeed(speed, it.t) }

    /** Feeds [ms] of 50 Hz samples; [vertical]/[lateral] add road motion at time offset. */
    private fun Drive.feed(
        ms: Long,
        noise: Double = 0.6,
        seed: Int = 1,
        speed: Float? = 10f,
        vertical: (Long) -> Double = { 0.0 },
        lateral: (Long) -> Double = { 0.0 },
        gravity: (Long) -> DoubleArray = { up }
    ) {
        val random = Random(seed)
        val start = t
        while (t - start < ms) {
            t += 20
            detector.updateSpeed(speed, t)
            val g = gravity(t - start)
            val v = vertical(t - start) + random.nextDouble(-noise, noise)
            val l = lateral(t - start) + random.nextDouble(-noise, noise)
            val sample = DoubleArray(3) { 9.81 * g[it] + v * g[it] + l * sideways[it] }
            detector.onAcceleration(t, sample[0].toFloat(), sample[1].toFloat(), sample[2].toFloat())
                ?.let(events::add)
        }
    }

    private fun pothole(at: Long, depth: Double = 7.0): (Long) -> Double = { offset ->
        when (offset - at) {
            in 0L..60L -> -depth
            in 61L..140L -> depth
            else -> 0.0
        }
    }

    @Test fun smoothRoadProducesNothing() {
        val d = drive()
        d.feed(20_000, noise = 1.2)
        assertTrue(d.events.isEmpty())
    }

    @Test fun sharpVerticalDropAndReboundIsReportedOnce() {
        val d = drive()
        d.feed(3_000)
        d.feed(3_000, vertical = pothole(1_000))
        assertEquals(1, d.events.size)
        val event = d.events.single()
        // Held for confirmation, then reported with the time of the shock itself.
        assertTrue(event.elapsedRealtimeMs in 5_000L..5_160L)
        assertTrue(event.peakToPeakMps2 >= BumpSensitivity.MEDIUM.peakToPeakMps2)
        assertEquals(10f, event.speedMps)
    }

    @Test fun worksInAnyMountOrientation() {
        val flat = doubleArrayOf(0.0, 0.0, 1.0)
        val d = drive()
        d.feed(3_000, gravity = { flat })
        d.feed(3_000, vertical = pothole(1_000), gravity = { flat })
        assertEquals(1, d.events.size)
    }

    @Test fun sensitivityChangesTheThreshold() {
        val gentle = pothole(1_000, depth = 3.3)
        val medium = drive(BumpSensitivity.MEDIUM)
        medium.feed(3_000); medium.feed(3_000, vertical = gentle)
        val high = drive(BumpSensitivity.HIGH)
        high.feed(3_000); high.feed(3_000, vertical = gentle)
        assertTrue(medium.events.isEmpty())
        assertEquals(1, high.events.size)
        val hard = pothole(1_000, depth = 4.8)
        val low = drive(BumpSensitivity.LOW)
        low.feed(3_000); low.feed(3_000, vertical = hard)
        assertTrue(low.events.isEmpty())
    }

    @Test fun slowOrUnknownSpeedNeverReports() {
        val slow = drive(speed = 2f)
        slow.feed(3_000, speed = 2f)
        slow.feed(3_000, speed = 2f, vertical = pothole(1_000))
        assertTrue(slow.events.isEmpty())
        val unknown = drive(speed = null)
        unknown.feed(3_000, speed = null)
        unknown.feed(3_000, speed = null, vertical = pothole(1_000))
        assertTrue(unknown.events.isEmpty())
    }

    @Test fun staleSpeedNeverReports() {
        val d = drive()
        d.feed(3_000)
        val speedAt = d.t
        d.detector.updateSpeed(10f, speedAt)
        // Feed samples without refreshing speed for longer than the allowed age.
        repeat(250) {
            d.t += 20
            val v = if (d.t - speedAt in 4_000L..4_060L) -7.0
                else if (d.t - speedAt in 4_061L..4_140L) 7.0 else 0.0
            d.detector.onAcceleration(
                d.t,
                ((9.81 + v) * up[0]).toFloat(), ((9.81 + v) * up[1]).toFloat(),
                ((9.81 + v) * up[2]).toFloat()
            )?.let(d.events::add)
        }
        assertTrue(d.events.isEmpty())
    }

    @Test fun warmupIgnoresTheFirstSeconds() {
        val d = drive()
        d.feed(3_000, vertical = pothole(500))
        assertTrue(d.events.isEmpty())
    }

    @Test fun twoHitsCloseTogetherCountOnceThenRefractoryEnds() {
        val d = drive()
        d.feed(3_000)
        d.feed(1_000, vertical = pothole(100))
        d.feed(1_000, vertical = pothole(100))
        assertEquals(1, d.events.size)
        d.feed(3_000, vertical = pothole(1_000))
        assertEquals(2, d.events.size)
    }

    @Test fun pickingUpThePhoneIsNotARoadShock() {
        val d = drive()
        d.feed(3_000)
        // Rotate the phone by ~60 degrees over 0.6 s with a jolt in the middle.
        d.feed(3_000, vertical = pothole(300), gravity = { offset ->
            val angle = Math.toRadians(60.0 * (offset.coerceAtMost(600L) / 600.0))
            val c = cos(angle); val s = sin(angle)
            DoubleArray(3) { up[it] * c + sideways[it] * s }.let { v ->
                val n = kotlin.math.sqrt(v.sumOf { x -> x * x }); DoubleArray(3) { v[it] / n }
            }
        })
        assertTrue(d.events.isEmpty())
    }

    @Test fun sensorGapResetsInsteadOfMisreading() {
        val d = drive()
        d.feed(3_000)
        d.t += 2_000
        d.feed(1_000, vertical = pothole(300))
        assertTrue(d.events.isEmpty())
    }

    @Test fun invalidSamplesAreIgnored() {
        val detector = RoadBumpDetector()
        assertNull(detector.onAcceleration(10, Float.NaN, 0f, 9.8f))
        assertNull(detector.onAcceleration(20, 0f, Float.POSITIVE_INFINITY, 9.8f))
    }

    @Test fun sensitivityWireValues() {
        assertEquals(BumpSensitivity.LOW, BumpSensitivity.fromWire("low"))
        assertEquals(BumpSensitivity.HIGH, BumpSensitivity.fromWire("high"))
        assertEquals(BumpSensitivity.MEDIUM, BumpSensitivity.fromWire("medium"))
        assertEquals(BumpSensitivity.MEDIUM, BumpSensitivity.fromWire(null))
        assertEquals(BumpSensitivity.MEDIUM, BumpSensitivity.fromWire("extreme"))
    }

    @Test fun evidenceFrameIsTheOneCapturedBeforeTheWheelHit() {
        // Frames every 500 ms; hit at 10_000 ms at 10 m/s -> lead 800 ms -> target 9_200.
        val frames = listOf(7_000L, 7_500L, 8_000L, 8_500L, 9_000L, 9_500L, 10_000L, 10_500L)
        assertEquals(800L, SensorEvidencePolicy.leadMs(10f))
        assertEquals(4, SensorEvidencePolicy.selectFrame(frames, 10_000L, 10f))
        // Slow: 8 m at 4 m/s = 2 s earlier.
        assertEquals(2, SensorEvidencePolicy.selectFrame(frames, 10_000L, 4f))
        // Very fast: lead clamps to 300 ms; the frame must still precede the hit by 150 ms.
        assertEquals(5, SensorEvidencePolicy.selectFrame(frames, 10_000L, 40f))
    }

    @Test fun noFrameWithoutEarlierEvidence() {
        assertNull(SensorEvidencePolicy.selectFrame(listOf(10_000L, 10_400L), 10_000L, 10f))
        assertNull(SensorEvidencePolicy.selectFrame(listOf(1_000L), 10_000L, 10f))
        assertNull(SensorEvidencePolicy.selectFrame(emptyList(), 10_000L, 10f))
        assertEquals(SensorEvidencePolicy.MAX_LEAD_MS, SensorEvidencePolicy.leadMs(0f))
        assertEquals(SensorEvidencePolicy.MAX_LEAD_MS, SensorEvidencePolicy.leadMs(Float.NaN))
    }
}
