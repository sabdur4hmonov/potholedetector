# SEC-015 — MD5 in highway source ingestion

## 1. STATUS

**RESOLVED — SOURCE/STATIC.** Verified 2026-09-14.

Severity is LOW (original classification preserved). The only MD5 integrity decision, the offline download gate, was replaced by a SHA-256-only gate with no MD5 fallback. The gate fails closed: the reviewed 2026-08-20 extract is no longer published and its SHA-256 was never recorded. A highway-data rebuild therefore requires reviewing and pinning a new extract first. Runtime and app behavior are unchanged. The overall security gate remains **FAIL** because of other existing blockers.

## 2. Finding

Audit (`outputs/SECURITY_AUDIT.md` §SEC-015; `outputs/SECURITY_VERIFICATION.md` §SEC-015): `tools/pull-national-highways.sh` verified the downloaded Geofabrik PBF against a pinned MD5 before parsing. MD5 is unsuitable for adversarial provenance. Remediation: pin a reviewed SHA-256/SHA-512, keep HTTPS, and keep immutable source references. The audit noted no independent runtime blocker, with modernization expected before rebuilding production data.

## 3. Applicability

**Applicable, at LOW severity; it is a build-input integrity decision, not a runtime one.** The script is run manually by a maintainer. No workflow, release script or test invokes it; `build-play-release.sh` runs only `build-national-highways.py --check`. It downloaded ~India-sized OSM data over HTTPS (`curl --location`) and authenticated it only by MD5 before `osmium` parsing and tile generation, which then feeds committed, published catalog files.

MD5 elsewhere is not a computed hash but a fixed provenance label (§4). No SHA-256 existed for the source; SHA-256 already protects every derived tile.

## 4. Exact MD5 data flow

| Location | Kind | Purpose |
| --- | --- | --- |
| `tools/pull-national-highways.sh:7,19-27` (HEAD) | **Computed** `md5`/`md5sum` of the downloaded PBF, compared to `SOURCE_MD5` | **Integrity/authentication gate** before parsing: the only security-relevant use |
| `tools/build-national-highways.py:42,275,445,462` | Constant string; written to receipt/manifest; `verify()` compares strings | Provenance label and schema pin; hashes nothing |
| `data/national-highways-source.json:713` | Receipt field `source_md5` | Provenance record; read only by `verify()` |
| `static`, `docs`, `android-app/www`, `android-app/android/app/src/main/assets/public` → `highway-manifest.json:42` | Manifest `source.source_md5` | Provenance label shipped with the catalog |
| Four `standalone.js` mirrors `:4171-4178` | Runtime `validateHighwayManifest`: exact key set plus `source_md5 === "c5e0…d7"` | Fixed schema/label check. Runtime never computes MD5 and has no access to the PBF. The inspected released APK JavaScript (`work/apk-standalone.js:3726-3733`) has the same strict check |
| `tests/national_highway_routing_test.py:44-45` | Playwright equality assertion | Label pin |
| `docs/SOURCES.md:108-109`, `docs/sources.html:107` | Documentation | Provenance text |
| `data/.../in-od-gepnic.json`, Odisha road-notice pack | False positive: `…mD5…` inside a tender URL token | None |

Authoritative input: Geofabrik `asia/india-260820.osm.pbf` (ODbL). Downstream consumers are `osmium tags-filter/export`, then `build-national-highways.py --source`. That produces 101 SHA-256 content-addressed tiles (`docs/packs/v1/highways/<tile>-<sha256>.json`) plus three manifest mirrors and a receipt, and the packaged asset copy is made by the APK copy step. The runtime downloads the manifest by relative URL (bundled in the APK; GitHub Pages for web) and verifies each tile's byte length and `sha256Bytes` before parsing.

SHA-256 already exists in this pipeline: tile build and `validate_pack` (`hashlib.sha256`), runtime `sha256Bytes`, SEC-004 pack manifests, SEC-007 `catalog-transfer.py` and hashed wheel locks, and the Gradle wrapper `distributionSha256Sum`. Git Bash provides `sha256sum`.

## 5. Security impact analysis

- **Integrity verification:** yes, in the pull script only. Nothing else used MD5 for cache identity, deduplication, filenames, content addressing, change detection or catalog selection. Tile identity, filenames and cache keys are SHA-256 or tile IDs.
- **Attacker influence on the hashed input:** only via compromise of the Geofabrik publication or mirror/redirect target, or a TLS/CA compromise. The pinned digest was of Geofabrik's own published file, so substitution needs a **second preimage** of a fixed MD5, which remains infeasible. A collision attack needs the attacker to author both colliding files before the pin is reviewed. That fits a malicious or compromised publisher, not a network attacker.
- **What an accepted malicious source could do:** poison mapped NH geometry, causing incorrect National Highway routing/handoff for users after a maintainer rebuilds and publishes. Tiles would then carry valid SHA-256 digests of poisoned content, so runtime SHA-256 cannot detect it. The damage is bounded by reviewer diffing and by the runtime's conservative matching rules (30 m accuracy, reference/direction ambiguity fails closed). There is no code execution, credential exposure or cross-user data access.
- **Runtime labels:** a `source_md5` collision has no effect because nothing is computed; the runtime compares a constant string.
- **Classification:** security-relevant supply-chain provenance for the offline data build, practical risk LOW (cryptographic best-practice modernization of a real integrity gate). The runtime MD5 appearances are non-security labels.

## 6. Threat model

| Actor | Before | After |
| --- | --- | --- |
| Network MITM | Needs a TLS break plus an MD5 second preimage: not practical | Needs a TLS break plus a SHA-256 second preimage |
| Compromised/malicious publisher preparing colliding files | MD5 collision could pass a pin reviewed on the benign twin | SHA-256 collision infeasible |
| Maintainer rebuilding without review | Script accepted anything matching the old MD5 | Script refuses to download or build until a reviewed 64-hex SHA-256 pin exists |
| Installed app / web user | Unaffected: runtime SHA-256 tiles, fixed label | Unchanged |

## 7. Remediation decision

MD5 gated a security-relevant integrity decision, so it was replaced.

- **Gate:** `pull-national-highways.sh` now authenticates the download only with `SOURCE_SHA256` via `sha256sum` or `shasum -a 256`, both SHA-256. It rejects malformed, uppercase, empty and MD5-length pins, missing files and mismatches. There is no MD5 computation or fallback.
- **Fail-closed pin:** no local copy of the extract exists; a filtered search of `bro`, `%TEMP%` and Downloads found none. On 2026-09-14 `https://download.geofabrik.de/asia/india-260820.osm.pbf` and its `.md5` returned **HTTP 404**, while `asia/india.html` and `india-latest.osm.pbf.md5` returned 200. The reviewed bytes can no longer be hashed, and no SHA-256 was ever recorded. Inventing a digest or silently switching to a different extract (a data change) is not allowed, so `SOURCE_SHA256` is empty. `main` validates the pin **before** any `curl` download.
- **Testable verification:** verification is in sourceable functions, and `main` runs only when executed directly.
- **Not changed (compatibility):** manifest, receipt, runtime and routing-test `source_md5` labels. They describe the provenance of the committed catalog, and the runtime (including released builds) enforces an exact field set and value. Removing or renaming them would break highway routing for no security gain. A future data refresh must update `SOURCE_URL`, pin SHA-256, and change the build-tool constants, receipt/manifest schema and runtime pin together.
- **Documentation:** `docs/SOURCES.md` now labels the MD5 as historical provenance and describes the new rebuild requirement. The hosted `docs/sources.html` is left unchanged; its MD5 text remains accurate.

## 8. Exact files changed

1. `tools/pull-national-highways.sh`: SHA-256-only fail-closed source verification (`require_sha256_pin`, `sha256_of`, `verify_source_digest`, guarded `main`). LF endings, matching the index.
2. `tests/sec015_source_digest_contract_test.py` (new): 17-check regression/contract test.
3. `docs/SOURCES.md`: one paragraph clarifying MD5 as historical label and the SHA-256 rebuild requirement.
4. `PROJECT_MASTER/SECURITY_REMEDIATION_SEC015.md` (new): this report.
5. `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md` and `PROJECT_MASTER/CHANGELOG.md`: SEC-015 status.

Evidence outside the repository is in `work/sec015/`: `pre_hashes.tsv`, `sec015_contract.out.txt`, `probe.sh`, `mutation_probe.py`, `pull-national-highways.HEAD.sh`.

## 9. Exact files deliberately not changed

`tools/build-national-highways.py`; all four `highway-manifest.json` copies; `data/national-highways-source.json`; the four `standalone.js` and `index.html` mirrors; `docs/sources.html`; `docs/packs/**`; `tests/national_highway_routing_test.py`; `tests/national_highway_pack_test.py`; `.github/**`; `tools/build-play-release.sh`, `tools/build-apk.sh`, `tools/verify-release-assets.py`; Android sources/resources; dependencies/lockfiles; and all SEC-001–014 remediation files, including the pre-existing stale SEC-002 lock digest. SEC-016+ files were not touched.

## 10. Verification/tests and results

| Check | Result |
| --- | --- |
| `python tests/sec015_source_digest_contract_test.py` | **PASS, 17 checks.** No MD5 computation or pin in the pull script. `SOURCE_SHA256` is empty or 64-hex. Order is enforced: pin check, download, SHA-256 verify, osmium, build. Main is guarded; LF line endings. Bash behavior (Git Bash 5.2.37, `/usr/bin/sha256sum`): matching SHA-256 accepted; wrong digest rejected (“SHA-256 mismatch”); the file's own MD5 refused as a pin; uppercase, empty and missing-file cases refused. Direct run with the committed empty pin exits before stub `curl`/`osmium` run (marker absent). Repo-wide scan of tools/tests/eval/.github/static/www/app src/docs found zero MD5 computations. The historical MD5 appears in exactly the 13 allowlisted label files. Builder verifies tiles by SHA-256; runtime label is fixed and tiles are SHA-256-verified. |
| Mutation probe against `git show HEAD:tools/pull-national-highways.sh` | HEAD **REJECTED** (MD5 gate present; no SHA-256 pin); working tree passes. |
| `bash -n tools/pull-national-highways.sh` (Git Bash) | OK. CR bytes: 0; `git ls-files --eol` shows `i/lf w/lf`. |
| `python tests/national_highway_pack_test.py` (`build-national-highways.py --check`) | PASS: committed 101 tiles, receipt and manifests unchanged and valid. |
| `python tests/android_release_optimization_test.py` | PASS: mirror verifier; `SOURCES.md` is a hosted-only doc. |
| `python tests/sec014_fileprovider_contract_test.py` | PASS (25), confirming SEC-014 is preserved. |
| Geofabrik HEAD requests (2026-09-14) | Dated `.pbf` and `.md5` return 404; site index and latest `.md5` return 200. |
| SHA-256 migration | SHA-256 accept/reject behavior verified on a synthetic fixture. No real extract was hashed (unavailable). |
| Before/after hash scope | See §12 and the handoff: only the §8 files differ. Test-generated `__pycache__` bytecode was removed before comparison. |

**Not run:** real download plus `osmium` rebuild (`osmium` absent; source retired); `tests/national_highway_routing_test.py` (requires Playwright and a local server; Playwright is not installed); workflow execution (no workflow uses the script); Gradle/APK/ADB/device. No Android, runtime or device verification is claimed.

## 11. Remaining limitations

- **Rebuild blocked:** highway rebuilds are blocked until a maintainer reviews a new extract, pins its SHA-256, and updates `SOURCE_URL`/date, the build-tool constants, receipt/manifest schema and runtime pins in lockstep. That is a data-refresh task outside SEC-015.
- **Unverifiable original:** the committed catalog's source cannot be independently re-verified with SHA-256, because the original bytes are unavailable. Its provenance rests on the historical MD5 label plus the SHA-256-pinned derived tiles.
- **Source authenticity:** Geofabrik publishes MD5 files but no signatures or SHA-256 files. A new SHA-256 pin establishes post-review integrity, not publisher authenticity.
- **Behavioral test dependency:** it requires bash (Git Bash on Windows, system bash on Linux/CI). Its static assertions are text-based.
- **Existing blocker:** the pre-existing SEC-002 contract lock-digest staleness (SEC-014 report) is unchanged.

## 12. Preservation of SEC-001–014

No credential, media-cleanup, transport, pack-download, inference, budget, workflow, dependency, CSP, image-budget, tooling, GPS-history or FileProvider code or configuration changed. The SEC-014 contract passes 25 checks and the release test passes. SEC-001–014 statuses in `SECURITY_STATUS.md` are unchanged apart from the new SEC-015 row and link. SEC-016, NEW-001 and NEW-002 were not started.

## 13. Current overall security roadmap

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
SEC-016 = NOT STARTED (recorded PENDING — BROWSER ONLY)
NEW-001 = NOT STARTED (release blocker)
NEW-002 = NOT STARTED (release blocker)
Overall gate = FAIL
```

## 14. CODEX HANDOFF / CONTINUATION CHECKPOINT

- **Exact task completed:** SEC-015 only. Traced all MD5 use in highway source ingestion and replaced the MD5 source gate with a fail-closed SHA-256 gate.
- **Final SEC-015 status:** RESOLVED — SOURCE/STATIC (rebuild requires a new reviewed SHA-256 pin).
- **Files/components investigated:** `tools/pull-national-highways.sh`; `tools/build-national-highways.py`; `data/national-highways-source.json`; `static`/`docs`/`android-app/www`/packaged `highway-manifest.json`; `static/standalone.js` (`validateHighwayManifest`, `getHighwayPackManifest`, `downloadPackResource`, `validateHighwayTile`, `PACK_SITE_ROOT`) and mirrors; `work/apk-standalone.js` (released runtime); `tests/national_highway_routing_test.py`, `tests/national_highway_pack_test.py`, `tests/android_release_optimization_test.py`; `tools/build-play-release.sh`, `tools/build-apk.sh`, `tools/verify-release-assets.py`; `.github/workflows/refresh-public-road-catalogs.yml`, `.github/scripts/catalog-transfer.py`; `docs/SOURCES.md`, `docs/sources.html`, `README.md`; audit/verification SEC-015 sections; repository-wide MD5/hash search; local filesystem search for the extract; Geofabrik HEAD availability.
- **Exact MD5 data flow:** §4. Computed MD5 existed only in the pull script (download → MD5 gate → osmium → builder → SHA-256 tiles/manifests/receipt). Everywhere else the historic value is a constant label (builder, receipt, four manifests, four runtime mirrors, routing test, docs).
- **Was MD5 security-sensitive:** yes in the pull script (build-input integrity gate, LOW practical risk); no elsewhere (fixed provenance labels; runtime integrity is SHA-256).
- **Exact remediation:** SHA-256-only `verify_source_digest` with no fallback; strict lowercase 64-hex pin; `SOURCE_SHA256` intentionally empty because the reviewed extract is retired (404) and was never SHA-256-recorded; pin checked before download; sourceable functions; regression contract; `SOURCES.md` note.
- **Exact files changed:** §8 items 1–5.
- **Files deliberately not changed:** §9.
- **Tests/checks and exact results:** SEC-015 contract PASS (17); HEAD mutation REJECTED; `bash -n` OK and LF; national highway pack test PASS; release optimization PASS; SEC-014 contract PASS (25); Geofabrik dated file 404, site 200.
- **Runtime/device/build limitations:** no real extract download, osmium rebuild, Playwright routing test, workflow run, Gradle build, APK inspection or device test. No runtime code changed.
- **Current statuses SEC-001–SEC-015:** §13.
- **Exact next task:** **SEC-016** (browser credential URL-fragment import shortcut).
- **Instructions for the next agent:**
  - Read `PROJECT_MASTER/README.md`, `PROJECT_MASTER/SECURITY_STATUS.md`, `PROJECT_MASTER/PROJECT_STATUS.md`, `PROJECT_MASTER/CHANGELOG.md`, `PROJECT_MASTER/SECURITY_REMEDIATION_SEC014.md`, this report, then the SEC-016 sections of `outputs/SECURITY_AUDIT.md` and `outputs/SECURITY_VERIFICATION.md`.
  - Work only on SEC-016. Do not re-audit SEC-001–015, re-add MD5, put a fabricated pin in `SOURCE_SHA256`, or rename/remove `source_md5` labels without a coordinated data refresh.
  - Keep `tests/sec015_source_digest_contract_test.py` and `tests/sec014_fileprovider_contract_test.py` passing.
  - Do not start NEW-001/NEW-002, upgrade dependencies broadly, fight Gradle/ADB, or commit/push.
- **Repository HEAD/state:** HEAD `f282454e8fb79a529894598b0af9a3d7008fd84c`, unchanged. Working tree = pre-existing uncommitted remediation changes (SEC-001–014) plus §8 files. Git needs `-c safe.directory=...`; global config not changed.
- **No commit/push:** none performed.
