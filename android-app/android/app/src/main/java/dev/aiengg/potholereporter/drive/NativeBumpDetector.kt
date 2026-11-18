package dev.aiengg.potholereporter.drive

import kotlin.math.abs
import kotlin.math.sqrt

/** Constant-memory 300 ms peak accumulator. Acceleration and gravity use device axes. */
internal class NativeBumpDetector(sensitivity: String = "medium") {
    data class Peak(val elapsedMs: Long, val peakVertical: Double, val speedMps: Float?, val triggered: Boolean)
    private val threshold = when (sensitivity) { "low" -> 6.0; "high" -> 3.0; else -> 4.5 }
    private val gravity = DoubleArray(3)
    private var initialized = false
    private var lastSample = -1L
    private var windowStart = -1L
    private var peakTime = 0L
    private var peak = 0.0
    private var peakSpeed: Float? = null
    private var lastEvent = -2_000L
    // No sample list: only the current peak and three low-pass state values survive.
    val retainedSampleCount: Int get() = if (windowStart >= 0) 1 else 0

    fun sample(elapsedMs: Long, x: Double, y: Double, z: Double, speedMps: Float?,
               gravityVector: DoubleArray? = null): Peak? {
        if (elapsedMs <= lastSample || !x.isFinite() || !y.isFinite() || !z.isFinite()) return null
        lastSample = elapsedMs
        val linear: DoubleArray
        val g: DoubleArray
        if (gravityVector != null) {
            if (gravityVector.size != 3 || gravityVector.any { !it.isFinite() }) return null
            g = gravityVector
            linear = doubleArrayOf(x, y, z)
        } else {
            val raw = doubleArrayOf(x, y, z)
            if (!initialized) { raw.copyInto(gravity); initialized = true; return null }
            for (i in 0..2) gravity[i] = 0.8 * gravity[i] + 0.2 * raw[i]
            g = gravity
            linear = DoubleArray(3) { raw[it] - g[it] }
        }
        val norm = sqrt(g.sumOf { it * it })
        if (norm < 1.0) return null
        val vertical = (linear[0] * g[0] + linear[1] * g[1] + linear[2] * g[2]) / norm
        val completed = if (windowStart >= 0 && elapsedMs - windowStart >= 300) finishWindow() else null
        if (abs(vertical) >= 2.0) {
            if (windowStart < 0) windowStart = elapsedMs
            if (abs(vertical) > abs(peak)) { peak = vertical; peakTime = elapsedMs; peakSpeed = speedMps }
        }
        return completed
    }

    fun flush(): Peak? = if (windowStart >= 0) finishWindow() else null

    fun resetGravity() { initialized = false; gravity.fill(0.0) }

    private fun finishWindow(): Peak {
        val speed = peakSpeed?.takeIf { it.isFinite() && it >= 4.2f }
        val triggered = abs(peak) >= threshold && speed != null && peakTime - lastEvent >= 2_000
        if (triggered) lastEvent = peakTime
        val result = Peak(peakTime, peak, peakSpeed, triggered)
        windowStart = -1L; peak = 0.0; peakSpeed = null
        return result
    }
}

internal object NativeSensorEventPolicy {
    fun selectFrame(eventMs: Long, frameTimes: List<Long>): Int? = frameTimes.indices
        .filter { frameTimes[it] in (eventMs - 4_000)..(eventMs - 150) }
        .maxByOrNull { frameTimes[it] }

    fun canMerge(sameDrive: Boolean, sensorSource: Boolean, distanceMeters: Double): Boolean =
        sameDrive && sensorSource && distanceMeters.isFinite() && distanceMeters >= 0 && distanceMeters <= 15.0
}
