# SEC-009 privileged WebView CSP remediation

Date: 2026-09-14. Finding: **SEC-009**. Severity: **LOW**.

**STATUS: RESOLVED — source/browser enforcement.** The missing-policy condition is fixed and focused tests pass. No exploitable application XSS was established or claimed. No Android build, physical-device/ADB test or replacement APK/AAB verification was performed.

## Original condition and actual WebView surface

The authoritative original audit and prior verification confirmed missing CSP in `static/index.html` and a previously shipped APK copy, inline application scripts/styles, and no reproduced exploitable HTML injection. SEC-009 was defense in depth, with no independent production blocker.

Actual `android-app/capacitor.config.json` sets `webDir: www` and `server.androidScheme: https`, with no remote server URL or `allowNavigation`. Capacitor serves `android-app/android/app/src/main/assets/public` at local `https://localhost`. The entry HTML matches canonical `static/index.html`, Android source mirror `android-app/www/index.html`, and hosted `docs/index.html`. All four entry copies were identical before and remain identical after this change.

Same-origin web content can invoke privileged Capacitor/Cordova capabilities. CSP supplies an additional browser restriction if a separate markup injection occurs; it does not authenticate bridge calls or replace escaping/native validation.

Inspection established these requirements:

- Local `vendor/leaflet.js`, local `standalone.js`, and one large inline application script. Actual HTML contains no inline event handlers. Application sources contain no `eval`, `new Function`, dynamic script-element creation, WebSocket or EventSource requirement.
- Local Leaflet CSS/images, one inline stylesheet, numerous static/template-generated style attributes, and direct style-property updates for visibility, camera preview geometry, zoom and reports. Fonts are system fonts.
- Same-origin APIs/assets and converted camera files; OpenAI model validation at `api.openai.com`; Nominatim reverse geocoding; Karnataka KGIS queries; Telangana point-query hosts in existing trusted pack metadata; manifests/packs under the pinned GitHub Pages project path.
- Local/blob/data photos and footage, live camera `srcObject`, and OSM tiles. Native file/content URI conversion maps to the local HTTP(S) origin, so raw `file:`/`content:` CSP allowances are unnecessary.
- Official portals, maps, WhatsApp/mail and policy links are handoffs/navigation, not application connections or embedded frames. There is no app frame/object/worker or HTML form-submission requirement.

## Exact policy and directive rationale

One enforced meta is inserted after UTF-8 charset and before the first application resource in each entry. The actual content attribute is one line; this is its exact directive content formatted for readability:

```text
default-src 'none';
script-src 'self' 'sha256-5lxY2XJ/MANLZ07inQSx1Ps56OIN40T7URgVxgtRj/g=';
script-src-attr 'none';
style-src 'self' 'unsafe-inline';
style-src-elem 'self' 'sha256-alMgFglTmLTaMAlOyaPUSj9LtMAekaj5T3g0uYO4LOg=';
style-src-attr 'unsafe-inline';
img-src 'self' blob: data: https://tile.openstreetmap.org;
media-src 'self' blob: data:;
font-src 'self';
connect-src 'self' blob: data: https://api.openai.com https://nominatim.openstreetmap.org https://kgis.ksrsac.in https://tgrac.telangana.gov.in https://coding-parrot.github.io/pothole-reporter/;
object-src 'none';
frame-src 'none';
child-src 'none';
worker-src 'none';
base-uri 'none';
form-action 'none'
```

| Directive | Purpose |
| --- | --- |
| `default-src` | Deny resources unless explicitly permitted. |
| `script-src`, `script-src-attr` | Local scripts and the exact existing inline block; block event-handler injection. No script `unsafe-inline`, `unsafe-eval`, remote host, blob or data execution allowance. |
| `style-src-elem` | On CSP3 browsers, allow local CSS and only the exact existing inline stylesheet. |
| `style-src-attr`, fallback `style-src` | Preserve existing inline/template styles and compatibility with older WebViews lacking split style directives. This verified CSS exception does not allow inline scripts. |
| `img-src` | Local/blob/data images and only the actual OSM tile host. |
| `media-src`, `font-src` | Local/blob/data media and local font resources; system fonts remain usable. |
| `connect-src` | Identified HTTPS services/project path, local APIs/converted camera files/native GET proxy, and blob/data fetches needed for legacy-photo reads/export. No unrestricted wildcard, generic HTTP(S) scheme or WebSocket allowance. |
| `object-src`, `frame-src`, `child-src`, `worker-src` | Deny unused plugins, embedded frames and workers. Native camera views are not HTML frames. |
| `base-uri`, `form-action` | Refuse injected base changes and form submissions; existing links/native handoffs remain usable. |

Hashes cover the original script/style bytes after browser HTML newline normalization. Hashing avoids rewriting the large application block and disturbing previous fixes. No fixed nonce was used. Tests recompute both hashes; future inline changes must deliberately update the hashes in all copies, not add script `unsafe-inline`.

Dynamic inline style values cannot be covered by a finite hash list without an unrelated UI/template rewrite. [Mozilla's style directive documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr) describes the distinction between attributes, style elements and direct property updates. Modern Chrome enforcement was tested. Older WebViews use the intentional `style-src` fallback, which also admits inline style blocks; their script restrictions remain in place.

## Bridge compatibility

Installed Capacitor Android `8.5.0` source was inspected without modification. `Bridge.java` prefers `WebViewCompat.addDocumentStartJavaScript` on the allowed origin. `JSInjector.java` falls back to inserting its trusted runtime immediately after literal `<head>`, before the CSP meta is parsed. That native bootstrap requires no script `unsafe-inline` allowance. The literal head and existing ordering were preserved. Later application content is subject to CSP.

Native `evaluateJavascript` callbacks are not JavaScript `eval`; no unsafe-eval exception was added. Local Cordova and same-origin `/_capacitor_file_/`, `/_capacitor_content_/` and `/_capacitor_http_interceptor_` resources remain permitted.

Chrome source models exercised actual installed `native-bridge.js` in both bootstrap positions, mocked Android bridge callbacks, the existing empty Cordova placeholder and local converted-file/GET-proxy requests. Later injected inline scripts were blocked. These models do not execute Java WebView APIs or real Android plugins.

## Exact files changed

Repository root: `C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter`.

1. `static/index.html` — one CSP meta line only.
2. `android-app/www/index.html` — matching entry change.
3. `docs/index.html` — matching entry change to preserve the existing asset mirror.
4. `android-app/android/app/src/main/assets/public/index.html` — matching change to the existing packaged-source entry only; no sync/build/generated-input repair.
5. `tests/sec009_csp_contract_test.py` — six standard-library static contracts.
6. `tests/sec009_csp_browser_test.cjs` — focused Playwright enforcement/bridge models using the existing `tests/serve_app.py` harness.
7. `SECURITY_REMEDIATION_SEC009.md` — this report.
8. `PROJECT_MASTER/SECURITY_STATUS.md` — SEC-009 row and report link only.
9. `PROJECT_MASTER/PROJECT_STATUS.md` — SEC-009 completion and relevant queued-work wording.

`standalone.js`, native security fixes, dependencies/lockfiles and unrelated tests were unchanged. Inline script/style and all non-CSP entry text were preserved. Existing modified/untracked files outside the intended entry/status files retained their baseline SHA-256 hashes.

## Focused verification

Used existing bundled Python `3.12.14`, Node `v24.18.0`, Node Playwright and installed Chrome `152.0.7977.84`. No package or browser install/upgrade occurred. Python Playwright and the expected managed Chromium binary were absent; available Node Playwright launched installed Chrome instead.

```powershell
Set-Location -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-09\bro\work\pothole-reporter'
$PythonExe = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PythonExe .\tests\sec009_csp_contract_test.py
# Separate session, stopped after testing:
& $PythonExe .\tests\serve_app.py --host 127.0.0.1 --port 8889
$env:NODE_PATH = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$env:POTHOLE_TEST_APP = 'http://127.0.0.1:8889/'
node .\tests\sec009_csp_browser_test.cjs
node --check .\tests\sec009_csp_browser_test.cjs
git diff --check -- static/index.html android-app/www/index.html docs/index.html
```

| Verification | Result |
| --- | --- |
| Static CSP/HTML tests | Six passed: early enforced meta and identical mirrors; current hashes; restrictive scripts/defaults/objects/frames/base/forms; explicit connections including trusted-pack query hosts; resources/styles/bridge compatibility; no dynamic-code/remote-script requirement. |
| Android source browser scenario `/` | PASS: startup/Settings UI, local assets/Leaflet, hash-approved app execution/styles, all required mocked fetches, legacy data/blob photos, OSM images, fake-camera live preview and actual recorded blob-video decoding. No legitimate-resource CSP violation. |
| Canonical browser scenario `/web-app/` | Same positive checks passed. |
| Negative checks on both surfaces | PASS: unapproved inline/event/eval/remote-script execution, unexpected images/fetch/WebSocket, frames/objects/base/forms and inline style elements blocked; expected violation directives observed and no unexpected HTTP host request intercepted. |
| Native document-start source model | PASS: installed runtime, mocked bridge round trip, local Cordova/file/content/GET proxy access, later inline injection blocked. |
| Native HTML fallback source model | Same checks passed using the pinned injector placement before CSP. |
| Node syntax, targeted whitespace and preservation checks | Passed. |

Tests explicitly use `bypassCSP: false`, with no disabled-web-security flag. All external responses are mocked; no OpenAI/provider, routing or pack-host service call occurred. Chrome's fake-device/fake-UI flags supply camera media, never a real camera. Inline/eval assertions use DOM insertions and an allowed local script probe, not privileged automation execution as proof of CSP blocking.

Test-only issues were corrected without weakening the policy: setup needed to skip an intentionally blocked child frame with inaccessible storage; a synthetic canvas recording produced an undecodable header-only clip without CSP violations. The final media test uses the fake camera and proves recorded blob video decodes. Final logs and baseline backups are under `C:\Users\user\Documents\Codex\2026-09-14\files-pasted-by-the-user-you\work\sec009`. A deliverable report copy is in that task's `outputs` directory.

## Residual risk and limitations

CSP trusts local scripts and the exact hash-approved application block. It cannot protect against control of those scripts, native code or installed assets. Inline CSS compatibility remains an intentional allowance; old-WebView style fallback is broader than modern split directives. Hash maintenance is required when inline blocks change.

CSP constrains browser resource loads, not existing native privileges. CapacitorHttp and same-origin native GET proxy requests can reach destinations beyond browser-visible `connect-src`; same-origin script trust also includes that proxy origin. This scoped policy does not claim that already-executing malicious privileged JavaScript cannot send data or invoke plugins. No native allowlist/architecture redesign was attempted. Existing escaping and native controls remain necessary.

No Android/Gradle build, ADB, emulator, physical-device/plugin test, real Java bootstrap/external-navigation test, or replacement APK/AAB inspection was performed. Older supported WebView behavior remains unverified. Existing release binaries were not changed and must not be assumed to contain the policy. The tests establish source/browser compatibility, not deployment certification.

**No independent production blocker remains specifically for SEC-009**, consistent with the authoritative LOW-severity baseline. Its source missing-policy condition is fixed; device/release verification remains recommended before broad distribution. Unrelated recorded production blockers remain unchanged.

**SEC-001–SEC-008 were not reworked. SEC-010 and later findings were not started.** No unrelated dependency, architecture, native behavior or functionality changes. No commit or push.
