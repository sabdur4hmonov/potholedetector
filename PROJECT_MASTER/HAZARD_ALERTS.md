# HAZARD-ALERT-001 — private known-pothole warnings

Owner chose 20 s pre-warnings for known potholes, both directions, unconfirmed bumps included by default. Implemented on `hazard-alerts` from SENSOR-DRIVE-001; physical-phone acceptance is pending.

## Source of truth and lifecycle

IndexedDB reports own warning eligibility, including manual Photo, confirmed sensor, accepted AI and unconfirmed sensor records. A bounded cursor produces metadata only: `{version:1,hazards:[{id,lat,lng,kind}]}`. Deleted/fixed/debug/invalid-coordinate and explicitly non-pothole rows are excluded. Native-imported reports retain `native:<Room id>` identity; web-only reports use `web:<IndexedDB id>`. Unreviewed sensor bumps are `unconfirmed`, not verified potholes.

The page awaits `DriveMode.setHazards` before native Drive admission. Committed report/import/confirmation/deletion/condition changes schedule a serialized refresh after two seconds; aborts do not emit a change. Bulk wipe cancels queued refreshes. Native validates the entire versioned batch before writing: at most 5,000 unique nonblank IDs of at most 64 characters, two known kinds, finite latitude/longitude in range. Oversize input fails visibly rather than silently truncating the page snapshot.

One private `filesDir/hazards/hazards-v1.json` snapshot (at most 1 MiB) is saved using a same-directory temporary file, file-descriptor sync and Android `Os.rename`; replacement failure leaves the previous snapshot. Temp files and snapshot are in SEC-002's `hazards` cleanup root, serialized with the existing media mutation/wipe mutex. A process-wide wipe epoch also rejects a pre-wipe request whose worker starts only after deletion finishes. It has no FileProvider alias. Existing backup exclusions apply. No new dependency or Room schema migration.

The service loads this snapshot and owns the alerter in both sensor and cloud modes. New committed, valid, non-debug sensor/accepted-AI reports from the current drive enter a bounded native overlay immediately, independently of WebView execution. Acknowledged records belong to the web snapshot: refresh removes their overlay entries; delayed additions check acknowledgement and serialize with native deletion. Unacknowledged new reports survive an unrelated page refresh. Stable IDs preserve one-shot alert state across refreshes. The overlay is drive-lifetime memory, not a second report database.

## Geometry, grouping and re-arm

Accepted fixes require finite coordinates, accuracy 0–30 m, speed at least 3 m/s, valid heading and monotonic time; the adapter also requires a fix no older than five seconds. Lead distance is `clamp(speed × leadSeconds,80,700)` meters. A hazard within that distance qualifies when its bearing differs from travel heading by at most 30 degrees, with angle wrap; within 40 m it qualifies irrespective of bearing. There is no original lane/heading filter, so the return carriageway is eligible.

The pure Kotlin policy indexes approximately 556 m latitude/longitude buckets and queries nearby buckets, including antimeridian wrap and bounded polar queries. It does not scan all 5,000 hazards for every ordinary GPS fix. Disarmed hazards use a bounded deferred-check heap keyed by travelled distance, avoiding a full disarmed-list distance scan per fix. A hazard re-arms only after an observed accepted fix is farther away than `max(300,1.5 × D_at_alert)`; returning can then warn again. Pause/resume and snapshot refresh preserve this state; a new Drive resets it.

The nearest eligible candidate leads a group of candidates within 30 m of it. A group containing any unconfirmed item is labelled possible. At most one group fires every four seconds. Remaining eligible groups stay pending in distance order, bounded by the list; every fix revalidates distance/bearing so passed or stale queued candidates are not spoken later.

## Output and settings

Drive-owned native tone, vibration, offline TTS, HUD and existing foreground notification work independently of the page. TTS selects an installed voice requiring no network: app Uzbek tries Uzbek, Russian, then English; app English tries English. With unavailable speech, notification/vibration/tone remain available. Audio focus uses navigation guidance and transient may-duck; completion/error, a bounded timeout, pause/stop/destroy release focus. Stop/destroy shut down TTS and release tone/vibration resources. There is no warning network client, provider/budget call or new sound dependency.

English/Uzbek settings default to warnings on, 20 seconds and inclusion of unconfirmed bumps. Ten/thirty seconds and off/exclusion are available for the next Drive. Test warning calls the same native output while parked. The HUD shows loaded eligible count and the last alert. Battery limits add 120/180 minutes, retaining the 30-minute default, expiry and paused timeout.

These are approximate proximity warnings, not route guidance or proof of potholes. Distance clamps, curves, GPS uncertainty, sparse fixes, rate limiting, road geometry and missing sensor evidence can change timing or miss warnings. Sound depends on Android audio focus, volume and installed offline voices. No promised twenty-second accuracy or field calibration exists.

## Verification and next task

See the HAZARD-ALERT-001 worklog entry for test counts, APK hash, commits and CI observations. JVM tests cover requested speeds/clamps, heading/wrap/behind/curve cases, speed/accuracy/invalid input, one-shot/re-arm, grouping/queue, 5,000-item index, JSON validation and atomic replacement failure. Chromium covers canonical/Android pages, authoritative eligibility, snapshot-before-start ordering, default/persisted options, confirmation/deletion/fixed/native refresh, HUD and real native test-button dispatch. Existing full-frame/security/sensor/trip/manual regressions remain active.

Exact next task: owner/reviewer installs the recorded debug APK and, while parked first, tests sound/vibration/offline voice and volume; then performs a conservative physical acceptance drive and return leg with Maps in front and screen off. Check warning timing/grouping/re-arm, unconfirmed wording, pause/resume/stop, manual and fixed/deleted hazards, and Delete All. Actual Android sound/focus restoration, vibration, offline TTS locales, lock-screen/background survival, GPS/road timing, battery/thermal behavior and real-device deletion remain unverified. NEW-002, release signing and model training remain separate.
