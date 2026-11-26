# TRAIN-001 unattended Kaggle training

The private kernel is `sardor007/pothole-yolox-train`. The first upload substitutes the pushed `train-001` commit into the single bootstrap script. The cloud runner uses pinned YOLOX and dependencies, scratch initialization, and complete frames. It downloads the public RDD2022 archive through the Figshare API under `/kaggle/tmp`, with one alternate official URL on HTTP 403, and checks the pinned SHA-256 before extraction. Only results, two small checkpoints, ONNX/JSON and logs are written to `/kaggle/working`.

`run_and_watch.ps1 -Register -Launch` registers `PotholeTrainWatch` for the current user every 15 minutes and launches a private smoke version. Kaggle uses an isolated Python 3.12 environment with the existing package pins. Smoke runs one real balanced training epoch, full COCO validation and 20 held-out ONNX comparisons. Its kernel limit is 44 minutes. A verified smoke result sizes and starts full training automatically. The task runs with limited privileges when the current user is signed in. `StartWhenAvailable` handles missed intervals. The cloud continues while the laptop sleeps.

Read `ml/TRAINING_REPORT.md` for current Uzbek/English status and timestamped changes. The durable state, upload staging and downloaded outputs are ignored by Git. No script reads or copies the Kaggle token. The official CLI uses the owner's configured access-token file.

TRAIN-003 uses the SHA-pinned Megvii COCO checkpoint, a fresh one-class head and balanced full-frame batches. Smoke times setup, one full training epoch and COCO validation. The watcher adds timing margin and sizes the cosine schedule for one approximately nine-hour training run. A recoverable crash with a verified pretrained checkpoint can resume once at the original target. Kaggle quota refusals leave the task waiting until the reported reset or the next daily quota check.

Threshold selection maximizes validation frame recall subject to precision of at least .80. Installation additionally requires validation recall of at least .40, test precision of at least .75 and test recall of at least .35, plus valid export parity. Failed or cancelled versions preserve output, reason and the last 40 log lines. Terminal failures unregister the task.

On success the watcher verifies the model digest and manifest, installs the assets and builds three debug APKs. Fresh JVM results must show the real ONNX fixture test ran and passed. The existing Windows symlink privilege failure is the sole allowed test failure. APK integrity, ABI, model digest, current web assets and signatures are checked. Install `app-arm64-v8a-debug.apk` for physical acceptance. Results and build details are under `ml/kaggle/output/version-N/`.

Test without GPU or downloads using `python ml/kaggle/train_kaggle.py --dry-run` and `python tests/kaggle_training_test.py`.
