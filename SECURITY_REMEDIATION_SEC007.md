# SEC-007 — GitHub Actions catalog refresh security

STATUS: RESOLVED

Verified locally on 2026-09-14. This status covers the workflow security changes and the requested source/static validation. It does not claim a live GitHub Actions run, successful live source refresh, or authenticated branch publication.

## Affected workflow and root cause

The continuation notes name `.github/workflows/refresh-catalog.yml`. That file does not exist in this working tree. The affected tracked workflow is `.github/workflows/refresh-public-road-catalogs.yml`, named **Refresh public road catalogs**. It was hardened in place without renaming it.

Originally, workflow-level `contents: write` and `pull-requests: write` permissions covered a single job that installed dependencies, launched a browser against remote pages, fetched public source data, ran parsers/builders, validated outputs, committed changes, pushed an automation branch, and opened a PR. Checkout explicitly retained authentication with `persist-credentials: true`. Playwright used the mutable range `>=1.40,<2`, Python used the floating minor version `3.12`, and browser installation included mutable privileged OS dependency installation with `--with-deps` on `ubuntu-latest`.

The root cause was combining remote-data/dependency processing with authenticated publication on the same runner and token scope. A compromised dependency, browser, or parser could reach repository write authority before the final catalog-only path check. That check restricted intended output paths but did not isolate credentials or the runner. The workflow had no PR preflight. Inspection did not establish direct attacker-controlled PR interpolation into its original shell commands.

## Exact hardening changes

- Set workflow permissions to `{}` and grant explicit permissions per job.
- Add an offline `pull_request` preflight with only `contents: read`, no secrets, no browser/dependency install, and no publication.
- Restrict refresh and publication to `refs/heads/main` and the existing `schedule` / `workflow_dispatch` events. There are no dispatch inputs, `pull_request_target`, `workflow_run`, or privileged cross-run follow-up workflows.
- Keep refresh/build/schema validation in a job with only `contents: read`. Move publication to a dependent job on a fresh GitHub-hosted runner with a clean checkout of the same immutable workflow commit.
- Set all three checkout steps to `persist-credentials: false`.
- Keep full Git history and tags in the refresh checkout: the existing pruner refuses shallow history and protects packs referenced by released `v1.*` manifests. PR and publication checkouts do not need full history.
- Preserve the twice-weekly cron `17 2 * * 1,4`, manual invocation, UTC retrieval timestamp, all original public-source commands/options, all original pack/schema/pruner checks, bot author, unique automation branch convention, and review PR against `main`.
- Keep manual/scheduled refreshes serialized while giving each PR a separate concurrency group.
- Pin Python to `3.12.12` and the runner OS family to `ubuntu-24.04`.
- Add a workflow-only four-package wheel lock with exact versions and SHA-256 hashes. Keep the general `requirements.txt`, npm dependencies, Android dependencies, and application files unchanged.
- Install only the pinned Chromium headless shell using Playwright's fixed revision; omit mutable privileged OS package installation. Add a headless launch smoke check before any live source requests so missing runner libraries fail visibly.
- Replace the final shell path-list check and whole-tree staging with a bounded, data-only transfer helper that validates independently on both runners.
- Bind the artifact name and manifest provenance to this repository, source SHA, workflow run ID, and attempt. Download from the current run only, outside the publication checkout.
- Combine local commit, narrowly authenticated push, and PR creation in one final publication step. Disable Git hooks for staging, branch switching, commit, and push. No artifact content is executed.

## Permissions and credential model

| Context | Explicit permissions | Content executed | Publication |
| --- | --- | --- | --- |
| Workflow default | None (`{}`) | No default token authority | None |
| PR `preflight` | `contents: read` | PR merge checkout, existing offline tests, SEC-007 tests | None |
| Main `refresh` | `contents: read` | Trusted workflow commit, locked dependencies, browser, public source parsing/building/checks | Upload data artifact only |
| Main `publish` | `contents: write`, `pull-requests: write` | SHA-pinned actions, trusted transfer helper, Git and GitHub CLI | Unique automation branch and review PR |

GitHub permissions are job-scoped. The publication job's token authority exists throughout that job; exposing `GH_TOKEN` only in the final step is not a claim of step-scoped permissions. Its earlier steps run only trusted actions and trusted transfer code, without installing Playwright, running the crawlers/builders, checking out a PR, or executing transferred content. No production credentials, personal access tokens, GitHub App credentials, paid API services, or new secrets were introduced. [GitHub's token documentation](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token) describes action access to the token and permission control.

Checkout never retains a token in Git configuration. The final push receives an HTTP authorization header through process-local `GIT_CONFIG_*` environment variables. The transformed Basic-auth value is masked, never added to the remote URL or persistent Git configuration, and unset afterward. `GH_TOKEN` is scoped in YAML to the final step. The workflow does not force-push, push directly to `main`, merge a PR, or request administrative token permissions.

## Data boundary, validation, and provenance

The transfer artifact contains a small JSON manifest and flat regular blobs named by their SHA-256 digests. It is not an archive, patch, executable checkout, or Git configuration bundle supplied to the publication helper. The upload/download actions are immutable SHA pins, and the download goes into the runner temporary directory.

The trusted publication helper validates:

- Exact transfer format, unique JSON keys, exact allowed manifest/entry fields, and nonempty entry count.
- Source SHA against the publisher's `HEAD`, plus repository/run/attempt identity against GitHub-provided environment values. Publisher identity does not come from a producer-supplied SHA output.
- The existing catalog root allowlist, restricted further to expected manifest paths and `.json` / `.json.gz` catalog files. Absolute paths, traversal, hidden path components, backslashes, control characters, and option-like components are rejected.
- Existing parent directories and destination/source file types. Symlinks, special files, directories used as blobs, and hard-linked files are rejected. Generated files are staged as regular non-executable data.
- Per-blob length and SHA-256; total logical data size; no extra artifact files; duplicate output paths; and valid deletions of existing regular files.
- Clean publisher checkout before application, exact changed-path set afterward, safe staged file modes, and the original Git whitespace check.

Limits are 16 MiB manifest, 128 MiB per catalog file, 1 GiB cumulative logical file bytes, and 100,000 changes; hashing streams in 64 KiB blocks. All artifact input is checked before the first destination write. Git operations use argument arrays and literal pathspecs. No source-controlled filename is interpreted as a shell command. The publication job is disposable if a later filesystem/staging operation fails.

Original source receipts, retrieval times, record-count semantics, schema checks, content-addressed pack algorithms, and release-tag retention remain unchanged. The review PR now records the source commit and workflow run/attempt. Version/hash pins improve tool reproducibility; live upstream feeds and retrieval times naturally change between refreshes. Hashes/provenance bind transferred bytes to this run; they do not prove the truth of upstream data or attest that a compromised producer ran its advertised validators.

## Actions, Python, and browser pins

| Action | Immutable commit | Version comment |
| --- | --- | --- |
| `actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683` | v4.2.2; retained existing pin |
| `actions/setup-python` | `42375524e23c412d93fb67b49958b491fce71c38` | v5.4.0; retained existing pin |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | v4.6.2 |
| `actions/download-artifact` | `d3f86a106a0bac45b974a628896c90dbdf5c8093` | v4.3.0 |

The new action commits were checked against their official GitHub release/tag metadata: [upload-artifact](https://github.com/actions/upload-artifact/releases/tag/v4.6.2), [download-artifact](https://github.com/actions/download-artifact/releases/tag/v4.3.0).

The workflow lock contains `playwright==1.58.0`, `pyee==13.0.1`, `greenlet==3.3.1`, and `typing_extensions==4.15.0`. Each hash was obtained from official PyPI release JSON and validated by downloading/resolving the CPython 3.12 / Linux x86_64 wheels with pip's `--require-hashes --only-binary=:all:`. Source distribution builds and unconstrained transitive installs are excluded. Official metadata: [Playwright](https://pypi.org/pypi/playwright/1.58.0/json), [pyee](https://pypi.org/pypi/pyee/13.0.1/json), [greenlet](https://pypi.org/pypi/greenlet/3.3.1/json), [typing_extensions](https://pypi.org/pypi/typing_extensions/4.15.0/json).

The hash-verified Playwright wheel's own `browsers.json` was inspected: Chromium headless shell is `145.0.7632.6`, revision `1208`. `--only-shell` preserves the existing crawler's `headless=True` launch behavior. [Playwright documents this installation mode](https://playwright.dev/python/docs/browsers#chromium-headless-shell). There is no floating browser channel or fallback to a system browser. Browser archives still rely on the vendor's fixed revision/CDN over TLS; an independent browser archive hash is not pinned.

## Trigger and shell review

PR events can execute only `preflight`. Main-branch schedule/manual events can execute `refresh`; `publish` additionally requires successful refresh and `changed == 'true'`. Feature-branch manual dispatch, PR/PR-target, push, and workflow-run contexts cannot enter the publication job in this workflow. Failed/cancelled/skipped/no-change refreshes do not publish.

No GitHub expression is interpolated into any `run` block. All run blocks retain `set -euo pipefail`. Retrieval timestamps, filesystem paths, branch names, repository names, and PR arguments are quoted. Branch names use validated numeric `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT`, not PR titles/branch inputs. Transfer paths pass through a strict allowlist and argument-array Git calls.

Workflow authority on `main` is the trust boundary. This change cannot prevent a repository administrator or trusted maintainer from changing/merging a different privileged workflow. Repository rules should protect main and review workflow changes; their configuration was not accessed or modified. No new environment approval requirement was added that would break the existing unattended refresh schedule.

Current GitHub documentation says PRs created/updated with `GITHUB_TOKEN` can create approval-required PR workflow runs; a user with write access approves them. Repository policy may also restrict PR creation or fork workflow execution. No broader credential was added to bypass those controls. [GitHub's current triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) support this limitation.

## Validation passed

- actionlint 1.7.12 accepted the final workflow YAML, action inputs, contexts, permissions, dependencies, and expression syntax. The local validation binary was downloaded from its official release and verified against the published asset SHA-256.
- PyYAML 6.0.3 parsed the complete workflow with duplicate-key rejection and exact trigger/job/permission assertions.
- 32 evaluated trigger/job cases passed, including PR contexts, feature-branch dispatch, trusted main schedule/dispatch, and failed/cancelled/skipped/no-change producer results.
- All nine shell blocks passed `bash -n`; neither direct expression interpolation nor unsafe publication inputs were found during the changed-line review.
- Both new Python files passed AST syntax checks.
- All 24 SEC-007 unittest cases passed: seven workflow contracts and 17 transfer tests. Tests cover successful add/modify/delete/staging, empty refresh, output allowlist, hostile path variants, foreign provenance, wrong checkout, tampered hash, extra files, duplicate keys/entries, unsafe fields, invalid sizes, byte/count limits, blob file types, and mocked symlink modes. The final seven workflow contracts were rerun after retaining full refresh history/tags and passed.
- The complete workflow diff and both new code files were reviewed. A direct comparison confirmed the entire original source-refresh and pack-build/verification block is unchanged.
- Locked Linux wheel resolution/download passed for all four packages with hashes enforced. Browser revision/version and dependency metadata were inspected inside the verified Playwright wheel.
- Sixteen existing offline commands passed: 75 unittest cases across source/parser/pack-builder suites, plus the separate tender-scope check with 11 road and 40 non-road fixtures. Five of nine existing pruner test cases also passed; that suite's four host errors are recorded below.
- Workflow `git diff --check` passed. New text files were checked for whitespace issues.
- A before/after SHA-256 inventory verified all 886 pre-existing files outside the affected workflow remain byte-identical, including prior tracked and untracked SEC-001 through SEC-006 work. Project HEAD remains `f282454e8fb79a529894598b0af9a3d7008fd84c`; no project index entries were staged.

## Validation failed / host errors

No final SEC-007 test failed. During development, the synthetic publisher checkout initially acquired Windows CRLF conversion; the fixture was corrected before the passing run. A later hostile-path test led to additionally rejecting option-like path components. Those development failures are resolved.

Five existing commands did not pass on this Windows checkout:

1. `tests/catalog_pack_pruner_test.py`: nine tests ran, five passed, four errored. Two deletion tests require POSIX directory-descriptor operations unavailable here (`PermissionError` opening a directory); two symlink tests fail with Windows privilege error 1314.
2. `tools/build-highway-contract-packs.py --check`: existing generated contract pack differs.
3. `tools/build-gepnic-road-notice-packs.py --check`: existing generated road-notice pack differs.
4. `tools/build-pmgsy-road-agreement-packs.py --check`: existing generated agreement pack differs.
5. `tools/prune-catalog-packs.py --check`: existing pack bytes do not match the filename digest.

For representative packs from all three families, the worktree bytes equal the checked-in LF bytes converted to CRLF. The SHA-256 of the checked-in bytes and of an in-memory LF normalization exactly match each filename digest; the unchanged worktree CRLF bytes do not. This is evidence of a pre-existing Windows checkout issue, not a catalog change introduced by SEC-007. No pack, manifest, Git line-ending configuration, pruner implementation, or existing test was repaired or relaxed. These issues remain outside scope, including NEW-002.

## Validation blocked / not performed

- A live GitHub-hosted Ubuntu Actions run, real browser launch in that runner image, official-source crawling, artifact-service transfer, authenticated push/PR creation, and server-enforced permission/branch-policy behavior were not exercised. The user prohibits commit/push, and no repository-connected authenticated workflow run was initiated.
- Real symlink/Unix executable-mode behavior for the new transfer helper was not exercised on Linux. Local symlink rejection was tested with mocked `lstat` modes; the existing real symlink tests demonstrate the Windows privilege blocker. Linux preflight retains all existing real symlink/pruner checks.
- Optional actionlint ShellCheck/Pyflakes integrations were unavailable locally (`-shellcheck= -pyflakes=`); shell syntax, Python AST, security contracts, and manual review were performed independently. No existing workflow security/validation step was removed or disabled.
- Android Gradle/APK/Keystore/device tests are unnecessary for this workflow-only change and were not attempted. The recorded Gradle JAR AccessDeniedException and missing ADB/device environment were not retried.

## Exact repository files changed

Repository root: `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter`.

1. `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter\.github\workflows\refresh-public-road-catalogs.yml` — modified workflow.
2. `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter\.github\catalog-refresh-requirements.txt` — new workflow-only dependency lock.
3. `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter\.github\scripts\catalog-transfer.py` — new trusted data boundary helper.
4. `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter\tests\sec007_workflow_security_test.py` — new focused offline security tests.
5. `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter\SECURITY_REMEDIATION_SEC007.md` — this report.

A matching user-facing report copy is saved at `C:\Users\user\Documents\Codex\2026-09-14\1\outputs\SECURITY_REMEDIATION_SEC007.md`. Validation downloads/scripts/logs live in the current task's `work` directory and are not repository changes.

## Remaining limitations and scope confirmation

The hosted runner image, OS libraries, bundled Git/GitHub CLI, and vendor browser archive remain external trust dependencies; the OS label is not a VM image digest. A compromised producer can still submit malicious or inaccurate data within permitted catalog paths, so source validation and human PR review remain necessary. The publication job has repository-scoped contents authority; branch protection must constrain direct writes to main outside this patch. Artifacts expire after seven days, so late publication reruns may require a fresh refresh. Transfers exceeding stated bounds fail closed.

SEC-001 through SEC-006 were preserved without weakening or editing their code/tests. SEC-008 through SEC-016 and NEW-001/NEW-002 were not remediated or changed. No application behavior, full-frame detection invariant, general dependency file, production credential, or paid service was changed. Existing failures were documented without fixing unrelated findings. Synthetic Git fixture objects used by tests were confined to temporary test repositories; the project repository was not committed, pushed, reset, reverted, or discarded.

Unrelated findings changed: NO

Commit/push: NO
