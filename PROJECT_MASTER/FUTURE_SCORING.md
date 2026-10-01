# FUTURE-SCORING-001: hazard scoring foundation

## 2026-10-01 CONF-001 consumer

CONF-001 now exposes the existing confidence/severity dimensions as `hazard-evidence-v1` and displays explained observation support and visual severity in report detail. The original score outputs and 18 shared vectors are unchanged. See [CONFIDENCE_SEVERITY.md](CONFIDENCE_SEVERITY.md). This consumes no freshness policy and adds no warning/map/road-health scoring. Statements below about no production consumer describe the original foundation checkpoint.

This task adds a deterministic, report-derived scoring snapshot for native and web consumers. It does not change report matching, storage, warnings, map display, or repair workflow. The shared cases live in `android-app/android/app/src/test/resources/hazard-scoring-v1.json`; `NativeHazardScoringPolicyTest` and `tests/hazard_scoring_parity_test.cjs` consume the same file.

## Contract

Only accepted, reportable, non-debug pothole records receive confidence, freshness, or severity categories. Other records return `unknown` for those categories. The ranks are ordinal labels, not probabilities or a combined score.

| Dimension | Derived from | Categories and ranks |
| --- | --- | --- |
| Confidence | Distinct, nonblank drive IDs in the canonical record and its sighting list | `unknown` 0 for ineligible records; `single_observation` 1 for an eligible record with fewer than two distinct drive IDs; `independent_reobservation` 2 for at least two distinct drive IDs |
| Freshness | `lastSeenAt` / `last_seen_at`, an explicit reference time, and caller supplied window | `unknown` 0 for missing, invalid, future, or ineligible time; `fresh` 2 through the inclusive fresh boundary; `aging` 1 through the inclusive stale boundary; `stale` 0 afterward |
| Severity | Existing visual `size` class | `unknown` 0; `small` 1; `medium` 2; `large` 3 |

The fixture uses a reference time of `1800000000`, a fresh boundary of 86,400 seconds, and a stale boundary of 604,800 seconds solely to test boundary behavior. These are **test inputs**, not selected product decay policy. Both implementations require the caller to supply the reference time and window. Neither reads the system clock.

`seen_count` can grow from repeated same-drive sightings, so it does not raise confidence. Two drive IDs are evidence of distinct drives, not necessarily different people or independently verified road hazards. A valid accepted manual report with no drive ID remains `single_observation`; its drive count is zero. `measurement_confidence` describes the visual size estimate and is not this hazard confidence category.

Web `condition_status` maps `fixed` to `is_fixed: true`, `open` and `repair_review` to `false`, and missing or unfamiliar status to `null`. Native reports do not contain this field; a native caller may supply repair state separately. Fixed status is returned separately and does not rewrite the historical component categories. Any future warning or road-health consumer must decide how to gate fixed reports before using the snapshot.

## Regression coverage and limits

The 18 shared vectors cover single and distinct-drive sightings, same-drive repeats, high `seen_count` alone, inclusive freshness boundaries, stale/missing/future timestamps, all known visual size levels, ineligible and debug records, fixed and unknown repair state, a manual report without a drive ID, and repeated execution. The native JVM test maps fixture fields into `ReportEntity`; the Node test scores the web record representation through the pure `static/hazard-model.js` module. The module is not yet wired into a production warning or map flow.

No numeric confidence probability, physical depth/area severity, road exposure, traffic weighting, negative-pass evidence, decay cutoff, combined hazard score, or road-health formula is defined here. Those need product evidence and a separate decision. Current native and web repair representations remain different; the optional repair-state input only lets the shared fixture express the same output contract.
