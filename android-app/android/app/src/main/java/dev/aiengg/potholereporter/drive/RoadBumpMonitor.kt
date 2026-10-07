package dev.aiengg.potholereporter.drive

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs

/**
 * Feeds the accelerometer into [RoadBumpDetector] on its own thread. The accelerometer
 * needs no runtime permission and nothing it measures leaves the phone.
 */
internal class RoadBumpMonitor(
    context: Context,
    sensitivity: BumpSensitivity,
    private val latestFix: () -> GpsFix?,
    private val onBump: (RoadBumpEvent) -> Unit
) : SensorEventListener {
    private val manager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
    private val sensor = manager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val detector = RoadBumpDetector(sensitivity)
    private var thread: HandlerThread? = null
    private val shocks = AtomicInteger()

    val isAvailable: Boolean get() = sensor != null
    val shockCount: Int get() = shocks.get()

    @Synchronized
    fun start(): Boolean {
        if (thread != null) return true
        val accelerometer = sensor ?: return false
        val sensorManager = manager ?: return false
        val worker = HandlerThread("road-bump-sensor").apply { start() }
        val registered = sensorManager.registerListener(
            this, accelerometer, SAMPLING_PERIOD_US, Handler(worker.looper)
        )
        if (!registered) {
            worker.quitSafely()
            return false
        }
        thread = worker
        return true
    }

    @Synchronized
    fun stop() {
        runCatching { manager?.unregisterListener(this) }
        thread?.quitSafely()
        thread = null
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.values.size < 3) return
        val now = SystemClock.elapsedRealtime()
        // Sensor timestamps share the elapsed-realtime clock on current Android; fall back
        // to receipt time on a device whose clock base differs.
        val stamped = event.timestamp / 1_000_000L
        val elapsedMs = if (abs(stamped - now) <= MAX_CLOCK_SKEW_MS) stamped else now
        val fix = latestFix()
        detector.updateSpeed(fix?.speedMps, fix?.elapsedRealtimeMs ?: 0L)
        detector.onAcceleration(elapsedMs, event.values[0], event.values[1], event.values[2])
            ?.let { bump ->
                shocks.incrementAndGet()
                runCatching { onBump(bump) }
            }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    companion object {
        /** 50 Hz is enough for a ~100 ms wheel drop and needs no high-rate permission. */
        const val SAMPLING_PERIOD_US = 20_000
        const val MAX_CLOCK_SKEW_MS = 1_000L
    }
}
