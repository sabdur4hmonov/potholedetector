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

## 21. Windows/Gradle continuation — 2026-09-29

This is a build-environment checkpoint, not a new security finding. The checkout was clean on `main` at `86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8` before documentation changes. No product source, dependency versions, Gradle scripts, signing configuration or generated-input verifier changed.

- **Toolchain:** Node 24.18.0, npm 11.16.0, Temurin JDK 21.0.12.1, Android platform 36 and build-tools 35.0.0/36.0.0 were present. The JDK/SDK under the older Windows profile were not readable by the current-user network-enabled command context. They were copied into the ignored `android-app/android/.gradle/toolchain/` on D:. Source and copy have 490 JDK files / 343,823,876 bytes and 11,841 SDK files / 591,706,838 bytes. SHA-256 matches for the copied `java.exe`, `platforms/android-36/android.jar` and `build-tools/36.0.0/apksigner.bat`; these sample checks and counts are not a full provenance attestation for the toolchain.
- **Locked inputs:** Initial sandboxed `npm ci` failed with `EACCES` while fetching `yauzl-2.10.0.tgz`. One network-enabled `npm ci --cache android\.gradle\npm-cache` succeeded (106 packages added, npm lockfile integrity enforced). The read-only `tools/verify-android-generated-inputs.py` then passed: CLI 8.5.0, seven Capacitor plugins, zero Cordova plugins. The existing ignored generated inputs were already current, so `cap sync` was not run over this tree.
- **Fresh D: Gradle home:** `GRADLE_USER_HOME=android-app/android/.gradle/codex-home` and `ANDROID_USER_HOME=android-app/android/.gradle/android-home` were used; no transformed JAR or module cache was copied from C:. The sandboxed wrapper download was denied network access. With network-enabled execution and the D: JDK, `gradlew.bat --version` downloaded the Gradle 8.14.3 distribution specified by the wrapper's SHA-256 pin and exited 0, reporting Launcher JVM 21.0.12.1 on Windows 11. The fresh home has no `caches/modules-2` after the following failure.
- **Dependency provisioning blocker:** `gradlew.bat --no-daemon --console=plain :app:dependencies` exited 1 before dependency resolution or any project task: `java.io.IOException: Unable to establish loopback connection` while Gradle attempted a single-use daemon. Two targeted `help` probes with `--no-daemon` (first clearing `org.gradle.jvmargs`, then matching launcher/build JVM settings) each exited 1 with the same error. Gradle was not retried further. This is a Gradle/Java execution-context failure, not a Java/Kotlin compile diagnostic or evidence of a bad dependency. The lower-level cause of the loopback denial was not established.
- **NEW-002 provenance:** `android-app/android/gradle/verification-metadata.xml` is absent; no dependency lock/checksum set was independently reviewed. Since the new Gradle module cache is empty, dependency provisioning and provenance are both incomplete. No hashes were invented, and no metadata was generated from unverified cache bytes. NEW-002 remains **PARTIALLY RESOLVED**.
- **Build, release and device:** The prerequisite dependency resolution failed, so the documented `:app:assembleDebug` and `tools/build-play-release.sh` were not run. No upload signing variables or ignored `keystore.properties` were present. No APK/AAB exists under the project build outputs; no signature, Bundletool, packaged-asset or NEW-001 ordering check on a newly built artifact was possible. `adb devices -l` started its daemon successfully but listed zero devices. No device/runtime verification occurred.
- **Focused checks:** `tests/new002_android_generated_inputs_test.py` passed 19 checks; `tests/new001_aab_signature_order_test.py` passed 17 with JDK 21 and English JDK output; `tests/android_release_optimization_test.py` passed. These are source/contract checks only.

**Exact next task:** use a Windows build context that allows Gradle's Java loopback connection, resolve dependencies into the D: home from configured repositories, establish independently reviewed dependency verification metadata or equivalent trustworthy provenance, then perform the documented narrow debug build and a real signed release run with legitimate upload material. Verify new APK/AAB and NEW-001's AAB gate, then perform device checks when a supported device/emulator is attached. Do not repeat the identical loopback failure without a concrete environment change. No commit or push was made in this checkpoint.

## 22. Gradle loopback diagnosis and one dependency-resolution attempt — 2026-09-29

This continuation diagnoses only the loopback blocker. Earlier documentation changes remain uncommitted; HEAD is still `86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8` on `main`. No application source, Gradle script, wrapper, signing configuration, firewall, antivirus or system-wide networking setting changed.

### Exact failing context and Java environment

The earlier failing command was `gradlew.bat --no-daemon --console=plain :app:dependencies` from `android-app/android`, with `JAVA_HOME` set to `D:\Coding projects\pothole-reporter\android-app\android\.gradle\toolchain\jdk`, `ANDROID_HOME`/`ANDROID_SDK_ROOT` to its copied `android-sdk`, `GRADLE_USER_HOME` to `.gradle/codex-home`, and `ANDROID_USER_HOME` to `.gradle/android-home`. It did not set `jdk.net.unixdomain.tmpdir`. The command's ignored log is `.gradle/codex-dependency-provision.log`; it exited 1 with `java.io.IOException: Unable to establish loopback connection` before project configuration/dependency resolution. Two later no-daemon `help` probes reproduced it, as recorded above.

In the same current-user (`LENOVOTHINKBOOK\codebysardor`) command context, explicit `java.exe -version` reported Temurin OpenJDK `21.0.12.1+1-LTS`. `where.exe java` found no Java on `PATH`, but `JAVA_HOME\bin\java.exe` exists and the wrapper uses it. `gradlew.bat --version` reported Gradle 8.14.3, Launcher JVM 21.0.12.1 and Daemon JVM at that D: JDK path. Project `gradle.properties` sets `org.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8 -XX:-TieredCompilation`; no `systemProp.*` network/proxy setting was found. No user-home Gradle properties/init script was present in the checked D: and current-user locations. `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`, `JAVA_OPTS`, `GRADLE_OPTS` and HTTP(S)/ALL/NO_PROXY environment variables were absent before the fix; WinHTTP reported direct access with no proxy.

### Reproduction and immediate cause

The existing daemon log `.gradle/codex-home/daemon/8.14.3/daemon-9212.out.log` shows Gradle **accepted** a TCP connection from `127.0.0.1:52755` to `127.0.0.1:52750`, then failed while `SocketConnection$SocketInputStream` called `Selector.open()` → `WEPollSelectorImpl` → `PipeImpl` → `UnixDomainSockets.connect0`: `java.net.SocketException: Invalid argument: connect`. Thus the top-level loopback message did not mean ordinary TCP localhost was unavailable.

A temporary standalone Java probe, run with that same JDK and Windows account, passed three TCP bind/connect checks on `127.0.0.1`/`localhost`, but `Selector.open()` independently failed with the identical `Unable to establish loopback connection` and `UnixDomainSockets.connect0` cause. Automatic Unix-domain socket binding produced a path under `TEMP=C:\Users\CODEBY~1\AppData\Local\Temp`; connecting failed with `Invalid argument: connect`. An explicit long-form path under the same C: user temp directory also failed, while an explicit socket path under the project-local D: `.gradle` directory passed. The JDK's bundled `PipeImpl.java`, `WEPollSelectorImpl.java` and `UnixDomainSocketsUtil.java` confirm that this selector prefers AF_UNIX and uses `jdk.net.unixdomain.tmpdir`, then Windows `TEMP`, for automatic socket names. The strongest established cause is a path-specific JDK/Windows AF_UNIX connection failure in the C: temp directory; why that directory fails at the OS level remains unproven. The evidence does not implicate a proxy, general TCP loopback, Gradle dependency coordinates, or a Java compile error.

### Narrow reversible fix and result

For one process tree only, `JDK_JAVA_OPTIONS` was set to `-Djdk.net.unixdomain.tmpdir="D:\Coding projects\pothole-reporter\android-app\android\.gradle"`. The same standalone Java probe then passed TCP loopback, `Selector.open()`, ordinary `Pipe.open()`, and automatic and explicit Unix-domain socket bind/connect under D:. No persistent Java, project or Windows setting was changed; the temporary Java probe source/socket files were removed.

With the same process-local setting and existing D: JDK/SDK/Gradle homes, one online `gradlew.bat --no-daemon --console=plain :app:dependencies` attempt exited 0: `BUILD SUCCESSFUL in 3m 5s` (one actionable task). Its ignored log is `.gradle/codex-dependency-resolution-20260929.log`. Resolvable app debug/release compile and runtime classpath sections were reported. The report also prints nine project dependencies as `FAILED` under the non-resolvable `implementation (n)` configuration; this is not a claim that those project variants were build-verified. The D: `modules-2` cache now contains 1,357 files / 176,070,706 bytes; `files-2.1` includes 506 `.pom`, 175 `.module` and 165 `.jar` files. This task did not run a build, so it does not establish that every future build artifact is present.

`android-app/android/gradle/verification-metadata.xml` remains absent. The wrapper's distribution SHA-256 pin and npm lock integrity do not independently verify Gradle dependencies; downloaded bytes were not blessed as trusted provenance. **NEW-002 remains PARTIALLY RESOLVED and the overall security gate remains FAIL.** Dependency provenance work can now proceed, but was not completed in this diagnostic checkpoint. No APK/AAB, artifact verification or device test was performed. No commit or push.

**Exact next task:** independently review and record Gradle dependency checksums/signatures or equivalent trustworthy provenance for the resolvable Android variants, ensure their required artifacts are actually fetched into the D: cache using the process-local JDK socket setting, then perform one documented narrow debug build in a separate build checkpoint. Signed release and device verification remain later work.

## 23. Debug dependency-cache and provenance check — 2026-09-29

This check stayed within NEW-002 and did not run the Android build. `main` and HEAD remained `86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8`; earlier documentation edits were already uncommitted. `PROJECT_MASTER/COMMANDS.md` documents `gradlew.bat --no-daemon --offline :app:assembleDebug` after copying the preserved web tree. The Gradle `--offline --dry-run :app:assembleDebug` task plan passed without executing a build task. It included `:app:kspDebugKotlin`, `:app:compileDebugKotlin`, `:app:compileDebugJavaWithJavac`, dexing, `:app:packageDebug` and `:app:assembleDebug`, together with compile/package tasks for nine Capacitor modules.

### Artifact availability

All Gradle calls used the copied JDK 21.0.12.1 and Android SDK on D:, `GRADLE_USER_HOME=android-app/android/.gradle/codex-home`, `ANDROID_USER_HOME=android-app/android/.gradle/android-home`, and process-local `JDK_JAVA_OPTIONS=-Djdk.net.unixdomain.tmpdir=<project>/android-app/android/.gradle`. A temporary ignored init script under `android-app/android/.gradle` inspected actual resolvable configurations, not the non-resolvable `implementation (n)` report. It checked external module artifact views, verified each file was nonempty and inside the D: Gradle cache, and resolved each project's buildscript classpath. No project build task ran.

The inspected `:app` configurations were `debugCompileClasspath` (70 external artifacts), `debugRuntimeClasspath` (107), `debugAnnotationProcessorClasspath` (0), `_agp_internal_javaPreCompileDebug_kspClasspath` (27), `kspDebugKotlinProcessorClasspath` (27), `kspPluginClasspath` (6), `kspPluginClasspathNonEmbeddable` (6), `kotlinCompilerClasspath` (8), `kotlinCompilerPluginClasspathDebug` (6) and `kotlinBuildToolsApiClasspath` (17). Across the app and nine included Capacitor projects, the probe checked 46 resolvable debug/Kotlin/KSP configurations and 11 buildscript classpaths. The generated local `app/libs` and Cordova `src/main/libs` directories contain no JARs.

The first `--offline` artifact-only probe failed for 33 configurations because the earlier `:app:dependencies` task had resolved the graph without fetching all artifact bytes. One online artifact-only resolution then completed `BUILD SUCCESSFUL in 1m 8s`. The same probe rerun `--offline` completed `BUILD SUCCESSFUL in 33s`: zero failures, 329 distinct nonempty external artifact files under the D: cache. At this point `caches/modules-2` contained 1,620 files / 305,444,049 bytes. Ignored local logs are `.gradle/codex-debug-task-plan.log`, `.gradle/codex-debug-artifacts-offline.log`, `.gradle/codex-debug-artifacts-online.log` and `.gradle/codex-debug-artifacts-offline-confirm.log`, all relative to `android-app/android`. This establishes availability for the inspected debug configurations, not that task-time transforms or compilation will succeed.

### Provenance boundary and exact next task

The Gradle wrapper distribution has a recorded SHA-256 pin and npm inputs have lockfile integrity, but neither independently verifies Gradle modules. Gradle's supported `--write-verification-metadata sha256,pgp` can bootstrap dependency verification; [Gradle's documentation](https://docs.gradle.org/current/userguide/dependency_verification.html) requires review of the resulting metadata and warns that task-time dependencies may be missed. The configured Google and Maven Central repositories and Gradle's downloaded-cache entries are the source of the current bytes, but no independently reviewed publisher checksum/signature set was available for the full resolved graph. `android-app/android/gradle/verification-metadata.xml` and Gradle lockfiles remain absent. Generating authoritative metadata from the current bytes alone would endorse an unverified first download, so none was generated. **NEW-002 remains PARTIALLY RESOLVED; the overall security gate remains FAIL.** The existing generated-input preflight still passed 19 tests. No Android build, APK/AAB, signing test or device verification occurred.

**Exact next task:** in a separate checkpoint, run the documented narrow offline `:app:assembleDebug` once with the process-local Java socket setting and D: cache, capture any task-time failure, and independently review Gradle dependency provenance before accepting the cache for release or recording verification metadata. Signed release and device verification remain later tasks. No commit or push.

## 24. Exact task-time AAPT2 provisioning — 2026-09-29

The first actual offline `:app:assembleDebug` stopped at `:app:compileDebugNavigationResources`: `:app:detachedConfiguration2` requested `com.android.tools.build:aapt2:8.13.0-13719691`, which was not cached. This continuation provisioned only that exact build-tool module; it did not rerun the build. The root `build.gradle` declares AGP `com.android.tools.build:gradle:8.13.0` and places `google()` before `mavenCentral()` for both buildscript and projects. Google's [repository documentation](https://developer.android.com/build/remote-repositories) identifies `https://dl.google.com/dl/android/maven2/` as its Maven endpoint and documents the Windows AAPT2 classifier naming convention.

At `https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/8.13.0-13719691/`, Google serves `aapt2-8.13.0-13719691.pom` (POM packaging; module coordinates match), `aapt2-8.13.0-13719691-windows.jar`, and SHA-256 sidecars for both. A `.module` URL returned 404, so POM is the available module metadata. Google's published SHA-256 values were `ad80277efc576ec7f0a71afe4d1d7b2b7dd7a7d486a3f709a2c5987ae9205854` for the POM and `273531f413184d00938178884b6c131b51fc45920d6b6bdc396438b06070895a` for the Windows JAR. No checksum was invented or taken from a random mirror.

A temporary ignored init script registered one Gradle task with a detached dependency on `com.android.tools.build:aapt2:8.13.0-13719691:windows`. With the existing D: `JAVA_HOME`, SDK, `GRADLE_USER_HOME`, `ANDROID_USER_HOME` and process-local `JDK_JAVA_OPTIONS=-Djdk.net.unixdomain.tmpdir=<project>/android-app/android/.gradle`, `gradlew.bat --no-daemon --console=plain --info --init-script .gradle/codex-aapt2-exact.init.gradle codexResolveExactAapt2` downloaded the POM and Windows JAR from the Google URL above and completed `BUILD SUCCESSFUL in 1m 4s`. The cached JAR is `android-app/android/.gradle/codex-home/caches/modules-2/files-2.1/com.android.tools.build/aapt2/8.13.0-13719691/a3a6f96d1adabdc8b426dad82176761d2431f0d1/aapt2-8.13.0-13719691-windows.jar` (2,240,596 bytes); the cached POM is under the same version directory's `ee728c95214dc788fe2657b0fe982b06c83add5a/` subdirectory (1,097 bytes). Local SHA-256 hashes of both match the Google sidecars above. `jar tf` read the Windows JAR and listed `aapt2.exe`.

The identical task with `--offline` completed `BUILD SUCCESSFUL in 23s`, resolving module `com.android.tools.build:aapt2:8.13.0-13719691` with classifier `windows` from the D: cache. The ignored logs are `android-app/android/.gradle/codex-aapt2-online.log` and `codex-aapt2-offline.log`; the temporary ignored init script was removed afterward. The sidecars support integrity against Google's own published bytes over HTTPS; they are not a separately signed attestation of the entire dependency graph. No authoritative `gradle/verification-metadata.xml` was generated. **NEW-002 remains PARTIALLY RESOLVED**, and no second Android build, APK/AAB, release or device verification occurred.

**Exact next task:** run one actual offline `:app:assembleDebug` in a separate checkpoint with the same D: cache and process-local Java socket setting; capture any new root failure, or verify the debug APK if successful. Full-graph dependency provenance, signed release and device checks remain separate later work. No commit or push.

## 25. NEW002-PROV-001 release-dependency provenance review — 2026-09-29

This is a scoped continuation after BUILD-DEBUG-001 and BUILD-APK-001 completed. `main` remains at `86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8`. No release build, signing, device test, dependency upgrade or product edit occurred. The root Gradle files use `google()` then `mavenCentral()` for buildscript and projects; the app also declares `flatDir` for local JAR directories. The inspected app and generated Cordova local JAR directories contained no JARs. `gradle/wrapper/gradle-wrapper.properties` pins Gradle 8.14.3. There is no version catalog, Gradle lockfile or `android-app/android/gradle/verification-metadata.xml` in the inspected project. The D: `files-2.1` module cache held 1,077 files (305,769,238 bytes: 541 POM, 206 module metadata, 234 JAR and 96 AAR). These cached files do not attest their own origin or full-graph integrity.

| Mechanism/artifact | Result and evidence | Classification |
| --- | --- | --- |
| Gradle 8.14.3 distribution | Wrapper `distributionSha256Sum=ed1a8d686605fd7c23bdf62c7fc7add1c5b23b2bbc3721e661934ef4a4911d7c` matches `https://services.gradle.org/distributions/gradle-8.14.3-all.zip.sha256`. This pin checks the distribution, not its dependencies. | VERIFIED for the configured distribution pin |
| AAPT2 8.13.0-13719691 | Existing §24 comparison matched Google's published sidecars for the POM and Windows JAR; the Windows JAR SHA-256 is `273531f413184d00938178884b6c131b51fc45920d6b6bdc396438b06070895a`. | VERIFIED for those two exact files only |
| Android Gradle Plugin 8.13.0 | Cached JAR `d0195874497b4ac3eaeb3a8525bf794d3a5b63a9a01084ca9ac330fb63060d01`, POM `ee4182f4b5cb6544f36d23db5d159674ca9ea3db05a8e474295afcfc6cf510da`, and `.module` `1ffebc2634d322d5ff1646fb54aa9cdaaa00ab5eb3900a193fa561b23e031a77` each matched the corresponding `.sha256` sidecar at `https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/8.13.0/`. | VERIFIED for those three exact files only |
| Room runtime 2.6.1 | Cached AAR `69624fd7add6ce5bfcc12362cd427341d2910e277ed5a6fcc46132a4899114d0`, POM `0e4150733d903468943f17dd9ceb4e828b26312966e2e13547a0e3aacd04299e`, and `.module` `828e4bead1b8d42ff17c41e74541133dc61a959b968f3c2a2221c24b3dac6c3b` each matched the corresponding `.sha256` sidecar at `https://dl.google.com/dl/android/maven2/androidx/room/room-runtime/2.6.1/`. | VERIFIED for those three exact files only |
| Kotlin Gradle Plugin 2.1.0 | The cached artifact is `kotlin-gradle-plugin-2.1.0-gradle85.jar` (local SHA-256 `caafc71157634bf7864f44026f5a63d256881c1cd9711456325266a53bafe728`). Its `.sha256` URL at the configured Maven Central endpoint returned HTTP 404. The local digest identifies cached bytes but is not an independent publisher comparison; no trusted PGP-key review was performed. | UNVERIFIED by the checked mechanism |
| Other Gradle modules and task-time release artifacts | The prior successful `:app:dependencies` log (`.gradle/codex-dependency-resolution-20260929.log`) includes release compile/runtime classpath trees, but it is graph resolution, not a full artifact provenance check. A focused offline `:app:dependencies --configuration releaseRuntimeClasspath` call in this continuation was interrupted when the command-runner host closed; its ignored log `.gradle/codex-new002-release-runtime-20260929.log` ends after project configuration and has no Gradle success/failure result. The same call was not retried. No release task was run, so task-time release dependencies remain unknown. | PARTIALLY VERIFIED graph visibility; full integrity/source provenance UNVERIFIED |
| Generated Android inputs | `tools/verify-android-generated-inputs.py` passed for locked CLI 8.5.0, seven Capacitor plugins and zero Cordova plugins; `tests/new002_android_generated_inputs_test.py` passed 19 checks. This validates generated-input consistency, not Gradle module provenance. | VERIFIED for the existing generated-input gate |

The publisher HTTPS checksum comparisons above are scoped to named artifacts and metadata; they are not independently signed attestations of the entire graph. The first AGP sidecar parser treated response bytes as decimal numbers; corrected ASCII decoding produced the matching 64-hex checksum reported above, so the initial apparent mismatch was a parsing error. A Gradle `--write-verification-metadata sha256,pgp` bootstrap would record current repository/cache bytes and, per [Gradle's verification guidance](https://docs.gradle.org/current/userguide/dependency_verification.html), requires trust review and can miss task-time dependencies when tasks are not executed. No authoritative metadata or lockfiles were generated from this incomplete evidence.

**Status and exact next action:** NEW002-PROV-001 is incomplete and NEW-002 remains **PARTIALLY RESOLVED**; the overall security gate remains **FAIL**. Within NEW002-PROV-001, obtain a reviewed source/checksum or authenticated signing-key basis for the remaining Google/Maven Central modules (including the Kotlin Gradle Plugin), establish the release task-time graph under an authorized check, then review and exercise Gradle verification metadata against that complete graph. If a full independent trust basis is unavailable, record a human-approved release-scope decision rather than treating cached bytes as verified. Do not start RELEASE-001 until the master plan's provenance gate is met or explicitly dispositioned.

## 26. NEW002-PROV-001 full declared-release artifact inventory — 2026-09-29

This continuation remained in the provenance task. It did **not** run `:app:lintRelease`, `:app:bundleRelease`, `:app:assembleRelease`, signing, device tests or product implementation. The release script names those three Gradle tasks; task execution dependencies remain a separate gate. All network lookups below used only the configured Google Maven (`https://dl.google.com/dl/android/maven2/`) and Maven Central (`https://repo.maven.apache.org/maven2/`) endpoints. The D: Gradle home and process-local `jdk.net.unixdomain.tmpdir` were retained.

An ignored Gradle init script enumerated external module artifacts from resolvable release, lint, KSP/Kotlin-tool and buildscript classpaths across 11 projects. The first probe used a generic artifact collection and failed on 16 release compile/runtime configurations because local Capacitor project variants had ambiguous artifact types; a narrow stack trace identified `ArtifactSelectionException`, not a missing external dependency or a release build failure. A corrected `artifactView` filtered to `ModuleComponentIdentifier`, and one `gradlew.bat --no-daemon --console=plain --init-script .gradle/codex-new002-release-inventory.init.gradle codexNew002ReleaseInventory` completed `BUILD SUCCESSFUL in 22s`: 127 configurations, 2,503 configuration/artifact rows, zero resolution failures. It found **329 distinct nonempty external JAR/AAR files from 328 modules**, all inside the D: Gradle cache. In `:app`, `releaseCompileClasspath` had 70 external artifacts, `releaseRuntimeClasspath` 107, `kspReleaseKotlinProcessorClasspath` 27 and `kotlinCompilerPluginClasspathRelease` 6. The ignored complete log and raw configuration mapping are `.gradle/codex-new002-release-inventory-fixed.log` and `.gradle/codex-new002-release-artifacts.tsv`. This is an artifact-only resolution, not a release build or task-time inventory.

For those 328 module coordinates, 470 cached POM/Gradle-module-metadata files were present (no module lacked cached metadata). A read-only SHA-256 comparison fetched the named file's `.sha256` sidecar from the two configured repositories over HTTPS; only an exact 64-hex digest equal to the locally computed file digest counted as a match. For unmatched lookups, **both configured sidecar URLs returned HTTP 404**; there were no digest mismatches, malformed sidecars or network errors in the recorded result. The tracked [file-level evidence table](NEW002_RELEASE_FILE_PROVENANCE.tsv) records every coordinate, filename, local byte count and SHA-256, comparison status, matched repository digest/URL or both 404 attempts. Local hashes in unmatched rows identify bytes only and do **not** confer provenance.

| Cached file class | Publisher/repository SHA-256 match | No `.sha256` sidecar at either configured endpoint |
| --- | ---: | ---: |
| 329 JAR/AAR artifacts | 184 (136 Google Maven; 48 Maven Central) | 145 |
| 470 POM/module metadata files | 317 (243 Google Maven; 74 Maven Central) | 153 |
| **799 files total** | **501** | **298** |

Across the 328 inventoried modules, 184 have a sidecar match for every cached artifact and metadata file inspected, 4 have partial coverage and 140 have no matched file. For the 145 artifact files lacking SHA-256 sidecars, a separate `HEAD` check found `.asc` signature files at configured repository URLs for 127, including the Kotlin Gradle Plugin `gradle85` JAR. This is **signature availability only**: no signature content, signer identity, authenticated key fingerprint or signature verification was reviewed. The other 18 artifacts had HTTP 404 for both `.sha256` and `.asc` at both configured endpoints; their exact coordinates are in the evidence table (notably legacy AndroidX artifacts, `javax.inject:javax.inject:1` and `net.sf.kxml:kxml2:2.3.0`). No SHA-1/MD5 value was promoted to a secure provenance substitute.

The declared-classpath inventory does not include the AAPT2 detached configuration previously observed only at debug task execution (`aapt2` has zero rows in this inventory). The exact release task-time dependency set cannot be inferred from the declared classpaths or Gradle `--dry-run`; the release tasks were deliberately not run in this checkpoint. No dependency-verification XML or lockfile was written: the 298 files without a published SHA-256 sidecar, 127 unreviewed signature/key chains, 18 files with neither checked mechanism, and unobserved release task-time artifacts prevent a trusted complete baseline. The publisher checksum matches remain scoped to named files and their current configured repository content, not an independent attestation of the whole supply chain. The existing Gradle distribution/AAPT2/AGP/Room evidence in §25 is preserved.

**Status / smallest next evidence requirement:** NEW002-PROV-001 remains **ACTIVE and incomplete**; NEW-002 remains **PARTIALLY RESOLVED**, overall security gate **FAIL**. A reviewer must establish an authenticated trust basis for the 127 signature candidates and independent evidence or an explicit release-scope disposition for the 18 files lacking both mechanisms; then cover the release task-time set under an authorized release check and exercise reviewed Gradle verification metadata. Until that evidence or a documented human release-scope decision exists, RELEASE-001 remains blocked. No dependency version or repository was changed.
