# Project master control center

This is the permanent local documentation and command center for the existing `coding-parrot/pothole-reporter` working tree. The project is being adapted for Uzbekistan; the inherited application and reference data still implement India-specific coverage. A free-to-user design without required paid AI is the agreed direction, not an implemented replacement detector/backend.

The real source stays in its normal directories. Nothing was moved, consolidated, rebuilt, or regenerated to create this center. Existing source and security remediation reports remain authoritative. This directory summarizes them as of 2026-09-14; it is not another security audit.

| Start here | Purpose |
| --- | --- |
| [MASTER_EXECUTION_PLAN.md](MASTER_EXECUTION_PLAN.md) | Primary task registry, current active task, phase dependencies and Codex continuation protocol |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current state, blockers, milestone |
| [SECURITY_STATUS.md](SECURITY_STATUS.md) | SEC-001–SEC-016 and NEW-001/NEW-002 |
| [SETUP_WINDOWS.md](SETUP_WINDOWS.md) | Actual Windows toolchain and setup |
| [COMMANDS.md](COMMANDS.md) | Copyable PowerShell commands |
| [RUN_PROJECT.ps1](RUN_PROJECT.ps1) | Prints commands; performs no project actions |
| [FILE_INDEX.md](FILE_INDEX.md) | Existing files and functionality |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Current layers, data and trust boundaries |
| [CHANGELOG.md](CHANGELOG.md) | Recorded SEC-001–SEC-007 work |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Ordered remaining work; not executed |

Main entry points are [Android/native source](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/), [web logic](../static/standalone.js), [Android web assets](../android-app/www/), [hosted pages and packs](../docs/), [tests](../tests/), [tools](../tools/), [data](../data/), and [GitHub automation](../.github/). See the file index before editing.

Actual repository root:

```text
C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter
```

Enter that directory and run the command guide:

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter'
& .\PROJECT_MASTER\RUN_PROJECT.ps1 -Mode Help
```

The helper prints instructions only. Follow the existing PowerShell execution policy; no bypass is included. Browser preview is a UI/data-development aid: native bridges and cloud detection are unavailable there. The current Android cloud detector still needs user-provided credentials for inference; none are provided, and paid calls are outside the authorized work.

The upstream [README](../README.md) describes the inherited release. For current restrictions—especially disabled dashcam, protected credential storage, bounded inference, and browser paid-inference refusal—use this center and the remediation reports. Existing release binaries do not prove deployment of the uncommitted fixes.
