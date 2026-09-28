# Security audit — Pothole Reporter

**Audit date:** 11 September 2026 (Asia/Tashkent)  
**Repository:** [coding-parrot/pothole-reporter](https://github.com/coding-parrot/pothole-reporter)  
**Audited commit:** `f282454e8fb79a529894598b0af9a3d7008fd84c`  
**Commit date:** 31 August 2026; version declared by source: 1.38.0, Android versionCode 67.  
**Purpose:** defensive, read-only assessment before adapting the project for Uzbekistan.  
**Decision:** **FAIL for immediate production approval.** Suitable for further isolated evaluation, subject to the remediation and verification gate below. This is not a finding of intentional malicious code.

## 1. Executive Summary

The application is a local Android/Capacitor application with an optional browser implementation. It does not currently operate a project backend, user-account system, public report API, or shared AI billing credential. The apparent `/api/...` paths in its JavaScript are dispatched to local application functions. Those facts significantly reduce its remote attack surface.

The most concrete privacy defect is incomplete deletion: manual camera originals can remain in an app-specific external Pictures directory after the user invokes **Delete all app data**. The email plugin creates a further temporary attachment location that is not explicitly covered by the verified wipe. The OpenAI key and optional dashcam credentials are readable from WebView storage. Remote pack buffering, paid-inference budget controls, and the write-privileged catalog automation also need attention before production use.

Published vulnerability records match the locked xmldom build dependency. Additional uuid and Kotlin version matches have more limited or unestablished reachability: the Kotlin fix concerns KAPT, whereas this project configures KSP. These are not evidence of an Android remote-code-execution vulnerability.

No confirmed live secret, reachable remote code execution, remotely exploitable XSS, unauthenticated shared-backend abuse path, or Android exported-component privilege bypass was established. This is a scoped negative result, not a guarantee that none exists. No Critical or High finding is asserted without a demonstrated applicable attack path.

Useful existing defenses include disabled backups and device-transfer exclusions; private Drive service/receiver; immutable notification PendingIntents; explicit permission/consent flows; HTML escaping and photo-source validation; constrained filesystem paths; verified pack hashes and schemas; AI structured output and deterministic acceptance gates; finite native retries and memory quotas; and user-reviewed complaint handoffs.

### Method, evidence and limitations

- Inventoried all **847 tracked files**, including the hidden workflow, build files, native source, web mirrors, tests, documentation, public data and tooling. Scanned tracked text and decompressed current `.gz` files; manually traced security-sensitive paths. Binary artwork was inventoried, not comprehensively OCR-scanned or reverse engineered.
- Searched **143 commits reachable from fetched refs**, including 137 on HEAD's ancestry. Examined **2,537 unique Git blobs / 199,122,003 bytes** using credential-pattern scanning and manually triaged candidate categories. Private/unfetched forks, deleted unreachable Git objects, private CI logs and secret settings were unavailable. The history scan was primarily text-based; it is not exhaustive entropy or steganography analysis.
- Read exact locked Capacitor/plugin package sources after verifying npm tarball integrity against the lockfile. These were downloaded into an audit directory, never installed or executed. The full transitive Java/Maven graph was **not resolved by running Gradle**.
- Queried current OSV records for all identified npm package/version identities, Leaflet and statically determined Maven declarations. Checked npm latest metadata for 102 distinct names. Absence of an advisory is not proof of security or maintenance. Python dependencies are not locked, so an exact installed version/CVE result cannot be supplied.
- Downloaded the public **v1.38.0 APK** as inert data; checked its SHA-256 against GitHub release metadata; enumerated its 496 ZIP entries; decoded its binary manifest; read Capacitor configuration and plugin registrations; scanned relevant assets/DEX strings for key patterns. Its main HTML and JavaScript match canonical Git blobs exactly. Windows checkout CRLF differences were normalized by comparing against `git show`, not treated as artifact tampering.
- APK SHA-256: `a028ae4dbf179ac792f73a101b5669bfcc447a3b41e2f78ae6ede120b548f06b`; size: 3,170,606 bytes. Matching GitHub's digest is an integrity check, **not independent signer validation**. No Android SDK/apksigner or device was available; cryptographic APK signature verification, full DEX decompilation, merged dependency resolution, and device exploitation tests remain outstanding. The AAB was not inspected.
- Did not run repository scripts, tests, dependency installers, Gradle, the APK, paid API requests or complaint submissions. Did not edit repository files, upgrade dependencies, rotate credentials, commit, push, or change GitHub settings. Only audit working files and these deliverables were created.

Source references below use one-based lines at the audited commit. `DriveModePlugin.kt`, `Native*.kt`, and other short native names resolve under `android-app/android/app/src/main/java/dev/aiengg/potholereporter/`. Dependency source references identify the exact npm package/version and its package-internal path; they are not tracked repository files. The companion **SECURITY_INVENTORY.json** contains every file, dependency declaration, extracted URL-origin inventory, redacted secret candidates and audit receipts.

## 2. Repository Architecture

| Area | Files | Purpose and security boundary |
|---|---:|---|
| `android-app/` | 195 | Capacitor package/lock/config; Android Gradle project; Kotlin Drive/camera/RTSP/inference/storage bridge; Java MainActivity; tests; packaged web mirror |
| `static/` | 21 | Primary HTML/JavaScript engine, vendored Leaflet, local manifests; no server process |
| `docs/` | 291 | GitHub Pages web mirror, privacy/source documentation and immutable downloadable public packs |
| `data/` | 122 | Public GIS/contact/procurement snapshots, compressed source receipts, boundaries and registries |
| `tools/` | 46 | Data ingestion/build/verification, APK/release and artwork/screenshot tooling |
| `eval/` | 22 | Offline and paid model evaluation; ignored private corpora referenced by manifests |
| `tests/` | 133 | Browser/static/contract tests and a loopback development server |
| `.github/` | 1 | Scheduled/manual catalog-refresh workflow |
| Other | 16 | README, license, repository instructions, requirements, artwork utility, store assets, architecture metadata |

**Languages:** Kotlin, Java, JavaScript, Python, Bash and Windows batch; HTML/CSS, XML, JSON and Groovy Gradle configuration. No TypeScript application source or SQL server was found. SQL appears in Room schemas/migrations and development analysis.

**Build/package systems:** npm lockfile and Capacitor CLI; Gradle wrapper 8.14.3 with a distribution SHA-256; Android Gradle Plugin 8.13.0; Kotlin/KSP; Google Maven/Maven Central; pip requirements with lower bounds only. Android minSdk 24, compile/targetSdk 36, Java 21. Leaflet 1.9.4 is vendored.

**Flow:** camera or dashcam → prepared full-frame JPEG evidence → OpenAI classification/repair check → deterministic validation → local report/track/media stores → local boundary/contract routing with selected external GIS queries → user-reviewed external email, portal, WhatsApp or share operation. A public map/community backend is not present.

**Storage:** WebView localStorage/settings; IndexedDB `potholes`; Room `native_potholes.db`; app-private reports, footage and repair files; SharedPreferences terminal summaries; plugin-created camera/external-cache files; optional user-exported debug/evidence files. “Synced to web” means native-to-WebView synchronization, not cloud upload.

Historical refs contain removed server/AWS/YOLO material. They were included in secret scanning, but their architecture is not attributed to the current Android app.

## 3. Attack Surface

| Entry/trust boundary | Attacker-controlled input | Present controls | Residual concern |
|---|---|---|---|
| Manual camera/import | Media bytes, metadata, capture timing | Explicit user action; re-encoding; source provenance | Initial decode budget; retained originals |
| Dashcam | RTSP endpoint and stream | Scheme/host/length validation; Wi-Fi binding; bounded reconnect and frame sizing | Unencrypted transport; hostile decoder input |
| OpenAI responses | Model JSON/SSE and descriptions | HTTPS, schemas, deterministic verdict checks, native output cap | Prompt manipulation, response-resource limits, costs |
| GIS/geocoder | Address strings, geometry/query response | Fixed/pinned endpoints, coordinate/boundary checks | Provider privacy, malformed/oversized response |
| Pack hosting | Public JSON bytes | Exact size/hash/schema and source checks | Full buffering before validation |
| Web UI/native bridge | UI values and same-origin scripts | Local origin, no remote-navigation whitelist, escaping, native permission/path checks | Any future XSS gains powerful plugins |
| Android inter-app | Launcher, granted content URIs, selected camera/email apps | Private components, scoped grants, immutable PendingIntents | Untrusted selected apps, broad provider roots |
| CI/build | Packages, public pages, contributor changes, cached metadata | Pinned Actions, reviewed main, catalog path gate, release checks | Mutable pip installation with a write token |

## 4. Secrets Findings

**No confirmed real embedded credential was identified.** Do not interpret test strings, public certificates, public API session headers or an environment variable name as leaked production secrets.

| Candidate/category | Location | Classification / APK exposure |
|---|---|---|
| User OpenAI key | `static/index.html:5767`; reader `static/standalone.js:17` | Real only when supplied at runtime; SEC-001. Extractable from a compromised user's storage/memory, not a fresh APK |
| Dashcam credentials in URI | `static/index.html:5773`; native URL validator | Runtime only; stored client-side; SEC-001/003 |
| Release signing values | `android-app/android/app/build.gradle:21-24` | Environment/ignored property references; not literal signing secrets |
| Keystore example | `android-app/android/keystore.properties.example:5-8` | Explicit replace-me/path examples; no keystore tracked |
| Public upload certificate | `store-assets/upload-certificate.pem:1` | Parsed as public X.509 certificate, not a private key. SHA-256 fingerprint `29:6F:94:7F:84:12:AC:A3:92:5C:F5:16:9C:19:5A:E0:97:C6:85:6D:57:51:EE:DD:78:9D:D4:BF:BA:7B:AC:8C` |
| OpenAI-like `sk-` matches | Sikkim IDs in web code and public routing JSON | Public authority identifier, not a credential; included in APK as data |
| Fake OpenAI/AWS/RTSP values | Tests and historical server/infra tests | Test/example credentials; ordinary test sources not packaged as runtime web assets |
| Bihar/Chhattisgarh authorization and CSRF fields | `tools/pull-bihar-road-tenders.py:145-168`; `pull-chhattisgarh-chips-road-tenders.py:235-305` | Runtime public-portal tokens; literal `X-Requested-With` is not a secret |
| Evaluation credentials | `eval/run_eval.py:63-71`, `eval/rad_dataset.py:165` | `OPENAI_API_KEY`, Kaggle credentials loaded from environment/config; not committed values |

The history scan produced 87 candidate occurrences across unique blobs. The inventory preserves each candidate's blob, path, line and type with **no credential values**. Same content shared by multiple paths is scanned once; a blob's representative path is not every historical path. No live API validation was attempted. `.gitignore` excludes `.env`, keystores, APK/AAB outputs, logs, private media and evaluation results; ignored files can still be force-added, so continuous secret scanning is recommended.

## 5. API Security Findings

### Current runtime API inventory

| Service / endpoint | Authentication and transmitted data | Validation / timeout / retry | Risk |
|---|---|---|---|
| `https://api.openai.com/v1/responses` | Bearer BYOK key; selected images/prompts; eligible Karnataka address/shortlist | Native strict output schema and verdict parser; 30s connect/read/write timeouts, bounded retries/backoff, native output token limits. JS 30s watchdog and streaming fallback; no JS output-token cap | SEC-001,005,006; provider sees images, not just pothole coordinates |
| `https://api.openai.com/v1/models?limit=1` | Same Bearer key, no photo; warm-up | At most one warm-up per 60s; errors ignored; no explicit timeout on this fetch | LOW hardening note: bound warm-up and cancellation; no generated-token request |
| `https://nominatim.openstreetmap.org/reverse` | No app secret; exact `lat/lon`, English address request, connection metadata | Local queue ≥1100ms spacing, 250-entry cache keyed on rounded coordinates; 12s watchdog; failure returns null | Precise coordinates leave device; local throttle is not a fleet-wide quota |
| `https://kgis.ksrsac.in/kgismaps/rest/services/Boundaries/Admin_Dynamic_New/MapServer/1/query` | No app secret; coordinate geometry | Fixed endpoint; jurisdiction checks and failure handling | Government GIS learns queried location |
| Same KGIS base: `State_Basemap/State_Basemap_Dynamic/MapServer/289/query` and `Boundaries/GP_Boundary/MapServer/0/query` | No app secret; coordinate geometry | Fixed query routes; geometry/coverage rules | Same privacy and provider-availability boundary |
| `https://tgrac.telangana.gov.in/arcgis/rest/services/TCUR_Folder/TCUR_Telangana_Core_Urban_Region_V2/MapServer/22/query` | No app secret; accuracy envelope | Validated pack endpoint; whole-envelope within test; bounded fetch path | Exact-area disclosure; provider response affects route selection |
| TGRAC `Hydra_Folder/Administrative_Layer/MapServer/1/query` | No app secret; accuracy envelope | Cantonment intersection exclusion; ambiguous/unavailable exact routing does not authorize a specific authority | Same boundary |
| `https://coding-parrot.github.io/pothole-reporter/packs/v1/...` | No auth; state/approximate tile in URL; requests omit credentials/referrer | Pinned size/hash/schema, local cache quotas/expiry, AbortController timer | SEC-004; GitHub/CDN learns state/tile and IP |
| `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | No auth; viewed map tile coordinates | Image rendering, tile error/fallback handling | Map-view area inference; no GPS track uploaded as a single payload |

The native transport uses a fixed production endpoint. Its injectable endpoint/client constructor is for internal tests, not an exposed UI setting. OpenAI credentials were not observed attached to geocoder, GIS or pack requests. No trust-all certificate handler was found in application code. The HTTP Capacitor bridge is enabled and can perform cross-origin requests: that capability makes script integrity important, not a public server-side SSRF endpoint.

GIS response validation is separate from data provenance: a currently trusted GIS operator can return incorrect information. Exact timeouts/behavior of final platform/plugin networking must be checked on-device; JavaScript AbortController should not be assumed to cancel every native request implementation solely from source inspection.

**External handoffs:** `mailto:`, `tel:`, `https://wa.me/...`, Google Maps links, Play Store/app-launch package names and multiple official complaint portals. These are user-driven external actions, not authenticated backend APIs. The public registries contain many additional contact/source URLs; the companion inventory groups 323 extracted URL origins, with representative file/line references. That inventory includes documentation, tests and tool-only sources and is not a claim that the APK contacts 323 services.

**Tool/evaluation services:** OpenAI evaluation calls; Kaggle dataset download with environment credentials; Geofabrik PBF download; OSM/Nominatim boundary requests; public Indian procurement, PMGSY, highway and GIS sites; npm/PyPI/Maven/browser-download infrastructure; GitHub API/CLI for catalog PRs. Evaluation request budgets and dry-run gates exist in several paths. None was executed during this audit.

## 6. Android Security Findings

Source manifest and decoded release manifest were both inspected. The release additionally contains normal library components that are absent from the source manifest.

| Permission | Purpose / assessment |
|---|---|
| INTERNET | OpenAI/GIS/geocoder/packs/maps and dashcam networking |
| CAMERA | Manual and phone-camera Drive capture; dashcam start separates camera permission requirements |
| ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION | Capture location and Drive tracking; a user may grant approximate location |
| FOREGROUND_SERVICE plus CAMERA, CONNECTED_DEVICE, LOCATION subtypes | Persistent Drive operation and RTSP connection while other apps are visible |
| ACCESS_NETWORK_STATE, CHANGE_NETWORK_STATE | Select/monitor network, route RTSP to Wi-Fi |
| POST_NOTIFICATIONS | Visible service controls/status |
| WAKE_LOCK | Keep active Drive processing running |
| App-specific DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION | Signature-level support-library permission in merged APK |

No broad storage, MANAGE_EXTERNAL_STORAGE, RECORD_AUDIO, READ_CONTACTS, CALL_PHONE or ACCESS_BACKGROUND_LOCATION permission appears in the inspected APK. Foreground-service location can nevertheless continue while the UI is backgrounded; absence of the separate background-location permission does not mean no background collection occurs.

**Externally triggerable components:** MainActivity is exported for MAIN/LAUNCHER. AndroidX ProfileInstallReceiver is exported but requires `android.permission.DUMP`; that is not an ordinary third-party-app entry. DriveForegroundService and NotificationActionReceiver are explicitly private. FileProvider, camera provider, Room invalidation service and Startup provider are private. Camera helper activities with no intent filters and no exported attribute default to non-exported. No BROWSABLE app link or custom externally registered deep-link scheme was found. The `#report-...` UI fragment is an in-document route, not evidence of an exported Android deep link.

Notification actions carry session identity and use FLAG_IMMUTABLE; stale notifications are not intended to operate a new session. Canonical-path checks protect native footage/private media operations. No other-app path to start hidden Drive capture was established. SEC-002/014 describe storage/grant concerns. Validate these conclusions on an actual supported Android device and confirm signature-protected components reject an ordinary app UID.

## 7. WebView/Capacitor Findings

The app serves bundled content using the local HTTPS scheme. Configuration has no `server.url` remote host or `allowNavigation` exception. Exact Capacitor 8.5.0 source constructs allowed bridge origins from the local host/config. Modern WebMessageListener handling restricts calls to the main frame; older/failing implementations fall back to addJavascriptInterface. Third-party navigation is normally launched externally. No current remote iframe or remote script dependency was identified in the application document; Leaflet is vendored.

Registered capabilities include Camera, Filesystem, Geolocation, Share, AppLauncher, App, EmailComposer and custom DriveMode, plus Capacitor built-ins such as HTTP/cookies. They are powerful within the app UID. File/content URL conversion is used for legitimate local image reads. Native custom bridge methods validate key paths and budget several media operations. They are not an independent authentication boundary against malicious same-origin JavaScript.

SEC-001 and SEC-009 address credential/script defense. The reviewed UI uses safePhotoSrc, escaping and DOM `.value` assignments for complaint text; no unescaped remote-data-to-executable sink was proven. Arbitrary URL handling by generic bridge plugins is an architectural capability, not a confirmed exploitable remote navigation vulnerability in this configuration. On-device tests should cover legacy WebView bridge fallback, file/content URI mapping and external navigation with a hostile local page.

## 8. Network Security Findings

Application internet endpoints observed in current runtime flows use HTTPS. No custom trust-all TLS verifier or disabled hostname verification was found. The release manifest does not opt into general cleartext HTTP; its target SDK defaults provide a further barrier. RTSP is a separate non-HTTPS transport and remains exposed as described in SEC-003.

Certificate pinning is not implemented in application code; that alone is not classified as a vulnerability. Any pinning decision needs certificate-rotation/recovery planning. Ordinary network attackers still must defeat TLS/device trust to alter OpenAI, GIS or pack traffic. Explicit redirect restrictions for sensitive provider requests would be useful; no validated cross-host Authorization leak was demonstrated, and different browser/native transports must be tested separately.

Known outbound disclosures are photographs to OpenAI; exact coordinates to Nominatim and selected GIS services; state/tile requests to GitHub Pages; map extent to OSM tile servers; and explicit complaint/evidence sharing to selected applications/recipients. IP addresses and normal request metadata are visible to those providers. “No project backend” does not mean “no data leaves the device.”

## 9. Location Privacy Findings

The app records selected-fix coordinates and a detailed Drive track including time, speed, accuracy and heading. Native track collection has a point cap, and Drive has an active-time limit. Track/report histories can still reveal repeated routes, probable home/work locations and historical movements to an attacker with appropriate device access. They are not bundled in the APK.

Native tracks are copied into local web storage for history/dashboard features. No analytics or project-operated trip upload was identified. Exact reverse-geocoding queries are sent even when the cache key is rounded: rounding the cache key is not anonymization of the outgoing query. Accepted Drive reports trigger geocoding; manual capture can start geocoding speculatively before the final classification.

Current notices describe provider sharing and background collection. That disclosure is useful but does not remove the need to minimize retention. SEC-013 records the design risk. For Uzbekistan, omit full-route collection unless it is justified, separate private travel records from public defect coordinates, and do not show reporter home/work histories on a community map.

## 10. Media Security Findings

Native Drive evidence is stored under app-private directories. Optional phone-camera recording is off by default, silent, and subject to footage/free-space limits (documented 4 GB and 500 MB reserve). Dashcam mode decodes video and saves selected evidence rather than storing/uploading the complete stream. Native bridge and stored-image policies constrain image sizes and ownership.

Browser preparation redraws the image on a canvas and outputs JPEG; native bitmap recompression similarly creates derived evidence. These derived copies do not copy original EXIF through that code path. **Original camera-plugin URI files are different:** the plugin explicitly copies EXIF, potentially including GPS metadata if the source contains it. There was no device-level metadata sample to prove which tags a given camera writes. SEC-002 covers the leftover originals; SEC-010 covers initial full-resolution decode.

Frames may contain faces, number plates, homes and businesses. The current pipeline uploads unblurred full frames; notices disclose this. No face/plate redaction was found. User-selected email/share recipients receive the actual evidence copy; that transfer may create additional retained files outside application control. Local deletion cannot retract delivered messages or provider copies. Predictable internal names are not an access bypass by themselves, but unique attachment identities and narrow URI grants are preferable.

No malicious-media RCE was demonstrated. Android/WebView/Media3 decoder behavior, EXIF stripping, cancellation cleanup and media-provider trust must be tested on real devices. File deletion is logical removal, not a guarantee of forensic erasure on flash storage.

## 11. Local Storage Findings

| Store | Contents | Protection / limits |
|---|---|---|
| localStorage | API key, name, model/detail, language, RTSP address, consent/settings | Web origin + Android UID; no added encryption; SEC-001 |
| IndexedDB `potholes` | Reports/photos, Drive metadata, footage and verified pack cache | Local origin isolation; transaction logic, pack quotas/expiry; accessible to compromised same-origin code |
| Room `native_potholes.db` | Reports, sightings, sessions/tracks, repair states, keyframe/footage metadata | App-private SQLite, typed Room queries; no SQLCipher/extra DB encryption found |
| Internal files | Reports, Drive media, repair targets | App-private; canonical containment; cleanup/quotas |
| SharedPreferences | Terminal Drive summaries plus framework state | Private mode; no app credential stored here in reviewed custom code |
| Camera external Pictures / email external cache | Original photos/EXIF, composed attachments | OS-version-dependent app-specific storage controls; not fully covered by wipe |
| Documents/debug exports/share destinations | Selected evidence and files | Explicit export; destination policy applies |

Backups and device transfer are explicitly excluded. Release debugging is disabled. Extraction generally requires user-authorized export/debugging, compromised same-origin context, appropriate legacy storage access, device privilege or physical/unlocked access. It is incorrect to equate “no additional app encryption” with world-readable data on every Android phone. No Firebase database, server-side session store, JWT secret or account-password database exists in the current application.

## 12. Input Validation Findings

- **SQL:** reviewed Room DAOs use parameter binding and fixed SQL; migration execSQL statements are fixed schema changes. No user-string SQL concatenation into a runtime query was found.
- **Commands:** production Android/JS code does not run OS shell commands. Python tooling uses subprocess argument lists for Git/media operations; shell scripts were read, not executed. Repository-controlled build commands remain executable trust boundaries.
- **Paths:** native private media and footage use canonical containment and session validation. The test HTTP server resolves paths under explicit roots and defaults to 127.0.0.1. No current path-traversal exploit was established there. Generic Filesystem/email bridge methods are wider than custom Drive methods; a compromised script can abuse permissions already held by the app.
- **HTML/JS:** report description/address/authority display paths generally escape text; form content is assigned through `.value`; photo sources are filtered. No demonstrated stored/DOM XSS. SEC-009 is defense in depth, not an XSS claim.
- **URLs:** official links are reconstructed/revalidated against route data. `https://` prefix checks alone would be too weak for arbitrary new domains, but the existing registry/hash checks narrow provenance. Number characters are filtered for `tel:`; WhatsApp and mailto query text is encoded.
- **Coordinates:** finite/range checks, GPS accuracy/age/heading gates and boundary containment prevent some invalid routing. They do not authenticate a user's physical presence or defeat a compromised device/GPS spoofing.
- **Serialization/media/network:** JSON/structured fields are parsed and often explicitly bounded. SEC-004/005/010 identify the boundaries where allocation precedes limits. No unsafe Python pickle/YAML load or application-level Java ObjectInputStream path was found; see the separate conditional Kotlin tooling advisory.

## 13. AI Security Findings

Inputs include user camera images, ordered Drive frames, repair before/after images, and—in the Karnataka matching path—reverse-geocoded address and public tender shortlist text. Text in images or address/record fields can attempt to alter the model's decision. Prompts are not a security boundary; strict schemas constrain shape, not truthfulness.

Current mitigations are meaningful: closed verdict fields, deterministic requirements for cavity/edge/surface/temporal consistency, no model tools/function execution, no eval of model output, limited shortlist candidates, lexical-leader checks, and separately verified contractor/ownership conditions. The model cannot by itself send an email or open an arbitrary returned URL through the inspected flow. Tender matching currently returns `contractor = null` unless later independent responsibility requirements can be satisfied; an outdated nearby comment about naming contractors is not the final behavior.

Residual prompt manipulation may create false positives/negatives, suppress real defects or distort descriptions. No prompt-injection-to-code-execution chain was identified. A future community/backend system must treat all model verdicts as untrusted observations, not repair authorization or payment approval. Costs and response handling are SEC-005/006. Requests set `store:false`; that is not a promise that providers retain no security/abuse data, and the project's privacy notice correctly makes that distinction.

## 14. Email Security Findings

Direct-email routes are revalidated against current coordinate-bound authority data before opening the composer. The app provides subject/body/attachment parameters through Android intents; it does not construct SMTP headers or send mail itself. The exact email plugin defaults `isHtml` to false. The browser fallback uses encoded mailto recipient/query parameters. No conventional CRLF SMTP-header injection or HTML-email execution path was established.

The user reviews and sends in a separate app. An app that registers a mailto handler is not necessarily a trustworthy email provider; the chooser is a user trust decision. A compromised official registry/new release can still misroute complaints, so recipient provenance requires review. SEC-002/014 cover attachment caches, reusable names and grants. The email plugin's generic base64 filename handling is not canonicalized, but the application's current call supplies a fixed issue-derived filename; no external attacker-controlled filename path was found. Do not promote this to a standalone remote path traversal without establishing that input path.

## 15. Dependency / Supply Chain Findings

Exact versions and statuses are in the dependency appendix and companion inventory. All locked npm resolved URLs use the npm registry and contain integrity fields. Selected package archives were independently checked against those fields. Integrity pins identify bytes; they do not prove the publisher or bytes are trustworthy.

**Applicable package-version matches:** xmldom 0.9.11 (eleven advisories, SEC-008); uuid 7.0.3 (SEC-011); kotlin-gradle-plugin declarations 2.1.0/2.2.20 (SEC-012). The latter two require reachability qualifications. No matching OSV advisory was returned for the other queried identities on the audit date. That statement excludes unresolved transitives, unknown installed Python versions, platform WebView/OS vulnerabilities and advisory-database omissions.

Python requirements are `playwright>=1.40`, `python-dotenv>=1.0.0`, `Pillow>=10.0.0`; the workflow separately installs `playwright>=1.40,<2`. These are permitted ranges, not installed versions. There is no reproducible Python lock with hashes. npm's `latest` comparison in the appendix is informational, not a recommended upgrade command; semver-major changes require compatibility review. A package may intentionally remain on a maintained older branch. uuid's deprecation is explicit; no other package is declared abandoned merely because its version is old.

Maven declarations include AndroidX, CameraX, Media3, Play Services Location, Room, Lifecycle, coroutines, OkHttp, Cordova, Ionic camera/filesystem/geolocation libraries, Gson, test libraries, Kotlin, KSP and build plugins. Their full effective transitive versions cannot be established safely from this repository alone without Gradle resolution. In particular the app pins Kotlin 2.1.0 while some plugin build scripts default `kotlin_version` to 2.2.20; no actual resolved conflict is claimed. Repository verification metadata/dependency locks were not found beyond the Gradle distribution checksum and npm lockfile.

Recommended later approach: create a clean isolated build without secrets, resolve/save an SBOM and dependency verification metadata, recheck advisories, then reproduce the release using reviewed dependencies. Do not run third-party build logic on a signing workstation with broad credentials. No dependency was changed during this audit.

## 16. GitHub Actions Findings

Only the catalog-refresh workflow is tracked. It runs on schedule or manual dispatch, checks out main, pins checkout/setup-python to full commit SHAs, sets a 180-minute timeout, tests/parses public sources, enforces catalog-only changed paths and opens a PR on a unique automation branch. It does not automatically merge main or run untrusted pull-request code via a PR trigger.

SEC-007 identifies the actual supply-chain exposure: writable checkout credentials coexist with unpinned package/browser installation and external-page processing. The later path gate does not contain an already-compromised process. No raw PR-title/body expression is inserted into a shell command in the reviewed workflow; run ID/attempt are used for branch naming.

GitHub branch protection, required reviews, Pages deployment settings, environment protection, organization policy, Actions token settings, private secrets and release logs were not visible. A malicious PR being opened alone is not shown to obtain secrets. A malicious change merged to main, an upstream dependency compromise, or a compromised maintainer is a separate path. No tracked release-signing workflow proves that signing keys are handled in CI; do not infer their location.

## 17. Build / APK Security Findings

Release configuration disables debugging, enables R8/resource shrinking, and refuses release artifacts without signing configuration. ProGuard retains Capacitor annotations/callbacks required by reflection. Native obfuscation is not secret protection: bundled HTML/JS, manifests, prompts, URLs, public certificate and permission/component information are extractable.

The debug script deliberately builds assembleDebug; it is not appropriate for production. The separate Play release script checks identity, manifest policy, source/packaged asset consistency and signatures using Android tooling. These checks were read but not executed. No hardcoded production signing private key was found. Build environment values are not automatically included as runtime credentials by the reviewed configuration.

The downloaded release's source assets match the audited commit and its manifest shows no debuggable=true, disabled backup and the expected private components. The release also includes a DUMP-protected AndroidX profile installer receiver and a separate camera provider; these must be considered in testing rather than relying only on the hand-written manifest. No API-key/private-key pattern was confirmed in scanned release assets/DEX strings; Sikkim identifiers were false positives.

**Outstanding release checks:** independent APK signer verification against a trusted release key; AAB/Play signing identity; full DEX/dependency audit; reproducible build/provenance; actual permission/URI-grant behavior on devices; and update continuity for a new Uzbekistan application ID. A GitHub-hosted checksum cannot alone prove the intended author signed the binary.

## 18. Cryptography Findings

Runtime pack and geometry checks use SHA-256 with locally pinned expected values; this protects against a changed remote pack while the installed app/manifests remain trusted. Some error strings call the manifest “signed,” but the inspected mechanism is a pinned hash catalog, not an independently verified digital signature on every downloaded manifest. A compromised web origin can replace web code and hashes together; signed APK updates have a different trust boundary.

The Gradle distribution has a pinned SHA-256. Native UUID.randomUUID is used for correlation/session/staging identities, not authentication tokens. No custom password hashing, hardcoded symmetric encryption key or custom cipher was found. App-specific credential/database encryption is absent as discussed in SEC-001/013. Public X.509 certificates and hashes are not secrets. SEC-015 covers MD5 for one offline source file. Standard platform Keystore and reviewed authenticated-encryption libraries are preferable to custom cryptography.

## 19. Authentication / Authorization Findings

**Current application:** no project user accounts, login sessions, roles, account passwords, project backend authorization or shared server credentials. OpenAI authorizes requests using the user's provider key; Android permissions and application UID protect local operations. The external complaint provider manages its own accounts and final submission.

Local report IDs and native/web API-like function names are not exposed authenticated server resources. A person controlling their own device can alter reports, GPS, counters or verdicts; client-side guards cannot establish authenticity for a future shared service. This is not an IDOR in a nonexistent current backend.

**Future backend boundaries:** authenticate users/devices; authorize report read/write/delete, attachment access, moderation, contractor assignments, repair-status updates, exports and administrator actions independently. Check object ownership/role at every request. Keep human/organization identity separate from public display identity, and record accountable changes without recording raw credentials or full private routes.

## 20. Abuse / Cost Risks

| Abuse | Current exposure | Production control needed |
|---|---|---|
| API quota/cost exhaustion | BYOK, repeatable sessions/replays; SEC-006 | Atomic server quotas/reservations if shared funding; per-user/day caps, output caps, bounded retries, global stop |
| Bots/report spam | No public ingest backend today; user can generate local drafts | Rate limits, account/device reputation, moderation queue, duplicate handling |
| Fake potholes / manipulated images | AI/deterministic checks can be fooled | Store evidence provenance; independent review; never treat model verdict as fact |
| Fake GPS / replayed reports | Client timing/accuracy checks do not prove location | Server consistency checks, replay-resistant uploads, timestamp/location plausibility, optional attestation as one signal |
| Duplicate evidence | Local geospatial/event dedupe | Server-side idempotency and privacy-preserving image/event dedupe; do not merge distinct nearby defects blindly |
| Malicious/oversized media | Local decode/network limits uneven | Strict byte/pixel/duration limits before allocation, isolated transcoding, safe metadata handling |
| False repair completion | Local before/after model checks | Privileged reviewed state transition and independent evidence; no automatic financial consequence |
| Complaint phishing | Curated routes but external recipient trust remains | Verified authority registry, change review and clear user-visible recipient |

Client/device throttles help battery and accidental misuse but cannot protect a shared API budget against a modified client. Provider spending alerts should not be assumed to be hard enforcement. Public release must use a service-side budget mechanism where the project funds requests.

## 21. Privacy Threat Model

Likelihood is qualitative and conditional on the stated access, not a statistical forecast.

| Actor | Attack path | Assets / impact | Likelihood | Mitigation |
|---|---|---|---|---|
| Malicious user | Fabricates image/GPS/report on their own phone | False civic data or spam if later accepted centrally; own BYOK costs today | High capability, low current shared impact | Treat client as untrusted; future moderation/provenance/rate limits |
| Malicious same-device app | Registers camera/email handler, receives selected grants; older storage permissions | Selected evidence, residual camera media | Medium with user interaction/legacy access | Narrow grants, cleanup, current OS, trusted destination choice |
| Network attacker | Intercepts RTSP Wi-Fi or defeats TLS trust | Video, credentials conditionally, false evidence | Medium RTSP; low ordinary HTTPS | Protected transport, no trust bypass, endpoint restriction |
| Abusive API user | Repeats sessions or uses stolen provider key | Victim/provider budget | Medium after access | SEC-001/006; revoke compromised credentials; enforce service quotas |
| Compromised dependency | Executes in build/catalog job or runs as native plugin | Repository token, future signing identity, reports/photos | Low–medium, high potential impact | Isolated builds, pinned reviewed inputs, minimal permissions, SBOM |
| Malicious contributor | Merged source/data change replaces code or routing contacts | User photos/keys, authority trust, release integrity | Requires review/merge access | Independent reviews, branch protection, signed provenance, separate signing |
| Compromised backend/provider | Present provider sees sent photos/locations; future backend leaks uploads | Precise location, images, identity, community data | Conditional | Data minimization, retention, encryption/access controls, provider assessment |
| Attacker with downloaded APK | Extracts code/prompts/URLs/public data and crafts a modified client | Intellectual/public configuration; future API abuse attempts | High reverse-engineering capability | Never embed server secrets; authenticate/authorize server requests |
| Physical-device attacker | Reads unlocked app or obtains privileged data access | Home/work inference, entire saved routes/photos, BYOK | Medium depending on device state | Device lock, minimal retention, key protection, verified deletion |
| Compromised web origin/extension | Reads browser localStorage/IndexedDB and invokes web functionality | Browser user's key/history/media | Conditional | Dedicated origin, CSP, no URL keys; native isolation for sensitive operations |
| Compromised catalog host | Sends oversized response or attempts data replacement | Availability; route integrity if app release also compromised | Low–medium | Streaming size caps plus pinned hashes/schemas; protect update channel |

Current identity information is mainly an optional sender name and data included by the user in external complaints. There is no central community database or backend credential to steal in this revision. Those assets become new responsibilities only if the Uzbekistan adaptation introduces them.

## 22. Complete Vulnerability Table

The table includes confirmed weaknesses, conditional dependency matches and informational architectural risks. Severity reflects this repository's actual exposure, not just an upstream advisory's headline. Detailed records follow, with attack prerequisites and production-blocking decisions.

| ID | Severity | Title | Production decision |
| --- | --- | --- | --- |
| SEC-001 | MEDIUM | Long-lived credentials are readable from WebView storage | Yes for public production with long-lived API credentials; remove the integration or redesign storage/use. |
| SEC-002 | MEDIUM | Delete all app data misses plugin-created camera photos and email attachments | Yes. Verify that all app-created sensitive media is removed before reporting successful deletion. |
| SEC-003 | MEDIUM | Dashcam video uses unencrypted RTSP transport | Conditional: required if dashcam mode is included outside a controlled trusted-network deployment. |
| SEC-004 | MEDIUM | Remote pack size limits are checked after complete buffering | Yes for production relying on remote packs; negative tests must show rejection before excessive allocation. |
| SEC-005 | LOW | SSE limits do not cover the entire incoming transport | No independent blocker in the current trust model; include in production transport hardening. |
| SEC-006 | MEDIUM | AI spending lacks an app-wide budget and JavaScript output-token ceiling | Yes for a public paid-AI deployment; no blocker if paid inference is completely removed. |
| SEC-007 | MEDIUM | Catalog-fetch job installs mutable dependencies while holding write credentials | Yes if this automation is retained in the production fork. |
| SEC-008 | MEDIUM | Locked xmldom has published parser/serializer vulnerabilities | Yes for approving the production build toolchain, or provide a documented and reviewed non-reachability exception. |
| SEC-009 | LOW | Privileged web document has no explicit Content Security Policy | No independent blocker; recommended before broad production distribution. |
| SEC-010 | LOW | Manual images are decoded before an explicit input size/pixel budget | No standalone blocker for a controlled pilot; required hardening before public media ingestion. |
| SEC-011 | INFO | Deprecated uuid has an advisory match without a demonstrated affected call path | No by itself; document reachability and replacement plan. |
| SEC-012 | INFO | Kotlin build-cache advisory matches declared versions, but KAPT is not configured | No if KAPT remains absent and cache trust is controlled; re-evaluate when the toolchain changes. |
| SEC-013 | INFO | Detailed location histories rely on device protection and manual retention choices | Architecture decision required for production; not a standalone remotely exploitable vulnerability. |
| SEC-014 | INFO | FileProvider grants cover broad app-specific cache and external-file roots | No independent blocker; address alongside SEC-002. |
| SEC-015 | LOW | Highway source provenance uses a legacy MD5 checksum | No independent runtime blocker; modernize before rebuilding production data. |
| SEC-016 | LOW | Browser key-import shortcut accepts credentials through URL fragments | Conditional: remove before publishing the browser app with real credentials. |

### SEC-001 — Long-lived credentials are readable from WebView storage

**Severity:** MEDIUM  
**File and line:** [static/index.html:5767](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/index.html#L5767)  
**Vulnerable component:** Settings and JavaScript credential access  
**Evidence status:** Confirmed design weakness; theft requires an additional access path

**Technical explanation:** The OpenAI key is persisted under openai_key and read directly by JavaScript. RTSP URLs, including userinfo, are stored the same way at line 5773. No app-level credential encryption or native-only request broker separates these secrets from the web document. Android sandboxing and disabled backups mitigate ordinary cross-app reads.

**Attack scenario:** An attacker with same-origin script execution, a compromised browser extension in the web version, authorized debugging access, or access to an unlocked/rooted app data directory reads credentials. Merely downloading the APK does not reveal users' keys.

**Impact:** Use of the victim's API account and possible disclosure of dashcam credentials. This is not a demonstrated remote XSS exploit or an embedded project-wide key.

**Evidence:** static/standalone.js:17 reads localStorage; static/index.html:5767 and :5773 write secrets; docs/privacy.html:208 discloses the lack of separate encryption.

**Recommended remediation:** For retained BYOK, place keys in Keystore-backed authenticated encryption and keep key use behind narrow native operations; do not return plaintext to the WebView. For a funded public service, use authenticated server-side inference with quotas and no shared provider key in clients. If AI is removed, remove key entry and storage in that later phase.

**Blocks production:** Yes for public production with long-lived API credentials; remove the integration or redesign storage/use.

### SEC-002 — Delete all app data misses plugin-created camera photos and email attachments

**Severity:** MEDIUM  
**File and line:** [static/index.html:5847](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/index.html#L5847)  
**Vulnerable component:** Media lifecycle and privacy deletion  
**Evidence status:** Confirmed by source tracing; device reproduction outstanding

**Technical explanation:** The wipe calls clearNativeData, removes the Documents debug folder and internal share cache, then clears browser stores. Native managedRoots lists only reports, footage, repair_targets, and the internal share cache. Camera getPhoto is called with resultType URI. The exact locked camera plugin creates files in externalFilesDir/Pictures, preserves the URI output, and copies EXIF. These files are not in the wipe list. The email plugin creates externalCacheDir/email_composer files; its cleanup runs at plugin load, not as a verified part of the wipe.

**Attack scenario:** A user photographs a sensitive location and invokes Delete all app data. Camera originals can remain after success, including possible original metadata. A physical/rooted-device attacker, or an app with relevant storage access on an older Android version, later obtains them. Email-cache lifetime adds another residual copy.

**Impact:** Images and possibly EXIF metadata outlive the user's deletion request. No claim is made that all modern Android apps can read these directories.

**Evidence:** static/index.html:4298-4305 and :5847-5868; DriveModePlugin.kt:1182-1186; @capacitor/camera 8.2.2 CameraUtils.java:24-26, LegacyCameraFlow.java:638-645 and :657-665; capacitor-email-composer 8.0.0 AssetUtil.java:25-38, :122-142 and EmailComposerPlugin.java:18-21.

**Recommended remediation:** Track plugin-produced URIs, delete originals after a successful private evidence copy, and explicitly clear and verify camera and email temporary directories during a wipe. Revoke relevant grants. Test successful, cancelled, interrupted, and failed captures and email composition. Do not promise secure flash overwriting; prefer bounded retention and encryption with key deletion.

**Blocks production:** Yes. Verify that all app-created sensitive media is removed before reporting successful deletion.

### SEC-003 — Dashcam video uses unencrypted RTSP transport

**Severity:** MEDIUM  
**File and line:** [android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeFrameSource.kt:65](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeFrameSource.kt#L65)  
**Vulnerable component:** Dashcam network source  
**Evidence status:** Confirmed transport property, disclosed by upstream

**Technical explanation:** The validator requires rtsp:// and accepts a host, port, path, query, and optional credentials. NativeRtspFrameSource uses RTSP/RTP over TCP and binds to the preferred Wi-Fi socket. TCP does not add encryption or authenticate the server. The configuration does not restrict endpoints to private addresses.

**Attack scenario:** An attacker controlling or observing the dashcam network intercepts video or alters the stream. Depending on camera authentication, credentials may also be exposed; Basic and Digest must not be treated as equally protective. A public RTSP address expands the exposed network path.

**Impact:** Road imagery disclosure, false visual evidence, connection disruption, and conditional credential exposure. Dashcam automatic authority/repair routing is currently withheld when timing is uncalibrated, reducing downstream impact.

**Evidence:** NativeFrameSource.kt:55-75; NativeRtspFrameSource.kt:180-189; docs/privacy.html:207-208.

**Recommended remediation:** Disable dashcam mode for the initial public release unless a protected transport is available. Otherwise use authenticated encrypted transport or a trusted encrypted tunnel, constrain accepted endpoints to the intended network, avoid reused passwords, and explicitly communicate residual risk.

**Blocks production:** Conditional: required if dashcam mode is included outside a controlled trusted-network deployment.

### SEC-004 — Remote pack size limits are checked after complete buffering

**Severity:** MEDIUM  
**File and line:** [static/standalone.js:2746](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/standalone.js#L2746)  
**Vulnerable component:** Downloaded routing and contract packs  
**Evidence status:** Confirmed resource-boundary weakness

**Technical explanation:** Resource manifests have strict expected byte counts and SHA-256 values, but fetchStatePack first calls response.arrayBuffer and only then validates size and hash. Equivalent patterns occur in contract, road-notice, road-agreement and highway downloads. A declared maximum does not cap bytes allocated while receiving or decompressing the response.

**Attack scenario:** A compromised pack host/CDN, or a network attacker who can defeat TLS trust, supplies a large or highly compressed body at an expected pack URL. The app allocates the body before rejecting its checksum.

**Impact:** Memory exhaustion, app termination, bandwidth consumption and loss of availability. The checks still prevent substituted pack content from being accepted; this is not a demonstrated recipient-replacement attack.

**Evidence:** static/standalone.js:2732-2747 and :2612-2623; analogous fetches near :2986, :3241, :3565 and :3837.

**Recommended remediation:** Enforce a cumulative decoded-byte ceiling while receiving, abort at expected length plus a small justified tolerance, and retain exact size/hash/schema checks. Bound native Capacitor HTTP buffering as well as browser streams. Set an overall deadline.

**Blocks production:** Yes for production relying on remote packs; negative tests must show rejection before excessive allocation.

### SEC-005 — SSE limits do not cover the entire incoming transport

**Severity:** LOW  
**File and line:** [android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceTransport.kt:162](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceTransport.kt#L162)  
**Vulnerable component:** AI streaming parsers  
**Evidence status:** Confirmed hardening gap; provider compromise or abnormal response required

**Technical explanation:** Native code caps accumulated output-text deltas at 64 KiB, but bufferedReader.readLine can allocate an oversized line before the JSON/delta checks. Non-text events are not subject to a cumulative byte budget, and the client has inactivity timeouts but no total call deadline. The JavaScript SSE parser also grows state.buf/state.text without a byte cap, and re-arms its timeout on every chunk.

**Attack scenario:** An abnormal or attacker-controlled provider response sends an oversized line or continues sending nonterminal chunks. TLS normally prevents an ordinary network attacker from injecting such a stream.

**Impact:** Memory pressure, prolonged inference slots and battery use. Existing cancellation, backoff and session limits reduce impact; unrestricted remote access is not established.

**Evidence:** NativeInferenceTransport.kt:160-181, :308-312; static/standalone.js:921-967.

**Recommended remediation:** Bound line length, total response bytes, number of events and total elapsed call time before allocation; stop on terminal completion and ensure cancellation releases every transport.

**Blocks production:** No independent blocker in the current trust model; include in production transport hardening.

### SEC-006 — AI spending lacks an app-wide budget and JavaScript output-token ceiling

**Severity:** MEDIUM  
**File and line:** [static/standalone.js:1040](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/standalone.js#L1040)  
**Vulnerable component:** BYOK detection, replay, repair and tender matching  
**Evidence status:** Confirmed cost-control gap; not a public unauthenticated API

**Technical explanation:** JavaScript detection request construction and tender matching omit max_output_tokens, unlike native detection (1536) and repair (768). Concurrency, per-session time limits, finite retries and provider rate responses constrain individual operations, but there is no persistent daily cost/call budget across photo, repeated Drive sessions, replay and repair. Provider-side account controls are external and were not inspected.

**Attack scenario:** A user repeatedly starts/replays sessions, leaves a costly model selected, or processes adversarial images that elicit long descriptions. Additional theft of a BYOK key also permits use outside all app controls.

**Impact:** Unexpected charges to the user's account. No shared project billing credential or public endpoint allowing an arbitrary third party to spend the maintainer's budget was found.

**Evidence:** static/standalone.js:1040-1044 and :6279-6283; NativeInferenceRequest.kt:79; NativeDetectionContract.kt:7; NativeRepairContract.kt:31; DriveSessionLimitPolicy.kt.

**Recommended remediation:** Add output limits to every AI path, persistent request/token budgets and explicit replay estimates; stop rather than endlessly resubmit paid work. For any shared backend, enforce atomic server-side reservations, per-user quotas, global spend shutdown and idempotency. If adopting no-AI detection, remove paid paths later.

**Blocks production:** Yes for a public paid-AI deployment; no blocker if paid inference is completely removed.

### SEC-007 — Catalog-fetch job installs mutable dependencies while holding write credentials

**Severity:** MEDIUM  
**File and line:** [.github/workflows/refresh-public-road-catalogs.yml:13](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/.github/workflows/refresh-public-road-catalogs.yml#L13)  
**Vulnerable component:** GitHub Actions supply chain  
**Evidence status:** Confirmed configuration exposure; no compromised package found

**Technical explanation:** The scheduled/manual job has contents:write and pull-requests:write, checks out main with persist-credentials:true, then installs playwright>=1.40,<2 and browser dependencies and processes external pages. The pinned GitHub actions and catalog-path checks are useful, but a malicious installed package or browser compromise executes before that path check and can use the job's write credentials directly.

**Attack scenario:** An upstream package release or dependency in the install/browser chain is compromised. Code running in the refresh job obtains the persisted Git credential and modifies a branch or PR, bypassing the normal generated-file check.

**Impact:** Repository or catalog tampering within token permissions. This workflow does not run pull_request or pull_request_target; a merely opened malicious PR is not shown to receive its token. Branch protections may reduce impact but were not available for inspection.

**Evidence:** Workflow permissions at :13-15; persist-credentials at :34; pip/browser install at :44-45; later path enforcement and git push do not sandbox earlier code.

**Recommended remediation:** Separate untrusted fetch/build into a read-only job with persist-credentials:false. Pin Python/browser inputs with hashes and reviewed updates. Publish validated data from a minimal write job using strict artifact provenance and path/schema checks. Protect main and release environments.

**Blocks production:** Yes if this automation is retained in the production fork.

### SEC-008 — Locked xmldom has published parser/serializer vulnerabilities

**Severity:** MEDIUM  
**File and line:** [android-app/package-lock.json:316](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/package-lock.json#L316)  
**Vulnerable component:** Capacitor CLI XML tooling  
**Evidence status:** Confirmed affected version; application exploitability not demonstrated

**Technical explanation:** The lockfile selects @xmldom/xmldom 0.9.11, pulled through plist. OSV returned eleven applicable advisories covering XML parsing/serialization integrity and resource exhaustion. The advisory appendix lists each ID. The version is a build-tool dependency, not the WebView DOM implementation; its presence does not establish an Android remote vulnerability.

**Attack scenario:** A developer processes untrusted plugin/project XML through the affected build-tool chain. Parser-level resource exhaustion is a plausible consequence if the relevant API receives that XML; serializer-specific attacks require additional call patterns not proven here.

**Impact:** Conditional build denial of service or XML output manipulation. No production service accepting attacker XML was found.

**Evidence:** package-lock.json:316-321 pins 0.9.11; :819 declares plist's xmldom dependency. Current upstream advisories identify 0.9.12 as the fixed 0.9 branch for these issues.

**Recommended remediation:** In the separate remediation phase update the compatible dependency chain/lock to at least 0.9.12 for these advisories, re-scan all advisories, and validate Capacitor sync/build behavior. Do not assume a forced arbitrary major upgrade is safe.

**Blocks production:** Yes for approving the production build toolchain, or provide a documented and reviewed non-reachability exception.

### SEC-009 — Privileged web document has no explicit Content Security Policy

**Severity:** LOW  
**File and line:** [static/index.html:1](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/index.html#L1)  
**Vulnerable component:** WebView defense in depth  
**Evidence status:** Confirmed missing defense; no reachable XSS demonstrated

**Technical explanation:** The application uses a large inline script and HTML template rendering without a CSP meta tag. A successful same-origin script injection could read localStorage and invoke privileged plugins. Many actual sinks use escapeHtml/escapeAttr and safePhotoSrc; the lack of CSP alone is not proof of XSS.

**Attack scenario:** A later change introduces an unescaped remote value into a template, or trusted web content is compromised. There is no CSP layer to restrict script execution or outgoing connections.

**Impact:** Increases consequences of a separate injection bug. Remote navigation is constrained by Capacitor's default origin rules.

**Evidence:** static/index.html document header and inline script; render paths near :2038 and :2122; capacitor.config.json has no remote server/allowNavigation entries.

**Recommended remediation:** After this audit, refactor inline execution as needed to deploy a restrictive CSP, prohibit frames/objects, constrain connect/img sources and keep HTML escaping. Test native bridge behavior on supported WebView versions, including the legacy bridge fallback.

**Blocks production:** No independent blocker; recommended before broad production distribution.

### SEC-010 — Manual images are decoded before an explicit input size/pixel budget

**Severity:** LOW  
**File and line:** [static/standalone.js:8466](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/standalone.js#L8466)  
**Vulnerable component:** Photo import and image preparation  
**Evidence status:** Confirmed input-hardening gap; user interaction required

**Technical explanation:** handleFile accepts a selected image without an explicit file-size ceiling. toDataUrl creates a full ImageBitmap before scaling it down to a maximum dimension. This can allocate the original decoded pixel area. Native stored/replayed evidence has additional budgets, but those do not protect this first decode.

**Attack scenario:** A user selects a very large image or a malicious camera/gallery provider returns a compact image with extreme dimensions. Decoding consumes memory before resizing.

**Impact:** App/browser crash or local resource exhaustion; no decoder code-execution exploit is asserted.

**Evidence:** static/index.html:1803-1836; static/standalone.js:8465-8477; static/index.html:4313-4322.

**Recommended remediation:** Enforce compressed-byte, image-format and decoded-pixel limits before full allocation; use bounded native decoders and request downsampled decode where available. Keep malformed-media tests isolated and resource-limited.

**Blocks production:** No standalone blocker for a controlled pilot; required hardening before public media ingestion.

### SEC-011 — Deprecated uuid has an advisory match without a demonstrated affected call path

**Severity:** INFO  
**File and line:** [android-app/package-lock.json:1116](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/package-lock.json#L1116)  
**Vulnerable component:** xcode build dependency  
**Evidence status:** Version match / non-reachability not fully proven

**Technical explanation:** uuid 7.0.3 is locked under the xcode tool dependency and is marked deprecated in the lockfile. GHSA-w5hq-g745-h8pq concerns v3/v5/v6 methods with caller-provided buffers/offsets. Native app IDs use Java UUID.randomUUID, not this npm implementation.

**Attack scenario:** A tooling consumer uses the affected API with an undersized supplied buffer. Such a call was not identified in this application's source.

**Impact:** Conditional malformed or partial UUID output in tooling; no app authorization bypass shown.

**Evidence:** package-lock.json:1116-1123 and :1165; advisory appendix.

**Recommended remediation:** Prefer a maintained parent dependency with a compatible fixed uuid. Advisory fixed lines start at 11.1.1, 12.0.1 and 13.0.1 respectively; do not force these major versions into xcode 3 without compatibility testing.

**Blocks production:** No by itself; document reachability and replacement plan.

### SEC-012 — Kotlin build-cache advisory matches declared versions, but KAPT is not configured

**Severity:** INFO  
**File and line:** [android-app/android/build.gradle:12](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/android/build.gradle#L12)  
**Vulnerable component:** Kotlin Gradle build tooling  
**Evidence status:** Version match; affected feature not observed

**Technical explanation:** OSV flags kotlin-gradle-plugin 2.1.0 and plugin-default 2.2.20 for CVE-2026-53914. The upstream patch restricts deserialization in KAPT incremental-cache metadata. This repository declares KSP for Room and no KAPT application or remote build cache configuration was found. Effective plugin resolution was not executed.

**Attack scenario:** A build using the affected KAPT feature consumes poisoned incremental metadata under a more privileged build identity. This path has not been established for the audited build.

**Impact:** Conditional build-time code execution in the advisory's threat model; not a confirmed app RCE.

**Evidence:** android-app/android/build.gradle:12; app/build.gradle:3 and Room ksp declaration; upstream fix bf51df665b458fda7c3eaf436c4d88dc119d7ec6.

**Recommended remediation:** Keep untrusted/shared build caches isolated. Confirm actual resolved plugins and KAPT absence. OSV names 2.4.20-Beta1 as the first fixed release; select a vendor-supported stable release containing the fix only after checking AGP/KSP/Capacitor compatibility, rather than blindly deploying a beta.

**Blocks production:** No if KAPT remains absent and cache trust is controlled; re-evaluate when the toolchain changes.

### SEC-013 — Detailed location histories rely on device protection and manual retention choices

**Severity:** INFO  
**File and line:** [android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeDriveLocationProvider.kt:263](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeDriveLocationProvider.kt#L263)  
**Vulnerable component:** Local privacy architecture  
**Evidence status:** Confirmed design characteristic, disclosed

**Technical explanation:** GPS tracks include time offsets, coordinates, accuracy, speed and heading; they are stored in Room/IndexedDB along with reports and media. No additional database encryption, biometric gate or automatic age-based purge of all movement history was found. Android device storage encryption and UID isolation still apply.

**Attack scenario:** A person with an unlocked device or a privileged compromise reads historical routes and identifies likely home/work endpoints and repeated journeys.

**Impact:** Sensitive movement inference. A normal APK downloader or unrelated sandboxed app cannot simply query these stores.

**Evidence:** NativeDriveLocationProvider.kt:263-271; DriveForegroundService.kt:2749-2756; PotholeDatabase.kt:174-179; static/standalone.js:7755; docs/privacy.html:119 and :193-199.

**Recommended remediation:** Minimize collected tracks, offer short retention and a route-history opt-out, protect sensitive views and encryption keys appropriately, and keep precise movement records out of public community data.

**Blocks production:** Architecture decision required for production; not a standalone remotely exploitable vulnerability.

### SEC-014 — FileProvider grants cover broad app-specific cache and external-file roots

**Severity:** INFO  
**File and line:** [android-app/android/app/src/main/res/xml/file_paths.xml:4](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/android-app/android/app/src/main/res/xml/file_paths.xml#L4)  
**Vulnerable component:** Android file sharing  
**Evidence status:** Hardening opportunity; provider is not exported

**Technical explanation:** external-files-path and cache-path use path='.'. The provider is exported=false and files still require URI grants, so this does not expose an unauthenticated directory listing. Broader roots increase the files that an accidental/malicious in-app share can grant. The email plugin reuses a deterministic pothole filename.

**Attack scenario:** A future incorrect bridge call grants an unintended file, or a recipient retains access to a reused attachment URI while that activity's grant remains alive. The latter requires on-device grant-lifetime verification.

**Impact:** Conditional unintended file disclosure; not confirmed arbitrary-file access by another app.

**Evidence:** file_paths.xml:3-7; AndroidManifest.xml:65-73; static/standalone.js:9494; email plugin AssetUtil.java:129-136.

**Recommended remediation:** Limit sharing to dedicated directories, use unique immutable attachment names, grant only read access for the selected operation and revoke expired grants. Keep all path canonicalization checks.

**Blocks production:** No independent blocker; address alongside SEC-002.

### SEC-015 — Highway source provenance uses a legacy MD5 checksum

**Severity:** LOW  
**File and line:** [tools/pull-national-highways.sh:7](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/tools/pull-national-highways.sh#L7)  
**Vulnerable component:** Offline data-build provenance  
**Evidence status:** Confirmed legacy integrity primitive

**Technical explanation:** The Geofabrik PBF download is verified against a pinned MD5 before parsing. Runtime packs use SHA-256, and transport uses HTTPS. MD5 is unsuitable for modern adversarial provenance, but ordinary collision attacks do not automatically replace an already-fixed file with the same pinned digest.

**Attack scenario:** A source-publication compromise or malicious preparation of colliding artifacts undermines the provenance check. A simple MITM cannot be claimed to bypass both TLS and the existing pinned MD5 without further capabilities.

**Impact:** Reduced confidence in build input identity; no practical replacement demonstrated.

**Evidence:** tools/pull-national-highways.sh:6-7 and :18-26.

**Recommended remediation:** Pin a reviewed SHA-256/SHA-512 digest and record source provenance; retain HTTPS and immutable source references.

**Blocks production:** No independent runtime blocker; modernize before rebuilding production data.

### SEC-016 — Browser key-import shortcut accepts credentials through URL fragments

**Severity:** LOW  
**File and line:** [static/standalone.js:9](https://github.com/coding-parrot/pothole-reporter/blob/f282454e8fb79a529894598b0af9a3d7008fd84c/static/standalone.js#L9)  
**Vulnerable component:** Browser-only development path  
**Evidence status:** Confirmed browser behavior; disabled in APK

**Technical explanation:** A #key= fragment silently overwrites the stored OpenAI key. replaceState removes it from the current URL, and fragments do not reach ordinary HTTP server logs, but the original URL may already exist in messages, clipboard, browser sync or extension observations.

**Attack scenario:** A developer distributes a bookmarked/shared URL containing a real key, or an attacker convinces a web user to replace their stored key via a crafted link.

**Impact:** Conditional credential disclosure or account/key confusion in the browser version. This does not leak the victim's existing key merely by visiting an attacker link.

**Evidence:** static/standalone.js:6-12 explicitly gates the shortcut with !NATIVE.

**Recommended remediation:** Remove or compile-gate the shortcut from production web builds; accept keys only through explicit settings entry and never put them in links.

**Blocks production:** Conditional: remove before publishing the browser app with real credentials.

## 23. Severity Ranking

| Severity | Count |
| --- | --- |
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 7 |
| LOW | 5 |
| INFO | 4 |

No Critical/High finding was established. Version-only advisory matches were not upgraded to remote compromise. A production gate can fail because of multiple Medium issues and incomplete release verification without alleging a Critical vulnerability.

Prioritize actual privacy deletion and credential handling, then enforce resource/cost limits and contain the build/automation trust boundary. Treat the conditional KAPT/uuid matches as explicit review items rather than silently ignoring or overstating them.

## 24. Recommended Fix Order

These are recommendations only; **none was implemented**.

1. **Close deletion/credential gaps:** SEC-002 and SEC-001. Include camera originals, email caches, grant lifetimes and failure-aware deletion tests. If the future product removes AI, explicitly remove all paid-key storage/use paths instead of leaving dormant credentials behind.
2. **Contain build and publishing:** SEC-007 and SEC-008. Separate write credentials from untrusted dependency/data processing; obtain a reviewed dependency graph; remediate xmldom or document verified non-reachability. Resolve SEC-011/012 applicability without blind major/beta upgrades.
3. **Bound network, media and spending:** SEC-004/005/006/010. Enforce limits before allocation and before paid work, including all JS/native/replay/repair paths.
4. **Choose dashcam policy:** SEC-003. Exclude the feature initially or establish a protected transport and verified supported camera configuration.
5. **Strengthen the web/storage boundary:** SEC-009/013/014/016. Dedicated web origin, restrictive policy, narrow native APIs/grants, minimal history and no credential-bearing URLs. Modernize SEC-015 before regenerating data.
6. **Verify a new signed build in a clean environment:** resolve dependencies, run relevant security regression tests, verify signer and source provenance, and test on supported Android versions. Tests must include untrusted intents, denied permissions, app/background lifecycle, large/malformed responses, hostile media, cancellation, and deletion after manual capture/email use.

## 25. Security Architecture Recommendations for the Future Uzbekistan Version

The existing client can be evaluated as a starting point; it is not already a national transport/road-maintenance platform. Replacing Indian authorities with Uzbek names does not establish data correctness, authorization or public-service integration.

- Start with the smallest data flow: manual/local detection and private evidence review. If adopting no-AI or on-device detection, explicitly disable/remove cloud inference, paid evaluation hooks from release workflows, BYOK UI/storage and any speculative cloud calls in the later development phase. On-device detection still requires media, GPS and supply-chain security.
- Use a reviewed Uzbekistan authority/road registry with source provenance and versioned updates. Separate complaint intake from actual road ownership and contractor obligation. Do not copy Indian grievance recipients, contractor assumptions or country checks into production.
- If reports become shared, build a narrow authenticated backend. Upload through scoped, short-lived authorizations; validate size/type/pixels before processing; store media privately; separate public defect coordinates from private journeys and reporter identity. Never trust a client-supplied role, repair status, AI verdict or GPS coordinate as authorization.
- Keep exact location/photo access restricted. Publish only the evidence needed for civic review, with a considered redaction process. Keep complete-frame detection evidence private when necessary; share derived redacted copies without silently changing the evidence's meaning.
- Keep an auditable moderation/repair workflow with role-specific transitions and human review of disputed reports. Payments, contractor attribution and official completion should require independently verified records, not model output alone.
- Choose retention and deletion rules before collecting public data. Include plugin files, databases, caches, logs, exports and provider-held copies. Have deletion tests that enumerate storage after use and distinguish app-owned copies from already-sent material.
- Operate with reproducible dependency inputs, isolated read-only build checks, protected release signing, reviewed data updates and a vulnerability intake process. Use existing platform cryptography and verified libraries.
- Confirm applicable Uzbekistan privacy/public-sector requirements with qualified local stakeholders before rollout. This technical report does not assert that the application complies with local law or has government authorization.

## Appendix A — Dependency inventory and advisory detail

### npm — exact lock entries

106 package/version entries (102 names), including nested duplicate versions. Package manager: npm. Purpose is inferred from dependency role; it is not a claim that every package is shipped in the APK. All non-plugin CLI transitives are assessed as build tooling. The companion inventory preserves each lock path and integrity metadata. Registry `latest` is an audit-date comparison, not a compatibility recommendation; a different version does not prove insecurity or abandonment. Deprecation is separately recorded. A zero-advisory result means no OSV match returned for that exact query, not proof of safety.

| Package | Locked | Registry latest | Purpose / relationship | Advisory result |
| --- | --- | --- | --- | --- |
| @capacitor/android | 8.5.0 | 8.5.1 | Native bridge / android; direct | No returned match |
| @capacitor/app | 8.1.1 | 8.1.1 | Native bridge / app; direct | No returned match |
| @capacitor/app-launcher | 8.0.1 | 8.0.1 | Native bridge / app-launcher; direct | No returned match |
| @capacitor/camera | 8.2.2 | 8.2.4 | Native bridge / camera; direct | No returned match |
| @capacitor/cli | 8.5.0 | 8.5.1 | Capacitor build/integration tooling; direct | No returned match |
| @capacitor/core | 8.5.0 | 8.5.1 | Native bridge / core; direct | No returned match |
| @capacitor/filesystem | 8.1.2 | 8.1.3 | Native bridge / filesystem; direct | No returned match |
| @capacitor/geolocation | 8.2.2 | 8.2.2 | Native bridge / geolocation; direct | No returned match |
| @capacitor/share | 8.0.1 | 8.0.1 | Native bridge / share; direct | No returned match |
| @capacitor/synapse | 1.0.4 | 1.0.4 | Capacitor build/integration tooling; transitive | No returned match |
| @ionic/cli-framework-output | 2.2.8 | 2.2.8 | CLI display/input formatting; transitive | No returned match |
| @ionic/utils-array | 2.1.6 | 2.1.6 | Supporting CLI/build utility (transitive); transitive | No returned match |
| @ionic/utils-fs | 3.1.7 | 3.1.7 | Build filesystem/path/archive utilities; transitive | No returned match |
| fs-extra | 9.1.0 | 11.4.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| @ionic/utils-object | 2.1.6 | 2.1.6 | Supporting CLI/build utility (transitive); transitive | No returned match |
| @ionic/utils-process | 2.1.12 | 2.1.12 | CLI process/device execution; transitive | No returned match |
| @ionic/utils-stream | 3.1.7 | 3.1.7 | Tooling stream/buffer utilities; transitive | No returned match |
| @ionic/utils-subprocess | 3.0.1 | 3.0.1 | CLI process/device execution; transitive | No returned match |
| @ionic/utils-terminal | 2.3.5 | 2.3.5 | CLI display/input formatting; transitive | No returned match |
| @isaacs/fs-minipass | 4.0.1 | 4.0.1 | Build filesystem/path/archive utilities; transitive | No returned match |
| @types/fs-extra | 8.1.5 | 11.0.4 | Build filesystem/path/archive utilities; transitive | No returned match |
| @types/node | 26.2.0 | 22.20.2 | Build-time type declarations; transitive | No returned match |
| @types/slice-ansi | 4.0.0 | 7.1.0 | CLI display/input formatting; transitive | No returned match |
| @xmldom/xmldom | 0.9.11 | 0.9.12 | Build metadata/XML/plist processing; transitive | SEC-008; 11 matches |
| ansi-regex | 5.0.1 | 6.3.0 | CLI display/input formatting; transitive | No returned match |
| ansi-styles | 4.3.0 | 7.0.0 | CLI display/input formatting; transitive | No returned match |
| astral-regex | 2.0.0 | 2.0.0 | CLI display/input formatting; transitive | No returned match |
| at-least-node | 1.0.0 | 1.0.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| balanced-match | 4.0.4 | 4.0.4 | Build filesystem/path/archive utilities; transitive | No returned match |
| base64-js | 1.5.1 | 1.5.1 | Tooling stream/buffer utilities; transitive | No returned match |
| big-integer | 1.6.52 | 1.6.52 | Supporting CLI/build utility (transitive); transitive | No returned match |
| bplist-creator | 0.1.0 | 0.3.0 | Build metadata/XML/plist processing; transitive | No returned match |
| bplist-parser | 0.3.2 | 0.5.0 | Build metadata/XML/plist processing; transitive | No returned match |
| brace-expansion | 5.0.9 | 5.0.9 | CLI display/input formatting; transitive | No returned match |
| buffer-crc32 | 0.2.13 | 1.0.0 | Tooling stream/buffer utilities; transitive | No returned match |
| capacitor-email-composer | 8.0.0 | 8.0.0 | Native email draft handoff; direct | No returned match |
| chownr | 3.0.0 | 3.0.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| color-convert | 2.0.1 | 3.1.3 | CLI display/input formatting; transitive | No returned match |
| color-name | 1.1.4 | 2.1.1 | CLI display/input formatting; transitive | No returned match |
| commander | 12.1.0 | 15.0.0 | CLI process/device execution; transitive | No returned match |
| cross-spawn | 7.0.6 | 7.0.6 | CLI process/device execution; transitive | No returned match |
| debug | 4.4.3 | 4.4.3 | Supporting CLI/build utility (transitive); transitive | No returned match |
| define-lazy-prop | 2.0.0 | 3.0.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| elementtree | 0.1.7 | 0.1.7 | Build metadata/XML/plist processing; transitive | No returned match |
| emoji-regex | 8.0.0 | 10.6.0 | CLI display/input formatting; transitive | No returned match |
| env-paths | 2.2.1 | 4.0.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| fd-slicer | 1.1.0 | 1.1.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| fs-extra | 11.4.0 | 11.4.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| glob | 13.0.6 | 13.0.6 | Build filesystem/path/archive utilities; transitive | No returned match |
| graceful-fs | 4.2.11 | 4.2.11 | Build filesystem/path/archive utilities; transitive | No returned match |
| inherits | 2.0.4 | 2.0.4 | Supporting CLI/build utility (transitive); transitive | No returned match |
| ini | 4.1.3 | 7.0.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| is-docker | 2.2.1 | 4.0.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| is-fullwidth-code-point | 3.0.0 | 5.1.0 | CLI display/input formatting; transitive | No returned match |
| is-wsl | 2.2.0 | 3.1.1 | Supporting CLI/build utility (transitive); transitive | No returned match |
| isexe | 2.0.0 | 4.0.0 | CLI process/device execution; transitive | No returned match |
| jsonfile | 6.2.1 | 6.2.1 | Build filesystem/path/archive utilities; transitive | No returned match |
| kleur | 4.1.5 | 4.1.5 | CLI display/input formatting; transitive | No returned match |
| lru-cache | 11.5.2 | 11.5.2 | Supporting CLI/build utility (transitive); transitive | No returned match |
| minimatch | 10.2.6 | 10.2.6 | Build filesystem/path/archive utilities; transitive | No returned match |
| minipass | 7.1.3 | 7.1.3 | Tooling stream/buffer utilities; transitive | No returned match |
| minizlib | 3.1.0 | 3.1.0 | Tooling stream/buffer utilities; transitive | No returned match |
| ms | 2.1.3 | 2.1.3 | Supporting CLI/build utility (transitive); transitive | No returned match |
| native-run | 2.0.3 | 2.0.3 | CLI process/device execution; transitive | No returned match |
| open | 8.4.2 | 11.0.2 | CLI process/device execution; transitive | No returned match |
| package-json-from-dist | 1.0.1 | 1.0.1 | Supporting CLI/build utility (transitive); transitive | No returned match |
| path-key | 3.1.1 | 4.0.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| path-scurry | 2.0.2 | 2.0.2 | Build filesystem/path/archive utilities; transitive | No returned match |
| pend | 1.2.0 | 1.2.0 | Tooling stream/buffer utilities; transitive | No returned match |
| plist | 3.1.1 | 5.0.0 | Build metadata/XML/plist processing; transitive | No returned match |
| prompts | 2.4.2 | 2.4.2 | CLI display/input formatting; transitive | No returned match |
| kleur | 3.0.3 | 4.1.5 | CLI display/input formatting; transitive | No returned match |
| readable-stream | 3.6.2 | 4.7.0 | Tooling stream/buffer utilities; transitive | No returned match |
| rimraf | 6.1.3 | 6.1.3 | Build filesystem/path/archive utilities; transitive | No returned match |
| safe-buffer | 5.2.1 | 5.2.1 | Tooling stream/buffer utilities; transitive | No returned match |
| sax | 1.1.4 | 1.6.1 | Build metadata/XML/plist processing; transitive | No returned match |
| semver | 7.8.5 | 7.8.5 | Supporting CLI/build utility (transitive); transitive | No returned match |
| shebang-command | 2.0.0 | 2.0.0 | CLI process/device execution; transitive | No returned match |
| shebang-regex | 3.0.0 | 4.0.0 | CLI process/device execution; transitive | No returned match |
| signal-exit | 3.0.7 | 4.1.0 | CLI process/device execution; transitive | No returned match |
| simple-plist | 1.3.1 | 1.3.1 | Build metadata/XML/plist processing; transitive | No returned match |
| bplist-parser | 0.3.1 | 0.5.0 | Build metadata/XML/plist processing; transitive | No returned match |
| sisteransi | 1.0.5 | 2.0.0 | CLI display/input formatting; transitive | No returned match |
| slice-ansi | 4.0.0 | 9.0.0 | CLI display/input formatting; transitive | No returned match |
| split2 | 4.2.0 | 4.2.0 | Tooling stream/buffer utilities; transitive | No returned match |
| stream-buffers | 2.2.0 | 3.0.3 | Tooling stream/buffer utilities; transitive | No returned match |
| string_decoder | 1.3.0 | 1.3.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| string-width | 4.2.3 | 8.2.2 | CLI display/input formatting; transitive | No returned match |
| strip-ansi | 6.0.1 | 7.2.0 | CLI display/input formatting; transitive | No returned match |
| tar | 7.5.22 | 7.5.22 | Build filesystem/path/archive utilities; transitive | No returned match |
| through2 | 4.0.2 | 5.0.11 | Tooling stream/buffer utilities; transitive | No returned match |
| tree-kill | 1.2.2 | 1.2.2 | CLI process/device execution; transitive | No returned match |
| tslib | 2.8.1 | 2.8.1 | Supporting CLI/build utility (transitive); transitive | No returned match |
| undici-types | 8.3.0 | 8.10.2 | Build-time type declarations; transitive | No returned match |
| universalify | 2.0.1 | 2.0.1 | Supporting CLI/build utility (transitive); transitive | No returned match |
| untildify | 4.0.0 | 6.0.0 | Build filesystem/path/archive utilities; transitive | No returned match |
| util-deprecate | 1.0.2 | 1.0.2 | Supporting CLI/build utility (transitive); transitive | No returned match |
| uuid | 7.0.3 | 14.0.2 | Build identifier generation; transitive | SEC-011; 1 match |
| which | 2.0.2 | 7.0.0 | CLI process/device execution; transitive | No returned match |
| wrap-ansi | 7.0.0 | 10.0.1 | CLI display/input formatting; transitive | No returned match |
| xcode | 3.0.1 | 3.0.1 | Build metadata/XML/plist processing; transitive | No returned match |
| xml2js | 0.6.2 | 0.6.2 | Build metadata/XML/plist processing; transitive | No returned match |
| xmlbuilder | 11.0.1 | 15.1.1 | Build metadata/XML/plist processing; transitive | No returned match |
| xmlbuilder | 15.1.1 | 15.1.1 | Build metadata/XML/plist processing; transitive | No returned match |
| yallist | 5.0.0 | 5.0.0 | Supporting CLI/build utility (transitive); transitive | No returned match |
| yauzl | 2.10.0 | 3.4.0 | Build filesystem/path/archive utilities; transitive | No returned match |

Locked deprecation: uuid 7.0.3: uuid@10 and below is no longer supported.  For ESM codebases, update to uuid@latest.  For CommonJS codebases, use uuid@11 (but be aware this version will likely be deprecated in 2028).. No confirmed intentionally malicious package was identified; package signing/publisher control was not independently attested.

### Gradle/Maven — statically declared coordinates

104 declaration occurrences were extracted from application Gradle files and verified package-source build files. The table deduplicates coordinate/version pairs. Plugin fallback versions and publishing-only branches are declarations, not proof of effective resolution. The complete occurrence list, scopes, conditional flags and line numbers are in the companion JSON. Transitive POM resolution, dynamic build logic and the effective dependency graph remain unverified because Gradle was not executed. Maven latest-version comparisons and maintenance status were not exhaustively established.

| Coordinate | Declared version | Purpose | Advisory query / applicability |
| --- | --- | --- | --- |
| org.jetbrains.kotlin:kotlin-stdlib | 2.1.0 | Kotlin/coroutines | No returned match |
| org.jetbrains.kotlinx:kotlinx-coroutines-core | 1.10.2 | Kotlin/coroutines | No returned match |
| org.jetbrains.kotlinx:kotlinx-coroutines-android | 1.10.2 | Kotlin/coroutines | No returned match |
| androidx.appcompat:appcompat | 1.7.1 | Android UI/lifecycle support | No returned match |
| androidx.coordinatorlayout:coordinatorlayout | 1.3.0 | Android UI/lifecycle support | No returned match |
| androidx.core:core-splashscreen | 1.2.0 | Android UI/lifecycle support | No returned match |
| androidx.camera:camera-core | 1.5.3 | Camera/media | No returned match |
| androidx.camera:camera-camera2 | 1.5.3 | Camera/media | No returned match |
| androidx.camera:camera-lifecycle | 1.5.3 | Camera/media | No returned match |
| androidx.camera:camera-video | 1.5.3 | Camera/media | No returned match |
| androidx.camera:camera-view | 1.5.3 | Camera/media | No returned match |
| androidx.media3:media3-exoplayer | 1.10.1 | Video/RTSP | No returned match |
| androidx.media3:media3-exoplayer-rtsp | 1.10.1 | Video/RTSP | No returned match |
| com.google.android.gms:play-services-location | 21.3.0 | Location | No returned match |
| androidx.room:room-runtime | 2.6.1 | Database | No returned match |
| androidx.room:room-ktx | 2.6.1 | Database | No returned match |
| androidx.room:room-compiler | 2.6.1 | Database | No returned match |
| androidx.lifecycle:lifecycle-service | 2.8.7 | Android UI/lifecycle support | No returned match |
| com.squareup.okhttp3:okhttp | 4.12.0 | HTTP transport | No returned match |
| junit:junit | 4.13.2 | Tests | No returned match |
| org.json:json | 20250517 | JSON | No returned match |
| com.squareup.okhttp3:mockwebserver | 4.12.0 | Tests | No returned match |
| androidx.test.ext:junit | 1.3.0 | Tests | No returned match |
| androidx.test.espresso:espresso-core | 3.7.0 | Tests | No returned match |
| com.android.tools.build:gradle | 8.13.0 | Build/code generation | No returned match |
| com.google.gms:google-services | 4.4.4 | Build/code generation | No returned match |
| org.jetbrains.kotlin:kotlin-gradle-plugin | 2.1.0 | Build/code generation | SEC-012; KAPT condition unestablished |
| com.google.devtools.ksp:com.google.devtools.ksp.gradle.plugin | 2.1.0-1.0.29 | Build/code generation | No returned match |
| io.github.gradle-nexus:publish-plugin | 1.3.0 | Build/code generation | Unresolved declaration / not queried |
| androidx.core:core | 1.17.0 | Android UI/lifecycle support | No returned match |
| androidx.activity:activity | 1.11.0 | Android UI/lifecycle support | No returned match |
| androidx.fragment:fragment | 1.8.9 | Android UI/lifecycle support | No returned match |
| androidx.webkit:webkit | 1.14.0 | Android UI/lifecycle support | No returned match |
| org.apache.cordova:framework | 14.0.1 | Native bridge | No returned match |
| org.mockito:mockito-core | 5.20.0 | Tests | No returned match |
| com.capacitorjs:core | $capacitorVersion | Native bridge | Unresolved declaration / not queried |
| org.jetbrains.kotlin:kotlin-gradle-plugin | 2.2.20 | Build/code generation | SEC-012; KAPT condition unestablished |
| io.ionic.libs:ioncamera-android | 1.0.2 | Camera/media | No returned match |
| androidx.exifinterface:exifinterface | 1.4.1 | Camera/media | No returned match |
| com.google.android.material:material | 1.13.0 | Android UI/lifecycle support | No returned match |
| androidx.core:core-ktx | 1.17.0 | Android UI/lifecycle support | No returned match |
| com.google.code.gson:gson | 2.10.1 | JSON | No returned match |
| io.ionic.libs:ionfilesystem-android | 1.1.0 | Filesystem | No returned match |
| io.ionic.libs:iongeolocation-android | 2.2.2 | Location | No returned match |
| com.google.code.gson:gson | 2.13.2 | JSON | No returned match |
| org.jetbrains.kotlinx:kotlinx-coroutines-play-services | 1.10.2 | Kotlin/coroutines | No returned match |

### Python and standalone web dependency

Package manager: pip. Root requirements are lower bounds, with no exact resolved environment/lock inspected. Therefore no exact-version vulnerability clearance or claim of current/latest versions is made.

| Dependency | Declared version | Purpose | Status |
| --- | --- | --- | --- |
| playwright | >=1.40 | Browser/evaluation checks | Unpinned; downloaded browser also requires provenance |
| python-dotenv | >=1.0.0 | Evaluation environment loading | Unpinned; dev/eval only |
| Pillow | >=10.0.0 | Artwork/image tooling | Unpinned; native decoder transitive risks unresolved |
| Leaflet | 1.9.4 | Web map presentation | OSV npm query: no returned match; standalone web asset |

Standard-library and local-module imports are listed separately in the JSON and must not be treated as installable third-party packages. Gradle wrapper/distribution integrity and pinned GitHub Action references are discussed in sections 16–17.

### Advisory evidence

Queried on 11 September 2026. OSV package/version responses are preserved in the inventory; primary advisory/fix links below support the matches. Applicability and project severity are recorded in SEC-008, SEC-011 and SEC-012, not inferred solely from upstream severity.

| Advisory | Summary | Matched declaration | Remediation boundary |
| --- | --- | --- | --- |
| [GHSA-27p8-2357-5qqv](https://github.com/xmldom/xmldom/security/advisories/GHSA-27p8-2357-5qqv) | xmldom: DocType `name` Injection Bypasses requireWellFormed | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-3px3-54cx-rmw9](https://github.com/xmldom/xmldom/security/advisories/GHSA-3px3-54cx-rmw9) | xmldom: Creation-time XML Name/QName validation is bypassable via an embedded line terminator, allowing injection on the default serialization path | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-6gmq-8vp8-gcm6](https://github.com/xmldom/xmldom/security/advisories/GHSA-6gmq-8vp8-gcm6) | xmldom: XML fragment injection via invalid EntityReference.nodeName during requireWellFormed serialization | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-6h8r-xr42-gp59](https://github.com/xmldom/xmldom/security/advisories/GHSA-6h8r-xr42-gp59) | xmldom: Parser silently accepts a not-well-formed end tag whose name is followed by a line break and trailing content | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-6mj3-qw4j-hgrw](https://github.com/xmldom/xmldom/security/advisories/GHSA-6mj3-qw4j-hgrw) | xmldom: HTML raw-text closing-tag case mismatch causes output amplification | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-8344-3jmq-59r6](https://github.com/xmldom/xmldom/security/advisories/GHSA-27p8-2357-5qqv) | xmldom: Quadratic-time attribute deduplication | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-93r5-fhx6-vmg9](https://github.com/xmldom/xmldom/security/advisories/GHSA-93r5-fhx6-vmg9) | xmldom: Quadratic-time parsing via the malformed-input recovery path — `parseElementStartPart` re-scan and `normalize()` adjacent-text merge | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-965w-775f-mr7g](https://github.com/xmldom/xmldom/security/advisories/GHSA-965w-775f-mr7g) | xmldom: Quadratic-memory consumption | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-c7q8-3ch8-vqpv](https://github.com/xmldom/xmldom/security/advisories/GHSA-c7q8-3ch8-vqpv) | xmldom: Processing Instruction Target Injection Bypasses requireWellFormed | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-jxjr-3g7g-3944](https://github.com/xmldom/xmldom/security/advisories/GHSA-jxjr-3g7g-3944) | xmldom: requireWellFormed element/attribute name validation is bypassable via an embedded line terminator | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-r937-wjx7-w2jp](https://github.com/advisories/GHSA-r937-wjx7-w2jp) | JetBrains Kotlin: Unsafe Deserialization in Kotlin Build Cache Enables Code Execution | Kotlin plugin 2.1.0 / 2.2.20 | KAPT only; verify stable release containing fix |
| [GHSA-vr34-hp96-76pp](https://github.com/xmldom/xmldom/security/advisories/GHSA-vr34-hp96-76pp) | xmldom: requireWellFormed DocType publicId/systemId validation is bypassable via an embedded line terminator | @xmldom/xmldom 0.9.11 | 0.9.12; verify tooling compatibility/reachability |
| [GHSA-w5hq-g745-h8pq](https://github.com/uuidjs/uuid/security/advisories/GHSA-w5hq-g745-h8pq) | uuid: Missing buffer bounds check in v3/v5/v6 when buf is provided | uuid 7.0.3 | Compatible parent update; fixed branches 11.1.1 / 12.0.1 / 13.0.1 |

The [Kotlin upstream fix](https://github.com/JetBrains/kotlin/commit/bf51df665b458fda7c3eaf436c4d88dc119d7ec6) targets KAPT cache deserialization. Its existence does not establish KAPT use in this app. Do not force major npm overrides or a beta Kotlin upgrade based only on version matches. Resolve and test a compatible maintained dependency set in the later remediation phase.

## Appendix B — Coverage, evidence and next verification

The accompanying JSON records the full 847-file inventory, working-copy hashes, 104 Maven declaration occurrences (some conditional), npm package paths/versions/integrity metadata, extracted URL origins with examples, Python import inventory, redacted history candidates, package-source verification receipts, APK inspection and current advisory results. Working-copy text hashes may reflect CRLF; the commit and canonical APK comparisons identify source content independently.

Risk-based manual review covered the manifests/configuration, native plugin permissions/paths/media transport, inference request/response parsing, storage/deletion paths, JS rendering and handoffs, email/camera/Capacitor package source, workflow/release scripts, public-data loaders/builders, evaluation credential paths and relevant security tests. Tests such as stored_xss, privacy_consent, delete_all_data, state_pack_validation, stalled_body, native path/budget checks and release optimization were inspected as supporting intent, **not counted as passed**. No repository test suite was executed.

The static audit cannot claim a complete resolved transitive SBOM, exhaustive runtime testing of all paths, binary decoder safety, verified signer identity, source-to-native-DEX reproducibility or inspection of private GitHub/provider settings. Those remain explicit acceptance evidence, not silent assumptions. No external service was probed for vulnerabilities and no real credential was printed or tested.

## SECURITY GATE

**FAIL — do not approve this revision unchanged as the foundation of a public production application.**

Before approval:

1. Fix and device-verify incomplete app-owned media deletion (SEC-002).
2. Remove paid AI credentials/calls or implement appropriate credential protection and bounded spending for the chosen BYOK/shared-service design (SEC-001/006).
3. Bound remote downloads before allocation and validate transport/media failure behavior (SEC-004, with SEC-005/010 regression checks).
4. Isolate the writable catalog automation if retained and approve a reproducible, scanned build dependency graph; address xmldom and document conditional uuid/KAPT reachability (SEC-007/008/011/012).
5. Disable unprotected dashcam use or accept only a documented protected deployment (SEC-003). Remove browser fragment-key imports if the web app is published (SEC-016).
6. Independently verify release signing/provenance and demonstrate Android permission, bridge, URI-grant and deletion behavior on devices. Produce the unresolved transitive-dependency and dynamic-test evidence noted above.
7. Before any shared Uzbekistan backend/community rollout, implement object/role authorization, private media storage, ingestion limits, quotas, moderation and location-minimizing publication. The current local app has none of that backend because it does not need it yet.

Remaining Low/Info items need remediation or a documented, reviewed risk acceptance appropriate to the chosen deployment. A closed private pilot with synthetic media is a different approval scope from national public deployment. No fixes or feature development were performed. **Audit ends here.**
