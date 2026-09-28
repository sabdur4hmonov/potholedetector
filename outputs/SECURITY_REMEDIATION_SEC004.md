# SEC-004 — Bounded remote pack downloads

**STATUS: PARTIALLY RESOLVED**

Date: 2026-09-14. Repository: `coding-parrot/pothole-reporter`. Audited base commit: `f282454e8fb79a529894598b0af9a3d7008fd84c`. Work continued the current uncommitted SEC-001 through SEC-003 tree. Source-level bounded downloading and focused verification pass. Actual Android WebView/proxy execution and replacement-artifact verification remain unperformed; no APK was rebuilt or replaced.

## Original vulnerability, root cause and affected path

Five remote binary pack downloaders in `static/standalone.js` called `response.arrayBuffer()` before validating expected byte length, SHA-256 and schema: state routing/tenders, National Highway tiles, highway contracts, procurement notices and current agreements. A malicious successful response could therefore allocate its entire body before rejection. Content validation and an AbortController timer did not impose a streaming memory ceiling.

Directly related manifest loaders called `response.text()` before their 128 KiB or 512 KiB checks. These manifests select the pack resources and were included in the same remediation.

The focused trace covered these entry points, manifest size/hash metadata, existing validators, `load*` consumers, memory/IndexedDB activation, local cache reads and the installed Capacitor GET implementation. Native code does not implement a separate pack downloader. The installed Android bridge routes GET through `/_capacitor_http_interceptor_`; `WebViewLocalServer.handleCapacitorHttpRequest` returns an HTTP InputStream in a WebResourceResponse. That proxy streams rather than using the generic CapacitorHttp response-to-byte-array/JSON helpers.

## Changes and size limits

Added one authoritative internal `downloadPackResource` path, shared by all five pack downloaders and all current manifest loaders. Its limits are centralized in `PACK_DOWNLOAD_LIMITS`, retaining the existing numeric policies:

| Resource | Hard maximum |
| --- | --- |
| State routing/tender pack | 16 MiB |
| Highway tile, contract, notice or agreement pack | 8 MiB |
| State/optional-catalog manifest | 128 KiB |
| Highway manifest | 512 KiB |

Pack decoded-body allocation is additionally limited to the exact positive `resource.bytes` value from the validated manifest. The current largest declared state pack is 2,147,041 bytes; highway tile 817,894; contract 188,248; notice 657,509; agreement 295,540. No new arbitrary large limit was introduced. Manifest ceilings now apply to bytes before UTF-8 decoding rather than string length after allocation.

The path now:

1. Validates configured limits/expected-size and hash syntax before fetching, and uses a fixed GET with omitted credentials/referrer.
2. Rejects bad HTTP status before examining body content.
3. Validates Content-Length when exposed. Missing length is allowed; empty, signed/negative, fractional, duplicate/comma-separated, nondecimal, unsafe-integer and oversized values fail closed before a reader or destination buffer is acquired.
4. Requires a readable response stream. There is no fallback to `arrayBuffer`, `text` or a fully buffered native response.
5. Allocates one fixed Uint8Array bounded by the validated expected size or manifest maximum. It retains no accumulating chunk list.
6. Checks each received chunk against the remaining cumulative budget **before copying**. Identity responses are also checked against declared length; an identity declaration inconsistent with the expected pack size is rejected before reading. Exact-limit content is accepted only after EOF and subsequent validation.
7. Rejects early EOF, interruptions, oversized streams and invalid data. Stalled reads race cancellation so timeout or explicit cancellation can end them.
8. Runs existing exact-size, SHA-256, fatal UTF-8 and resource schema/identity validators before returning `{pack, bytes}` to activation/cache consumers.
9. Cancels failed response bodies, releases reader locks, removes cancellation listeners/timers and drops partial buffers. No partial temporary file or IndexedDB record is written by the downloader.

Existing 30-second state/highway deadlines and 1.5-second optional-catalog deadlines were preserved and applied to the shared path. State/highway manifests also receive an overall request/read deadline. No downloader retry loop was added. Existing cache-write retries remain bounded to the existing initial write and one retry, using only complete verified data.

### Android buffering boundary

Android pack requests now explicitly use the original `CapacitorWebFetch` and the installed GET InputStream proxy. This avoids depending on the generic patched fetch dispatch choosing a streaming implementation and avoids CapacitorHttp.request's fully buffered response construction. The server origin must match the current page origin; missing original fetch/proxy support fails closed. Same-origin manifests use the original fetch directly.

No Capacitor configuration, Java/Kotlin source, dependency, network permission or security policy was changed. A source contract checks that the installed proxy still returns the InputStream without `readData`, `buildResponse`, `readAllBytes` or byte-array buffering. This is source evidence, not proof of actual WebView cancellation or buffering behavior on a device.

## Integrity, decompression and partial-state handling

Existing SHA-256 checks were preserved, including exact expected byte length, lowercase 64-hex metadata, fatal UTF-8 decoding, envelope/identity checks and resource-specific schema validation. Hashes are public integrity values; the existing strict equality comparison remains unchanged. No weaker checksum, signature bypass or new manifest trust model was introduced. Manifests retain their existing schema/URL/hash-metadata validation; this task does not claim they gained cryptographic signatures.

Only fully verified packs reach existing cache/memory activation. The routing validator is the sole validation callback that installs contact state; it now receives the cancellation signal and checks it immediately before installation. Other validators remain side-effect-free. A failed new download cannot overwrite a valid cache entry or install an invalid pack. Existing invalid-local-cache handling remains unchanged.

There is **no application archive extraction, ZIP/TAR processing or application inflater** in this path. No archive logic was added. HTTP gzip/br/deflate decoding is performed by Fetch/platform networking. The stream reader bounds the exposed decoded bytes, so expanded output cannot accumulate beyond the pack budget. Encoded Content-Length, when present, is independently capped at the resource maximum; it is not incorrectly compared to decoded byte length. Unknown/stacked encodings fail closed.

Fetch does not expose raw compressed wire-byte counts. HTTP framing/compressed-input consumption and decoder working buffers remain platform responsibilities; this implementation does not claim to measure hidden wire bytes or implement a separate compressed-stream limiter. The overall deadline bounds waiting, and application-owned accumulation is bounded regardless of missing length or decoding expansion. Actual compressed InputStream behavior on Android remains a runtime verification item.

No partial download files require deletion because this path uses bounded memory. Failure/cancellation returns null; partial arrays are discarded. IndexedDB receives a Blob only after integrity/schema validation. Storage failure preserves the existing behavior of allowing the complete verified pack for the session if persistent caching fails; unsafe partial content is never substituted.

## Exact files changed

Application repository root: `C:/Users/user/Documents/Codex/2026-09-09/bro/work/pothole-reporter`.

- `static/standalone.js` — shared bounded downloader, manifest/pack wrappers and cancellation check before routing-contact installation.
- `docs/standalone.js` — exact mirror.
- `android-app/www/standalone.js` — exact mirror.
- `android-app/android/app/src/main/assets/public/standalone.js` — exact generated mirror, ignored by Git.
- `tests/sec004_bounded_download_test.cjs` — new deterministic production-function tests.
- `tests/sec004_download_contract_test.py` — new focused source/proxy contracts.
- `tests/sec004_pack_flow_test.cjs` — new browser/cache integration and native-proxy-mock tests.

Only new documentation: `C:/Users/user/Documents/Codex/2026-09-09/bro/outputs/SECURITY_REMEDIATION_SEC004.md` (this report). Prior reports were not rewritten. Workspace-local `work/sec004-*` edit/review helpers, baseline hashes, a pre-change JS snapshot and incremental diff are outside the application repository.

## Tests actually passed

| Check | Result |
| --- | --- |
| `sec004_bounded_download_test.cjs` | **PASS — 23 deterministic tests.** Below/exact/above-limit declaration, missing length, cumulative excess, smaller declaration, malformed/negative/invalid length, status ordering, early EOF/interruption, missing stream, timeout, pre/during-read cancellation, simulated decoded compression expansion, encoded declaration ceiling, valid differing encoded/decoded lengths, invalid encoding/metadata, actual production SHA validator, failed replacement preserving existing memory/cache, simulated cache failure, 100 repeated failures with fixed allocation counts/released readers/no retry, and native streaming dispatch. |
| `sec004_download_contract_test.py` | **PASS — 29 checks.** Header/read/copy/activation ordering, cancellation/cleanup, all five wrappers and integrity validators, all manifest paths, existing installed Android InputStream proxy assumptions, absence of full-response helpers in the pack path and mirror equality. |
| `sec004_pack_flow_test.cjs` | **PASS — 14 browser/native-proxy-mock scenarios.** All five pack families use actual production validators and verified fixtures; corruption is rejected without cache mutation or automatic retries. Browser Fetch/IndexedDB exercised through local pages and Playwright response fixtures. Android proxy behavior was mocked, not executed natively. |
| JavaScript syntax | **PASS** — production standalone client and both new Node test scripts. |
| Existing `national_highway_pack_test.py` | **PASS** — current pack metadata/fixtures. |
| Existing `pages_assets_test.py` | **PASS**. |
| Existing `full_frame_invariant_test.py` | **PASS — 18 checks**. |
| Existing SEC-001 credential-storage contract | **PASS — 13 checks**. |
| Existing SEC-002 media-cleanup contract | **PASS — 68 checks**, including unchanged storage-writer review barriers. |
| Existing SEC-003 transport contract | **PASS — 19 checks**. |
| Scope/hash comparison and incremental diff review | **PASS** — only the four intended existing JS downloader/mirror files differ from the phase baseline; every other captured repository file and previous report is unchanged. Existing credential/media implementation prefix is unchanged; native SEC-001/002/003 implementations and SEC-003 UI/tests are unchanged. New test files and resulting incremental diff inspected. |
| Git whitespace check | **PASS**, using CR-at-EOL handling for the existing Windows checkout. |

Tests instrument fixed destination allocations and reader cleanup, not total process heap usage or OS network buffers. Compression-size tests supply simulated decoded chunks; no hostile real compressed network server was exercised. No real credential or destructive resource-exhaustion payload was used.

### Tests actually failed during development

Initial deterministic-test integrity coverage failed because its isolated VM omitted the global crypto binding; the test harness was corrected. Initial browser integration failed because Windows checkout conversion changed fixture JSON's terminal LF to CRLF, and a selected notice catalog was outside its review window. The fixture server now serves canonical LF bytes and verifies their pinned hash before delivery, and the test clock is explicitly fixed to 2026-08-29 for all fixture review windows. A cache-inspection fixture was corrected to use the actual `potholes` IndexedDB store rather than a nonexistent exported helper.

These were test-harness/fixture failures. Production payload files, manifest hashes and review deadlines were not changed, and integrity checks were not weakened. **No final executed focused check remains failed.**

## Tests blocked or not attempted

- Existing `state_pack_test.py`: **BLOCKED before assertions** by Python `ModuleNotFoundError: playwright`. The available Node Playwright suite covers the changed pack/cache flow, but the full existing Python browser suite is not claimed to pass.
- Android WebView/proxy runtime, cancellation/connection closure, compressed response handling and replacement APK verification: **not performed**. The prior documented Windows Gradle `AccessDeniedException` and unavailable ADB session remain environment limitations. The full build/device blocker was not retried.
- Kotlin/Java compilation: **not applicable to changed source**; no native source changed. No dependency upgrade, full build or unrelated environment workaround was attempted.

## Remaining risks and scope confirmation

The source no longer fully buffers any audited remote pack or manifest before applying its byte ceiling. Relevant focused tests pass. Actual Android proof still requires a built test artifact: verify normal pack availability, declared/missing-length excess rejection, gzip/br handling, cancellation closing the InputStream, bounded WebView/native memory behavior and unchanged valid-cache retention. Installed/shipped older APKs remain vulnerable until replaced. These runtime/artifact gaps keep status **PARTIALLY RESOLVED**.

Local cached Blob/ArrayBuffer conversions and the 12-byte image-header conversion remain distinct from remote pack downloading. Unrelated GIS/API JSON responses, inference/SSE transport and remote media helpers were not changed and are not claimed to have gained this download limit. JSON parsing and validated pack caches consume additional bounded application memory; platform decoder buffers and aggregate concurrent-work memory were not heap-profiled here.

**SEC-001 through SEC-003 were preserved. SEC-005 through SEC-016 and other unrelated findings were NOT intentionally remediated.** No Uzbekistan features, backend, unrelated redesign, broad audit, dependency upgrade, new native storage writer, commit or push occurred. Stop after SEC-004.

**Final SEC-004 status: PARTIALLY RESOLVED.**
