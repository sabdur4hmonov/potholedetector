# Security Verification — Pothole Reporter

Repository: `https://github.com/coding-parrot/pothole-reporter`  
Verified commit: `f282454e8fb79a529894598b0af9a3d7008fd84c`  
Verification window: 2026-09-11 through 2026-09-12, Asia/Tashkent  
Scope: read-only verification of SEC-001 through SEC-016; no fixes, refactors, upgrades, commits, pushes, publishing, paid API calls, or connections to unknown RTSP endpoints.

## A. Environment

- Host: Windows 11, PowerShell.
- Source checkout: clean detached verification of commit `f282454e8fb79a529894598b0af9a3d7008fd84c`. The original checkout remained at that commit and clean.
- Node.js: `v24.18.0`; npm: `11.16.0`.
- Java: Eclipse Temurin `21.0.12.1`, downloaded from the Adoptium release and checked against SHA-256 `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e`.
- Gradle: wrapper `8.14.3`, revision `e5ee1df3d88b8ca3a8074787a94f373e3090e1db`. The wrapper distribution SHA-256 is pinned in the repository as `ed1a8ad0e173c24d1f87b7ea69b5a98087cc7e1c9a7875f68c22c0a01311d7c`; the downloaded official checksum matched. The wrapper JAR SHA-256 `7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172` also matched the official wrapper JAR.
- Android command-line tools: official package `commandlinetools-win-15859902_latest.zip`; SHA-256 `90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a`. Android platform tools `37.0.1`, platform `android-36` revision 2, Build Tools `36`, and Build Tools `35.0.0` were installed from Google repository metadata with package SHA-1 verification. Gradle selected Build Tools `35.0.0`.
- Bundletool: `1.18.3`, SHA-256 `a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29`.
- Python: official CPython embeddable `3.13.7`, SHA-256 `f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65`.
- Available and used: npm audit/explain, Gradle dependency reporting, repository security contract tests, `aapt2`, `apksigner`, `jarsigner`, `keytool`, `jar`, Bundletool, and read-only custom history/artifact inspection scripts.
- Unavailable: OSV Scanner CLI, Semgrep, Gitleaks, MobSF, a usable Android emulator, and a connected physical Android test device. Advisory data collected during the audit was retained for comparison, but these unavailable scanners were not represented as executed.
- No actual OpenAI or RTSP credential was entered, read, or printed. The release attempt used a temporary audit-only RSA-3072 signing certificate, never a production signing key.

## B. Build verification

### Wrapper and dependency graph

The wrapper integrity checks passed. `gradlew --version` executed Gradle 8.14.3 on Temurin 21. The complete `releaseRuntimeClasspath` dependency resolution completed successfully.

Security-relevant resolved versions include:

- Kotlin standard library `2.1.0`; Kotlin coroutines `1.10.2`.
- AndroidX Core/Core KTX `1.17.0`, AppCompat `1.7.1`, Activity `1.11.0`, Lifecycle `2.8.7`, Room `2.6.1`, ExifInterface `1.4.2`.
- CameraX `1.5.3`; Media3/ExoPlayer/RTSP `1.10.1`.
- Google Play Services Location `21.3.0`.
- OkHttp `4.12.0`; Okio `3.6.0`; Gson `2.13.2`; Material `1.13.0`; Cordova Android `14.0.1`.
- Capacitor Android and local Capacitor plugin projects, Ion camera `1.0.2`, filesystem `1.1.0`, and geolocation `2.2.2`.

`@xmldom/xmldom`, `uuid`, and `xcode` do not appear in `releaseRuntimeClasspath`. npm resolution instead shows:

- `@xmldom/xmldom@0.9.11` is used by `plist@3.1.1`, reached through `@capacitor/cli@8.5.0` and related native-run/xcode tooling.
- `uuid@7.0.3` is used only by `xcode@3.0.1`, reached through `@capacitor/cli@8.5.0`.

The affected XML package is therefore reachable in build/developer tooling that parses XML/plists, but it is not included in the Android application runtime graph. `uuid@7.0.3` is likewise an iOS/xcode CLI dependency and is not Android runtime code.

The Android build uses KSP, not KAPT: root `android-app/android/build.gradle:13` declares KSP `2.1.0-1.0.29`, `android-app/android/app/build.gradle:3` applies KSP, and line 124 sends the Room compiler to `ksp`. Searches found no `kapt`, `kotlin-kapt`, or `annotationProcessor` configuration. The Kotlin KAPT cache advisory's required KAPT condition is absent.

Live `npm audit --json` reported four vulnerability nodes: one high (`@xmldom/xmldom`) and three moderate (`uuid`, `xcode`, and the transitive `@capacitor/cli` result). No critical or low npm nodes were reported. npm's automated suggestion included a Capacitor downgrade; that suggestion was not applied because compatibility and whether the target version carries the required fixed transitive packages must be verified first.

### Release build attempt

`tools/build-play-release.sh` is the repository's signed APK/AAB release path. It invokes Gradle offline at lines 168–171 and checks signing, assets, manifests, secrets, and R8 output afterward. A clean checkout could not enter the Gradle build because the ignored generated file `android-app/android/capacitor-cordova-android-plugins/cordova.variables.gradle` was absent. `npx cap sync android` generated that prerequisite; `npx cap copy` alone did not.

After synchronization, release build attempts reached `compileReleaseJavaWithJavac`. Java then repeatedly received `AccessDeniedException` while closing or reading Gradle-transformed Android dependency JARs. Retrying with one worker, no file watching, no build cache, a fresh Gradle cache, and a copy under the Windows system temporary directory changed which transformed JAR failed but did not remove the failure. Direct `jar tf` and .NET `File.OpenRead` operations on the same files succeeded. This is consistent with a host Java/Gradle file-sharing or sandbox interaction, not a Java source compilation diagnostic.

Consequences:

- An independent APK/AAB rebuild, `lintRelease`, and fresh R8-output generation did not complete.
- The source build is not verified reproducible on this host.
- No failed or partial locally built artifact is treated as evidence.
- The already-published APK and AAB for version `1.38.0`, whose release metadata points to the exact audited commit, were inspected independently in Section C.

### Repository tests

The following read-only security/release contract tests passed against the synchronized exact-commit verification copy:

- `tests/android_release_optimization_test.py` — 17 checks passed, including shrinking, mapping, manifest, wrapper pin, dependency lines, logging policy, FileProvider, and asset mirrors.
- `tests/native_inference_resource_contract_test.py` — 11 checks passed.
- `tests/native_report_evidence_quota_test.py` — 9 checks passed.
- `tests/native_capture_safety_contract_test.py` — 7 checks passed.
- `tests/native_dashcam_contract_test.py` — 14 checks passed.

An initial run of two tests stopped before assertions because generated Capacitor assets were absent and Windows selected CP1251. Rerunning after Capacitor sync with `PYTHONUTF8=1` passed. These were harness prerequisites, not failing security assertions.

## C. APK/AAB verification

### Artifact identity

The inspected GitHub release is `v1.38.0` for the audited commit.

- APK: 3,170,606 bytes; SHA-256 `a028ae4dbf179ac792f73a101b5669bfcc447a3b41e2f78ae6ede120b548f06b`. This matches the GitHub release digest.
- AAB: 5,485,974 bytes; SHA-256 `10f302b6c7729cc68b5fcbdce7436fdc8e0d6c7a123b1371425e77e12c27bf9c`. This matches the GitHub release digest.
- The APK's `index.html` and `standalone.js` are byte-identical to their canonical Git blobs at the audited commit. CRLF working-tree normalization was excluded from this comparison.

### APK signature

`apksigner verify --verbose --print-certs` passed. The APK uses APK Signature Scheme v2 with one signer. V1, v3, v3.1, v4, and SourceStamp are absent. The signer is RSA-4096 with subject `CN=Pothole Reporter Upload, O=coding-parrot, C=IN` and certificate SHA-256 `296f947f8412aca3925cf5169c195ae097c6856d5751eedd789dd4bfba7bac8c`. That fingerprint matches the release script's pinned expected certificate.

### AAB signature and structure

Bundletool `validate` passed, `bundletool dump manifest` succeeded, and `jar --validate` returned success. Normal `jarsigner -verify` printed `jar verified`; the AAB certificate matches the APK signer. The self-signed certificate is valid from 2026-08-21 through 2051-08-15 and the AAB has no trusted timestamp, which is expected for this self-managed upload certificate but makes the signing-time warning permanent.

However, `jarsigner -verify -strict` returned exit code 4 and reported internal inconsistencies: signed entries are visible through `JarFile` but not through `JarInputStream`. The AAB has one `META-INF/MANIFEST.MF`, positioned as entry 505 of 506 after `UPLOAD.SF` and `UPLOAD.RSA`. Bundletool accepts the bundle, but standard Java signature APIs interpret it differently. This is NEW-001.

### Manifest and packaging policy

The APK and AAB manifests agree on package `dev.aiengg.potholereporter`, version code `67`, version name `1.38.0`, minimum SDK 24, and target/compile SDK 36.

- `android:debuggable` and `android:testOnly` are absent from the release application.
- `android:allowBackup="false"` is present. `dataExtractionRules` and `fullBackupContent` are configured; reviewed rules exclude app databases, shared preferences, files, external files, and roots containing credentials/evidence.
- No `usesCleartextTraffic` or `networkSecurityConfig` override is present. Target SDK 36 therefore retains the platform's default denial of HTTP cleartext. RTSP is a separate protocol and remains explicitly accepted by application code.
- Permissions: Internet, camera, fine/coarse location, foreground service and its camera/connected-device/location types, access/change network state, notifications, wake lock, and the generated signature-level dynamic-receiver permission. No microphone, storage, or background-location permission is declared.
- Exported components: the launcher `MainActivity` is exported. The app FileProvider, Drive foreground service, notification-action receiver, camera provider, Room service, initialization provider, and Google API activity are private. AndroidX `ProfileInstallReceiver` is exported but guarded by the signature/privileged `android.permission.DUMP` permission. Camera loading/editor activities have no intent filters and resolve private under merged-manifest semantics.
- FileProvider paths are broad within the app sandbox: `files/footage/`, the whole app-specific external-files root, `cache/`, and `external-cache/email_composer/`.
- No JavaScript or CSS source map was found in either artifact. The AAB includes the R8 mapping at `BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map`.
- Capacitor config sets native logging behavior to `none`. Searches found no embedded actual OpenAI key or RTSP password. The application intentionally embeds service/catalog URLs and code paths that accept user-supplied OpenAI and RTSP credentials.

## D. Device verification

No controlled device test was possible. Before setup, neither `adb` nor an emulator was installed. Platform tools were installed, but `adb devices -l` failed before enumeration because this sandboxed host denied creation under `C:\.android`. No emulator binary/system image or connected physical test device was otherwise available. Docker's daemon pipe and WSL were also unavailable, so an alternate Android runtime could not be started.

The following remain **not device-verified**:

- Delete All Data before/after inventory.
- Successful, cancelled, and interrupted camera capture.
- Camera originals, EXIF-bearing originals, email attachments, and cache retention.
- URI grant issuance/revocation and cross-app FileProvider access.
- Notification actions and runtime exported/private-component behavior.
- Runtime location collection and Drive foreground-service behavior.
- Malformed manual-image behavior and hostile remote-pack behavior.

No unrelated user file was accessed. Conclusions about these behaviors are identified below as source/artifact-confirmed rather than device-confirmed.

## E. SEC-001 through SEC-016 status

### SEC-001

ID: SEC-001  
Original severity: MEDIUM  
Verification status: CONFIRMED — source and shipped-artifact confirmed; no actual secret used.  
Evidence: `static/standalone.js:17` reads browser storage. `static/index.html:275`, `:316`, `:3536`, `:5697`, `:5704`, `:5767`, and `:5773` expose credential values to or persist them from the privileged web layer. The exact code is present in the APK. The native transport uses the key but the bridge path supplies it from WebView JavaScript. Browser fallback also reads the value. Backup is disabled/excluded and native logging is `none`; no embedded real credential or credential-log statement was found.  
Actual exploitability: A script executing in the privileged WebView, local browser-origin script, or a party with equivalent app-data access could read retained OpenAI and RTSP credentials. No remote script injection was demonstrated. Android backup does not provide the identified path.  
Production impact: Theft or misuse of the user's API account and disclosure of dashcam credentials.  
Required remediation: Keep retained secrets behind narrow native operations using Keystore-backed protection and never return plaintext to WebView JavaScript; for shared service funding, use authenticated server-side quotas.  
Production blocker: YES

### SEC-002

ID: SEC-002  
Original severity: MEDIUM  
Verification status: CONFIRMED in source/plugin behavior; NOT DEVICE-VERIFIED.  
Evidence: App deletion logic at `static/index.html:4298-4305` and `:5847-5868` does not enumerate plugin-created camera originals or email-composer cache. Capacitor Camera 8.2.2 creates originals under app external Pictures and copies EXIF data (`CameraUtils.java:24-26`, `LegacyCameraFlow.java:638-645`, `:657-665`) without an app cleanup handoff. Email Composer 8.0.0 creates files under external cache `email_composer` (`AssetUtil.java:25-38`, `:122-142`) and cleans only during plugin load (`EmailComposerPlugin.java:18-21`). FileProvider configuration in the shipped manifest exposes the relevant app-specific roots only through grants.  
Actual exploitability: App-owned images and EXIF metadata can outlive the in-app wipe until plugin/startup cleanup, overwrite, uninstall, or explicit deletion. Persistence after every device/OEM path and residual URI grants were not reproduced without a device. This is not a claim of secure flash wiping or unrestricted access by other sandboxed apps.  
Production impact: The UI's deletion promise can leave sensitive road images, location-bearing EXIF, and email attachments behind.  
Required remediation: Track and delete plugin originals after private evidence import; enumerate and verify camera/email temporary roots during wipe; revoke relevant grants; test success, cancellation, interruption, email composition, and failure paths on devices.  
Production blocker: YES

### SEC-003

ID: SEC-003  
Original severity: MEDIUM  
Verification status: CONFIRMED — source and packaged-code confirmed; no external camera contacted.  
Evidence: `static/index.html` URL validation accepts `rtsp://` URLs with any nonempty host. `NativeFrameSource.kt:55-75` accepts scheme `rtsp`, optional user info, and any nonblank host. `NativeRtspFrameSource.kt:180-189` passes the URI to Media3 RTSP. No private/local address restriction exists; authentication is optional; `rtsps://` is rejected; no TLS transport is implemented. The code does not perform an HTTP redirect flow, but arbitrary external RTSP hosts can be supplied directly. Credentials are retained through the SEC-001 storage path.  
Actual exploitability: A hostile or observed network path can read or alter unencrypted RTSP traffic, disrupt capture, or expose inline credentials. Direct server redirection was not established, but user/configuration input can target an arbitrary host.  
Production impact: Road imagery disclosure, misleading visual evidence, connection disruption, and credential exposure; downstream authority/repair routing is partially limited when timing is uncalibrated.  
Required remediation: Disable dashcam mode for public release until protected transport exists, or use authenticated encryption/tunneling, restrict allowed endpoints to intended networks, and avoid reused credentials.  
Production blocker: YES

### SEC-004

ID: SEC-004  
Original severity: MEDIUM  
Verification status: CONFIRMED — source-confirmed allocation order; destructive resource-exhaustion test not run.  
Evidence: `static/standalone.js:2732-2747` calls `response.arrayBuffer()` before validating complete response length and hash. Analogous pack paths occur near `:2986`, `:3241`, `:3565`, and `:3837`. Timeout and post-buffer integrity/schema checks do not impose a streaming byte ceiling.  
Actual exploitability: A configured/compromised remote pack source or network path able to deliver an oversized successful body can force complete buffering before rejection. Hash validation still prevents substituted content from being accepted.  
Production impact: Memory exhaustion, app termination, bandwidth use, and loss of availability.  
Required remediation: Enforce a cumulative decoded-byte limit while receiving, abort slightly above the exact expected length, retain exact size/hash/schema checks, bound native Capacitor buffering, and impose an overall deadline.  
Production blocker: YES

### SEC-005

ID: SEC-005  
Original severity: LOW  
Verification status: CONFIRMED in source; bounded-output contract tests passed.  
Evidence: Native code uses `BufferedReader.readLine()` at `NativeInferenceTransport.kt:160-181`, so a single line is allocated before the cumulative 64 KiB bound can reject it. Both native SSE outputs have a 64 KiB cumulative ceiling, explicit token limits, bounded consumers, cancellation, and retry classification, as confirmed by `native_inference_resource_contract_test.py`. Browser SSE parsing at `static/standalone.js:921-967` also lacks a transport-wide preallocation line cap.  
Actual exploitability: A malicious or malfunctioning inference endpoint can send an extremely long unterminated line or hold a response open. Existing session, concurrency, cancellation, and retry controls reduce impact.  
Production impact: Memory pressure, prolonged inference slots, battery drain, and local denial of service.  
Required remediation: Bound individual line/chunk size, total transport bytes, event count, and whole-call elapsed time before unbounded allocation; stop on terminal completion and release transports on cancellation.  
Production blocker: NO

### SEC-006

ID: SEC-006  
Original severity: MEDIUM  
Verification status: CONFIRMED — source-confirmed cost-control gap; no paid request made.  
Evidence: Native structured requests cap outputs at 1,536 and 768 tokens (`NativeInferenceRequest.kt:79`, `NativeDetectionContract.kt:7`, `NativeRepairContract.kt:31`), and native concurrency/replay/session controls passed contract tests. JavaScript calls around `static/standalone.js:1040-1044` and `:6279-6283` have no output-token ceiling. No persistent app-wide request/token/currency budget was found. The evidence quota test's 512 MiB disk quota does not limit provider spending.  
Actual exploitability: A user, repeated failure/replay sequence, or compromised client path can generate charges against the user's BYOK account within provider-side limits. No shared maintainer billing credential or public spending endpoint was found.  
Production impact: Unexpected user charges and uncontrolled repeated paid inference.  
Required remediation: Add output limits to every AI path, persistent request/token budgets, replay estimates, and a fail-closed spending limit. Any shared backend needs atomic reservations, per-user quotas, a global shutdown, and idempotency.  
Production blocker: YES

### SEC-007

ID: SEC-007  
Original severity: MEDIUM  
Verification status: CONFIRMED by workflow inspection; workflow was not executed.  
Evidence: `.github/workflows/refresh-catalog.yml:13-15` grants contents write; checkout at line 34 leaves credentials persisted; lines 44–45 install mutable Python/browser inputs before validation and push. The workflow has scheduled/manual triggers, not `pull_request` or `pull_request_target`, and reviewed shell inputs do not directly interpolate attacker-controlled PR values. Later path/schema validation does not isolate earlier dependency execution.  
Actual exploitability: Compromise of a fetched mutable package/browser installer can act with the job's repository credential. Opening an untrusted PR alone does not trigger this workflow or expose its token. Branch protection was outside the available repository data.  
Production impact: Repository/catalog tampering within token and branch-policy permissions, with possible artifact poisoning.  
Required remediation: Fetch/build under a read-only token with `persist-credentials:false`; pin packages and browser inputs with hashes; transfer only validated artifacts to a minimal write job with provenance and protected environments.  
Production blocker: YES

### SEC-008

ID: SEC-008  
Original severity: MEDIUM  
Verification status: CONFIRMED as a build-tool dependency; NOT PRESENT in Android runtime.  
Evidence: `npm ci` installed `@xmldom/xmldom@0.9.11`. `npm explain` resolves it through `plist@3.1.1` and `@capacitor/cli@8.5.0`; live `npm audit` marks it high and lists the known parser/serializer advisories. The complete Gradle `releaseRuntimeClasspath` contains no npm/xmldom package. Capacitor sync invokes the affected tooling class, establishing toolchain reachability, while no production service accepting attacker XML was found.  
Actual exploitability: Conditional build/developer-tool denial of service or XML manipulation when affected tooling processes hostile XML/plists. It is not a shipped Android runtime attack surface.  
Production impact: Compromised or unavailable developer/release builds and potentially manipulated generated project data.  
Required remediation: In a separate remediation phase move the compatible dependency chain to a release containing `@xmldom/xmldom` 0.9.12 or later on the compatible 0.9 line, then rescan and validate Capacitor sync/build behavior. Do not blindly force npm's suggested version change.  
Production blocker: YES

### SEC-009

ID: SEC-009  
Original severity: LOW  
Verification status: CONFIRMED — source and APK asset confirmed.  
Evidence: The privileged `static/index.html` and shipped APK copy have no Content-Security-Policy meta directive. Inline scripts/styles are present. `capacitor.config.json` has no remote server or `allowNavigation` entries, and no exploitable HTML injection path was reproduced.  
Actual exploitability: CSP absence increases the consequence of a separate markup/script injection or compromised local content path; it is not independently a remote-code exploit.  
Production impact: A successful web-content injection would have fewer browser-enforced restrictions and could reach privileged WebView data/bridge operations.  
Required remediation: Refactor inline execution as needed for a restrictive CSP, prohibit frames/objects, constrain connect/image sources, preserve escaping, and test native bridge compatibility across supported WebViews.  
Production blocker: NO

### SEC-010

ID: SEC-010  
Original severity: LOW  
Verification status: CONFIRMED in source; NOT DEVICE-VERIFIED with hostile media.  
Evidence: `static/standalone.js:8465-8477` creates a bitmap from the complete user blob before applying an explicit compressed-byte or decoded-pixel budget. Related import/capture paths are at `static/index.html:1803-1836` and `:4313-4322`.  
Actual exploitability: A user-selected malformed or oversized image can cause large decoder allocations. No decoder memory-corruption claim or remote delivery path was established.  
Production impact: Browser/app crash and local resource exhaustion.  
Required remediation: Enforce compressed-byte, image-format, and decoded-pixel limits before full allocation; use bounded native decode/downsampling; test malformed media in a resource-limited device environment.  
Production blocker: NO

### SEC-011

ID: SEC-011  
Original severity: INFO  
Verification status: NOT APPLICABLE to the Android production runtime; advisory match confirmed in tooling.  
Evidence: `npm explain uuid` shows `uuid@7.0.3` only under `xcode@3.0.1` through Capacitor CLI. The Gradle release graph contains no uuid package. The advisory concerns output-buffer calls in v3/v5/v6 APIs; no such repository call path was found.  
Actual exploitability: Conditional malformed or partial UUID output in iOS/xcode tooling; no Android authorization or identifier bypass demonstrated.  
Production impact: None identified for the shipped Android app; tooling compatibility remains a maintenance concern.  
Required remediation: Prefer a maintained parent dependency that resolves a compatible fixed uuid, with xcode/Capacitor compatibility tests; do not force a new uuid major directly into xcode 3.  
Production blocker: NO

### SEC-012

ID: SEC-012  
Original severity: INFO  
Verification status: NOT APPLICABLE to the current build configuration.  
Evidence: The affected Kotlin version family is declared, but the advisory requires KAPT build-cache handling. This project applies KSP `2.1.0-1.0.29` and Room through `ksp`; no KAPT plugin or processor configuration exists. The resolved Kotlin runtime is `2.1.0`.  
Actual exploitability: The required KAPT path is absent. A future introduction of KAPT or hostile/shared build-cache conditions would require reassessment.  
Production impact: No confirmed application or current-build code execution.  
Required remediation: Keep untrusted/shared caches isolated, preserve KAPT absence unless reviewed, and select a vendor-supported compatible Kotlin fix during planned dependency maintenance rather than blindly adopting a beta.  
Production blocker: NO

### SEC-013

ID: SEC-013  
Original severity: INFO  
Verification status: NEEDS DESIGN DECISION; source-confirmed collection, NOT DEVICE-VERIFIED.  
Evidence: `NativeDriveLocationProvider.kt:263-271`, `DriveForegroundService.kt:2749-2756`, and `PotholeDatabase.kt:174-179` persist detailed route/location history; UI export/history handling appears near `static/standalone.js:7755`. Backup is disabled/excluded and Android sandbox protections apply.  
Actual exploitability: A party with unlocked-device/app-data access, a compromised app process, or an authorized export can infer sensitive movement. An ordinary unrelated sandboxed app cannot query the private database directly.  
Production impact: Privacy harm from disclosure of precise travel history.  
Required remediation: Decide and document minimum retention, offer short retention and route-history opt-out, protect sensitive views and keys, and exclude precise traces from public community data.  
Production blocker: NO

### SEC-014

ID: SEC-014  
Original severity: INFO  
Verification status: CONFIRMED configuration breadth; disclosure exploit NOT REPRODUCED.  
Evidence: `file_paths.xml:3-7` grants provider eligibility to `files/footage/`, all app-specific external files, cache, and external cache `email_composer`. The artifact manifest keeps the provider private and requires per-URI grants. Attachment code near `static/standalone.js:9494` and plugin `AssetUtil.java:129-136` uses these paths.  
Actual exploitability: Another app would still need a granted content URI, a confused-deputy path, or compromised app flow. Broad roots increase what a mistaken grant can expose; unrestricted arbitrary-file access was not confirmed.  
Production impact: Conditional disclosure of unintended app-owned evidence, cached data, or attachments.  
Required remediation: Restrict the provider to dedicated share directories, use unique immutable names, grant read access only for the selected operation, and revoke expired grants.  
Production blocker: NO

### SEC-015

ID: SEC-015  
Original severity: LOW  
Verification status: CONFIRMED by source inspection.  
Evidence: `tools/pull-national-highways.sh:6-7` and `:18-26` pin and verify a downloaded highway source with MD5 rather than SHA-256/SHA-512. HTTPS is used, and no practical collision/replacement was demonstrated.  
Actual exploitability: An attacker who can influence the fetched source and construct content matching the legacy digest may weaken provenance. This is a build/data ingestion path, not an in-app hash check.  
Production impact: Reduced confidence that generated highway data came from the reviewed input.  
Required remediation: Pin a reviewed SHA-256 or SHA-512 digest and retain immutable source provenance and HTTPS.  
Production blocker: NO

### SEC-016

ID: SEC-016  
Original severity: LOW  
Verification status: CONFIRMED for browser builds; NOT APPLICABLE to the native APK runtime.  
Evidence: `static/standalone.js:6-12` imports a credential from a URL fragment only when `!NATIVE`. The exact guarded code is also packaged, but Capacitor native mode prevents execution of the shortcut.  
Actual exploitability: In a browser deployment, a user who follows or shares a fragment-bearing link can expose or import that link's credential through browser history/synchronization/screenshots/extensions. Visiting an attacker link does not reveal an already-stored victim key. The native APK does not execute this path.  
Production impact: Conditional credential disclosure or account/key confusion in the browser version; no native APK impact established.  
Required remediation: Remove or compile-gate the shortcut from production web builds and accept credentials only through explicit settings entry, never links.  
Production blocker: NO for Android; YES before a public browser deployment

## F. Newly discovered security findings

### NEW-001

ID: NEW-001  
Original severity: N/A — newly discovered; assessed MEDIUM.  
Verification status: CONFIRMED in the published AAB.  
Evidence: `jarsigner -verify` prints `jar verified`, but `jarsigner -verify -strict` returns 4 and reports that entries are signed in `JarFile` but not `JarInputStream`. The single `META-INF/MANIFEST.MF` is entry 505 of 506, after `UPLOAD.SF` and `UPLOAD.RSA`. `jar --validate` and Bundletool 1.18.3 validation pass. `tools/build-play-release.sh:229-233` accepts the non-strict `jar verified` result and therefore misses this parser differential.  
Actual exploitability: No modified bundle or Play compromise was demonstrated. Different standard Java readers disagree on whether entries have signature metadata, which creates a supply-chain validation ambiguity and can cause strict verifiers to reject the artifact.  
Production impact: Release validation can report success for an AAB that fails strict Java signature verification; downstream tooling may treat signer coverage inconsistently.  
Required remediation: Produce the AAB with conventional JAR metadata ordering/signing, require `jarsigner -verify -strict` exit code 0, retain Bundletool validation, and document/verify the exact Play upload transformation.  
Production blocker: YES

### NEW-002

ID: NEW-002  
Original severity: N/A — newly discovered; assessed LOW.  
Verification status: CONFIRMED from a clean exact-commit checkout.  
Evidence: `tools/build-play-release.sh` expects `android-app/android/app/src/main/assets/capacitor.config.json` and the ignored `android-app/android/capacitor-cordova-android-plugins/cordova.variables.gradle`, then invokes Gradle with `--offline`. A clean checkout lacks the Cordova generated file. `npx cap copy android` did not create it; `npx cap sync android` did. The release script does not perform or explicitly preflight this sync/cache bootstrap.  
Actual exploitability: This is primarily a reproducibility/integrity gap. A stale local generated tree or prewarmed cache can affect what is built, while a clean builder fails before the documented checks. No malicious generated file was found.  
Production impact: Release provenance is harder to reproduce and review; stale ignored build inputs can escape source-control comparison.  
Required remediation: In the later remediation phase, define an immutable clean-build bootstrap, preflight every generated input, generate it from the locked dependency tree, and either avoid offline-only hidden cache prerequisites or provision a verified cache. Verify the generated tree before signing.  
Production blocker: YES until a clean independent release build succeeds

## G. False positives / non-applicable findings

- SEC-008 is a real vulnerable package in the npm/Capacitor toolchain, but it is not in the Android runtime dependency graph. Describing it as shipped app XML parsing would be a false positive.
- SEC-011's uuid advisory is real for the locked iOS/xcode tooling dependency; no affected call and no Android runtime reachability were found. It is not applicable to the Android app artifact.
- SEC-012 matches a declared Kotlin version, but its KAPT prerequisite is absent because the project uses KSP. It is not applicable to the current build.
- SEC-016 is reachable in the browser fallback only and is guarded out in native mode. It is not an APK runtime finding.
- The exported AndroidX ProfileInstallReceiver is permission-guarded by `android.permission.DUMP`; treating it as freely callable by ordinary apps would be inaccurate.
- `DebugProbesKt.bin` and JUnit-named resources inside dependency archives do not establish a debuggable release. The merged artifact has no debuggable/testOnly flag.
- No embedded production OpenAI key, RTSP password, unrestricted Android backup, storage permission, microphone permission, background-location permission, JavaScript source map, or confirmed secret in 2,537 Git history blobs was found. History candidates were fixtures/test values or false positives.

## H. Exact remaining blockers

1. SEC-001: retained credentials remain readable by the privileged WebView/browser layer.
2. SEC-002: the deletion flow does not cover all camera/email plugin files, and the behavior has not been verified on a device.
3. SEC-003: dashcam video and optional inline credentials use unencrypted RTSP with arbitrary-host acceptance.
4. SEC-004: remote pack bodies are completely buffered before the byte ceiling and integrity checks.
5. SEC-006: JavaScript AI requests and the app as a whole lack enforceable spend ceilings.
6. SEC-007: mutable workflow dependencies execute while repository write credentials are present.
7. SEC-008: the release/developer toolchain resolves vulnerable `@xmldom/xmldom@0.9.11`.
8. NEW-001: the published AAB fails strict JAR signature verification because standard Java readers disagree on signature coverage.
9. NEW-002 and environment limitation: a clean release requires undeclared generated/cache state, and the independent signed release build/lint could not complete on this host due repeatable Java/Gradle transformed-JAR access failures.
10. Device coverage: destructive deletion, temporary-file, URI-grant, component, notification, location, and foreground-service behaviors remain unverified on Android hardware/emulation.

## I. Exact commands/tools used

Paths below define the exact verification locations. The temporary keystore password is intentionally represented as `<REDACTED_AUDIT_PASSWORD>`.

```powershell
$ROOT = 'C:\Users\user\Documents\Codex\2026-09-09\bro'
$SOURCE = "$ROOT\work\pothole-reporter"
$VERIFY = "$ROOT\work\verification-f282454"
$JAVA_HOME = "$ROOT\work\toolchain\jdk"
$SDK = "$ROOT\work\toolchain\android-sdk"
$PYTHON = "$ROOT\work\toolchain\python\python3.exe"

git -C $SOURCE rev-parse HEAD
git -C $SOURCE status --short
git -C $VERIFY checkout --detach f282454e8fb79a529894598b0af9a3d7008fd84c

Set-Location "$VERIFY\android-app"
npm ci --ignore-scripts --no-audit --no-fund --cache "$ROOT\work\npm-cache"
npm explain @xmldom/xmldom uuid
npm audit --json
npx cap copy android
npx cap sync android

$env:JAVA_HOME = $JAVA_HOME
$env:ANDROID_HOME = $SDK
$env:ANDROID_SDK_ROOT = $SDK
& "$VERIFY\android-app\android\gradlew.bat" --version
& "$VERIFY\android-app\android\gradlew.bat" :app:dependencies --configuration releaseRuntimeClasspath --no-daemon
& "$VERIFY\android-app\android\gradlew.bat" :app:lintRelease :app:bundleRelease :app:assembleRelease --no-daemon --offline
& "$VERIFY\android-app\android\gradlew.bat" :app:compileReleaseJavaWithJavac --no-daemon --offline --max-workers=1 --no-watch-fs --no-build-cache --stacktrace

$env:PYTHONUTF8 = '1'
& $PYTHON "$VERIFY\tests\android_release_optimization_test.py"
& $PYTHON "$VERIFY\tests\native_inference_resource_contract_test.py"
& $PYTHON "$VERIFY\tests\native_report_evidence_quota_test.py"
& $PYTHON "$VERIFY\tests\native_capture_safety_contract_test.py"
& $PYTHON "$VERIFY\tests\native_dashcam_contract_test.py"

& "$SDK\build-tools\35.0.0\apksigner.bat" verify --verbose --print-certs "$ROOT\work\app-release.apk"
& "$SDK\build-tools\35.0.0\aapt2.exe" dump badging "$ROOT\work\app-release.apk"
& "$SDK\build-tools\35.0.0\aapt2.exe" dump xmltree "$ROOT\work\app-release.apk" AndroidManifest.xml
& "$JAVA_HOME\bin\jarsigner.exe" -verify "$ROOT\work\app-release.aab"
& "$JAVA_HOME\bin\jarsigner.exe" -verify -strict -verbose -certs "$ROOT\work\app-release.aab"
& "$JAVA_HOME\bin\keytool.exe" -printcert -jarfile "$ROOT\work\app-release.aab"
& "$JAVA_HOME\bin\jar.exe" --validate --file "$ROOT\work\app-release.aab"
& "$JAVA_HOME\bin\java.exe" -jar "$ROOT\work\toolchain\bundletool-all-1.18.3.jar" validate --bundle "$ROOT\work\app-release.aab"
& "$JAVA_HOME\bin\java.exe" -jar "$ROOT\work\toolchain\bundletool-all-1.18.3.jar" dump manifest --bundle "$ROOT\work\app-release.aab" --module base

& "$SDK\platform-tools\adb.exe" devices -l
rg -n "kapt|kotlin-kapt|annotationProcessor|ksp" "$VERIFY\android-app\android"
rg -n "Content-Security-Policy|usesCleartextTraffic|networkSecurityConfig|debuggable|testOnly" $VERIFY
```

Additional read-only inspection used PowerShell/.NET ZIP enumeration and hashing, `git cat-file` for canonical blob comparisons, and a local Node.js history scanner over all 2,537 unique Git blobs. Downloads were made only from official Adoptium, Python, Google Android, Gradle, and GitHub release endpoints and were checked against publisher metadata. No write-capable repository workflow was run.

## J. Evidence for every conclusion

| Conclusion | Evidence class | Evidence |
|---|---|---|
| Exact commit and unchanged source | Repository | `git rev-parse`, clean `git status`, and SHA-256 comparison of all 847 tracked files against the pre-verification inventory: 0 mismatches |
| Gradle wrapper integrity | Build | Pinned distribution checksum matched official download; official wrapper JAR checksum matched; Gradle 8.14.3 executed |
| Actual Android dependencies | Build | Successful complete `releaseRuntimeClasspath` resolution |
| xmldom/uuid reachability | Build | `npm ci`, `npm explain`, live `npm audit`, negative Android runtime graph result |
| KSP/KAPT applicability | Build/source | Plugin/dependency declarations plus repository-wide negative KAPT search |
| Release reproducibility limitation | Build | Clean-checkout missing generated file; repeated Gradle failures with stack traces; independent read success on affected JARs |
| Published artifact identity | Artifact/release | GitHub release digests matched local SHA-256; APK assets matched canonical commit blobs |
| APK signing | Artifact | `apksigner` v2 verification and pinned certificate match |
| AAB signing differential | Artifact | normal and strict `jarsigner`, ZIP entry order, `jar --validate`, Bundletool validation |
| Manifest/permissions/components | Artifact | `aapt2` APK manifest and Bundletool AAB manifest dumps |
| Backup, FileProvider, logging | Source/artifact | merged manifest, XML rules, packaged Capacitor config, provider paths |
| SEC-001–SEC-016 | Source/build/artifact | Per-finding line references, resolved graphs, packaged asset comparisons, and five passing contract suites above |
| Device behavior | Limitation | no emulator/device; adb could not enumerate in sandbox; therefore explicitly not device-confirmed |
| Tool coverage | Tool output | npm/Gradle/Android/Java/Bundletool/test outputs; unavailable tools explicitly excluded |

The verification did not infer device behavior from passing source contract tests. Likewise, artifact inspection does not substitute for a reproducible clean build. These limits are carried into the production gate.

## K. Production security gate

The gate fails. Multiple confirmed Medium findings affect credentials, deletion semantics, RTSP transport, remote-content resource use, spend controls, build-workflow trust, and build-tool dependencies. The published AAB also fails strict JAR signature verification. A clean independent release and the required Android device tests are incomplete, so the remaining uncertainty cannot support production approval.

SECURITY GATE:
FAIL

PRODUCTION BLOCKERS:
- SEC-001, SEC-002, SEC-003, SEC-004, SEC-006, SEC-007, SEC-008, NEW-001, and NEW-002; incomplete clean release build/lint; and missing controlled Android device verification.

NEXT REQUIRED ACTION:
- Remediate the listed blockers in a separate authorized phase, then repeat a clean reproducible signed APK/AAB build, strict artifact verification, dependency scans, Android lint, and the full controlled device test matrix before reconsidering the gate.
