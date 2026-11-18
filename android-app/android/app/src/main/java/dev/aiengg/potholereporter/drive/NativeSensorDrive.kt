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
    private val onDeletedBytes: (Long) -> Unit,
    private val inferenceMs: () -> Double = { 0.0 }
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
    private data class CameraHit(
        val frameId: Long, val at: Long, val lat: Double, val lng: Double, val version: String,
        val reportId: Long? = null
    )
    private val cameraHits = ArrayDeque<CameraHit>()
    private val recentBumps = ArrayDeque<Pair<NativeBumpDetector.Peak, GpsFix?>>()
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
        log.writeText("elapsedMs,wallclock,peak,speed,lat,lng,accuracy,triggered,inferenceMeanMs\n")
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
                        fix?.lat ?: "", fix?.lng ?: "", fix?.accuracy ?: "", if (peak.triggered) 1 else 0, inferenceMs())
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

    suspend fun cameraResult(id: Long, elapsedMs: Long, result: NativePotholeDetector.Result,
                             stillAllowed: () -> Boolean) = frameMutex.withLock {
        if (!result.yes || !stillAllowed()) return@withLock
        val frame = db.driveKeyframeDao().getKeyframe(id) ?: return@withLock
        val lat = frame.lat ?: return@withLock
        val lng = frame.lng ?: return@withLock
        val hit = CameraHit(id, elapsedMs, lat, lng, result.version)
        val bump = recentBumps.lastOrNull { (peak, fix) -> fix != null && NativePotholeFusion.matches(elapsedMs, peak.elapsedMs,
            NativeDeduplicationEngine.distMeters(lat, lng, fix.lat, fix.lng)) }
        val reportId = saveObservation(id, bump?.first, bump?.second, hit, stillAllowed) ?: return@withLock
        cameraHits.addLast(hit.copy(reportId = reportId))
        while (cameraHits.size > 16 || (cameraHits.firstOrNull()?.at ?: elapsedMs) < elapsedMs - 8_000) cameraHits.removeFirst()
    }

    private suspend fun saveReport(peak: NativeBumpDetector.Peak, eventFix: GpsFix?) = frameMutex.withLock {
        recentBumps.addLast(peak to eventFix)
        while (recentBumps.size > 16 || (recentBumps.firstOrNull()?.first?.elapsedMs ?: peak.elapsedMs) < peak.elapsedMs - 8_000) recentBumps.removeFirst()
        val camera = cameraHits.lastOrNull { hit -> frames.any { it.id == hit.frameId } && eventFix != null &&
            NativePotholeFusion.matches(hit.at, peak.elapsedMs,
                NativeDeduplicationEngine.distMeters(hit.lat, hit.lng, eventFix.lat, eventFix.lng)) }
        val items = frames.toList()
        val selected = NativeSensorEventPolicy.selectFrame(peak.elapsedMs, items.map { it.elapsedMs })
        val id = camera?.frameId ?: selected?.let { items[it].id }
        if (id == null) { missingCount.incrementAndGet(); return@withLock }
        saveObservation(id, peak, eventFix, camera)
    }

    private suspend fun saveObservation(id: Long, peak: NativeBumpDetector.Peak?, eventFix: GpsFix?,
                                        camera: CameraHit?, stillAllowed: () -> Boolean = { true }): Long? {
        val frame = db.driveKeyframeDao().getKeyframe(id) ?: return null
        val store = NativeInferenceEvidenceStore(context)
        val lease = NativeReportEvidenceStorage.reserveInferenceCapacity(context)
        var bitmap: android.graphics.Bitmap? = null
        var unowned: File? = null
        try {
            val image = BitmapFactory.decodeFile(frame.filePath)
                ?: throw IllegalStateException("Saved primary frame unavailable")
            bitmap = image
            return withContext(NonCancellable) {
                if (!stillAllowed()) return@withContext null
                val file = store.saveDetection(image, sessionId, frame.captureSeq, lease)
                unowned = file
                val thumb = store.thumbnailDataUrl(image) ?: error("Thumbnail unavailable")
                val lat = eventFix?.lat ?: frame.lat ?: error("Frame GPS missing")
                val lng = eventFix?.lng ?: frame.lng ?: error("Frame GPS missing")
                val eventElapsed = peak?.elapsedMs ?: camera!!.at
                val eventWall = (wallAnchor + eventElapsed - elapsedAnchor) / 1000
                val source = NativePotholeFusion.source(camera != null, peak != null)
                val candidate = ReportEntity(
                    createdAt = eventWall, lat = lat, lng = lng,
                    photoPath = file.absolutePath, photoFullPath = file.absolutePath, photoDataUrl = thumb,
                    isReportable = if (camera != null) 1 else 0, isPothole = if (camera != null) 1 else 0, looksLikeSpeedBreaker = false,
                    damageType = if (camera != null) "pothole_cavity" else "none", defectType = if (camera != null) "pothole" else "not_pothole", assessment = "unverified",
                    imageQuality = null, onDrivableSurface = false, hasLocalizedCavity = false,
                    hasUnambiguousLowerInterior = false, hasBrokenEdgeOrRim = false,
                    hasDepthOrSurfaceLoss = false, temporalConsistency = null, size = null,
                    decision = "needs_review", status = "draft", detectionModel = camera?.version ?: "sensor-accelerometer-v1",
                    promptVersion = null, imageDetail = null, evidenceCount = if (camera != null) 3 else 1,
                    description = if (camera != null) "Camera Yes in at least 2 of 3 complete views. ${if (peak != null) "Bump corroborated within 0.15–6 seconds and 40 m." else "No corroborating bump yet; review after driving."}"
                        else "Unconfirmed bump. Peak vertical: ${peak!!.peakVertical} m/s²; speed: ${peak.speedMps} m/s. Review photo after driving.",
                    driveId = sessionId, captureSource = source, dedupeEligible = false,
                    capturedAt = frame.capturedAtMs / 1000, lastSeenAt = eventWall,
                    sourceEventKey = "${if (camera != null) "camera" else "sensor"}:$sessionId:${camera?.at ?: eventElapsed}",
                    sourceEventKeysJson = JSONArray().put("${if (camera != null) "camera" else "sensor"}:$sessionId:${camera?.at ?: eventElapsed}").toString(),
                    sightingDriveIdsJson = JSONArray().put(sessionId).toString(),
                    sourceOffsetS = frame.sourceOffsetMs / 1000.0,
                    gpsAccuracy = eventFix?.accuracy ?: frame.gpsAccuracy,
                    speedMps = peak?.speedMps ?: frame.speedMps, heading = eventFix?.heading ?: frame.heading
                )
                val result = NativeMediaFilesystemMutation.mutex.withLock {
                    if (!stillAllowed()) return@withLock null
                    db.withTransaction {
                        val dao = db.reportDao()
                        val matchedCamera = camera?.reportId?.let { dao.getReportById(it) }
                            ?.takeIf { it.driveId == sessionId && NativePotholeFusion.offlineSource(it.captureSource) }
                        // A latitude band safely contains every point within 15 m.
                        val prior = matchedCamera ?: dao.getNearbyOfflineReports(sessionId, lat - .00015, lat + .00015)
                            .mapNotNull { report ->
                                val oldLat = report.lat ?: return@mapNotNull null
                                val oldLng = report.lng ?: return@mapNotNull null
                                val distance = NativeDeduplicationEngine.distMeters(lat, lng, oldLat, oldLng)
                                if (NativePotholeFusion.merge(report.driveId == sessionId, distance)) report to distance else null
                            }.minByOrNull { it.second }?.first
                        if (prior != null) {
                            // Preserve acknowledged evidence by donating the new complete photo when necessary.
                            val upgrade = camera != null && (prior.captureSource != "drive_camera_bump" || peak != null)
                            // Upgrade a bump's saved photo to the primary frame that supplied camera evidence.
                            val replacePhoto = upgrade && prior.captureSource == "drive_sensor"
                            val mergeBase = if (replacePhoto) prior.copy(photoPath = null, photoFullPath = null, photoDataUrl = null)
                                else prior
                            val merged = NativeDuplicateReportOwnership.merge(mergeBase, candidate,
                                candidate.sourceEventKeysJson, candidate.sightingDriveIdsJson, false)
                            db.reportDao().updateReport(merged.report.copy(
                                captureSource = if (upgrade) source else prior.captureSource,
                                detectionModel = if (upgrade) candidate.detectionModel else prior.detectionModel,
                                isPothole = if (upgrade) candidate.isPothole else prior.isPothole,
                                isReportable = if (upgrade) candidate.isReportable else prior.isReportable,
                                damageType = if (upgrade) candidate.damageType else prior.damageType,
                                defectType = if (upgrade) candidate.defectType else prior.defectType,
                                evidenceCount = maxOf(prior.evidenceCount, candidate.evidenceCount),
                                description = if (upgrade || merged.candidateEvidenceAdopted) candidate.description else prior.description))
                            if (replacePhoto || merged.priorEvidenceDisplaced) NativeMediaReconciliationEpoch.invalidate()
                            Triple(prior.id, true, merged.candidateEvidenceAdopted)
                        } else {
                            val id = db.reportDao().insertReport(candidate)
                            Triple(id, false, true)
                        }
                    }
                } ?: return@withContext null
                if (result.third) unowned = null
                onReport(result.first, result.second)
                result.first
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
