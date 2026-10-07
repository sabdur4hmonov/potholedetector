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
 */
class SensorDriveDetector(
    context: Context,
    private val fixAt: (Long) -> GpsFix?,
    private val isCapturing: () -> Boolean,
    private val debug: Boolean = false
) : DriveDetector {
    private val appContext = context.applicationContext
    private val evidenceStore = NativeInferenceEvidenceStore(appContext)
    private val pendingBumps = ConcurrentLinkedQueue<RoadBumpEvent>()
    private val ringLock = Any()
    private val ring = ArrayDeque<RingFrame>()
    @Volatile private var closed = false

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
        val sourceOffsetMs: Long
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
        // The complete frame, downscaled only. No crop, tile or road band.
        FrameQualityEvaluator.bitmapToBoundedJpegBytes(
            primary.bitmap,
            NativeStoredImagePolicy.MAX_BRIDGE_IMAGE_BYTES,
            NativeStoredImagePolicy.EVIDENCE_MAX_DIMENSION,
            88
        )?.let { jpeg ->
            remember(RingFrame(
                primary.capturedAtElapsedMs, primary.capturedAtMs, jpeg, lat, lng,
                gpsAccuracy, speedMps, heading, captureSeq, sourceOffsetMs
            ))
        }
        val (bump, frame) = nextMatchedBump() ?: return@withContext noShock()
        val report = createReport(bump, frame, driveId, onEvidenceSaved)
            ?: return@withContext noShock()
        InferenceOutcome(
            analyzed = true,
            accepted = true,
            decision = SENSOR_DECISION,
            assessment = null,
            reportEntity = report.first,
            sightings = listOf(report.second)
        )
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

    private suspend fun createReport(
        bump: RoadBumpEvent,
        frame: RingFrame,
        driveId: String,
        onEvidenceSaved: (String) -> Unit
    ): Pair<ReportEntity, EventSightingEntity>? {
        val lease = NativeReportEvidenceStorage.reserveInferenceCapacity(appContext)
        val photo = try {
            NativeReportEvidenceStorage.saveJpegAtomically(
                appContext,
                File(appContext.filesDir, "reports/" + safeComponent(driveId)),
                "sensor_${frame.captureSeq}_${System.currentTimeMillis()}.jpg",
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
        val hit = fixAt(bump.elapsedRealtimeMs)
        val lat = hit?.lat ?: frame.lat
        val lng = hit?.lng ?: frame.lng
        val accuracy = if (hit != null) hit.accuracy else frame.gpsAccuracy
        val heading = hit?.heading ?: frame.heading
        val hitWallMs = System.currentTimeMillis() -
            (SystemClock.elapsedRealtime() - bump.elapsedRealtimeMs).coerceAtLeast(0L)
        val sourceOffsetMs = frame.sourceOffsetMs + (bump.elapsedRealtimeMs - frame.elapsedMs)
        val sourceEventKey = "sensor:$driveId:${bump.elapsedRealtimeMs}"
        val kmh = (bump.speedMps * 3.6f).toInt()
        val description = String.format(
            Locale.US,
            "Road shock felt by the phone sensor (%.1f m/s², %d km/h). Not verified: it may be a pothole, a speed bump, a manhole or a rail crossing.",
            bump.peakToPeakMps2,
            kmh
        )
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
            damageType = SENSOR_DAMAGE_TYPE,
            surfaceType = "unknown",
            defectType = "unverified_road_shock",
            measurementProvenance = "accelerometer_peak_to_peak",
            measurementConfidence = "low",
            assessment = "sensor",
            imageQuality = "unknown",
            onDrivableSurface = true,
            hasLocalizedCavity = false,
            hasUnambiguousLowerInterior = false,
            hasBrokenEdgeOrRim = false,
            hasDepthOrSurfaceLoss = false,
            temporalConsistency = "not_applicable",
            size = null,
            decision = SENSOR_DECISION,
            description = description,
            emailSubject = null,
            emailBody = null,
            status = "draft",
            detectionModel = SENSOR_MODEL,
            imageDetail = null,
            promptVersion = SENSOR_CONTRACT_VERSION,
            schemaVersion = SENSOR_SCHEMA_VERSION,
            evidenceCount = 1,
            driveId = driveId,
            captureSource = SENSOR_CAPTURE_SOURCE,
            sourceEventKey = sourceEventKey,
            sourceEventKeysJson = JSONArray(listOf(sourceEventKey)).toString(),
            capturedAt = hitWallMs / 1000,
            sourceOffsetS = sourceOffsetMs.coerceAtLeast(0L) / 1000.0,
            gpsAccuracy = accuracy,
            speedMps = bump.speedMps,
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
            speedMps = bump.speedMps,
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
        const val MAX_PENDING_BUMPS = 8
        const val MAX_RING_FRAMES = 12
        const val RING_SPAN_MS = SensorEvidencePolicy.MAX_FRAME_AGE_MS + 1_000L
        private val UNSAFE_COMPONENT = Regex("[^A-Za-z0-9_-]")

        private fun safeComponent(value: String) = value.replace(UNSAFE_COMPONENT, "_").take(128)
    }
}
