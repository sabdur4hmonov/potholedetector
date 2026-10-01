# TRIP-001: private sampled drive statistics

## Implemented scope

TRIP-001 is complete at source/Node/browser level for non-persisting private statistics in the existing dashboard. The pure `static/trip-stats.js` consumes the existing `[offset_seconds, latitude, longitude, accuracy_m, speed, heading]` track shape. `openDash` uses its aggregate after the existing native-history merge. Canonical, hosted and Android WebView sources use the same module; no native computation or parity implementation is required because the service does not compute these summaries.

This is the Phase 1 display-only slice allowed by the roadmap and the TRIP-001 card. It does not implement trip history, route rendering, destination entry, retention, opt-out, deletion, ranking or sharing. D1 remains unapproved; TRIP-002 is blocked. FRESH-001's human cutoffs/expired semantics and REPORT-LOCAL-001's physical-device validation remain blocked independently. No NEW-002 or release gate is closed.

## Versioned calculation contract

`trip-stats-v1` is deterministic, synchronous and in memory. Distance uses whole-track consecutive fixes and spherical haversine geometry with Earth radius 6,371,000 metres. Each admitted displacement is discounted by both accuracy radii, floored at zero. This suppresses plausible stationary jitter and deliberately undercounts uncertain movement; it is not a guaranteed physical lower bound or calibrated odometer.

Moving time sums the durations of admitted intervals whose discounted displacement is positive. Average moving speed is discounted distance divided by that moving time; the aggregate is time-weighted, not an average of drive averages. Peak sampled speed is the highest admitted discounted interval speed. Supplied speed and heading fields cannot promote movement. This is a sampled interval estimate, not instantaneous/measured vehicle maximum speed, driving compliance, safety or a ranking input.

| Admission/resource bound | Value and rationale |
| --- | --- |
| Points per drive | First 20,000; matches existing native `MAX_TRACK_POINTS`. Excess marks coverage partial. |
| Drives per dashboard calculation | First 200 in existing returned order; caps computation at four million points without changing storage or retention. Excess marks partial. |
| Coordinates/time | Finite numeric coordinates within latitude/longitude ranges; finite nonnegative offsets. No numeric-string/null coercion. |
| Accuracy | Finite 0 through 15 metres inclusive; reuses the existing strict event-matching accuracy envelope, not native capture's coarser 30-metre gate. Poor/missing accuracy is omitted. |
| Adjacent interval | Positive and at most 30 seconds; a conservative engineering continuity bound, three times existing 10-second live-fix age admission. It is not a hazard freshness cutoff or inferred journey duration. |
| Raw displacement speed | At most 100 m/s; permissive finite teleport rejection before discounting. An engineering bound, not a legal speed limit, empirical calibration or product safety claim. |

Invalid samples, duplicates, reversed time, oversized gaps and jumps reset continuity. A rejected pair's endpoint is discarded; no connection bridges the omitted segment. The next valid sample seeds a new segment. No resampling, smoothing, timestamp repair, route lookup, inference or provider call occurs.

Outputs contain scalar statistics and a policy version only, never coordinate arrays. Missing tracks or no admitted interval yield null distance/time and `unavailable`, rather than a false zero. A stationary admitted track has zero distance/moving time but unavailable moving/peak speed. Coverage is `sampled` for wholly admitted input, `partial` if samples/intervals/drives were omitted, or `unavailable` if none is usable. `sampled` does not assert complete real-world journey coverage: capture itself can omit time before/after the track. The UI explains this for every result.

## Storage, compatibility and boundaries

The existing `gps_track`, Room sessions, IndexedDB drives, native `getDrives` and native-history import remain unchanged. Rendering retains no new fields, route history or settings; no migration or automatic upload is added. Existing Delete All behavior is preserved. Derived metrics appear only in the private dashboard, not report export, public hazard coordinates, badges, warnings or scoring. Existing native-history synchronization still works as before; this package adds no bridge operation.

Labels use the current English fallback until reviewed translation. Dashboard distance now uses the filtered sampled estimate instead of the unfiltered `trackKm` sum. The old helper is preserved; capture, detection thresholds, scoring, deduplication, whole-frame evidence, manual reports, cloud/BYOK, durable native acknowledgement and inference/resource limits are unchanged. CSP hashes and local script inventory are updated without relaxing policy. Hosted and packaged assets mirror canonical sources exactly.

## Validation and limits

`node tests/trip_stats_test.cjs` covers known numerical geometry, repeatability/input immutability, jitter/reported-speed suppression, invalid/poor fixes, disordered/duplicate timestamps, gaps/jumps/no bridging, antimeridian geometry, weighted summaries, unknowns and bounded input truncation.

`tests/trip_stats_browser_test.cjs` runs real Chrome on canonical and packaged surfaces with networking disabled. It verifies unknown and partial coverage, formatted distance/time/speed estimates, private/uncertainty copy, deterministic repeat rendering, enforced CSP, no network attempt and byte-identical stored-drive JSON before/after dashboard opening. Its synthetic tracks are test-only IndexedDB records; they are not device evidence.

Scoring/evidence and road-match parity, outbox durability, manual offline reporting, full-frame, image/AI budgets, native inference ownership/quota/resource, asset and CSP regressions also pass; exact results are in AGENT_WORKLOG.md. No Android build, APK/AAB, physical-device validation or field calibration was performed. Actual device performance and measurement accuracy remain unverified.

## Exact next task

TRIP-002 requires the recorded human D1 retention/opt-out/minimization decision before any new retained fields, per-drive deletion or route-history UI. Obtain that decision; do not start its implementation or choose defaults. FRESH-001 separately still requires its own human policy response.
