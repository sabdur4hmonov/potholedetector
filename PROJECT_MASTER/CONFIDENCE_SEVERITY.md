# CONF-001: conservative observation support and visual severity

CONF-001 exposes the completed FUTURE-SCORING-001 confidence/severity dimensions without selecting a freshness window, and consumes them in report detail on canonical, Android WebView and hosted web assets. No new scoring formula, detection threshold, storage field or model is introduced.

## Inputs and existing rules

Native inference produces the binary assessment, accepted/reportable flags, visual `size`, damage type, quality/temporal cues, GPS/capture metadata and model/prompt provenance. `ReportEntity` and web reports retain the accepted canonical result, drive ID, distinct sighting drive IDs, `seenCount`/`seen_count`, last-seen time and size. Matching already controls which observations join that canonical event. Manual private reports have `decision: manual`, user-reported provenance and unknown model/size fields.

`NativeHazardScoringPolicy.evidence` and `HazardModel.deriveHazardEvidence` reuse the existing categories:

| Dimension | Rule | Bounds |
| --- | --- | --- |
| Eligibility | Exactly accepted, pothole=1, reportable=1 and non-debug | Otherwise confidence/severity unknown |
| Observation support | Eligible record with fewer than two distinct nonblank drive IDs: single observation; two or more: distinct-drive reobservation | Existing ordinal ranks 0–2; no accuracy probability |
| Visual severity estimate | Eligible canonical size is small, medium or large | Existing ordinal ranks 0–3; absent/unrecognized size unknown |
| Condition | Fixed=true; open/review=false; absent/unrecognized=null | Separate historical condition; no repair transition |

The two-drive boundary and size mapping come directly from `hazard-scoring-v1.json`; they are not new calibration. Drive IDs retain their existing exact string identity. Blank/non-string IDs do not count; duplicate IDs count once. Malformed sighting lists supply no additional drives. `seen_count`, image-quality labels, measurement confidence, GPS accuracy and temporal cues do not promote this category. Their existing detection/matching roles remain unchanged. Weak measurements therefore never become a numeric probability or stronger support merely through this presentation layer.

Conflicting eligibility fields (for example accept plus pothole=0), rejected/review decisions, missing decisions and debug records yield unknown confidence/severity even with many drives or a large size. This layer does not reconcile contradictory raw sightings or replace canonical merge policy. A canonical visual size remains an estimate, not a depth/area measurement or safety ranking. Distinct drives are not proof of independent people or independently verified hazards.

## Version and compatibility

The new non-persisted evidence snapshot identifies `hazard-evidence-v1`. Its 18 shared vectors are in `android-app/android/app/src/test/resources/hazard-evidence-v1.json`, consumed by the JVM and Node tests. The original 18-vector scoring contract and returned scoring shape remain unchanged; `score` delegates its confidence/severity/condition portion to the same derivation. Freshness still requires explicit caller parameters and is not displayed by CONF-001.

Report detail shows observation support and visual severity with their explanations. Actual manual-first reports remain unknown and explicitly user-reported. Fixed reports label the categories as historical evidence. Non-road civic reports do not display this panel. English strings use the existing localization fallback pending separately reviewed translations. The UI performs no request and mutates/persists no report. Native reports imported into the WebView use the same consumer; no native bridge/schema change is required.

## Validation and limits

Shared tests cover clear and weak observations, incomplete/invalid size, conflicting gates, zero/one/two drives, blank/duplicate/invalid IDs, malformed lists, extreme same-drive counts, manual/debug input, fixed/unknown condition and repeated evaluation. The existing scoring fixture verifies unchanged score behavior. Chromium tests exercise every detail branch on canonical and packaged assets with networking disabled, unchanged input records and the enforced CSP. Existing full-frame, image-budget, inference/resource/evidence, matching and outbox guards remain required.

No combined importance score, physical severity, calibrated probability, product freshness cutoff, warning/road-health integration or independent-person evidence is supplied. FRESH-001 needs a separately approved freshness policy before user-visible age categories are integrated. REPORT-LOCAL-001 remains PARTIALLY COMPLETE and DEFERRED/BLOCKED on physical Android-device validation under the explicit authorization to proceed with CONF-001. No physical evidence, release claim or NEW-002 change is made.
