package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.RepairTargetEntity

/**
 * What Drive mode asks of a detector for each complete, durably saved burst. The cloud
 * engine ([NativeInferenceEngine]) needs an API key; [SensorDriveDetector] needs none and
 * uses only the phone's accelerometer plus the complete camera frames.
 */
interface DriveDetector {
    suspend fun analyzeBurst(
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
        onDiagnostic: ((DetectionDiagnosticEvent) -> Unit)? = null
    ): InferenceOutcome

    /** Null when this detector cannot verify a repair. */
    suspend fun verifyRepair(
        target: RepairTargetEntity,
        burstFrames: List<BurstFrame>,
        primaryIndex: Int,
        driveId: String,
        captureSeq: Int,
        onEvidenceSaved: (String) -> Unit
    ): RepairVerificationResult?

    fun close()
}

/** Wire values for the Drive detection mode passed from the web layer. */
object DriveDetectionMode {
    const val CLOUD = "cloud"
    const val SENSOR = "sensor"

    /** Without a key the only possible mode is the AI-free sensor mode. */
    fun resolve(requested: String?, hasApiKey: Boolean): String =
        if (!hasApiKey || requested == SENSOR) SENSOR else CLOUD
}
