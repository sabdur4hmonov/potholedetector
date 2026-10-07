package dev.aiengg.potholereporter.drive

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.sqrt

/**
 * Sensor-only, AI-free road shock detection. A wheel dropping into a pothole produces a
 * short, sharp vertical acceleration swing that the phone's accelerometer can feel. This
 * pure class estimates gravity with a low-pass filter (so any mount orientation works),
 * projects each sample onto it, and reports a candidate when the vertical peak-to-peak
 * swing inside a short window crosses the selected threshold.
 *
 * A shock is a candidate, not a confirmed pothole: speed bumps, rail crossings and
 * manholes can feel similar. Reports created from it say so and wait for human review.
 */
internal enum class BumpSensitivity(
    val wireValue: String,
    val peakToPeakMps2: Double,
    val peakMps2: Double
) {
    LOW("low", 11.0, 6.0),
    MEDIUM("medium", 8.0, 4.5),
    HIGH("high", 5.5, 3.0);

    companion object {
        fun fromWire(value: String?): BumpSensitivity =
            entries.firstOrNull { it.wireValue == value } ?: MEDIUM
    }
}

internal data class RoadBumpEvent(
    val elapsedRealtimeMs: Long,
    val peakToPeakMps2: Double,
    val peakMps2: Double,
    val speedMps: Float
)

internal class RoadBumpDetector(private val sensitivity: BumpSensitivity = BumpSensitivity.MEDIUM) {
    private val slow = DoubleArray(3)
    private val fast = DoubleArray(3)
    private var initialized = false
    private var firstMs = 0L
    private var lastMs = 0L
    private var suppressedUntilMs = 0L
    private var lastEventMs = Long.MIN_VALUE / 2
    private val windowTimes = ArrayDeque<Long>()
    private val windowValues = ArrayDeque<Double>()
    private var speedMps: Float? = null
    private var speedAtMs = 0L
    private var pending: RoadBumpEvent? = null

    /** Latest GPS speed and the monotonic time it was measured. */
    fun updateSpeed(speed: Float?, measuredAtElapsedMs: Long) {
        speedMps = speed?.takeIf { it.isFinite() && it >= 0f }
        speedAtMs = measuredAtElapsedMs
    }

    /**
     * One raw accelerometer sample in m/s^2 (gravity included). A shock is held for
     * [CONFIRM_MS] and dropped if the phone turns out to be handled in that time, so the
     * returned event is about that long after the shock itself.
     */
    fun onAcceleration(elapsedMs: Long, x: Float, y: Float, z: Float): RoadBumpEvent? {
        if (!x.isFinite() || !y.isFinite() || !z.isFinite()) return null
        if (!initialized || elapsedMs <= lastMs || elapsedMs - lastMs > MAX_GAP_MS) {
            reset(elapsedMs, x, y, z)
            return null
        }
        val dt = (elapsedMs - lastMs) / 1000.0
        lastMs = elapsedMs
        lowPass(slow, x, y, z, dt / (SLOW_TAU_S + dt))
        lowPass(fast, x, y, z, dt / (FAST_TAU_S + dt))

        val gravity = norm(slow)
        // Picking up, rotating or dropping the phone is not a road shock.
        if (gravity < MIN_GRAVITY_MPS2 || gravity > MAX_GRAVITY_MPS2 ||
            angleDegrees(slow, fast) > ORIENTATION_CHANGE_DEG
        ) {
            suppressedUntilMs = elapsedMs + SETTLE_AFTER_HANDLING_MS
            pending = null
            clearWindow()
            return null
        }
        pending?.let { held ->
            if (elapsedMs - held.elapsedRealtimeMs >= CONFIRM_MS) {
                pending = null
                return held
            }
        }
        val vertical = ((x - slow[0]) * slow[0] + (y - slow[1]) * slow[1] +
            (z - slow[2]) * slow[2]) / gravity
        windowTimes.addLast(elapsedMs)
        windowValues.addLast(vertical)
        while (windowTimes.isNotEmpty() && elapsedMs - windowTimes.first() > WINDOW_MS) {
            windowTimes.removeFirst()
            windowValues.removeFirst()
        }

        if (elapsedMs - firstMs < WARMUP_MS || elapsedMs < suppressedUntilMs) return null
        val speed = speedMps ?: return null
        if (elapsedMs - speedAtMs > SPEED_MAX_AGE_MS || speed < MIN_SPEED_MPS) return null
        if (elapsedMs - lastEventMs < REFRACTORY_MS) return null

        var low = Double.MAX_VALUE
        var high = -Double.MAX_VALUE
        var peak = 0.0
        for (value in windowValues) {
            if (value < low) low = value
            if (value > high) high = value
            if (abs(value) > peak) peak = abs(value)
        }
        val peakToPeak = high - low
        if (peakToPeak < sensitivity.peakToPeakMps2 || peak < sensitivity.peakMps2) return null
        lastEventMs = elapsedMs
        clearWindow()
        pending = RoadBumpEvent(elapsedMs, peakToPeak, peak, speed)
        return null
    }

    private fun reset(elapsedMs: Long, x: Float, y: Float, z: Float) {
        slow[0] = x.toDouble(); slow[1] = y.toDouble(); slow[2] = z.toDouble()
        slow.copyInto(fast)
        initialized = true
        pending = null
        firstMs = elapsedMs
        lastMs = elapsedMs
        clearWindow()
    }

    private fun clearWindow() {
        windowTimes.clear()
        windowValues.clear()
    }

    private fun lowPass(state: DoubleArray, x: Float, y: Float, z: Float, alpha: Double) {
        state[0] += (x - state[0]) * alpha
        state[1] += (y - state[1]) * alpha
        state[2] += (z - state[2]) * alpha
    }

    private fun norm(v: DoubleArray) = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])

    private fun angleDegrees(a: DoubleArray, b: DoubleArray): Double {
        val na = norm(a)
        val nb = norm(b)
        if (na == 0.0 || nb == 0.0) return 180.0
        val cos = ((a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (na * nb)).coerceIn(-1.0, 1.0)
        return Math.toDegrees(acos(cos))
    }

    companion object {
        /** About 14 km/h. Slower shocks are mostly parking, kerbs and speed bumps. */
        const val MIN_SPEED_MPS = 4.0f
        const val WINDOW_MS = 300L
        const val REFRACTORY_MS = 1_500L
        const val WARMUP_MS = 2_000L
        const val MAX_GAP_MS = 250L
        const val SPEED_MAX_AGE_MS = 3_000L
        const val SLOW_TAU_S = 1.0
        const val FAST_TAU_S = 0.2
        const val CONFIRM_MS = 600L
        const val ORIENTATION_CHANGE_DEG = 25.0
        const val SETTLE_AFTER_HANDLING_MS = 2_000L
        const val MIN_GRAVITY_MPS2 = 7.0
        const val MAX_GRAVITY_MPS2 = 12.5
    }
}

/**
 * Chooses which recent complete camera frame shows the road the wheel just hit. The
 * windscreen camera sees the pothole a few metres before the wheel reaches it, so the
 * chosen frame is the one captured about [LEAD_DISTANCE_M] earlier at the current speed.
 * The whole frame is kept as evidence; nothing is cropped.
 */
internal object SensorEvidencePolicy {
    const val LEAD_DISTANCE_M = 8.0
    const val MIN_LEAD_MS = 300L
    const val MAX_LEAD_MS = 2_500L
    const val MIN_BEFORE_HIT_MS = 150L
    const val MAX_FRAME_AGE_MS = 4_000L
    /** A shock that found no frame within this time is dropped. */
    const val MAX_PENDING_MS = 10_000L

    fun leadMs(speedMps: Float): Long {
        if (!speedMps.isFinite() || speedMps <= 0f) return MAX_LEAD_MS
        return (LEAD_DISTANCE_M / speedMps * 1000.0).toLong().coerceIn(MIN_LEAD_MS, MAX_LEAD_MS)
    }

    /** Index of the best earlier frame, or null when no frame was captured before the hit. */
    fun selectFrame(frameElapsedMs: List<Long>, bumpElapsedMs: Long, speedMps: Float): Int? {
        val target = bumpElapsedMs - leadMs(speedMps)
        var best: Int? = null
        var bestDistance = Long.MAX_VALUE
        frameElapsedMs.forEachIndexed { index, capturedAt ->
            val beforeHit = bumpElapsedMs - capturedAt
            if (beforeHit < MIN_BEFORE_HIT_MS || beforeHit > MAX_FRAME_AGE_MS) return@forEachIndexed
            val distance = abs(capturedAt - target)
            if (distance < bestDistance) {
                best = index
                bestDistance = distance
            }
        }
        return best
    }
}
