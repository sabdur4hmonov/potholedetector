/* Pure report-derived scoring foundation. No clock, storage, DOM, or network access. */
(function (root) {
  "use strict";

  // CONF-001 consumes the existing categories without choosing a freshness policy.
  function deriveHazardEvidence(report) {
    const row = report || {};
    const accepted = row.decision === "accept" && row.is_pothole === 1
      && row.is_reportable === 1 && row.debug_capture !== true;
    const drives = new Set();
    const addDrive = (id) => {
      if (typeof id === "string" && id.trim()) drives.add(id);
    };
    addDrive(row.drive_id);
    if (Array.isArray(row.sighting_drive_ids)) row.sighting_drive_ids.forEach(addDrive);
    const confidence = !accepted ? "unknown" : drives.size >= 2
      ? "independent_reobservation" : "single_observation";
    const severity = accepted && ["small", "medium", "large"].includes(row.size)
      ? row.size : "unknown";
    return Object.freeze({
      policy_version: "hazard-evidence-v1",
      confidence, confidence_rank: confidence === "independent_reobservation" ? 2
        : confidence === "single_observation" ? 1 : 0,
      severity, severity_rank: { unknown: 0, small: 1, medium: 2, large: 3 }[severity],
      independent_drive_count: drives.size,
      is_fixed: row.condition_status === "fixed" ? true
        : ["open", "repair_review"].includes(row.condition_status) ? false : null,
    });
  }

  function scoreHazardReport(report, referenceAtSeconds, window) {
    if (!Number.isFinite(referenceAtSeconds) || referenceAtSeconds < 0
        || !window || !Number.isSafeInteger(window.freshThroughSeconds)
        || !Number.isSafeInteger(window.staleAfterSeconds)
        || window.freshThroughSeconds < 0
        || window.staleAfterSeconds <= window.freshThroughSeconds) {
      throw new RangeError("A reference time and explicit freshness window are required");
    }
    const row = report || {};
    const accepted = row.decision === "accept" && row.is_pothole === 1
      && row.is_reportable === 1 && row.debug_capture !== true;
    const evidence = deriveHazardEvidence(row);

    const observedAt = row.last_seen_at;
    let freshness = "unknown";
    if (accepted && Number.isFinite(observedAt) && observedAt > 0
        && observedAt <= referenceAtSeconds) {
      const age = referenceAtSeconds - observedAt;
      freshness = age <= window.freshThroughSeconds ? "fresh"
        : age <= window.staleAfterSeconds ? "aging" : "stale";
    }
    const freshnessRank = freshness === "fresh" ? 2 : freshness === "aging" ? 1 : 0;
    return Object.freeze({
      confidence: evidence.confidence, confidence_rank: evidence.confidence_rank,
      freshness, freshness_rank: freshnessRank,
      severity: evidence.severity, severity_rank: evidence.severity_rank,
      independent_drive_count: evidence.independent_drive_count,
      is_fixed: evidence.is_fixed,
    });
  }

  const api = Object.freeze({ scoreHazardReport, deriveHazardEvidence });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.HazardModel = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
