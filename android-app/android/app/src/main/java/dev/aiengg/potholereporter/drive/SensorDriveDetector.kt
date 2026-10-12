package dev.aiengg.potholereporter.drive

import android.content.Context
import android.graphics.BitmapFactory
import android.os.SystemClock
import dev.aiengg.potholereporter.db.EventSightingEntity
import dev.aiengg.potholereporter.db.RepairTargetEntity
import dev.aiengg.potholereporter.db.ReportEntity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File
import java.util.Locale
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * AI-free Drive detector. It never calls a network service. Each analysed burst only
 * keeps a JPEG of its complete primary frame in a short in-memory ring. When the
 * accelerometer feels a road shock ([onBump]), the next burst turns the frame captured
 * just before the wheel hit into a report marked as a sensor candidate that needs human
 * review. Repair verification needs a model, so it is never attempted here.
 *
 * When the build bundles an on-device camera model ([OnDevicePotholeModel]), every complete
 * frame of each burst is also scored on the phone. A shock report says whether the camera
 * model agreed; when the model accepts a burst and no shock was felt, the complete primary
 * frame becomes a separate "seen by the camera model" candidate, also unverified and left
 * for the owner to label. The model never suppresses a shock report.
 */
class SensorDriveDetector internal constructor(
    context: Context,
    private val fixAt: (Long) -> GpsFix?,
    private val isCapturing: () -> Boolean,
    private val debug: Boolean = false,
    private val model: OnDevicePotholeModel? = null
) : DriveDetector {
    private val appContext = context.applicationContext
    private val evidenceStore = NativeInferenceEvidenceStore(appContext)
    private val pendingBumps = ConcurrentLinkedQueue<RoadBumpEvent>()
    private val ringLock = Any()
    private val ring = ArrayDeque<RingFrame>()
    @Volatile private var closed = false
    private var lastModelReportElapsedMs = Long.MIN_VALUE
    private var lastModelReportLat: Double? = null
    private var lastModelReportLng: Double? = null

    private class RingFrame(
        val elapsedMs: Long,
        val wallMs: Long,
        val jpeg: ByteArray,
        val lat: Double?,
        val lng: Double?,
        val gpsAccuracy: Float?,
        val speedMps: Float?,
        val heading: Float?,
        val captureSeq: Int,
        val sourceOffsetMs: Long,
        val modelVerdict: OnDeviceBurstVerdict?
    )

    /** Called on the sensor thread; only queues. */
    internal fun onBump(event: RoadBumpEvent) {
        if (closed || !isCapturing()) return
        if (pendingBumps.size < MAX_PENDING_BUMPS) pendingBumps.add(event)
    }

    override suspend fun analyzeBurst(
        burstFrames: List<BurstFrame>,
        primaryIndex: Int,
        lat: Double?,
        lng: Double?,
        driveId: String,
        captureSeq: Int,
        capturedAtMs: Long,
        sourceOffsetMs: Long,
        gpsAccuracy: Float?,
        speedMps: Float?,
        heading: Float?,
        allowEarlyReject: Boolean,
        onEvidenceSaved: (String) -> Unit,
        onDiagnostic: ((DetectionDiagnosticEvent) -> Unit)?
    ): InferenceOutcome = withContext(Dispatchers.IO) {
        if (closed || burstFrames.isEmpty()) return@withContext noShock()
        val primary = burstFrames.getOrElse(primaryIndex) { burstFrames[0] }
        // Each burst frame is scored whole; the verdict travels with the remembered frame.
        val verdict = model?.let { m -> runCatching { m.decide(burstFrames.map { it.bitmap }) }.getOrNull() }
        // The complete frame, downscaled only. No crop, tile or road band.
        val current = FrameQualityEvaluator.bitmapToBoundedJpegBytes(
            primary.bitmap,
            NativeStoredImagePolicy.MAX_BRIDGE_IMAGE_BYTES,
            NativeStoredImagePolicy.EVIDENCE_MAX_DIMENSION,
            88
        )?.let { jpeg ->
            RingFrame(
                primary.capturedAtElapsedMs, primary.capturedAtMs, jpeg, lat, lng,
                gpsAccuracy, speedMps, heading, captureSeq, sourceOffsetMs, verdict
            ).also(::remember)
        }
        val matched = nextMatchedBump()
        if (matched != null) {
            val report = createReport(matched.first, matched.second, driveId, onEvidenceSaved)
                ?: return@withContext noShock()
            return@withContext InferenceOutcome(
                analyzed = true,
                accepted = true,
                decision = SENSOR_DECISION,
                assessment = null,
                reportEntity = report.first,
                sightings = listOf(report.second)
            )
        }
        // ONDEVICE-003: nothing was felt, but the camera model sees a pothole in this burst.
        if (current != null && verdict?.decision == OnDeviceBurstDecision.ACCEPT &&
            modelReportAllowed(current)
        ) {
            val report = createReport(null, current, driveId, onEvidenceSaved)
            if (report != null) {
                lastModelReportElapsedMs = current.elapsedMs
                lastModelReportLat = current.lat
                lastModelReportLng = current.lng
                return@withContext InferenceOutcome(
                    analyzed = true,
                    accepted = true,
                    decision = ONDEVICE_DECISION,
                    assessment = null,
                    reportEntity = report.first,
                    sightings = listOf(report.second)
                )
            }
        }
        noShock()
    }

    /** Moving, located, and far enough in time and space from the last camera-model report. */
    private fun modelReportAllowed(frame: RingFrame): Boolean {
        val lat = frame.lat ?: return false
        val lng = frame.lng ?: return false
        if ((frame.speedMps ?: 0f) < MODEL_MIN_SPEED_MPS) return false
        if (lastModelReportElapsedMs != Long.MIN_VALUE &&
            frame.elapsedMs - lastModelReportElapsedMs < MODEL_REPORT_MIN_GAP_MS
        ) return false
        val lastLat = lastModelReportLat
        val lastLng = lastModelReportLng
        if (lastLat != null && lastLng != null) {
            val dLat = (lat - lastLat) * 111_320.0
            val dLng = (lng - lastLng) * 111_320.0 * Math.cos(Math.toRadians(lat))
            if (Math.hypot(dLat, dLng) < MODEL_REPORT_MIN_SPACING_M) return false
        }
        return true
    }

    private fun remember(frame: RingFrame) = synchronized(ringLock) {
        ring.addLast(frame)
        ring.sortBy { it.elapsedMs }
        val newest = ring.last().elapsedMs
        while (ring.size > MAX_RING_FRAMES ||
            (ring.isNotEmpty() && newest - ring.first().elapsedMs > RING_SPAN_MS)
        ) ring.removeFirst()
    }

    private fun nextMatchedBump(): Pair<RoadBumpEvent, RingFrame>? {
        val now = SystemClock.elapsedRealtime()
        while (true) {
            val bump = pendingBumps.poll() ?: return null
            if (now - bump.elapsedRealtimeMs > SensorEvidencePolicy.MAX_PENDING_MS) continue
            val frame = synchronized(ringLock) {
                val frames = ring.toList()
                SensorEvidencePolicy.selectFrame(
                    frames.map { it.elapsedMs }, bump.elapsedRealtimeMs, bump.speedMps
                )?.let(frames::get)
            } ?: continue
            return bump to frame
        }
    }

    /** A shock report when [bump] is set, otherwise a camera-model report for [frame]. */
    private suspend fun createReport(
        bump: RoadBumpEvent?,
        frame: RingFrame,
        driveId: String,
        onEvidenceSaved: (String) -> Unit
    ): Pair<ReportEntity, EventSightingEntity>? {
        val lease = NativeReportEvidenceStorage.reserveInferenceCapacity(appContext)
        val photo = try {
            NativeReportEvidenceStorage.saveJpegAtomically(
                appContext,
                File(appContext.filesDir, "reports/" + safeComponent(driveId)),
                (if (bump != null) "sensor_" else "ondevice_") + "${frame.captureSeq}_${System.currentTimeMillis()}.jpg",
                frame.jpeg,
                lease
            )
        } finally {
            NativeReportEvidenceStorage.releaseInferenceCapacity(lease)
        }
        publishEvidence(photo, onEvidenceSaved)
        val thumbnail = BitmapFactory.decodeByteArray(frame.jpeg, 0, frame.jpeg.size)?.let { bitmap ->
            try {
                evidenceStore.thumbnailDataUrl(bitmap)
            } finally {
                bitmap.recycle()
            }
        }?.takeIf(String::isNotBlank) ?: return null

        // The wheel hit the shock where the car was at the bump, not where the frame was taken.
        // A camera-model report is placed where the frame was taken.
        val hit = bump?.let { fixAt(it.elapsedRealtimeMs) }
        val lat = hit?.lat ?: frame.lat
        val lng = hit?.lng ?: frame.lng
        val accuracy = if (hit != null) hit.accuracy else frame.gpsAccuracy
        val heading = hit?.heading ?: frame.heading
        val eventElapsedMs = bump?.elapsedRealtimeMs ?: frame.elapsedMs
        val hitWallMs = System.currentTimeMillis() -
            (SystemClock.elapsedRealtime() - eventElapsedMs).coerceAtLeast(0L)
        val sourceOffsetMs = frame.sourceOffsetMs + (eventElapsedMs - frame.elapsedMs)
        val sourceEventKey = (if (bump != null) "sensor" else "ondevice") + ":$driveId:$eventElapsedMs"
        val speedMps = bump?.speedMps ?: frame.speedMps
        val description = if (bump != null) String.format(
            Locale.US,
            "Road shock felt by the phone sensor (%.1f m/s², %d km/h). Not verified: it may be a pothole, a speed bump, a manhole or a rail crossing.",
            bump.peakToPeakMps2,
            (bump.speedMps * 3.6f).toInt()
        ) + OnDeviceDetectorContract.reviewNote(frame.modelVerdict, model?.spec)
        else OnDeviceDetectorContract.cameraOnlyNote(frame.modelVerdict, model?.spec)
        val report = ReportEntity(
            createdAt = System.currentTimeMillis() / 1000,
            lat = lat,
            lng = lng,
            address = "Road coordinates (" +
                "${lat?.let { "%.5f".format(Locale.US, it) }}, " +
                "${lng?.let { "%.5f".format(Locale.US, it) }})",
            photoPath = photo.absolutePath,
            photoDataUrl = thumbnail,
            photoFullPath = photo.absolutePath,
            isReportable = 0,
            isPothole = 0,
            looksLikeSpeedBreaker = false,
            damageType = if (bump != null) SENSOR_DAMAGE_TYPE else ONDEVICE_DAMAGE_TYPE,
            surfaceType = "unknown",
            defectType = if (bump != null) "unverified_road_shock" else "unverified_camera_model",
            measurementProvenance = if (bump != null) "accelerometer_peak_to_peak" else "ondevice_model_score",
            measurementConfidence = "low",
            assessment = if (bump != null) "sensor" else "ondevice",
            imageQuality = "unknown",
            onDrivableSurface = true,
            hasLocalizedCavity = false,
            hasUnambiguousLowerInterior = false,
            hasBrokenEdgeOrRim = false,
            hasDepthOrSurfaceLoss = false,
            temporalConsistency = "not_applicable",
            size = null,
            decision = if (bump != null) SENSOR_DECISION else ONDEVICE_DECISION,
            description = description,
            emailSubject = null,
            emailBody = null,
            status = "draft",
            detectionModel = if (bump != null) SENSOR_MODEL else ONDEVICE_MODEL,
            imageDetail = null,
            promptVersion = if (bump != null) SENSOR_CONTRACT_VERSION else ONDEVICE_CONTRACT_VERSION,
            schemaVersion = SENSOR_SCHEMA_VERSION,
            evidenceCount = 1,
            driveId = driveId,
            captureSource = if (bump != null) SENSOR_CAPTURE_SOURCE else ONDEVICE_CAPTURE_SOURCE,
            sourceEventKey = sourceEventKey,
            sourceEventKeysJson = JSONArray(listOf(sourceEventKey)).toString(),
            capturedAt = hitWallMs / 1000,
            sourceOffsetS = sourceOffsetMs.coerceAtLeast(0L) / 1000.0,
            gpsAccuracy = accuracy,
            speedMps = speedMps,
            heading = heading,
            primaryFrameIndex = 0,
            debugCapture = debug,
            dedupeEligible = !debug,
            sightingDriveIdsJson = JSONArray(listOf(driveId)).toString(),
            seenCount = 1,
            lastSeenAt = hitWallMs / 1000,
            syncedToWeb = false
        )
        val sighting = EventSightingEntity(
            reportId = 0,
            driveId = driveId,
            lat = lat,
            lng = lng,
            sourceOffsetS = sourceOffsetMs.coerceAtLeast(0L) / 1000.0,
            capturedAt = hitWallMs / 1000,
            gpsAccuracy = accuracy,
            speedMps = speedMps,
            heading = heading,
            sourceEventKey = sourceEventKey
        )
        return report to sighting
    }

    private fun noShock() = InferenceOutcome(
        analyzed = true,
        accepted = false,
        decision = "no_shock",
        assessment = null
    )

    override suspend fun verifyRepair(
        target: RepairTargetEntity,
        burstFrames: List<BurstFrame>,
        primaryIndex: Int,
        driveId: String,
        captureSeq: Int,
        onEvidenceSaved: (String) -> Unit
    ): RepairVerificationResult? = null

    override fun close() {
        closed = true
        model?.close()
        pendingBumps.clear()
        synchronized(ringLock) { ring.clear() }
    }

    companion object {
        const val SENSOR_CAPTURE_SOURCE = "drive_sensor"
        const val SENSOR_DAMAGE_TYPE = "road_shock"
        const val SENSOR_DECISION = "sensor_candidate"
        const val SENSOR_MODEL = "phone_accelerometer"
        const val SENSOR_CONTRACT_VERSION = "sensor-shock-v1"
        const val SENSOR_SCHEMA_VERSION = 1
        const val ONDEVICE_CAPTURE_SOURCE = "drive_ondevice"
        const val ONDEVICE_DAMAGE_TYPE = "pothole_candidate"
        const val ONDEVICE_DECISION = "ondevice_candidate"
        const val ONDEVICE_MODEL = "ondevice_pothole_v1"
        const val ONDEVICE_CONTRACT_VERSION = "ondevice-pothole-v1"
        /** About 14 km/h, like the shock detector: a parked car never reports. */
        const val MODEL_MIN_SPEED_MPS = 4f
        const val MODEL_REPORT_MIN_GAP_MS = 3_000L
        const val MODEL_REPORT_MIN_SPACING_M = 25.0
        const val MAX_PENDING_BUMPS = 8
        const val MAX_RING_FRAMES = 12
        const val RING_SPAN_MS = SensorEvidencePolicy.MAX_FRAME_AGE_MS + 1_000L
        private val UNSAFE_COMPONENT = Regex("[^A-Za-z0-9_-]")

        private fun safeComponent(value: String) = value.replace(UNSAFE_COMPONENT, "_").take(128)
    }
}
