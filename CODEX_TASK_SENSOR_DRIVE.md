# Codex task: SENSOR-DRIVE-001 — AI-free Drive mode (accelerometer bump detection)

Owner: Sardorbek. Reviewer/manager: Claude (will review your diff, tests and APK after you finish).
Deadline: the owner field-tests Drive in his own car **tomorrow**. A working, conservative,
honestly-labelled feature beats a clever one. Keep the diff small and focused.

## 0. Before you change anything

1. `git status` must be clean. Then `git pull --ff-only origin main`.
   The local `main` is 13 commits behind `origin/main` (Oct 6: India removal, Uzbek UI,
   **real-phone startup crash fix** `e0db1ac`). Never use reset/clean/force/rebase.
   If a stale `.git/*.lock` blocks git and no git process is running, rename it, don't delete others.
2. `git switch -c sensor-drive`.
3. Read `AGENTS.md`, then `PROJECT_MASTER/README.md`, `PROJECT_STATUS.md`, `PRODUCT_DECISIONS.md`
   (D0 reopened: on-device detection chosen by owner) and the last 3 entries of `AGENT_WORKLOG.md`.
   All AGENTS.md rules apply (full-frame invariant, no destructive git, no secrets, no broad upgrades,
   honest reporting, preserve SEC-001..SEC-016 / NEW-001/NEW-002).

## 1. Problem

Today Drive cannot start without an OpenAI API key:
- web: `startDriveAdmitted()` in `static/index.html` → `if (!window.CredentialBroker.hasOpenAi()) { openSettings(...); return; }`
- native: `DriveModePlugin.kt` → `call.reject("An OpenAI API key is required")`

The owner has **no OpenAI API key** and wants Drive to work fully without AI. The labelled-data
on-device vision model is not available yet. So we add a **sensor mode**: the phone's accelerometer
detects the jolt when the car hits a pothole, and the app saves the full camera frame taken just
before the jolt plus GPS, as an **unconfirmed** report that the owner reviews after the drive.

## 2. Required behaviour

### 2.1 Mode selection
- No stored OpenAI key → Drive starts in **sensor mode** (no Settings redirect, no rejection).
- Key stored → existing cloud-AI Drive path, **byte-for-byte unchanged in behaviour**.
- Pass the mode explicitly from web to native (`detectionMode: "sensor" | "cloud"` in `startDrive`);
  native must independently force `sensor` when the key is blank (never trust the page alone),
  and must never create `NativeInferenceEngine`, never call `NativeAiUsageBudget`, never open any
  network connection for detection in sensor mode.
- Dashcam stays disabled exactly as now. Sensor mode is phone-camera only.

### 2.2 Bump detector (pure Kotlin, JVM-testable)
New `drive/NativeBumpDetector.kt` with no Android imports (feed it samples; easy unit tests):
- Input: timestamped acceleration samples (elapsedRealtime ms, x, y, z in m/s²) plus gravity
  vector (or derive gravity with a low-pass filter, α≈0.8 at ~50 Hz) → compute **vertical**
  component = projection of linear acceleration on the gravity unit vector. Must work for any
  phone orientation in a mount.
- Trigger an event when |vertical| ≥ threshold, using the peak within a 300 ms window.
- Thresholds (m/s²) by sensitivity: `low` 6.0, `medium` 4.5 (default), `high` 3.0.
- Gate: GPS speed ≥ 4.2 m/s (15 km/h) from the latest valid fix; ignore when speed unknown.
- Refractory period 2000 ms after an event (one pothole = one event).
- Event = (elapsedMs, peakVertical, speedMps). Bounded memory (ring buffer, no unbounded lists).
- Android adapter in the foreground service: `SensorManager`, prefer `TYPE_LINEAR_ACCELERATION`
  + `TYPE_GRAVITY`; fall back to `TYPE_ACCELEROMETER` with the low-pass split. `SENSOR_DELAY_GAME`.
  Register only while a sensor-mode Drive is capturing; unregister on pause/stop/destroy.
  If the device has no accelerometer, show a clear status message and do not crash.

### 2.3 Event → report
- In sensor mode bursts keep being captured and persisted exactly as now (`persistSelectedBurst`);
  just do not hand them to an inference worker.
- On a bump event pick the most recent persisted burst whose primary frame
  `capturedAtElapsedMs` is within **[event − 4000 ms, event − 150 ms]** (camera looks ahead of
  the wheel). Use the GPS fix nearest the **event time** for the report location
  (`fixNearestToElapsed`), falling back to the burst fix.
- Create one `ReportEntity` from that burst's **complete primary frame** (whole-frame resize/JPEG
  only — no crop, tile, mask, ROI; follow the existing evidence storage/ownership/quota code paths).
  Honest fields, e.g. `captureSource = "drive_sensor"`, `detectionModel = "sensor-accelerometer-v1"`,
  `promptVersion = null`, `decision = "needs_review"`, `assessment = "unverified"`, `size = null`,
  `measurementProvenance/Confidence = "not_applicable"`, `status = "draft"`, and store the peak
  vertical acceleration and speed somewhere visible (e.g. `description`). No Room schema
  migration unless unavoidable; if one is unavoidable, add a proper migration + test.
- No matching burst → do not invent a photo; count it as "bump without frame" in the HUD/summary.
- Duplicates: a second event within 15 m of a sensor report from the same drive merges into it
  (increment seen count) instead of creating another report. Do not reuse the AI verdict
  dedupe criteria if they don't fit; keep it simple and tested.
- Deliver reports to the page through the existing native → web report/outbox path so they show
  up in the normal report list.

### 2.4 Saved frames in sensor mode
- At drive end, persisted keyframes **not** used by a sensor report must not stay "pending AI
  replay" (they would grow storage and show an "Analyse saved frames" button that needs a key).
  Release/delete them through the existing cleanup/ledger mechanisms. Frames owned by reports stay.

### 2.5 Calibration log (important for tomorrow)
- Per sensor-mode drive, write a small CSV in app-private storage: every vertical peak ≥ 2.0 m/s²
  (even below threshold): elapsedMs, wallclock ISO time, peak, speed, lat, lng, accuracy,
  triggered(0/1). Cap at 20 000 rows. Add a "Share sensor log" button on that drive in the
  dashboard using the existing FileProvider/share pattern (respect SEC-014 narrowed paths;
  add a dedicated subdirectory if needed and extend the SEC-014 contract test accordingly).
  Delete All must remove these logs (extend SEC-002 cleanup + its test).

### 2.6 UI (English + Uzbek; the app already has both)
- Drive HUD in sensor mode: "Sensor mode (no AI)" / "Sensor rejimi (AI'siz)", bump count,
  "bumps without frame" count. Drive tip text explains that bumps are saved for review.
- Settings: "Bump sensitivity: Low / Medium / High" (default Medium), stored like other settings,
  passed to native at start. The API-key field text must say the key is optional.
- Report list/detail: sensor reports get a clear badge "Bump — unconfirmed" /
  "Silkinish — tasdiqlanmagan", show the full photo, time, map coordinates, peak and speed,
  and two actions: **Confirm pothole** (mark as user-confirmed, like the manual report path) and
  **Delete**. Never present a sensor report as AI-verified or as an official submission.
- Keep `static/`, `android-app/www/`, `docs/` mirrors in sync with the existing
  `tools/sync-web-assets.py`; respect the CSP (no inline handlers that CSP blocks).

### 2.7 Out of scope (do not do)
- No ML model, no new dependencies, no AI-budget change, no dashcam, no release signing,
  no NEW-002 work, no changes to the cloud-AI Drive logic beyond the mode branch.

## 3. Tests (must add and run)
- JVM: `NativeBumpDetectorTest` — pothole spike (e.g. 7 m/s² 80 ms) triggers at medium; smooth
  road noise (±1.5 m/s²) never triggers; spike below 15 km/h ignored; unknown speed ignored;
  two spikes 1 s apart → one event; same spike with phone rotated 90° (gravity on x) still
  triggers; sensitivity thresholds respected; ring buffer bounded.
- JVM: burst-selection test for the [event−4000, event−150] window (none / one / several /
  frame after event ignored) and the 15 m merge rule.
- Web/Playwright (existing native-bridge mock in `tests/browser_test_utils.py`): with no key,
  tapping Drive calls `startDrive` with `detectionMode: "sensor"` and does **not** open Settings;
  with a key it passes `"cloud"`; a sensor report renders the unconfirmed badge and Confirm/Delete work.
- Static contract: sensor path in `DriveForegroundService` never constructs
  `NativeInferenceEngine` and never calls `NativeAiUsageBudget`.
- Run the existing suites that touch what you changed (full-frame invariant, sec002, sec006,
  sec009 CSP, sec014, pages assets, trip stats, manual offline report). All must pass.
  `full_frame_invariant_test.py` must still pass with your new code.

## 4. Build
Build the debug APK with the documented Windows recipe from the worklog (D: JDK/SDK/Gradle home,
process-local `JDK_JAVA_OPTIONS=-Djdk.net.unixdomain.tmpdir=<project .gradle dir>`), after
`tools/sync-web-assets.py` and `npx cap copy android`:
`android-app\android\gradlew.bat --no-daemon --console=plain :app:assembleDebug` and
`:app:testDebugUnitTest`. Record the APK SHA-256 and size. If the build hits a recorded blocker,
stop and report — don't loop. (Owner authorises pushing **only** the `sensor-drive` branch to
`origin` so GitHub CI also builds/tests it. Do not push or merge `main`.)

## 5. Finish
- Commit on `sensor-drive` with clear messages (no secrets, no APK in git).
- Update `PROJECT_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`, `PRODUCT_DECISIONS.md` (record:
  "owner chose accelerometer sensor mode as the AI-free Drive fallback until the vision model exists")
  and append one `AGENT_WORKLOG.md` entry (SENSOR-DRIVE-001).
- Final report to the owner: files changed, tests run with pass/fail counts, build result,
  APK path + SHA-256, commit hashes, and everything **not** verified (no physical phone run yet).
  Do not claim device verification.
