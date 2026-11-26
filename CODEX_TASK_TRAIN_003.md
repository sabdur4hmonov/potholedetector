# Codex task: TRAIN-003 — fix the gate, stop the weak run, retrain from official pretrained weights

Reviewer (Claude) findings from `ml/kaggle/output/version-7/`:
- v7 (111 epochs, scratch) is **not usable**: val box recall **0.6 %** (4 / 646), test 0.45 %.
  YOLOX's own COCO eval in the log shows AP50 ≈ **0.18** on val.
- The gate **wrongly passed** it: threshold selection pushed the threshold up until precision hit
  exactly 0.80 (4 TP / 1 FP). A precision-only gate can be satisfied by a model that finds nothing.
- The watcher copied this model into `android-app/android/app/src/main/assets/ml/` (gitignored);
  only a separate failure (`powershell.exe command failed with exit 1` in the APK step) stopped it
  from shipping.
- v8 (scratch resume to epoch 204) is running and is unlikely to become good; it is burning the
  limited weekly free GPU quota (state shows ≈ 15 GPU-hours already used).
- Data balance: 28 782 train images but only ~4 300 contain potholes (≈ 82 % negatives).

**Owner decision (record verbatim in `PRODUCT_DECISIONS.md` and `MODEL_LICENSE.md`):** use
Megvii's official COCO-pretrained `yolox_nano.pth` (release `0.1.1rc0`, SHA-256
`cd28f55fbbc1829f99d9ac9b38a16d259a22889739c8728ea877610201feff7b`) as initialisation. The YOLOX
repository is Apache-2.0 and its README links these weights; no separate weight licence is stated,
and the owner accepts treating them as Apache-2.0. Keep this caveat in `MODEL_LICENSE.md`.

All `AGENTS.md` rules apply (full-frame invariant: no mosaic/mixup/crop/translate). Branch `train-001`.

**Update 2026-11-26 (reviewer):** this task was not started earlier. Meanwhile v8 finished
(epoch 204, val box recall 0.46 %, worse than v7) and the watcher stopped with `phase: failed`.
So: v8 does **not** need stopping; the weekly Kaggle GPU quota has most likely reset since
2026-11-20 (confirm from a push response, don't assume). The v7 model files are **still** in
`assets/ml/` — quarantine them first. `git status` shows `android-app/www/index.html` and
`docs/index.html` modified, but `git diff --ignore-cr-at-eol` is empty (line-ending churn only):
restore them with `git checkout -- <file>` after confirming that, and find/fix what rewrote them
(likely the sync step with CRLF) so it does not recur. Keep the `ml/TRAINING_REPORT.md` changes.

## 1. Make it safe right now (before anything else)
- Disable `PotholeTrainWatch` while you work (re-enable at the end).
- **Quarantine** the v7 model: move both files out of `assets/ml/` into
  `ml/kaggle/output/version-7/quarantined/` (move, don't delete). Assets must be empty → app = sensor mode.
- Stop Kaggle v8. If the CLI has no reliable cancel, write exact Uzbek click steps for the owner in
  `TRAINING_REPORT.md` (Kaggle → Your Work → pothole-yolox-train → running version → Stop) and in your reply.
  Don't push a new version until v8 is confirmed stopped.

## 2. Fix the gate (the app answers Yes/No per frame)
- In `ml/evaluate_export.py` add **frame-level** metrics: a frame is positive if it has ≥ 1 GT
  pothole box; predicted positive if ≥ 1 detection ≥ threshold. Keep box-level P/R@IoU 0.5 and
  the YOLOX COCO AP50 as extra reported numbers.
- Choose the threshold on **val** = the one with the highest frame recall subject to frame
  precision ≥ 0.80. **Gate (all required):** val frame precision ≥ 0.80 **and** val frame recall
  ≥ 0.40; on **test** at the same threshold: precision ≥ 0.75 and recall ≥ 0.35. Otherwise no
  `pothole_model.json`, no install.
- Unit tests: the v7 pattern (4 TP / 1 FP / 642 FN) must **fail**; synthetic good/bad cases;
  threshold-selection edge cases (no threshold reaches precision → fail).
- The watcher must use only this gate and never install a model whose `result.json` lacks the
  new frame-level fields.

## 3. Better training recipe
- Init from the pinned pretrained weights (verify SHA-256; fail closed). Load with `strict=False`,
  fresh 1-class head; log which tensors were loaded/skipped. `result.json` records `init` + weight SHA.
- **Negative sampling per epoch:** all positive train images + an equal number of negatives drawn
  each epoch with a fixed seed, ~half from images with other damage classes (hard negatives:
  cracks), half from clean images. Val/test stay complete and untouched.
- Input stays **416** (app contract). Measure epoch time in the smoke run and set `max_epoch` so
  the full schedule (warm-up + cosine to min LR) **finishes within one run** of ≈ 9 h training.
  No resume planned; keep resume only for crashes.
- Keep eval every 5 epochs; save `best` by YOLOX AP50 and evaluate the gate on `best`.

## 4. Fix the APK step
- Reproduce `powershell.exe command failed with exit 1` locally: run the watcher's build step on
  a scratch copy with the quarantined v7 files, capture the full error into the report, fix the
  root cause, prove the build + real ONNX JVM test pass, then remove the files from `assets/ml/` again.

## 5. Quota-aware launch
- Estimate remaining weekly GPU hours from your recorded runs (and Kaggle's message if a push is
  refused). If a run is refused for quota, the watcher waits and retries after the weekly reset
  instead of marking failure. Smoke run (< 45 min) first, then the full run automatically.

## 6. Finish
- Tests + dry-run, commit and push only `train-001`, re-enable the task, update
  `TRAINING_REPORT.md` (UZ + EN: "v7 yaroqsiz, karantinda; yangi o'qitish ...") and append
  `AGENT_WORKLOG.md` (TRAIN-003).
- Report: v8 stopped (how), quarantine done, gate tests, APK-step root cause + fix, smoke epoch
  time, planned `max_epoch`, full-run URL. No accuracy claims until the new `result.json` exists.
