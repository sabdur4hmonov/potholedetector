#!/usr/bin/env python3
"""NEW-001: signed AABs must present one signature view to every standard JAR reader.

Builds throwaway JARs signed by a throwaway key with the JDK's keytool/jarsigner, recreates
AGP's manifest-last order, and proves that the release normalizer fixes the reader
differential without changing entries or masking tampering. No release key is used.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/normalize-aab-signature-order.py"
RELEASE = (ROOT / "tools/build-play-release.sh").read_text(encoding="utf-8")
INCONSISTENT = "internal inconsistencies"
checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print(f"  ok   {label}")


def jdk_tool(name: str) -> str:
    candidates = [shutil.which(name)]
    if os.environ.get("JAVA_HOME"):
        candidates.append(str(Path(os.environ["JAVA_HOME"]) / "bin" / (name + (".exe" if os.name == "nt" else ""))))
    candidates.append(str(ROOT.parent / "toolchain/jdk/bin" / (name + (".exe" if os.name == "nt" else ""))))
    found = next((c for c in candidates if c and Path(c).is_file()), None)
    assert found, f"{name} is required (install a JDK or set JAVA_HOME)"
    return found


def run(*args, check_rc=True):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if check_rc and result.returncode:
        raise AssertionError(f"{args[0]} failed: {result.stdout}{result.stderr}")
    return result


def tool(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def rewrite(src: Path, dst: Path, order):
    with zipfile.ZipFile(src) as zin:
        infos = {i.filename: i for i in zin.infolist()}
        with zipfile.ZipFile(dst, "w") as zout:
            for name in order([i.filename for i in zin.infolist()]):
                info = infos[name]
                clone = zipfile.ZipInfo(name, date_time=info.date_time)
                clone.compress_type = info.compress_type
                clone.external_attr = info.external_attr
                zout.writestr(clone, zin.read(name))


def manifest_last(names):
    meta = [n for n in names if n.startswith("META-INF/") and n != "META-INF/MANIFEST.MF"]
    return [n for n in names if not n.startswith("META-INF/")] + meta + ["META-INF/MANIFEST.MF"]


keytool, jarsigner = jdk_tool("keytool"), jdk_tool("jarsigner")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    store, password = tmp / "throwaway.jks", "throwaway-test-only"
    run(keytool, "-genkeypair", "-alias", "fixture", "-keyalg", "RSA", "-keysize", "2048", "-validity", "2",
        "-dname", "CN=NEW-001 synthetic fixture", "-keystore", store, "-storepass", password, "-keypass", password)
    unsigned = tmp / "fixture.aab"
    with zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BundleConfig.pb", b"synthetic bundle config")
        archive.writestr("base/manifest/AndroidManifest.xml", b"<manifest/>")
        archive.writestr("base/assets/public/standalone.js", b"console.log('fixture');\n")
    signed = tmp / "signed.aab"
    shutil.copy(unsigned, signed)
    run(jarsigner, "-keystore", store, "-storepass", password, "-keypass", password, signed, "fixture")

    def verify(path):
        return run(jarsigner, "-verify", path, check_rc=False).stdout

    agp_like = tmp / "agp-like.aab"
    rewrite(signed, agp_like, manifest_last)
    report = verify(agp_like)
    check("jar verified." in report and INCONSISTENT in report,
          "manifest-last order reproduces the JarFile/JarInputStream differential")
    check(tool("--check", agp_like).returncode == 1, "--check rejects manifest-last metadata")

    with zipfile.ZipFile(agp_like) as original:
        before = {i.filename: (original.read(i.filename), i.compress_type, i.date_time, i.external_attr)
                  for i in original.infolist()}
    result = tool(agp_like)
    check(result.returncode == 0 and "normalized" in result.stdout, "normalizer rewrites manifest-last metadata")
    with zipfile.ZipFile(agp_like) as fixed:
        names = [i.filename for i in fixed.infolist()]
        after = {i.filename: (fixed.read(i.filename), i.compress_type, i.date_time, i.external_attr)
                 for i in fixed.infolist()}
    check(names[0] == "META-INF/MANIFEST.MF" and names[1].endswith(".SF") and names[2].endswith(".RSA"),
          "manifest and signature files come first")
    check(before == after, "every entry keeps identical bytes, compression, timestamp and attributes")
    report = verify(agp_like)
    check("jar verified." in report and INCONSISTENT not in report, "normalized archive verifies with one reader view")
    check(tool("--check", agp_like).returncode == 0, "--check accepts the normalized archive")
    digest = agp_like.read_bytes()
    check(tool(agp_like).returncode == 0 and "already conventional" in tool(agp_like).stdout
          and agp_like.read_bytes() == digest, "conventional archive is left byte-for-byte untouched")
    check(tool("--check", signed).returncode == 0, "jarsigner's own output order is accepted")

    tampered = tmp / "tampered.aab"
    rewrite(agp_like, tampered, lambda names: names)
    with zipfile.ZipFile(tampered) as zin, zipfile.ZipFile(tmp / "t2.aab", "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "base/assets/public/standalone.js":
                data = b"console.log('tampered');\n"
            clone = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            clone.compress_type = info.compress_type
            zout.writestr(clone, data)
    tampered = tmp / "t2.aab"
    check(tool(tampered).returncode == 0 and "jar verified." not in verify(tampered),
          "normalization does not bless tampered content; jarsigner still rejects it")

    check(tool("--check", unsigned).returncode == 1 and tool(unsigned).returncode == 1,
          "unsigned archive fails closed")
    duplicate = tmp / "duplicate.aab"
    shutil.copy(signed, duplicate)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with zipfile.ZipFile(duplicate, "a") as archive:
            archive.writestr("base/assets/public/standalone.js", b"shadow entry")
    result = tool(duplicate)
    check(result.returncode == 1 and "duplicate" in result.stderr, "duplicate entry names fail closed")
    check(tool("--check", tmp / "missing.aab").returncode == 1, "missing archive fails closed")

# Release gate wiring.
step = RELEASE[RELEASE.index('echo "4/7 validating AAB and APK signatures"'):RELEASE.index('echo "5/7')]
order = [step.find(token) for token in (
    'python3 tools/normalize-aab-signature-order.py "$AAB_PATH"',
    'python3 tools/normalize-aab-signature-order.py --check "$AAB_PATH"',
    'jarsigner -verify "$AAB_PATH"',
    "internal inconsistencies|not signed in JarInputStream|Manifest is missing when reading via JarInputStream",
    "expected_upload_cert_sha256=",
)]
check(all(p >= 0 for p in order) and order == sorted(order),
      "release step normalizes, checks, verifies, rejects reader differentials, then pins the upload certificate")
check('fail "AAB JAR signature differs between JarFile and JarInputStream readers"' in step,
      "reader differential is a release failure")
check(RELEASE.index('echo "4/7') < RELEASE.index('--aab "$AAB_PATH" --apk "$APK_PATH"'),
      "asset verification reads the normalized AAB")
check("29:6F:94:7F:84:12:AC:A3:92:5C:F5:16:9C:19:5A:E0:97:C6:85:6D:57:51:EE:DD:78:9D:D4:BF:BA:7B:AC:8C" in step,
      "registered upload certificate pin is preserved")

print(f"\nNEW-001 AAB SIGNATURE ORDER TEST PASS ({checks} checks)")
