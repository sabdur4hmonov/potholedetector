package dev.aiengg.potholereporter.drive

import android.content.Context
import android.graphics.BitmapFactory
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.SystemClock
import androidx.room.withTransaction
import dev.aiengg.potholereporter.db.PotholeDatabase
import dev.aiengg.potholereporter.db.ReportEntity
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File
import java.time.Instant
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs

/** Local-only sensor adapter. This class has no detector client, usage budget or network API. */
internal class NativeSensorDrive(
    private val context: Context,
    private val sessionId: String,
    sensitivity: String,
    private val latestFix: () -> GpsFix?,
    private val nearestFix: (Long) -> GpsFix?,
    private val capturing: () -> Boolean,
    private val onReport: (Long, Boolean) -> Unit,
    private val onIssue: (String) -> Unit,
    private val onDeletedBytes: (Long) -> Unit
) : SensorEventListener {
    private val manager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
    private val detector = NativeBumpDetector(sensitivity)
    private val linear = manager?.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)
    private val gravitySensor = manager?.getDefaultSensor(Sensor.TYPE_GRAVITY)
    private val accelerometer = manager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private var gravity: DoubleArray? = null
    private var gravityElapsedMs = 0L
    private var registered = false
    private val peaks = Channel<NativeBumpDetector.Peak>(64)
    private val frameMutex = Mutex()
    private data class Frame(val id: Long, val elapsedMs: Long)
    private val frames = ArrayDeque<Frame>()
    private val db = PotholeDatabase.getDatabase(context)
    private var rows = 0
    private val wallAnchor = System.currentTimeMillis()
    private val elapsedAnchor = SystemClock.elapsedRealtime()
    private val log = logFile(context, sessionId)
    @Volatile var bumpCount = 0
        private set
    private val missingCount = AtomicInteger(0)
    val withoutFrame: Int get() = missingCount.get()
    @Volatile var issue: String? = null
        private set

    fun initialize() {
        check(log.parentFile!!.isDirectory || log.parentFile!!.mkdirs()) { "Sensor log storage unavailable" }
        log.writeText("elapsedMs,wallclock,peak,speed,lat,lng,accuracy,triggered\n")
    }

    fun updateRegistration(enabled: Boolean) {
        if (!enabled) { unregister(); return }
        if (registered) return
        val paired = linear != null && gravitySensor != null
        val sensor = if (paired) linear else accelerometer
        if (sensor == null) { fail("No accelerometer available; sensor detection is unavailable"); return }
        val gravityOk = !paired || manager?.registerListener(this, gravitySensor, SensorManager.SENSOR_DELAY_GAME) == true
        val motionOk = gravityOk && manager?.registerListener(this, sensor, SensorManager.SENSOR_DELAY_GAME) == true
        registered = motionOk
        if (!motionOk) { manager?.unregisterListener(this); fail("Accelerometer could not start; sensor detection is unavailable") }
    }

    fun unregister() {
        manager?.unregisterListener(this)
        registered = false; gravity = null
        detector.flush()?.let(::enqueue)
        detector.resetGravity()
    }

    fun closeInput() { unregister(); peaks.close() }

    private fun fail(message: String) {
        if (issue == message) return
        issue = message; onIssue(message)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
    override fun onSensorChanged(event: SensorEvent) {
        if (!registered || !capturing()) return
        val elapsed = event.timestamp / 1_000_000
        if (event.sensor.type == Sensor.TYPE_GRAVITY) {
            gravity = DoubleArray(3) { event.values[it].toDouble() }; gravityElapsedMs = elapsed
            return
        }
        val fix = latestFix()?.takeIf { elapsed - it.elapsedRealtimeMs in 0..5_000 &&
            it.accuracy?.let { a -> a.isFinite() && a <= 30f } == true }
        val g = if (event.sensor.type == Sensor.TYPE_LINEAR_ACCELERATION) {
            gravity?.takeIf { elapsed - gravityElapsedMs in 0..1_000 } ?: return
        } else null
        detector.sample(elapsed, event.values[0].toDouble(), event.values[1].toDouble(),
            event.values[2].toDouble(), fix?.speedMps, g)?.let(::enqueue)
    }

    private fun enqueue(peak: NativeBumpDetector.Peak) {
        if (peak.triggered) bumpCount++
        if (!peaks.trySend(peak).isSuccess) {
            if (peak.triggered) missingCount.incrementAndGet()
            fail("Sensor processing queue full; some peaks were not saved")
        }
    }

    suspend fun registerFrame(id: Long, elapsedMs: Long) = frameMutex.withLock {
        // A sensor JPEG is never AI replay work, including after process death.
        db.driveKeyframeDao().markAnalyzed(id)
        frames.addLast(Frame(id, elapsedMs))
        while (frames.size > 16 || (frames.firstOrNull()?.elapsedMs ?: elapsedMs) < elapsedMs - 8_000) {
            deleteFrame(frames.removeFirst().id)
        }
    }

    suspend fun consume() {
        for (peak in peaks) {
            val fix = nearestFix(peak.elapsedMs)?.takeIf { abs(it.elapsedRealtimeMs - peak.elapsedMs) <= 5_000 }
            try {
                if (rows < 20_000) {
                    val time = Instant.ofEpochMilli(wallAnchor + peak.elapsedMs - elapsedAnchor)
                    log.appendText(listOf(peak.elapsedMs, time, peak.peakVertical, peak.speedMps ?: "",
                        fix?.lat ?: "", fix?.lng ?: "", fix?.accuracy ?: "", if (peak.triggered) 1 else 0)
                        .joinToString(",") + "\n")
                    rows++
                }
                if (peak.triggered) saveReport(peak, fix)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                if (peak.triggered) missingCount.incrementAndGet()
                fail("Sensor evidence/log could not be saved; check app storage")
            } finally {
                runCatching { summaryFile(context, sessionId).writeText("$bumpCount,$withoutFrame") }
                    .onFailure { fail("Sensor summary could not be saved") }
            }
        }
    }

    private suspend fun saveReport(peak: NativeBumpDetector.Peak, eventFix: GpsFix?) = frameMutex.withLock {
        val items = frames.toList()
        val selected = NativeSensorEventPolicy.selectFrame(peak.elapsedMs, items.map { it.elapsedMs })
        val frame = selected?.let { db.driveKeyframeDao().getKeyframe(items[it].id) }
        if (frame == null) { missingCount.incrementAndGet(); return@withLock }
        val store = NativeInferenceEvidenceStore(context)
        val lease = NativeReportEvidenceStorage.reserveInferenceCapacity(context)
        var bitmap: android.graphics.Bitmap? = null
        var unowned: File? = null
        try {
            val image = BitmapFactory.decodeFile(frame.filePath)
                ?: throw IllegalStateException("Saved primary frame unavailable")
            bitmap = image
            withContext(NonCancellable) {
                val file = store.saveDetection(image, sessionId, frame.captureSeq, lease)
                unowned = file
                val thumb = store.thumbnailDataUrl(image) ?: error("Thumbnail unavailable")
                val lat = eventFix?.lat ?: frame.lat ?: error("Frame GPS missing")
                val lng = eventFix?.lng ?: frame.lng ?: error("Frame GPS missing")
                val eventWall = (wallAnchor + peak.elapsedMs - elapsedAnchor) / 1000
                val candidate = ReportEntity(
                    createdAt = eventWall, lat = lat, lng = lng,
                    photoPath = file.absolutePath, photoFullPath = file.absolutePath, photoDataUrl = thumb,
                    isReportable = 0, isPothole = 0, looksLikeSpeedBreaker = false,
                    damageType = "none", defectType = "not_pothole", assessment = "unverified",
                    imageQuality = null, onDrivableSurface = false, hasLocalizedCavity = false,
                    hasUnambiguousLowerInterior = false, hasBrokenEdgeOrRim = false,
                    hasDepthOrSurfaceLoss = false, temporalConsistency = null, size = null,
                    decision = "needs_review", status = "draft", detectionModel = "sensor-accelerometer-v1",
                    promptVersion = null, imageDetail = null, evidenceCount = 1,
                    description = "Unconfirmed bump. Peak vertical: ${peak.peakVertical} m/s²; speed: ${peak.speedMps} m/s. Review photo after driving.",
                    driveId = sessionId, captureSource = "drive_sensor", dedupeEligible = false,
                    capturedAt = frame.capturedAtMs / 1000, lastSeenAt = eventWall,
                    sourceEventKey = "sensor:$sessionId:${peak.elapsedMs}",
                    sourceEventKeysJson = JSONArray().put("sensor:$sessionId:${peak.elapsedMs}").toString(),
                    sightingDriveIdsJson = JSONArray().put(sessionId).toString(),
                    sourceOffsetS = frame.sourceOffsetMs / 1000.0,
                    gpsAccuracy = eventFix?.accuracy ?: frame.gpsAccuracy,
                    speedMps = peak.speedMps, heading = eventFix?.heading ?: frame.heading
                )
                val result = NativeMediaFilesystemMutation.mutex.withLock {
                    db.withTransaction {
                        val prior = db.reportDao().getReportsForDrive(sessionId).firstOrNull { r ->
                            r.lat != null && r.lng != null && NativeSensorEventPolicy.canMerge(
                                r.driveId == sessionId, r.captureSource == "drive_sensor",
                                NativeDeduplicationEngine.distMeters(lat, lng, r.lat, r.lng))
                        }
                        if (prior != null) {
                            // Preserve acknowledged evidence by donating the new complete photo when necessary.
                            val merged = NativeDuplicateReportOwnership.merge(prior, candidate,
                                candidate.sourceEventKeysJson, candidate.sightingDriveIdsJson, false)
                            db.reportDao().updateReport(merged.report.copy(description =
                                if (merged.candidateEvidenceAdopted) candidate.description else prior.description))
                            Triple(prior.id, true, merged.candidateEvidenceAdopted)
                        } else {
                            val id = db.reportDao().insertReport(candidate)
                            Triple(id, false, true)
                        }
                    }
                }
                if (result.third) unowned = null
                onReport(result.first, result.second)
            }
        } finally {
            bitmap?.recycle()
            NativeReportEvidenceStorage.releaseInferenceCapacity(lease)
            unowned?.let(NativeReportEvidenceStorage::deleteVerified)
        }
    }

    suspend fun cleanup() = frameMutex.withLock {
        // Report photos have separate quota/ownership; all sampling bursts can be released.
        cleanupFrames(context, db, sessionId, onDeletedBytes)
        frames.clear()
    }

    private suspend fun deleteFrame(id: Long) {
        val row = db.driveKeyframeDao().getKeyframe(id) ?: return
        deleteStoredFrame(db, row.id, File(row.filePath), onDeletedBytes)
    }

    companion object {
        private fun summaryFile(context: Context, sessionId: String) =
            File(logFile(context, sessionId).parentFile, "$sessionId.summary")

        fun summary(context: Context, sessionId: String): List<Int> = runCatching {
            val file = summaryFile(context, sessionId)
            if (file.length() > 128) return@runCatching emptyList<Int>()
            file.readText().split(',').map { it.toInt().coerceAtLeast(0) }.take(2)
        }.getOrDefault(emptyList())

        fun logFile(context: Context, sessionId: String): File {
            require(Regex("[A-Za-z0-9][A-Za-z0-9_-]{0,127}").matches(sessionId))
            return File(context.filesDir, "sensor_logs/$sessionId.csv")
        }

        suspend fun cleanupFrames(context: Context, db: PotholeDatabase, sessionId: String,
                                  onDeletedBytes: (Long) -> Unit = {}) {
            if (!logFile(context, sessionId).isFile) return
            while (true) {
                val batch = db.driveKeyframeDao().getForSession(sessionId, 64)
                if (batch.isEmpty()) break
                for (row in batch) deleteStoredFrame(db, row.id, File(row.filePath), onDeletedBytes)
            }
        }

        private suspend fun deleteStoredFrame(db: PotholeDatabase, id: Long, file: File,
                                             onDeletedBytes: (Long) -> Unit) {
            NativeMediaFilesystemMutation.mutex.withLock {
                val files = NativeKeyframeFiles.readSet(file).files
                var complete = true
                for (owned in files) {
                    val bytes = if (owned.isFile) owned.length() else 0L
                    if (NativeRetryableFileCleanup.deleteVerified(owned)) onDeletedBytes(bytes)
                    else complete = false
                }
                check(complete) { "Sensor frame cleanup failed" }
                db.driveKeyframeDao().deleteKeyframe(id)
                // Existing reconciliation inventories footprint before the next Drive reserves bytes.
                NativeMediaReconciliationEpoch.invalidate()
            }
        }
    }
}
