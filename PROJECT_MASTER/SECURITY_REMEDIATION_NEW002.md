# NEW-002 — Clean-build generated inputs and offline cache bootstrap

## 1. Status

**PARTIALLY RESOLVED — SOURCE/RELEASE TOOLING.** Verified 2026-09-14.

- **Resolved:** the release script now fails closed, before Gradle, unless every git-ignored Capacitor/Cordova Android input exactly matches what the installed, lock-matched Capacitor CLI generates. A clean checkout gets explicit bootstrap instructions instead of failing deep in Gradle configuration. A stale or altered generated tree can no longer reach the build.
- **Not resolved:** provenance of the Gradle dependency cache required by `--offline` (there is no dependency verification metadata), and a clean, independent signed release build.
- **Overall security gate:** remains **FAIL**.

## 2. Finding

`outputs/SECURITY_VERIFICATION.md` §F NEW-002 (and §“Release build attempt”): `tools/build-play-release.sh` expects `android-app/android/app/src/main/assets/capacitor.config.json` and the ignored `android-app/android/capacitor-cordova-android-plugins/cordova.variables.gradle`, then invokes Gradle with `--offline`. A clean checkout lacks the Cordova generated file. `npx cap copy android` did not create it; `npx cap sync android` did. The script neither performs nor preflights this sync/cache bootstrap. Result: release provenance is hard to reproduce, stale ignored inputs escape source-control comparison, and a clean builder fails before the documented checks.

## 3. Severity

- **Original:** LOW (assessed at discovery). Production blocker YES until a clean independent release build succeeds.
- **Current:** LOW. This is a release-integrity and build-reproducibility issue, not an application runtime vulnerability.
- **Security relevance:** ignored generated inputs include a Gradle module whose `build.gradle` compiles any JAR in `src/main/libs`, and WebView scripts (`cordova.js`, `cordova_plugins.js`) that the existing asset verifier requires to exist but never compared. A stale or maliciously altered local tree could therefore influence the signed artifact with no source-control diff.

## 4. Applicability

**Still applicable before this task; verified against the current tree.**

- **Required but ignored.** HEAD's git tree contains 0 entries under `android-app/android/capacitor-cordova-android-plugins/` and 0 under `app/src/main/assets/`, and no `res/xml/config.xml`. All are ignored by `android-app/android/.gitignore` (`capacitor-cordova-android-plugins`, `app/src/main/assets/public`, `capacitor.config.json`, `capacitor.plugins.json`, `res/xml/config.xml`). Yet tracked `settings.gradle` includes `:capacitor-cordova-android-plugins`, and tracked `app/capacitor.build.gradle` applies `../capacitor-cordova-android-plugins/cordova.variables.gradle`. Gradle configuration cannot succeed without them.
- **Never checked.** The HEAD release script had no generated-input preflight and no bootstrap. It compared only `capacitor.config.json` and `assets/public` against `www`. `tools/verify-release-assets.py` adds `cordova.js`/`cordova_plugins.js` to the expected packaged file set but compares bytes only for `www` files, so their content was unverified.
- **Present locally.** The authoritative tree currently contains all generated inputs from an earlier `cap sync`; the new preflight confirms they match the locked CLI exactly.
- **`--offline` cache.** It still depends on a pre-provisioned Gradle cache (`work/gradle-home`). `android-app/android/gradle/verification-metadata.xml` does not exist. The wrapper distribution is SHA-256 pinned (`gradle-wrapper.properties`).

## 5. Affected components

- `tools/build-play-release.sh` step 1 (release preflight before `./gradlew --no-daemon --offline`).
- Ignored generated inputs:
  - `android-app/android/capacitor-cordova-android-plugins/{build.gradle, cordova.variables.gradle, src/main/AndroidManifest.xml, src/main/java/.gitkeep, src/main/res/.gitkeep}`
  - `app/src/main/assets/{capacitor.config.json, capacitor.plugins.json, public/cordova.js, public/cordova_plugins.js}`
  - `app/src/main/res/xml/config.xml`
- Tracked CLI-generated wiring: `android-app/android/capacitor.settings.gradle`, `android-app/android/app/capacitor.build.gradle`.
- Generator: `@capacitor/cli` 8.5.0 (`dist/android/update.js`, `dist/cordova.js`, `assets/capacitor-cordova-android-plugins.tar.gz`) and the npm lock (`android-app/package-lock.json`, lockfileVersion 3).
- Gradle `--offline` dependency cache (outside the repository).

## 6. Root cause

1. **Required at configuration time, but ignored.** Capacitor's Android project keeps CLI-generated files out of git, while tracked Gradle files require them at configuration time. They exist only after `npx cap sync android` (update step), not `cap copy`.
2. **No release preflight.** The release script did not document, run or verify that bootstrap. Nothing compared those ignored files to what the locked CLI would produce, including the unverified WebView `cordova*.js` and the `fileTree` JAR directory.
3. **Unverified offline cache.** `--offline` makes an unverified local dependency cache an undeclared prerequisite.

**The Gradle/JAR `AccessDeniedException` is not NEW-002.**

- **Where it occurred.** The original evidence places it after sync, at `compileReleaseJavaWithJavac` / `:capacitor-android:compileDebugJavaWithJavac`, on varying transformed JARs, while `jar tf` and .NET reads succeeded. NEW-002's failure is earlier: missing configuration inputs.
- **Configuration succeeds.** In this session, `gradlew.bat help --offline --no-daemon` with the portable JDK/SDK and `work/gradle-home` succeeded (BUILD SUCCESSFUL in 58 s) as `LENOVOTHINKBOOK\by.maverickk`, with the generated inputs present.
- **The file reads cleanly.** A deterministic Java probe (`work/new002/ZipAccessProbe.java`, JDK 21.0.12) ran 50 rounds of `FileSystems.newFileSystem` walks with full reads, plus 50 `JarFile` full reads, on the exact previously failing `…transforms/2b6d554…/lifecycle-viewmodel-2.6.2-api.jar`. Result: 50/50 and 50/50, 1,750 entries, 0 failures.
- **Different account.** That JAR and `work/gradle-home` are owned by `LENOVOTHINKBOOK\CodexSandboxOnline`, with ACL entries for Codex sandbox groups. Together, these findings point to a host/sandbox-session file-access interaction, not repository configuration. The compile step itself was deliberately not retried.

## 7. Threat/failure model

| Actor / condition | Before | After |
| --- | --- | --- |
| Clean checkout / new release machine | Gradle configuration fails on missing `cordova.variables.gradle`; no guidance; documented release checks never run. | Preflight fails first with the exact missing input and `cd android-app && npm ci && npx cap sync android`. |
| Stale generated tree (plugins added/removed, CLI or npm deps changed, no re-sync) | Outdated plugin registry, Gradle wiring or Cordova module silently built into a signed artifact. | Rejected: installed versions must match the lock; tracked wiring, registry, module, config and manifest must match the locked CLI output. |
| Local tampering with ignored inputs (host compromise, malicious tooling) | Extra `src/main/libs/*.jar` compiled via `fileTree`, altered module `build.gradle`/manifest, non-empty WebView `cordova.js`, or permissive `config.xml` access origin could enter the artifact without any git diff. | Rejected by exact file-set and content checks; `cordova*.js` must be empty. |
| Poisoned Gradle offline cache | Undetected. | **Still undetected**: no dependency verification metadata (remaining risk). |
| Runtime app user / remote attacker | No direct path. | No direct path. |

## 8. Attack/failure preconditions

- **Failure:** any clean or partially provisioned checkout.
- **Integrity:** write access to ignored files or caches on the release host, or a maintainer forgetting to re-sync after dependency or plugin changes.
- **Remote:** no remote or runtime trigger.

## 9. Impact

- **Before:** releases were not reproducible from source control; generated or stale inputs could alter the signed APK/AAB (compiled code, manifest merge, WebView scripts, plugin registry) invisibly to review; clean builders failed before any documented validation.
- **After:** the generated-input half is enforced. Remaining: cache provenance and an unproven clean end-to-end build.

## 10. Existing mitigations

- Packaged `assets/public` web assets are byte-compared to `www`/`static` (`tools/verify-release-assets.py`, before and after build).
- The packaged `capacitor.config.json` is compared to source.
- The Gradle wrapper distribution is SHA-256 pinned.
- The npm lockfile carries integrity hashes (`npm ci`).
- Release signing, manifest, permission, R8 and secret-scan checks run.
- NEW-001's AAB signature gate.

None of these verified the Cordova module, the plugin registry, `config.xml` or `cordova*.js` content, and none provided a clean-checkout preflight.

## 11. Remediation performed

1. **New `tools/verify-android-generated-inputs.py`** (read-only, stdlib Python, fail-closed). For the reviewed configuration (Capacitor 8.5.0; Capacitor plugins only; JSON config without `includePlugins`/`cordova`), it regenerates in memory exactly what `update.js`/`cordova.js` write, then:
   - requires each `package.json` dependency to be installed at the `package-lock.json` version;
   - rejects Cordova plugins, TypeScript/JS Capacitor config, `includePlugins`, and Cordova preferences/origins;
   - pins the CLI version and its Android `minVersion`;
   - compares the tracked `capacitor.settings.gradle`/`capacitor.build.gradle`, tolerating Windows CRLF;
   - requires the Cordova module's exact file set (template files plus `cordova.variables.gradle`; ignored `build/` and `.gradle/` Gradle outputs excluded), its `build.gradle` rebuilt from the CLI template tarball using the CLI's regex substitutions, `cordova.variables.gradle`, the manifest (including the `server.cleartext` rule) and `.gitkeep` bytes;
   - checks the plugin registry against plugin classes scanned with the CLI's regexes, `capacitor.config.json` equality, `config.xml`, empty `cordova.js`/`cordova_plugins.js`, and no `public/plugins`;
   - on failure prints the exact bootstrap: `cd android-app && npm ci && npx cap sync android`.
2. **`tools/build-play-release.sh`:** five added lines in step 1, after the existing asset and config checks and before Gradle, that run the preflight and fail with the bootstrap command. Nothing else in the script changed for NEW-002.
3. **New `tests/new002_android_generated_inputs_test.py`:** a focused regression/contract test.

**Deliberately not done:**

- Running `npx cap sync android` inside the release script: it rewrites tracked Gradle files and the web copy; the preflight instead requires a reviewed, explicit bootstrap.
- Adding Gradle `verification-metadata.xml`: it requires a network-backed full dependency resolution/metadata generation run and a review of every checksum, a broader change than this scoped task.
- Changing AGP, Gradle, Capacitor, npm dependencies, the wrapper or `--offline`.

## 12. Tests and exact results

**Source-level verification:**

| Check | Result |
| --- | --- |
| `python tests/new002_android_generated_inputs_test.py` | **PASS (19 checks).** Current tree matches the locked CLI (“@capacitor/cli 8.5.0, 7 Capacitor plugins, 0 Cordova plugins”). A copied fixture passes; the CRLF tracked-wiring variant passes. Each of the following fails closed with the bootstrap command: clean checkout (missing module); missing `cordova.variables.gradle`; stray `src/main/libs/stale.jar`; altered module `build.gradle`; stale `capacitor.plugins.json`; non-empty `cordova.js`; tracked `capacitor.build.gradle` drift; installed plugin ≠ lock (`0.0.0-unlocked` vs 8.2.2); Cordova plugin dependency; altered `config.xml`; altered module manifest; `capacitor.config.ts`. Release script runs the preflight before Gradle with the bootstrap message; NEW-001 gate and existing asset/config checks preserved. |
| Before-fix evidence | HEAD `tools/build-play-release.sh` contains no `verify-android-generated-inputs` invocation (probe: `False`), so the wiring checks would fail against it. The clean-checkout fixture reproduces the missing-module condition the release previously did not preflight. |
| `bash -n tools/build-play-release.sh` (Git Bash 5.2.37) | OK. Worktree CRLF convention preserved (335 CR / 335 LF; index LF). `git diff --ignore-cr-at-eol` vs HEAD: +5 NEW-002 lines in step 1, plus the unchanged +11 NEW-001 lines in step 4. |
| `ast.parse` of verifier and test | OK (no bytecode written). |
| `tests/new001_aab_signature_order_test.py` | PASS (17). |
| `tests/android_release_optimization_test.py` | PASS. |
| `tests/hybrid_drive_contract_test.py` (`PYTHONUTF8=1`; default Windows cp1251 decoding is the pre-existing NEW-001-recorded environment issue) | PASS. |
| `tests/sec014_fileprovider_contract_test.py` (scans the Cordova module source) | PASS (25). |

**Environment diagnosis (deterministic):**

| Check | Result |
| --- | --- |
| `gradlew.bat help --offline --no-daemon` (JDK/SDK/gradle-home from `work/toolchain`) | BUILD SUCCESSFUL in 58 s; configuration of all projects including the Cordova module succeeds with present inputs. It wrote the ignored `android-app/android/build/reports/problems/problems-report.html` (23:28, after the 23:24 snapshot). That was left in place because earlier Gradle sessions may already have written a report at this ignored path; it is outside source scope. |
| `ZipAccessProbe.java` on the previously failing transformed JAR | 50/50 ZIP filesystem walks and 50/50 JarFile reads, 1,750 entries, 0 failures, as the current user. |
| ACL inspection | JAR and gradle-home owned by `CodexSandboxOnline`; current user has FullControl. |

**Artifact-level verification:** none. No APK/AAB was built.

## 13. Limitations

- **No release build:** no Gradle compile, lint, `bundleRelease`/`assembleRelease` or signed artifact from a clean checkout. The private upload keystore is unavailable, and the earlier compile-phase `AccessDeniedException` was diagnosed but not retried.
- **Not run:** no clean-checkout `npm ci` + `npx cap sync android` end-to-end run (it would rewrite tracked files in the authoritative tree). The fixture variants model the clean state instead.
- **Cache provenance open:** Gradle offline cache provenance remains unverified (no `verification-metadata.xml`).
- **Reviewed configuration only:** the preflight models CLI 8.5.0 for a Capacitor-only configuration. A CLI upgrade, Cordova plugin or config change fails closed by design and requires updating the model.
- **Not covered:** `tools/build-apk.sh` (debug path, uses `cap copy`) was not changed.
- **No device/runtime testing.**

## 14. Files changed

1. `tools/verify-android-generated-inputs.py` (new).
2. `tests/new002_android_generated_inputs_test.py` (new).
3. `tools/build-play-release.sh`: +5 lines in step 1.
4. `PROJECT_MASTER/SECURITY_REMEDIATION_NEW002.md` (new): this report.
5. `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md` and `PROJECT_MASTER/CHANGELOG.md`: NEW-002 status.

Evidence outside the repository is in `work/new002/`: `pre_hashes.tsv`, `template_probe.py`, `lock_probe.py`, `ZipAccessProbe.java`, `gradle_help.out.txt`, `new002_test.out.txt`, `syntax_probe.sh`. The Gradle `help` run wrote or refreshed ignored Gradle state: `android-app/android/build/reports/problems/problems-report.html`, and possibly `android-app/android/.gradle/` and `work/gradle-home`. All of it is git-ignored and excluded from the source scope comparison. A test-generated `tools/__pycache__` bytecode file was removed.

## 15. Files deliberately not changed

- Gradle/AGP/Kotlin/Capacitor/npm versions, `package.json`/`package-lock.json`, `gradle-wrapper.properties`, `settings.gradle`, `build.gradle` files.
- The generated inputs themselves: not regenerated, `cap sync` not run.
- `tools/verify-release-assets.py`, `tools/build-apk.sh`, `.gitignore` files.
- `tools/normalize-aab-signature-order.py`, `tests/new001_aab_signature_order_test.py` and the NEW-001 step-4 lines.
- All SEC-001–016 files.
- `PROJECT_MASTER/PRODUCT_IMPLEMENTATION_ROADMAP.md`.
- Product source/web assets.

## 16. Preservation of SEC-001–016

No SEC-001–016 remediation file or control was modified. The release script keeps all prior checks. SEC-014's contract passes. SEC-001–016 statuses in `SECURITY_STATUS.md` are unchanged apart from the NEW-002 row and link.

## 17. Preservation of NEW-001

NEW-001's normalizer, test and release step-4 gate are unchanged (`git diff` shows the same 11 NEW-001 lines). `tests/new001_aab_signature_order_test.py` passes (17). NEW-001 status remains RESOLVED — SOURCE/RELEASE TOOLING.

## 18. Confirmation NEW-002 scope only

Only the files listed in section 14 changed (confirmed by before/after SHA-256 scope comparison after removing test and Gradle artifacts). No other finding was started, no SEC-017 was invented, and the product roadmap was not modified. No commit or push.

## 19. Exact handoff for the next task

- **Task completed:** NEW-002 only.
- **Final status:** PARTIALLY RESOLVED (generated-input integrity/bootstrap enforced; Gradle offline cache provenance and clean independent release build open).
- **No further audit finding:** the recorded audit material (`outputs/SECURITY_AUDIT.md`, `SECURITY_VERIFICATION.md`, `SECURITY_INVENTORY.json`) defines SEC-001–016 and NEW-001–002 only. No further security finding exists after NEW-002, and none was invented.
- **Next project action from existing documentation** (`PROJECT_MASTER/NEXT_STEPS.md`): resolve the recorded Windows/Gradle environment blocker **once** in a dedicated build-verification task. This report's evidence shows it is host/sandbox-session related, not repository configuration. Then obtain a clean, independent signed release build from the preserved tree and complete the outstanding SEC-001–006 Keystore/device/APK verification. Within that task, NEW-002's remaining items are:
  1. On a clean checkout run `npm ci` and `npx cap sync android`, review the diff, and confirm `tools/verify-android-generated-inputs.py` passes.
  2. Decide and implement verified Gradle dependency provisioning (for example reviewed `gradle/verification-metadata.xml`) or remove the hidden `--offline` prerequisite.
  3. Run `tools/build-play-release.sh` end to end with authorized signing.
- **Instructions for the next agent:**
  - Read `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`, `NEXT_STEPS.md`, this report and `SECURITY_REMEDIATION_NEW001.md` first.
  - Keep `tests/new002_android_generated_inputs_test.py` and `tests/new001_aab_signature_order_test.py` passing.
  - Do not weaken the step-1 preflight or step-4 AAB gate.
  - Do not run `cap sync` over the authoritative tree without reviewing its diff.
  - Do not commit/push.
- **Current HEAD:** `f282454e8fb79a529894598b0af9a3d7008fd84c` (unchanged). Working tree = pre-existing uncommitted SEC-001–016 and NEW-001 changes, the concurrently created `PROJECT_MASTER/PRODUCT_IMPLEMENTATION_ROADMAP.md` (untouched), plus the NEW-002 files above.
- **Commit/push:** not done.

## 20. Dedicated Windows/Gradle and release verification — 2026-09-23

This addendum supersedes the verification handoff in section 19. It records an environment/build check, not a new finding or a source-code remediation. **NEW-002 remains PARTIALLY RESOLVED; the overall security gate remains FAIL.** SEC-001–016 and NEW-001 source/status are unchanged.

### Gradle blocker and root-cause boundary

- A focused `gradlew.bat --offline --no-daemon --rerun-tasks --stacktrace :capacitor-android:compileDebugJavaWithJavac` run with the existing JDK 21, SDK and `work/gradle-home` first stopped during Android Gradle plugin configuration: `AccessDeniedException: C:\.android` while resolving the default debug-keystore preferences location. `ANDROID_USER_HOME` was then set to a writable task-local directory, and one follow-up run configured `:app` and `:capacitor-cordova-android-plugins` and executed eight tasks. It failed at `:capacitor-android:compileDebugJavaWithJavac` in 2m 57s.
- The reproduced exception was `java.nio.file.AccessDeniedException: C:\Users\user\Documents\Codex\2026-09-09\bro\work\gradle-home\caches\8.14.3\transforms\2b6d554ba8c9daf5de9f065479573c89\transformed\lifecycle-viewmodel-2.6.2-api.jar`. The stack reaches `jdk.nio.zipfs.ZipFileSystemProvider.removeFileSystem` → `WindowsPath.toRealPath` as `JavacFileManager$ArchiveContainer.close` closes the archive. This is the same transformed JAR and failure phase recorded previously.
- The JAR is 84,638 bytes, SHA-256 `3AB961A66C0BF6DFADA8DD056CE8A5903E1B50B911595EDBBEFFA6D5DC9AB278`. `Get-FileHash`, `.NET File.OpenRead` and JDK `jar tf` (35 entries) succeed. A direct Java ZIP-filesystem full-read/close probe fails at `toRealPath` on that JAR, its byte-identical task-local copy, and a newly created tiny ZIP. The prior report's 50/50 successful ZIP reads were from a different host session. This isolates the current failure to Java ZIP-filesystem real-path access in this Windows execution context; it is not evidence of a corrupt JAR, a single bad Gradle transform, or a Java source diagnostic. The underlying OS access denial mechanism (sandbox policy, locking, or another host condition) is **not proven**. No third Gradle retry or speculative source workaround was made. The second run still emitted a nonfatal metrics warning about `C:\.android`.

### NEW-002 offline cache provenance

- `android-app/android/gradle/wrapper/gradle-wrapper.properties` pins the Gradle 8.14.3 distribution SHA-256. The existing `work/gradle-home/caches/modules-2` and transformed artifacts permit offline configuration/task execution, but `android-app/android/gradle/verification-metadata.xml` and a Gradle dependency lockfile are absent. No independent upstream checksum/signature comparison of the cached dependencies was available here.
- The observed JAR hash above identifies bytes in this session; it does **not** establish upstream provenance. Generating verification metadata from this unverified offline cache would merely bless its present contents, so none was added. No dependencies, wrapper, Gradle scripts or generated Android inputs were changed. The existing NEW-002 generated-input preflight still passes 19 checks. Cache provenance remains open.

### Release, device and checks

- No `POTHOLE_RELEASE_*` signing values or ignored `android-app/android/keystore.properties` were present. The production upload key was not supplied, and no audit key was substituted for it. Given the reproduced compile failure, the intended `tools/build-play-release.sh` could not produce a clean independent signed APK/AAB. No APK/AAB, Bundletool result, artifact signature result or artifact hash was generated in this task. NEW-001's source-level AAB signature-order test passes 17 checks; it was not validated on a new artifact.
- `adb devices -l` failed before enumeration with `Cannot mkdir '\.android': Permission denied`, including attempts with writable `ANDROID_USER_HOME` and `ANDROID_SDK_HOME`. The installed SDK has no `system-images` directory. No actual device/emulator run or SEC-001–006 runtime check was completed; device availability through a functioning ADB session remains unverified.
- Focused results: `tests/new002_android_generated_inputs_test.py` **PASS (19)**; `tests/new001_aab_signature_order_test.py` **PASS (17)**; `tests/android_release_optimization_test.py` **PASS**; Git Bash `bash -n tools/build-play-release.sh` **PASS**. The two Gradle attempts both exited 1 with the distinct paths above. Final scope/hash checks are recorded at handoff; the roadmap, SEC-001–016, NEW-001, dependencies and product code were untouched.
- This checkpoint changed only `PROJECT_MASTER/SECURITY_REMEDIATION_NEW002.md`, `SECURITY_STATUS.md`, `PROJECT_STATUS.md` and `CHANGELOG.md`. `git diff --check` exited 0; a UTF-8/trailing-whitespace check of all four documents passed. The protected product roadmap retained SHA-256 `DB58424F26C56E13F61234835D3C3688200D466D8AD67A6D54F3AFB13297F98C`; the NEW-002 verifier, release script and focused test retained their prior hashes. HEAD remains `f282454e8fb79a529894598b0af9a3d7008fd84c`.

### Remaining blockers and next task

NEW-002's generated-input check remains in place, while a verified Gradle dependency cache and a clean signed release build remain outstanding. Device/Keystore/URI-grant/runtime verification and live SEC-007 Actions execution remain separate recorded blockers. Per `PROJECT_MASTER/NEXT_STEPS.md`, the next task is to obtain a supported build environment where Java ZIP filesystem can complete, establish independently verified Gradle dependency provenance (or remove the hidden offline-cache prerequisite), then run a clean signed release with legitimate signing material and complete artifact/device verification. The Windows/Gradle failure has now been reproduced and characterized in this dedicated task; do not repeat the same failing operation on this host without a concrete environment change. `NEXT_STEPS.md` itself was not changed. No commit or push.
