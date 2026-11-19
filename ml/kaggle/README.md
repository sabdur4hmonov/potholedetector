# TRAIN-001 unattended Kaggle training

The private kernel is `sardor007/pothole-yolox-train`. The first upload substitutes the pushed `train-001` commit into the single bootstrap script. The cloud runner uses pinned YOLOX and dependencies, scratch initialization, and complete frames. RDD2022 download/extraction stays under `/kaggle/tmp`. Only results, two small checkpoints, ONNX/JSON and logs are written to `/kaggle/working`.

`run_and_watch.ps1 -Register -Launch` registers `PotholeTrainWatch` for the current user every 15 minutes and launches a private smoke version. Kaggle uses an isolated Python 3.12 environment with the existing package pins. Smoke runs the real dataset preparation, one epoch on 128 complete training frames and ONNX parity on 20 held-out frames. Its kernel limit is 44 minutes. A verified smoke result starts full training automatically. The task runs with limited privileges when the current user is signed in. `StartWhenAvailable` handles missed intervals. The cloud continues while the laptop sleeps.

Read `ml/TRAINING_REPORT.md` for current Uzbek/English status and timestamped changes. The durable state, upload staging and downloaded outputs are ignored by Git. No script reads or copies the Kaggle token. The official CLI uses the owner's configured access-token file.

At most two checkpoint resumes are allowed. Requested kernel time is capped at 30 GPU-hours. Full runs allow up to 12 hours, and training stops by 10 h 15 min from the start or earlier to reserve evaluation time. Validation precision must reach 0.80 and export parity must pass before installation. Failed or cancelled versions preserve output, reason and the last 40 log lines. The watcher can relaunch once for a confirmed transient failure. Permanent failures unregister the task.

On success the watcher verifies the model digest and manifest, installs the assets and builds three debug APKs. Fresh JVM results must show the real ONNX fixture test ran and passed. The existing Windows symlink privilege failure is the sole allowed test failure. APK integrity, ABI, model digest, current web assets and signatures are checked. Install `app-arm64-v8a-debug.apk` for physical acceptance. Results and build details are under `ml/kaggle/output/version-N/`.

Test without GPU or downloads using `python ml/kaggle/train_kaggle.py --dry-run` and `python tests/kaggle_training_test.py`.
