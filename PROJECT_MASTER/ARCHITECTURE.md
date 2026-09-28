# Current architecture

This describes the existing source/remediation state, not a proposed implementation. Sources: [upstream README](../README.md), [architecture record](../architecture/pothole-reporter.archify.json), [file index](FILE_INDEX.md), and [existing security reports](SECURITY_STATUS.md). Inherited architecture pictures/README may predate the remediations below.

## Layers and current data flow

1. Capacitor packages the web app in an Android WebView. `static/` is the canonical web asset set; `android-app/www/` is its Android mirror; generated Android `assets/public/` is what Gradle packages. `docs/` hosts web pages and separately downloaded reference packs. The configured local Android scheme is HTTPS.
2. Android's foreground drive service coordinates phone-camera capture, timestamp/location association, bounded inference and durable replay/evidence. The native plugin exposes the drive/report operations to the JS UI. Media3 RTSP source code remains present, but SEC-003's native policy currently disables dashcam because supported secure RTSPS is unavailable.
3. Manual/photo and report UI logic resides in `static/standalone.js`. Native requests use the credential gateway; native drive inference uses its transport. Cloud detection/repair code is still inherited, not replaced by a free/on-device detector.
4. Reports/evidence are reviewed locally. Reference-pack/GPS matching suggests an intake channel; it does not establish road ownership or contractor liability. Existing research catalogs are optional. The user chooses and completes an external official/email/share/portal handoff; nothing is automatically filed.
5. Offline tools ingest official/public reference sources into `data/`, build content-addressed packs under `docs/packs/v1/`, and maintain small manifest mirrors. The GitHub catalog workflow reads/builds/validates with a read-only token, then sends checked data to a separate publication runner to open a review PR. The workflow does not merge main.

Every detection/evaluation view must preserve the complete edge-to-edge frame. Whole-frame orientation correction/downscale/compression is allowed; cropping, tiling, masks and road-only regions are prohibited by [AGENTS.md](../AGENTS.md).

## Storage boundaries

Native Room classes in `db/` store native records; private/app-specific files hold drive media and evidence. Web report/pack state uses IndexedDB (the source opens the `potholes` database); non-secret preferences still use localStorage. Native credential storage is authenticated encryption backed by Android Keystore. The credential bridge reports availability and performs constrained requests rather than returning plaintext credentials. Browser credentials are session-only.

App-owned cleanup is coordinated by the media plugin/cleanup journal and includes the documented private, cache, app-specific external, camera/composer and managed public-output locations. Existing deletion limitations for already handed-off/shared copies and real URI grants are recorded in SEC-002. GPS/history retention design remains SEC-013; this center does not invent an automatic retention policy.

Native AI usage accounting has a central lifetime reservation gate with encrypted rollback-resistant persistence. SEC-006 records 32 requests / 32,768 reserved output tokens and per-path output caps. It is an installation-local application quota, not an account-wide monetary guarantee. Browser paid inference is disabled.

## Network boundaries

- Native cloud image/inference paths still target OpenAI through constrained native code and require user credentials. No production credentials were provided and no paid calls are authorized. Browser preview does not enable paid inference.
- Reverse geocoding uses OpenStreetMap Nominatim with coordinates; the inherited India-specific routing also has Karnataka/Telangana GIS checks where applicable. These are external services, not this project's backend.
- Runtime reference packs are fetched from the inherited GitHub Pages host using small manifests. Bounded streaming, length/schema/hash checks and cancellation/cleanup precede activation; required invalid routing data fails closed.
- Public-source catalog acquisition is a separate build/maintenance process. It does not upload user reports or create a national incident API.
- Official handoff destinations/email/share recipients are external systems selected and confirmed by the user. App-owned deletion cannot retract completed external handoffs.

## Existing security boundaries and limitations

SEC-001 isolates credentials; SEC-002 constrains cleanup ownership; SEC-003 refuses insecure camera transport; SEC-004/005 bound downloads and inference; SEC-006 gates paid native requests; SEC-007 separates data processing from repository write credentials. Source-level controls have focused verification recorded in their reports, while device/runtime/build completion remains blocked. The privileged WebView still has the recorded pending CSP finding (SEC-009), image resource limits remain SEC-010, sharing roots remain SEC-014, and browser fragment import remains SEC-016. No new audit conclusion is implied.

The command helper is a documentation utility: it derives the repository path and prints instructions. It does not touch storage, start a server, install tools, invoke inference, regenerate assets, build, sign, or publish.

## Future direction already recorded, not implemented

The existing [audit's Uzbekistan recommendations](../outputs/SECURITY_AUDIT.md) describe a smallest manual/private-evidence flow, reviewed Uzbekistan road/authority data, and an option to disable/remove cloud inference if choosing no-AI/on-device detection. The continuation decision favors a free-to-user production app without required paid AI; no detector removal/replacement was performed.

If reports later become shared, the recorded recommendation is a narrow authenticated backend with scoped uploads, validated/private media, separate public defect positions from private journeys/reporter identity, role/object authorization, quotas, moderation and retention/deletion rules. No such backend/account/API is currently operated or implemented in this repository. No provider, endpoint, payment service or paid dependency is selected here.
