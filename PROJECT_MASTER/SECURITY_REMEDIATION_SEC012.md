# SEC-012 — Kotlin cache advisory disposition

Status: **RESOLVED — APPLICABILITY ONLY**

Severity: **INFO for this project**. Verified 2026-09-14. The affected KAPT mechanism is absent from the current configured Android build. Dependencies remain unchanged; this is an applicability conclusion, not a claim that the Kotlin version was patched. The **overall security gate remains FAIL** because the recorded final blockers remain unresolved.

## Exact advisory and affected component

[GHSA-r937-wjx7-w2jp / CVE-2026-53914](https://github.com/advisories/GHSA-r937-wjx7-w2jp), “JetBrains Kotlin: Unsafe Deserialization in Kotlin Build Cache Enables Code Execution,” identifies `org.jetbrains.kotlin:kotlin-gradle-plugin` versions before `2.4.20-Beta1`; the advisory lists that beta as its patched boundary and rates the general vulnerability Moderate.

The vendor's [fix bf51df665b458fda7c3eaf436c4d88dc119d7ec6](https://github.com/JetBrains/kotlin/commit/bf51df665b458fda7c3eaf436c4d88dc119d7ec6) changes `plugins/kapt/kapt-base/src/org/jetbrains/kotlin/kapt/base/incremental/JavaClassCacheManager.kt`. It restricts Java deserialization of KAPT incremental metadata, including `java-cache.bin` and annotation-processing cache data, to allowed classes. This establishes the affected mechanism behind the broad Kotlin package-version match: consuming KAPT incremental-cache metadata. A remote cache service is not a necessary prerequisite; poisoned local metadata also belongs to the threat model.

## Actual dependency/tooling paths

| Current file/configuration | Exact declaration and role |
| --- | --- |
| `android-app/android/build.gradle:12` | Buildscript classpath `org.jetbrains.kotlin:kotlin-gradle-plugin:2.1.0`; a version match to the advisory. |
| `android-app/android/build.gradle:13` | KSP marker `com.google.devtools.ksp:com.google.devtools.ksp.gradle.plugin:2.1.0-1.0.29`. |
| `android-app/android/app/build.gradle:2–3` | Applies `kotlin-android` and `com.google.devtools.ksp`, not KAPT. |
| `android-app/android/app/build.gradle:124` and `variables.gradle:22` | `ksp "androidx.room:room-compiler:$roomVersion"`, with Room `2.6.1`. Room annotation processing runs through KSP. |
| Included camera, filesystem and geolocation module `android/build.gradle` files | Their buildscript classpaths declare Kotlin plugin through `kotlin_version`, with a `2.2.20` fallback. These also match the advisory version family, but apply Kotlin Android without KAPT. |
| `variables.gradle:16`, app runtime dependency and root stdlib alignment | Kotlin stdlib `2.1.0`; runtime standard library is distinct from the affected build-cache implementation. |

The relevant chain is Android Gradle configuration → Kotlin Gradle buildscript plugin → KAPT incremental-cache implementation **only if KAPT is activated**. This project's actual processor path is Android app → KSP plugin → Room compiler. Kotlin Android compilation alone does not establish execution of the KAPT cache reader.

`settings.gradle` includes the app and generated Cordova module and applies `capacitor.settings.gradle`. The latter selects eight native plugin modules: Capacitor Android, app, launcher, camera, filesystem, geolocation, share and email composer. Their actual build files were included in the focused inspection, along with the app's generated Capacitor script, Cordova build/variables scripts, root variables and Gradle properties. No `kapt`, `kotlin-kapt`, `org.jetbrains.kotlin.kapt`, KAPT artifact configuration or `annotationProcessor` configuration was present in those files. The generated Cordova post-build extension list is empty. No other configured Kotlin annotation-processing mechanism was identified beyond KSP.

No repository-defined build-cache service or composite build was found in the inspected configuration. This is supporting context, not the basis for non-applicability: the decisive evidence is KAPT absence. External Gradle init scripts, injected `postBuildExtras`, user/CI cache configuration and custom publishing environments were not attested.

## Applicability and runtime/release impact

**Applicability: NOT APPLICABLE to the current configured build. Android-runtime impact: NO identified path.** The required KAPT processing/cache mechanism is absent. The advisory is about build-time deserialization, not Android app runtime deserialization. The shipped Kotlin stdlib version does not make this build-cache issue an APK runtime vulnerability.

If an affected KAPT build consumed poisoned metadata, build-process compromise could affect release outputs; that is a build-integrity consequence, not a direct runtime vulnerability in Kotlin stdlib. No such configured path was established here. No fresh APK/AAB inspection or effective Gradle plugin/task resolution was performed. The previously recorded Kotlin runtime resolution of `2.1.0` remains supporting historical evidence, not a fresh verification of plugin classloader versions.

## Decision and changes

No Kotlin, Gradle, AGP, KSP, Capacitor, Cordova or other dependency was upgraded. No overrides or resolutions were added. A beta adoption or toolchain migration is unnecessary for an absent feature and would introduce compatibility work outside this disposition. The existing architecture and all previous fixes were preserved.

Only these repository documents changed:

1. `PROJECT_MASTER/SECURITY_REMEDIATION_SEC012.md`: this report.
2. `PROJECT_MASTER/SECURITY_STATUS.md`: refreshed SEC-012 applicability evidence and added its report link.
3. `PROJECT_MASTER/PROJECT_STATUS.md`: recorded SEC-012 verification and preserved the overall FAIL gate.

A matching report copy is provided in the current task's outputs. The deterministic verification script, file inventory and preservation evidence are intermediate files in `work/sec012`, outside the repository.

## Focused checks and results

Read the three project-control documents and the existing SEC-012 audit/verification sections first. Checked the current upstream advisory and vendor fix, then inspected the relevant Android build files and included modules.

The standalone `work/sec012/check_sec012.py --repo <repository>` check completed **9 passing deterministic assertions across 17 configuration files**:

- Root Kotlin/KSP versions, app Kotlin/KSP application and Room's KSP processor/version.
- Separation of Kotlin stdlib runtime configuration from build tooling.
- All eight selected native module build files and the three Kotlin `2.2.20` fallback declarations.
- Absence of KAPT/annotationProcessor/KAPT artifact configuration.
- Absence of repository-defined cache-service/composite-build configuration and empty Cordova post-build extension list.

Source declarations and line references were also inspected directly with targeted searches. Preservation hashes confirmed that only the two authorized status documents differed from the pre-task tree and this report was the only new repository file. Previous remediation/application files, manifests, npm locks and generated assets remained unchanged. Scoped document whitespace/conflict-marker checks passed.

No full Android build, release build, Gradle troubleshooting, ADB/device/emulator test, broad audit or broad test suite was run. Effective Gradle task/plugin resolution was intentionally not claimed; the existing environment limitations were not retried. A new repository regression test was unnecessary for this documentation-only disposition; the focused deterministic check examines the actual configuration.

## Remaining limitations and closure

The version-only advisory match remains. Reassess SEC-012 if KAPT is introduced, build scripts are changed or external configuration enables the affected mechanism. This disposition does not certify cache trust or remove the need for compatible toolchain maintenance later. SEC-012 has no independent current Android production blocker; existing release/build/device blockers remain, and the overall gate stays **FAIL**.

SEC-001–SEC-011 were not re-audited or modified. **SEC-013 and later findings were not touched. No commit or push was performed.**
