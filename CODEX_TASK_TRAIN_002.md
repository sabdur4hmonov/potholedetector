# Codex task: TRAIN-002 — fix the learning-rate schedule before full run v7 ends

Reviewer (Claude) checked `ml/kaggle/output/version-7/reconnected-kernel.log`. Training is healthy
(iter_time ≈ 0.17–0.20 s, 1 799 iters/epoch ⇒ **≈ 5.4 min per epoch**), but the schedule is wrong:
- `cloud_run.py` sets `POTHOLE_EPOCHS='500'`, so the YOLOX warm-cos LR schedule is built for 500 epochs.
- The 10 h 15 min budget fits only **≈ 100–110 epochs**. Training stops at ~20 % of the cosine
  curve, with the learning rate still ≈ 0.9 × max. The final model never gets the low-LR phase,
  so it will be under-converged and will very likely fail the precision ≥ 0.80 gate.
- The watcher's resumes would continue the same 500-epoch schedule (≈ 330 epochs after 3 runs,
  still not annealed) and need ≈ 33 GPU-hours, more than Kaggle's weekly free GPU allowance.

**Do not cancel v7.** Its epochs are useful. Make this change **before v7 finishes (started
≈ 01:28 +05:00, budget ends ≈ 11:45 +05:00 on 2026-11-20)**; the watcher must use the new logic
when v7 completes. All `AGENTS.md` and TRAIN-001 constraints still apply; stay on `train-001`.

1. **Measure, don't guess.** From the v7 log compute median epoch time and validation time
   (eval every 5 epochs). Derive `E_run` = whole epochs that fit in the resume run's training
   budget (same 10 h 15 min minus setup, download/extract and export margin). Record the numbers.
2. **Exactly one resume that finishes the schedule.** When v7 ends, resume from its `latest`
   checkpoint with `POTHOLE_EPOCHS = start_epoch_of_resume + E_run`, so the cosine schedule
   reaches its minimum LR at the end of run 2. Pass the target epoch from the watcher to the
   Kaggle job (state file / dataset metadata), not by editing code each time. Confirm in code that
   YOLOX resume rebuilds the LR scheduler from the new `max_epoch` (if it restores the old total
   iterations instead, override it explicitly and add a test).
3. Always evaluate + run the gate after **each** run. If v7 alone already passes, install it
   (APK build as designed), then still run the single resume and replace the model only if the
   final run's val F1 is higher at precision ≥ 0.80.
4. **Remove the second extra resume** (max total = v7 + 1 resume). If the final run still fails the
   gate, stop, keep the checkpoint/metrics, and write in `TRAINING_REPORT.md` (UZ + EN) that the
   next lever is the owner's decision on the official pretrained YOLOX-Nano weights.
5. Future fresh runs (not v7): set `POTHOLE_EPOCHS` from the measured budget (≈ 2 × `E_run`
   spread over two runs), never a fixed 500.
6. Unit-test the epoch arithmetic and the new watcher transitions (v7 pass/fail × resume
   pass/fail, no third run). Run local tests + dry-run, commit and push only `train-001`, verify
   `PotholeTrainWatch` still runs, update `TRAINING_REPORT.md`, append `AGENT_WORKLOG.md`.
7. Report the measured epoch/eval times, `E_run`, the planned final epoch, commits, and confirm
   v7 was **not** interrupted.
