# SECURITY REMEDIATION — SEC-002

**Status: PARTIALLY RESOLVED**  
Date: 2026-09-14  
Repository: coding-parrot/pothole-reporter  
Audited base commit: `f282454e8fb79a529894598b0af9a3d7008fd84c`

Source remediation and available JVM/browser/contract verification are complete. A full Android build, Android instrumentation, real capture/composer callbacks, and real URI-grant revocation remain blocked by the host environment. The previously shipped APK has not been rebuilt or replaced and must not be considered fixed.

## Finding and root cause

SEC-002: **Delete All Data misses plugin-created camera originals / email attachments.**

Camera 8.2.2 creates originals in app-specific external Pictures; the URI-result flow can retain originals and copy EXIF into its returned file. Derived/edit files can also occupy internal cache. Email Composer 8.0.0 writes attachments to external-cache `email_composer`; its startup cleanup does not provide verified cleanup after compose or during Delete All Data. The modern camera library also has private `ion_android_camera_videos` storage.

Previously, native deletion listed only reports, footage, repair-target photos, and the share cache. JavaScript separately removed debug frames and share files. Camera originals, external composer files, modern camera artifacts, and associated grants did not share an authoritative inventory.

Inspected app capture/import, Drive photo/video/keyframe and repair-evidence writers, debug-frame/manifest exports, evidence/ZIP sharing, native footage sharing, composer source, camera legacy/modern flows, FileProvider configuration, Filesystem directory mapping, and cached ioncamera 1.0.2 file-helper bytecode/provider resources. Current app camera capture remains CAMERA-only, URI-result, editing disabled, and gallery saving disabled. Imported user originals and recipient-created external copies are outside deletion ownership.

## Changed files

These are **SEC-002 changes**, separate from pre-existing SEC-001 worktree changes.

| File | Change |
| --- | --- |
| [MainActivity.java](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/java/dev/aiengg/potholereporter/MainActivity.java) | Register ManagedMedia plugin. |
| [DriveModePlugin.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt) | Authoritative cleanup, writer interlock, independent failure handling, safe deletion errors. |
| [OwnedMediaCleanup.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/OwnedMediaCleanup.kt) | New bounded deletion engine and process-wide operation gate. |
| [AndroidAppMediaCleanup.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/AndroidAppMediaCleanup.kt) | New Android ownership registry, volume journal, temporary-file snapshots, grant revocation. |
| [ManagedMediaPlugin.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/ManagedMediaPlugin.kt) | New authorized begin/end bridge; accepts operation kind/token, no paths or URIs. |
| [static/index.html](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/static/index.html) | Camera/share leases; wipe-status guard; native filesystem cleanup delegated to authoritative path. |
| [static/standalone.js](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/static/standalone.js) | Finally-based native media helper and composer cleanup. |
| [docs/index.html](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/docs/index.html) | Exact web-source mirror. |
| [docs/standalone.js](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/docs/standalone.js) | Exact web-source mirror. |
| [android-app/www/index.html](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/www/index.html) | Exact web-source mirror. |
| [android-app/www/standalone.js](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/www/standalone.js) | Exact web-source mirror. |
| [browser_test_utils.py](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/tests/browser_test_utils.py) | Extend shared native mock with ManagedMedia; credential mock behavior preserved. |
| [OwnedMediaCleanupTest.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/test/java/dev/aiengg/potholereporter/media/OwnedMediaCleanupTest.kt) | New JVM filesystem, failure, ownership, grant-hook, lifecycle/gate tests. |
| [AppMediaCleanupInstrumentedTest.kt](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/androidTest/java/dev/aiengg/potholereporter/media/AppMediaCleanupInstrumentedTest.kt) | New Android sweep, callback cleanup, lstat, and actual recipient-grant tests; not run. |
| [sec002_media_cleanup_contract_test.py](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/tests/sec002_media_cleanup_contract_test.py) | New audited-writer/registry, bridge, scoped-storage, logging, and mirror contracts. |
| [sec002_media_cleanup_flow_test.cjs](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/tests/sec002_media_cleanup_flow_test.cjs) | New browser lifecycle, late-writer, and wipe/retry tests with mocked native operations. |

Generated, ignored packaged mirrors were also refreshed: [packaged index.html](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/assets/public/index.html) and [packaged standalone.js](C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter/android-app/android/app/src/main/assets/public/standalone.js).

This is the only remediation report created/updated. Temporary compiler scripts, diagnostics, and class outputs remain outside the repository under the task's work directory; they are not application changes.

## Cleanup architecture and locations

`DriveMode.clearNativeData` remains the native Delete All Data entry point. It preserves pending-Drive cancellation, foreground-service shutdown, the media-filesystem mutex, quota reconciliation, and reconciliation-epoch invalidation. It invokes one Android media registry, rather than maintaining another media allowlist. Native secrets, media, Room records, and terminal Drive results are attempted independently; failure in one storage class does not deliberately skip the others.

The registry covers:

- Private `filesDir/reports`, `footage`, `repair_targets` including staging, and `ion_android_camera_videos`.
- All contents of the app's internal cache, including camera derivatives/edit files and `pothole-reporter-shares`.
- All contents of Context-discovered app-specific external files, cache, and media directories. This includes external `Pictures`, external-cache `email_composer`, and stale app-owned artifacts with older names.
- Only the existing documented public `Documents/pothole-frames` subtree, including manifests; other public Documents/gallery/download files are excluded.
- CameraStore's persisted edit-URI metadata. Existing SEC-001 native-secret deletion and existing Room/end-summary deletion remain in the entry point.

Context-owned cache/external directory anchors are preserved; their contents are removed. No general filesDir, public-storage root, user-selected content URI, gallery, or unrelated user directory is recursively deleted. Android `lstat` rejects linked anchors and unlinks child symlinks without traversing their targets. Parent containment is checked for each entry. Android parent aliases are resolved while external package-directory ownership is validated.

A private native journal records only Context-discovered external directory roots, never media filenames, EXIF, coordinates, or credentials. It survives restart and retains unavailable-volume information after an incomplete wipe. Advertised unavailable roots, unmounted primary storage, invalid roots, and inaccessible previously known volumes produce an incomplete result while accessible roots are still attempted. After a successful media wipe, the journal is cleared and verified; later startup/operations inventory the current Context roots again.

Missing entries are tolerated; repeated sweeps are idempotent. Entry/root exceptions are counted without logging or returning paths. Success is returned only when registry cleanup, grants, native state, and reconciliation complete successfully. A partial wipe is not rolled back: some media, records, or native credentials may already be deleted. The UI retains its failure/retry flow instead of reporting completion.

## Capture, composer, sharing, and restart

The narrow ManagedMedia bridge admits only camera/email/share kinds and issues one native token. Trusted-local-document authorization and token ownership are required; callers cannot specify a deletion path. Activity/plugin recreation preserves the active snapshot in process memory.

Camera holds its lease through capture, read, and full-frame import. Finally cleanup deletes newly observed app-camera Pictures/top-level cache files on success, cancellation, capture failure, or import failure. Existing camera files are preserved by routine snapshot cleanup and removed by the full sweep. No cropping or detection changes were introduced.

Composer cleanup runs after the plugin's activity callback resolves/rejects, covering success/cancel/failure without removing an attachment before the recipient activity closes. Evidence/ZIP share writers also hold leases. Shared cache files remain available for lazy recipient reads after chooser return and are removed by Delete All Data.

An active writer prevents native wipe admission; native wipe prevents new writer admission. A JavaScript wipe-status fence also blocks delayed email/share preparation between native cleanup completion and browser-store cleanup. Browser/PWA behavior needs no native lease and continues its existing browser-store cleanup.

Process interruption can bypass finally. Known-location enumeration removes those stale files on the next explicit wipe, without needing the lost callback, filename, or snapshot. A same-process writer whose activity never returns remains a deliberate wipe barrier; return/close that activity or restart the app process before retrying. No timer prematurely releases an external writer.

## URI grants and scoped storage

Cleanup revokes read/write grants through both app FileProvider authorities before deleting mapped ordinary entries. Symlinks are unlinked without mapping their unrelated targets into revocation URIs. Owned files/cache/external-files/external-cache/external-media aliases are also revoked by prefix to cover previously unlinked files. The camera provider's shared external mapping is revoked only for the documented debug-frame subtree, never the general external alias. Grant-revocation failure marks deletion incomplete and does not skip disk cleanup.

No provider configuration, target/min SDK, Gradle/Capacitor version, dependency, backend, or legacy storage permission was changed. Current target SDK 36 scoped-storage restrictions remain applicable. Denied debug-folder access is an incomplete wipe, not a reason to request broad storage access.

## Tests executed and exact results

| Check | Final result |
| --- | --- |
| Direct Kotlin compiler + JUnitCore `OwnedMediaCleanupTest` | **PASS — 14 tests, 0 failures.** Real JVM fixture deletion covers registered locations, synthetic EXIF/GPS-marker bytes, first-run/missing entries, stale/restart sweeps, repeated cleanup, partial/thrown failure, grant hooks, traversal rejection, linked-anchor/target protection, invalid kinds/tokens, lifecycle gates, and 32 simultaneous writer/wipe admission races. |
| Node Playwright `sec002_media_cleanup_flow_test.cjs`, system Chrome | **PASS — 18 scenarios.** Actual browser JavaScript; native bridge/camera/composer/share operations mocked. Covers success/cancel/failure leases, actual camera-wrapper import/failure paths, ZIP writing, active-writer wipe refusal, retry, late-writer refusal, and cleanup failure. Seeded IndexedDB reports/photos, drives, footage, state packs, local/session storage, and Cache Storage are empty after successful wipe. |
| `sec002_media_cleanup_contract_test.py` | **PASS — 68 checks.** Audited native/plugin/web writer hashes require explicit ownership review on writer/dependency changes; new recognized writers fail inventory checks. Cleanup package cannot introduce a media producer. Roots, native barriers, bridge validation, scoped storage, safe errors/no cleanup logging, late-writer fence, and six hosted/www/packaged mirrors checked. |
| Direct K2 compilation of application Kotlin sources with Java sources for type resolution | **PASS.** Includes updated Drive plugin and all new native production files, using existing SDK 36/cached dependencies. Existing CameraX and externalMediaDirs deprecation warnings only. This is not an APK/AAB build or Java packaging verification. |
| Node `--check` for standalone engine and new browser test | **PASS.** |
| `full_frame_invariant_test.py` | **PASS — 18 checks.** |
| `native_cleanup_retry_contract_test.py` | **PASS — 10 checks.** Existing process-global Drive interlock retained. |
| `native_background_lifecycle_contract_test.py` | **PASS — 14 checks.** |
| `native_dashcam_contract_test.py` | **PASS — 15 checks.** |
| `android_release_optimization_test.py` | **PASS — 17 checks.** |
| Diff inspection / whitespace check | **PASS.** Cumulative audited-base diff and all new native files inspected; Git diff check passes with CR-at-EOL handling for existing Windows files. Test-created untracked pycache artifacts removed. |
| SEC-001 native baseline hashes | **PASS — 5 files unchanged.** SEC-001 report was not rewritten. |
| Repository text/credential-path search | **PASS — 781 UTF-8 tracked/new source files plus packaged web mirrors scanned, values withheld.** Fourteen key-like matches classify as public Sikkim authority IDs or an existing synthetic fixture; 21 RTSP-userinfo matches classify as documented examples/test fixtures; zero unclassified candidates. No actual production credential used or introduced. Zero old plaintext OpenAI/RTSP browser-storage writes. Old native wipe allowlist/recursive-deletion path absent from clearNativeData; required root references now point to the registry/fallback contracts. |
| Dependency/build/permission/provider diff checks | **PASS — unchanged.** |

Initial development checks exposed the Windows-junction unlink limitation and an IndexedDB fixture-initialization error; final focused tests above pass. A writer interlock contract was preserved in its existing form. No failed development result is represented as Android runtime verification.

## Tests blocked by environment

- Normal offline Gradle `:app:testDebugUnitTest --tests dev.aiengg.potholereporter.media.OwnedMediaCleanupTest :app:compileDebugAndroidTestKotlin`: initial Android user-directory initialization failures were bypassed with workspace-local JVM home settings. Final attempt failed at `:capacitor-android:compileDebugJavaWithJavac` with host `java.nio.file.AccessDeniedException` opening/closing transformed `lifecycle-viewmodel-2.6.2-api.jar`. Application Gradle tests and Android test compilation did not complete. Dependencies were not changed to work around this.
- Standalone compilation including SEC-002 Android test sources: **BLOCKED** by missing cached AndroidX test runner/InstrumentationRegistry classes; resulting type errors cascade from those unresolved imports. Four instrumented test methods are provided but not compiled/run successfully here.
- `adb devices -l`: **BLOCKED**, exit 1, Android tool initialization cannot create its user directory. No successful Android device/emulator session was obtained. Actual camera/composer callbacks, lstat deletion, removable-volume behavior, recipient-grant revocation, scoped Documents access, and logcat observations remain unverified on Android.
- Existing `delete_all_data_test.py` and `photo_pothole_only_test.py`: **BLOCKED before assertions**, Python `ModuleNotFoundError: playwright`. Available Node Playwright covered the modified lifecycle/wipe flows; these two existing Python scripts are not claimed to have passed.
- Windows JVM junction fixture: target protection and incomplete-result behavior verified; host sandbox refusal to unlink is not claimed as successful Android symlink deletion.

## Remaining limitations and scope confirmation

Complete Android build and isolated-device instrumentation are required before changing SEC-002 to RESOLVED and producing a replacement release artifact. Instrumented full-sweep tests intentionally erase the isolated test installation's media and must be run on test data. OEM camera/mail behavior, removable volumes, scoped public debug-folder access, and real grant lifetimes need that runtime evidence.

Deletion concerns app-owned directory entries, not flash secure erase, already-open recipient file descriptors, sent mail, or copies exported into recipient/user-owned storage. The filesystem tests use synthetic EXIF/GPS-marker payloads, not real camera/location data or an EXIF parser. Existing third-party plugin failure logging remains unchanged; the new cleanup code does not log artifact contents/paths, and real logcat verification is blocked. The contracts enforce recognizable storage writers and explicitly reviewed hash updates; they do not replace review of future dynamically implemented storage APIs.

**SEC-003 through SEC-016 were NOT intentionally remediated.** No Uzbekistan features, unrelated refactors, upgrades, UI redesign, backend, permission/provider broadening, commit, or push were performed. SEC-001 native security implementation/tests and its report were preserved; the shared test harness gained only the new media mock.

**Final SEC-002 status: PARTIALLY RESOLVED.** Stop after SEC-002; Android build/runtime and replacement-artifact verification remain the blockers.
