# Codex task: TRAIN-001 — train the pothole model on Kaggle GPU, fully unattended

Owner: Sardorbek. Reviewer: Claude. The owner leaves the laptop on Wi-Fi + charger and **cannot
watch**. Training must run in the cloud (Kaggle free GPU), then come back, be checked, installed
into the app and built — without the owner. All `AGENTS.md` rules apply.

Why Kaggle: this laptop (i7-1065G7, no NVIDIA GPU) would need 1–2 days on CPU, and drive D: has
only ~6 GB free while RDD2022 needs ~30 GB unpacked. Do **not** download RDD2022 to this laptop.

## 0. Start
- `git status` clean; `git switch finish-001 && git pull --ff-only && git switch -c train-001`.
- Read `ml/README.md`, `ml/pins.json`, `MODEL_LICENSE.md`, `PROJECT_MASTER/ONDEVICE_ML.md`.

## 1. Kaggle access (owner prepares the token before leaving)
- The owner creates a Kaggle account, verifies the phone number (needed for GPU and internet),
  and on https://www.kaggle.com/settings/api clicks **Generate New Token**, saving the token to
  `%USERPROFILE%\.kaggle\access_token` (official kaggle-api "Option 3").
- Install the official `kaggle` CLI with pip, **one pinned version**, into the existing Python.
  Check with `kaggle kernels list --mine`. If auth fails, **stop** and write the exact Uzbek steps
  into `ml/TRAINING_REPORT.md` (no retries loop).
- Never print, log, commit or copy the token anywhere else. Kernel and any dataset you create stay **private**.

## 2. Kaggle job (`ml/kaggle/`)
- `kernel-metadata.json`: `kernel_type: "script"`, `is_private: "true"`, `enable_gpu: "true"`,
  `enable_internet: "true"`, `machine_shape: "NvidiaTeslaT4"`, id `<owner-username>/pothole-yolox-train`.
- `train_kaggle.py` (single script, no secrets):
  1. Print GPU info; fail fast if no CUDA.
  2. `git clone` the public repo `https://github.com/sabdur4hmonov/potholedetector` and check out
     the **exact pushed `train-001` commit hash** (pass it in the script, not a branch name).
  3. Install `ml/requirements-colab.txt` + pinned YOLOX commit (reuse the notebook's cells/logic;
     factor shared code into `ml/` modules rather than duplicating).
  4. Download RDD2022 to `/kaggle/tmp` (not `/kaggle/working`), compute SHA-256, extract **only**
     the needed country archives, delete the zip as soon as possible; run `ml/prepare_rdd2022.py`.
  5. Train with the existing full-frame exp (no mosaic/mixup/crop/translate). Init: **from scratch**
     (keep FINISH-001's rule: pretrained only if its licence is verified — it is not).
     Save a checkpoint every epoch to `/kaggle/working/ckpt/` (only `latest` + `best`, small).
     Wall-clock budget: stop training at **10 h 15 min** after start, then always run
     `ml/evaluate_export.py` (keeps the precision ≥ 0.80 gate) and write
     `/kaggle/working/result.json` (`status`, epochs, val/test precision, recall, F1, per-country
     recall, threshold, dataset SHA-256, model SHA-256, init, train commit). If the gate fails,
     still save metrics + checkpoint, but **no** `pothole_model.json`.
  6. Resume support: if a private Kaggle dataset `<owner>/pothole-yolox-ckpt` is attached
     (`dataset_sources`), resume from its `latest` checkpoint.

## 3. Unattended watcher on this laptop
- `ml/kaggle/run_and_watch.ps1` + a **Windows Scheduled Task** for the current user
  (`PotholeTrainWatch`, every 15 min, "run as soon as possible after a missed start", no admin,
  no stored passwords). It must survive Codex exiting and laptop sleep/reboot:
  - first run: `kaggle kernels push -p ml/kaggle --accelerator NvidiaTeslaT4`;
  - then poll `kaggle kernels status`; on complete → `kaggle kernels output -p` into
    `ml/kaggle/output/<version>/` (gitignored);
  - if `result.json` says the gate failed **and** fewer than 2 resumes were done → upload the
    checkpoint as a new version of the private dataset `pothole-yolox-ckpt`, attach it, push again
    (max 2 extra runs ≈ 30 GPU-hours total; never more);
  - on success → verify both files (SHA-256 in JSON matches the ONNX; `NativePotholeMath` config
    rules), copy to `android-app/android/app/src/main/assets/ml/`, run
    `tools/sync-web-assets.py`, `npx cap copy android`, the Windows Gradle recipe
    `:app:assembleDebug :app:testDebugUnitTest` (the ONNX runtime JVM test must now **run, not skip**),
    record split APK sizes + SHA-256;
  - on any failure → stop retrying that step, write the reason.
  - Always append a timestamped line to `ml/TRAINING_REPORT.md` (UZ + EN summary at the top:
    "Holat: ishlayapti / tayyor / xato") and finally unregister the scheduled task when done or
    permanently failed.
- Do not change power/sleep/lid settings. Kaggle keeps training while the laptop sleeps; the
  watcher catches up when it wakes.
- Keep disk use on D: small (outputs are only checkpoints, ONNX, JSON, logs).

## 4. Tests before launching
- Unit-test the watcher's pure logic in Python or Pester-free PowerShell (state machine: pushed →
  running → complete/failed → resume/finish; max-resume limit; gate-failed → no install;
  SHA mismatch → no install). Static contract: no token strings, kernel private, GPU+internet on,
  full-frame exp unchanged (`tests/full_frame_invariant_test.py` still passes).
- Dry-run `train_kaggle.py --dry-run` locally on the three tiny VOC fixtures (no GPU, no download)
  to prove the pipeline wiring before spending GPU hours.

## 5. Commit, launch, report
- Commit code/docs on `train-001` (no token, weights, datasets, outputs, APKs), push **only**
  `train-001` (owner authorised), then launch the first Kaggle run and register the task.
- Update `PROJECT_STATUS.md`, `NEXT_STEPS.md`, `CHANGELOG.md`, append `AGENT_WORKLOG.md` (TRAIN-001).
- Report: Kaggle kernel URL, commit hashes, scheduled task name, where to read progress
  (`ml/TRAINING_REPORT.md`), and that results are pending. Never claim accuracy before
  `result.json` exists; never claim phone/road validation.
