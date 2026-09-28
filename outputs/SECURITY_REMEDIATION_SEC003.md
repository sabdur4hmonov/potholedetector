# SEC-003 remediation — Unencrypted RTSP / dashcam transport

**STATUS: PARTIALLY RESOLVED**

Date: 2026-09-14. Repository: `coding-parrot/pothole-reporter`. Audited base: `f282454e8fb79a529894598b0af9a3d7008fd84c`. This phase continued the existing uncommitted SEC-001/SEC-002 tree. Nothing was committed or pushed.

The source-level production dashcam path now fails closed for every endpoint. Focused verification passes. Android packaging, device execution and verification of a replacement APK remain unavailable; the previously shipped APK has not been replaced and must still be treated as vulnerable.

## Original vulnerability and architecture audit

`NativeFrameSourceConfig.create` accepted plaintext RTSP URLs. The bridge read the retained dashcam URL inside native code and passed the source configuration through `DriveForegroundService` to `NativeRtspFrameSource`. That source created a Media3 RTSP media source, optionally using the Wi-Fi network's socket factory, and forced RTP over TCP. Routing to Wi-Fi and TCP interleaving provided neither encryption nor authenticated peer identity.

Inspected the source/configuration classes, all native callers, bridge and foreground-service intent entry points, native retained-secret validation/storage, WebView settings and Drive startup, bundled mirrors, source status/error handling, reconnect/watchdog paths, Media3 dependencies, manifest/configuration and related tests. Repository searches included `rtsp://`, `rtsps://`, `Rtsp`, `RTSP`, both frame-source class names, dashcam configuration, userinfo/password handling and logging references. No second production RTSP client or JavaScript stream-connection fallback was identified.

The pinned dependency is Media3 **1.10.1**. Its factory defaults to an ordinary socket factory and merely accepts a caller-supplied factory; it does not select or configure verified RTSPS/TLS. See the pinned [RtspMediaSource source](https://raw.githubusercontent.com/androidx/media/1.10.1/libraries/exoplayer_rtsp/src/main/java/androidx/media3/exoplayer/rtsp/RtspMediaSource.java). Its client opens the host/port using that factory without TLS peer/hostname verification. See the pinned [RtspClient source](https://github.com/androidx/media/blob/1.10.1/libraries/exoplayer_rtsp/src/main/java/androidx/media3/exoplayer/rtsp/RtspClient.java).

A socket-factory extension point alone is not verified secure transport. No custom TLS wrapper, proxy, tunnel, backend or dependency upgrade was introduced. The unsupported production dashcam feature was disabled as authorized.

## Remediation and architecture after

- Added `NativeRtspTransportPolicy`, the authoritative native parsing/transport-authorization boundary. Its private native build capability for verified secure RTSP is fixed to false and cannot be enabled by bridge arguments or JavaScript settings.
- Source configuration invokes this policy before the normal bridge/service path can start dashcam capture. Both existing entry points continue to use `NativeFrameSourceConfig.create` independently. JavaScript cannot supply a connection URL to `DriveModePlugin.startDrive`; the existing native secret lookup is preserved.
- Direct construction of `NativeRtspFrameSource` invokes the same policy before Android handlers, decoder threads, storage ledgers or network resources are initialized. This also protects against directly constructing the public source-config data class instead of using its factory.
- The sole Media3 factory, Wi-Fi socket-factory lookup and endpoint handoff are inside `withProductionEndpoint`. Unsupported or plaintext endpoints throw before its client/resource callback executes. No RTSP session exists that could reach reconnect, redirect, UDP/TCP retry or downgrade logic.
- WebView settings disable the dashcam option and endpoint field. The save handler independently rejects programmatic dashcam selections, including configurations already retained natively. Drive startup rejects a saved dashcam selection before requesting Drive permissions or invoking native startup. Clear security feedback instructs the user to select Phone camera.
- Updated only dashcam security copy in the four existing locale dictionaries; the new security message currently uses English in those locales. Removed guidance suggesting trusted Wi-Fi makes plaintext RTSP acceptable. Hosted, Android www and packaged web mirrors match.
- Phone-camera detection, GPS policy, complete-frame decoding helpers, media lifecycle, permission configuration and unrelated features were preserved.

### Endpoint validation

Validation performs no DNS resolution or network access. Input is trimmed, bounded to 2,048 characters, and rejects whitespace, controls, backslashes and non-ASCII ambiguity. URI parser exceptions are replaced with fixed public errors without retaining their input-bearing cause.

Plain `rtsp` is explicitly rejected with secure-RTSP-required feedback, including old saved configurations and case variants. Only syntactically valid hierarchical `rtsps` endpoints can reach the separate capability decision; they are then rejected because this build cannot provide verified secure transport. No endpoint is currently authorized or returned to a connection callback.

Malformed/missing/unsupported schemes, opaque URIs, missing hosts, fragments, malformed escapes, ambiguous authorities, multiple userinfo delimiters, empty usernames and encoded control/backslash/nested-encoding userinfo are rejected. Hosts require valid DNS labels, canonical IPv4 or URI-validated bracketed IPv6; ambiguous numeric aliases, octal/hex IPv4, scoped IPv6 and empty/trailing labels are rejected. Ports must be absent or canonical decimal values from 1–65535; empty, padded, nonnumeric and out-of-range ports are rejected.

### Credentials, migration and certificate handling

Existing SEC-001 Android Keystore-backed authenticated encryption and native credential operations remain unchanged. No new credential store, WebView-readable credential retention or native plaintext-return API was introduced. RTSP debug logging remains explicitly disabled. Policy code performs no logging, and fixed errors/exception traces contain no submitted credentials or full endpoint URL.

Existing encrypted plaintext-scheme endpoints remain retained; their presence is not transport authorization. A saved dashcam selection fails closed and is not automatically converted, reconnected, rewritten or silently switched to phone capture. Users explicitly select Phone camera to proceed. No unrelated user data is deleted. Existing legacy browser-secret removal/native migration continues unchanged, after which the transport policy still blocks that endpoint.

There is no dashcam TLS handshake in this build, so certificate validation is **not exercised**, rather than claimed as successful. No trust-all implementation, permissive trust manager, hostname-verification bypass or cleartext exception was added. Manifest, permissions, provider configuration, Capacitor configuration and dependencies are unchanged. No `network_security_config.xml` or explicit cleartext-allowance attribute was present in the inspected app configuration; the remediation relies on the native transport gate, not an assumption that Android network policy encrypts raw sockets.

## Files changed in this phase

Repository-relative application/test paths:

1. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeRtspTransportPolicy.kt` — new native policy.
2. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeFrameSource.kt` — use authoritative policy.
3. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeRtspFrameSource.kt` — constructor and client-resource gates.
4. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeRtspTransportPolicyTest.kt` — new focused JVM tests.
5. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeFrameSourceConfigTest.kt` — replace plaintext-acceptance assertions with fail-closed assertions.
6. `static/index.html` — unsupported-feature settings and startup rejection.
7. `docs/index.html` — exact web mirror.
8. `android-app/www/index.html` — exact web mirror.
9. `android-app/android/app/src/main/assets/public/index.html` — exact generated web mirror, ignored by Git.
10. `tests/dashcam_capture_source_test.py` — adapt existing dashcam settings/startup expectations; retain phone assertions and existing native mock.
11. `tests/sec003_rtsp_transport_contract_test.py` — new security source contracts.
12. `tests/sec003_dashcam_flow_test.cjs` — new executable browser checks using the existing native mock.

Only new documentation: `C:/Users/user/Documents/Codex/2026-09-09/bro/outputs/SECURITY_REMEDIATION_SEC003.md` (this report). Prior reports were not edited. Workspace-local `work/sec003-*` orchestration scripts, baseline hashes, compiler argument files and class outputs support verification and are outside the application repository. The compile entry point is `work/sec003-native-compile.ps1`.

## Verification results

| Verification | Result |
| --- | --- |
| Direct Kotlin 2.1.0 compilation against cached Android/Media3/Capacitor dependencies | **PASS** — all native application Kotlin sources plus the two focused JVM test classes; existing deprecation warnings only. Final source compiled after diff review. This is not Gradle packaging or Java/APK assembly. |
| `NativeRtspTransportPolicyTest` and `NativeFrameSourceConfigTest`, JUnit 4.13.2 | **PASS — 20 tests.** Plaintext/case variants, unsupported valid RTSPS including IPv6/userinfo, malformed/missing/unsupported schemes, unsafe hosts/userinfo/ports, fixed errors/no credential-bearing exception cause or trace, saved plaintext rejection, zero connection callbacks, repeated secure/plaintext attempts, native config/bridge input rejection and existing phone/frame/reconnect helper contracts. |
| `sec003_rtsp_transport_contract_test.py` | **PASS — 19 checks.** Native gates, sole factory placement, bridge/service enforcement, no permissive TLS/downgrade/new store/logging, disabled settings, saved-source startup rejection and mirror equality. Source contracts supplement JVM evidence; they are not device tests. |
| `sec003_dashcam_flow_test.cjs`, Node Playwright with system Chrome | **PASS — 5 scenarios.** Legacy saved dashcam cannot start/request permissions; web endpoint acceptance blocked; programmatic save blocked with/without retained configuration; phone startup passes no credential arguments. Native operations mocked; no camera network or OpenAI request. |
| Existing `native_dashcam_contract_test.py` | **PASS — 15 checks.** Existing decoder/lifecycle/routing contracts preserved inside the disabled transport path. |
| Existing `full_frame_invariant_test.py` | **PASS — 18 checks.** |
| Existing `native_background_lifecycle_contract_test.py` | **PASS — 15 checks.** |
| Existing `native_cleanup_retry_contract_test.py` | **PASS — 10 checks.** |
| Existing `android_release_optimization_test.py` | **PASS — 17 checks.** Source release contracts only. |
| Existing `hybrid_drive_contract_test.py` | **PASS — 23 checks.** |
| Existing `sec001_credential_storage_test.py` / `sec001_credential_flow_test.cjs` | **PASS — 13 static checks and browser suite.** No secret-storage regression. |
| Existing `sec002_media_cleanup_contract_test.py` / `sec002_media_cleanup_flow_test.cjs` | **PASS — 68 static checks and 18 mocked browser scenarios.** No media-cleanup regression. |
| JavaScript syntax | **PASS** — production inline script, unchanged standalone client and new Node flow test. |
| Repository-wide sanitized credential/static scan | **PASS — 785 UTF-8 tracked/new files plus packaged mirrors included.** Fourteen key-pattern candidates classify as existing public authority IDs or synthetic fixture; 17 RTSP/RTSPS userinfo candidates classify as existing examples/tests or new synthetic rejection tests; zero unclassified candidates. Values withheld. No actual production credential used or introduced. Zero old production plaintext browser-credential writes. |
| Scope, diff and configuration checks | **PASS** — resulting diff/new files inspected; accidental encoding change restored; Git whitespace check passes with Windows CR-at-EOL handling. SHA-256 comparison confirms only the two intended existing native transport files changed in this phase; existing SEC-001/SEC-002 native implementations, both prior reports and captured network/build configurations are unchanged. Dependency/permission/provider diff checks also pass. |

## Blocked/unperformed verification

- Full Gradle build/unit-test task and Android packaging were **not retried**. The prior documented host `java.nio.file.AccessDeniedException` at `:capacitor-android:compileDebugJavaWithJavac`, involving transformed `lifecycle-viewmodel-2.6.2-api.jar`, remains an environment limitation. No upgrade or broad environment workaround was attempted.
- No Android device/emulator session, packaged-APK test, packet capture or logcat verification was obtained. Prior ADB initialization was blocked by inability to create its Android user directory. Actual release artifact enforcement and absence of dashcam packets still require an isolated Android runtime test on a newly built artifact.
- Existing `dashcam_capture_source_test.py` and `dashcam_location_fail_closed_test.py` were attempted but **BLOCKED before assertions** by Python `ModuleNotFoundError: playwright`. Available Node Playwright verifies the changed settings/startup and phone-start behavior; the unchanged location/routing browser suite is not claimed to pass.
- The legacy device streaming/recovery smoke test was not run: successful dashcam streaming is intentionally unavailable in this build. It must not be used as evidence that encrypted transport works.

Initial development checks caught a static-contract identifier mismatch and a Windows source-decoding issue; both were corrected. Final focused results above pass. No failed or mocked result is represented as Android runtime verification.

## Remaining risks and scope confirmation

The replacement application must be built, tested on Android and distributed before installed/shipped vulnerable artifacts are addressed. Verify rejected legacy/plaintext/RTSPS settings, direct bridge/service attempts, zero camera connection packets and credential-free logcat on that artifact. These packaging/runtime gaps are why status remains **PARTIALLY RESOLVED**, despite the verified fail-closed source boundary.

Dashcam functionality is unavailable by design. Restoring it requires a separately audited implementation that authenticates the peer and encrypts both RTSP control and media, including redirects/retries; changing the native capability flag alone is not an acceptable implementation. The retained dormant decoder/client code remains gated to keep this remediation small. Parser/source contracts require review when future connection entry points or library versions change.

**SEC-001, SEC-002, SEC-004 through SEC-016, NEW-001 and NEW-002 were intentionally NOT remediated in this phase.** Existing protections were preserved. No Uzbekistan features, backend, unrelated redesign/refactor, dependency/Gradle/Capacitor upgrade, security-policy weakening, commit or push occurred. Stop after SEC-003.

**Final SEC-003 status: PARTIALLY RESOLVED.**
