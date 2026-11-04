package dev.aiengg.potholereporter.drive

import org.junit.Assert.*
import org.junit.Test

class NativeBumpDetectorTest {
    private fun spike(detector: NativeBumpDetector, start: Long = 1000, value: Double = 7.0,
                      speed: Float? = 10f, rotated: Boolean = false): NativeBumpDetector.Peak? {
        val g = if (rotated) doubleArrayOf(9.81, 0.0, 0.0) else doubleArrayOf(0.0, 0.0, 9.81)
        var result: NativeBumpDetector.Peak? = null
        for (dt in 0L..320L step 20) {
            val a = if (dt < 80) value else 0.0
            detector.sample(start + dt, if (rotated) a else 0.0, 0.0, if (rotated) 0.0 else a, speed, g)
                ?.let { result = it }
        }
        return result
    }

    @Test fun mediumSpikePeaksInWindow() {
        val p = spike(NativeBumpDetector())!!
        assertTrue(p.triggered); assertEquals(7.0, p.peakVertical, 1e-9); assertEquals(1000L, p.elapsedMs)
    }
    @Test fun smoothNoiseNeverTriggers() {
        val d = NativeBumpDetector()
        for (i in 0..5000) assertNull(d.sample(i * 20L, 0.0, 0.0, if (i % 2 == 0) 1.5 else -1.5,
            10f, doubleArrayOf(0.0, 0.0, 9.81)))
    }
    @Test fun lowAndUnknownSpeedIgnored() {
        for (speed in listOf(4.19f, 0f, null, Float.NaN)) assertFalse(spike(NativeBumpDetector(), speed = speed)!!.triggered)
        assertTrue(spike(NativeBumpDetector(), speed = 4.2f)!!.triggered)
    }
    @Test fun refractoryPeriod() {
        val d = NativeBumpDetector()
        assertTrue(spike(d)!!.triggered)
        assertFalse(spike(d, 2000)!!.triggered)
        assertTrue(spike(d, 3000)!!.triggered)
    }
    @Test fun rotatedAndNegativeSpikes() {
        assertTrue(spike(NativeBumpDetector(), rotated = true)!!.triggered)
        assertTrue(spike(NativeBumpDetector(), value = -7.0)!!.triggered)
    }
    @Test fun sensitivityBoundaries() {
        for ((level, limit) in listOf("low" to 6.0, "medium" to 4.5, "high" to 3.0)) {
            assertFalse(spike(NativeBumpDetector(level), value = limit - 0.01)!!.triggered)
            assertTrue(spike(NativeBumpDetector(level), value = limit)!!.triggered)
        }
    }
    @Test fun calibrationPeaksAndConstantMemory() {
        val d = NativeBumpDetector()
        assertFalse(spike(d, value = 2.0)!!.triggered)
        for (i in 2000..102000) {
            d.sample(i * 20L, 0.0, 0.0, 3.0, 10f, doubleArrayOf(0.0, 0.0, 9.81))
            assertTrue(d.retainedSampleCount in 0..1)
        }
    }
    @Test fun fallbackSplitsGravityAndRejectsHorizontalMotion() {
        val d = NativeBumpDetector()
        for (i in 0..100) d.sample(i * 20L, 0.0, 0.0, 9.81, 10f)
        var triggered = false
        for (i in 101..130) {
            val p = d.sample(i * 20L, 0.0, 0.0, if (i < 105) 16.81 else 9.81, 10f)
            triggered = triggered || p?.triggered == true
        }
        assertTrue(triggered)
        assertNull(NativeBumpDetector().sample(10, 7.0, 0.0, 0.0, 10f, doubleArrayOf(0.0, 0.0, 9.81)))
    }
    @Test fun resumeReinitializesGravityWithoutStationaryRotationEvent() {
        val d = NativeBumpDetector()
        d.sample(0, 0.0, 0.0, 9.81, 10f)
        d.resetGravity()
        for (i in 1..30) assertNull(d.sample(i * 20L, 9.81, 0.0, 0.0, 10f))
    }
}
