# Next steps from the preserved tree

## 2026-10-07 next actions after ALERT-002

1. Owner: request the official camera list in the format of [CAMERA_DATA_FORMAT.md](CAMERA_DATA_FORMAT.md) and import it (Settings → Road cameras). For a quick check, make a CSV with 2–3 points on a road you know and drive past them with Antiradar on.
2. Road test: warning distance, direction filtering, voice clarity, over-limit reminder, notification Stop.
3. Next coding task, **TRIP-003**: trip statistics (time, distance, turns, hard braking from the accelerometer), a safe-driving score that rewards keeping the rules, and an Instagram/Telegram share card with trip start/end hidden.

## 2026-10-07 next actions after ALERT-001

1. Owner road test together with SENSOR-001: check that the warnings come at a useful distance and that the voice is understandable.
2. **ALERT-002 antiradar:** define the official camera data format (coordinates, direction, type, limit), add an offline camera pack plus a loader and its validation, and add a camera-free "warnings only" Drive so alerts work without recording. Needs the official Uzbek camera list from the owner; until then, test points only and nothing shipped as real data.
3. Then TRIP-003 (trip stats, safe-driving score, share card), then the server, then routing (see PRODUCT_DECISIONS 2026-10-07).

## 2026-10-07 next actions after SENSOR-001

1. Owner road test (tonight): install the CI debug APK, leave the OpenAI key empty (or Settings → Drive detection → Phone sensor only), mount the phone firmly, drive above ~15 km/h. Note how many real potholes, speed bumps and smooth stretches produced a shock, then open each report and check whether the saved frame shows the spot. Try Medium first, then High/Low.
2. Tune `BumpSensitivity` thresholds and `SensorEvidencePolicy.LEAD_DISTANCE_M` from that drive. Optional: a debug log of shock peaks for tuning.
3. Label the shock frames in Review (Pothole / Not pothole), export, and train the camera model with `ml/train_on_device_detector.py` (ONDEVICE-001). Then ONDEVICE-002 (LiteRT runtime) can combine "shock felt" with "camera model agrees".
4. Unchanged: shared map/backend ("collect everything in one place") does not exist; it needs a server, accounts, moderation and a retention policy, and is a separate decision.

## 2026-10-07 next actions after ONDEVICE-001

1. Human: collect and label frames (Photo, then "Review and label frames"), export them, and run `ml/train_on_device_detector.py inspect`, then `train` (see `ml/README.md`). Several hundred frames per class from many drives, including hard negatives, is a realistic start. Review the licence of the ImageNet base weights and the data.
2. Next coding task, **ONDEVICE-002**: add the LiteRT runtime (one new dependency; record it under NEW-002 provenance), load `assets/models/pothole_detector.{tflite,json}` only when the card passes `OnDeviceModelSpec.parse`, resize each complete frame with `Bitmap.createScaledBitmap(frame, w, h, true)`, score every burst frame, and use `decideBurst`. With no model, or with a refused card, keep today's behaviour.
3. Then **ONDEVICE-003**: let Drive mode start without a cloud key when a runnable on-device model exists; save its accepted frames as reports marked as on-device, size unknown, "not field validated" until a human road test sets `validated_on_real_roads`. Optionally let Drive save frames for labelling without any detector.
4. Unrelated, recorded only: `tests/sec006_ai_budget_contract_test.py` fails on the current `main` as well ("all JS builders/fallbacks and contract match have explicit ceilings"); it is not in `run-all.sh` or CI.

## 2026-10-06 next actions after the Uzbekistan refocus

1. Human: decide how to get the on-device detector trained. It needs labelled Uzbek road frames and a GPU, which the cloud session does not have. The app's "save every analysed frame" option plus dataset export already collects frames labelled by the cloud model.
2. Human: have Uzbek speakers review the O'zbekcha strings; supply a privacy contact address; enable GitHub Pages; decide whether to rename the application ID before any store upload.
3. Run the debug APK on a real phone and exercise Photo, Drive, deduplication, freshness chips, track deletion and Delete-all-data (nothing here has been device-verified).
4. Later: Uzbekistan hazard and speed-camera data from authoritative sources, heatmap, repair confirmation, road-health score, offline-first sync.

## 2026-10-01 TRIP-001 display-only package complete

The authorized independent TRIP-001 private dashboard slice is complete at source/Node/browser level; [TRIP_STATISTICS.md](TRIP_STATISTICS.md) documents its versioned bounds and limits. The exact next trip work package is **TRIP-002**, BLOCKED until the human records D1 retention/opt-out/minimization policy. Obtain D1 before implementation; no route history, new retained fields or defaults are authorized. FRESH-001 independently remains BLOCKED on the [freshness decision](FRESHNESS_DECISION.md). REPORT-LOCAL-001 remains PARTIALLY COMPLETE and DEFERRED/BLOCKED on physical validation. NEW-002 stays separate. Earlier checkpoint sequencing below is historical; this cycle authorized only one independent implementation package.

## 2026-10-01 FRESH-001 decision package

The next future-product action is the human freshness-policy response in [FRESHNESS_DECISION.md](FRESHNESS_DECISION.md): approved fresh/aging age boundaries with rationale, and whether the planned expired state is included with its boundary and behavior. Preparation is complete; FRESH-001 implementation remains BLOCKED and not started. No cutoff is inferred from the one-day/seven-day fixture or 30-day matching horizon. Do not advance to a dependent task. REPORT-LOCAL-001 remains partially complete and DEFERRED/BLOCKED on physical-device validation. D0/CONF-001 and NEW-002/release gates are unchanged.

## 2026-10-01 authorized CONF-001 work package

CONF-001 is complete at source/JVM/browser level; original scoring behavior and relevant regressions pass. Git preservation and validation details are recorded in the worklog.

The human explicitly deferred REPORT-LOCAL-001 physical validation and authorized CONF-001 source work. REPORT-LOCAL-001 remains PARTIALLY COMPLETE, DEFERRED/BLOCKED on a supported physical Android device; preparation and browser/JVM checks do not close it. CONF-001 exposes and displays existing confidence/severity categories without a new formula or freshness policy; see [CONFIDENCE_SEVERITY.md](CONFIDENCE_SEVERITY.md). The next task is FRESH-001, whose user-visible freshness policy/cutoffs require a separate product decision; existing fixture windows remain test parameters. Do not start FRESH-001 here. Earlier instructions barring later tasks are historical and superseded only for the explicitly authorized CONF-001 package. D0, NEW-002 and release gates are unchanged.

## 2026-10-01 device preparation ready — gate still OPEN/PENDING

The exact next task remains **REPORT-LOCAL-001 physical-device validation**. When a supported, authorized Android phone is available, follow [REPORT_LOCAL_DEVICE_VALIDATION.md](REPORT_LOCAL_DEVICE_VALIDATION.md) using the recorded verified debug APK, synthetic geometry target and tested evidence/resource tool. Real camera, offline Android restart, export/media and performance observations are still required. Preparation does not pass any physical acceptance check or permit later product tasks. NEW-002 remains untouched.

## Latest future-product next action — REPORT-LOCAL-001 implementation

REPORT-LOCAL-001 source/browser work is implemented and validated. The exact next future-product action remains **REPORT-LOCAL-001 device verification**: confirm real Android camera capture, offline save/review after app restart, bounded resource behavior and user-initiated export on a supported device. No device was connected or tested in this checkpoint; preserve the recorded blocker rather than retrying it. The task is partially complete overall; do not start CONF-001 or another task. Cloud/BYOK remains optional; source/browser evidence and limits are in PROJECT_STATUS.md and AGENT_WORKLOG.md. NEW-002/release work stays separate. Earlier NOT STARTED entries below are historical.

## Latest future-product next task — 2026-09-30 DETECT-001

D0 is decided and DETECT-001 is complete at decision/acceptance-contract level; see [PRODUCT_DECISIONS.md](PRODUCT_DECISIONS.md). Exact next future-product task: **REPORT-LOCAL-001**, implement and verify manual-first private offline pothole photo reporting while retaining cloud/BYOK as optional. CORE-002 is complete. No primary on-device integration or cloud removal selected. REPORT-LOCAL-001 was not started here; browser/device offline workflow evidence remains required. Earlier D0-pending entries below are historical. NEW002-PROV-001 and release gates remain separate and unchanged.

This is an ordered work queue, not authorization to execute it. This documentation task stops before SEC-008. Preserve the current remediations, full-frame invariant and normal source locations. No commit/push or paid calls are authorized.

1. SEC-008 — handle the recorded xmldom build-tool dependency finding as a separately scoped task; avoid broad dependency upgrades.
2. SEC-009 — add/validate an appropriate CSP for the privileged WebView without breaking its legitimate existing bridges/resources.
3. SEC-010 — address manual image input/decode resource limits while preserving whole-frame evidence.
4. SEC-011 — record the remaining uuid/iOS tooling disposition using the existing Android-not-applicable evidence; do not upgrade unrelated Android dependencies on that basis.
5. SEC-012 — retain the existing applicability closure: KSP is used and KAPT is absent. No Kotlin/KAPT remediation is established as necessary in the current build.
6. SEC-013 — decide and implement GPS/history retention/privacy requirements.
7. SEC-014 — narrow FileProvider sharing roots while retaining valid capture/composer/share workflows.
8. SEC-015 — modernize highway-ingestion provenance checks; do not silently regenerate source data before that scoped work.
9. SEC-016 — remove or safely retire the browser credential-fragment shortcut in its own task.
10. NEW-001 — correct and independently verify strict AAB signature metadata consistency.
11. NEW-002 — establish and verify a clean, locked build bootstrap for generated Capacitor/Cordova inputs and cache provenance.

Then resolve the recorded Windows/Gradle environment blocker once in a dedicated verification task. Do not repeatedly retry it during each source finding. Obtain a supported Android test device/emulator and complete the outstanding SEC-001–SEC-006 Keystore, media/URI grants, network/stream cancellation, inference quota and APK runtime checks. Run the catalog workflow in an explicitly authorized GitHub context to verify SEC-007's Ubuntu browser/runtime, artifacts, token permissions and review-branch behavior. Keep existing validation/security checks active; do not normalize or overwrite current pack files to hide the documented Windows hash failures.

Before production, verify a newly built artifact's signing, packaged web assets and source provenance; do not assume previously published v1.38.0 APK/AAB artifacts include uncommitted changes.

The next product phase must explicitly decide the paid-AI-free/manual/on-device path and whether inherited cloud/BYOK functionality is removed. No paid provider is required by the agreed final design. Use reviewed Uzbekistan authority/road/source data instead of relabeling Indian routing, then validate intended language/intake flows and a local/private pilot. Only if shared reports are chosen should the already documented backend/auth/private-media/moderation/retention recommendations become implementation work. Those features do not exist today.

## Current exact next task after 2026-09-29 checkpoint

Use a Windows build session in which the Gradle Java process can establish its loopback daemon connection. With the existing D: project-local toolchain/cache, resolve dependencies from the configured repositories and establish independently reviewed checksum/signature provenance before relying on an offline release cache; do not derive trusted metadata solely from unverified cached bytes. Then run the documented narrow Android debug build once, followed by the documented signed release workflow with legitimate upload signing material, and verify the produced APK/AAB including NEW-001's AAB ordering/signature gate. Device/runtime checks require a connected supported device or emulator. The current session stopped before dependency resolution with `java.io.IOException: Unable to establish loopback connection`; ADB enumerated zero devices. Do not repeat the same Gradle failure without a concrete environment change. Product implementation is not the next task.

## Current exact next task after loopback diagnosis

Complete NEW-002 dependency provenance for the Android build: use the verified process-local `jdk.net.unixdomain.tmpdir` setting for Gradle, ensure the required artifacts for the resolvable debug/release classpaths are actually fetched into the D: cache, and establish independently reviewed checksums/signatures or equivalent trusted verification metadata. Do not treat the successful `:app:dependencies` report or its newly downloaded cache as independent provenance. After that, run one documented narrow debug build in a separate build checkpoint; the signed release and device checks remain later work. Do not start product implementation.

## Current exact next task after debug artifact-cache check

In a separate build checkpoint, run the documented narrow `:app:assembleDebug` command once with the existing D: JDK/SDK/Gradle homes and process-local `jdk.net.unixdomain.tmpdir` setting. The 46 inspected debug/Kotlin/KSP configurations and 11 buildscript classpaths now resolve offline with 329 distinct external files present; capture any task-time transform/compiler failure exactly rather than retrying it blindly. Independently review Gradle dependency checksums/signatures against trusted publisher or repository evidence before treating the D: cache as provenance-verified or generating authoritative `verification-metadata.xml`; this remains NEW-002 work. Do not start the release/device checkpoint or product implementation as part of the debug build task.

## Current exact next task after first actual offline debug build

The single build failed at `:app:compileDebugNavigationResources` because AGP requested `com.android.tools.build:aapt2:8.13.0-13719691` through `:app:detachedConfiguration2` and no cached version was available offline. In a separate scoped task, provision this exact task-time AAPT2 artifact into the D: Gradle home from the configured repository, checking its origin/integrity without inventing provenance; then make one new offline `:app:assembleDebug` attempt with the process-local Java socket setting and capture its result. Do not repeat the unchanged failing build, run a release build, or start product implementation. Independent Gradle dependency provenance for NEW-002 remains open.

## Current exact next task after AAPT2 provisioning

Run one actual documented offline `:app:assembleDebug` in a separate checkpoint, using the existing D: Gradle home and process-local `jdk.net.unixdomain.tmpdir`. The formerly missing AAPT2 `8.13.0-13719691` Windows JAR and POM are now cached, match Google's published SHA-256 sidecars, and resolve offline. Capture the first new root failure if one appears; do not repeat an identical failing build or make speculative changes. If it succeeds, verify the debug APK using documented artifact checks. Keep the signed release, device verification and unresolved full-graph NEW-002 provenance for later scoped work; do not start product implementation.

## Current exact next task after master execution plan creation

Follow [MASTER_EXECUTION_PLAN.md](MASTER_EXECUTION_PLAN.md) §9: BUILD-DEBUG-001 is the only active task. In a separate execution checkpoint, run one actual documented offline :app:assembleDebug with the existing D: cache and process-local jdk.net.unixdomain.tmpdir after exact AAPT2 provisioning. Capture the first new root failure and take BUILD-ROOT-001 only if needed; on success take BUILD-APK-001 to verify the fresh debug APK. NEW-002 remains PARTIALLY RESOLVED and is a later release provenance gate, not a reason to skip the debug build. This planning task did not run Gradle, implement features, commit or push.

## Current exact next task after BUILD-DEBUG-001

BUILD-DEBUG-001 completed successfully on 2026-09-29 with one actual offline `:app:assembleDebug`. Execute **BUILD-APK-001** only: validate the fresh debug APK at `android-app/android/app/build/outputs/apk/debug/app-debug.apk` using the documented applicable checks, record its hash and results, and stop at that task boundary. The build log is `android-app/android/.gradle/codex-build-debug-001-20260929.log`; basic metadata is in [PROJECT_STATUS.md](PROJECT_STATUS.md). NEW-002 provenance, signed release, device verification and product implementation remain separate later tasks.

## Current exact next task after BUILD-APK-001

BUILD-APK-001 completed on 2026-09-29: the fresh debug APK passed ZIP/manifest inspection, `aapt` package metadata, `apksigner` debug v2 signing, and the existing packaged-asset verifier; its SHA-256 is recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md). Execute **NEW002-PROV-001** only, according to [MASTER_EXECUTION_PLAN.md](MASTER_EXECUTION_PLAN.md): review the complete Gradle dependency graph and establish legitimate independent provenance where possible. Keep NEW-002 PARTIALLY RESOLVED until evidence supports closure. RELEASE-001, device verification and product implementation remain later tasks.

## Current exact next action after partial NEW002-PROV-001 review

Continue **NEW002-PROV-001**; it is incomplete. [NEW-002 §25](SECURITY_REMEDIATION_NEW002.md) records publisher checksum matches for the distribution pin and named Google Maven files, and the remaining gaps. Obtain a reviewed checksum/signing-key basis for the remaining Google/Maven Central modules, including the Kotlin Gradle Plugin, and account for release task-time dependencies under an authorized check. Review any generated Gradle verification metadata against independent evidence before accepting it. If full independent provenance is unavailable, record a human-approved release-scope disposition; do not silently bless the D: cache. Do not start RELEASE-001, device verification or product implementation from this checkpoint.

## Current exact next action after declared-release inventory

Continue **NEW002-PROV-001**. The [file-level evidence](NEW002_RELEASE_FILE_PROVENANCE.tsv) and [NEW-002 §26](SECURITY_REMEDIATION_NEW002.md) identify 298 cached artifact/metadata files with no `.sha256` sidecar at either configured repository; 127 of the 145 artifact gaps have only an unreviewed `.asc` file, and 18 have neither checked mechanism. Establish authenticated signer keys and verify applicable signatures, obtain independent evidence or an explicit human release-scope disposition for the 18 remaining artifacts, and account for task-time release dependencies under an authorized check. Only then review/exercise Gradle verification metadata and reconsider RELEASE-001. Do not start release/device/product work in this checkpoint.

## Current exact next action after signer and lint task-time review

Continue **NEW002-PROV-001**; it is still incomplete. [NEW-002 §27](SECURITY_REMEDIATION_NEW002.md) and the [expanded file table](NEW002_RELEASE_FILE_PROVENANCE.tsv) record four corrected AndroidX sidecar matches, four Apache JARs with official-key-verified historical PGP signatures, 126 other `.asc` candidates without authenticated/verified signer keys, and 14 artifacts with only current HTTPS repository-byte consistency. A lint-only probe found 69 external modules in `:capacitor-app:detachedConfiguration1`, but two required Google Maven IntelliJ JARs remain uncached after a Gradle DNS failure; do not rerun that unchanged failure. Restore reliable configured-repository access and provision/verify those exact JARs, then cover the remaining lint and `bundleRelease`/`assembleRelease` task-time dependencies under a separately authorized safe check. A human security/release owner must explicitly decide any file-specific release-scope acceptance for the 14 no-mechanism artifacts and residual unauthenticated signatures, or require stronger publisher evidence; no acceptance has been granted. Review/exercise Gradle verification metadata only against a complete trusted graph. **RELEASE-001 remains blocked**; do not begin device or product tasks.

## Current exact next action after exact lint JAR and publisher-key review

Continue **NEW002-PROV-001**; see [NEW-002 §28](SECURITY_REMEDIATION_NEW002.md) and the [current file table](NEW002_RELEASE_FILE_PROVENANCE.tsv). The two IntelliJ JARs and `lint-gradle:31.13.0` have matching Google Maven SHA-256 sidecars. Official Apache Commons and Kotlin key evidence raised the authenticated valid signature count to 62, while 68 cached `.asc` candidates and 14 no-mechanism artifacts remain unverified; 165 metadata files also lack sidecars. Provision **only as a new scoped dependency task** and independently verify `org.mockito:mockito-core:5.20.0` and `org.json:json:20250517`, the two exact JARs missing from the lint unit-test classpath; rerun lint only after the cache condition changes. The `assembleRelease`/`bundleRelease` task graph is blocked by the project's missing release-signing values: obtain legitimate authorized signing configuration before inspecting that graph, without inventing values or bypassing the guard. Then cover remaining task-time artifacts, review verification metadata against a complete trusted graph, and obtain an explicit human file-specific security/release decision for unresolved provenance if stronger publisher evidence cannot be established. **RELEASE-001 remains blocked.**

## Current exact next action after Mockito/JSON lint continuation

Continue **NEW002-PROV-001** in a separate scoped checkpoint. The exact Mockito and org.json JARs are cached and independently verified as recorded in [NEW-002 §29](SECURITY_REMEDIATION_NEW002.md). The single changed-cache offline `:app:lintRelease` failed because Mockito requires uncached `net.bytebuddy:byte-buddy:1.17.7` and `net.bytebuddy:byte-buddy-agent:1.17.7`; their published Maven Central SHA-256 sidecars are inventoried but cannot verify absent bytes. Provision and independently verify those two exact JARs from the configured repository, then run one changed-cache offline lint probe and record the first new boundary. Do not repeat the unchanged lint failure. Release packaging task-time inspection requires legitimate human-owned upload keystore and all four release signing values under the existing guard; no non-secret bypass is documented. Residual provenance gaps need stronger evidence or explicit file-specific human security/release disposition before reviewed verification metadata and RELEASE-001. **NEW-002 remains PARTIALLY RESOLVED; RELEASE-001 remains blocked.** Do not start release/device/product work now.

## Current exact next action after Byte Buddy lint continuation

Continue **NEW002-PROV-001** in a new scoped checkpoint. Both Byte Buddy 1.17.7 JARs now match Maven Central publisher SHA-256 sidecars in the D: cache, but one changed-cache offline `:app:lintRelease` stopped at `:app:generateReleaseUnitTestLintModel` because `com.squareup.okhttp3:mockwebserver:4.12.0` JAR is absent from `:app:releaseUnitTestCompileClasspath`. Its POM/module metadata and publisher SHA-256 expectation do not verify missing JAR bytes. Provision and independently verify **only that exact JAR** from the configured repository, then run one changed-cache offline lint probe and stop at the first new boundary. Do not repeat the unchanged failure. The release-signing guard and remaining NEW-002 provenance gaps remain later gates; do not build release artifacts or begin device/product work. See [NEW-002 §30](SECURITY_REMEDIATION_NEW002.md). **NEW-002 remains PARTIALLY RESOLVED; RELEASE-001 remains blocked.**

## Current exact next action after mockwebserver lint continuation

Continue **NEW002-PROV-001** in a new scoped checkpoint. The exact mockwebserver 4.12.0 JAR now matches Maven Central's publisher SHA-256 sidecar, but the single changed-cache offline `:app:lintRelease` stopped at `:capacitor-android:generateReleaseUnitTestLintModel` because `org.objenesis:objenesis:3.3` is unavailable in `:capacitor-android:releaseUnitTestRuntimeClasspath`. Its Maven Central `.sha256` and `.sha512` sidecars returned 404; `.asc` availability alone does not authenticate a signer or verify absent bytes. Provision **only this exact dependency** from the configured repository and establish legitimate independent provenance if possible; otherwise keep it explicitly unverified. After the cache condition changes, make one offline lint probe and stop at its first new boundary. Do not repeat the unchanged failure, change the release-signing guard or start release/device/product work. See [NEW-002 §31](SECURITY_REMEDIATION_NEW002.md). **NEW-002 remains PARTIALLY RESOLVED; RELEASE-001 blocked.**

## Current exact next action after Objenesis lint continuation

Continue **NEW002-PROV-001** only in a separately scoped checkpoint. The exact Objenesis 3.3 JAR is cached and its Maven Central detached signature verifies under a fingerprint Gradle's published verification metadata trusts for `org.objenesis`; direct publisher-key attribution was not established and the signature uses legacy DSA-1024/SHA-1. One changed-cache offline `:app:lintRelease` completed `BUILD SUCCESSFUL`, with no new missing dependency. Next, review residual file-specific provenance gaps and obtain a legitimate human-owned upload keystore and the four required signing values before attempting release packaging task-time dependency inspection. Do not bypass the guard or infer a verified release from lint. See [NEW-002 §32](SECURITY_REMEDIATION_NEW002.md). **NEW-002 remains PARTIALLY RESOLVED; RELEASE-001 remains blocked.**

## Current exact next action after residual provenance and signing-gate review

The JSON-java 20250517 POM now has authenticated publisher-signature evidence, but the table still records 14 artifacts without an independent digest/signature, 68 unauthenticated artifact-signature candidates, 164 other metadata provenance gaps and no direct Objenesis publisher fingerprint. The Windows release-signing guard is **unsatisfied**: no ignored properties file or nonblank `POTHOLE_RELEASE_*` values are present. The next **NEW002-PROV-001** gate is human-owned: provide stronger file-specific publisher evidence or an explicit security/release-scope disposition for residual gaps, and securely provision the existing registered upload keystore/alias/passwords through the documented private route. Do not send secret values to the worklog. Only after both gates are genuinely satisfied, inspect release packaging task-time dependencies and review verification metadata before RELEASE-001. No release task graph, APK/AAB or device test ran in this checkpoint. See [NEW-002 §33](SECURITY_REMEDIATION_NEW002.md). **NEW-002 remains PARTIALLY RESOLVED; RELEASE-001 blocked.**

## Future product development after FUTURE-DEDUP-001

The shared native/web road-event matcher fixture is in `android-app/android/app/src/test/resources/road-event-match-v1.json`; it covers 20 current match decisions. The exact next future product task is **CORE-002 outbox acknowledgement parity**: establish focused regression checks that a native paged report is acknowledged only after its IndexedDB commit, without altering deduplication or taking over the separate NEW002-PROV-001 stream. This task has not started.

## Future product development after FUTURE-OBS-001

The optional native detection diagnostic lifecycle and its tests are complete at source/JVM level; see [FUTURE_OBSERVABILITY.md](FUTURE_OBSERVABILITY.md). The next separately authorized future product task remains **CORE-002 outbox acknowledgement parity**. Browser and device runtime observability were not established by FUTURE-OBS-001.

## Future product development after CORE-002

CORE-002 source/contract regression coverage is complete. The production paged web import awaits durable IndexedDB transaction completion before acknowledging native reports; aborts leave reports retryable, and a failed native acknowledgement leaves committed web records intact for replay. No production outbox change was needed. The exact next future product task is **D0: record the human detection-path choice for DETECT-001** (manual-first or a reviewed on-device detector), including its licence, quality and privacy targets. Do not start DETECT-001 implementation without that decision. NEW002-PROV-001 remains a separate security/release stream.

## Future product development after FUTURE-SCORING-001

The categorical native/web scoring foundation and 18 shared vectors are in place; see [FUTURE_SCORING.md](FUTURE_SCORING.md). A product owner still needs to choose freshness cutoffs and whether/how the separate categories enter warnings or road-health summaries. Until then, the explicit window in the fixture is only a test input. The roadmap's D0 detection-path decision for DETECT-001 remains separate and unstarted here. NEW002-PROV-001 is unaffected.
