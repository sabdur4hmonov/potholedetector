# SEC-005 inference output remediation

Status: **PARTIALLY RESOLVED**

Repository: `coding-parrot/pothole-reporter`.
Verified base commit: `f282454e8fb79a529894598b0af9a3d7008fd84c`.
Verification date: 2026-09-14. Changes remain uncommitted in the existing working tree.

The oversized line allocation and unbounded JS output accumulation are fixed. Native Drive and browser parsing now have explicit byte, line, event, event-count and processing deadlines. Full cancellation coverage is incomplete because the SEC-001 credential gateway has no per-request cancellation interface and was required to remain exactly unchanged. A JS cancellation can stop awaiting that gateway without immediately stopping its already-running native HTTP reader. That operation remains bounded by its existing 1 MiB response ceiling and 35-second call timeout. This report therefore does not claim SEC-005 is fully resolved.

## Vulnerability and exact path

Native: `NativeInferenceEngine` calls `NativeInferenceTransport.detect` and `verifyRepair`, which track an OkHttp call, execute it, and pass the response body to `readSse`. Previously `charStream().buffered().readLine()` materialized an attacker-controlled line before the accumulated model-text UTF-8 cap was checked. Non-delta events and comments did not consume that output budget. Completion markers did not stop reading. Idle timeouts alone could be extended by continuing traffic.

Web: `analyzeImage` calls `oaiStream` or the `oai` JSON fallback. The old `drainSSE` concatenated decoded chunks and output deltas without line, transport-byte or event-count limits; streaming traffic rearmed the idle watchdog. The JSON fallback used the general full-response JSON reader. Native WebView requests pass through `CredentialBroker` to `NativeCredentialPlugin.openAiRequest`, which already bounded its buffered response independently.

## Changes and limits

| Boundary | Implemented maximum |
| --- | --- |
| Native Drive / JS parser cumulative response bytes | 65,536 bytes, including framing, metadata and comments |
| Individual SSE line, excluding CR/LF | 32,768 UTF-8 bytes |
| Aggregate SSE event data, including inserted multiline separators | 49,152 UTF-8 bytes |
| Dispatched data events, including terminal events | 512 |
| Accumulated model output | Existing native 65,536 UTF-8 bytes preserved; equivalent JS cap added |
| Whole inference operation / parser deadline | 35,000 milliseconds; monotonic processing checks and transport cancellation |
| JSON nesting | Maximum depth 32, checked before object-tree parsing |
| Preserved SEC-001 native credential gateway | Existing 1,048,576-byte response limit and 35-second call timeout |

Native framing uses fixed 4 KiB read, 32 KiB line and 48 KiB event arrays. Read size is restricted to the remaining cumulative budget plus one overflow-detection byte; that byte is rejected before line/event storage. Capacity checks precede writes. UTF-8 decoding happens only on bounded complete data and reports malformed input. Limit settings may only tighten production maxima, preventing arithmetic overflow or accidental relaxation.

JS framing uses fixed line/event arrays and checks actual `Uint8Array.byteLength` before processing or copying chunks. UTF-8 output size is computed before string concatenation or encoding; surrogate errors fail closed. SSE arrays and retained parser text are released after completion/failure. No event list is accumulated. The JSON fallback reads through the same byte/deadline boundary into one fixed 64 KiB buffer before decoding/parsing.

Browser responses without a readable stream are rejected before calling `.text()`. Only the already-bounded SEC-001 native envelope may use that fallback. Its string is checked against the tighter parser cap before allocating encoded bytes. Literal replacement characters are rejected there because the preserved native decoder can replace malformed UTF-8; this deliberately also rejects legitimate literal U+FFFD in that envelope.

For browser fetch streams, byte accounting applies to bytes delivered by the Fetch body reader, after browser content decoding. Native Drive counts bytes from the OkHttp body stream. Neither uses decoded character count as its byte budget. Runtime-owned network chunks and OkHttp/browser internal buffers are outside application allocation control; application copies, protocol frames, decoded strings and JSON trees are bounded before accumulation. Content-Length is supplementary, never a substitute for actual streaming-byte checks.

## Deadline and cancellation

Native tracked calls receive a 35-second whole-call timeout in addition to existing 30-second connection/read/write timeouts. The framer checks cancellation and elapsed monotonic time before/after reads, during byte processing and around event callbacks. Blocking network reads are interrupted by OkHttp cancellation/timeout. Input ownership uses `use`; `readSse` unconditionally cancels the call and closes the body. Terminal markers and existing early-negative decisions stop immediately rather than reading hostile trailing traffic.

JS uses a single 35-second timer plus monotonic checks that incoming chunks cannot extend. Pending reader operations race cancellation. Available fetch handles and readers are cancelled, reader locks released, timer/listeners removed and buffers relinquished on success, rejection, interruption or timeout. A late response after cancellation is cancelled without creating a JS body reader. Early-negative behavior and the missing-terminal rejection remain intact.

**Remaining cancellation gap:** `CredentialBroker.request` does not accept a caller cancellation signal; the preserved native credential plugin exposes no per-request cancel operation. Before a response handle is returned, browser HTTP work remains subject to its existing 30-second watchdog, and native credential-gateway work can continue up to its existing 35-second call timeout/1 MiB ceiling after the JS caller cancels. No late JS parser is started, but the native reader can remain active until completion or that timeout. Prompt cross-boundary cancellation requires changing that preserved gateway interface/implementation; it was not done under this request's exact-preservation constraint. Native Drive's tracked-call cancellation is implemented independently.

## Malformed input behavior

Missing field separators, unknown SSE fields, invalid metadata, invalid UTF-8, malformed JSON, excessive nesting, invalid event objects/types and non-string deltas fail closed. Standard comments, CR/LF/CRLF and multiline data are supported within all budgets. Bounded `response.*` metadata is ignored; `response.failed` and `response.incomplete` reject. An unterminated event or a stream without confirmation cannot become a final verdict. Errors contain fixed diagnostic text rather than response payloads or credentials. JS safety failures are fatal to the existing streamed-to-JSON fallback, preventing hostile framing from being retried through another parser.

Limits are deliberately suitable for this application's small structured detection/repair responses and existing 1,536/768 native output-token caps. Responses with unusually large metadata, individual deltas or more than 512 events now fail safely. Live-provider compatibility was not exercised and is a remaining validation limitation; token/cost controls were not increased.

## Verification results

| Verification | Result |
| --- | --- |
| Cached Kotlin compiler: all application Kotlin sources plus new focused test class | PASS; three existing deprecation warnings, no compile errors |
| `NativeBoundedSseReaderTest` via JUnit 4 | PASS: 20 tests |
| `node tests/sec005_inference_stream_test.cjs` | PASS: 24 deterministic JS tests |
| `node tests/sec005_inference_flow_test.cjs` with system Chrome/Node Playwright | PASS: 10 browser/native-gateway-mock scenarios |
| `python tests/sec005_inference_contract_test.py` | PASS: 15 production wiring checks |
| `python tests/native_inference_resource_contract_test.py` | PASS: 11 existing guards, including output/token caps and tracked-call stop behavior |
| SEC-001 credential storage contract and Chrome credential flow | PASS |
| SEC-002 media cleanup contract | PASS: 68 checks |
| SEC-003 RTSP transport contract | PASS: 19 checks |
| SEC-004 download contract and deterministic downloader tests | PASS: 29 checks and 23 tests |
| Node syntax check of canonical standalone source | PASS; exact mirrored sources checked |
| Incremental diff inspection and `git diff --check` | PASS; only expected SEC-005 baseline files differ |
| Credential-shaped literal scan of affected production code | PASS; values suppressed, no production credential used |

Native tests exercise generated oversized unterminated lines without materializing a huge string; exact inclusive limits and one-byte overflow; missing lengths; comments/multibyte transport accounting; multiline aggregate overflow; event-count exhaustion; strict framing/UTF-8/JSON; cancellation, input closure, interruption and deadlines including event-callback processing; terminal read termination; and invalid/overflowing limit settings. Native malformed JSON grammar tests run without Android JSON runtime dependencies.

JS tests cover the corresponding budgets, oversized headers, missing Content-Length, premature EOF, malformed fields/UTF-8/JSON, nesting, cumulative raw-byte limits, no-stream browser rejection, native buffered-envelope bounds, nonstream inference bounds, active/stalled deadlines, cancellation before/during parsing, late headers, resource release and terminal/early-negative closure. Allocation probes assert bounded destination arrays. The Chrome flow loads the real application source and substitutes synthetic provider responses; its native gateway is a mock, not an Android runtime test.

Tests failed: **none in the final run**. The new static guard initially checked an inline depth literal instead of the implementation's named constant; that test assertion was corrected and all 15 checks passed.

Tests blocked/not run:

- Existing `NativeInferenceTransportTest` integration execution requires MockWebServer and a functioning JVM `org.json` implementation, absent from the cached runtime. Its terminal test was updated to the required immediate-close behavior. The native transport itself compiled against the available Android API stubs; those stubs do not constitute runtime integration verification.
- Full Android Gradle/device verification retains the previously documented transformed-jar permission/ADB blocker. Neither was retried. No Android runtime or rebuilt APK result is claimed.
- Legacy Python `stream_completion_test.py` requires unavailable Python Playwright and loads an OpenAI key through `.env`. It was not executed or given real credentials. Missing-terminal behavior was covered in the new deterministic JS suite.

## Exact application/report files changed in this phase

Paths below are relative to `work/pothole-reporter`, except the report:

1. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeBoundedSseReader.kt` — new fixed-buffer transport framer and limits.
2. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceJsonSyntax.kt` — new strict bounded JSON grammar.
3. `android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceTransport.kt` — framer wiring, strict event validation, total call deadline and cleanup.
4. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeBoundedSseReaderTest.kt` — new 20-test focused class.
5. `android-app/android/app/src/test/java/dev/aiengg/potholereporter/drive/NativeInferenceTransportTest.kt` — immediate terminal-close expectation.
6. `static/standalone.js` — bounded SSE/JSON inference handling and cancellable returned fetch handle.
7. `docs/standalone.js` — exact mirror.
8. `android-app/www/standalone.js` — exact mirror.
9. `android-app/android/app/src/main/assets/public/standalone.js` — exact existing generated asset mirror; ignored by Git.
10. `tests/sec005_inference_stream_test.cjs` — deterministic budget/cleanup suite.
11. `tests/sec005_inference_flow_test.cjs` — Chrome browser and native-gateway-mock flow.
12. `tests/sec005_inference_contract_test.py` — production boundary guards.
13. `outputs/SECURITY_REMEDIATION_SEC005.md` in the workspace — this report, the only report created/updated.

Local compilation outputs, argument files and incremental review evidence are scratch artifacts under `work/sec005-*`, outside the repository. They are not application changes.

## Scope preservation and remaining limitations

Phase-start SHA-256 comparison verified exactly six existing files changed: native transport, its existing test and four standalone mirrors. All prior reports and all other captured native security, media, RTSP, index, dependency and configuration files remain byte-for-byte unchanged. The complete standalone prefix before timeout helpers and every line after the inference section/prewarm marker remain identical. This preserves the SEC-001 credential broker, SEC-002 media leases and SEC-004 pack downloader verbatim. SEC-001 through SEC-004 were preserved, and their relevant contracts pass.

SEC-006 through SEC-016 and NEW-001/NEW-002 were **not changed**. No Uzbekistan features, unrelated dependency upgrades, backend, real credentials, commits or pushes were introduced. Detection/repair output-token controls and complete-frame processing are unchanged. Existing APKs have not been rebuilt or replaced. The cancellation gap and blocked integration/device/live-provider verification above remain; they are not presented as passing tests or full remediation.
