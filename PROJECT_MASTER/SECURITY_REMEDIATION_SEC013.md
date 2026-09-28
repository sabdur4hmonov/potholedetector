# SEC-013 — GPS/location-history retention disposition

Status: **PARTIALLY RESOLVED — INVESTIGATION/DISPOSITION COMPLETE; RETENTION/OPT-OUT PRODUCT DECISION OPEN**

Severity: **INFO** (original classification preserved). Verified 2026-09-14 by source inspection and 11 deterministic checks. **No code changes.** No independent SEC-013 production blocker was recorded or found; the recorded "architecture decision required for production" note remains open. The **overall security gate remains FAIL** because of the existing blockers.

## Finding

Original audit (`outputs/SECURITY_AUDIT.md` §SEC-013; `outputs/SECURITY_VERIFICATION.md` §SEC-013): detailed drive location histories depend on device protection and manual retention choices. The audit recommended track minimization, short retention, a route-history opt-out and protected storage. Its verification result was “NEEDS DESIGN DECISION”, with production blocker **NO**.

## What is retained, where, and for how long

| Data | Location | Retention |
| --- | --- | --- |
| **Native drive track**: one `[offsetS, lat, lng, accuracy, speedMps, heading]` entry per Fused Location result, using a high-accuracy request with a 500 ms interval, 250 ms minimum and 1 m minimum distance | In memory at `NativeDriveLocationProvider.gpsTrack` (`:158`, `:263-271`); persisted by `DriveForegroundService.persistSession` (`:2748-2757`) to Room `native_potholes.db` table `sessions.gpsTrackJson` (`Entities.kt:192`) | Capped at **20,000 points per session** (`MAX_TRACK_POINTS`, `:170`) and reset on each new session (`:184`). Sessions are also bounded by the Drive active-time limit (15/30/60/90 min, default 30). **No age-based purge across sessions**: rows remain until Delete All. |
| **WebView copy of the same track** | `getDrives` returns `gps_track` (`DriveModePlugin.kt:1303`). `index.html:3032-3036` POSTs stopped/interrupted sessions to the local `/api/drives` route, stored in IndexedDB `drives` (`standalone.js:11233-11241`) | Indefinite until Delete All. There is no per-drive IndexedDB delete. |
| **Browser-fallback track** (`navigator.geolocation.watchPosition`, 6-decimal coordinates plus accuracy/speed/heading) | `ctx.gpsTrack` (`index.html:3690-3693`) → IndexedDB `drives` at stop (`:4014-4018`) | No explicit point cap. Per session, bounded by the Drive limit timer (`:3642-3644`); indefinite until Delete All. |
| Pairing buffer `NativeGpsFixHistory` | Memory only, 16 fixes | Cleared on stop and re-registration (`NativeDriveLocationProvider.kt:201, :320, :434`). Not persisted. |
| Point locations (not routes): reports, event sightings, repair targets/observations, drive keyframes | Room/IndexedDB rows with lat/lng/accuracy/speed/heading | Needed for reports and deduplication. Keyframe rows can be deleted per drive; other rows remain until report deletion or Delete All. |
| Optional `Documents/pothole-frames` manifest (Settings frame-saving, off unless enabled) | Shared Documents; per analysed frame `lat/lng` (`index.html:5368-5369`) | Until the user deletes it. Delete All removes the folder (SEC-002). Recorded here only; not changed. |

## Necessity for current functionality

Only two consumers exist; check 6 verifies the complete list:

1. `gpsAt(track, seconds)` (`index.html:5076`, used at `:5330`) pairs **browser-recorded footage** frames with coordinates during `analyseFootage`. Native footage uses `analyseNativeKeyframes`, whose keyframe rows carry their own coordinates and do not read `gps_track`.
2. `trackKm` (`index.html:5511`, used at `:5466`) computes the “km of road covered” statistic.

Conclusion: the browser-fallback track is functionally required to geolocate re-analysed footage. The **native** persisted track currently serves only the km statistic. Its accuracy, speed, heading and full point sequence exceed that use, so the native route history is **not strictly necessary** in its current detail. Reducing it would change stored data and History/statistics behavior. No repository requirement defines the replacement or a retention period, so it was not implemented. See the options below.

## User control, protection, local/remote

- **Deletion:** Delete All clears Room `sessions` (`DriveModePlugin.kt:1221`), in the same transaction as other app tables, plus IndexedDB `drives` (`standalone.js:8258-8275`). This is covered by the existing SEC-002 cleanup work. The per-drive “Delete video” action (`deleteFootage`) removes footage and keyframes, **not** the session track. A user cannot delete one drive’s route or clear only route history.
- **Opt-out:** None specific to route history. Location permission is required for Drive, and denying it disables Drive. Recording, Debug retention and frame saving have settings; the track does not.
- **Protection:** App-private Room DB and WebView IndexedDB use Android UID sandboxing and device storage encryption. `allowBackup="false"`; backup and device-transfer rules exclude root, file, database, sharedpref and external domains. No database-level encryption or biometric/view gate is used; this matches the audit. Keystore protection covers credentials only (SEC-001), not location history.
- **Local vs remote:** **Local-only.** `api()` is the local `StandaloneAPI.handle` router (`index.html:1337-1339`). No `fetch`, XHR, beacon or WebSocket call carries `gps_track`/`gpsTrack`. The native track is held only by the provider, service, entity and plugin, not by the inference transport. The track is not in the frame manifest. Individual report coordinates can still go to disclosed geocoding/GIS and handoff recipients (`docs/privacy.html:119, :165-173`). That is point data, not route history.
- **Disclosure:** `docs/privacy.html:119` states that a local drive track may be retained with accuracy, speed, heading and timestamps. `:193` says drive summaries remain until deleted, `:198` covers Delete All, and `:202` states backup is disabled. The notice is accurate for current behavior and was not changed.

## Decision

**No code changes.** Current behavior is local-only, sandboxed, backup-excluded, bounded per session, disclosed and deletable through Delete All. The audit's remaining recommendations are short/automatic retention, a route-history opt-out, per-drive route deletion, native-track minimization and at-rest encryption/view gating. Each requires a product or architecture choice that the repository does not specify, such as a retention period, UX, stored schema/statistic semantics or a key-management design. Implementing one would invent a requirement. SEC-013 therefore stays **PARTIALLY RESOLVED**, not RESOLVED.

Options for the owner (not implemented; ordered by smallest change):

1. Persist only a derived distance, or a decimated coordinate list, for native sessions instead of the full-detail track. Keep the browser-footage track, which `gpsAt` needs.
2. Add per-drive route deletion alongside “Delete video”, clearing `sessions.gpsTrackJson` and the IndexedDB `gps_track` field.
3. Add an owner-approved automatic retention period or a “don't keep route history” setting.
4. Encrypt/gate history at rest only as part of a reviewed key-management design.

Reassess before any Uzbekistan community map/sync or other remote history feature. The audit requires precise traces to stay out of public data.

## CODEX HANDOFF / CONTINUATION CHECKPOINT

1. **Current task:** SEC-013.
2. **Final SEC-013 status:** PARTIALLY RESOLVED (investigation/disposition complete; retention/opt-out/minimization product decision open; no independent production blocker).
3. **What was investigated:**
   - Files: `drive/NativeDriveLocationProvider.kt`, `drive/NativeGpsFixHistory.kt`, `drive/DriveForegroundService.kt` (`persistSession`), `drive/NativeDriveEndSummaryStore.kt` (no location fields), `db/Entities.kt`, `db/Daos.kt`, `db/PotholeDatabase.kt`, `plugin/DriveModePlugin.kt` (`getDrives`, `deleteFootage`, Delete All, `parseGpsTrack`), `AndroidManifest.xml`, `res/xml/backup_rules.xml`, `res/xml/data_extraction_rules.xml`, `static/index.html` (browser watch, native sync, `analyseFootage`/`gpsAt`, `trackKm`, History delete, `api()`, frame manifest), `static/standalone.js` (IndexedDB `drives`, Delete All), `docs/privacy.html`, existing tests referencing drives/`gps_track`, audit/verification SEC-013 sections. Kotlin paths are under `android-app/android/app/src/main/java/dev/aiengg/potholereporter/`.
   - Flow: Fused Location → `gpsTrack` (≤20,000/session) → Room `sessions.gpsTrackJson` → `getDrives` → IndexedDB `drives.gps_track`. The browser flow is `watchPosition` → `ctx.gpsTrack` → IndexedDB `drives.gps_track`. Consumers: `gpsAt` (browser footage) and `trackKm` (stat).
   - Storage/retention: described in the table above. Retention is per-session bounded and cross-session indefinite until Delete All.
   - Deletion/opt-out: Delete All only; there is no per-drive route deletion and no route-history opt-out.
   - Protection: UID sandbox, device encryption and backup/transfer exclusion. There is no DB-level encryption.
   - Local vs remote: route history is local-only. Report point coordinates are sent to disclosed services.
4. **What Claude Code changed:** No code changes. Documentation only:
   - `PROJECT_MASTER/SECURITY_REMEDIATION_SEC013.md` (new): this report and handoff.
   - `PROJECT_MASTER/SECURITY_STATUS.md`: SEC-013 row and report link.
   - `PROJECT_MASTER/PROJECT_STATUS.md`: SEC-013 completed-work bullet and remaining-work sentence.
   - `PROJECT_MASTER/CHANGELOG.md`: SEC-013 row.
   - Outside the repository: evidence script `work/sec013/check_sec013.cjs` and output `work/sec013/check_sec013.out.txt`.
5. **What Claude Code did NOT change:** application source, web mirrors, native code, manifests, Room schema, privacy notice, tests, dependencies/lockfiles, Gradle/build config, SEC-001–SEC-012 remediations, SEC-014+ and NEW-001/NEW-002, architecture, retention policy or product behavior.
6. **Verification:**
   - `node work/sec013/check_sec013.cjs --repo <repo>` → **11 passed, 0 failed** (exit 0). The checks cover track shape/cap/reset; in-memory pairing buffer; Room persistence without DB encryption; session deletion only via Delete All with `deleteFootage` not touching sessions; WebView copy with no per-drive delete; the exhaustive consumer list; no network sink; backup/transfer exclusions; the browser limit timer; byte-identical four web mirrors (index.html `f640ac7b17159f3c`, standalone.js `7708b84f13d51293`); and privacy-notice disclosure.
   - The first run returned 10 passed/1 failed because of a script bug: check 4 used the wrong end marker for `deleteFootage`, the last `@PluginMethod`. After the script was fixed, check 4 passed; no source changed.
   - Preservation SHA-256 comparison against a pre-task snapshot showed that only the four PROJECT_MASTER documents above differ.
   - Not run: Gradle/build, ADB/device/emulator, Room runtime inspection, browser/Playwright tests (Playwright not installed for the PATH Python 3.14; `tests/delete_all_data_test.py` therefore not executed). These checks are source-level and static, not runtime proof.
7. **Security state after SEC-013:**
   ```text
   SEC-001 = PARTIALLY RESOLVED
   SEC-002 = PARTIALLY RESOLVED
   SEC-003 = PARTIALLY RESOLVED
   SEC-004 = PARTIALLY RESOLVED
   SEC-005 = PARTIALLY RESOLVED
   SEC-006 = RESOLVED — SOURCE LEVEL
   SEC-007 = RESOLVED — SOURCE/STATIC
   SEC-008 = RESOLVED — DEPENDENCY/TOOLCHAIN
   SEC-009 = RESOLVED — SOURCE/BROWSER
   SEC-010 = PARTIALLY RESOLVED — SOURCE/BROWSER
   SEC-011 = RESOLVED — INFO / TOOLING DISPOSITION
   SEC-012 = RESOLVED — APPLICABILITY ONLY
   SEC-013 = PARTIALLY RESOLVED — DISPOSITION COMPLETE; PRODUCT DECISION OPEN
   SEC-014 = NOT STARTED
   SEC-015 = NOT STARTED
   SEC-016 = NOT STARTED
   NEW-001 = NOT STARTED (release blocker)
   NEW-002 = NOT STARTED (release blocker)
   Overall gate = FAIL
   ```
8. **EXACT NEXT TASK:** "SEC-014" (broad app-specific FileProvider roots; `android-app/android/app/src/main/res/xml/file_paths.xml`).
9. **Instructions for the next agent:** Read `PROJECT_MASTER/README.md`, `PROJECT_MASTER/PROJECT_STATUS.md`, `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/CHANGELOG.md`, then this report, then the SEC-014 sections of `../outputs/SECURITY_AUDIT.md` and `../outputs/SECURITY_VERIFICATION.md` (relative to `work/`). Do **not** re-audit SEC-001–SEC-013. Do not implement SEC-013 options unless the owner chooses one. Do not upgrade dependencies broadly, retry the recorded Gradle `AccessDeniedException` or ADB blockers, or commit/push. Work only on SEC-014. Note that `Documents/pothole-frames` and FileProvider share paths relate to SEC-014 scope and were not changed here.
10. **Repository state:** no commit and no push. Working tree = the pre-existing uncommitted remediation changes plus this task's four `PROJECT_MASTER/` documentation changes. Git requires `-c safe.directory=...` because the directory is owned by the `CodexSandboxOnline` user; global git config was not changed.
