# SEC-006 application-wide AI spending controls

STATUS: RESOLVED

This status covers the current source tree and focused verification. Android Keystore/device execution and deployment are not claimed.

Repository: `coding-parrot/pothole-reporter`.
Verified base: `f282454e8fb79a529894598b0af9a3d7008fd84c`.
Date: 2026-09-14. Work remains uncommitted in the existing tree.

## Vulnerability, root cause and affected paths

Native detection/repair already had per-request output-token ceilings, but those did not bound repeated app-wide spending. Native Drive and the WebView credential gateway were independent network entry points. JS photo/repair, streamed-to-JSON fallback and tender matching could omit an explicit output-token ceiling. Retries, repeated scans and simultaneous requests had no shared persistent reservation gate.

Paid application paths inspected:

- `NativeInferenceEngine` → `NativeInferenceTransport.detect` / `verifyRepair` → tracked OkHttp call.
- JS `analyzeImage` → `oaiStream` / `oai`, including one streamed-to-JSON fallback; tender matching → `oai` → `CredentialBroker.request` → `NativeCredentialPlugin.openAiRequest`.
- Native Drive launch/model configuration in `static/index.html`, request builders, bounded detection voting/replay loops, credential retention and existing contracts.

The application has no Python/backend inference path. `eval/` contains separate operator-invoked evaluation clients, not reachable through app/WebView operations; they were identified in the search, not executed or modified. The preserved `/v1/models` browser prewarm is a metadata GET, not paid inference. App spending controls do not regulate external use of the same API key.

## Central policy and default budget

Both paid native entry points call `NativeAiUsageBudget.reserve`, using the same canonical native-owned ledger at `noBackupFilesDir/ai_usage_budget/usage.bin`. `PersistentAiUsageBudget` owns validation and the serialized reservation transaction; `AiOutputPolicy` owns approved identities and ceilings.

| Policy | Limit |
| --- | --- |
| Lifetime provider request reservations per installation | 32 |
| Lifetime reserved maximum output tokens | 32,768 |
| Detection output ceiling | 1,536 tokens, existing native limit preserved |
| Repair output ceiling | 768 tokens, existing native limit preserved |
| Tender matching / bounded general request ceiling | 512 tokens |
| Provider and endpoint | OpenAI, exactly `https://api.openai.com/v1/responses` |
| Models | Existing `gpt-5-mini` and `gpt-5.6` allowlist |

This is a deterministic request/output reservation quota, not a monetary estimate or actual provider token meter. It does not invent pricing, billable input-token precision or a dollar guarantee. Request count also bounds repeated input-bearing calls; existing request/image bounds remain unchanged. There is no automatic daily refill, clock-based reset or WebView budget-setting/reset API. The exhaustion message is **"AI usage limit reached."**, without a promise of a timed refill.

JS builders and the common request entrance now attach explicit finite `max_output_tokens`. Native bridge policy independently defaults omitted limits, clamps valid positive integers to the purpose ceiling, and rejects invalid types, non-positive values, out-of-range integers and unapproved purposes/models. Native-transmitted JSON contains the normalized value; its reservation identity uses that same value. Native Drive reserves the existing request-builder constants.

The gateway admits only existing request fields. Extra paid tools, alternate service tiers, background/conversation continuations and client usage fields cannot create a different paid operation behind an approved identity. Provider/model/endpoint/output ceiling are checked by the authoritative native budget before transmission. A native transport created without a gate fails closed.

## Reservation, reconciliation and failure behavior

Each attempted transmission permanently reserves one request and its full requested maximum output allowance before network I/O. The accounting model pessimistically finalizes the entire reservation for every outcome. Reconciliation never credits unused output, even for a successful response reporting less usage. Provider/client usage values are not accounting inputs and cannot refund, inflate or make counters negative. This avoids trusting unvalidated usage reports or guessing how much a cancelled/interrupted request was billed.

Connection failure, authentication failure, timeout, cancellation, malformed output and process termination retain the reservation. A failure before reservation/network does not spend a request; a failure after reservation may consume quota without generating a paid request. This intentional over-accounting favors safety. There are no pending-reservation refunds to recover on restart and no retry route that bypasses reservation.

Native policy denial is a suspending inference error; the credential bridge returns only the safe `AI_USAGE_LIMIT` code/message. JS maps that code to a fatal error, preventing streamed-to-JSON paid fallback. Tender matching propagates budget denial rather than swallowing it. No uncontrolled provider or paid fallback was added.

## Concurrency and retries

Canonical-path synchronization serializes threads and instances; a ledger file-channel lock serializes cooperating native processes. Validation, reading/decrypting state, remaining-budget checks, key rotation and durable write occur within the reservation transaction. Subtraction checks precede additions; persisted requests/output must be non-negative and within finite maxima.

Existing native detection voting remains at most three attempts, and JS inference fallback remains at most one additional request. Every actual application attempt re-enters the shared gate. Continuous scan/replay work cannot generate more paid requests after quota exhaustion. Both production AI clients disable connection recovery and redirects. Every paid POST also wraps its body in `NonReplayableAiBody`: `isOneShot()` prevents status-based follow-ups, and an atomic write-once check rejects any second body transmission before writing input. A later application attempt creates a new body and requires a new reservation. Existing connection/stream deadlines and cancellation controls are preserved.

Connection-retry flags alone do not prevent OkHttp 4.12's `503 Retry-After: 0` follow-up. Its [RetryAndFollowUpInterceptor source](https://raw.githubusercontent.com/square/okhttp/parent-4.12.0/okhttp/src/main/kotlin/okhttp3/internal/http/RetryAndFollowUpInterceptor.kt) checks one-shot bodies before resending, including HTTP status follow-ups. A local HTTP regression test verifies that a queued retry response produces only one request and one reservation; a body unit test verifies that attempted reuse writes no bytes.

## Persistence, encryption, tampering and corruption

Ordinary private-file placement was insufficient as an authority: the installed privileged Filesystem capability accepts native file paths, so WebView-controlled filesystem operations could target a ledger. The final implementation therefore uses a separate Android Keystore AES-GCM record key, rotated at the same alias for each reservation, plus a permanent Keystore initialization marker. This addresses SEC-006 state tampering/rollback without changing the Filesystem dependency or its unrelated behavior.

The 24-byte internal payload contains magic/version and two `Long` counters. It is persisted only as a fixed 53-byte authenticated envelope: version, 12-byte IV, ciphertext and 128-bit GCM tag. Associated data binds it to the AI-budget format. Counters, keys, credentials, prompts and responses are not exposed through a budget bridge. Keys are generated in Android Keystore; neither exported key bytes nor source/preferences/WebView key material are used. Budget aliases are distinct from SEC-001 credential aliases.

Current-key replacement happens **before** writing the next ledger. Earlier valid ciphertext becomes invalid under the current key, so replaying a saved ledger cannot refund usage. A crash or failed write after rotation can permanently block inference, but cannot turn an old record into a fresh allowance. The permanent marker survives file/directory deletion; deleting the whole budget directory does not authorize initialization again. Missing/partial keys, missing files, unexpected record size/version, decryption/authentication failure, invalid counters and unavailable storage all fail closed.

The file write is forced to durable storage before return. The Android adapter additionally fsyncs the ledger directory and its native parent before allowing network transmission. Failure to sync blocks transmission. No automatic corruption recovery/refill is exposed. First-run initialization is allowed only for a newly created directory with neither budget Keystore alias present; first reservation writes charged state. There was no preexisting application budget to reconstruct or migrate. Credential migration remains untouched.

Android documents Keystore-backed AES-GCM generation in [KeyGenParameterSpec](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec). Alias replacement behavior is corroborated by the platform [AndroidKeyStore key-generator source](https://android.googlesource.com/platform/prebuilts/fullsdk/sources/android-30/+/refs/heads/androidx-datastore-release/android/security/keystore/AndroidKeyStoreKeyGeneratorSpi.java), which removes prior alias entries before generation. Platform lifecycle behavior still needs the added device tests; it was not executed on Windows.

Budget metadata is deliberately retained through app credential/media deletion, preventing those app operations from refilling quota. Full operating-system app-data reset/uninstall, compromise of Android Keystore/native execution or external API-key usage is outside an installation-local policy's authority.

## Browser/PWA behavior

Browser-owned accounting cannot authoritatively constrain the JS that owns or resets it. The browser paid-inference branch now fails closed before provider fetch with **"AI inference is available only in the Android app."**. No backend or pretend-secure browser quota was introduced. Existing memory-only browser credential handling and SEC-016 shortcut behavior were not remediated. Native WebView inference remains supported within the authoritative quota. Browser paid inference is intentionally unavailable under this security policy.

## Verification performed

| Check | Final result |
| --- | --- |
| Cached Kotlin compiler, all application Kotlin plus focused JVM test sources | PASS; three existing deprecation warnings |
| `AiUsageBudgetTest` | PASS: 23 JVM tests |
| `AiOpenAiBudgetPolicyTest` | PASS: 5 JVM tests using real `org.json` parsing |
| `NativeAiBudgetTransportTest` | PASS: 4 local MockWebServer tests |
| `NonReplayableAiBodyTest` | PASS: 2 JVM tests |
| Existing `NativeOpenAiRequestPolicyTest` | PASS: 1 JVM test |
| Existing `NativeInferenceTransportTest` | PASS: 7 JVM tests; existing assertions retained, budget fixture added |
| Existing SEC-005 bounded framer/strict JSON class | PASS: 20 JVM tests |
| Existing native inference request tests | PASS: 2 JVM tests |
| Total focused JVM run | **PASS: 64 tests** |
| `tests/sec006_ai_request_test.cjs` | PASS: 38 JS checks |
| `tests/sec006_ai_flow_test.cjs` | PASS: 9 Chrome browser/native-gateway-mock checks |
| `tests/sec006_ai_budget_contract_test.py` | PASS: 21 production wiring/security checks |
| SEC-001 storage contract and Chrome credential flow | PASS |
| SEC-002 media registry contract | PASS: 68 checks; original writer hashes/rules retained |
| SEC-003 RTSP contract | PASS: 19 checks |
| SEC-004 bounded download contract | PASS: 29 checks |
| SEC-005 inference contract / deterministic JS suite | PASS: 15 checks / 24 tests |
| Existing inference resource contract | PASS: 11 guards, including full-frame and token controls |
| Node syntax, incremental diff inspection, `git diff --check` | PASS |
| Production credential-shaped literal scan | PASS; matched values never printed |

Tests cover native/JS ceilings and safe defaults; invalid/negative/overflow values; shared native/JS accounting and retries; repeated/exact quota exhaustion; concurrent output and request-count spending; reconstructed budget instances; failures/cancellation/timeouts/malformed outcomes; corrupt/missing/oversized files; validly encrypted invalid counters; unkeyed forgery; old-record replay; entire-directory deletion; key loss; failed durability after key replacement; encrypted retained counters; safe errors and no credential logging. MockWebServer verifies actual native request JSON and that exhaustion, missing policy, incorrect endpoints and implicit `503` follow-ups cause no additional HTTP transmission. Body tests additionally verify unchanged content metadata, first transmission and rejection of reuse before input bytes are written.

The JVM key provider simulates protected key persistence across instances and uses real JVM AES-GCM. It is test-only, not the Android production key provider. Chrome native-gateway tests are mocks, not Android runtime tests. The missing test JARs were downloaded from primary Maven HTTPS at already-declared versions (`org.json:json:20250517`, MockWebServer 4.12.0); no dependency/build versions changed. All inference HTTP was synthetic/loopback. **No paid API calls, real credentials or `.env` credentials were used.**

Tests failed: **none in final runs**. Interim compiler/test-harness assertions were corrected during implementation. The initial SEC-002 contract rejection correctly required ownership review of the new ledger writers; the inventory was extended only for those two audited files, without relaxing existing checks.

Tests blocked/not run:

- The two added `AiBudgetKeyLifecycleInstrumentedTest` device tests, covering real alias replacement/non-exportability, reinstantiation, file rollback and directory deletion. They were not compiled/executed as an Android instrumentation suite here.
- Full Android Gradle/device/APK verification: previously documented transformed-jar permission and ADB blockers remain unchanged and were not retried. No rebuilt APK is claimed.
- Legacy Python browser/live-provider evaluation suites requiring unavailable Python Playwright or `.env` keys were not run. Their relevant parser properties were covered by deterministic local tests. No paid evaluation was attempted.

## Exact application/test/report files changed

Application/test paths are relative to `work/pothole-reporter`:

1. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/AiUsageBudget.kt` — new central policy and encrypted reservation ledger.
2. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeAiUsageBudget.kt` — shared Android ledger and durability adapter.
3. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/AndroidAiBudgetAuthenticator.kt` — separate Keystore marker/rotating AES-GCM record key.
4. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeCredentialPlugin.kt` — token normalization, approved paid fields, reservation and safe denial; non-replayable POST and connection recovery/redirects disabled.
5. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceTransport.kt` — shared gate before HTTP; non-replayable POST and connection recovery/redirects disabled.
6. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceEngine.kt` — authoritative Android budget wiring.
7. `static/standalone.js` — explicit ceilings, fatal budget denial and browser paid-inference rejection.
8. `docs/standalone.js` — exact mirror.
9. `android-app/www/standalone.js` — exact mirror.
10. `android-app/android/app/src/main/assets/public/standalone.js` — exact existing generated mirror, ignored by Git.
11. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/security/AiUsageBudgetTest.kt`.
12. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/security/AiOpenAiBudgetPolicyTest.kt`.
13. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/security/AiBudgetTestKeys.kt` — test-only simulated protected keys.
14. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeAiBudgetTransportTest.kt`.
15. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeInferenceTransportTest.kt` — persistent budget fixture only; prior assertions retained.
16. `android-app/android/app/src/androidTest/java/dev/aiengg/potholereporter/security/AiBudgetKeyLifecycleInstrumentedTest.kt` — blocked device suite, test aliases only.
17. `tests/sec006_ai_request_test.cjs`.
18. `tests/sec006_ai_flow_test.cjs`.
19. `tests/sec006_ai_budget_contract_test.py`.
20. `tests/sec002_media_cleanup_contract_test.py` — append-only ownership inventory for the two new non-media budget writers.
21. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NonReplayableAiBody.kt` — paid input can be transmitted only once per gated request.
22. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/security/NonReplayableAiBodyTest.kt`.
23. `outputs/SECURITY_REMEDIATION_SEC006.md` in the workspace — this report, the only report created/updated.

Compilation classes, argument files, downloaded test JARs, phase snapshots and incremental review scripts are scratch artifacts under workspace `work/sec006-*`, outside the repository.

## Scope preservation and remaining limitations

Phase-start hashes show exactly nine existing application/test files changed, all listed above. Prior reports, credential cryptography/storage/migration, native media cleanup, RTSP, bounded parser classes, index/config/build/dependency files remain unchanged. Native `readSse`, the complete SEC-005 JS parser/deadline block, SEC-004 downloader block and every relevant pack downloader/validator remain identical. Existing protection contracts pass. Necessary gate wiring extends existing AI entry points; it does not undo earlier remediations. SEC-001 through SEC-005 protections were preserved, including SEC-005's previously reported native-bridge cancellation limitation. Permanent reservations remain consistent across that limitation.

SEC-007 through SEC-016 and NEW-001/NEW-002 were **not remediated or modified**. No Uzbekistan features, backend, broad upgrades, commits or pushes were introduced.

Remaining limitations: real Android Keystore/filesystem lifecycle and deployment await the blocked device/build environment; existing APKs remain unchanged. Conservative lifetime accounting can exhaust earlier than actual billed usage and can block permanently after a failed key/write transaction or corruption. There is no automatic refill/recovery and no browser paid inference. It is an installation-local app quota, not an account-wide monetary spending guarantee or protection against operating-system reset/root compromise/external key usage. Live-provider compatibility with the new JS ceilings was not tested through paid calls.
