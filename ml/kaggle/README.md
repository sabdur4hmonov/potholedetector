# TRAIN-001 unattended Kaggle training

The private kernel is `sardor007/pothole-yolox-train`. The first upload substitutes the pushed `train-001` commit into the single bootstrap script. The cloud runner uses pinned YOLOX and dependencies, scratch initialization, and complete frames. RDD2022 download/extraction stays under `/kaggle/tmp`. Only results, two small checkpoints, ONNX/JSON and logs are written to `/kaggle/working`.

`run_and_watch.ps1 -Register -Launch` registers `PotholeTrainWatch` for the current user every 15 minutes and launches the first run. The task uses an interactive logon token and runs with limited privileges. After reboot it catches up when this user signs in. `StartWhenAvailable` handles missed intervals. No password or power configuration is stored or changed. The cloud continues while the laptop sleeps.

Read `ml/TRAINING_REPORT.md` for current Uzbek/English status and timestamped changes. The durable state, upload staging and downloaded outputs are ignored by Git. No script reads or copies the Kaggle token. The official CLI uses the owner's configured access-token file.

At most two resumes are allowed. Requested kernel time is capped at 30 GPU-hours across all runs. Each run allows up to 12 hours, training stops by 10 h 15 min from its start, and the final run shortens training to leave evaluation/export time within the remaining budget. Validation precision must reach 0.80 and the export parity checks must pass before installation. A failed step becomes a permanent error and unregisters the task.

On success the watcher verifies the model digest and manifest, installs the assets and builds three debug APKs. Fresh JVM results must show the real ONNX fixture test ran and passed. The existing Windows symlink privilege failure is the sole allowed test failure. APK integrity, ABI, model digest, current web assets and signatures are checked. Install `app-arm64-v8a-debug.apk` for physical acceptance. Results and build details are under `ml/kaggle/output/run-N/`.

Test without GPU or downloads using `python ml/kaggle/train_kaggle.py --dry-run` and `python tests/kaggle_training_test.py`.
