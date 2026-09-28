# NEW-001 — AAB JAR signature reader inconsistency

## STATUS

**RESOLVED — SOURCE/RELEASE TOOLING.** Verified 2026-09-14.

The release gate now normalizes the AAB's JAR metadata order without changing any entry. It proves the order and fails if `jarsigner` reports that `JarFile` and `JarInputStream` disagree. The fix was verified on synthetic signed archives and on a scratch copy of the published AAB. A fresh Gradle-built, upload-key-signed release run was **not** performed: no signing key, the recorded Gradle blocker, and NEW-002. The overall security gate remains **FAIL** because NEW-002 and other recorded limitations remain.

## Finding

`outputs/SECURITY_VERIFICATION.md` §F NEW-001: the published AAB passes `jarsigner -verify` (“jar verified”), but `jarsigner -verify -strict` returns 4 and reports entries signed in `JarFile` but not in `JarInputStream`. `META-INF/MANIFEST.MF` comes after `UPLOAD.SF`/`UPLOAD.RSA`. `tools/build-play-release.sh` accepted the non-strict result. Required remediation: conventional ordering, `-strict` exit 0, keep Bundletool validation, and document the Play upload transformation. It was discovered during the release-artifact signature review of the earlier security verification.

## Original severity

MEDIUM (assessed at discovery); production blocker YES.

## Current severity

**LOW** for security; it remains a release-integrity defect. Independent verification refined the original conclusion:

- **Reproduced:** the local published AAB (`work/app-release.aab`, SHA-256 `10F302B6…BF9C`, 506 entries) has `MANIFEST.MF` at entry **506 of 506**, after `UPLOAD.SF` (504) and `UPLOAD.RSA` (505); the audit said 505. Non-strict verification exits 0 and prints “This JAR file contains internal inconsistencies…”, “Manifest is missing when reading via JarInputStream”, and every entry as signed in `JarFile` only.
- **Corrected:** strict exit code 4 is caused by the **self-signed upload certificate** (chain not validated), not by the ordering. With only the signer certificate trusted, `-strict` exits **0 on the unmodified manifest-last AAB** while still printing the inconsistency. With default trust, a correctly ordered AAB still exits 4. “Require `-strict` exit 0” would therefore reject every legitimate self-signed Play upload key and still miss this defect. It was not adopted.
- **No exploit demonstrated:** no tampered bundle was demonstrated. The certificate SHA-256 pin, full `JarFile` verification and Play-side validation remain. The risk is that two standard verifiers disagree about signer coverage of the same artifact, so a streaming verifier can see no signature at all.

## Applicability

- **AAB (Play upload):** applicable. This is the artifact produced by AGP 8.13.0 `bundleRelease` with a standard `signingConfig` (`android-app/android/app/build.gradle:69-84`). No project code writes the order.
- **Release tooling:** applicable (`tools/build-play-release.sh` step 4).
- **APK:** not applicable. It is verified with `apksigner` (v2 scheme, one signer, pinned certificate).
- **Browser build, runtime app code, audit reports:** not applicable.
- **SEC-001–016:** none of those changes touched signing, Gradle signing configuration or this gate.

## Exact affected components

- `tools/build-play-release.sh` step “4/7 validating AAB and APK signatures” (pre-change lines 228–245): accepted a manifest-last AAB.
- AGP 8.13.0 bundle signing output (`android-app/android/build.gradle:10`): root cause of the order. It is a dependency and was not changed.
- Downstream consumers of the signed AAB: step 5 `tools/verify-release-assets.py --aab`, the upload-certificate pin, Play upload.

## Data/control flow

**Before:**
1. `gradlew :app:bundleRelease` signs the AAB; the JAR is written with `.SF`/`.RSA` and then `MANIFEST.MF` last.
2. `jarsigner -verify` (`JarFile`, central directory) prints “jar verified.”, and the grep passes.
3. The `-verbose -certs` checks and the certificate SHA-256 pin pass.
4. The AAB is accepted, although `JarInputStream` sees no manifest and treats all entries as unsigned.

**After:**
1. `gradlew :app:bundleRelease` produces the signed AAB as before.
2. `python3 tools/normalize-aab-signature-order.py "$AAB_PATH"`:
   - Fails closed on duplicate names, a missing manifest or missing signature files.
   - If the order is not already conventional, rewrites it atomically as `[META-INF/] MANIFEST.MF, *.SF/*.RSA/*.DSA/*.EC/SIG-*, rest in original order`.
   - Proves every entry is unchanged: name set, bytes, compression method, timestamp and attributes.
3. `--check` re-proves the order; `JarInputStream` needs the manifest first and signature files before signed content.
4. `jarsigner -verify` must print “jar verified.” and must **not** report internal inconsistencies, “not signed in JarInputStream”, or a missing `JarInputStream` manifest.
5. The existing unsigned-entry, validity and disabled-algorithm checks run, then the upload certificate SHA-256 pin, APK `apksigner` checks and step 5 asset verification on the normalized AAB.

JAR v1 signatures bind entry contents through `MANIFEST.MF` digests signed by the `.SF`/block file, not ZIP order. Reordering therefore keeps the signature valid, as verified below.

## Threat model

| Actor | Before | After |
| --- | --- | --- |
| Attacker able to alter a built artifact before upload (compromised CI/workstation or artifact store) | Tampering is still detected by `JarFile` verification and Play. A streaming verifier or pipeline check sees the artifact as unsigned, so signer coverage is ambiguous. | Both reader models see the same signed view; tampered content still fails `jarsigner` (test proves normalization does not bless tampering). |
| Downstream strict or streaming verifier | Rejects or treats the AAB as unsigned; results differ by parser. | Consistent result. |
| Remote/network attacker, app user | No path. | No path. |

## Attack preconditions

Write access to the AAB between build and upload, or a consumer relying on a streaming JAR verifier. There is no remote trigger and no runtime or device impact. The maintainer's upload key is not exposed.

## Impact

Before: release validation reported success for an AAB whose signature coverage depended on the reader. This weakens supply-chain verification guarantees and can cause strict tooling rejections. No confidentiality impact, no runtime impact, and no demonstrated signature bypass.

## Existing mitigations

- Pre-existing: full `JarFile` signature verification; unsigned-entry, validity and disabled-algorithm checks; upload certificate SHA-256 pin; `apksigner` v2 verification for the APK; Bundletool validation (1.18.3 passes on the original); Play's own upload verification; Gradle refusing unsigned release builds.
- None of these detected the reader differential.

## Remediation

1. **New `tools/normalize-aab-signature-order.py`:** a content-preserving, fail-closed normalizer with a `--check` mode, stdlib-only Python. It does not verify signatures; `jarsigner` remains the verifier.
2. **`tools/build-play-release.sh` step 4:** runs the normalizer and `--check`, then rejects any `jarsigner` reader-inconsistency report. The change is 11 added lines and nothing else. The comment documents why `-strict` is not the gate.
3. **New `tests/new001_aab_signature_order_test.py`:** a focused regression test.

Play upload transformation: the uploaded file is the normalized AAB. Its signature, signer certificate and all 506 entries are unchanged. Bundletool validation passes before and after.

## Compatibility

- Signed contents, signer certificate, entry names, bytes, compression methods, timestamps and attributes are all preserved.
- ZIP order and container bytes change, so the AAB file SHA-256 differs from Gradle's raw output. The script prints the final artifact hash, as before.
- An already conventional AAB is left byte-for-byte untouched.
- Normalization happens before step 5, so asset verification reads the uploaded bytes.
- APK handling is unchanged.
- Requires only `python3` and `jarsigner`, both already required tools.
- The release script worktree copy keeps its existing CRLF convention (index LF); the change is ASCII-only.

## Files changed

1. `tools/build-play-release.sh`: 11 added lines in step 4.
2. `tools/normalize-aab-signature-order.py` (new).
3. `tests/new001_aab_signature_order_test.py` (new).
4. `PROJECT_MASTER/SECURITY_REMEDIATION_NEW001.md` (new): this report.
5. `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md` and `PROJECT_MASTER/CHANGELOG.md`: NEW-001 status.

Evidence outside the repository is in `work/new001/`: `pre_hashes.tsv`, `reorder_probe.py`, `reordered-probe.aab`, `published-copy.aab` (normalized scratch copy), `upload-cert.pem` and `probe-truststore.jks` (public certificate only, probe password), `new001_test.out.txt`, `syntax_probe.sh`. The published `work/app-release.aab` was only read; its hash is unchanged.

## Files intentionally unchanged

- `android-app/android/app/build.gradle`, `android-app/android/build.gradle` (AGP version and signing config), `gradle.properties`, `keystore.properties*`.
- `tools/verify-release-assets.py`.
- APK `apksigner` checks; `tests/android_release_optimization_test.py`; `tests/hybrid_drive_contract_test.py`.
- Dependencies and lockfiles.
- All SEC-001–016 remediation files.
- All NEW-002 surfaces: Cordova generated inputs, `cap sync`, Gradle `--offline` bootstrap.

## Tests and exact results

| Check | Result |
| --- | --- |
| `python tests/new001_aab_signature_order_test.py` | **PASS (17 checks)**. It uses a throwaway RSA key and JDK jarsigner. A manifest-last fixture reproduces the reader differential, and `--check` rejects it. The normalizer rewrites it with manifest and signatures first, with identical bytes, compression, timestamps and attributes. It then verifies with no inconsistency and passes `--check`. An already conventional archive stays byte-identical, and jarsigner's native order is accepted. Tampered content still fails jarsigner after normalization. Unsigned, duplicate-name and missing archives fail closed. Release step order: normalize, check, verify, reject differential, then certificate pin. The differential is a release failure, asset verification follows, and the certificate pin is preserved. |
| Published AAB, scratch copy | Before: `--check` FAIL (“MANIFEST.MF is entry 506 of 506”); non-strict jarsigner reports the internal inconsistency. After normalizing: `--check` PASS; a second run reports “already conventional”. `jarsigner -verify` exit 0, “jar verified.”, no inconsistency. `-strict` with only the signer certificate trusted: exit 0, no inconsistency. `-strict` with default trust: exit 4 (self-signed chain, expected). Bundletool 1.18.3 `validate`: exit 0 (also exit 0 on the original). Signer SHA-256 `29:6F:94:…:AC:8C` matches the release-script pin. Entry set identical (506), all bytes identical. Original published file hash unchanged. |
| Root-cause isolation probe | Original, trusted signer: strict exit 0 but inconsistent. Reordered, default trust: strict exit 4 but consistent. This shows strict exit status and ordering are independent. |
| `bash -n tools/build-play-release.sh` (Git Bash 5.2.37) | OK. |
| Line-ending/diff scope | Worktree uniformly CRLF (330/330) as before, 0 non-ASCII bytes; `git diff --ignore-cr-at-eol` shows exactly 11 added lines in step 4. |
| `python -m py_compile tools/normalize-aab-signature-order.py` | exit 0 (bytecode removed afterwards). |
| `python tests/android_release_optimization_test.py` | PASS. |
| `python tests/hybrid_drive_contract_test.py` | Default run fails with a **pre-existing environment issue unrelated to NEW-001**: it reads UTF-8 files with the Windows cp1251 default (`UnicodeDecodeError` at byte 68395 of a large file). With `PYTHONUTF8=1`: **PASS**. Not modified. |
| Before/after hash scope | Changed: `tools/build-play-release.sh` and the three PROJECT_MASTER status docs. New: `tools/normalize-aab-signature-order.py`, `tests/new001_aab_signature_order_test.py`, this report. Test-generated `__pycache__` was removed first. One additional new file was **not written by this task**: `PROJECT_MASTER/PRODUCT_IMPLEMENTATION_ROADMAP.md`, 51,859 bytes, SHA-256 `DB58424F…F98C`. It was created 2026-09-14T23:17:38+05:00, after the NEW-001 pre-snapshot (23:11:54) and before this report. It declares itself a separate product-planning document that implements nothing. It was left untouched and is outside NEW-001 scope. |

## Limitations

- No end-to-end `tools/build-play-release.sh` run: it needs the private upload keystore, Gradle offline release build (recorded Windows `AccessDeniedException`) and NEW-002's generated-input bootstrap.
- AGP's raw manifest-last output was demonstrated on the previously published artifact, not rebuilt from the current tree.
- No Play Console upload, device install, or `apksigner`/APK run for this change (APK path unchanged).
- The jarsigner inconsistency message is a secondary gate that depends on JDK wording. The Python `--check` structural gate is primary and wording-independent.
- `JarInputStream` behavior was verified through jarsigner's reader comparison, not a separate Java harness.

## Remaining risk

- If a future AGP emits different metadata (for example additional signature schemes inside META-INF), `--check` or the inconsistency gate fails closed and needs review.
- Release provenance still depends on a trusted build host; NEW-002 reproducibility remains open.
- Pre-existing, out of scope: `hybrid_drive_contract_test.py` default-encoding failure on this Windows host; SEC-002/SEC-004 contract drifts recorded in the SEC-016 report.

## Preservation of SEC-001–016

No SEC-001–016 file or control was modified. The release script retains every previous check (identity, manifest policy, permissions, certificate pin, `apksigner` v2, asset mirrors, key-shaped secret scan, forbidden data packs). The release optimization test passes. SEC-001–016 statuses in `SECURITY_STATUS.md` are unchanged apart from the NEW-001 row and link.

## NEW-002 remains untouched

No change to Cordova generated files, `npx cap sync`, `cordova.variables.gradle`, the Gradle offline/cache bootstrap or clean-build preflight. The NEW-002 row stays PENDING — RELEASE BLOCKER.

## Next task

**NEW-002** — clean-build sync/generated Cordova assets and offline cache bootstrap reproducibility.

## CODEX HANDOFF

- **Exact task:** NEW-001 only.
- **Final status:** RESOLVED — SOURCE/RELEASE TOOLING. Current severity LOW (originally MEDIUM). No fresh signed release run.
- **What was investigated:** `outputs/SECURITY_VERIFICATION.md` §NEW-001/NEW-002 context; `tools/build-play-release.sh`; `android-app/android/app/build.gradle` signing configuration; AGP version (`android-app/android/build.gradle`); existing tests reading the release script (`android_release_optimization_test.py`, `hybrid_drive_contract_test.py`); published `work/app-release.aab` with JDK `jarsigner`/`keytool` and Bundletool 1.18.3; trust-isolation and reorder probes.
- **Exact root cause:** AGP 8.13.0 AAB signing writes `META-INF/MANIFEST.MF` after the `.SF`/`.RSA` files (entry 506/506). `JarInputStream` therefore sees no manifest and all entries as unsigned, while `JarFile` verifies them. The release gate checked only non-strict “jar verified.” Strict exit 4 is an unrelated self-signed-chain result.
- **Attack path/preconditions:** requires write access to the AAB between build and upload, or a downstream streaming/strict verifier; creates verifier disagreement about signer coverage. No remote or runtime path; no bypass demonstrated.
- **Impact:** release validation could accept a reader-dependent signature view. Supply-chain verification ambiguity; no runtime, user-data or key exposure.
- **Remediation:** content-preserving, fail-closed metadata-order normalizer plus structural `--check`, and a jarsigner reader-inconsistency gate in release step 4. `-strict` exit 0 deliberately not required (it would reject valid self-signed upload keys and does not detect this defect).
- **Files changed:** `tools/build-play-release.sh`; `tools/normalize-aab-signature-order.py` (new); `tests/new001_aab_signature_order_test.py` (new); `PROJECT_MASTER/SECURITY_REMEDIATION_NEW001.md` (new); `PROJECT_MASTER/SECURITY_STATUS.md`; `PROJECT_MASTER/PROJECT_STATUS.md`; `PROJECT_MASTER/CHANGELOG.md`.
- **Files unchanged:** Gradle build/signing config and AGP version; `tools/verify-release-assets.py`; APK checks; existing tests; dependencies/lockfiles; all SEC-001–016 files; all NEW-002 surfaces.
- **Tests/results:**
  - NEW-001 test PASS (17).
  - Published-AAB copy: `--check` FAIL before / PASS after; jarsigner consistent; strict with trusted signer exit 0; Bundletool validate exit 0; certificate and entries unchanged.
  - `bash -n` OK; `py_compile` OK; release optimization PASS.
  - `hybrid_drive_contract_test.py` fails only under the Windows cp1251 default and PASSES with `PYTHONUTF8=1` (pre-existing).
- **Limitations:** no keystore/Gradle end-to-end release run, Play upload or device verification; AGP raw output not rebuilt from the current tree.
- **SEC-001 through SEC-016 preservation:** unchanged; statuses preserved.
- **NEW-002 status:** untouched (PENDING — RELEASE BLOCKER).
- **Exact next task:** **NEW-002**, handled independently in its own scoped session. Read `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`, this report and `outputs/SECURITY_VERIFICATION.md` §NEW-002 first. Keep `tests/new001_aab_signature_order_test.py` passing and do not remove the step-4 normalizer/gate.
- **Current HEAD:** `f282454e8fb79a529894598b0af9a3d7008fd84c` (unchanged). Working tree = pre-existing uncommitted SEC-001–016 changes plus the NEW-001 files above. It also contains `PROJECT_MASTER/PRODUCT_IMPLEMENTATION_ROADMAP.md`, created concurrently by a separate product-planning session during this task; not NEW-001 work and not modified here. Git requires `-c safe.directory=...`.
- **Commit/push status:** no commit, no push.
