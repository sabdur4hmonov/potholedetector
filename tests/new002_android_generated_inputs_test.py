#!/usr/bin/env python3
"""NEW-002: ignored generated Android inputs must be present and exactly CLI-generated.

Runs the preflight against the real tree, then against a copied fixture with clean-checkout,
stale, tampered and unsupported variants. Needs the installed android-app/node_modules
(npm ci); no Gradle, device, network or credentials.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify-android-generated-inputs.py"
RELEASE = (ROOT / "tools/build-play-release.sh").read_text(encoding="utf-8")
APP = "android-app"
MAIN = f"{APP}/android/app/src/main"
MODULE = f"{APP}/android/capacitor-cordova-android-plugins"
checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print(f"  ok   {label}")


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), "--root", str(root)], capture_output=True, text=True)


def copy(rel: str, target: Path) -> None:
    source = ROOT / rel
    destination = target / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("build", ".gradle"))
    else:
        shutil.copy2(source, destination)


def build_fixture(target: Path) -> None:
    package = json.loads((ROOT / APP / "package.json").read_text(encoding="utf-8"))
    for rel in ("package.json", "package-lock.json", "capacitor.config.json"):
        copy(f"{APP}/{rel}", target)
    for name in list(package.get("dependencies") or {}) + list(package.get("devDependencies") or {}):
        copy(f"{APP}/node_modules/{name}/package.json", target)
        meta = json.loads((ROOT / APP / "node_modules" / name / "package.json").read_text(encoding="utf-8"))
        if meta.get("capacitor", {}).get("android"):
            src = ROOT / APP / "node_modules" / name / meta["capacitor"]["android"].get("src", "android") / "src/main"
            for file in src.rglob("*"):
                if file.is_file() and file.suffix in (".java", ".kt"):
                    copy(file.relative_to(ROOT).as_posix(), target)
    for rel in ("node_modules/@capacitor/cli/dist/config.js",
                "node_modules/@capacitor/cli/assets/capacitor-cordova-android-plugins.tar.gz"):
        copy(f"{APP}/{rel}", target)
    for rel in (f"{APP}/android/capacitor.settings.gradle", f"{APP}/android/app/capacitor.build.gradle",
                MODULE, f"{MAIN}/assets/capacitor.config.json", f"{MAIN}/assets/capacitor.plugins.json",
                f"{MAIN}/assets/public/cordova.js", f"{MAIN}/assets/public/cordova_plugins.js",
                f"{MAIN}/res/xml/config.xml"):
        copy(rel, target)


def variant(base: Path, name: str, mutate) -> subprocess.CompletedProcess:
    target = base.parent / name
    shutil.copytree(base, target)
    mutate(target)
    return run(target)


real = run(ROOT)
check(real.returncode == 0 and "0 Cordova plugins" in real.stdout,
      f"current tree generated inputs match the locked Capacitor CLI ({real.stdout.strip() or real.stderr.strip()})")

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp) / "fixture"
    build_fixture(base)
    check(run(base).returncode == 0, "copied fixture passes before mutation")

    def expect_fail(name, mutate, needle, label):
        result = variant(base, name, mutate)
        check(result.returncode == 1 and needle in result.stderr and "npx cap sync android" in result.stderr,
              f"{label} (stderr: {result.stderr.strip().splitlines()[0] if result.stderr.strip() else ''})")

    def clean_checkout(t):
        shutil.rmtree(t / MODULE)
        for rel in (f"{MAIN}/assets/capacitor.config.json", f"{MAIN}/assets/capacitor.plugins.json",
                    f"{MAIN}/assets/public", f"{MAIN}/res/xml/config.xml"):
            path = t / rel
            shutil.rmtree(path) if path.is_dir() else path.unlink()
    expect_fail("clean", clean_checkout, "missing", "clean checkout without ignored generated inputs fails closed")
    expect_fail("novars", lambda t: (t / MODULE / "cordova.variables.gradle").unlink(),
                "missing", "missing cordova.variables.gradle fails closed")

    def extra_jar(t):
        libs = t / MODULE / "src/main/libs"
        libs.mkdir(parents=True)
        (libs / "stale.jar").write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    expect_fail("jar", extra_jar, "unexpected", "stray JAR picked up by fileTree(src/main/libs) fails closed")

    def module_build(t):
        path = t / MODULE / "build.gradle"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "// SUB-PROJECT DEPENDENCIES END", 'implementation "com.example:unreviewed:1.0"\n    // SUB-PROJECT DEPENDENCIES END'),
            encoding="utf-8")
    expect_fail("modbuild", module_build, "build.gradle differs", "altered Cordova module build.gradle fails closed")

    def stale_registry(t):
        path = t / MAIN / "assets/capacitor.plugins.json"
        data = [e for e in json.loads(path.read_text(encoding="utf-8")) if e["pkg"] != "capacitor-email-composer"]
        path.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
    expect_fail("registry", stale_registry, "capacitor.plugins.json", "stale plugin registry fails closed")
    expect_fail("cordovajs", lambda t: (t / MAIN / "assets/public/cordova.js").write_text("window.stale=1;", encoding="utf-8"),
                "must be empty", "non-empty generated cordova.js fails closed")

    def tracked_drift(t):
        path = t / APP / "android/app/capacitor.build.gradle"
        path.write_text(path.read_text(encoding="utf-8").replace("    implementation project(':capacitor-share')\n", ""),
                        encoding="utf-8")
    expect_fail("tracked", tracked_drift, "capacitor.build.gradle differs", "tracked Capacitor Gradle wiring drift fails closed")

    def version_drift(t):
        path = t / APP / "node_modules/@capacitor/camera/package.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = "0.0.0-unlocked"
        path.write_text(json.dumps(data), encoding="utf-8")
    expect_fail("version", version_drift, "does not match package-lock.json", "installed plugin not matching the lockfile fails closed")

    def cordova_plugin(t):
        package_path = t / APP / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["dependencies"]["cordova-plugin-example"] = "1.0.0"
        package_path.write_text(json.dumps(package), encoding="utf-8")
        lock_path = t / APP / "package-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["packages"]["node_modules/cordova-plugin-example"] = {"version": "1.0.0"}
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        plugin = t / APP / "node_modules/cordova-plugin-example"
        plugin.mkdir(parents=True)
        (plugin / "package.json").write_text('{"name":"cordova-plugin-example","version":"1.0.0"}', encoding="utf-8")
        (plugin / "plugin.xml").write_text("<plugin id='cordova-plugin-example'/>", encoding="utf-8")
    expect_fail("cordova", cordova_plugin, "Cordova plugin", "Cordova plugin dependency fails closed")
    expect_fail("configxml", lambda t: (t / MAIN / "res/xml/config.xml").write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n<widget><access origin=\"https://evil.example\" /></widget>", encoding="utf-8"),
        "config.xml differs", "altered Cordova config.xml fails closed")
    expect_fail("manifest", lambda t: (t / MODULE / "src/main/AndroidManifest.xml").write_text(
        "<manifest><uses-permission android:name=\"android.permission.READ_CONTACTS\"/></manifest>", encoding="utf-8"),
        "AndroidManifest.xml differs", "altered Cordova module manifest fails closed")
    expect_fail("tsconfig", lambda t: (t / APP / "capacitor.config.ts").write_text("export default {};", encoding="utf-8"),
                "not supported", "unsupported TypeScript Capacitor config fails closed")

    def crlf(t):
        for rel in (f"{APP}/android/capacitor.settings.gradle", f"{APP}/android/app/capacitor.build.gradle"):
            path = t / rel
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    check(variant(base, "crlf", crlf).returncode == 0, "Windows CRLF checkout of tracked Gradle wiring is accepted")

# Release wiring: preflight precedes Gradle; NEW-001 step 4 remains.
preflight = RELEASE.find("python3 tools/verify-android-generated-inputs.py")
gradle = RELEASE.find("./gradlew --no-daemon --offline")
check(0 < preflight < gradle, "release script runs the generated-input preflight before Gradle")
check("npm ci && npx cap sync android" in RELEASE[preflight:gradle], "release failure message gives the locked bootstrap")
check('python3 tools/normalize-aab-signature-order.py --check "$AAB_PATH"' in RELEASE
      and "internal inconsistencies|not signed in JarInputStream" in RELEASE,
      "NEW-001 AAB signature gate is preserved")
check('python3 "$RELEASE_ASSET_VERIFIER"' in RELEASE and 'same_json "$SOURCE_CAPACITOR_CONFIG"' in RELEASE,
      "existing asset mirror and Capacitor config checks are preserved")

print(f"\nNEW-002 ANDROID GENERATED INPUTS TEST PASS ({checks} checks)")
