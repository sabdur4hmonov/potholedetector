# SEC-011 dependency disposition

Finding: **SEC-011 — INFO — `uuid@7.0.3` advisory in iOS/Xcode tooling, not Android runtime.**

**STATUS: RESOLVED** — applicability and risk treatment completed; the affected dependency version remains installed. This status does not mean the upstream advisory has been patched or npm audit is clean.

Verified 2026-09-14 in the existing authoritative working tree. Only SEC-011 was investigated. The original INFO classification is preserved.

## Advisory and exact dependency chain

The upstream [GHSA-w5hq-g745-h8pq / CVE-2026-41907 advisory](https://github.com/uuidjs/uuid/security/advisories/GHSA-w5hq-g745-h8pq) concerns missing bounds validation in the `v3()`, `v5()` and `v6()` APIs when callers supply output buffers/offsets. It can silently produce partial or stale identifiers. Upstream rates it Moderate and lists fixes at 11.1.1, 12.0.1 and 13.0.1; that package severity is distinct from this project's INFO applicability finding.

The actual installed tree and root lockfile contain exactly one uuid node:

```text
android-app@1.0.0
└── @capacitor/cli@8.5.0   (root declaration ^8.5.0)
    └── xcode@3.0.1       (CLI declaration ^3.0.1)
        └── uuid@7.0.3    (Xcode declaration ^7.0.3)
```

`npm ls`, `npm explain` and lock inspection agree. No second uuid version or other parent of uuid exists in the actual lock. Installed package versions, the root package lock and the hidden installed-tree lock agree for all three packages, including lock integrity entries. The root manifest's dependency declarations equal the root lock's declarations.

## Actual use and Android relevance

- `node_modules/xcode/lib/pbxProject.js:22` imports uuid. Its sole direct uuid API call is `uuid.v4()` with no arguments at line 90, inside `generateUuid`. It strips hyphens, takes 24 characters and uppercases the result for an Xcode project identifier. It does not call the advisory's affected APIs or supply an external buffer/offset.
- `node_modules/@capacitor/cli/dist/util/xcode.js:5` imports Xcode to edit `project.pbxproj` and register Swift files. Its caller is `dist/tasks/migrate-uiscene.js`, used by the iOS migration branch. These are developer-side Xcode/Swift project operations. Module import into a shared CLI process does not make this Android runtime code.
- `@capacitor/cli` is listed in the npm manifest's `dependencies`, not `devDependencies`. Therefore this tooling can be installed even with npm development dependencies omitted; npm's production/development flags alone cannot establish Android shipping relevance.
- Android `capacitor.settings.gradle` selects native Capacitor/plugin projects, and `app/capacitor.build.gradle` references native app, launcher, camera, filesystem, geolocation, share and email-composer modules. Neither selects CLI, Xcode or npm uuid. `capacitor.config.json` uses `webDir: "www"`; the application does not bundle all of node_modules. Targeted searches of the application web/native sources and packaged public assets found no npm uuid/Xcode import or vendored package path.
- Native application identifiers use `java.util.UUID.randomUUID()` in Kotlin/Java, a separate implementation. They do not use this npm library.
- The existing security verification previously obtained `releaseRuntimeClasspath` and recorded no `uuid`, `xcode` or xmldom in it. That prior result is supporting evidence, not a newly executed Gradle check.

**Android-runtime impact: NO. Production application-code impact: NO. Shipped APK/AAB behavior impact from this npm advisory: NO identified path.** The inspected source/packaging configuration and prior runtime graph support this conclusion. No new build or independent binary inspection was performed, so this is not a fresh attestation of all existing release artifacts.

## Minimal remediation decision

Published npm metadata was checked directly:

| Package query | Result |
| --- | --- |
| Xcode latest stable | `3.0.1`, declaring `uuid ^7.0.3` |
| Xcode versions satisfying the legitimate parent range `^3.0.1` | Stable `3.0.1`, still declaring `uuid ^7.0.3` |
| Installed CLI `8.5.0` | Declares `xcode ^3.0.1` |
| Latest stable CLI | `8.5.2`, still declaring `xcode ^3.0.1` |

There is no stable compatible parent update in this chain that eliminates the advisory. Patched uuid branches require moving beyond Xcode's declared major-version range. A forced override would create an unsupported dependency combination without addressing a demonstrated application call path. A nightly Xcode tag is not a stable compatible remediation; it was not installed or tested. npm audit suggests CLI `8.4.3`, outside the project's declared `^8.5.0` range; a downgrade is not justified for this isolated INFO finding and was not applied. No Capacitor/Cordova or Android runtime dependency was changed.

**No dependency change was made because the advisory is isolated to non-Android iOS/Xcode tooling and changing the dependency would create unnecessary compatibility risk.**

The correct action is to close SEC-011's applicability/disposition work while retaining an explicit record of the deprecated, advisory-matching tooling version. Revisit this treatment when a stable parent supports a patched uuid, when iOS tooling is adopted, or if new code uses affected buffer-taking APIs. This is not a claim that every future consumer of uuid is unaffected.

## Focused checks and results

| Check executed | Result |
| --- | --- |
| `npm ls uuid`; `npm ls uuid xcode @capacitor/cli --json` | Passed, exit 0; exactly the chain above. |
| `npm explain uuid` and JSON form | Passed, exit 0; sole parent Xcode, declared ranges confirmed. |
| `npm audit --json --ignore-scripts` | Completed successfully as an advisory lookup; exit 1 because the advisory remains. Three Moderate nodes (`uuid`, `xcode`, CLI) represent this propagated chain, not three newly identified independent exploits. No audit fix was run. |
| Upstream advisory and targeted `npm view` queries | Confirmed advisory conditions/fixed lines and stable parent versions/ranges. |
| `npm ci --dry-run --ignore-scripts --audit=false --fund=false` | Passed, exit 0, up to date. No install scripts or actual clean install performed. |
| Focused Node assertions | Passed: root manifest/lock declarations, sole uuid parent/node, installed/root/hidden lock versions and integrity entries. |
| Actual Xcode `generateUuid` smoke check | Passed: 100 distinct identifiers matching 24 uppercase hexadecimal characters; source check confirms only zero-argument `v4()` use. No Xcode project file was written. |
| Targeted source/asset/Gradle-configuration inspection | Confirmed tooling versus Android packaging separation described above. |
| File-hash preservation and scoped whitespace check | Passed; application, manifests, both npm locks, installed hidden lock and all earlier remediation files preserved. Only the authorized documentation changes differ. |

Initial registry queries encountered a Windows permission error writing npm's default cache. They were rerun successfully with the cache redirected to this task's writable `work/sec011/npm-cache`; no wider filesystem permission or npm upgrade was needed. A PowerShell wildcard path in an initial search was replaced with the explicit configuration filename. Neither error is presented as a passing check.

## Files changed

Only three repository documentation files changed:

1. `SECURITY_REMEDIATION_SEC011.md`: this report.
2. `PROJECT_MASTER/SECURITY_STATUS.md`: SEC-011 INFO/tooling disposition and report link.
3. `PROJECT_MASTER/PROJECT_STATUS.md`: completed SEC-011 disposition and remaining-work wording.

A matching user-facing report copy and intermediate verification evidence are stored in the current task's outputs/work directories. No application code, manifest, dependency lockfile or Android generated/native asset was changed. No new repository test was needed for this documentation-only disposition; focused checks ran against the actual installed packages.

## Residual risk and limits

uuid 7.0.3 remains deprecated and matches the advisory. Audit will continue reporting its propagated tooling nodes. A future tooling consumer using the affected APIs with invalid buffers/offsets could encounter malformed identifiers; this treatment applies to the inspected Xcode call and current application configuration. No general safety guarantee for all dependency APIs is made.

SEC-011 has **no independent Android production blocker**. Existing native verification gaps and NEW-001/NEW-002 release blockers remain unchanged. No full Android/release build, Gradle troubleshooting, ADB, emulator/device test, iOS/Xcode build, broad security scan or broad project suite was performed. Dry-run consistency and the smoke check do not replace platform build verification or publisher/supply-chain attestation.

SEC-001–SEC-010 were **not reworked**. Earlier source/dependency/CSP changes were preserved. SEC-012 and later findings were not started. No commit or push occurred.
