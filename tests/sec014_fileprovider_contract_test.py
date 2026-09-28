#!/usr/bin/env python3
"""SEC-014 FileProvider least-privilege contract.

The app FileProvider may expose only the directories that an in-app grant uses. A new
`.fileprovider` caller, a broader root, or a writer moved outside these roots requires
re-review. Run after npm ci; missing plugin source is a failure, never a silent skip.
"""
from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "android-app/android/app/src/main"
NM = ROOT / "android-app/node_modules"
ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print(f"  ok   {label}")


def text(path):
    return Path(path).read_text(encoding="utf-8")


# 1. Exact, narrow roots. Names are the revocation prefixes used by Delete All.
paths = ET.parse(APP / "res/xml/file_paths.xml").getroot()
entries = [(child.tag, child.get("name"), child.get("path")) for child in paths]
EXPECTED_ROOTS = [
    ("files-path", "drive_footage", "footage/"),
    ("external-files-path", "my_images", "Pictures/"),
    ("cache-path", "my_cache_images", "pothole-reporter-shares/"),
    ("external-cache-path", "email_composer_attachments", "email_composer/"),
]
check(entries == EXPECTED_ROOTS, "app FileProvider exposes exactly the four reviewed directories")
check(all(p not in (".", "", "/") for _, _, p in entries), "no app FileProvider alias maps a whole storage root")
check(not any(tag in ("root-path", "external-path", "external-media-path") for tag, _, _ in entries),
      "no shared-storage or filesystem-root alias")

cleanup = text(APP / "java/dev/aiengg/potholereporter/media/AndroidAppMediaCleanup.kt")
match = re.search(r'"\.fileprovider" to listOf\(([^)]*)\)', cleanup)
aliases = re.findall(r'"([^"]+)"', match.group(1)) if match else []
check(aliases == [name for _, name, _ in EXPECTED_ROOTS], "Delete All revokes every app FileProvider alias prefix")

# 2. Provider and component exposure.
manifest = ET.parse(APP / "AndroidManifest.xml").getroot()
application = manifest.find("application")
providers = application.findall("provider")
check(len(providers) == 1, "app manifest declares one FileProvider")
provider = providers[0]
check(provider.get(ANDROID_NS + "name") == "androidx.core.content.FileProvider"
      and provider.get(ANDROID_NS + "authorities") == "${applicationId}.fileprovider"
      and provider.get(ANDROID_NS + "exported") == "false"
      and provider.get(ANDROID_NS + "grantUriPermissions") == "true",
      "FileProvider is unexported and reachable only through explicit URI grants")
for kind in ("service", "receiver"):
    check(all(c.get(ANDROID_NS + "exported") == "false" for c in application.findall(kind)),
          f"every app {kind} is unexported")
activities = application.findall("activity")
filters = [f for a in activities for f in a.findall("intent-filter")]
actions = sorted(x.get(ANDROID_NS + "name") for f in filters for x in f.findall("action"))
check(len(activities) == 1 and actions == ["android.intent.action.MAIN"]
      and not any(f.findall("data") for f in filters),
      "only exported activity is the launcher; no VIEW/SEND/data intent entry point")

# 3. Every `.fileprovider` URI minter is known and writes inside a declared root.
# Whole src/main trees: some plugins keep Kotlin outside src/main/java.
sources = [APP / "java"]
for pattern in ("@capacitor/*/android/src/main", "@capacitor/android/capacitor/src/main",
                "capacitor-*/android/src/main"):
    sources += list(NM.glob(pattern))
sources.append(ROOT / "android-app/android/capacitor-cordova-android-plugins/src")
# app + six @capacitor plugins + Capacitor core + email composer + Cordova bridge module.
check(all(s.is_dir() for s in sources) and len(sources) == 10, "app, Capacitor core and all plugin sources present")
minters = sorted(
    p.relative_to(ROOT).as_posix()
    for s in sources for p in s.rglob("*")
    if p.suffix in (".kt", ".java") and ".fileprovider" in p.read_text(encoding="utf-8", errors="replace")
)
EXPECTED_MINTERS = sorted([
    "android-app/android/app/src/main/java/dev/aiengg/potholereporter/media/AndroidAppMediaCleanup.kt",
    "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt",
    "android-app/node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/BridgeWebChromeClient.java",
    "android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraUtils.java",
    "android-app/node_modules/@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/LegacyCameraFlow.java",
    "android-app/node_modules/@capacitor/share/android/src/main/java/com/capacitorjs/plugins/share/SharePlugin.java",
    "android-app/node_modules/capacitor-email-composer/android/src/main/java/de/einfachhans/emailcomposer/AssetUtil.java",
])
check(minters == EXPECTED_MINTERS, f"`.fileprovider` callers unchanged (found {minters})")

plugin = text(APP / "java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt")
share_footage = plugin[plugin.index("fun shareFootage("):plugin.index("fun deleteFootage(")]
check("getSegmentsForSession(requestedSession)" in share_footage
      and "addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)" in share_footage
      and "WRITE_URI" not in share_footage and "PERSISTABLE" not in share_footage,
      "footage share grants read-only temporary access to Room-owned clips")
camera_manager = text(APP / "java/dev/aiengg/potholereporter/drive/NativeDriveCameraManager.kt")
check('File(context.filesDir, "footage/$sessionId")' in camera_manager, "native clips are written under files/footage/")

camera_utils = text(NM / "@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/CameraUtils.java")
chrome = text(NM / "@capacitor/android/capacitor/src/main/java/com/getcapacitor/BridgeWebChromeClient.java")
legacy = text(NM / "@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/LegacyCameraFlow.java")
check("getExternalFilesDir(Environment.DIRECTORY_PICTURES)" in camera_utils
      and "getExternalFilesDir(Environment.DIRECTORY_PICTURES)" in chrome
      and "CameraUtils.createImageFile(activity)" in legacy,
      "camera capture files granted through my_images are created in external Pictures/")
check("if (settings.getAllowEditing() && !isEdited)" in legacy,
      "legacy cache-root edit grant only runs when editing is requested")
ion = text(NM / "@capacitor/camera/android/src/main/java/com/capacitorjs/plugins/camera/IonCameraFlow.kt")
check('AUTHORITY = ".camera.provider"' in ion and ".fileprovider" not in ion,
      "IonCamera flows use their own provider, not the app FileProvider")

web = text(ROOT / "static/index.html")
engine = text(ROOT / "static/standalone.js")
check(re.search(r"camera\.getPhoto\(\{[^}]*allowEditing: false[^}]*source: \"CAMERA\"", web) is not None,
      "app camera call disables editing, so no cache-root edit URI is minted")
check('const SHARE_CACHE_DIR = "pothole-reporter-shares";' in web, "share cache directory constant matches cache alias")
shares = re.findall(r"P\.Share\.share\(", web)
share_writes = re.findall(r'writeFile\(\{ path: `\$\{SHARE_CACHE_DIR\}/\$\{[a-z]+\.name\}`, data: [a-z]+\.base64, directory: "CACHE" \}\)', web)
cache_dirs = re.findall(r'directory: "CACHE"', web)
check(len(shares) == 2 and len(share_writes) == 2 and len(cache_dirs) == 4 and "Share.share" not in engine,
      "both native share calls send only files just written to CACHE/pothole-reporter-shares")
check(engine.count("EmailComposer.open(") == 1 and 'attachments: [{ type: "base64"' in engine
      and '"absolute"' not in engine and '"absolute"' not in web,
      "email composer receives base64 evidence only, never an app-chosen absolute path")
asset = text(NM / "capacitor-email-composer/android/src/main/java/de/einfachhans/emailcomposer/AssetUtil.java")
check('ATTACHMENT_FOLDER = "/email_composer"' in asset and "ctx.getExternalCacheDir()" in asset,
      "email attachments are written to external cache email_composer/")

# 4. Grants are temporary; revocation fixture stays inside the narrowed alias.
grant_sources = [p for s in sources for p in s.rglob("*") if p.suffix in (".kt", ".java")]
check(not any(re.search(r"FLAG_GRANT_PERSISTABLE_URI_PERMISSION|FLAG_GRANT_PREFIX_URI_PERMISSION|takePersistableUriPermission",
                        p.read_text(encoding="utf-8", errors="replace")) for p in grant_sources),
      "no persistable or prefix URI grants are requested")
instrumented = text(ROOT / "android-app/android/app/src/androidTest/java/dev/aiengg/potholereporter/media/AppMediaCleanupInstrumentedTest.kt")
check('seed(File(context.cacheDir, "pothole-reporter-shares"))' in instrumented,
      "instrumented revocation fixture is mappable by both providers after narrowing")

# 5. Share code reviewed here is the code shipped in every web mirror.
for name in ("index.html", "standalone.js"):
    mirrors = [ROOT / d / name for d in ("static", "docs", "android-app/www", "android-app/android/app/src/main/assets/public")]
    check(len({hashlib.sha256(m.read_bytes()).hexdigest() for m in mirrors}) == 1, f"{name} mirrors are identical")

print(f"\nSEC-014 FILEPROVIDER CONTRACT PASS ({checks} checks)")
