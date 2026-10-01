# REPORT-LOCAL-001 physical-device validation runbook

**Physical-device gate: OPEN/PENDING.** Preparation, APK checks, simulated collector tests and Chromium results are not physical-camera, Android-restart or device-performance evidence. No later product task may start until the recorded REPORT-LOCAL-001 gate is satisfied.

Implementation baseline: `92ccf4aa97c821fe5f0183ef281c2c506392237a`. This runbook adds no product behavior, acceptance thresholds or release/provenance disposition. Use a supported physical Android device with a rear camera, USB debugging and an explicitly authorized ADB connection. An emulator cannot establish physical-camera acceptance. Use a debug test installation with disposable local data; do not clear or uninstall an existing personal installation without permission.

## 2026-10-01 preparation checkpoint

A debug APK is available locally at `android-app/android/app/build/outputs/apk/debug/app-debug.apk`: 14,204,933 bytes, SHA-256 `935e93efac773dc58c5f8a4dd86c44b5aba4088eae04214859c2151ae4b15edf`. Product/native tracked sources are unchanged from the baseline. Existing-toolchain offline incremental `:app:assembleDebug` succeeded in 5m 44s, but artifact inspection found an omitted generated `hazard-model.js`. The documented `cap.cmd copy android` refreshed ignored packaged assets; one changed-assets rebuild succeeded in 1m 5s (213 tasks: 3 executed, 210 up-to-date). Logs are ignored `.gradle/report-local-debug-20261001.log` and `.gradle/report-local-debug-assets-20261001.log` under `android-app/android`.

Final APK CRC/required-entry checks and normalized baseline HTML/JS comparison passed. Existing asset verification passed byte-for-byte across current source/www/docs/generated/APK assets. SDK 36.0.0 aapt read package `dev.aiengg.potholereporter`, version 1.38.0/code 67, min SDK 24, target SDK 36 and MainActivity. apksigner verification passed with v2 signing and an Android Debug signer. These are debug-artifact checks, not clean independent build reproducibility or NEW-002/release verification. APK and private local evidence are ignored, not committed.

Eight synthetic harness tests, full-frame and pages-assets contracts, and 17 deterministic image-resource tests passed. The prepared acceptance template is `.gradle/report-local-device-prep/acceptance-template.json` under `android-app/android`; every physical check remains PENDING. No ADB device command, physical camera, Android restart, export grant or real-device performance check was executed.

## Prepare the artifact and private evidence directory

Use the existing D: toolchain/cache from the worklog. The narrow build is `android-app/android/gradlew.bat --no-daemon --offline --console=plain :app:assembleDebug`. Inspect canonical/www/docs/generated assets before building. A filename is insufficient: preserve the build exit status/log, Git source state, toolchain versions and APK hash. A single build does not prove reproducibility or NEW-002 provenance. Stop at any new build error; do not retry unchanged blockers, fetch new dependencies, change signing or touch NEW-002 in this task.

```powershell
$PythonExe = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$AdbExe = 'D:\Coding projects\pothole-reporter\android-app\android\.gradle\toolchain\android-sdk\platform-tools\adb.exe'
$ApkPath = 'D:\Coding projects\pothole-reporter\android-app\android\app\build\outputs\apk\debug\app-debug.apk'
$EvidenceDir = 'D:\Coding projects\pothole-reporter\android-app\android\.gradle\report-local-device-evidence'
& $PythonExe -B tools/report-local-device-evidence.py prepare --apk $ApkPath --output "$EvidenceDir\acceptance-template.json"
```

`prepare` checks APK CRC/required entries and compares packaged HTML/JS with Git's baseline contents, allowing only LF/CRLF checkout differences. It does not verify native source provenance or APK signing. Also run existing `tools/verify-release-assets.py` with `--static static --www android-app/www --docs docs --packaged android-app/android/app/src/main/assets/public --apk $ApkPath`, SDK `aapt.exe dump badging`, and `apksigner.bat verify --verbose --print-certs`. That existing verifier compares the current asset trees and APK byte-for-byte. Record exact results; debug signing does not imply release readiness. A stale APK must fail the baseline content check. The template refuses overwrites and starts every physical check PENDING.

## Device admission and installation (only when the phone is available)

```powershell
& $AdbExe devices -l
$DeviceSerial = '<copy the explicitly authorized physical device serial>'
& $AdbExe -s $DeviceSerial get-state
& $AdbExe -s $DeviceSerial shell getprop ro.product.model
& $AdbExe -s $DeviceSerial shell getprop ro.build.version.release
& $AdbExe -s $DeviceSerial install -r $ApkPath
& $AdbExe -s $DeviceSerial shell am start -n dev.aiengg.potholereporter/.MainActivity
```

Inspect existing installation/signature/data before `install -r`; stop on incompatibility. Do not uninstall to bypass a signature conflict. Keep serials, photos and personal device evidence in the ignored directory, not Git. Record model, Android/WebView versions, installed APK hash and build metadata. No API key or signing credential is required for manual reporting. Do not enter credentials or trigger Drive/cloud inference during these tests.

## Execute the acceptance matrix

For each row record UTC/local date and timezone, operator, APK hash, observed result, elapsed time where relevant, failure details, and evidence file names. The template is an evidence index, not a test runner; review and fill it only after actual observations.

Print [the synthetic camera target](../tests/fixtures/report-local-camera-target.svg) or display it on a separate screen. It is a camera-scene reference, not an importable raster, model input or accuracy benchmark. Use existing `tests/fixtures/sec010-images.json` rasters for bounded import preparation; real-device camera results still require taking an actual photo.

| Check | Procedure | Evidence required |
| --- | --- | --- |
| No-key/consent | Complete first-launch settings with no key. Decline camera/location disclosure once; confirm camera/location are not used. Then accept consent. | Actual device observations of both paths; no configured key. |
| Physical camera/full frame | While safely stopped, photograph a synthetic scene with four distinct corner markers, a center marker and a pothole-like drawing. Avoid faces/plates. Cancel a capture once, then capture and confirm another. | Real rear-camera operation, cancellation outcome, saved image showing all markers; orientation/whole-frame resize allowed. A drawing tests evidence geometry, not detector accuracy. |
| Offline/no location | Enable airplane mode in device Settings, explicitly turn off Wi-Fi and mobile data, retain USB ADB. Save/review a camera photo without location; import a fixture and decline current-location association. | Network-disabled state, private manual label, no claimed AI size/confidence, reviewable evidence and honest absent location. Browser tests are not a substitute. |
| Independent manual saves | Save the same photo twice and two photos from the same location. | Distinct reports; no silent merging or overwritten evidence. |
| Android restart | Note report IDs/count/evidence. Run the force-stop/start commands below while still offline. Reopen and review the same reports/photos. | Actual Android process restart with preserved report/evidence identity. Reboot/device-power-cycle evidence is additional; do not confuse a WebView refresh with force-stop. |
| Export/share | Explicitly export the saved full-frame evidence to a local file through the Android share sheet, without sending it to a remote recipient. Inspect the exported image off-device. Cancel share once. | File SHA-256/dimensions/corner markers, user-reported text, cancellation leaves report intact, no claim of official submission. |
| Resources/repetition | Sample idle, capture, save, review, restart and export; repeat the manual cycle ten times with representative available camera resolutions/orientations. Include the existing oversized/corrupt fixtures only where safely supported; no arbitrary new pixel budget. | Per-phase PSS/frame snapshots, operation timing, cycle/resolution metadata, observed freeze/crash/ANR or failure, camera/preview cleanup and post-cycle idle recovery. No model latency/accuracy test is applicable. |

```powershell
& $AdbExe -s $DeviceSerial shell am force-stop dev.aiengg.potholereporter
& $AdbExe -s $DeviceSerial shell am start -n dev.aiengg.potholereporter/.MainActivity
& $PythonExe -B tools/report-local-device-evidence.py collect --adb $AdbExe --serial $DeviceSerial --label idle --samples 5 --interval 2 --output "$EvidenceDir\idle-01.json"
# Repeat with unique filenames and capture/save/review/export/restart labels during the actual phases.
```

The collector is read-only: named-device authorization state, emulator hint, per-app `dumpsys meminfo` and `gfxinfo` only. It never installs, restarts, resets statistics, changes radios, accesses reports/photos, or reads logcat. It rejects offline/unauthorized/emulator/missing-process/unsupported PSS output and bounds sample count, interval, command timeout and captured-output size. A non-emulator flag alone does not prove a physical device; the operator must identify the real phone.

PSS snapshots are not guaranteed peak memory; cumulative gfxinfo counters may omit WebView rendering. Record wall-clock operation times manually and qualitative UI behavior. Do not label numerical performance PASS without reviewed acceptance evidence; no numerical budget has been selected in PRODUCT_DECISIONS.md. Failures must be retained and investigated in REPORT-LOCAL-001. Existing full-frame/image bounds and private persistence criteria remain unchanged.

## Closeout rules

Physical camera, offline Android restart, export/media behavior and resources remain PENDING until actual evidence exists. Append a truthful worklog entry and update status/task card only after review. Record unsupported checks as blocked, not passed. A verified debug build or synthetic test cannot close the gate. Retain NEW-002/security/release gates separately; do not start a later task here.
