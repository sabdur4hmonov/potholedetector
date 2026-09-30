package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.EventSightingEntity
import dev.aiengg.potholereporter.db.ReportEntity
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_ADJACENT_RADIUS_M
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_HISTORY_RADIUS_M
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_HISTORY_S
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_MISSING_HEADING_RADIUS_M
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_POOR_GPS_S
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.DEDUPE_SAME_DRIVE_S
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.distMeters
import dev.aiengg.potholereporter.drive.NativeDeduplicationEngine.Companion.headingDifference
import kotlin.math.abs
import kotlin.math.min

/** Pure match decision; the engine retains DAO reads, canonical merge and transaction ownership. */
internal object NativeRoadEventMatcher {
    fun match(
        candidate: ReportEntity,
        prior: ReportEntity,
        priorSightings: List<EventSightingEntity>,
        priorKeys: List<String>
    ): String? {
        if (!candidate.dedupeEligible || prior.debugCapture || !prior.dedupeEligible) return null
        if (candidate.status == "draft" && prior.status == "unrouted") return null

        if (candidate.sourceEventKey != null &&
            (prior.sourceEventKey == candidate.sourceEventKey || priorKeys.contains(candidate.sourceEventKey))
        ) return "same_source"

        if (candidate.captureSource == "manual") return null
        if (!areDamageTypesCompatible(candidate.damageType, prior.damageType)) return null
        if (sizeConflict(candidate.size, prior.size)) return null

        val candLat = candidate.lat
        val candLng = candidate.lng
        val priorLat = prior.lat
        val priorLng = prior.lng
        val positioned = candLat != null && candLng != null && priorLat != null && priorLng != null
        val distance = if (positioned) distMeters(candLat!!, candLng!!, priorLat!!, priorLng!!)
            else Double.POSITIVE_INFINITY

        val candidateDrive = candidate.driveId
        if (candidateDrive != null) {
            val sameDriveSightings = priorSightings.filter { it.driveId == candidateDrive }
            if (sameDriveSightings.isNotEmpty()) {
                val matchesAll = sameDriveSightings.all { s ->
                    val seconds = min(
                        finiteDelta(candidate.sourceOffsetS, s.sourceOffsetS),
                        finiteDelta(candidate.capturedAt?.toDouble(), s.capturedAt?.toDouble())
                    )
                    if (!seconds.isFinite()) return@all false
                    val sLat = s.lat
                    val sLng = s.lng
                    val positionedSighting = sLat != null && sLng != null && candLat != null && candLng != null
                    val poorGps = candidate.gpsAccuracy == null || s.gpsAccuracy == null ||
                        candidate.gpsAccuracy > 30f || s.gpsAccuracy > 30f
                    if (!positionedSighting || poorGps) return@all seconds <= DEDUPE_POOR_GPS_S

                    val sightingDistance = distMeters(candLat!!, candLng!!, sLat!!, sLng!!)
                    val stationary = candidate.speedMps != null && s.speedMps != null &&
                        candidate.speedMps <= 1f && s.speedMps <= 1f
                    if (stationary) seconds <= 30.0 && sightingDistance <= 5.0
                    else seconds <= DEDUPE_SAME_DRIVE_S && sightingDistance <= DEDUPE_ADJACENT_RADIUS_M
                }
                return if (matchesAll) "same_drive" else null
            }
        }

        val candAcc = candidate.gpsAccuracy
        val priorAcc = prior.gpsAccuracy
        if (!positioned || candAcc == null || priorAcc == null || candAcc > 15f || priorAcc > 15f) return null

        val candTime = candidate.lastSeenAt ?: candidate.capturedAt ?: candidate.createdAt
        val priorTime = prior.lastSeenAt ?: prior.capturedAt ?: prior.createdAt
        if (abs(candTime - priorTime) > DEDUPE_HISTORY_S) return null

        val left = candidate.damageType ?: "none"
        val right = prior.damageType ?: "none"
        if (left == "other_road_damage" || right == "other_road_damage") return null

        var radius = if (left == right) DEDUPE_HISTORY_RADIUS_M else 5.0
        val candSpeed = candidate.speedMps
        val priorSpeed = prior.speedMps
        val moving = candSpeed != null && priorSpeed != null && candSpeed >= 2f && priorSpeed >= 2f
        val candHeading = candidate.heading
        val priorHeading = prior.heading
        if (moving && candHeading != null && priorHeading != null) {
            if (headingDifference(candHeading, priorHeading) > 45f) return null
        } else {
            radius = min(radius, DEDUPE_MISSING_HEADING_RADIUS_M)
        }
        return if (distance <= radius) "prior_drive" else null
    }

    private fun areDamageTypesCompatible(left: String?, right: String?): Boolean {
        if (left == null || right == null) return false
        if (left == right) return true
        val localDamageFamily = setOf("pothole_cavity", "failed_patch")
        return localDamageFamily.contains(left) && localDamageFamily.contains(right)
    }

    private fun sizeConflict(left: String?, right: String?): Boolean =
        (left == "small" && right == "large") || (left == "large" && right == "small")

    private fun finiteDelta(left: Double?, right: Double?): Double =
        if (left != null && right != null && left.isFinite() && right.isFinite()) abs(left - right)
        else Double.POSITIVE_INFINITY
}
