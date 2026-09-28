# Repository instructions

## Full-frame pothole-detection invariant

- Every pothole-detection input must preserve the complete camera frame from edge to edge.
- Never spatially crop, tile, mask, extract a road band, or substitute a region of interest for the full frame in live detection, saved-frame replay, evaluation, training-data preparation, or exported evidence.
- Whole-frame orientation correction, downscaling, compression, and whole-frame low-light enhancement are allowed only when they are applied to the entire image and preserve the original field of view.
- Every temporal view must independently be a complete frame. A separate lower-road or candidate crop must never be added as model evidence.
- Tests must fail if a pothole-detection crop path or crop-specific prompt language is introduced again.

## Instructions for coding agents (Codex, Claude Code, and others)

Before you change anything:

1. Read `PROJECT_MASTER/README.md`, then `PROJECT_MASTER/PROJECT_STATUS.md`,
   `PROJECT_MASTER/SECURITY_STATUS.md` and `PROJECT_MASTER/NEXT_STEPS.md`.
2. Read the latest entries in `PROJECT_MASTER/AGENT_WORKLOG.md`. That file is the
   chronological cross-agent history and is the fastest way to pick up the current state.
3. Detailed per-finding evidence lives in `PROJECT_MASTER/SECURITY_REMEDIATION_*.md`,
   the root-level `SECURITY_REMEDIATION_SEC007..SEC011.md`, and `outputs/`.

While you work:

- **Preserve existing remediation.** SEC-001 through SEC-016 and NEW-001/NEW-002 are done or
  dispositioned. Do not re-audit, rewrite or undo them. There is no SEC-017; do not invent one.
- **Work on one scoped task at a time** and do not start the next finding or task unasked.
- **Never run destructive Git commands**: no `git reset --hard`, no `git clean -fd`/`-fdx`, no
  force checkout, no force push, no history rewrite. Uncommitted work in this tree has been
  weeks of effort.
- **No broad dependency, AGP or Gradle-wrapper upgrades** unless the task proves one necessary.
- **Do not repeatedly retry the known blockers**: the Windows/Gradle transformed-JAR
  `AccessDeniedException` and the missing Android device. They are recorded; note them and
  move on.
- **Prefer deterministic static and unit checks** over builds, devices, network calls or paid
  services. Run the relevant existing tests in `tests/`.
- **Make the smallest safe change**, or none if none is justified. Do not manufacture a fix.
- **Report honestly.** Never claim runtime, build or device verification you did not perform.

When you finish:

- Update the authoritative documents when the state actually changed: `PROJECT_STATUS.md`,
  `SECURITY_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`.
- Append one entry to `PROJECT_MASTER/AGENT_WORKLOG.md` covering date/time, agent, task,
  status, files changed, tests performed, decisions, remaining blockers, the **exact next
  task**, and the commit hash if you committed. Never delete or rewrite earlier entries.
- **Never write secrets** — API keys, tokens, passwords, private keys, keystore credentials —
  into documentation, logs, tests or commits.
- **Never commit or push unless the user explicitly authorizes it in that request.**
