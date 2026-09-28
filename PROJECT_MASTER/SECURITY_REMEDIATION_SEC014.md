# SEC-014 — FileProvider roots and URI exposure

## 1. STATUS

**RESOLVED — SOURCE/STATIC.** Verified 2026-09-14.

Severity is INFO (original classification preserved). The provider was over-broad, not exploitable: no path was found for an unrelated app to obtain a URI without an in-app grant. The two whole-root aliases were narrowed to the only directories any grant uses. A 25-check contract passes. There is no Android build, device or instrumented verification (§11). The overall security gate remains **FAIL** because of existing blockers.

## 2. Finding

Audit (`outputs/SECURITY_AUDIT.md` §SEC-014; `outputs/SECURITY_VERIFICATION.md` §SEC-014): `external-files-path` and `cache-path` used `path="."`. The provider is `exported="false"` and requires grants, but broad roots increase what a mistaken or malicious in-app share can grant. The email composer also reuses a deterministic filename. The recommendation was dedicated share directories, unique names, read-only grants, and revoking expired grants.

## 3. Applicability

**Applicable, as a least-privilege violation.** At HEAD `f282454`, `my_images` mapped all of `getExternalFilesDir(null)` and `my_cache_images` mapped all of `cacheDir`. No legitimate caller needs either whole root.

The `cacheDir` root holds the legacy Camera plugin's processed temp photos, which carry copied EXIF including possible GPS (`LegacyCameraFlow.saveImage`/`getTempFile`, `:517-550`), plus WebView/HTTP and other plugin cache. Such files became grantable by any in-process `.fileprovider` caller given a `file:` path.

**Not exploitable by an unrelated app.** Declaring the provider unexported with `grantUriPermissions="true"` means another app gets access only through a grant carried by an Intent this app starts.

## 4. Exact FileProvider data flow

Complete `.fileprovider` caller inventory, enforced by the contract:

| Caller | Grant | File actually granted | Alias after fix |
| --- | --- | --- | --- |
| `DriveModePlugin.shareFootage` (`:1521-1554`); JS History “Share” (`index.html:1655-1660`) | `ACTION_SEND_MULTIPLE` via chooser, `FLAG_GRANT_READ_URI_PERMISSION` only | Room `footage_segments` paths under `files/footage/<session>/` (`NativeDriveCameraManager.kt:797`) | `drive_footage` → `footage/` (unchanged) |
| `@capacitor/share` `SharePlugin.shareFiles` (`:141-179`); JS `shareEvidence` (`index.html:2346-2360`) and `shareZip` (`:5620-5637`) | `ACTION_SEND(_MULTIPLE)` via chooser, READ only | Base64 evidence `issue-<id>.jpg` / dataset `road-damage-dataset-<ms>.zip` written to `CACHE/pothole-reporter-shares/` (`SHARE_CACHE_DIR`, `:4357`) | `my_cache_images` → **`pothole-reporter-shares/`** |
| `capacitor-email-composer` `AssetUtil.getUriForBase64Content` (`:122-153`); JS `EmailComposer.open` type `base64` (`standalone.js:10156-10163`) | email-app chooser. Multi-attachment adds READ; single `ACTION_SEND` gets READ from platform ClipData migration | `externalCache/email_composer/<issue>.jpg` (fixed name) | `email_composer_attachments` → `email_composer/` (unchanged) |
| Camera `LegacyCameraFlow.openCamera` (`:261-273`) using `CameraUtils.createImageFile` (`:20-28`); JS `camera.getPhoto({allowEditing:false, source:"CAMERA"})` (`index.html:4295-4303`) | `ACTION_IMAGE_CAPTURE` output, READ\|WRITE to the camera app | `getExternalFilesDir(Pictures)/JPEG_*.jpg` | `my_images` → **`Pictures/`** |
| Capacitor core `BridgeWebChromeClient.createImageFileUri` (`:454-466`); `<input type=file capture>` (`index.html:86`) | image-capture chooser, READ\|WRITE | `getExternalFilesDir(Pictures)/JPEG_*.jpg` | `my_images` → **`Pictures/`** |
| `LegacyCameraFlow.createEditIntent` (`:758-767`) | ACTION_EDIT, READ\|WRITE | cache-root temp image | **Not reached:** runs only when `getAllowEditing()` (`:572`), and the app passes `allowEditing:false` |
| `AndroidAppMediaCleanup.revokeFile` / prefix revocation (`:20-23, :90-99, :115-121`) | revokes only | all four aliases | alias names unchanged |

`IonCameraFlow` (`AUTHORITY = ".camera.provider"`, `:74`) and the IonCamera AAR use the library's own provider, whose class scan found no `.fileprovider` string. The app's only Camera call, `getPhoto`, routes to the legacy flow (`CameraPlugin.kt:95-97`). The Filesystem, Geolocation, App and AppLauncher plugins and the Cordova bridge module contain no FileProvider callers. Capacitor core `AssetUtil` uses an undeclared `.provider` authority and is unused.

## 5. Exposed roots and reachable paths

| Alias | Before (HEAD) | After |
| --- | --- | --- |
| `drive_footage` | `filesDir/footage/` (clips + sparse keyframe JPEGs) | same |
| `my_images` | **entire** `externalFilesDir` | `externalFilesDir/Pictures/` |
| `my_cache_images` | **entire** `cacheDir` (camera temp photos with EXIF, WebView/HTTP/plugin cache, share copies) | `cacheDir/pothole-reporter-shares/` |
| `email_composer_attachments` | `externalCache/email_composer/` | same |

**Never reachable through the app provider, before or after:** Keystore-encrypted credentials (`shared_prefs/`, SEC-001); Room `native_potholes.db` with GPS tracks (`databases/`, SEC-013); IndexedDB/localStorage (`app_webview/`); `files/reports/`, `files/repair_targets/`, `noBackupFilesDir` AI budget; `Documents/pothole-frames` (shared storage). FileProvider canonicalizes paths, so a symlink or `..` cannot escape a root.

The separate library-owned `.camera.provider` (IonCamera AAR `ioncamera_paths.xml`) maps `files`, `cache`, `external-files`, `external-cache`, `external` and `external-media` roots at `.`. It is also unexported and grant-only. The app never mints its URIs, because it does not call IonCamera methods. SEC-002 Delete All revokes its prefixes. It is recorded as a dependency limitation and was not overridden (§11).

## 6. URI grant/export/IPC analysis

- **Exported components:** only `MainActivity`, with MAIN/LAUNCHER. It has no VIEW/SEND/data filters and does not read incoming intent data. The FileProvider, `DriveForegroundService` and `NotificationActionReceiver` are `exported="false"`. The manifest has no `<grant-uri-permission>` narrowing and no path permissions; grants are the only access mechanism.
- **Temporary vs persistable:** all grants are temporary Intent grants, READ for shares/email and READ|WRITE only for the camera output target. No `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`, `FLAG_GRANT_PREFIX_URI_PERMISSION` or `takePersistableUriPermission` exists in app, Capacitor core or plugin sources. An Intent grant lives while the receiving component/task holds it; it does not survive `revokeUriPermission`.
- **Recipients:** always a user-chosen chooser target or the system camera/email app, never an app-selected package.
- **WebView bridge:** Share, EmailComposer and DriveMode `shareFootage` do not check `NativeBridgeAuthorization.isTrustedMainDocument`, which is used by ManagedMedia/credentials. The bridge serves only the bundled `https://localhost` origin; `capacitor.config.json` has no `allowNavigation`. SEC-009 CSP restricts scripts. Share accepts any `file:` path, and email accepts an `absolute` type the app never uses. So only malicious same-origin JavaScript could ask for other files, still limited to the four narrowed roots and to a user-selected recipient.
- **Email fixed name:** a stale grantee of `email_composer/pothole.jpg` could read a later overwrite. ManagedMedia `endOperation` → `finish("email")` deletes composer files through `OwnedMediaCleanup.remove`, which revokes each URI for all grantees before deletion (SEC-002). The plugin also clears the folder on load. Residual exposure: only while a new composer session is open after an abnormal end of the previous one.
- **Share lifetime:** `finish("share")` intentionally keeps files, because a recipient may still be reading. Evidence names are per report and dataset names are timestamped; files and grants persist until Delete All or the end of the recipient task.

## 7. Threat model

| Actor | Result |
| --- | --- |
| Unrelated installed app, no grant | Cannot open any `content://dev.aiengg.potholereporter.fileprovider/...` URI (unexported provider; no path found). |
| Share/email/camera recipient chosen by the user | Reads only the intended file. With the old config, a stale grant to a reused name could read later content in that same file. |
| Compromised same-origin JavaScript (XSS/supply chain) plus a user tap | Before: could share any file in all of `cacheDir`/external files (e.g. EXIF-bearing camera temps). After: footage, Pictures captures, share copies and email temps only. Credentials/DB/reports were never reachable. |
| Unlocked device / root | Out of provider scope (SEC-013 device-protection model). |

## 8. Remediation decision

The change is justified: it enforces least privilege on an actual over-broad reach, with no behavior change for any existing caller. `file_paths.xml` now maps `my_images` to `Pictures/` and `my_cache_images` to `pothole-reporter-shares/`. Alias names are kept, so SEC-002 prefix revocation and any old outstanding prefixes still match.

Not changed, with reasons: `drive_footage` is already scoped to footage. Unique email attachment names would change a user-visible filename, and SEC-002 revocation already mitigates reuse. IonCamera's provider is dependency-owned and unused, and overriding its resources risks a future IonCamera flow. Adding plugin-level origin checks would mean patching node_modules; SEC-009 CSP and the local-only origin already cover this. No dependency, JS, Kotlin behavior or manifest change was needed.

## 9. Exact files changed

1. `android-app/android/app/src/main/res/xml/file_paths.xml`: narrowed two paths and added per-alias comments.
2. `android-app/android/app/src/androidTest/java/dev/aiengg/potholereporter/media/AppMediaCleanupInstrumentedTest.kt`: the grant-revocation fixture now seeds in `cacheDir/pothole-reporter-shares/` so `.fileprovider` can still map it (1 line + comment). SEC-002 test semantics are unchanged.
3. `tests/sec014_fileprovider_contract_test.py` (new): 25-check static contract.
4. `PROJECT_MASTER/SECURITY_REMEDIATION_SEC014.md` (new): this report.
5. `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md` and `PROJECT_MASTER/CHANGELOG.md`: SEC-014 status.

Evidence outside the repository is in `work/sec014/`: pre-hash snapshot, `sec014_contract.out.txt`, `sec002_digest_probe.py`, `sec002_replay_lock_substituted.py`, `mutation_probe.py`, `file_paths.HEAD.xml`, `sources_probe.py`.

## 10. Verification/tests

| Check | Result |
| --- | --- |
| `python tests/sec014_fileprovider_contract_test.py` | **PASS, 25 checks**: exact roots and no whole-root alias; revocation aliases match; one provider, unexported with grants; service/receiver unexported; launcher-only activity; all 10 app/core/plugin/Cordova source trees scanned; exact 7-file `.fileprovider` caller set; footage share READ-only on Room clips under `footage/`; camera/WebView captures in Pictures; legacy edit guarded and app `allowEditing:false`; IonCamera uses `.camera.provider`; both native shares write to `CACHE/pothole-reporter-shares`; email base64-only to `email_composer/`; no persistable/prefix grants; instrumented fixture inside the narrowed alias; 4 web mirrors identical. The first run failed at the source-presence check because the filesystem/geolocation plugins have no `src/main/java`. The test now scans whole `src/main` trees. |
| Mutation probe against `git show HEAD:…/file_paths.xml` | HEAD config **REJECTED** (broad `my_images`, `my_cache_images` at `.`); working tree PASS. |
| `python tests/android_release_optimization_test.py` | PASS (includes the unchanged email alias line and mirror verifier). |
| `python tests/sec002_media_cleanup_contract_test.py` | **FAIL at baseline, before any SEC-014 edit.** Only mismatch: `android-app/package-lock.json` digest, a pre-existing consequence of the SEC-008 xmldom lock update. Replaying the unchanged test in memory with only that digest substituted: **PASS, 68 checks**, after the SEC-014 change. The repository test was not edited (SEC-002/008 scope). |
| IonCamera AAR class scan (Gradle transform cache) | Only `.camera.provider` authorities; no `.fileprovider`. |
| Changed-file scope (SHA-256 before/after, excluding build/node_modules/.git) | Exactly the files in §9 differ or are new. Running the release test generated `tools/__pycache__/verify-release-assets.cpython-314.pyc`; that byproduct was removed and scope was re-verified. SEC-002-audited plugin sources are unchanged: the only digest mismatch remains the pre-existing lock file. HEAD unchanged. |

**Not run:** Gradle build/aapt resource compile, JVM or instrumented tests, APK manifest merge, ADB/device checks of camera capture, WebView file-input capture, Share, email or footage share. Playwright/browser suites were not run. These were skipped deliberately under the recorded Windows Gradle `AccessDeniedException` and no-device constraints.

## 11. Remaining limitations

- Runtime not proven: `FileProvider.getUriForFile` resolution for `Pictures/` and `pothole-reporter-shares/` on a device, including the external-files primary volume, and all five grant flows. The instrumented test, including the edited fixture, was not compiled or executed.
- IonCamera's dependency-owned `.camera.provider` keeps `.` roots, including shared external storage. It is unexported and not minted by current app code; reassess if `takePhoto`/`chooseFromGallery`/`editPhoto`/`recordVideo` are adopted.
- Plugins accept arbitrary `file:`/absolute paths from same-origin JavaScript. Exposure is now bounded to the four roots, and the app provides no origin check inside third-party plugins.
- Share copies and their grants persist until Delete All or the end of the recipient task. Email fixed-name reuse is mitigated but not eliminated after an abnormal composer exit.
- The pre-existing SEC-002 contract digest for `package-lock.json` is stale and needs a separate SEC-002/008 maintenance update.

## 12. Preservation of SEC-001–013

No credential, cleanup-engine, transport, pack, inference, budget, workflow, dependency, CSP, image-budget, tooling or GPS-history code was changed. `AndroidAppMediaCleanup` alias names and prefix revocation (SEC-002) are intact; the in-memory SEC-002 replay passes 68 checks. The only SEC-002 artifact touched is the instrumented fixture location, which keeps the same assertions. SEC-001–013 statuses are unchanged. SEC-015 and later were not started.

## 13. Overall security-roadmap status

```text
SEC-001 = PARTIALLY RESOLVED
SEC-002 = PARTIALLY RESOLVED
SEC-003 = PARTIALLY RESOLVED
SEC-004 = PARTIALLY RESOLVED
SEC-005 = PARTIALLY RESOLVED
SEC-006 = RESOLVED — SOURCE LEVEL
SEC-007 = RESOLVED — SOURCE/STATIC
SEC-008 = RESOLVED — DEPENDENCY/TOOLCHAIN
SEC-009 = RESOLVED — SOURCE/BROWSER
SEC-010 = PARTIALLY RESOLVED — SOURCE/BROWSER
SEC-011 = RESOLVED — INFO / TOOLING DISPOSITION
SEC-012 = RESOLVED — APPLICABILITY ONLY
SEC-013 = PARTIALLY RESOLVED — DISPOSITION COMPLETE; PRODUCT DECISION OPEN
SEC-014 = RESOLVED — SOURCE/STATIC
SEC-015 = NOT STARTED (recorded PENDING)
SEC-016 = NOT STARTED (recorded PENDING — BROWSER ONLY)
NEW-001 = NOT STARTED (release blocker)
NEW-002 = NOT STARTED (release blocker)
Overall gate = FAIL
```

## 14. CODEX HANDOFF / CONTINUATION CHECKPOINT

- **Exact task completed:** SEC-014 only. Investigated the FileProvider roots and URI exposure, and narrowed the app FileProvider.
- **Final SEC-014 status:** RESOLVED — SOURCE/STATIC. The provider was over-broad, not exploitable. There is no Android runtime/device verification and no independent production blocker.
- **Files/components investigated:** `AndroidManifest.xml`; `res/xml/file_paths.xml`, `backup_rules.xml`, `data_extraction_rules.xml`; `MainActivity.java`; `plugin/DriveModePlugin.kt` (`shareFootage`, `deleteFootage`, Delete All); `media/AndroidAppMediaCleanup.kt`, `OwnedMediaCleanup.kt`, `ManagedMediaPlugin.kt`; `security/NativeCredentialPlugin.kt` (`NativeBridgeAuthorization`); `drive/NativeDriveCameraManager.kt`; `androidTest/.../AppMediaCleanupInstrumentedTest.kt`; `static/index.html` (share, zip, camera, file input, History share); `static/standalone.js` (email, evidence/zip naming); `capacitor.config.json`. From node_modules: `@capacitor/share` SharePlugin; `capacitor-email-composer` AssetUtil/EmailComposer/EmailComposerPlugin; `@capacitor/camera` CameraPlugin/CameraUtils/LegacyCameraFlow/IonCameraFlow; `@capacitor/android` BridgeWebChromeClient/AssetUtil. Also the plugin manifests, the packaged debug manifest (build intermediates), the IonCamera AAR `ioncamera_paths.xml` and classes, `tests/sec002_media_cleanup_contract_test.py`, `tests/android_release_optimization_test.py`, and the audit/verification SEC-014 sections.
- **Exact data flow:** §4. Five callers mint `.fileprovider` URIs into four directories (`footage/`, external `Pictures/`, `cache/pothole-reporter-shares/`, external-cache `email_composer/`) via temporary chooser/camera Intent grants. Delete All revokes all alias prefixes; email finish revokes per file.
- **Exact remediation:** `my_images` `.` → `Pictures/`; `my_cache_images` `.` → `pothole-reporter-shares/`; the instrumented fixture moved inside the new alias; a static contract test was added.
- **Exact files changed:** §9 items 1–5.
- **Deliberately not changed:** `drive_footage`/`email_composer` aliases; `AndroidManifest.xml`; all Kotlin/Java main sources; JS/web mirrors; node_modules and IonCamera provider; dependencies and lockfiles; `tests/sec002_media_cleanup_contract_test.py` (stale lock digest left for SEC-002/008 maintenance); privacy notice; SEC-001–013 and SEC-015+ code.
- **Tests/checks and results:** SEC-014 contract PASS (25); HEAD mutation REJECTED/working tree PASS; release optimization PASS; SEC-002 contract baseline FAIL on pre-existing lock digest only, in-memory replay PASS (68); IonCamera class scan clean; hash scope exactly §9.
- **Runtime/device limitations:** no Gradle/aapt/JVM/instrumented/ADB/device runs. Camera capture, WebView capture, Share, email and footage share with narrowed roots are unverified on Android. Do not retry the recorded Gradle `AccessDeniedException` during scoped source tasks.
- **Current statuses SEC-001–SEC-014:** §13.
- **Exact next task:** **SEC-015** (MD5 in highway source ingestion/provenance: `tools/pull-national-highways.sh`).
- **Instructions for the next agent:**
  - Read `PROJECT_MASTER/README.md`, `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md`, `PROJECT_MASTER/CHANGELOG.md`, `PROJECT_MASTER/SECURITY_REMEDIATION_SEC013.md`, this report, then the SEC-015 sections of `outputs/SECURITY_AUDIT.md` and `outputs/SECURITY_VERIFICATION.md`.
  - Work only on SEC-015. Do not re-audit SEC-001–014 or re-widen `file_paths.xml`.
  - Keep `tests/sec014_fileprovider_contract_test.py` passing; it will intentionally fail if a new `.fileprovider` caller or storage-location change appears.
  - Do not start SEC-016/NEW-001/NEW-002, upgrade dependencies broadly, fight Gradle/ADB, or commit/push.
- **Repository HEAD/state:** HEAD `f282454e8fb79a529894598b0af9a3d7008fd84c`, unchanged. Working tree = pre-existing uncommitted remediation changes plus §9 files. Git needs `-c safe.directory=...`; global config was not changed.
- **No commit/push:** confirmed; none performed.
