package dev.aiengg.potholereporter.drive

import dev.aiengg.potholereporter.db.ReportEntity
import org.json.JSONArray

/** Explicit caller policy; the product has not selected freshness cutoffs. */
internal data class HazardFreshnessWindow(
    val freshThroughSeconds: Long,
    val staleAfterSeconds: Long
) {
    init {
        require(freshThroughSeconds >= 0 && staleAfterSeconds > freshThroughSeconds)
    }
}

internal enum class HazardConfidence(val rank: Int) {
    UNKNOWN(0), SINGLE_OBSERVATION(1), INDEPENDENT_REOBSERVATION(2)
}

internal enum class HazardFreshness(val rank: Int) {
    UNKNOWN(0), STALE(0), AGING(1), FRESH(2)
}

internal enum class HazardSeverity(val rank: Int) {
    UNKNOWN(0), SMALL(1), MEDIUM(2), LARGE(3)
}

internal data class HazardScore(
    val confidence: HazardConfidence,
    val freshness: HazardFreshness,
    val severity: HazardSeverity,
    val independentDriveCount: Int,
    val isFixed: Boolean?
)

internal data class HazardEvidence(
    val confidence: HazardConfidence,
    val severity: HazardSeverity,
    val independentDriveCount: Int,
    val isFixed: Boolean?,
    val policyVersion: String = "hazard-evidence-v1"
)

/** Derived snapshot only. It never changes matching, repair state, or persisted reports. */
internal object NativeHazardScoringPolicy {
    fun evidence(
        report: ReportEntity,
        conditionStatus: String? = null
    ): HazardEvidence {
        val accepted = report.decision == "accept" && report.isPothole == 1 &&
            report.isReportable == 1 && !report.debugCapture
        val driveIds = buildList {
            report.driveId?.takeIf(String::isNotBlank)?.let(::add)
            try {
                val stored = JSONArray(report.sightingDriveIdsJson)
                for (index in 0 until stored.length()) {
                    (stored.get(index) as? String)?.takeIf(String::isNotBlank)?.let(::add)
                }
            } catch (_: Exception) {
                // A malformed legacy list is not evidence of another independent drive.
            }
        }.distinct()
        val confidence = when {
            !accepted -> HazardConfidence.UNKNOWN
            driveIds.size >= 2 -> HazardConfidence.INDEPENDENT_REOBSERVATION
            else -> HazardConfidence.SINGLE_OBSERVATION
        }
        val severity = if (!accepted) HazardSeverity.UNKNOWN else when (report.size) {
            "small" -> HazardSeverity.SMALL
            "medium" -> HazardSeverity.MEDIUM
            "large" -> HazardSeverity.LARGE
            else -> HazardSeverity.UNKNOWN
        }
        val isFixed = when (conditionStatus) {
            "fixed" -> true
            "open", "repair_review" -> false
            else -> null
        }
        return HazardEvidence(confidence, severity, driveIds.size, isFixed)
    }

    fun score(
        report: ReportEntity,
        referenceAtSeconds: Long,
        window: HazardFreshnessWindow,
        conditionStatus: String? = null
    ): HazardScore {
        require(referenceAtSeconds >= 0)
        val evidence = evidence(report, conditionStatus)
        val observedAt = report.lastSeenAt
        val freshness = when {
            evidence.confidence == HazardConfidence.UNKNOWN || observedAt == null ||
                observedAt <= 0 || observedAt > referenceAtSeconds -> HazardFreshness.UNKNOWN
            referenceAtSeconds - observedAt <= window.freshThroughSeconds -> HazardFreshness.FRESH
            referenceAtSeconds - observedAt <= window.staleAfterSeconds -> HazardFreshness.AGING
            else -> HazardFreshness.STALE
        }
        return HazardScore(evidence.confidence, freshness, evidence.severity,
            evidence.independentDriveCount, evidence.isFixed)
    }
}
