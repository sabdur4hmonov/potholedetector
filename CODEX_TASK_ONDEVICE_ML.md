# Codex task: ML-DETECT-001 — on-device camera pothole detector, fused with sensor + warnings

Owner: Sardorbek. Reviewer/manager: Claude (will independently rebuild, run tests and review the diff).
Goal: the camera itself recognises potholes **on the phone**, with no API key, no internet and
no per-image cost. Keep everything that already works (sensor bumps, hazard warnings, Photo,
optional cloud AI) and combine it with the new detector. All `AGENTS.md` rules apply.

This task has two halves. You build both, but you **cannot** train the model on this laptop
(no GPU). You write the training notebook; the owner runs it on free Google Colab GPU and drops
the resulting model file into the repo. The app must build, pass tests and behave exactly as
today when the model file is absent.

## 0. Start
1. `git status` clean. `git switch hazard-alerts`, `git pull --ff-only`, then `git switch -c ondevice-ml`.
2. Read `AGENTS.md`, `PROJECT_MASTER/PRODUCT_DECISIONS.md` (D0 reopened = on-device detector),
   `SENSOR_DRIVE.md`, `HAZARD_ALERTS.md`, last 3 `AGENT_WORKLOG.md` entries.

## 1. Owner decisions already made (record them in PRODUCT_DECISIONS.md)
- Detector: **YOLOX-Nano** (fallback YOLOX-Tiny if Nano recall is too low), Megvii YOLOX,
  **Apache-2.0**, pinned to an exact commit. **No Ultralytics / YOLOv5/v8/11 code or weights (AGPL).**
- Runtime on Android: **ONNX Runtime Android** (MIT), one exact pinned version. Record its
  Maven coordinates and publisher SHA-256 sidecar check in `NEW002_RELEASE_FILE_PROVENANCE.tsv`
  style evidence (do not weaken NEW-002; just document the new artifact like the others).
- Training data: **RDD2022** (Arya et al., CC BY-SA 4.0), class **D40 = pothole**. All other
  damage classes (cracks D00/D10/D20, etc.) are **hard negatives**; images with no D40 are negatives.
  Use the smartphone/vehicle subsets (Japan, India, Czech, Norway, United States, China_MotorBike);
  **exclude China_Drone**. Because of CC BY-SA, the trained weights are distributed under
  **CC BY-SA 4.0 with attribution** (separate from the MIT app code): add a `MODEL_LICENSE.md`
  + attribution line in the app's About/Data sources and `docs/sources.html`.
- Product rule unchanged: users see **Yes/No**, never a confidence percentage.

## 2. Training pipeline (`ml/` directory, Python, runs on Colab)
- `ml/prepare_rdd2022.py`: download the official RDD2022 zip, verify a SHA-256 you record from the
  first download (print it; fail if a pinned value exists and differs), convert Pascal VOC XML →
  COCO JSON with **one class `pothole`**, keep negatives, deterministic split by image
  (train/val/test 80/10/10, fixed seed, stratified by country). Write dataset stats (images,
  boxes, positives/negatives per country) to `ml/dataset_stats.json`.
- **Full-frame invariant applies to training too.** Every training/eval/inference input is the
  complete frame, only whole-image resize + letterbox padding. Therefore **disable YOLOX mosaic,
  mixup, random crop and any affine scale/translate that cuts the field of view**
  (`enable_mosaic=False`, `mosaic_prob=0`, `mixup_prob=0`, translate 0, scale ≥ 1 only via
  letterbox shrink). Allowed: horizontal flip, HSV/brightness/blur/noise, whole-frame
  downscale-with-padding. Add a test that greps the exp file for these settings
  (extend `tests/full_frame_invariant_test.py`).
- `ml/yolox_pothole_exp.py`: YOLOX exp, `num_classes=1`, input **416×416**, Nano width/depth.
- `ml/train_pothole_yolox.ipynb`: one-click Colab notebook: checks GPU, clones pinned YOLOX,
  installs pinned deps, runs prepare script, trains (sensible default epochs that fit the free
  Colab session, resumable from checkpoint saved to Google Drive), evaluates on the test split
  and prints **precision, recall, F1 at the chosen threshold, plus per-country recall**, picks the
  score threshold that maximises F1 with precision ≥ 0.80 on val, exports **ONNX (opset pinned,
  static 1×3×416×416)**, runs the exported ONNX on 20 test images and compares with PyTorch
  outputs, then downloads `pothole_yolox_nano.onnx` + `pothole_model.json`
  (`{version, input_size, score_threshold, nms_iou, sha256, metrics, dataset_sha256, yolox_commit}`).
- `ml/README.md` in **Uzbek + English**: exact steps for the owner (open in Colab → Runtime → GPU →
  Run all → download two files → put them in `android-app/android/app/src/main/assets/ml/` → tell
  Codex/Claude). No secrets, no Drive tokens in the repo.

## 3. Android integration
- `drive/NativePotholeDetector.kt`: loads `assets/ml/pothole_yolox_nano.onnx` + `pothole_model.json`,
  verifies the model SHA-256 against the JSON before use (fail closed = detector disabled with a
  clear status), letterboxes the **complete** frame to 416×416 (no crop), runs ONNX Runtime on one
  background thread, decodes YOLOX outputs, NMS, returns `Yes/No` + boxes (boxes are internal,
  for debug overlay only). Pure decode/NMS/letterbox math lives in a separate JVM-testable object.
- If the model files are absent → detector unavailable, app behaves exactly like today
  (sensor + warnings + optional cloud). Show "Camera detector: not installed" in Settings.
- Bounded work: at most one inference in flight; if busy, skip that frame (never queue raw
  bitmaps). Measure and expose average inference ms in the Drive HUD (debug mode) and the
  sensor CSV log (new columns are fine).
- Use the existing 3-view burst: a **camera detection = pothole in ≥ 2 of the 3 views** (existing
  "consistent Drive views" rule). Persist the primary full frame as evidence via the existing
  storage/ownership/quota path (same as sensor reports).

## 4. Fusion with what already exists ("eskisini ham qo'shib")
Drive mode without key becomes **"Offline mode (camera + sensor)"**; with model absent it is the
current sensor mode. Report origin labels (EN + UZ), stored in a field such as `captureSource`
/ `detectionModel` (no schema migration unless unavoidable; if needed, proper Room migration + test):
| Evidence | Label | Kind for warnings |
| --- | --- | --- |
| Camera Yes **and** a bump within 0.15–6 s after the frame, within 40 m | "Pothole — camera + bump" / "Chuqur — kamera + silkinish" | confirmed |
| Camera Yes, no bump (driver avoided it) | "Pothole — camera" / "Chuqur — kamera" | unconfirmed (owner can confirm) |
| Bump, camera No or no frame | "Bump — unconfirmed" (as today) | unconfirmed |
- One physical pothole = one report: merge camera and bump evidence within 15 m in the same drive.
- New reports immediately feed the HAZARD-ALERT-001 native list, so the return trip warns.
- Optional cloud AI (key present) stays exactly as it is; on-device runs only when no key, or when
  the owner turns on "Use on-device detector" (default on when no key).

## 5. Improve the model from the owner's own roads (data loop)
- Every camera/sensor report detail gets **"Correct" / "Wrong"** buttons (Wrong ≠ delete: keeps
  the frame as a labelled negative). Extend the existing dataset ZIP export so the owner can export
  full frames + labels (Yes/No + model version + GPS-free metadata by default) to add to training.
  `ml/prepare_rdd2022.py` accepts an optional `--extra owner_export.zip`.
- Privacy: export is manual, local, and strips GPS unless the owner ticks "include location".

## 6. Small fix the owner asked for
- Drive "Share evidence" (video) currently has no location. Attach a **GPX of the drive's GPS
  track** and put start/end time + Google Maps links of start and end in the share text.
  Respect SEC-013/TRIP-002 track retention and the SEC-014 FileProvider paths (extend its test).

## 7. Tests (add and run)
- JVM: letterbox math keeps the whole frame (corners map inside the 416 canvas, aspect kept);
  YOLOX decode on a synthetic output tensor; NMS; threshold from JSON; 2-of-3 view rule;
  fusion table (all rows, time/distance boundaries); merge within 15 m; detector-absent path;
  SHA mismatch → disabled.
- JVM with real runtime: if `assets/ml/*.onnx` exists, run ONNX Runtime JVM on 3 fixture images
  and check shape/latency; skip cleanly (reported as skipped, not passed) when absent.
- Python: `ml/` VOC→COCO conversion on 3 tiny synthetic XML fixtures; exp-file full-frame settings.
- Browser (native-bridge mock): labels, Correct/Wrong, export, Settings detector status.
- All existing suites (full-frame, SEC-002/006/009/014, sensor_drive, hazard_alerts, trip stats,
  manual offline) must still pass.

## 8. Build, commit, report
- Same Windows build recipe; `:app:assembleDebug :app:testDebugUnitTest`. Report APK size
  before/after (ONNX Runtime adds MB — use ABI filters `arm64-v8a`, `armeabi-v7a` only if needed
  to keep it reasonable; do not touch release signing).
- Commit on `ondevice-ml`; owner authorises pushing **only** `ondevice-ml` for CI. No `main`.
  No model weights, datasets or APKs committed (add them to `.gitignore`).
- Update `PROJECT_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`, `PRODUCT_DECISIONS.md`,
  `SECURITY_STATUS.md` (new dependency), append `AGENT_WORKLOG.md` (ML-DETECT-001).
- Final report: files, test counts (incl. skipped), build result, APK SHA-256 and size, commits,
  CI status, and clearly: **model not trained yet / not field-validated / no accuracy claim**.
