# Actual file index

Paths below are relative to this master center; every linked target existed when inspected. Expected generated artifact locations are labeled separately in the command guide. No source was moved or duplicated.

## Android / native

| Function | Existing file / directory |
| --- | --- |
| Android application and activity integration | [MainActivity.java](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/MainActivity.java) |
| Manifest / declared components | [AndroidManifest.xml](../android-app/android/app/src/main/AndroidManifest.xml) |
| Drive capture, service, inference, replay | [drive/](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/) |
| Foreground drive service | [DriveForegroundService.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/DriveForegroundService.kt) |
| Capture sources | [NativeFrameSource.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeFrameSource.kt), [NativeRtspFrameSource.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeRtspFrameSource.kt) |
| On-device detector contract (no runtime yet) | [OnDeviceDetectorContract.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/OnDeviceDetectorContract.kt), shared vectors [ondevice-detector-v1.json](../android-app/android/app/src/test/resources/ondevice-detector-v1.json) |
| Inference | [NativeInferenceEngine.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceEngine.kt), [NativeInferenceTransport.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceTransport.kt), [NativeBoundedSseReader.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeBoundedSseReader.kt) |
| Transport policy | [NativeRtspTransportPolicy.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeRtspTransportPolicy.kt) |
| JS/native bridge, evidence ownership and reconciliation | [plugin/](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/), [DriveModePlugin.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt) |
| Room data | [db/](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/db/), [PotholeDatabase.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/db/PotholeDatabase.kt) |
| Credential storage/request gateway | [security/](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/), [NativeSecretStore.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeSecretStore.kt), [NativeCredentialPlugin.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeCredentialPlugin.kt) |
| Native AI quota/accounting | [AiUsageBudget.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/AiUsageBudget.kt), [NativeAiUsageBudget.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeAiUsageBudget.kt), [AndroidAiBudgetAuthenticator.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/AndroidAiBudgetAuthenticator.kt) |
| Owned-media cleanup | [media/](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/), [OwnedMediaCleanup.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/OwnedMediaCleanup.kt), [ManagedMediaPlugin.kt](../android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/ManagedMediaPlugin.kt) |
| Sharing root configuration | [file_paths.xml](../android-app/android/app/src/main/res/xml/file_paths.xml) |

## Web / data / tooling

| Function | Existing file / directory |
| --- | --- |
| On-device detector training (TFLite from labelled app exports) | [ml/](../ml/), [train_on_device_detector.py](../ml/train_on_device_detector.py), [README](../ml/README.md) |
| Canonical web UI and behavior | [static/](../static/), [index.html](../static/index.html), [standalone.js](../static/standalone.js) |
| Android web mirror | [android-app/www/](../android-app/www/) |
| Generated Android packaged assets | [assets/public/](../android-app/android/app/src/main/assets/public/) — generated tree, not canonical web source |
| Hosted app/privacy/source pages and runtime packs | [docs/](../docs/), [privacy.html](../docs/privacy.html), [sources.html](../docs/sources.html), [packs/v1/](../docs/packs/v1/) |
| Small runtime manifests | [pack-manifest-v1.35.json](../static/pack-manifest-v1.35.json), [highway-manifest.json](../static/highway-manifest.json), [contract-manifest-v1.36.json](../static/contract-manifest-v1.36.json), [road-notice-manifest-v1.36.json](../static/road-notice-manifest-v1.36.json), [road-agreement-manifest-v1.36.json](../static/road-agreement-manifest-v1.36.json) |
| Input data / provenance | [data/](../data/), [tenders-national-highways.json](../data/tenders-national-highways.json), [gepnic-road-notices/](../data/gepnic-road-notices/), [custom-road-tenders/](../data/custom-road-tenders/), [pmgsy-road-agreements/](../data/pmgsy-road-agreements/) |
| Source adapters, pack builders and verification | [tools/](../tools/), [build-highway-contract-packs.py](../tools/build-highway-contract-packs.py), [build-gepnic-road-notice-packs.py](../tools/build-gepnic-road-notice-packs.py), [build-pmgsy-road-agreement-packs.py](../tools/build-pmgsy-road-agreement-packs.py), [prune-catalog-packs.py](../tools/prune-catalog-packs.py) |
| Debug / signed build / asset verifier | [build-apk.sh](../tools/build-apk.sh), [build-play-release.sh](../tools/build-play-release.sh), [verify-release-assets.py](../tools/verify-release-assets.py) |
| Test fixtures, Python/browser/JS contracts | [tests/](../tests/), [serve_app.py](../tests/serve_app.py), [run-all.sh](../tests/run-all.sh), [full_frame_invariant_test.py](../tests/full_frame_invariant_test.py), [sec007_workflow_security_test.py](../tests/sec007_workflow_security_test.py) |
| Native JVM tests / device tests | [src/test/](../android-app/android/app/src/test/), [src/androidTest/](../android-app/android/app/src/androidTest/) |
| Evaluation datasets/contracts/harnesses | [eval/](../eval/), [eval README](../eval/README.md) — paid/provider evaluation is not the default run path |
| Architecture record | [architecture/pothole-reporter.archify.json](../architecture/pothole-reporter.archify.json) |
| Store material / release checklist | [store-assets/](../store-assets/) |

## Build and configuration

| Function | Existing file |
| --- | --- |
| Node dependency declarations and exact lock | [package.json](../android-app/package.json), [package-lock.json](../android-app/package-lock.json) |
| Capacitor app identity, webDir and transport scheme | [capacitor.config.json](../android-app/capacitor.config.json) |
| Android app/signing/build options | [app/build.gradle](../android-app/android/app/build.gradle), [proguard-rules.pro](../android-app/android/app/proguard-rules.pro) |
| Plugins / SDK/library declarations | [build.gradle](../android-app/android/build.gradle), [variables.gradle](../android-app/android/variables.gradle) |
| Included native projects | [settings.gradle](../android-app/android/settings.gradle), [capacitor.settings.gradle](../android-app/android/capacitor.settings.gradle) |
| Windows Gradle wrapper and pinned distribution | [gradlew.bat](../android-app/android/gradlew.bat), [gradle-wrapper.properties](../android-app/android/gradle/wrapper/gradle-wrapper.properties), [gradle-wrapper.jar](../android-app/android/gradle/wrapper/gradle-wrapper.jar) |
| Gradle configuration | [gradle.properties](../android-app/android/gradle.properties) — contents not copied here |
| General Python tooling | [requirements.txt](../requirements.txt) |
| Repository invariants / ignored local material | [AGENTS.md](../AGENTS.md), [.gitignore](../.gitignore) |
| GitHub workflow | [refresh-public-road-catalogs.yml](../.github/workflows/refresh-public-road-catalogs.yml) — actual existing name; no `refresh-catalog.yml` file |
| Workflow-only pins / artifact boundary | [catalog-refresh-requirements.txt](../.github/catalog-refresh-requirements.txt), [catalog-transfer.py](../.github/scripts/catalog-transfer.py) |

Security report locations and links are in [SECURITY_STATUS.md](SECURITY_STATUS.md). Private environment/signing material is intentionally not indexed by value or copied. Build configuration describes how to provide it privately; this center contains no keys, certificates, passwords or token values.
