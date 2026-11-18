# Codex task: FINISH-001 — make ML training realistic, shrink the APK, prepare merge

Owner: Sardorbek. Reviewer: Claude (independently rebuilt `ondevice-ml` @ `8df2e5d`: build OK,
JVM 42 pass / 1 skipped (no model yet), ML/sensor/hazard/full-frame contracts and browser tests pass).
Three small, scoped fixes. All `AGENTS.md` rules apply. Work on a new branch from `ondevice-ml`:
`git switch ondevice-ml && git pull --ff-only && git switch -c finish-001`.

## 1. Start training from official pretrained weights (accuracy)
Problem: the notebook trains YOLOX-Nano **from scratch**. With a few thousand pothole boxes on a
free Colab GPU this is very likely to miss the notebook's own precision ≥ 0.80 export gate.
- Add an **optional, default-on** initialisation from Megvii's official `yolox_nano.pth`
  (COCO-pretrained) from the YOLOX GitHub release that matches the pinned commit.
  Before relying on it, confirm and record in `ml/pins.json` + `MODEL_LICENSE.md`: the exact
  release URL, its SHA-256 (verify after download; fail closed on mismatch), and the license
  under which Megvii publishes the weights. If the license is not clearly permissive
  (Apache-2.0/MIT/BSD), keep from-scratch as default and say so in the report instead.
- Load with `strict=False`, re-initialise the 1-class head, keep all full-frame settings
  (no mosaic/mixup/crop/translate). Freeze nothing by default.
- Notebook prints which init was used; `pothole_model.json` records `init` and weight SHA-256.
  Native `NativePotholeMath.config` must accept the new optional field without weakening checks.
- Update `ml/README.md` (UZ + EN) and `tests/ondevice_ml_contract_test.py` / `ml_prepare_test.py`.

## 2. Phone-sized APK (57.9 MB → ABI split)
The debug APK carries ONNX Runtime for 4 ABIs (~106 MB of `.so` uncompressed).
- Enable Gradle `splits.abi` for `arm64-v8a`, `armeabi-v7a`, `x86_64` (drop 32-bit `x86`),
  `universalApk false`. Keep `x86_64` working for the CI emulator smoke job (update the CI
  workflow/`tools/emulator-smoke.sh` to pick the x86_64 split APK).
- Make sure `tools/verify-release-assets.py` and any APK-path assumptions in tests/tools still work.
  Do not touch release signing or NEW-002 files beyond what the APK path change strictly needs.
- Report every split APK's size + SHA-256. The owner installs **`app-arm64-v8a-debug.apk`**
  (say so in `ml/README.md` and the worklog).

## 3. Prepare (do not perform) the merge to `main`
- Rebase is forbidden. Open a **draft pull request** `finish-001 → main` with `gh pr create --draft`
  summarising SENSOR-DRIVE-001, HAZARD-ALERT-001, ML-DETECT-001, FINISH-001, the test evidence,
  and an explicit "not verified on a physical phone / model not trained" section.
  Owner authorises pushing **only** `finish-001` and creating that draft PR. **Do not merge.**

## Tests, build, report
- Run the affected Python/Node suites, `:app:assembleDebug :app:testDebugUnitTest` (Windows
  recipe; the known symlink-privilege failure may remain), and confirm CI is green on `finish-001`.
- Update `PROJECT_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`, append `AGENT_WORKLOG.md` (FINISH-001).
- Final report: files, test counts, split APK sizes + SHA-256, commit hashes, CI link, PR link,
  and what remains unverified. No device/accuracy claims.
