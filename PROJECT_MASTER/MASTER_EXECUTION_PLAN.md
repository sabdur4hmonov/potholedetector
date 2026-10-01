# Master execution plan

**Plan date:** 2026-09-29 (+05:00). **Repository:** D:\Coding projects\pothole-reporter. **Checkpoint:** main at 86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8. This file is an execution index, not evidence that a proposed feature or release exists. Read [AGENTS.md](../AGENTS.md) first. [PROJECT_STATUS.md](PROJECT_STATUS.md), [SECURITY_STATUS.md](SECURITY_STATUS.md), [AGENT_WORKLOG.md](AGENT_WORKLOG.md), and the per-finding reports own their detailed facts.

## 1. Executive summary

Pothole Reporter is an existing local Android/Capacitor app being adapted from India-specific coverage toward a free-to-user Uzbekistan product. Preserve its working local capture, full-frame evidence, report, deduplication, repair, storage, and pack-verification paths. The existing detector calls OpenAI with a user credential; a free local/manual production path is a decision and implementation gap. No project-operated backend, account system, shared map, Uzbekistan authority registry, navigation route feed, or speed-camera dataset exists.

**Current active task: NEW002-PROV-001.** BUILD-DEBUG-001 and BUILD-APK-001 completed on 2026-09-29: the actual offline debug build succeeded, and the generated APK passed the applicable structural, metadata, debug-signature and packaged-asset checks. Release, device, NEW-002 provenance, and product work remain separate gates.

Use the phase and task registry below as an ordered queue with explicit conditional branches. A phase is not permission to execute every task in it. A future session takes one eligible task, checks its current evidence, and stops at its documented boundary.

## 2. Current verified state and authority

| Item | Verified state at this plan checkpoint | Evidence |
| --- | --- | --- |
| Git | main; HEAD 86ef123450927a91b1cdee7fdb1f4fbbb0b0d7b8. Six PROJECT_MASTER documents are already modified by earlier uncommitted checkpoint work. No plan-time commit or push. | Git status; [worklog](AGENT_WORKLOG.md) |
| Windows and toolchain | Current-user command runner works; repository ownership corrected. D: project-local JDK 21.0.12.1, Android SDK 36, build-tools 35.0.0/36.0.0 and pinned Gradle 8.14.3 work. | [PROJECT_STATUS.md](PROJECT_STATUS.md), [NEW-002](SECURITY_REMEDIATION_NEW002.md) §§21–24 |
| Java socket setting | Gradle needs process-local JDK_JAVA_OPTIONS with jdk.net.unixdomain.tmpdir pointed at the Android project’s D: .gradle directory. No system-wide change. | [NEW-002](SECURITY_REMEDIATION_NEW002.md) §22 |
| Dependency cache | 329 external files in inspected resolvable debug configurations passed an offline check. A first actual debug build then found task-time AAPT2 missing. The exact AAPT2 POM and Windows JAR were fetched from Google Maven, matched Google SHA-256 sidecars, and resolved offline. | [NEW-002](SECURITY_REMEDIATION_NEW002.md) §§23–24 |
| Build and artifacts | After exact AAPT2 provisioning, one actual offline :app:assembleDebug succeeded on 2026-09-29. `app-debug.apk` is 13,761,302 bytes, SHA-256 `7225a5a321b93b1827202719f4f16401b3aa5006e20ef85deebb7ee5801a39d1`; ZIP integrity, aapt metadata, debug v2 signature and packaged web assets passed. Signed release and device run are not established. | [PROJECT_STATUS.md](PROJECT_STATUS.md), [worklog](AGENT_WORKLOG.md) |
| Security gate | Overall FAIL. SEC-001–SEC-016 and NEW-001 have the statuses in SECURITY_STATUS; there is no SEC-017. NEW-002 remains PARTIALLY RESOLVED: generated-input preflight exists, but full Gradle dependency provenance and clean signed release are unverified. | [SECURITY_STATUS.md](SECURITY_STATUS.md) |
| Product | Existing Android/local app and India reference packs. Uzbekistan deployment, free detector choice, shared backend/community, and public-sector integration remain future work. | [ARCHITECTURE.md](ARCHITECTURE.md), [PRODUCT_IMPLEMENTATION_ROADMAP.md](PRODUCT_IMPLEMENTATION_ROADMAP.md), source |

**Source precedence.** AGENTS.md controls agent invariants; current PROJECT_STATUS, SECURITY_STATUS, NEXT_STEPS and latest worklog control checkpoint status; remediation reports control their findings; source/tests control claims that code exists. The 2026-09-14 [product roadmap](PRODUCT_IMPLEMENTATION_ROADMAP.md) owns detailed *proposals*, not later execution status. Its mention of “SEC-017” conflicts with AGENTS.md and the current security record; **no SEC-017 exists**. Its old “NEW-001 open” and old build-blocker wording are superseded by the current security status and 2026-09-29 worklog. Historical text stays intact for provenance. The old C: paths in README/SETUP_WINDOWS/COMMANDS are snapshots, not the current D: checkout.

## 3. Intended product and non-negotiable boundaries

The documented direction is a private-first Uzbekistan pothole reporter: capture or import complete frames; produce conservative local observations; merge repeated sightings of the same physical defect; let the person review and explicitly hand off a report to an appropriate verified channel; show useful, honest hazard/road information; and work offline wherever feasible. A free-to-user detector path is required before claiming practical continuous Drive detection. Optional shared/community services are conditional on a human choice and a separate backend/privacy design. India logic and packs remain intact for compatibility; Uzbekistan coverage must be built from reviewed sources, never relabeled India data.

Every detection, replay, evaluation, training-preparation, and evidence input preserves the full edge-to-edge frame. Whole-frame orientation, scaling, compression and enhancement may preserve the field of view. No crop, tile, mask or road-band evidence path is allowed. Keep the SEC-001–016 and NEW-001/002 controls, transaction ownership, fail-closed matching, user-confirmed handoff, bounded downloads/inference, CSP, and generated-input preflight. Do not claim government authorization, legal compliance, complete road/speed-camera coverage, actual road ownership, measured pothole dimensions, or device/release verification without evidence.

## 4. Implemented versus planned feature matrix

Here **Implemented** means source behavior exists, not that a new APK/device run verified it. **Partial** means useful source behavior exists with a material gap. **Planned** means the roadmap describes it but source does not implement it. **Blocked** requires a named prerequisite. **Deferred** is conditional on a human decision. **Unknown/needs verification** is not silently promoted to implemented.

| Functional area | Current status | Current evidence and remaining work |
| --- | --- | --- |
| Phone-camera Drive and GPS association | Implemented at source; runtime unverified | Native DriveForegroundService, NativeDriveLocationProvider and NativeGpsFixHistory; device gate remains. |
| Full-frame cloud pothole detection | Partial | NativeInferenceEngine and web analyzeImage call OpenAI; user credential/network and lifetime AI budget limit scale. Full-frame invariant remains enforced. |
| Free/manual or on-device detection | D0 decided; implementation pending | Manual-first private offline photo reporting selected; cloud/BYOK retained as optional. DETECT-001 decision complete; REPORT-LOCAL-001 not started. No on-device model shipped. See PRODUCT_DECISIONS.md. |
| Manual photo/report and reviewed handoff | Partial | Local report and external official/email/share handoff exist; India-specific routes and no automatic filing. Uzbekistan authority paths need reviewed data. |
| Canonical physical-pothole deduplication | Implemented locally | NativeDeduplicationEngine and web roadEventMatch merge eligible observations into one report; manual photos intentionally do not auto-merge. Cross-user canonicalization is absent. |
| Repeated sightings | Implemented locally | Native event_sightings and seenCount/drive IDs; web seen_count, sighting_drive_ids and last_seen_at. Independent cross-user confirmation is absent. |
| Confidence, freshness and severity | Planned | Existing timestamps, size/damage and condition are inputs; no score/state-machine policy or user-facing confidence. Size is a visual estimate, not a measurement. |
| Repair/fixed workflow | Partial | NativeRepairStatusEngine and web condition routes, repair_review/fixed, replay-safe observations; free non-AI and multi-user consensus are missing. Negative passes must never auto-mark fixed. |
| GPS tracks and drive limits | Implemented locally | Room sessions.gpsTrackJson and IndexedDB drives.gps_track; 20,000-point native cap and active-time limit. Retention decision D1 remains open. |
| Trip statistics and history | Partial | Local distance/km, drive counts and terminal checked/found/already summary exist; moving time, average/max speed, route history controls and per-drive route deletion do not. |
| Offline-first storage/replay/outbox | Partial | Room/IndexedDB, durable keyframes, native-to-web paged sync/ack, verified pack cache and offline map fallback exist; detection, geocoding and future community sync are not offline-complete. |
| Native-to-web report/repair outbox | Implemented locally | DriveModePlugin sync/ack and NativeOutboxKeysetPager; future warning and shared-sync paths should reuse contracts. |
| India highway matcher and tile builder | Implemented for inherited coverage | matchHighwayTile and tools/build-national-highways.py with cached packs; this is not Uzbekistan coverage. Current extract rebuild needs reviewed SHA-256 source (SEC-015). |
| Uzbekistan roads, segments and authority routing | Blocked | No Uzbekistan pack or registry in source; D2 source, licensing, authority and legal review precede new packs/handoffs. |
| Road-health score and personal heatmap | Planned | Existing local point map and offline SVG scatter; no segment IDs, segment aggregation, score or heatmap. |
| Dynamic hazard warnings | Planned | Native service has live speed/heading and one notification channel; no lookahead policy, target mirror, throttle, safe audio or warning feedback. |
| Route-aware warnings, navigation and ETA | Blocked | openMaps is a Google Maps handoff without route feedback; no routing engine or ETA. Route-source decision RS is required. |
| Speed-camera/radar and other hazard infrastructure | Deferred | No dataset, pack, alert or legal review. Published/static POIs and mobile crowdsourcing are separate decisions; neither may imply complete coverage. |
| Maps/offline fallback | Partial | Leaflet points with online tiles and local SVG scatter fallback exist. No licensed offline basemap or Uzbekistan segment overlay. |
| Verified pack cache | Implemented at source | Bounded streaming, hash/schema checks and pruning exist; new Uzbekistan pack families must retain them. |
| Production Uzbekistan backend/accounts/auth | Deferred | No project backend, accounts or API. Required only if shared reports/community are chosen (D3); provider unselected. |
| Community sync, server dedupe and shared repair | Deferred | No remote sync or server canonical hazard; requires backend, consent, authorization and privacy policy. |
| Trust/reputation and contribution rankings | Deferred | No identity or ledger. Contributions may be ranked only after server verification; speed/distance/time must never feed ranking. |
| Community heatmap | Deferred | No shared data; may publish defect positions only, never private trips/reporter identity. |
| Uzbek/Russian localization | Planned | Current I18N has English, Kannada, Marathi, Bengali only. Translation, review and layout checks required. |
| Production TTS | Planned | No TextToSpeech path; safety policy, local voices and device checks required before audible driving alerts. |
| Government/operations dashboard | Deferred | BMC_PILOT.md is a pilot proposal, not a dashboard. A separate app/authorized partner and backend roles are prerequisites. |
| Signed release and device verification | Blocked | NEW-001 source/tooling fix exists; no new signed release, independent full dependency provenance or physical device/emulator run. |

Source anchors: [FILE_INDEX.md](FILE_INDEX.md), [ARCHITECTURE.md](ARCHITECTURE.md), [PRODUCT_IMPLEMENTATION_ROADMAP.md](PRODUCT_IMPLEMENTATION_ROADMAP.md) §§1–8, native source under [drive](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/) and [db](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/db/), [DriveModePlugin.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt), [static/standalone.js](../static/standalone.js), [static/index.html](../static/index.html), and [SEC-013](SECURITY_REMEDIATION_SEC013.md).

## 5. Architecture and data boundaries

Android native owns capture, foreground/background Drive execution, GPS pairing, inference, local transaction/dedupe, repair observation, private media and Keystore-backed secret handling. The privileged Capacitor WebView owns report review, local REST-shaped handle() routes, IndexedDB, map/dashboard and pack downloads. DriveModePlugin connects them through bounded, paged outbox calls with acknowledgement after web commit. static/ is canonical web source; android-app/www and docs are mirrors; generated Android assets/public is packaged output. tools/ and data/ build reviewed content-addressed packs for docs/packs/v1; the app checks envelopes and SHA-256 before activation. This architecture is described in [ARCHITECTURE.md](ARCHITECTURE.md).

Do not replace the existing backend-free local API facade with a remote service merely because it uses /api/ paths. If D3 selects shared reports, add an opt-in sync layer alongside the local facade. Public hazard points, private journeys, reporter identity and evidence media need separate access and retention controls. No raw track is shared by default. The citizen WebView and any future government dashboard must remain separate trust surfaces.

Data evolution should be additive: current native Room v7 and IndexedDB v6 remain authoritative until migrations are specified and tested. Prefer derived confidence/freshness/severity before persisting fields. Introduce segment IDs, warning targets, pass logs and remote IDs only when their tasks need them. Extend both delete-all paths and migration tests for every new store. See [roadmap §5](PRODUCT_IMPLEMENTATION_ROADMAP.md) for proposed S1–S8 fields; those are **not implemented schemas**.

## 6. Phase roadmap

Each phase card names its objective/why, prerequisites and dependencies, tasks, affected areas and reusable code, tests and acceptance/definition of done, privacy/security and performance/offline rules, protected behavior, and likely blockers. Conditional phases remain deferred until their decisions are recorded. The task registry in §7 is the executable level.

### Phase 0 — Windows debug, provenance, release and device checkpoint

- **Objective/why:** Establish an actual build and artifact baseline before product work; do not confuse cached dependencies with a successful APK.
- **Prerequisites/dependencies:** Existing D: toolchain/cache and process-local Java socket setting; AAPT2 now cached. Human signing material and device/emulator are later gates.
- **Tasks and areas/reuse:** BUILD-DEBUG-001, conditional BUILD-ROOT-001, BUILD-APK-001, NEW002-PROV-001, RELEASE-001, RELEASE-VERIFY-001, DEVICE-001; use COMMANDS.md, build-play-release.sh, generated-input preflight and NEW-001 tooling.
- **Tests/acceptance/done:** One actual debug build; if it succeeds, nonempty APK and documented checks. Later: reviewed dependency provenance, signed APK/AAB with identity/order checks, then device scenarios. Record exact failures rather than loop retries.
- **Security/privacy and performance/offline:** No secrets in logs; preserve full-frame/CSP and offline cache integrity. No paid calls. The debug build remains offline.
- **Must not change:** No speculative application code, broad AGP/Gradle upgrades, security rewrites or signing bypasses.
- **Likely blockers:** New task-time missing artifact, genuine compile error, full-graph NEW-002 provenance, legitimate signing key, no connected device.

### Phase 1 — Core behavior and shared contracts

- **Objective/why:** Make native/web dedupe and outbox behavior testable before extending it.
- **Prerequisites/dependencies:** Phase 0 source/build result recorded; no product feature requires release approval. Owner decisions can proceed in parallel.
- **Tasks and areas/reuse:** CORE-001 and CORE-002 in NativeDeduplicationEngine, pure matcher/fixtures, roadEventMatch and existing outbox tests; reuse NativeRepairCandidateMatcher and image parity fixture pattern.
- **Tests/acceptance/done:** Existing dedupe/repair behavior unchanged, shared native/JS cases pass including manual non-merge, replay, heading, GPS and fixed recurrence; outbox ack remains after commit.
- **Security/privacy and performance/offline:** No network or schema change; bound fixture data and preserve evidence ownership.
- **Must not change:** Dedupe transaction/mutex, repair decision semantics, full-frame path, India routing.
- **Likely blockers:** Native JVM test execution if build still fails; document static-only evidence honestly.

### Phase 2 — Free-to-user detection and local reporting

- **Objective/why:** Replace the practical dependence on user-paid cloud inference without weakening detection/evidence quality.
- **Prerequisites/dependencies:** D0 human decision on manual-first versus reviewed on-device detector; Phase 1 contracts. Model/licence/performance evidence if an on-device option is selected.
- **Tasks and areas/reuse:** DETECT-001 and REPORT-LOCAL-001; NativeInferenceEngine, DriveForegroundService, manual Photo, evidence factory, local report/handoff.
- **Tests/acceptance/done:** Whole-frame hard-negative evaluation, latency/memory/battery budget, offline replay, manual path, false-positive/false-merge samples and unchanged report/export contracts; no claim of production detector until evidence passes.
- **Security/privacy and performance/offline:** No hidden paid call or retained credential path in a chosen no-cloud release; bounded images, private media, offline operation or explicit deferred analysis.
- **Must not change:** Frame field of view, SEC-005/006 limits, existing strict detection contract, user-confirmed handoff.
- **Likely blockers:** D0, approved model/data licence and device performance corpus.

### Phase 3 — Confidence, freshness, severity and repair signals

- **Objective/why:** Convert existing sightings and condition fields into conservative, explainable hazard information.
- **Prerequisites/dependencies:** Phase 1 parity contract; Phase 2 detector decision informs calibration, but source-level score prototypes may use existing records.
- **Tasks and areas/reuse:** CONF-001, FRESH-001 and REPAIR-001; pure Kotlin/JS policy, existing report fields, NativeRepairStatusEngine and repair_status_test.py.
- **Tests/acceptance/done:** Shared fixtures agree across runtimes; score inputs/unknown cases documented; stale and fixed handling correct; negative evidence never auto-marks fixed; display labels distinguish visual estimate from measurement.
- **Security/privacy and performance/offline:** Derived locally, bounded cost, no network or precise location disclosure.
- **Must not change:** Manual non-merge, fixed recurrence, repair temporal ordering, conservative candidate matcher.
- **Likely blockers:** Calibration evidence and owner acceptance of public wording/thresholds.

### Phase 4 — Native driving warnings and safety behavior

- **Objective/why:** Give useful warnings while Maps/WebView is backgrounded without distracting the driver.
- **Prerequisites/dependencies:** Phase 3 score/freshness, Phase 1 contracts, available device for release verification. Route-aware ETA is later Phase 7.
- **Tasks and areas/reuse:** WARN-001, WARN-002 and WARN-NEG-001; new pure lookahead/throttle policy, native service hook, Room warning-target mirror, DriveModePlugin target-sync pattern and NotificationHelper.
- **Tests/acceptance/done:** Accurate heading/speed corridor, duplicate throttle, offline warning target use, bounded logs, stationary-only feedback and instrumented notification/drive checks.
- **Security/privacy and performance/offline:** On-device decision path with no network, no action required while moving, conservative GPS gates, low battery overhead.
- **Must not change:** Foreground service ownership, report/fixed state, existing notification channel semantics until migration tested.
- **Likely blockers:** Device access, false-warning calibration, OS notification behavior.

### Phase 5 — Private trip statistics and route retention

- **Objective/why:** Make the existing local drive track useful without turning private journeys into public contribution metrics.
- **Prerequisites/dependencies:** D1 human retention/opt-out/minimization decision; Phase 1 contracts.
- **Tasks and areas/reuse:** TRIP-001 and TRIP-002; existing gps_track, trackKm, sessions/drives, getDrives, delete-all and migration patterns.
- **Tests/acceptance/done:** Accuracy/jump-filtered private distance/moving time/average/max, per-drive route deletion/retention behavior, additive migrations and storage enumeration; route history screen uses only retained data.
- **Security/privacy and performance/offline:** Local-only; no track upload or speed ranking; compute incrementally/bounded; no network needed.
- **Must not change:** SEC-013 disclosure and Delete All completeness; do not infer consent to store routes indefinitely.
- **Likely blockers:** D1 and device/migration verification.

### Phase 6 — Reviewed Uzbekistan roads, segments and handoffs

- **Objective/why:** Replace India-only coverage with trustworthy Uzbekistan data, without guessing road owner or grievance recipient.
- **Prerequisites/dependencies:** D2 reviewed road/authority sources, licensing, source pins and local legal/operational review; Phase 1 contracts.
- **Tasks and areas/reuse:** UZ-SOURCE-001, SEG-001 and UZ-HANDOFF-001; data/uz, source receipts, highway builder/matcher, verified pack downloader and routing facade.
- **Tests/acceptance/done:** Reproducible SHA-256-pinned pack, coverage/ambiguity fixtures, nullable unmatched segments, fail-closed authority selection, user-confirmed external handoff; no India regression.
- **Security/privacy and performance/offline:** Bounded authenticated source process and runtime pack verification, source attribution, offline cached matching, no automatic filing.
- **Must not change:** India routing/pack compatibility, SEC-004/015 checks, road-owner caveats.
- **Likely blockers:** No approved source/authority agreement; retired highway extract pin is not reusable.

### Phase 7 — Personal road health, maps and route context

- **Objective/why:** Combine local hazards with reviewed segments for honest personal health views; route ETA only if a route source is chosen.
- **Prerequisites/dependencies:** Phases 3 and 6; RS decision for ETA; offline-basemap licence decision if needed.
- **Tasks and areas/reuse:** HEALTH-001, MAP-001 and conditional ROUTE-001; static map/Leaflet/scatter, segment matching and hazard scoring.
- **Tests/acceptance/done:** Segment normalization and unknown exposure labels, personal heatmap offline fallback, no fabricated traffic coverage; route-aware ETA tested only with authorized route feed.
- **Security/privacy and performance/offline:** Local aggregation by default, no trip disclosure; bounded tile cache and licensed basemap; fail closed without route.
- **Must not change:** OSM tile terms, precise-route privacy, India map compatibility.
- **Likely blockers:** RS, traffic/exposure data and basemap licence.

### Phase 8 — Static hazard and speed-camera infrastructure

- **Objective/why:** Add only reviewed, legal, clearly incomplete published POIs before considering crowd radar.
- **Prerequisites/dependencies:** D2 source/licence and legal review; Phase 4 warning policy and Phase 6 pack mechanism.
- **Tasks and areas/reuse:** POI-001 and POI-ALERT-001; new pack family/validator, state_packs cache, distinct warning kind.
- **Tests/acceptance/done:** Source receipts, expiry, direction/speed-limit ambiguity, disclaimer and offline pack validation; no warning for stale/unreviewed POIs.
- **Security/privacy and performance/offline:** No user camera/track upload; no claim of 100% coverage; throttle and driving-safe audio; bounded cache.
- **Must not change:** Pothole score semantics, existing pack integrity/CSP controls.
- **Likely blockers:** No reviewed Uzbekistan dataset and unsettled legality of enforcement alerts.

### Phase 9 — Optional production backend foundation

- **Objective/why:** Enable shared reports only if D3 opts in and the local-first product cannot meet the chosen community goal alone.
- **Prerequisites/dependencies:** D3 scope/provider/data-controller decision, D0 practical detection path, Phase 1 contracts, privacy/legal review.
- **Tasks and areas/reuse:** BACKEND-001 and BACKEND-002; new isolated service/API, private media, roles, validation and audit. Reuse local report schema and shared matcher fixtures, not WebView privilege.
- **Tests/acceptance/done:** Threat model, authenticated object authorization, bounded scoped uploads, deletion/retention, quotas, moderation and audit with adversarial tests.
- **Security/privacy and performance/offline:** Separate public defect points from private trips/identity; local operation continues offline; remote sync is optional/idempotent.
- **Must not change:** Local report ownership or credential broker; no hard-coded provider/key or automatic user-data upload.
- **Likely blockers:** D3, provider/hosting choice, legal documents and operating budget.

### Phase 10 — Optional community sync and canonical observation model

- **Objective/why:** Reconcile independent reporters without conflating their private observations with one public physical hazard.
- **Prerequisites/dependencies:** Phase 9 backend, Phases 1/3 matching and scoring; explicit consent/privacy terms.
- **Tasks and areas/reuse:** SYNC-001, DEDUPE-SERVER-001 and COMMUNITY-001; existing outbox keys/ack, report/repair records, fixtures and map display.
- **Tests/acceptance/done:** Idempotent retry/conflict fixtures, server canonical IDs, moderation of disputed repair, public heatmap containing only approved defect locations.
- **Security/privacy and performance/offline:** Role/object checks, private media, opt-in sync, no trip/track default upload; bounded queue and offline-first app.
- **Must not change:** Local manual non-merge or fixed recurrence without a reviewed contract migration.
- **Likely blockers:** Backend choice, consent, abuse controls and representative field evidence.

### Phase 11 — Uzbekistan localization and safe speech

- **Objective/why:** Make the app understandable in Uzbekistan and allow optional audible warnings without requiring driver interaction.
- **Prerequisites/dependencies:** Reviewed Uzbek/Russian product wording; Phase 4 warning policy for TTS; D2 authority terminology for handoff text.
- **Tasks and areas/reuse:** L10N-001 and TTS-001; I18N in index.html, privacy/notice pages, Android strings, warning notifier.
- **Tests/acceptance/done:** Human-reviewed translations, RTL/font/layout/accessibility checks as applicable, CSP/mirror tests, offline voice fallback and device sound/interruption checks.
- **Security/privacy and performance/offline:** No cloud TTS assumed; no spoken private detail by default; bounded announcements and mute.
- **Must not change:** Existing languages, CSP hashes without regeneration, quiet/safety behavior.
- **Likely blockers:** Translation reviewers, local voice availability and device.

### Phase 12 — Optional trust, reputation and abuse controls

- **Objective/why:** Prevent gaming if community contributions/rankings are approved.
- **Prerequisites/dependencies:** Phases 9–10, human ranking policy, moderation/appeal rules.
- **Tasks and areas/reuse:** TRUST-001 and ABUSE-001; server observation history, verified distinct confirmations, quotas and moderation.
- **Tests/acceptance/done:** Same-drive repeat earns zero, speed/distance/time never score, adversarial fake GPS/media and appeal/deletion tests, explainable score.
- **Security/privacy and performance/offline:** No home/work or identity leakage; server verifies, client does not award authority; bounded operations.
- **Must not change:** Private trip statistics or local detector results into unquestioned public truth.
- **Likely blockers:** D3, policy legitimacy, moderation staffing.

### Phase 13 — Optional government/operations dashboard

- **Objective/why:** Provide controlled operational views only after a real authorized partner and backend exist.
- **Prerequisites/dependencies:** Phases 9–10, written partner authorization/data schedule and role model.
- **Tasks and areas/reuse:** GOV-001; separate application using backend API and audit, inspired by BMC_PILOT.md as a process precedent only.
- **Tests/acceptance/done:** Role/object authorization, export redaction, audit log and partner-approved pilot metrics verified end to end.
- **Security/privacy and performance/offline:** No private track in civic dashboard; least privilege, retention/deletion and monitored access.
- **Must not change:** Citizen WebView bundle into an admin surface or imply government endorsement.
- **Likely blockers:** No Uzbekistan partner, agreement, backend or approved data policy.

### Phase 14 — Production hardening and release

- **Objective/why:** Ship only the chosen, validated scope with reproducible artifacts and honest limits.
- **Prerequisites/dependencies:** Phase 0 gates, relevant implemented phases, owner decisions, legal/privacy approval and device evidence.
- **Tasks and areas/reuse:** PROD-001 and PROD-002; build-play-release.sh, NEW-001/002 checks, app/store/privacy docs and rollout monitoring.
- **Tests/acceptance/done:** Locked generated inputs and reviewed dependencies, signed APK/AAB and packaged-asset checks, security regression, device/offline/performance test matrix, controlled pilot and rollback plan.
- **Security/privacy and performance/offline:** Minimize user data, prove deletion, protect signing, no unapproved paid provider or unsupported coverage claim.
- **Must not change:** Source provenance, release gates, full-frame invariant or consent merely to meet a date.
- **Likely blockers:** Signing material, NEW-002 full provenance, device/emulator, legal approvals and partner decision.

## 7. Detailed executable task registry

**Status vocabulary:** ACTIVE = the one next task; CONDITIONAL = do only when its branch occurs; PLANNED = documented but not started; BLOCKED = prerequisites unavailable; DEFERRED = requires an optional product choice. A source-level implementation cannot be marked complete without its tests, and a release/device gate cannot be marked complete by static tests. The task order below is the normal sequence; branch and decision gates override simple numbering.

### BUILD-DEBUG-001

- **Title:** Run one actual offline debug build after AAPT2 provisioning.
- **Phase:** 0. **Priority:** P0. **Status:** COMPLETE (2026-09-29; offline build succeeded, log `.gradle/codex-build-debug-001-20260929.log`, debug APK `app/build/outputs/apk/debug/app-debug.apk`, 13,761,302 bytes).
- **Dependencies:** Exact AAPT2 Windows classifier cached and offline-resolved; this is confirmed in NEW-002 §24. Existing D: JDK/SDK/Gradle homes and process-local Java socket setting.
- **Repository areas:** android-app/android and ignored build outputs. **Existing code to reuse:** COMMANDS.md debug sequence and generated assets already copied in the prior build checkpoint.
- **Implementation steps:** Check the current tree/status; set JAVA_HOME, ANDROID_HOME, ANDROID_SDK_ROOT, GRADLE_USER_HOME, ANDROID_USER_HOME on D: and JDK_JAVA_OPTIONS to the project-local D: .gradle socket directory. From android-app/android run the documented gradlew.bat --no-daemon --offline :app:assembleDebug exactly once; capture complete log and exit status. Do not repeat dry-run or the earlier dependency audit.
- **Tests:** The build itself; no release or device test in this task.
- **Acceptance criteria:** Build succeeds and task output identifies app-debug.apk, or the first/root failed task and cause are captured exactly.
- **Security/privacy constraints:** No credentials, paid call, global setting or source change unless a proven root cause later requires a separate scoped task.
- **Documentation updates:** PROJECT_STATUS, NEXT_STEPS, AGENT_WORKLOG; security evidence only if a security status actually changes.
- **Stop conditions:** Stop on first root failure or after successful build; no same-command retry, release or product implementation.
- **Next task:** BUILD-ROOT-001 on failure; BUILD-APK-001 on success.

### BUILD-ROOT-001

- **Title:** Resolve the first concrete new debug-build root failure.
- **Phase:** 0. **Priority:** P0 conditional. **Status:** CONDITIONAL.
- **Dependencies:** BUILD-DEBUG-001 failed with a new specific root cause.
- **Repository areas:** Only the failing configuration/task and its documented environment or source file. **Existing code to reuse:** prior AAPT2 targeted-provisioning pattern and existing tests when applicable.
- **Implementation steps:** Classify environment, exact missing artifact, or actual project diagnostic; gather one decisive reproduction/trace; make the smallest evidence-backed change in a separately scoped task. For a missing artifact, use configured authoritative repository and published integrity evidence. Never treat generic non-resolvable implementation entries as proof.
- **Tests:** Narrow failing task/configuration check, then one new build attempt in a later BUILD-DEBUG-001 checkpoint.
- **Acceptance criteria:** Root cause documented and targeted correction independently verified; no speculative broad upgrade.
- **Security/privacy constraints:** Preserve dependency provenance and all remediation; no secrets or global security changes.
- **Documentation updates:** Worklog, status, exact next build checkpoint; NEW-002 only if its evidence changes.
- **Stop conditions:** A second identical failure without a concrete change, uncertain provenance, or need for source/architecture decision.
- **Next task:** Return to BUILD-DEBUG-001 for one new actual attempt after the proven correction.

### BUILD-APK-001

- **Title:** Validate the newly generated debug APK.
- **Phase:** 0. **Priority:** P0. **Status:** COMPLETE (2026-09-29; debug APK ZIP, metadata, signature and packaged assets verified; SHA-256 recorded in PROJECT_STATUS).
- **Dependencies:** BUILD-DEBUG-001 successful.
- **Repository areas:** android-app/android/app/build/outputs/apk/debug and documented validators. **Existing code to reuse:** COMMANDS.md artifact-location check and release-asset verifier where applicable to debug assets.
- **Implementation steps:** Record exact path, length, timestamp and file hash; confirm nonempty APK; run only documented APK/packaged-asset checks that apply to debug; distinguish debug signing from upload signing.
- **Tests:** Artifact inspection and documented validator outputs.
- **Acceptance criteria:** Nonempty APK matches the current build and checks pass; any unverified check is named.
- **Security/privacy constraints:** Do not publish, sign with a release key or infer device correctness from file existence.
- **Documentation updates:** Project status, worklog and next task.
- **Stop conditions:** Missing/stale artifact or validation failure; do not rename an older APK as new.
- **Next task:** NEW002-PROV-001 and then RELEASE-001 when its gates are met.

### NEW002-PROV-001

- **Title:** Establish reviewed Gradle dependency provenance for release.
- **Phase:** 0. **Priority:** P0 release gate. **Status:** ACTIVE as the next task; NEW-002 is PARTIALLY RESOLVED.
- **2026-09-29 checkpoint:** Distribution pin and named AAPT2, AGP and Room files have publisher SHA-256 comparisons, but the full release graph, Maven Central modules and task-time artifacts lack reviewed provenance. `verification-metadata.xml` and lockfiles remain absent. Keep this task ACTIVE/incomplete; see NEW-002 §25.
- **2026-09-29 continued evidence:** An external-module-only inventory resolved 127 release/lint/tool/buildscript configurations, finding 329 distinct artifacts from 328 modules. The [file-level table](NEW002_RELEASE_FILE_PROVENANCE.tsv) records 501/799 cached artifact/metadata files matching configured-repository SHA-256 sidecars; 298 have no sidecar, and 127 of the 145 artifact gaps only have unreviewed `.asc` availability. Release task-time artifacts remain unobserved. Keep ACTIVE/incomplete; see NEW-002 §26.
- **2026-09-29 signer/task-time continuation:** Four AndroidX published-filename corrections have matching Google Maven sidecars. The original 127 `.asc` files expose 44 issuer key IDs; three Apache HttpComponents JARs have valid signatures under Apache's official key, with legacy algorithms, while 124 still lack authenticated key/verification evidence. Fourteen original artifacts lack the checked independent mechanism despite matching current repository HTTPS bytes. A lint-only probe found `:capacitor-app:detachedConfiguration1`; two required IntelliJ JARs remained uncached after Google Maven DNS failure. The current table has 860 cached files (552 sidecar matches) plus two unavailable JARs; four Apache signatures total are publisher-key verified, 126 `.asc` candidates remain unverified, and `bundleRelease`/`assembleRelease` task-time dependencies are unobserved. Keep ACTIVE/incomplete; see NEW-002 §27.
- **2026-09-29 exact lint/key continuation:** The two IntelliJ JARs now resolve through configured Google Maven and match publisher sidecars; `lint-gradle:31.13.0` also matches. Apache Commons' official `KEYS` authenticated five further JAR signatures, and Kotlin's official primary fingerprint plus verified subkey binding authenticated 53 Kotlin JAR signatures. The table now covers 863 cached files (554 sidecar matches) and two unavailable lint-unit-test JARs. Of cached artifact sidecar gaps, 62 signatures are authenticated/valid, 68 remain unverified, and 14 have no checked independent mechanism; 165 metadata files also lack sidecars. Offline lint stopped on Mockito, with a lenient classpath check additionally finding uncached org.json. A packaging-task dry run stopped at the existing missing signing-values guard before graph creation. Keep ACTIVE/incomplete; see NEW-002 §28.
- **Dependencies:** BUILD-APK-001 and complete knowledge of actual task-time dependencies; legitimate authoritative publisher/repository evidence.
- **Repository areas:** android-app/android/gradle, D: Gradle home and NEW-002 report. **Existing code to reuse:** wrapper distribution hash, npm lock/preflight, Google AAPT2 sidecar evidence and Gradle-supported verification mechanism.
- **Implementation steps:** Inventory the release/debug resolved graph including task-time artifacts; independently compare published hashes/signatures where available; review any Gradle-generated verification metadata before accepting it; record gaps rather than blessing cached bytes. Keep dependency versions unchanged unless a specific task proves otherwise.
- **Tests:** Gradle dependency verification in the intended offline/online modes, and generated-input preflight.
- **Acceptance criteria:** Reviewed metadata or equivalent traceable evidence covers the graph needed by release, with named exceptions and no fabricated hashes.
- **Security/privacy constraints:** No random mirror, untrusted cache import, secret in metadata or broad dependency change.
- **Documentation updates:** NEW-002 evidence, SECURITY_STATUS if its status truly changes, project status and worklog.
- **Stop conditions:** Publisher evidence absent, verification mismatch or review incomplete; leave NEW-002 PARTIALLY RESOLVED.
- **Next task:** RELEASE-001 only when release provenance gate is satisfied or an explicit documented release-scope decision addresses the gap.

### RELEASE-001

- **Title:** Produce one legitimate signed release APK and AAB.
- **Phase:** 0. **Priority:** P0 release gate. **Status:** BLOCKED.
- **Dependencies:** BUILD-APK-001, NEW002-PROV-001, generated-input preflight and legitimate private upload signing material.
- **Repository areas:** tools/build-play-release.sh, android-app/android and ignored signing inputs. **Existing code to reuse:** existing seven-step release script; do not create an alternate signing path.
- **Implementation steps:** Confirm clean inputs and authorized signing context, run the documented release workflow once, capture exact task result and artifact paths without exposing credentials.
- **Tests:** Script preflight, Gradle lint/bundle/assemble as implemented, release-asset validation.
- **Acceptance criteria:** Fresh nonempty release APK/AAB produced by this source tree and no bypassed gate.
- **Security/privacy constraints:** Keep keystore values private; no debug key substitution, secret logging or release of unverified sources.
- **Documentation updates:** Status, worklog, NEW-001/002 only when evidence changes.
- **Stop conditions:** Missing signing/provenance, first root build failure or failed script gate.
- **Next task:** RELEASE-VERIFY-001 on success; a scoped root-failure task on failure.

### RELEASE-VERIFY-001

- **Title:** Verify signed release artifacts and NEW-001 ordering.
- **Phase:** 0. **Priority:** P0 release gate. **Status:** BLOCKED.
- **Dependencies:** RELEASE-001 successful.
- **Repository areas:** release APK/AAB, tools/normalize-aab-signature-order.py, tools/verify-release-assets.py. **Existing code to reuse:** jarsigner/apksigner/Bundletool checks in build-play-release.sh.
- **Implementation steps:** Record exact paths, lengths and hashes; verify packaged assets, AAB metadata order and JarFile/JarInputStream consistency, APK v2+ signer, certificate pin and Bundletool validity as documented.
- **Tests:** Existing NEW-001 contract plus live artifact checks.
- **Acceptance criteria:** All documented checks pass on newly produced artifacts with the expected signer; no signature-order warning is normalized away without verification.
- **Security/privacy constraints:** Do not reveal certificate private material or claim Play acceptance from local checks.
- **Documentation updates:** Status, worklog and NEW-001/002 evidence if applicable.
- **Stop conditions:** Wrong signer, stale artifact, validation failure or absent verifier.
- **Next task:** DEVICE-001.

### DEVICE-001

- **Title:** Complete device or emulator runtime verification of the chosen build.
- **Phase:** 0. **Priority:** P0 release gate. **Status:** BLOCKED; no device/emulator is attached in the recorded checkpoint.
- **Dependencies:** BUILD-APK-001; RELEASE-VERIFY-001 for release-specific tests; supported Android test device/emulator and test data.
- **Repository areas:** androidTest fixtures, camera/media/credential/drive flows and app APK. **Existing code to reuse:** SEC-001–006 and SEC-014 instrumented tests and source-level contracts.
- **Implementation steps:** Confirm an actual target; install the newly built artifact; run Keystore, URI-grant, capture, full-frame, drive/offline/replay, deletion, quota, notification and device-specific performance checks; separately log any unavailable scenario.
- **Tests:** Relevant androidTest, manual device flows and artifact version/signature confirmation.
- **Acceptance criteria:** Recorded device model/OS, APK hash, pass/fail evidence and no unresolved release-critical runtime gap.
- **Security/privacy constraints:** Use synthetic/private test media and credentials; no paid requests or real complaint submission.
- **Documentation updates:** Project/security status, worklog, affected remediation reports.
- **Stop conditions:** No device, incompatible device, first material runtime failure or unsafe test data.
- **Next task:** CORE-001 if the build/device checkpoint is closed, or a documented scoped blocker task; product source work may proceed earlier only by explicit human direction.

### CORE-001

- **Title:** Extract the native road-event matcher without behavior change.
- **Phase:** 1. **Priority:** P1. **Status:** COMPLETE for FUTURE-DEDUP-001 (2026-09-30).
- **Dependencies:** Phase 0 checkpoint closed, or explicit owner authorization for source-only work while release/device remains blocked.
- **Repository areas:** drive/NativeDeduplicationEngine.kt and a small pure matcher file. **Existing code to reuse:** current matchRoadEvent, headingDifference, NativeRepairCandidateMatcher style.
- **Implementation steps:** Move only pure match decisions; pass prior sightings as data; retain DAO reads, transaction and mutex in the engine.
- **Tests:** Existing persistent/native dedupe contracts and new JVM matcher cases.
- **Acceptance criteria:** Identical decisions for replay, manual, GPS, heading, damage, size and fixed recurrence; no schema change.
- **Security/privacy constraints:** No new media or location egress; preserve SEC-002 ownership.
- **Documentation updates:** Status, roadmap task status and worklog.
- **Stop conditions:** Any observed behavior drift without an approved requirement.
- **Next task:** CORE-002.

### CORE-002

- **Title:** Add shared native/web dedupe and outbox parity fixtures.
- **Phase:** 1. **Priority:** P1. **Status:** COMPLETE (2026-09-30): FUTURE-DEDUP-001 shared matcher fixture plus CORE-002 outbox acknowledgement durability regression.
- **Dependencies:** CORE-001.
- **Repository areas:** JVM test resources, tests, static/standalone.js test surface and DriveModePlugin contracts. **Existing code to reuse:** image_enhancement_parity_test.py fixture pattern, roadEventMatch and NativeAcknowledgementCommit.
- **Implementation steps:** Create one versioned JSON corpus, run it in Kotlin and JS, and assert paged sync acknowledgement only after IndexedDB commit.
- **Tests:** Shared matcher JVM/Node fixture; `native_outbox_ack_durability_test.cjs` against the production page loop and IndexedDB helper; existing native pager/acknowledgement JVM tests and web paging/native contracts.
- **Acceptance criteria:** Same fixture outputs in both runtimes, including ambiguous GPS and replay cases.
- **Security/privacy constraints:** Synthetic coordinates/media only; no real trip data in fixtures.
- **Documentation updates:** Status, roadmap and worklog.
- **Stop conditions:** Matcher disagreement or outbox contract ambiguity; resolve before new scoring.
- **Next task:** DETECT-001 after D0, or CONF-001 for derived local scores.

### DETECT-001

- **Title:** Record and validate the free detection path decision.
- **Phase:** 2. **Priority:** P1. **Status:** COMPLETE — decision/acceptance contract recorded 2026-09-30; implementation verification remains REPORT-LOCAL-001.
- **Dependencies:** Human choice of manual-first or reviewed on-device detector; CORE-002; model/data licence and evaluation corpus if on-device.
- **Repository areas:** PRODUCT_DECISIONS.md to be created, eval/, native inference contract and privacy notice. **Existing code to reuse:** NativeInferenceEngine outcome contract and full-frame evaluation tests.
- **Implementation steps:** Record user-approved mode and acceptance targets; compare candidates on whole frames and hard negatives; specify what happens to BYOK/cloud paths and saved replay.
- **Tests:** Full-frame invariant, offline behavior and representative evaluation with measured latency/memory/battery.
- **Acceptance criteria:** One documented implementable path with licence, quality and privacy evidence; no claim that a model exists before integration.
- **Security/privacy constraints:** No paid/provider call without authorization; protect private images and keys.
- **Documentation updates:** Decision record, status, roadmap and worklog.
- **Decision/evidence:** [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md) records the approved private offline manual-first path with optional retained cloud/BYOK and pass/fail targets. CORE-002 is complete. No model is selected, so model/data licensing, hard-negative accuracy and detector latency/memory/battery evaluation are not applicable. Existing deterministic contracts are regression evidence; actual offline workflow verification remains REPORT-LOCAL-001.
- **Stop conditions:** Missing human direction or model licence/quality evidence.
- **Next task:** REPORT-LOCAL-001.

### REPORT-LOCAL-001

- **Title:** Implement the chosen local/free detection and private report path.
- **Phase:** 2. **Priority:** P1. **Status:** PARTIALLY COMPLETE — source/browser implementation verified 2026-09-30; Android camera/offline/device performance evidence remains blocked by the recorded missing device.
- **Dependencies:** DETECT-001 and CORE-002.
- **Repository areas:** NativeInferenceEngine, DriveForegroundService, manual Photo/web report path and evidence storage. **Existing code to reuse:** existing report factory, keyframe replay, bounded image handling and user-confirmed handoff.
- **Implementation steps:** Integrate the chosen path behind current outcome shape; remove/disable cloud/BYOK surfaces only if D0 chose no-cloud production; retain private review and strict acceptance.
- **Tests:** Full-frame regression, negative corpus, native/web report contracts, offline replay, bounded resources and device performance.
- **Acceptance criteria:** Ordinary user can produce/review a local report without paid AI under the chosen mode; no false claim of unattended accuracy.
- **Implementation/evidence:** Photo and first-launch settings require no key. Confirmed manual potholes save privately without geocoding/routing/model calls; review/export uses whole-frame evidence and honest user-reported labels. Optional confirmed cloud analysis creates a separate report and preserves the manual row. Real Chromium tests on packaged and canonical assets cover offline/no-key operation, consent/cancel/invalid input, transaction abort/retry, non-merge, export, restart and Delete All. Full-frame/image/CSP/mirror/outbox/AI-budget regressions pass. No model was added; detector accuracy/licensing/latency targets are inapplicable under D0. Actual native camera, Android restart and device resource/performance checks remain required; no release claim is made.
- **2026-10-01 preparation:** [Device runbook](REPORT_LOCAL_DEVICE_VALIDATION.md), all-pending evidence generator, read-only bounded ADB metric collector, synthetic tool tests and printable camera geometry target are ready. Verified local debug APK packages the baseline product sources; offline incremental builds and artifact checks do not establish clean reproducibility or release provenance. No physical results exist; gate remains OPEN/PENDING and task PARTIALLY COMPLETE.
- **Security/privacy constraints:** Complete frames only, no hidden network call, private media and explicit handoff.
- **Documentation updates:** Status, privacy/README as behavior changes, roadmap and worklog.
- **Stop conditions:** Accuracy, latency, memory or licensing target unmet; preserve existing behavior until approved.
- **Next task:** CONF-001.

### CONF-001

- **Title:** Derive conservative confidence and severity from existing observations.
- **Phase:** 3. **Priority:** P1. **Status:** PLANNED.
- **Dependencies:** CORE-002; DETECT-001 decision for calibration targets.
- **Repository areas:** pure Kotlin hazard policy, small static hazard model, report detail. **Existing code to reuse:** seenCount, distinct drive IDs, GPS accuracy, damage type, size estimate and condition.
- **Implementation steps:** Define bounded, explainable formula and unknown state; implement mirror functions with one shared fixture; do not persist initially.
- **Tests:** Native/JS parity, edge cases, false-merge and manual/fixed regressions.
- **Acceptance criteria:** Deterministic score/label; independent confirmation contributes more than repeated same-drive sighting; visual severity is labeled an estimate.
- **Security/privacy constraints:** No inference of exact physical dimensions, no network or private-route exposure.
- **Documentation updates:** Status, scoring specification, roadmap and worklog.
- **Stop conditions:** Missing calibration evidence or misleading public wording.
- **Next task:** FRESH-001.

### FRESH-001

- **Title:** Add time-based freshness without auto-repair.
- **Phase:** 3. **Priority:** P1. **Status:** PLANNED.
- **Dependencies:** CONF-001.
- **Repository areas:** same pure hazard policies and report/map UI. **Existing code to reuse:** last_seen_at, 30-day dedupe horizon and conditionStatus.
- **Implementation steps:** Define fresh/aging/stale/expired display states; keep matching horizon distinct from freshness; expose unknown timestamps honestly.
- **Tests:** Clock boundary, stale cache, fixed/open/review and native/JS parity fixtures.
- **Acceptance criteria:** Freshness is deterministic and cannot set fixed or conceal uncertainty.
- **Security/privacy constraints:** Local derived computation, no precise trip disclosure.
- **Documentation updates:** Scoring spec, status, roadmap and worklog.
- **Stop conditions:** State transition conflicts with repair rules.
- **Next task:** REPAIR-001 for non-AI confirmation, and WARN-001 for warnings.

### REPAIR-001

- **Title:** Add a reviewed non-AI repair confirmation path.
- **Phase:** 3. **Priority:** P2. **Status:** BLOCKED on D0/owner workflow decision.
- **Dependencies:** DETECT-001, FRESH-001 and human decision on acceptable repair evidence.
- **Repository areas:** NativeRepairStatusEngine, repair observations, web condition route. **Existing code to reuse:** strict after-time ordering, repair_review, sourceEventKey and SEC-010 image bounds.
- **Implementation steps:** Add explicit user/photo confirmation beside existing AI path; retain review state and idempotency; distinguish source and uncertainty.
- **Tests:** repair_status_test.py, native matcher JVM, duplicate/replay and bounded evidence tests.
- **Acceptance criteria:** No pass-without-detection or one weak claim marks fixed; recurrence remains a new event after fixed.
- **Security/privacy constraints:** Private evidence, no automatic official status claim.
- **Documentation updates:** Status, privacy/help wording, roadmap and worklog.
- **Stop conditions:** Workflow/legal authority ambiguity.
- **Next task:** WARN-001 or later COMMUNITY-001 for multi-user review.

### WARN-001

- **Title:** Implement pure local hazard lookahead and throttle policies.
- **Phase:** 4. **Priority:** P1. **Status:** PLANNED.
- **Dependencies:** CONF-001 and FRESH-001; no route feed required for heading-corridor warnings.
- **Repository areas:** new native warning policy and JVM tests. **Existing code to reuse:** speed/heading fix, GPS quality and headingDifference.
- **Implementation steps:** Define conservative speed-based corridor, direction/accuracy/freshness gates and bounded per-hazard throttle; keep side-effect free.
- **Tests:** JVM property/fixture cases for crossing roads, stationary state, uncertain GPS, stale hazards and repeated alerts.
- **Acceptance criteria:** No unsafe or stale target triggers; policy never changes report/repair state.
- **Security/privacy constraints:** No network or driver interaction.
- **Documentation updates:** Warning spec, status, roadmap and worklog.
- **Stop conditions:** High false-alert rate or missing safety thresholds.
- **Next task:** WARN-002.

### WARN-002

- **Title:** Wire offline native warning targets, notification and post-drive feedback.
- **Phase:** 4. **Priority:** P1. **Status:** BLOCKED on WARN-001 and device verification.
- **Dependencies:** WARN-001; Phase 0 device access for completion.
- **Repository areas:** DriveForegroundService, Room warning tables/migration, DriveModePlugin, NotificationHelper and settings UI. **Existing code to reuse:** begin/append/commit repair-target sync, paged outbox and stationary check.
- **Implementation steps:** Add bounded target mirror and alert log, thin service hook, distinct channel/mute, stationary/post-drive feedback; keep WebView background independence.
- **Tests:** Migration/delete-all, bridge commit/ack, unit policy, instrumented notification/drive and offline behavior.
- **Acceptance criteria:** Offline alert from reviewed local target; throttle and user safety hold on device.
- **Security/privacy constraints:** No interaction while moving; no trip upload; bounded battery/storage use.
- **Documentation updates:** Status, privacy/permissions, roadmap and worklog.
- **Stop conditions:** No device, notification regression or distracting behavior.
- **Next task:** POI-001 or later TTS-001.

### WARN-NEG-001

- **Title:** Record carefully qualified negative passes as weak freshness evidence.
- **Phase:** 4. **Priority:** P2. **Status:** BLOCKED on WARN-002.
- **Dependencies:** WARN-002 and a reviewed definition of usable frame/GPS/direction.
- **Repository areas:** native pass log/outbox, web hazard freshness and repair review. **Existing code to reuse:** NativeRepairCandidateMatcher gates, event-sighting idempotency and repair-observation outbox.
- **Implementation steps:** Record only bounded accurate passes without a detection; sync idempotently; reduce freshness conservatively and permit review without setting fixed.
- **Tests:** Usable-frame, heading, GPS uncertainty, duplicate pass, delete-all and native/web parity.
- **Acceptance criteria:** Weak absence evidence never erases a positive sighting or independently marks repair complete.
- **Security/privacy constraints:** Do not retain or share whole private trip history to support the pass count.
- **Documentation updates:** Scoring/repair spec, status, roadmap and worklog.
- **Stop conditions:** Poor detector recall or uncertain pass validity; disable negative evidence rather than treating absence as proof.
- **Next task:** HEALTH-001 or REPAIR-001 as their prerequisites permit.

### TRIP-001

- **Title:** Derive private drive statistics from the existing GPS track.
- **Phase:** 5. **Priority:** P2. **Status:** PLANNED, with persistence blocked on D1.
- **Dependencies:** CORE-002; D1 for retaining/displaying route history beyond current behavior.
- **Repository areas:** new pure static trip-stats module and existing dashboard/drive views. **Existing code to reuse:** trackKm, gps_track shape and getDrives.
- **Implementation steps:** Apply accuracy and jump filters; compute distance, moving time, average moving speed and private max speed; label unavailable/uncertain values.
- **Tests:** Synthetic tracks, timestamp disorder, GPS gaps and browser view tests.
- **Acceptance criteria:** Deterministic bounded private statistics, with no ranking/sharing path.
- **Security/privacy constraints:** No upload, no speed gamification, no new raw-track retention before D1.
- **Documentation updates:** Status, roadmap and worklog.
- **Stop conditions:** D1 unresolved for any data-retaining design.
- **Next task:** TRIP-002.

### TRIP-002

- **Title:** Implement owner-approved route retention, per-drive deletion and history UI.
- **Phase:** 5. **Priority:** P2. **Status:** BLOCKED on D1.
- **Dependencies:** Human retention/opt-out/minimization choice and TRIP-001.
- **Repository areas:** Room sessions migration, IndexedDB drives migration, getDrives/delete paths and history/map UI. **Existing code to reuse:** Delete All, migration tests and Leaflet polyline capability.
- **Implementation steps:** Add only chosen retention setting and derived fields; provide per-drive route deletion, additive migration and route display for retained tracks.
- **Tests:** Migration from real old schema, Delete All/storage enumeration, per-drive deletion, backup exclusion and browser/device flows.
- **Acceptance criteria:** Route can be declined or deleted per policy; private stats remain correct or explicitly unavailable after deletion.
- **Security/privacy constraints:** No public tracks/home-work inference, consent versioning if behavior changes.
- **Documentation updates:** SEC-013, privacy notice, status, roadmap and worklog.
- **Stop conditions:** D1 absent or irreversible data migration not approved.
- **Next task:** MAP-001 for personal route/health display, or Phase 6 source work.

### UZ-SOURCE-001

- **Title:** Review Uzbekistan road and authority source registry.
- **Phase:** 6. **Priority:** P1. **Status:** BLOCKED on D2.
- **Dependencies:** Human-supplied or approved authoritative sources, rights/licensing and local stakeholder review.
- **Repository areas:** proposed data/uz registry, source receipts and docs/SOURCES.md. **Existing code to reuse:** India source receipts, SEC-015 SHA-256 gate and audit §25 requirements.
- **Implementation steps:** For each candidate source, record publisher, URL, licence, retrieval date, immutable digest, coverage and update terms; separately verify complaint intake versus legal ownership.
- **Tests:** Deterministic registry/schema validation and source boundary fixtures; no unapproved bulk fetch.
- **Acceptance criteria:** At least one reviewed pilot region/authority source set with traceable licence and checksums, or explicit blocked status.
- **Security/privacy constraints:** No private user reports in source corpus; do not claim government endorsement.
- **Documentation updates:** Source registry, SOURCES, status, roadmap and worklog.
- **Stop conditions:** Unclear rights, source provenance or authority mapping; ask human/local expert.
- **Next task:** SEG-001 and UZ-HANDOFF-001.

### SEG-001

- **Title:** Build and match reviewed Uzbekistan road-segment packs.
- **Phase:** 6. **Priority:** P1. **Status:** BLOCKED on UZ-SOURCE-001.
- **Dependencies:** Reviewed pilot-region road source and UZ-SOURCE-001.
- **Repository areas:** new builder under tools, manifest/pack validators, static matcher, optional report segment migration. **Existing code to reuse:** build-national-highways.py, matchHighwayTile, state_packs download/cache.
- **Implementation steps:** Define stable segment IDs and source version; build content-addressed tiles; validate geometry, ambiguity, heading and nullable unmatched result; add segment ID only when needed.
- **Tests:** Builder determinism, source pin, released-pack compatibility, matcher ambiguity, cache bounds and migrations/delete-all if schema changes.
- **Acceptance criteria:** Reviewed pilot-region segment pack reproduces from pinned input and matches offline without guessing.
- **Security/privacy constraints:** OSM/government licence attribution; no false road-owner inference.
- **Documentation updates:** SOURCES, pack spec, status, roadmap and worklog.
- **Stop conditions:** Source pin/licence unavailable or matching uncertainty above approved threshold.
- **Next task:** HEALTH-001.

### UZ-HANDOFF-001

- **Title:** Add verified Uzbekistan complaint handoff beside India routing.
- **Phase:** 6. **Priority:** P1. **Status:** BLOCKED on UZ-SOURCE-001.
- **Dependencies:** Reviewed authority/intake registry and tested geographic boundaries.
- **Repository areas:** static route module/facade, review UI and notices. **Existing code to reuse:** routeForIssue, routeOfficerCore and explicit external handoff.
- **Implementation steps:** Add country/coverage gate before India branches; validate exact authority category and destination; require user review and confirmation; fail closed to coordinates/copyable report where unknown.
- **Tests:** Boundary and ambiguous-road fixtures, no India regressions, external-handoff contract and CSP/mirrors.
- **Acceptance criteria:** Pilot-region report offers only sourced valid channels and never auto-files or guesses contractor liability.
- **Security/privacy constraints:** Explain any outbound coordinates; no unofficial recipient or claim of submission before confirmation.
- **Documentation updates:** SOURCES/privacy/help, status, roadmap and worklog.
- **Stop conditions:** Missing authority agreement, contradictory source or unsupported geography.
- **Next task:** HEALTH-001 or L10N-001.

### HEALTH-001

- **Title:** Compute an explainable personal road-segment health score.
- **Phase:** 7. **Priority:** P2. **Status:** BLOCKED on scoring and segments.
- **Dependencies:** CONF-001, FRESH-001 and SEG-001.
- **Repository areas:** pure hazard/segment model and local derived cache. **Existing code to reuse:** existing size/damage estimate, condition state and segment matcher.
- **Implementation steps:** Define bounded hazard weighting and per-km normalization; show unknown exposure separately; keep fixed hazards at zero weight; avoid pretending own drives represent traffic.
- **Tests:** Synthetic segment/hazard fixtures, zero-length/unknown segments, fixed/aged hazards and cache invalidation.
- **Acceptance criteria:** Reproducible score with explanation and data-coverage label; no unsupported safety ranking.
- **Security/privacy constraints:** Local computation, no route exposure.
- **Documentation updates:** Scoring spec, status, roadmap and worklog.
- **Stop conditions:** Missing reviewed segments or misleading score semantics.
- **Next task:** MAP-001.

### MAP-001

- **Title:** Render personal road health and an offline fallback.
- **Phase:** 7. **Priority:** P2. **Status:** BLOCKED on HEALTH-001.
- **Dependencies:** HEALTH-001; D1 if private trip route display is included.
- **Repository areas:** static/index.html, a small map module, Leaflet and scatter fallback. **Existing code to reuse:** drawMap, scatter and contribution_map_test.py.
- **Implementation steps:** Add local segment coloring/aggregated markers, explicit stale/coverage legends and SVG fallback; license any separate offline basemap before adding it.
- **Tests:** Browser map/fallback, CSP hash/mirror, large local dataset performance and privacy inspection.
- **Acceptance criteria:** Same personal health information remains usable without network; no raw route or reporter location is published.
- **Security/privacy constraints:** No bulk caching against an unlicensed tile service or crowd exposure.
- **Documentation updates:** UI/help, status, roadmap and worklog.
- **Stop conditions:** Unsupported basemap terms or unreadable offline fallback.
- **Next task:** ROUTE-001 only after RS; otherwise Phase 8 or localization.

### ROUTE-001

- **Title:** Add route-aware lookahead and ETA only from an approved route source.
- **Phase:** 7. **Priority:** P3. **Status:** BLOCKED on RS.
- **Dependencies:** Human route-source/provider decision, WARN-002 and reviewed segment data.
- **Repository areas:** native warning policy/adapter and navigation integration. **Existing code to reuse:** heading corridor fallback and openMaps handoff.
- **Implementation steps:** Specify route data provenance, permission and freshness; compute route distance/ETA conservatively; retain corridor-only warnings when route unavailable.
- **Tests:** Off-route, reroute, stale feed, offline loss, speed/heading uncertainty and device safety.
- **Acceptance criteria:** No ETA is shown without a valid route; warnings remain useful and safe offline in corridor mode.
- **Security/privacy constraints:** Do not leak complete trip/route to a provider without informed consent and retention terms.
- **Documentation updates:** Product decision, privacy, status, roadmap and worklog.
- **Stop conditions:** RS absent, provider terms unclear or unsafe ETA error.
- **Next task:** PROD-001 when chosen feature set is stable.

### POI-001

- **Title:** Define and build a reviewed static hazard/speed-camera pack.
- **Phase:** 8. **Priority:** P3. **Status:** BLOCKED on D2 legal/source review.
- **Dependencies:** UZ-SOURCE-001 and explicit legal/rights decision for each POI category.
- **Repository areas:** new hazard-POI builder/schema, manifests and state_packs validator. **Existing code to reuse:** road-notice pack builder, verified download/cache and SOURCES receipts.
- **Implementation steps:** Require kind, coordinates, direction, source, observation date, verification state and expiry; reject missing provenance; begin with published/static data only.
- **Tests:** Builder determinism, invalid/stale pack rejection, hashes, direction/expiry and offline cache.
- **Acceptance criteria:** Reviewed pack for a bounded region, or an explicit blocked record if source/legal review fails.
- **Security/privacy constraints:** Mandatory incomplete/outdated disclaimer; no community mobile-radar ingestion.
- **Documentation updates:** SOURCES, legal decision record, status, roadmap and worklog.
- **Stop conditions:** No licensed source or local legal approval.
- **Next task:** POI-ALERT-001.

### POI-ALERT-001

- **Title:** Add conservative native alerts for approved static POIs.
- **Phase:** 8. **Priority:** P3. **Status:** BLOCKED.
- **Dependencies:** POI-001, WARN-002, device testing and category-specific legal approval.
- **Repository areas:** warning-target kind, notifier and settings. **Existing code to reuse:** HazardLookaheadPolicy, throttle and pack sync.
- **Implementation steps:** Match direction/expiry and differentiate POI kinds from potholes; show mandatory uncertainty and mute; keep mobile radar disabled.
- **Tests:** Wrong-direction/stale/no-coverage fixtures, notification device checks and offline pack behavior.
- **Acceptance criteria:** Only approved current POIs alert; no completeness or enforcement-avoidance promise.
- **Security/privacy constraints:** Driving-safe, no route upload, no private location log beyond approved retention.
- **Documentation updates:** Privacy/help, SOURCES, status, roadmap and worklog.
- **Stop conditions:** Legal uncertainty, poor source freshness or unsafe alert frequency.
- **Next task:** TTS-001 if audio is chosen; otherwise PROD-001 for this scope.

### BACKEND-001

- **Title:** Decide and specify an opt-in shared backend boundary.
- **Phase:** 9. **Priority:** P3. **Status:** DEFERRED pending D3.
- **Dependencies:** Human decision to share reports, provider/controller choices, legal/privacy design and D0 detection path.
- **Repository areas:** new backend specification and decision record. **Existing code to reuse:** local report/outbox schema and audit §25 minimum controls.
- **Implementation steps:** Define public hazard/private report/media/identity separation, auth roles, scoped upload, moderation, retention, deletion, threat model and failure/offline modes.
- **Tests:** Contract and abuse-case specification before implementation.
- **Acceptance criteria:** Human-approved API/privacy contract with explicit provider and operating responsibility; no implied automatic sharing.
- **Security/privacy constraints:** No trip sync by default; server never trusts client verdict, role or repair status.
- **Documentation updates:** Product decisions, architecture, privacy, status, roadmap and worklog.
- **Stop conditions:** D3/provider/legal decision absent.
- **Next task:** BACKEND-002.

### BACKEND-002

- **Title:** Implement the minimal authenticated private-media backend.
- **Phase:** 9. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** BACKEND-001 approved.
- **Repository areas:** new isolated service and infrastructure; no existing backend directory. **Existing code to reuse:** report contracts and shared matcher fixtures, not the WebView's local /api/ facade as a remote implementation.
- **Implementation steps:** Implement object/role authorization, scoped short-lived media upload, input limits, private storage, quotas, moderation queue, retention/deletion and audit.
- **Tests:** Adversarial auth/IDOR, file type/size/pixel, quota, deletion, replay and load tests.
- **Acceptance criteria:** A secured staging service satisfies the approved contract before any live user-data sync.
- **Security/privacy constraints:** Secret management, encryption, least privilege and private media; no raw journeys in public tables.
- **Documentation updates:** Deployment/privacy/operations, status, roadmap and worklog.
- **Stop conditions:** Missing production owner, budget, legal basis or vulnerability.
- **Next task:** SYNC-001.

### SYNC-001

- **Title:** Add explicit opt-in, offline-first client synchronization.
- **Phase:** 10. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** BACKEND-002 and approved consent/retention.
- **Repository areas:** client sync module beside handle(), native/web outbox and CSP. **Existing code to reuse:** sourceEventKey, paged sync/ack and transaction-commit-correct IndexedDB op().
- **Implementation steps:** Send only selected approved fields/media, idempotent keys and retries; acknowledge after durable server response; preserve local behavior offline; add explicit opt-in/out and deletion request.
- **Tests:** Offline queue, duplicate/reorder, conflict, account switch, deletion and CSP/privacy flows.
- **Acceptance criteria:** No automatic upload; retries do not duplicate hazards or lose local reports.
- **Security/privacy constraints:** Never upload tracks by default; private evidence and authentication boundaries.
- **Documentation updates:** Privacy/consent, status, roadmap and worklog.
- **Stop conditions:** Server authorization or consent contract mismatch.
- **Next task:** DEDUPE-SERVER-001.

### DEDUPE-SERVER-001

- **Title:** Build a server canonical-hazard model from independent observations.
- **Phase:** 10. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** SYNC-001, CORE-002 and BACKEND-002.
- **Repository areas:** server hazard/observation schema and conformance tests. **Existing code to reuse:** native/web road-event fixtures and manual non-merge/fixed recurrence rules.
- **Implementation steps:** Separate immutable reporter observations from canonical public hazard; add idempotent merge/split, uncertainty, moderation and repair disputes.
- **Tests:** Shared parity fixtures, adversarial GPS/heading, false merge/split and concurrent retry cases.
- **Acceptance criteria:** Canonical ID stable under replay and uncertain reports stay reviewable without conflation.
- **Security/privacy constraints:** Do not expose identity, full media or trip in public record; server validates all claims.
- **Documentation updates:** API/schema, status, roadmap and worklog.
- **Stop conditions:** Unacceptable false merges, privacy leakage or moderation gap.
- **Next task:** COMMUNITY-001.

### COMMUNITY-001

- **Title:** Show moderated community hazard/repair and heatmap views.
- **Phase:** 10. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** DEDUPE-SERVER-001, reviewed publication policy and Phase 7 personal map.
- **Repository areas:** public API read models, client map and moderation UI. **Existing code to reuse:** local map, condition states and scored/fresh hazard model.
- **Implementation steps:** Publish only approved defect positions/aggregate status, delayed/coarsened where required; support disputed repair review; label sparse data and staleness.
- **Tests:** Authorization, re-identification checks, moderation transitions, offline cached view and map load.
- **Acceptance criteria:** Public view contains no private journeys/reporter identity and never claims live completeness.
- **Security/privacy constraints:** Location minimization, private media and appeal/deletion paths.
- **Documentation updates:** Privacy/source coverage, status, roadmap and worklog.
- **Stop conditions:** Insufficient moderation, consent or privacy review.
- **Next task:** TRUST-001 if rankings are chosen, otherwise PROD-001.

### L10N-001

- **Title:** Add reviewed Uzbek and Russian localization.
- **Phase:** 11. **Priority:** P2. **Status:** PLANNED.
- **Dependencies:** Human-reviewed terminology, with UZ-HANDOFF-001 for authority names; can be sourced before backend.
- **Repository areas:** static/index.html I18N, Android strings, notices and mirrors. **Existing code to reuse:** four existing I18N languages and pages/CSP contracts.
- **Implementation steps:** Inventory visible strings, translate and review Uzbek/Russian, keep existing languages, update mirror/CSP hashes and layout.
- **Tests:** String completeness, browser locale/layout, pages_assets_test.py, sec009_csp_contract_test.py and accessibility review.
- **Acceptance criteria:** Reviewed language switch and accurate safety/privacy/handoff wording across supported screens.
- **Security/privacy constraints:** No misleading legal/authority translation or hidden network provider.
- **Documentation updates:** Help/privacy language list, status, roadmap and worklog.
- **Stop conditions:** No qualified translation review for safety-critical text.
- **Next task:** TTS-001 when warnings are ready.

### TTS-001

- **Title:** Add optional offline-capable driving speech.
- **Phase:** 11. **Priority:** P2. **Status:** BLOCKED on warning and device tests.
- **Dependencies:** WARN-002, reviewed language/voice choices and device access.
- **Repository areas:** native warning notifier/settings and Android text-to-speech API. **Existing code to reuse:** warning throttle and notification channel.
- **Implementation steps:** Specify short non-sensitive phrases, voice availability/fallback, mute and interruption policy; speak only after safety gates.
- **Tests:** Device voice/language, focus/interruption, offline fallback, repeat throttle and accessibility.
- **Acceptance criteria:** Understandable optional alerts with no repeated distraction or default speech of private locations.
- **Security/privacy constraints:** No cloud TTS assumed; no provider selection without human choice.
- **Documentation updates:** Privacy/settings/help, status, roadmap and worklog.
- **Stop conditions:** Voice unavailable, unsafe interruption or no device validation.
- **Next task:** PROD-001 for selected release scope.

### TRUST-001

- **Title:** Define and compute server-verified contribution reputation.
- **Phase:** 12. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** BACKEND-002, DEDUPE-SERVER-001, community/ranking decision and moderation policy.
- **Repository areas:** server ledger and optional client display. **Existing code to reuse:** distinct confirmation and repair observation semantics.
- **Implementation steps:** Count only independently validated new defects, confirmations and reviewed repairs; cap daily points; publish explanation and appeals.
- **Tests:** Same-drive repeat, bot farm, collusion, deletion, identity switch and score reproducibility.
- **Acceptance criteria:** Speed, distance and trip duration never contribute; score cannot be granted solely by client claim.
- **Security/privacy constraints:** No public home/work/trip derivation or unreviewed user ranking.
- **Documentation updates:** Policy/privacy, status, roadmap and worklog.
- **Stop conditions:** No moderation/appeal capacity or unclear legitimacy.
- **Next task:** ABUSE-001.

### ABUSE-001

- **Title:** Operate quota, moderation and abuse response for shared observations.
- **Phase:** 12. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** BACKEND-002 and DEDUPE-SERVER-001; TRUST-001 if rankings launch.
- **Repository areas:** server rate limits, review queue and operations. **Existing code to reuse:** validated report schema, event-source idempotency and audit recommendations.
- **Implementation steps:** Apply account/device quotas and anomaly review; define suspension/appeal, disputed repair and media takedown with audit evidence.
- **Tests:** Flood, replay, malicious media, privilege escalation, moderation reversal and incident drill.
- **Acceptance criteria:** Documented abuse metrics/response, bounded service cost and no silent false repair.
- **Security/privacy constraints:** Least privilege, limited retention and access logging.
- **Documentation updates:** Operations/security/privacy, status, roadmap and worklog.
- **Stop conditions:** No staffed operator or unresolved adversarial failures.
- **Next task:** GOV-001 only with an authorized partner; otherwise PROD-001.

### GOV-001

- **Title:** Build a separate authorized operations dashboard.
- **Phase:** 13. **Priority:** P3. **Status:** DEFERRED.
- **Dependencies:** BACKEND-002, COMMUNITY-001, role model and signed partner/data agreement.
- **Repository areas:** separate admin application and API read models. **Existing code to reuse:** moderated canonical hazard/repair data and audit logs; BMC_PILOT.md is process precedent, not Uzbekistan authorization.
- **Implementation steps:** Define partner roles, scoped queues/exports and audit; create separate surface; test revocation and data minimization.
- **Tests:** Role/object authorization, export redaction, audit completeness, partner acceptance and incident drill.
- **Acceptance criteria:** Partner-approved pilot dashboard cannot see unauthorized private trips/media and does not claim official status without source record.
- **Security/privacy constraints:** Never put admin functions inside citizen WebView; no assumed government endorsement.
- **Documentation updates:** Agreements/operations/privacy, status, roadmap and worklog.
- **Stop conditions:** No partner authorization, backend or data schedule.
- **Next task:** PROD-001 for the approved scope.

### PROD-001

- **Title:** Complete scope-specific production security, privacy and release gate.
- **Phase:** 14. **Priority:** P0 before launch. **Status:** BLOCKED.
- **Dependencies:** Phase 0 release/device gates, selected product tasks, approved D0/D1/D2/D3/RS/legal decisions as applicable.
- **Repository areas:** build/release scripts, tests, privacy/SOURCES/store material and selected app/backend code. **Existing code to reuse:** SEC/NEW reports, full-frame/CSP/mirror, generated-input and signature checks.
- **Implementation steps:** Run appropriate static/JVM/browser/device/backend test matrix; establish dependency/data provenance; verify deletion, consent, offline behavior, performance, signing and packaged assets; document unsupported features.
- **Tests:** Relevant existing tests and targeted new regression/device/penetration checks, not blanket claims from tests never run.
- **Acceptance criteria:** Every release-critical gate has a fresh pass or a documented human-approved scope limit; signed artifacts trace to tested source.
- **Security/privacy constraints:** No secrets in repo/log, no paid API or live report submission without authorization; legal review for data/service claims.
- **Documentation updates:** Status/security status/changelog/worklog and release checklist.
- **Stop conditions:** Any unresolved critical gate, unknown signer/source or misleading coverage claim.
- **Next task:** PROD-002.

### PROD-002

- **Title:** Run a controlled private pilot and prepare monitored rollout.
- **Phase:** 14. **Priority:** P0 before public launch. **Status:** BLOCKED.
- **Dependencies:** PROD-001, owner-approved pilot scope, real operators/partners where sharing is involved.
- **Repository areas:** pilot/test plan, feedback and incident/rollback operations. **Existing code to reuse:** privacy/source notices, artifact checks and local report workflow.
- **Implementation steps:** Define synthetic/private pilot data and consent, measure false positives/misses/false merges, battery/network/cost, handoff correctness, deletion and rollback; expand scope only on reviewed evidence.
- **Tests:** Device field scenarios and backend load/abuse tests only for selected scope.
- **Acceptance criteria:** Pilot report records numerator/denominator and known misses, incidents and unsupported roads; go/no-go owner decision documented.
- **Security/privacy constraints:** No surprise public sync, government claim or retained private track; protect participant data.
- **Documentation updates:** Pilot report, status, security status if evidence changes, roadmap and worklog.
- **Stop conditions:** Safety/privacy incident, unapproved scope or no owner decision.
- **Next task:** Human-approved rollout or a concrete remediation task from pilot evidence; no automatic expansion.

## 8. Dependency graph and decision gates

The normal technical spine is:

    BUILD-DEBUG-001
      -> BUILD-APK-001 -> NEW002-PROV-001 -> RELEASE-001 -> RELEASE-VERIFY-001
      -> DEVICE-001 -> CORE-001 -> CORE-002
      -> DETECT-001 [D0] -> REPORT-LOCAL-001
      -> CONF-001 -> FRESH-001 -> WARN-001 -> WARN-002 -> WARN-NEG-001
      -> UZ-SOURCE-001 [D2] -> SEG-001 -> HEALTH-001 -> MAP-001
      -> PROD-001 -> PROD-002

On a build failure, BUILD-ROOT-001 interrupts the first line; it diagnoses/corrects the **new** root cause before one later BUILD-DEBUG-001 attempt. This is an explicit conditional recovery loop, not permission to repeat an unchanged failing command. UZ-HANDOFF-001 follows UZ-SOURCE-001. REPAIR-001 follows DETECT-001 and FRESH-001. TRIP-001/TRIP-002 require D1 for retention changes. ROUTE-001 requires RS plus WARN-002. POI-001/POI-ALERT-001 require D2 legal/source review. L10N-001 may progress after translation review; TTS-001 waits for WARN-002 and device checks.

If D3 chooses shared reports, the optional branch is BACKEND-001 -> BACKEND-002 -> SYNC-001 -> DEDUPE-SERVER-001 -> COMMUNITY-001, then TRUST-001/ABUSE-001 and GOV-001 only if separately selected and authorized. These are **DEFERRED**, not silently part of the local pilot. Completion of one optional branch is not required for a deliberately private-only product, but any public/community claim requires its gates.

**Human decisions:** D0 = free detector strategy and legacy cloud disposition; D1 = SEC-013 track retention/opt-out/deletion; D2 = Uzbekistan sources/rights/authority and enforcement-alert legal review; D3 = whether reports are shared and who operates a backend; RS = route/navigation source; D4 = offline basemap licence/provider; D5 = reputation/ranking and dashboard policy. Record each in a reviewed decision file before a dependent task changes product behavior. “Unknown” is not consent.

## 9. Current active task and first five task sequence

1. **BUILD-DEBUG-001 — COMPLETE:** one real offline debug build succeeded after the AAPT2 fix; see the latest [worklog](AGENT_WORKLOG.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).
2. **BUILD-ROOT-001 — NOT NEEDED:** the successful build reported no new root failure.
3. **BUILD-APK-001 — COMPLETE:** fresh debug APK passed structural, package metadata, debug signing and packaged-asset checks; see [PROJECT_STATUS.md](PROJECT_STATUS.md) and latest [worklog](AGENT_WORKLOG.md).
4. **NEW002-PROV-001 — ACTIVE RELEASE GATE, INCOMPLETE:** [NEW-002 §33](SECURITY_REMEDIATION_NEW002.md) records one further file-specific provenance result: `org.json:json:20250517` POM has a valid publisher-key detached signature. The other 14 no-mechanism artifacts, 68 unauthenticated artifact-signature candidates, 164 remaining metadata provenance gaps and direct Objenesis publisher-key attribution remain open. The existing release-signing guard requires a genuine registered upload keystore plus four private signing values; none are configured in this Windows context. The human security/release owner must supply stronger file-specific publisher evidence or an explicit release-scope disposition and securely provision the genuine registered upload key. Only then inspect `assembleRelease`/`bundleRelease` task-time dependencies and review verification metadata; do not start RELEASE-001 while these gates remain open. NEW-002 remains PARTIALLY RESOLVED.
5. **RELEASE-001 — BLOCKED:** build signed artifacts only with legitimate signing material and prior release gates; then RELEASE-VERIFY-001 and DEVICE-001.

No product source task is active. Do not start a feature merely because a phase is written here.

## 10. Release and checkpoint path

| Checkpoint | Evidence required | Cannot be inferred from |
| --- | --- | --- |
| Debug build | Fresh actual Gradle success, task log, APK path and size | Dependency graph report, dry-run, cached AAPT2 |
| Debug artifact | APK hash and documented packaged-asset checks | Filename or timestamp alone |
| NEW-002 provenance | Reviewed Gradle module checksums/signatures or equivalent trusted evidence plus generated-input preflight | Wrapper SHA-256, npm lock, one AAPT2 sidecar, unreviewed generated metadata |
| Signed release | Legitimate upload signer, fresh APK/AAB and complete build-play-release.sh gates | Debug APK or old published release |
| NEW-001 artifact | AAB metadata order, reader-consistent signature, signer pin, Bundletool; APK apksigner checks | Source-level NEW-001 test alone |
| Device/runtime | Recorded device/emulator/OS, installed artifact hash and actual Keystore/media/Drive/offline/privacy scenarios | JVM/browser/static checks |
| Product pilot | Chosen feature scope, source/legal approvals, measured detection and deletion, owner go/no-go | A successful build or map rendering |

For each checkpoint record exact commands, date/time, host, source HEAD, dirty tree state, log/artifact paths, failure task/root cause, tests and limitations. The D: Gradle cache and process-local Java socket workaround are current-host facts; a new host must verify its own environment. Never silently reuse old artifact evidence after source changes.

## 11. Security, privacy, safety and provenance requirements

- Preserve all recorded SEC-001–016 and NEW-001/002 controls. [SECURITY_STATUS.md](SECURITY_STATUS.md) owns their current dispositions; no SEC-017 exists.
- Enforce complete-frame pothole inputs in live capture, replay, evaluation, training preparation and exported detection evidence. Maintain [full_frame_invariant_test.py](../tests/full_frame_invariant_test.py).
- Keep credentials in the native constrained broker/Keystore design; browser credentials stay session-only. If D0 chooses no cloud production, explicitly review removal/disablement of every BYOK, inference and paid-evaluation path rather than leaving hidden calls.
- Keep report/media/route storage private. Track deletion and retention need D1 before trip product work. Any future shared service separates public hazard coordinates from private reporter identity, media and journeys; never publish full tracks by default.
- Keep bounds on frames, bridge payloads, downloads, SSE/inference, caches and outbox pages; maintain CSP, FileProvider, RTSP refusal, native AI budget and signed artifact checks.
- Source every Uzbekistan road, authority and POI claim. Geometry does not prove maintenance duty. Do not invent checksum pins, accepted complaint channels, enforcement legality or government authorization.
- Driver warnings are optional, conservative and offline-capable, with no interaction while moving. Missing route, poor GPS, stale POI or unknown confidence fails closed. Speed and distance remain private stats, never competitive scores.
- Release requires current source, generated-input preflight, provenance, signing, packaged assets and real device evidence. Do not downgrade NEW-002 from PARTIALLY RESOLVED because one artifact matched a publisher sidecar.

## 12. Testing strategy

Match each change to the narrowest existing harness first. Pure native policy changes use app/src/test JVM tests; JS logic uses Node/Python fixtures; native/web parity uses one JSON corpus; UI uses browser/Playwright when available; Room/IndexedDB changes require migration and delete-all tests; pack changes require builder determinism, source pins, envelope/hash and offline-cache tests; mirror/CSP changes require pages_assets_test.py and sec009_csp_contract_test.py. Full-frame and privacy-consent guards remain universal. Backend tasks add auth/object authorization, media abuse, quota, deletion and load tests. Device-only claims need actual androidTest/manual device evidence. See [roadmap §11](PRODUCT_IMPLEMENTATION_ROADMAP.md) and [FILE_INDEX.md](FILE_INDEX.md) for existing test locations.

Do not run paid/provider evaluation, live complaint submission or public data refresh merely to test a local feature. Do not relax known Windows CRLF/pack or POSIX-pruner failures to make a broad suite green. Record tests not run and why. Documentation-only updates use link/registry checks and git diff --check; they do not need an Android build.

## 13. CODEX CONTINUATION PROTOCOL

1. Read AGENTS.md, then this plan, PROJECT_STATUS.md, SECURITY_STATUS.md when security is relevant, and the latest AGENT_WORKLOG.md entries. Open a cited remediation/source file only for the task at hand.
2. Confirm branch, HEAD, dirty tree and the current host/toolchain. Preserve all uncommitted work. Never assume historical C: paths are current.
3. Find the first incomplete task in §7 whose dependencies and human decisions are satisfied. Use §9's active task first. Conditional and deferred tasks do not become eligible by elapsed time.
4. Work on **only that task**, unless it exposes a concrete prerequisite/root-failure task. Inspect source before editing, reuse existing behavior and tests, and make the smallest safe change.
5. Do not restart completed audits or repeat the known ownership, loopback, generic dependency and missing-device diagnostics. A new build attempt requires the documented changed condition. Preserve the full-frame invariant and security remediations.
6. Run relevant deterministic tests; use actual builds/devices only for their named checkpoints. Never claim a test, device, release, pilot or feature complete without recorded evidence.
7. Update current status/next steps when state changes and append one chronological worklog entry with date/time, agent/tool, task ID, result, files, commands/tests, decisions, blockers and **exact next task**. Keep prior historical entries intact.
8. At a context/time limit or a blocker, write the evidence and exact resume point before stopping. Never silently skip a blocked task; state whether it needs a scoped fix, an external condition or a human decision.
9. Never invent product requirements, provenance or missing source data. Ask the human only at the gates in §14 or when evidence cannot determine essential behavior.
10. Never commit or push without explicit authorization in that request. Never put secrets, private keys, raw private trips or credentials in documentation, logs or commits.

**Standard session-end report:** task ID/status; branch/HEAD/dirty tree; exact work/change; commands and test results; artifact paths/hashes if any; security/privacy/provenance impact; blockers and human decisions; files changed; exact next eligible task. Distinguish observed facts from inference and pending verification.

## 14. WHEN CODEX MUST ASK THE HUMAN

Stop dependent work and ask when: a material product requirement is ambiguous; two authoritative requirements conflict after source precedence is applied; privacy/security policy (especially D0/D1/D3), retention or public visibility needs a product decision; an irreversible data migration is proposed; production credentials or signing material are required; applicable legal/compliance or enforcement-alert rules require qualified review; a destructive action is proposed; a choice changes the product direction; an external provider, route source, basemap or backend operator is unspecified; or feature behavior cannot be determined from repository evidence. Prepare a concrete, reviewable recommendation and continue independent safe work where possible. Do not ask for routine coding details already fixed by architecture and tests.

Human-reserved decisions are D0 free/manual/on-device detection and cloud/BYOK disposition; D1 track retention/opt-out/per-drive deletion; D2 Uzbekistan source rights, real authority/intake ownership and local enforcement-alert legality; D3 whether/how to operate shared reports and which provider/controller; RS routing/navigation integration; D4 licensed offline basemap; D5 rankings/reputation and government/dashboard scope; and production signing, pilot scope and go/no-go. No plan entry constitutes approval for paid calls, data transfer, publication, signing, deployment, commit or push.

## 15. Definition of done

A **task** is done only when its acceptance criteria and relevant tests are recorded, its stop conditions are absent or explicitly resolved, documentation/worklog are updated, and the next task is exact. A **phase** is done only when all required tasks for the chosen product scope are done and the phase-specific privacy, safety, offline, performance and regression gates pass. Conditional/deferred branches are either completed with approval or explicitly excluded from that scope; they are never silently counted as done. A **release** is done only with a fresh validated signed artifact and actual device evidence. A **production feature** is done only when source, tests, data rights, user wording, privacy policy and operating responsibility align. A planning document alone completes none of those.

## 16. Change-management rules

- This plan is the execution index; detailed source evidence stays in linked authoritative files. Update one task card/status and its dependency edges when evidence or an approved decision changes, and append the worklog. Do not rewrite historical checkpoint text.
- Keep stable task IDs. If a task splits, preserve its ID as a parent/reference and add a new suffix ID with rationale. Never silently recycle an ID or mark a task complete because a different task passed.
- Source, schema, dependency, signing, CSP, data-pack or backend changes need their own scoped review/tests and explicit human decision where noted. Preserve India compatibility and prior security remediation.
- For competing requirements, name the conflict, apply the source precedence in §2, and ask the human if it changes product direction or privacy. Do not invent a reconciliation.
- Do not treat old release scripts' documentation prose (“not performed”) as a live checkpoint. New actual evidence belongs in PROJECT_STATUS and AGENT_WORKLOG; this plan points to it.

## 17. Historical checkpoint references and continuation command

- [AGENTS.md](../AGENTS.md): mandatory invariants and agent workflow.
- [PROJECT_STATUS.md](PROJECT_STATUS.md), [SECURITY_STATUS.md](SECURITY_STATUS.md), [NEXT_STEPS.md](NEXT_STEPS.md), [AGENT_WORKLOG.md](AGENT_WORKLOG.md): current checkpoint and chronological changes.
- [PRODUCT_IMPLEMENTATION_ROADMAP.md](PRODUCT_IMPLEMENTATION_ROADMAP.md): detailed 2026-09-14 feature proposals and source map, with historical status caveats described in §2.
- [ARCHITECTURE.md](ARCHITECTURE.md), [FILE_INDEX.md](FILE_INDEX.md), [COMMANDS.md](COMMANDS.md), [SETUP_WINDOWS.md](SETUP_WINDOWS.md): current structure, commands and historical setup. Use the D: project-local paths from the latest worklog for this host.
- [NEW-002 report](SECURITY_REMEDIATION_NEW002.md) §§21–24: Windows/Gradle progression, first build failure and exact AAPT2 provenance; [NEW-001 report](SECURITY_REMEDIATION_NEW001.md): AAB signature gate. [Original audit](../outputs/SECURITY_AUDIT.md) §25 gives conditional Uzbekistan backend/privacy recommendations; it is not a live security re-audit.

**Exact read-only start command for a future Windows Codex session:**

    Set-Location -LiteralPath 'D:\Coding projects\pothole-reporter'
    Get-Content -LiteralPath '.\AGENTS.md'
    Get-Content -LiteralPath '.\PROJECT_MASTER\MASTER_EXECUTION_PLAN.md'
    Get-Content -LiteralPath '.\PROJECT_MASTER\PROJECT_STATUS.md'
    Get-Content -LiteralPath '.\PROJECT_MASTER\SECURITY_STATUS.md'
    Get-Content -LiteralPath '.\PROJECT_MASTER\AGENT_WORKLOG.md' -Tail 80
    git status --short
    git branch --show-current
    git rev-parse HEAD

Then continue **NEW002-PROV-001** only within the newly authorized checkpoint scope; BUILD-DEBUG-001 and BUILD-APK-001 are complete. Re-read the latest NEXT_STEPS/worklog first if another session has advanced the checkpoint.
