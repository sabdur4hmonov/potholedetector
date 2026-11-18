# Codex task: HAZARD-ALERT-001 — warn the driver ~20 s before a known pothole

Owner: Sardorbek. Reviewer/manager: Claude. Field test is **tomorrow**: the owner drives to a
destination with Drive running (sensor mode records bumps + GPS), then on the way back the app must
warn him about each recorded pothole **about 20 seconds before he reaches it**, while Google Maps
or another app is on screen. Small, conservative, tested diff. All `AGENTS.md` rules apply.

## 0. Start
1. `git status` clean. `git switch sensor-drive` and `git pull --ff-only` (your SENSOR-DRIVE-001
   commits `f59d93a`, `c2888ee`). Then `git switch -c hazard-alerts` from it.
2. Check the GitHub CI result for `sensor-drive` (`gh run list --branch sensor-drive`). If any job
   failed, fix that first in a separate commit on `hazard-alerts` and say so in the report.
3. Re-read the latest `AGENT_WORKLOG.md` entries and `PROJECT_MASTER/SENSOR_DRIVE.md`.

## 1. Where the hazard list comes from
The **web layer (IndexedDB) is the source of truth** for reports: manual Photo reports exist only
there, and Confirm/Delete/fixed state live there. Native Room rows alone are not enough.
- New plugin method `DriveModePlugin.setHazards({ version, hazards: [{ id, lat, lng, kind }] })`.
  `kind` ∈ `confirmed` (AI-accepted, manual/user-confirmed, user-confirmed sensor) |
  `unconfirmed` (sensor bump not yet reviewed). Exclude deleted, `condition_status === "fixed"`,
  rows without finite coordinates, and debug-only rows.
- Validate strictly natively: ≤ 5 000 items, finite lat/lng in range, id ≤ 64 chars, known kind;
  reject the whole call otherwise. Persist atomically to one small app-private JSON file
  (`files/hazards/hazards-v1.json`, write temp + rename) so it survives WebView death mid-drive.
  Delete All must remove it (extend SEC-002 cleanup + contract test).
- The page calls `setHazards` before `startDrive`, and again (debounced ~2 s) whenever reports are
  added, confirmed, deleted, marked fixed, or synced from native.
- During a Drive, sensor/AI reports created **in the same drive** are added to the native
  in-memory list immediately (kind `unconfirmed` for sensor, `confirmed` for AI-accepted), so a
  same-trip return leg works even if the page is not running.

## 2. Alert decision (pure Kotlin, JVM-testable, no Android imports)
New `drive/NativeHazardAlertPolicy.kt`. On every accepted GPS fix:
- Use only fixes with accuracy ≤ 30 m and speed ≥ 3 m/s (≈ 11 km/h); heading from the fix if
  speed ≥ 3 m/s, else skip (no alerts when stopped/crawling).
- Lead distance `D = clamp(speed × leadSeconds, 80 m, 700 m)`, `leadSeconds` default **20**.
- A hazard is *ahead* when distance ≤ D **and** the bearing from the car to the hazard is within
  **±30°** of the heading (handle 359°/1° wrap), **or** distance ≤ 40 m regardless of bearing
  (curves). Ignore hazards farther than D.
- Fire **one** alert per hazard per drive. Re-arm a hazard only after the car has been > 1.5 × D
  (min 300 m) away from it (U-turn / loop / second pass).
- Group: hazards within 30 m of each other that fire together are one alert ("2 potholes").
- Rate limit: at most one spoken alert every 4 s; queue the rest in distance order (bounded).
- Spatial pre-filter (e.g. lat/lng grid buckets ~500 m) so 5 000 hazards cost little per fix.
- Opposite carriageway: the owner returns on the other side of the road. Do **not** filter by
  lane/direction of the original recording; warn for any hazard on the path ahead.

## 3. Alert output (native, works with Maps in front and screen off)
New `drive/NativeHazardAlerter.kt`, owned by `DriveForegroundService`, active in **both** sensor
and cloud Drive modes:
- Short distinctive tone (`ToneGenerator` or bundled tiny sound) + vibration pattern, then
  `TextToSpeech` phrase with rounded distance, e.g. Uzbek "Diqqat, 300 metrdan keyin chuqur",
  Russian "Внимание, яма через 300 метров", English "Pothole in 300 meters". Choose TTS locale:
  app language `uz` → try `uz-UZ`, else `ru-RU`, else `en`; app language `en` → `en`.
  If TTS is unavailable, tone + vibration + notification still happen. Unconfirmed bumps use the
  same alert with the word "possible / ehtimoliy / возможная".
- Audio: `AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE`, transient focus *may duck*,
  abandon focus after speaking. Never stop the user's music/Maps permanently.
- Also update the Drive HUD + the existing foreground notification text with the last alert.
- Release TTS/tone/vibrator on stop/destroy. No network use. No new dependencies.

## 4. Settings & UI (EN + UZ)
- Settings: "Pothole warnings" on/off (default **on**), "Warn before: 10 / 20 / 30 s"
  (default **20**), "Include unconfirmed bumps" (default **on**), and a **"Test warning"** button
  that plays the real tone + TTS once (so the owner can check volume before driving).
  Pass these to native in `startDrive`.
- Drive HUD: "Warnings: N potholes loaded" and the last alert text.
- Drive battery limit: add **120** and **180** minute options (keep 30 default unless the owner
  changes it). Do not remove the limit.
- Keep the three web mirrors synced with `tools/sync-web-assets.py`; respect CSP.

## 5. Tests (add and run)
- JVM `NativeHazardAlertPolicyTest`: straight approach at 50 km/h fires once at ≈ 278 m
  (≈ 20 s); at 20 km/h D clamps to 111 m; at 120 km/h ≈ 667 m; at 140 km/h clamps to 700 m; at 12 km/h clamps up to 80 m; hazard behind → no alert;
  hazard 40° off heading at 200 m → no, at 35 m → yes; heading wrap 355°→5°; speed < 3 m/s or
  accuracy > 30 m → no; one-shot then re-arm after moving > 1.5 × D away and returning;
  grouping of 2 hazards 20 m apart → one alert with count 2; 5 000-hazard list processes a fix
  quickly (bounded, no per-fix full scan if avoidable); invalid inputs ignored.
- JVM: `setHazards` validation (oversize, NaN, bad kind → reject; atomic persist/reload).
- Browser (existing native-bridge mock): `setHazards` called before `startDrive` with confirmed +
  unconfirmed items, excluding deleted/fixed; re-sent after Confirm/Delete; settings round-trip;
  Test warning calls the native test method.
- Static contracts: alerter uses no network; Delete All removes hazard file; existing full-frame,
  SEC-002, SEC-006, SEC-009 CSP, SEC-014, sensor_drive and trip-stats suites still pass.

## 6. Build, commit, report
- Same Windows build recipe as SENSOR-DRIVE-001 (`tools/sync-web-assets.py`, `npx cap copy android`,
  `gradlew.bat --no-daemon --console=plain :app:assembleDebug :app:testDebugUnitTest`).
  Record APK path, size, SHA-256. The known Windows symlink-privilege unit-test failure may stay
  failing; any other failure must be fixed or reported.
- Commit on `hazard-alerts`; owner authorises pushing **only** `hazard-alerts` to `origin` for CI.
  No push/merge to `main`. No APK in git.
- Update `PROJECT_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`, `PRODUCT_DECISIONS.md` ("owner chose
  20 s pre-warnings for known potholes, both directions, unconfirmed bumps included by default"),
  append one `AGENT_WORKLOG.md` entry (HAZARD-ALERT-001).
- Final report: files, test counts, build result, APK SHA-256, commits, CI status, and what is
  not verified on a physical phone. Never claim device verification.
