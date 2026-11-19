# Codex task: TRAIN-001-FIX — the first Kaggle run failed; diagnose, fix, relaunch

Reviewer (Claude) found: `ml/TRAINING_REPORT.md` → "Holat: xato", `.state/state.json` →
`RuntimeError: Kaggle run ended with status error` at 23:40, ~14 min after launch.
The watcher did not download the failed run's log or `result.json`, so the cause is unknown.
All `AGENTS.md` rules and the TRAIN-001 constraints still apply. Stay on branch `train-001`.

1. **Get the evidence first.** `kaggle kernels output sardor007/pothole-yolox-train -p ml/kaggle/output/run1-failed`
   (gitignored). Read `result.json` (`reason`) and the kernel log. Quote the exact failing step and
   the last ~40 log lines (redact nothing secret should be there; never print the token).
2. **Fix the root cause only** (e.g. dependency install, figshare download, disk path, SHA pin
   handling, YOLOX build). No guessing: the fix must match the logged error. If the error is a
   Kaggle quota/verification/account problem, stop and write the owner's exact steps in Uzbek.
3. **Fix the watcher:** on *any* failed/cancelled run it must download the output and log into
   `ml/kaggle/output/<run>/`, copy `reason` + last 40 log lines into `ml/TRAINING_REPORT.md`, and
   allow **one** automatic relaunch only when the failure is clearly transient (HTTP/network/
   download timeout, Kaggle infrastructure error). Code errors → stop, no relaunch. Add unit
   tests for this classification.
4. **Cheaper smoke run before the long one:** add a `--smoke` mode (download + extract + prepare
   + 1 short epoch + export on a small subset, < 45 min) and run it on Kaggle first. Only when the
   smoke run completes successfully, launch the full 10 h run automatically from the watcher.
5. Re-run local tests + dry-run, commit and push only `train-001`, re-register `PotholeTrainWatch`
   if it was unregistered, relaunch, and update `TRAINING_REPORT.md` + append `AGENT_WORKLOG.md`.
6. Report: the logged root cause, the fix, smoke-run result, full-run kernel version URL, commits.
   Do not claim the run is healthy until the log shows training epochs progressing.
