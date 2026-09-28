# SEC-016 — Browser credential import through URL fragments

## STATUS

**RESOLVED — SOURCE/STATIC.** Verified 2026-09-14.

Severity is LOW (original classification preserved). The browser build no longer accepts, configures or transmits a credential taken from a URL fragment. A legacy `#key=` fragment is removed from the address bar without being read. The fix is proven by 18 deterministic checks, run in `node:vm` against the production `CredentialBroker` code. The Playwright browser flow test was updated but not executed (Playwright unavailable). No change affects Android native behavior. The overall security gate remains **FAIL** because of other existing blockers.

## Finding

Audit (`outputs/SECURITY_AUDIT.md` §SEC-016) and verification (`outputs/SECURITY_VERIFICATION.md` §SEC-016): in non-native mode, a `#key=` fragment silently set the OpenAI key. `replaceState` hid it afterwards, but the original URL could already sit in messages, clipboard, history, sync or extensions. A crafted link could replace a web user's key. The audit gave “remove before publishing the browser app”, with the production blocker being NO for Android and YES for a public browser deployment.

## Applicability

**Applicable in the current tree, in reduced form.** SEC-001 had already made the imported key memory-only (no `localStorage`) and kept fragment removal, and SEC-006 disabled browser paid inference. Before this task, the current code at `static/standalone.js:55-63` still did the following when `!NATIVE`:

1. It read `new URLSearchParams(location.hash).get("key")` into `legacyOpenAiKey`, which `readyPromise` copied into `browserOpenAiKey`, setting `openAiConfigured = true`.
2. `CredentialBroker.prewarm()` (`:165-173`, driven by engine `prewarm()` `:1451-1456`) sent that value as `Authorization: Bearer …` to `https://api.openai.com/v1/models?limit=1`.
3. `hasOpenAi()` reported the link-supplied key as configured to the UI and to AI-gated paths (`index.html` initial-settings gate `:5749`, capture gates `:3468`, `:4273`; `matchTender` `:6681`; status `:11122`). Actual inference calls still threw “AI inference is available only in the Android app”.

The browser build is published: `docs/index.html:269-270` loads `standalone.js` for the GitHub Pages site referenced by `README.md`. The audit's publishing precondition is therefore met. The Android APK sets `NATIVE` and never executed the shortcut.

## Exact affected components

- `static/standalone.js` `CredentialBroker` fragment import (pre-change `:55-63`), plus byte-identical shipped mirrors `docs/standalone.js`, `android-app/www/standalone.js` and `android-app/android/app/src/main/assets/public/standalone.js`.
- Consumers: `CredentialBroker.prewarm`, `hasOpenAi`, `readyPromise` browser branch; `index.html` Settings/capture gating.
- Test: `tests/sec001_credential_flow_test.cjs` fragment scenario, which asserted that the import configured the key.

## Data/control flow

Before: link `…/pothole-reporter/#key=<value>` → `CredentialBroker` IIFE at page load → `legacyOpenAiKey` → `browserOpenAiKey` / `openAiConfigured=true` → `history.replaceState` strips the hash → UI treats AI as configured (initial Settings can be skipped) → `prewarm()` fetches `/v1/models` with the link value as bearer token. Inference itself is refused (SEC-006).

After: link `#key=<value>` → `URLSearchParams(hash).has("key")` → `replaceState` strips the hash; the value is never read → `openAiConfigured=false` → no prewarm fetch → the user is sent to Settings. Explicit Settings entry (`storeCredentials`) is the only browser credential source. `#report-N` deep links and native mode are untouched.

## Threat model

| Actor / input | Before | After |
| --- | --- | --- |
| Attacker-crafted link (phishing, chat, QR) to the hosted web app | Silently installs an attacker-chosen key for the page session, marks AI configured, bypasses the initial Settings prompt, and makes the victim's browser send an authenticated request using that key (to an attacker-controlled OpenAI org: timing/IP/User-Agent telemetry). This is key/account confusion. | Key discarded unread and hash stripped; nothing configured or sent. |
| User or developer sharing a link containing a real key | The app's supported import encouraged credential-bearing URLs; secrets persisted in history, sync, screenshots and extensions. | No supported import, so there is no reason to build such links. A stray fragment is stripped from the current entry. |
| Visiting a link while holding an existing key | Existing key not disclosed (memory-only, SEC-001). | Unchanged. |
| Android APK / native WebView | Not applicable (`NATIVE` gate). | Not applicable; test confirms native ignores the fragment and never migrates it. |

## Attack preconditions

Browser (non-Capacitor) deployment, such as GitHub Pages or a local static server. The victim opens an attacker-supplied or credential-bearing link. No code execution, network position, device access or native access is needed. The attack is remote in the malicious-content/social-engineering sense. It yields no access to the victim's own credential, and no paid inference, because SEC-006 blocks browser inference.

## Security impact

LOW. It covers integrity of the browser credential state (attacker-chosen key accepted without user action), an attacker-observable authenticated request, and the handling of credential-bearing URLs. There is no confidentiality loss of an existing victim key, no native impact and no paid-inference abuse in the current tree.

## Existing mitigations

- `!NATIVE` gate: the APK never ran the shortcut.
- SEC-001: browser credential kept in memory only; fragment removed via `replaceState`.
- SEC-006: browser `request()` fails closed.
- SEC-009: CSP restricts scripts in entry HTML.
- URL fragments are not sent in HTTP requests or `Referer`.

None of these prevented the import itself or the prewarm request.

## Remediation performed

Replaced the import block in `static/standalone.js` with an unread strip:

```js
// SEC-016: credentials are accepted only through explicit Settings entry, never from a
// link. A legacy `#key=` fragment is discarded unread and removed from the address bar.
if (!NATIVE && new URLSearchParams(location.hash.replace(/^#/, "")).has("key")) {
  history.replaceState(null, "", location.pathname + location.search);
}
```

Copied the file byte-for-byte to the three shipped mirrors; all four SHA-256 values start `669055FD54866FD4`. Each mirror's pre-task hash equaled the pre-task static hash, so no mirror-only change was overwritten. Updated the SEC-001 Playwright flow test to expect `configured: false` and an empty hash. Added `tests/sec016_fragment_credential_test.cjs`.

## Compatibility considerations

- **Removed:** the undocumented browser convenience of importing an OpenAI key by link (no README, privacy, SOURCES or eval documentation referenced it). Users enter the key in Settings, which is unchanged and still session-only.
- **Unaffected:** `#report-N` deep links (not stripped); stored data; native credential storage and migration; Android behavior.
- **Not retroactive:** already-open pages keep existing state; links previously saved elsewhere are not revoked.
- **Deployment:** the hosted GitHub Pages copy changes only when `docs/` is published. No commit or push was made.

## Files changed

1. `static/standalone.js`: fragment import removed; unread strip added (−4 lines net).
2. `docs/standalone.js`, `android-app/www/standalone.js`, `android-app/android/app/src/main/assets/public/standalone.js`: byte-identical mirror copies of item 1.
3. `tests/sec001_credential_flow_test.cjs`: fragment scenario now asserts no import (SEC-016 comment).
4. `tests/sec016_fragment_credential_test.cjs` (new): regression and contract test.
5. `PROJECT_MASTER/SECURITY_REMEDIATION_SEC016.md` (new): this report.
6. `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md` and `PROJECT_MASTER/CHANGELOG.md`: SEC-016 status.

Evidence outside the repository is in `work/sec016/`: `pre_hashes.tsv`, `standalone.pre-sec016.js` (baseline), `sec016_test.out.txt`, `sec004_baseline_replay.py`.

## Files intentionally not changed

- All `index.html` mirrors: the only hash reader is the `#report-N` deep link.
- `docs/privacy.html`, `README.md`: no fragment import was documented.
- Native Kotlin/Java, including `NativeCredentialPlugin`, and the Android manifest/resources.
- `tests/sec001_credential_storage_test.py`: no fragment assertions; still passes.
- `tests/sec004_download_contract_test.py` and `tests/sec002_media_cleanup_contract_test.py`: pre-existing failures, left out of scope.
- Dependencies/lockfiles, workflows, tools, data.
- All SEC-001–015 remediation code except the four `standalone.js` lines above and the SEC-001 flow-test expectation.

## Tests/checks performed

- Focused: `node tests/sec016_fragment_credential_test.cjs`, which extracts the production `CredentialBroker` block into `node:vm` with stubbed `location`, `history`, `localStorage`, `fetch` and `Capacitor`.
- Mutation: the same test with `SEC016_SOURCE=work/sec016/standalone.pre-sec016.js`.
- Syntax: `node --check` on `static/standalone.js`, the SEC-016 test and the updated SEC-001 flow test.
- Regression: SEC-001 storage; SEC-004 download contract and bounded-download; SEC-005 contract and stream; SEC-006 contract and request; SEC-009 CSP; SEC-010 image budget; SEC-014; SEC-015; Android release optimization; SEC-002 contract (unmodified, plus in-memory lock-digest replay).
- Baseline replay of the SEC-004 download contract against the pre-SEC-016 source.
- Before/after SHA-256 scope comparison after removing test-generated `__pycache__`.

## Exact test results

| Check | Result |
| --- | --- |
| SEC-016 fragment credential test | **PASS (18 checks)**. `#key=` is stripped exactly once, not configured, not persisted, no prewarm fetch, and `request` rejects as missing key. Explicit Settings key configures, and prewarm uses only the typed value. Mixed `#lang=en&key=` and empty `#key=` are stripped and not imported. `#report-12` and a plain load leave history untouched. Native mode ignores the fragment with no migration. The four mirrors are identical, and no fragment credential reader remains in the engine or either `index.html`. |
| Mutation against pre-SEC-016 source | **FAILS as expected**: `fragment key does not configure OpenAI` (`true !== false`). |
| `node --check` (3 files) | exit 0 each. |
| `sec001_credential_storage_test.py` | PASS. |
| `sec005_inference_contract_test.py` / `sec005_inference_stream_test.cjs` | PASS (15) / PASS (24). |
| `sec006_ai_budget_contract_test.py` / `sec006_ai_request_test.cjs` | PASS (21) / PASS (38). |
| `sec009_csp_contract_test.py` | OK. |
| `sec004_bounded_download_test.cjs` | PASS (23). |
| `sec010_image_budget_test.cjs` | PASS (17). |
| `sec014_fileprovider_contract_test.py` / `sec015_source_digest_contract_test.py` | PASS (25) / PASS (17). |
| `android_release_optimization_test.py` | PASS (includes exact web mirror verification). |
| `sec002_media_cleanup_contract_test.py` | FAIL, **pre-existing**: stale `android-app/package-lock.json` digest (SEC-008), recorded in SEC-014. In-memory replay with only that digest substituted: PASS (68 checks, including web writer function hashes and mirrors). |
| `sec004_download_contract_test.py` | FAIL, **pre-existing and out of scope**: `only remaining arrayBuffer reads are local cache or bounded image header` expects 2 `.arrayBuffer()` occurrences. Pre-SEC-016 baseline and current both have 6; only line numbers shifted by −4. A baseline replay fails at the same assertion after the same 25 passing checks. |
| Scope comparison | Only the files listed under “Files changed” differ or are new. HEAD unchanged. |

## Runtime/device/build limitations

- `tests/sec001_credential_flow_test.cjs` (Playwright/Chrome) was updated but **not executed**: `require.resolve('playwright')` fails in this environment.
- No real browser, GitHub Pages deployment, Android WebView, Gradle build, APK inspection, ADB or device run. The `node:vm` harness executes the production broker code but not the full page lifecycle.
- The SEC-009 CSP `connect-src` content was not re-audited; the CSP contract test passes.

## Preservation of SEC-001–015

- SEC-001 guarantees are intact: memory-only browser key, legacy plaintext removal, native Keystore migration, no plaintext bridge return. Its storage test passes; its flow test was updated only for the removed import.
- SEC-006's browser inference refusal is unchanged (contract and request tests pass).
- SEC-002, SEC-004, SEC-005, SEC-009, SEC-010, SEC-014 and SEC-015 regressions pass, apart from the two documented pre-existing failures.
- SEC-001–015 statuses in `SECURITY_STATUS.md` are unchanged apart from the new SEC-016 row and link.

## Remaining risks, if any

- Credential-bearing links already shared or recorded elsewhere cannot be recalled.
- A browser session still holds a typed key in page memory (SEC-001 design) and can still send it to `/v1/models` during prewarm after explicit entry.
- **Out of scope, recorded only:** `tests/sec004_download_contract_test.py` arrayBuffer-count contract is stale against the current source (6 occurrences vs. expected 2), and the SEC-002 contract lock digest is stale. Both need separate review.
- The audit/verification material defines no SEC-017; remaining recorded items after SEC-016 are NEW-001, NEW-002 and the open parts of partially resolved findings.

## Roadmap / next finding

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
SEC-015 = RESOLVED — SOURCE/STATIC (rebuild requires a new reviewed SHA-256 pin)
SEC-016 = RESOLVED — SOURCE/STATIC (browser runtime flow test not executed)
NEW-001 = NOT STARTED (release blocker)
NEW-002 = NOT STARTED (release blocker)
Overall gate = FAIL
```

Next finding as directed: **SEC-017**. No SEC-017 is defined in `outputs/SECURITY_AUDIT.md`, `SECURITY_VERIFICATION.md` or `SECURITY_INVENTORY.json` (0 occurrences). It must be identified or defined before any work.

## CODEX HANDOFF

- **Exact task:** SEC-016 only.
- **Final SEC-016 status:** RESOLVED — SOURCE/STATIC (Playwright browser flow test updated but not executed).
- **What was investigated:**
  - Audit and verification SEC-016 sections; SEC-001/006/009 context.
  - `static/standalone.js` `CredentialBroker` (import, `readyPromise`, `request`, `storeCredentials`, `prewarm`, `clear`), engine `prewarm` and `matchTender`.
  - `static/index.html` hash consumers and credential gates; `docs/index.html` script loading (published web build); `README.md` hosted URLs.
  - `tests/sec001_credential_flow_test.cjs`, `tests/sec001_credential_storage_test.py` and the other contract tests that read `standalone.js`.
  - Existing `node:vm` harness style; Playwright availability.
- **Exact vulnerability/data/control flow:** non-native page load → `location.hash` `key` → `legacyOpenAiKey` → `browserOpenAiKey`/`openAiConfigured` → UI treats AI as configured, and `prewarm` sends `Bearer <link value>` to `api.openai.com/v1/models`. Inference was already refused by SEC-006. The native gate excluded the APK.
- **Attacker influence and impact:** anyone who gets a user to open a crafted or credential-bearing link to the browser build controls the session credential state and triggers an authenticated request with that value. The victim's existing key is not disclosed; there is no paid inference and no native impact. LOW.
- **Remediation:** the fragment value is never read. A `key` fragment is only stripped via `replaceState`; Settings entry is the sole browser credential source.
- **Exact files changed:** `static/standalone.js`; `docs/standalone.js`; `android-app/www/standalone.js`; `android-app/android/app/src/main/assets/public/standalone.js`; `tests/sec001_credential_flow_test.cjs`; `tests/sec016_fragment_credential_test.cjs` (new); `PROJECT_MASTER/SECURITY_REMEDIATION_SEC016.md` (new); `PROJECT_MASTER/SECURITY_STATUS.md`; `PROJECT_MASTER/PROJECT_STATUS.md`; `PROJECT_MASTER/CHANGELOG.md`.
- **Exact files not changed:** all `index.html` mirrors; `docs/privacy.html`; `README.md`; native sources/manifest/resources; `tests/sec001_credential_storage_test.py`; `tests/sec004_download_contract_test.py`; `tests/sec002_media_cleanup_contract_test.py`; dependencies, lockfiles, workflows, tools, data.
- **Tests and results:**
  - SEC-016: PASS (18); mutation vs. baseline FAILS as expected; `node --check` ×3 OK.
  - SEC-001 storage PASS; SEC-005 PASS (15/24); SEC-006 PASS (21/38); SEC-009 OK; SEC-004 bounded PASS (23); SEC-010 PASS (17); SEC-014 PASS (25); SEC-015 PASS (17); release PASS; SEC-002 replay PASS (68).
  - Pre-existing failures, unchanged by SEC-016: SEC-002 unmodified (lock digest) and SEC-004 download contract (arrayBuffer count 6 vs. 2; baseline fails identically).
- **Limitations:** Playwright flow test not run (module unavailable); no real browser, Pages deployment, Gradle, APK or device verification.
- **SEC-001 through SEC-016 status preservation:** SEC-001–015 unchanged (see roadmap); SEC-016 newly RESOLVED — SOURCE/STATIC. NEW-001/NEW-002 not started.
- **Exact next task:** **SEC-017**.
- **Instructions for the next agent:**
  - Handle SEC-017 independently, in a new scoped session.
  - First read `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md`, `PROJECT_MASTER/CHANGELOG.md` and this report.
  - Confirm SEC-017's definition, because the recorded audit material contains no SEC-017; do not invent one. If it is undefined, ask the owner whether to proceed with NEW-001/NEW-002 or another scoped item.
  - Do not re-add the fragment import; keep `tests/sec016_fragment_credential_test.cjs` passing.
  - Do not fix the recorded SEC-004/SEC-002 contract drifts under SEC-017 unless explicitly scoped.
  - Do not commit/push.
- **Current HEAD/state:** HEAD `f282454e8fb79a529894598b0af9a3d7008fd84c`, unchanged. Working tree = pre-existing uncommitted SEC-001–015 changes plus the SEC-016 files above. Git requires `-c safe.directory=...`.
- **Commit/push:** none occurred.
