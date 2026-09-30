package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.EventSightingEntity
import dev.aiengg.potholereporter.db.ReportEntity
import dev.aiengg.potholereporter.db.PotholeDatabase
import androidx.room.withTransaction
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import kotlin.math.*

data class DedupeResult(
    val isDuplicate: Boolean,
    val existingReportId: Long?,
    val matchKind: String? = null,
    /** True when the canonical row took ownership of this candidate's evidence file. */
    val candidateEvidenceAdopted: Boolean = false
)

internal data class NativeDuplicateReportMergeResult(
    val report: ReportEntity,
    val candidateEvidenceAdopted: Boolean,
    /** A previously referenced file is now orphaned and must be found by reconciliation. */
    val priorEvidenceDisplaced: Boolean
)

internal fun requireCompleteNativeReportEvidence(candidate: ReportEntity) {
    // Production candidates receive this reference only from the private managed evidence
    // store. Do not accept the legacy thumbnail/path fallback as a new native candidate.
    val managedFullPath = candidate.photoFullPath?.takeIf(String::isNotBlank)
    require(managedFullPath != null && !candidate.photoDataUrl.isNullOrBlank()) {
        "Native report candidates require a managed full image and thumbnail"
    }
}

/**
 * Merges a later sighting into its canonical report without losing bridgeable evidence.
 *
 * Acknowledgement deliberately scrubs the first native photo after the WebView commits it.
 * The next accepted revisit therefore donates its fresh full image and thumbnail. The
 * engine rejects incomplete candidates before this merge can mutate the canonical row.
 */
internal object NativeDuplicateReportOwnership {
    fun merge(
        prior: ReportEntity,
        candidate: ReportEntity,
        sourceEventKeysJson: String,
        sightingDriveIdsJson: String,
        exactReplay: Boolean
    ): NativeDuplicateReportMergeResult {
        requireCompleteNativeReportEvidence(candidate)
        val priorHasFullImage =
            !prior.photoFullPath.isNullOrBlank() || !prior.photoPath.isNullOrBlank()
        val priorHasThumbnail = !prior.photoDataUrl.isNullOrBlank()
        val priorEvidenceIncomplete = !priorHasFullImage || !priorHasThumbnail
        val candidateFullPath = candidate.photoFullPath?.takeIf(String::isNotBlank)
            ?: candidate.photoPath?.takeIf(String::isNotBlank)
        val candidateThumbnail = candidate.photoDataUrl?.takeIf(String::isNotBlank)
        val adoptCandidateEvidence =
            priorEvidenceIncomplete && candidateFullPath != null && candidateThumbnail != null

        return NativeDuplicateReportMergeResult(
            report = prior.copy(
                photoPath = if (adoptCandidateEvidence) {
                    candidate.photoPath?.takeIf(String::isNotBlank) ?: candidateFullPath
                } else {
                    prior.photoPath
                },
                photoFullPath = if (adoptCandidateEvidence) {
                    candidate.photoFullPath?.takeIf(String::isNotBlank) ?: candidateFullPath
                } else {
                    prior.photoFullPath
                },
                photoDataUrl = if (adoptCandidateEvidence) candidateThumbnail else prior.photoDataUrl,
                // The managed photo and these fields form one provenance unit. Keeping the
                // canonical row's old keyframe identity after adopting a revisit photo makes
                // evidence recovery reopen the wrong burst (or permanently lose the report).
                driveId = if (adoptCandidateEvidence) candidate.driveId else prior.driveId,
                captureSource = if (adoptCandidateEvidence) {
                    candidate.captureSource
                } else {
                    prior.captureSource
                },
                sourceEventKey = if (adoptCandidateEvidence) {
                    candidate.sourceEventKey
                } else {
                    prior.sourceEventKey
                },
                capturedAt = if (adoptCandidateEvidence) candidate.capturedAt else prior.capturedAt,
                sourceOffsetS = if (adoptCandidateEvidence) {
                    candidate.sourceOffsetS
                } else {
                    prior.sourceOffsetS
                },
                gpsAccuracy = if (adoptCandidateEvidence) candidate.gpsAccuracy else prior.gpsAccuracy,
                speedMps = if (adoptCandidateEvidence) candidate.speedMps else prior.speedMps,
                heading = if (adoptCandidateEvidence) candidate.heading else prior.heading,
                primaryFrameIndex = if (adoptCandidateEvidence) {
                    candidate.primaryFrameIndex
                } else {
                    prior.primaryFrameIndex
                },
                sourceEventKeysJson = sourceEventKeysJson,
                sightingDriveIdsJson = sightingDriveIdsJson,
                seenCount = if (exactReplay) prior.seenCount else prior.seenCount + 1,
                lastSeenAt = max(prior.lastSeenAt ?: 0L, candidate.capturedAt ?: 0L),
                syncedToWeb = false
            ),
            candidateEvidenceAdopted = adoptCandidateEvidence,
            priorEvidenceDisplaced = adoptCandidateEvidence && priorHasFullImage
        )
    }
}

class NativeDeduplicationEngine(
    private val database: PotholeDatabase
) {
    private val reportDao = database.reportDao()
    private val sightingDao = database.eventSightingDao()
    companion object {
        const val DEDUPE_ADJACENT_RADIUS_M = 12.0
        const val DEDUPE_HISTORY_RADIUS_M = 8.0
        const val DEDUPE_MISSING_HEADING_RADIUS_M = 5.0
        const val DEDUPE_SAME_DRIVE_S = 4.0
        const val DEDUPE_POOR_GPS_S = 2.0
        const val DEDUPE_HISTORY_S = 30L * 24 * 3600

        fun distMeters(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
            val r = 6371000.0
            val dLat = Math.toRadians(lat2 - lat1)
            val dLon = Math.toRadians(lon2 - lon1)
            val a = sin(dLat / 2).pow(2.0) +
                    cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) *
                    sin(dLon / 2).pow(2.0)
            val c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
            return r * c
        }

        fun headingDifference(a: Float, b: Float): Float {
            val diff = abs(((a - b + 180f) % 360f + 360f) % 360f - 180f)
            return diff
        }
    }

    suspend fun checkAndCommitReport(
        candidate: ReportEntity,
        sightings: List<EventSightingEntity>
    ): DedupeResult {
        // Reject before taking the media/Room mutation boundary. A partial candidate can
        // neither become a new canonical row nor turn an acknowledged canonical into an
        // unsyncable all-null outbox row.
        requireCompleteNativeReportEvidence(candidate)
        return NativeMediaFilesystemMutation.mutex.withLock {
            // Acknowledgement clears media columns after bridging. Hold the same process-wide
            // lock for the read/merge transaction so a stale full-row @Update can never put
            // an acknowledged path back into Room after its file has been deleted.
            database.withTransaction {
            if (!candidate.dedupeEligible || candidate.debugCapture) {
                val newId = reportDao.insertReport(candidate)
                val mappedSightings = sightings.map { it.copy(reportId = newId) }
                sightingDao.insertSightings(mappedSightings)
                return@withTransaction DedupeResult(isDuplicate = false, existingReportId = newId)
            }

            val candLat = candidate.lat
            val candLng = candidate.lng
            val candidates = mutableListOf<ReportEntity>()

            if (candLat != null && candLng != null) {
                val latitudeBand = DEDUPE_HISTORY_RADIUS_M / 110900.0
                candidates.addAll(reportDao.getCandidateReportsInLatitudeBand(candLat - latitudeBand, candLat + latitudeBand))
            }

            val driveId = candidate.driveId
            if (driveId != null) {
                val driveReports = reportDao.getReportsForDrive(driveId)
                for (dr in driveReports) {
                    if (candidates.none { it.id == dr.id }) {
                        candidates.add(dr)
                    }
                }
            }

            for (prior in candidates) {
                val match = matchRoadEvent(candidate, prior)
                if (match != null) {
                    val priorSightings = sightingDao.getSightingsForReport(prior.id).toMutableList()
                    val currentDrive = candidate.driveId
                    val observedAt = candidate.capturedAt ?: (System.currentTimeMillis() / 1000)
                    val cutoff = observedAt - DEDUPE_HISTORY_S

                    val filteredSightings = priorSightings.filter { s ->
                        val seenAt = s.capturedAt
                        (s.driveId != null && s.driveId == currentDrive) || seenAt == null || seenAt >= cutoff
                    }.toMutableList()

                    val sameDriveCount = if (currentDrive == null) 0 else filteredSightings.count { it.driveId == currentDrive }
                    val exactReplay = match == "same_source"

                    if ((match == "same_drive" || match == "prior_drive") && !exactReplay && (currentDrive == null || sameDriveCount < 64)) {
                        filteredSightings.add(
                            EventSightingEntity(
                                reportId = prior.id,
                                driveId = candidate.driveId,
                                lat = candidate.lat,
                                lng = candidate.lng,
                                sourceOffsetS = candidate.sourceOffsetS,
                                capturedAt = candidate.capturedAt,
                                gpsAccuracy = candidate.gpsAccuracy,
                                speedMps = candidate.speedMps,
                                heading = candidate.heading,
                                sourceEventKey = candidate.sourceEventKey
                            )
                        )
                    }

                    val sightingDrives = filteredSightings.mapNotNull { it.driveId }.distinct()
                    val keys = parseJsonArray(prior.sourceEventKeysJson)
                    if (candidate.sourceEventKey != null && !keys.contains(candidate.sourceEventKey)) {
                        keys.add(candidate.sourceEventKey)
                    }

                    val merged = NativeDuplicateReportOwnership.merge(
                        prior = prior,
                        candidate = candidate,
                        sourceEventKeysJson = JSONArray(keys.takeLast(64)).toString(),
                        sightingDriveIdsJson = JSONArray(sightingDrives).toString(),
                        exactReplay = exactReplay
                    )

                    reportDao.updateReport(merged.report)
                    if (merged.priorEvidenceDisplaced) {
                        // The old managed path is intentionally not deleted here. Once this
                        // transaction commits it is an orphan; reconciliation, under this same
                        // mutex, will retain the newly adopted path and retry only true orphans.
                        NativeMediaReconciliationEpoch.invalidate()
                    }
                    sightingDao.deleteSightingsForReport(prior.id)
                    sightingDao.insertSightings(filteredSightings)

                    return@withTransaction DedupeResult(
                        isDuplicate = true,
                        existingReportId = prior.id,
                        matchKind = match,
                        candidateEvidenceAdopted = merged.candidateEvidenceAdopted
                    )
                }
            }

            // No match found -> Insert as new canonical report
            val newId = reportDao.insertReport(candidate)
            val mappedSightings = sightings.map { it.copy(reportId = newId) }
            sightingDao.insertSightings(mappedSightings)

            DedupeResult(isDuplicate = false, existingReportId = newId)
            }
        }
    }

    private suspend fun matchRoadEvent(candidate: ReportEntity, prior: ReportEntity): String? =
        NativeRoadEventMatcher.match(
            candidate, prior, sightingDao.getSightingsForReport(prior.id),
            parseJsonArray(prior.sourceEventKeysJson)
        )

    private fun parseJsonArray(json: String?): MutableList<String> {
        val list = mutableListOf<String>()
        if (json.isNullOrBlank()) return list
        try {
            val array = JSONArray(json)
            for (i in 0 until array.length()) {
                list.add(array.getString(i))
            }
        } catch (_: Exception) {}
        return list
    }
}
