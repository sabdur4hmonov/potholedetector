# SEC-008 dependency remediation

Date: 2026-09-14. Repository: `coding-parrot/pothole-reporter`; base HEAD `f282454e8fb79a529894598b0af9a3d7008fd84c`.

**Finding:** SEC-008. **Severity:** HIGH, as required for this remediation and confirmed by live npm audit. The authoritative original audit recorded project severity MEDIUM; the prior verification already distinguished that from npm's HIGH package severity. Those baseline reports were not changed.

**STATUS: RESOLVED — dependency/toolchain level.** Actual installed package, normal lockfile and npm hidden lockfile all resolve `@xmldom/xmldom@0.9.12`. SEC-008 is absent from the final live audit. This does not approve a production release or claim Android/device verification.

## Root cause and exact dependency chain

The existing `android-app/package-lock.json` pinned `@xmldom/xmldom@0.9.11`, an affected XML parser/serializer release. Its immediate parent, `plist@3.1.1`, already declares `@xmldom/xmldom: ^0.9.10`, which permits the patched `0.9.12` release. The old lock resolution retained the vulnerable patch despite that compatible range.

Both the actual lockfile and baseline/final `npm explain @xmldom/xmldom` verify all three paths from `android-app@1.0.0`:

```text
@capacitor/cli@8.5.0 -> plist@3.1.1 -> @xmldom/xmldom
@capacitor/cli@8.5.0 -> native-run@2.0.3 -> plist@3.1.1 -> @xmldom/xmldom
@capacitor/cli@8.5.0 -> xcode@3.0.1 -> simple-plist@1.3.1 -> plist@3.1.1 -> @xmldom/xmldom
```

The root range for Capacitor CLI is `^8.5.0`. CLI declares `plist: ^3.1.0`, `native-run: ^2.0.3`, and `xcode: ^3.0.1`; native-run declares `plist: ^3.1.0`; xcode declares `simple-plist: ^1.1.0`; simple-plist declares `plist: ^3.0.5`. All paths share one resolved plist and one xmldom copy.

This is developer/build tooling. The authoritative prior verification established that these npm packages do not appear in Android `releaseRuntimeClasspath`. No new Android dependency scan was performed, and no Android runtime dependency was changed.

## Minimal compatible change

| Component | Before | After |
| --- | --- | --- |
| `@xmldom/xmldom` | `0.9.11` | `0.9.12` |
| `plist` | `3.1.1` | `3.1.1` |
| `@capacitor/cli` | `8.5.0` | `8.5.0` |
| Other lockfile package entries | Original versions/metadata | Identical |

Registry metadata confirmed plist's existing range, xmldom `0.9.12` availability and unchanged Node engine requirement (`>=14.6`). The registry's latest xmldom release was `0.9.12`. The maintainer's [high-severity memory advisory](https://github.com/xmldom/xmldom/security/advisories/GHSA-965w-775f-mr7g) identifies `0.9.11` as affected and the `0.9.12` branch as patched; the final npm audit verifies removal of the complete reported xmldom finding, not just that one advisory.

The immediate parent already safely admits the patch, so changing its version is unnecessary. The targeted npm update changed only xmldom's version, registry tarball URL and SHA-512 integrity in the existing lockfile. `package.json` remains byte-for-byte identical, with synchronized root dependency ranges. No new direct dependency, override, resolution, force option, downgrade, broad upgrade or architecture change was needed.

Patched integrity:

```text
sha512-5AXjrcMClTryPe9LgZrygpB1lj7s0S9E0+W+AHaVKAVyHanafK86iPSvG5xHVSp/jC+VH1UXu0TAEmY279xH7A==
```

## Exact repository files changed for SEC-008

- `android-app/package-lock.json`: one package entry, three fields.
- `SECURITY_REMEDIATION_SEC008.md`: this report.
- `PROJECT_MASTER/SECURITY_STATUS.md`: SEC-008 conclusion, scoped verification note and report link.
- `PROJECT_MASTER/PROJECT_STATUS.md`: record SEC-008 completion and move the pending-source starting point to SEC-009.

Local ignored installation state was also refreshed: xmldom package contents and `android-app/node_modules/.package-lock.json`. Backups and inspection evidence are outside the repository under `C:\Users\user\Documents\Codex\2026-09-14\files-pasted-by-the-user-you\work\sec008`; npm's task cache is under that task's `work\npm-cache`. A deliverable copy of this report is in that task's `outputs` directory.

## Commands and focused verification

Commands were run from `android-app` using Node `v24.18.0` and npm `11.16.0`. Network commands used the task-local cache and `--fetch-retries=0 --fetch-timeout=20000`. No install lifecycle scripts were executed.

| Command/check | Result |
| --- | --- |
| Baseline `npm ls @xmldom/xmldom` and `npm explain @xmldom/xmldom` | Confirmed `0.9.11` and the three parent paths above; exit 0. |
| Baseline `npm audit --json` | Exit 1; one HIGH xmldom node with eleven advisories, plus three unrelated MODERATE nodes. |
| `npm view plist@3.1.1 version dependencies --json` | Confirmed existing parent permits `^0.9.10`. |
| `npm view @xmldom/xmldom@0.9.12 version engines dist --json` and package dist-tag queries | Confirmed compatible patch, published tarball/integrity and xmldom latest `0.9.12`; exit 0. |
| `npm update @xmldom/xmldom --package-lock-only --ignore-scripts --no-audit --no-fund` | Exit 0; only the xmldom lock entry changed. |
| `npm install --ignore-scripts --no-audit --no-fund` | First run incorrectly reported up to date because hidden npm lock metadata described `0.9.12` while package contents were still `0.9.11`; see recovery below. Final run changed exactly one package; exit 0. |
| Final `npm ls @xmldom/xmldom --all` and `npm explain @xmldom/xmldom` | `0.9.12`, same parent chains; exit 0. |
| Final `npm ls --all --json` | Exit 0; no missing/invalid/extraneous dependency problems. Used only to check installation consistency, not to re-audit other findings. |
| `npm ci --dry-run --ignore-scripts --no-audit --no-fund --offline` | Exit 0; npm accepts manifest/lock synchronization. Dry run only, not a clean reinstall. |
| Direct package/lock checks in task-local `verify.cjs` | PASS: unchanged manifest, identical root ranges and lock structure/package keys; exactly one changed package entry; one xmldom lock copy and one actual installed copy, both `0.9.12`; hidden lock also `0.9.12`. |
| Actual plist module resolution and `plist.parse(plist.build(sample))` smoke check | PASS using xmldom `0.9.12`; identifier, escaped text, boolean, integer and string-array values round-trip correctly. |
| Final `npm audit --json` plus focused assertions | SEC-008 absent, HIGH count 0; the three other advisory nodes are identical to baseline. Audit exit 1 is expected for those remaining findings. |
| Final scoped diff/preservation check | Only intended dependency changes; prior tracked application/workflow edits preserved; no whitespace errors in the dependency diff. |

### Hidden-lock mismatch and recovery

The first direct disk assertion failed: npm's tree display and hidden lock reported `0.9.12`, but `node_modules/@xmldom/xmldom/package.json` still contained `0.9.11`. No success was declared at that point. Targeted config queries confirmed that package-lock-only and dry-run were not persistent defaults. The hidden lock was moved, as a single file, to the task-local backup `node-modules-lock.stale.json`; rerunning the normal script-disabled npm install reconstructed installation metadata and changed exactly one package. Final checks read real package manifests and traversed nested module directories, rather than trusting only npm's cached tree display. No vulnerable duplicate remains in the inspected installation.

Evidence retained: `package-lock.before.json`, `package.before.json`, `audit.before.json`, `audit.after.json`, `tree.after.json`, `node-modules-lock.stale.json`, `verify.cjs`, and `verification.txt` in the task-local evidence directory.

## Audit outcome, residual risk and limitations

| Live npm audit | Before | After |
| --- | --- | --- |
| HIGH | 1 | 0 |
| MODERATE | 3 | 3 |
| Total vulnerability nodes | 4 | 3 |
| xmldom node | Present, eleven advisories | Absent |

**npm audit is clean for SEC-008, but not globally clean.** Its remaining moderate nodes are `uuid`, `xcode`, and the propagated `@capacitor/cli` result. They were not remediated or investigated beyond checking that their existing audit records were unchanged. They do not negate removal of the xmldom finding.

SEC-008's known vulnerable-version blocker is removed from the source/dependency toolchain. Advisory coverage remains limited to the live registry response; this report does not promise freedom from undiscovered vulnerabilities. Developers and release jobs must install from the updated lockfile to obtain the patched package.

No Capacitor sync, Gradle/Android build, emulator, ADB/device test, generated-asset regeneration, broad project test suite or full final security verification was run. The plist smoke check is limited compatibility evidence, not end-to-end build validation. Previously recorded Windows transformed-JAR access denial, device/Keystore/URI-grant verification gaps, live GitHub Actions verification, NEW-001/NEW-002 release blockers and other pending security work remain outstanding. No APK/AAB was created or replaced.

**SEC-001–SEC-007 were not reworked. SEC-009 was not started.** No unrelated functionality or Android runtime dependencies were changed. No commit or push was performed.
