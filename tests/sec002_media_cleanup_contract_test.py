#!/usr/bin/env python3
"""SEC002 registry contract. A changed storage writer requires explicit ownership review.

Writer hashes are deliberate review barriers, not dynamically generated expectations.
Run after npm ci; missing audited plugin source is a blocked contract, never a silent skip.
"""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = "android-app/android/app/src/main/java/dev/aiengg/potholereporter/"
WRITER_PATTERN = '\\bFile\\s*\\(|FileOutputStream|\\.writeBytes\\(|\\.writeText\\(|\\.outputStream\\(|createTempFile|\\.mkdirs\\(|setOutputFile|FileOutputOptions|openOutputStream|openFileDescriptor|MediaStore|DocumentFile|FileWriter|RandomAccessFile|createNewFile|Files\\.(copy|move|write)'
AUDITED_NATIVE_WRITERS = {'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/DriveForegroundService.kt': 'd40e2534aa9a71cc78cfefd14fca84a92983fa0df303ab058fd97aadbff4fb87',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeDriveCameraManager.kt': '8a51ce3b7495773004a9a3882a7a4b7f117170d574dd3976c0a5be274417767d',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeInferenceEvidenceStore.kt': '6a28078525308a7eecbe0d5fbc8cb87a35e7ecd51a6aba20d0f896ddf7304397',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeKeyframeFiles.kt': '6889d0f0e27b6c1857b2211e34ae37aa6956872e21453a8b473581d9b0e4b36d',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeReportEvidenceStorage.kt': '724df2ab9f8c255f1fad5a2953e99f6b5f8c3ed1bef4bc9bec67d873e42f07b0',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeSourceMediaLedger.kt': 'ad71edeacf63b5dc9f0ce2a0d8f8c14ee8f1d21e1997a41ed4b97765676bbb4a',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt': '27726aa0062f0255e24ef40edaaca8aecc3942c91fbdd4bcacc8378767714e46',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/NativeKeyframeOwnershipPaging.kt': '585af5648ba5a0cf16e8b1b001327c32f9d3c74c64f92ad53f04ff80c7341878',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/NativePrivateMediaFiles.kt': '1799f47d02c0306ca27c8f6398a5e977754e5b41b3d6b250f795653ed65ff884',
 # SEC-006 ownership review: native-private noBackupFilesDir/ai_usage_budget/usage.bin.
 # Not media; deliberately retained through credential/media wipes to prevent budget reset.
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/AiUsageBudget.kt': 'cd2eb2079439583d81c3c247db6fb73a9e83d3efd1b312c147c07523221e8f35',
 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeAiUsageBudget.kt': 'b5f49341cf9e09729035057455b3b4df6e070d116f8d6e93a6cbad39d15d734d'}
AUDITED_PLUGIN_WRITERS = {'android-app/node_modules/@capacitor/camera/android/build.gradle': '97be858b6bdae7dca5db417e225d8d0a02c3b1b9979ab2662cf19b8bb20fce7a',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraBottomSheetDialogFragment.java': 'aeae6712090896e4a9f41f5e4ec495864ca67d307641a38e491c2afe7301e2c0',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraPlugin.kt': '9d8013e6d3ef5108784f67b9338c2ec1c906e94244d5d8de9e88d3d44764d07c',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraResultType.java': '37543b1ebd544d69d26927653c63aa45b53a9cafefb1320ba8bf9e727315f2e7',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraSource.java': 'b309ed7662810d7bd2297306336611aad44ab636ba27b42910b151591c4c03aa',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraUtils.java': '082c7388447f7c6fdadceefbc6b4b9425df25b595436a09f07c5a3f6ba0faf06',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/ExifWrapper.java': 'f3bb698c482d4d556abc130cf58ce1e4dbddf08d8ec45fc52de514f75aa912d4',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/ImageUtils.java': '0fad0d1a1e24b50dc0ab3d781aa6201c77cbedb585e5566fd6aafe20c9e833f6',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonCameraFlow.kt': '9e226f6fa24eba5baf1a1a0e40ac89d1b10520d37959f553fad337466cb990e4',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonCameraSettings.kt': '30499dd54b60f2fb0d8c3be2ccb360ee483ddcfa215b98fb95a4b05903b62eb9',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonCameraUtils.kt': 'e70160126fbe968be85b8dccc0ccfab921f5582b93f011ca5cc1950aa9f10e79',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonEditableMode.kt': 'f2e96189dd39152f70de8a153ea9771e5bb15c4a2e867344ca71d1b114071332',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonGallerySettings.kt': '8d6748ef7f836a92bb15a59eb01aa43cb9b4b233f98009b9d28804345cda0b85',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/LegacyCameraFlow.java': 'b84bdac89e9ad1dbcdbd817957b9726fb2a8f08f5ca15d7eb53911db3f0170bc',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/LegacyCameraSettings.kt': '0f0eac80ce087aa64a151f1fc07f1050ef92f0d526e3250ebd72e6ca2ec25e57',
 'android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/PermissionHelper.kt': '275f27933d449276ef4b060258d8e6b67e14be9cc2085cfa72197f50fe49fe2b',
 'android-app/node_modules/@capacitor/share/android/src/main/java/com/capacitorjs/plugins/share/SharePlugin.java': '0adb329c9e88645c40aea238927b9f2178db3b5aa9ce8644147bc60c29d41e90',
 'android-app/node_modules/capacitor-email-composer/android/src/main/java/de/einfachhans/emailcomposer/AssetUtil.java': '90ccd162fdf1fb12a053ee2dc822b0055f0dc1cdd7fcc389c7fe53a524ef9401',
 'android-app/node_modules/capacitor-email-composer/android/src/main/java/de/einfachhans/emailcomposer/EmailComposer.java': '898eb7c51ac459731bcfb70f8385ee6dcc7410a52453e79a1da9ffae3ff3197c',
 'android-app/node_modules/capacitor-email-composer/android/src/main/java/de/einfachhans/emailcomposer/EmailComposerPlugin.java': '4b9cfea12917ddb0737d480b94c4ead8e510123f42dcde5001f35ef01710aebc',
 'android-app/package-lock.json': 'c4eb80f7870498d1eb0ed4a14f182d21a19450fc795d203bf78dc17ed980fec7'}
AUDITED_WEB_WRITERS = {'shareEvidence': '413cea4a2056e90b3bcaffedc1f62eb04aef387aecfffbb3b35afb27515986ec',
 'shareZip': '6b3e5aeb3f55cfadfdb569d19fc8124efbc82644ac55d64c1ed9e9cb79433470',
 'writeFrameFile': 'c1ae7d8720490f25c4bc7a73ef364d4618fdccc4599c7770ce3561b18651d0c3',
 'writeManifest': '6919e45b89eeb9e9b7fa3410d6208187ff3ea4a43451e06d772038cde76fc8ae'}
checks = 0
def check(condition, label):
    global checks
    assert condition, label
    checks += 1
def text(name): return (ROOT/name).read_text(encoding="utf-8")
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

native = {}
for p in (ROOT/BASE).rglob("*"):
    if p.suffix in (".kt", ".java") and "/media/" not in p.as_posix() and re.search(WRITER_PATTERN, p.read_text(encoding="utf-8")):
        native[p.relative_to(ROOT).as_posix()] = digest(p.read_text(encoding="utf-8"))
check(native == AUDITED_NATIVE_WRITERS, "Native writer changed/new storage writer: review and register ownership")
for name, expected in AUDITED_PLUGIN_WRITERS.items():
    check((ROOT/name).is_file() and digest(text(name)) == expected, "Plugin writer/dependency changed: re-audit its storage roots")

web = text("static/index.html")
client = text("static/standalone.js")
for name, expected in AUDITED_WEB_WRITERS.items():
    start = web.index("async function " + name + "(")
    if name == "shareEvidence": finish = web.index("// A burst", start)
    elif name == "writeManifest": finish = web.index("\n}", start) + 2
    else: finish = web.index({"writeFrameFile": "async function writeManifest", "shareZip": '$("fileInput").onchange'}[name], start + 1)
    check(digest(web[start:finish]) == expected, "Web storage writer changed: review and register ownership")
check(len(re.findall(r"Filesystem\.writeFile\(", web + client)) == 4, "New web file writer requires ownership review")
registry = text(BASE + "media/AndroidAppMediaCleanup.kt")
engine = text(BASE + "media/OwnedMediaCleanup.kt")
bridge = text(BASE + "media/ManagedMediaPlugin.kt")
drive = text(BASE + "plugin/DriveModePlugin.kt")
clear = drive[drive.index("fun clearNativeData"):drive.index("fun getDrives")]
for root in ("reports", "footage", "repair_targets", "ion_android_camera_videos", "pothole-frames", "email_composer"):
    check('"' + root + '"' in registry, "Known media root missing from authoritative registry")
for api in ("context.filesDir", "context.cacheDir", "getExternalFilesDirs(null)", "externalCacheDirs", "externalMediaDirs", "DIRECTORY_DOCUMENTS"):
    check(api in registry, "Known Android storage class missing")
check("AndroidAppMediaCleanup(context).clearAll()" in clear and "managedRoots" not in clear, "Wipe uses one authoritative media registry")
check("AppMediaOperations.gate.beginClear()" in clear and "AppMediaOperations.gate.endClear()" in clear, "Native wipe/writer barrier preserved")
check("NativeMediaFilesystemMutation.mutex.withLock" in clear and "service.stopDriveSession" in clear and "queuePendingStartStop" in clear, "Drive producer shutdown barriers preserved")
check("failure?.message" not in clear and "${error.message}" not in clear, "No sensitive path exceptions returned by wipe")
check("Os.lstat" in registry and "S_ISLNK" in registry and "deleteRecursively" not in engine.replace("File.deleteRecursively", ""), "No directory symlink traversal")
check("revokeUriPermission" in registry and '".fileprovider"' in registry and '".camera.provider"' in registry, "Both providers revoke owned URI grants")
check('"external"' not in registry, "No broad shared external provider revocation")
check('getSharedPreferences("CameraStore"' in registry and ".clear().commit()" in registry, "Deleted camera URI metadata cleared")
check("NativeBridgeAuthorization.isTrustedMainDocument" in bridge and "gate.owns(token)" in bridge and "token.length != 36" in bridge, "Native lease authorization and token validation")
check('call.getString("path")' not in bridge and 'call.getString("uri")' not in bridge, "No JS-controlled native deletion paths")
check('setOf("camera", "email", "share")' in engine, "Only audited operation kinds admitted")
check('finally {\n      const result = await plugin.endOperation' in client, "Cleanup runs on success/cancel/failure")
check('withManagedMediaOperation("camera"' in web and 'withManagedMediaOperation("email"' in client, "Camera and composer use native finally cleanup")
check(web.count('withManagedMediaOperation("share"') == 2, "Native share writers participate in wipe barrier")
check("saveToGallery: false" in web and "allowEditing: false" in web, "No camera originals exported into unrelated user gallery")
check("window.isManagedMediaWipeInProgress" in client and "if (wipeActive())" in client and "window.isManagedMediaWipeInProgress = () => nativeWipeInProgress" in web, "Late media writers cannot cross native/web wipe completion")
manifest = text("android-app/android/app/src/main/AndroidManifest.xml")
check("android.permission.WRITE_EXTERNAL_STORAGE" not in manifest and "android.permission.READ_EXTERNAL_STORAGE" not in manifest, "Scoped storage preserved without legacy permission")
for name in ("index.html", "standalone.js"):
    for mirror in ("docs", "android-app/www", "android-app/android/app/src/main/assets/public"):
        check((ROOT/"static"/name).read_bytes() == (ROOT/mirror/name).read_bytes(), "Web source/mirror mismatch")
for source in (registry, engine, bridge):
    check(not re.search(r"(?:println|printStackTrace|Log\.[diwe]|console\.log)\s*\(", source), "No cleanup paths or artifact contents logged")
for p in (ROOT/BASE/"media").glob("*.kt"):
    check(not re.search(r"FileOutputStream|FileWriter|RandomAccessFile|writeBytes|writeText|outputStream\(|createTempFile|mkdirs\(|openOutputStream|openFileDescriptor|Files\.(copy|move|write)", p.read_text(encoding="utf-8")), "Cleanup package cannot add an unregistered media producer")
print(f"SEC002 static registry contract PASS: {checks} checks")
