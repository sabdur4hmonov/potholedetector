#!/usr/bin/env python3
"""SEC-015 source-digest contract.

Downloaded build inputs are authenticated only by a pinned SHA-256; MD5 must never be
computed or accepted as an integrity check. The historical `source_md5` value is a
provenance label of the already-built highway catalog and is allowed only where listed.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PULL = ROOT / "tools/pull-national-highways.sh"
HISTORICAL_MD5 = "c5e0a62a1cb00c80d8c5948bf18370d7"
checks = 0


def check(condition, label):
    global checks
    assert condition, label
    checks += 1
    print(f"  ok   {label}")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# 1. Static shape of the only downloaded-source verifier.
pull = text(PULL)
check(not re.search(r"(?i)\bmd5sum\b|\bmd5\s+-q\b|SOURCE_MD5|ACTUAL_MD5|dgst\s+-md5|openssl\s+md5", pull)
      and HISTORICAL_MD5 not in pull, "pull script neither computes nor pins MD5")
pin = re.search(r"^SOURCE_SHA256=(.*)$", pull, re.M)
check(pin is not None and (pin.group(1) == "" or re.fullmatch(r"[0-9a-f]{64}", pin.group(1))),
      "SOURCE_SHA256 is empty (fail closed) or a lowercase 64-hex digest")
main = pull[pull.index("main() {"):]
positions = [main.find(token) for token in (
    'require_sha256_pin "$SOURCE_SHA256"', "curl --fail", 'verify_source_digest "$PBF" "$SOURCE_SHA256"',
    "osmium tags-filter", "tools/build-national-highways.py")]
check(all(p >= 0 for p in positions) and positions == sorted(positions),
      "pin check precedes download; SHA-256 verification precedes parsing and build")
check('if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then' in pull, "sourcing the script never runs the download")
check("\r" not in pull, "pull script uses LF line endings")

# 2. Behaviour, executed by bash (Git Bash on Windows).
bash = next((b for b in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")) if b and Path(b).is_file()), None)
check(bash is not None, "bash is available for the behavioural checks")
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    fixture = tmp_path / "source.pbf"
    fixture.write_bytes(b"sec015 synthetic source fixture\n")
    good = hashlib.sha256(fixture.read_bytes()).hexdigest()
    md5 = hashlib.md5(fixture.read_bytes(), usedforsecurity=False).hexdigest()
    wrong = ("0" if good[0] != "0" else "1") + good[1:]
    posix = lambda p: p.as_posix()

    def verify(expected: str, file: Path = fixture) -> subprocess.CompletedProcess:
        script = f'source "{posix(PULL)}"; verify_source_digest "{posix(file)}" "{expected}"'
        return subprocess.run([bash, "-c", script], capture_output=True, text=True)

    check(verify(good).returncode == 0, "matching SHA-256 is accepted")
    result = verify(wrong)
    check(result.returncode != 0 and "SHA-256 mismatch" in result.stderr, "different SHA-256 is rejected")
    result = verify(md5)
    check(result.returncode != 0 and "pin is missing or malformed" in result.stderr,
          "the file's own MD5 is refused as a pin (no weaker fallback)")
    check(verify(good.upper()).returncode != 0, "non-canonical uppercase digest is refused")
    check(verify("").returncode != 0, "empty pin is refused")
    check(verify(good, tmp_path / "missing.pbf").returncode != 0, "missing source file is refused")

    # Direct execution with the committed pin: no network tool may run if the pin is unset.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "invoked"
    for tool in ("curl", "osmium"):
        stub = fake_bin / tool
        stub.write_bytes(f'#!/usr/bin/env bash\necho {tool} >> "{posix(marker)}"\nexit 0\n'.encode())
        stub.chmod(0o755)
    env = dict(os.environ)
    run = subprocess.run([bash, "-c", f'export PATH="{posix(fake_bin)}:$PATH"; "{posix(PULL)}"'],
                         capture_output=True, text=True, env=env)
    if pin.group(1) == "":
        check(run.returncode != 0 and "pin is missing" in run.stderr and not marker.exists(),
              "unpinned script exits before invoking curl or osmium")
    else:
        check(True, "script is pinned; direct-run fail-closed check not applicable")

# 3. No first-party code computes MD5 for any purpose.
SCAN_DIRS = ["tools", "tests", "eval", ".github", "static", "android-app/www",
             "android-app/android/app/src", "docs"]
SUFFIXES = {".py", ".sh", ".js", ".cjs", ".mjs", ".kt", ".java", ".yml", ".yaml", ".ps1", ".html"}
MD5_COMPUTE = re.compile(r"hashlib\.md5|\bmd5sum\b|createHash\(\s*['\"]md5|getInstance\(\s*['\"]MD5"
                         r"|\bmd5\s+-q\b|openssl\s+(dgst\s+-)?md5|-Algorithm\s+MD5|crypto\.subtle\.digest\(\s*['\"]MD5", re.I)
offenders = []
for directory in SCAN_DIRS:
    for path in (ROOT / directory).rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if (not path.is_file() or path.suffix not in SUFFIXES or "/build/" in rel or "/packs/" in rel
                or "/vendor/" in rel or path.resolve() == Path(__file__).resolve()):
            continue
        if MD5_COMPUTE.search(text(path)):
            offenders.append(rel)
check(offenders == [], f"no first-party MD5 computation remains (found {offenders})")

# 4. The historical MD5 survives only as a provenance label with SHA-256 doing integrity.
label_files = sorted(
    path.relative_to(ROOT).as_posix()
    for directory in ["tools", "tests", "static", "android-app/www", "android-app/android/app/src", "data", "docs"]
    for path in (ROOT / directory).rglob("*")
    if path.is_file() and path.suffix in {".py", ".sh", ".js", ".json", ".md", ".html"}
    and "/packs/" not in path.relative_to(ROOT).as_posix()
    and path.resolve() != Path(__file__).resolve()
    and HISTORICAL_MD5 in text(path)
)
mirrors = ["static", "docs", "android-app/www"]
packaged = ROOT / "android-app/android/app/src/main/assets/public"
if (packaged / "highway-manifest.json").is_file():
    mirrors.append("android-app/android/app/src/main/assets/public")
EXPECTED_LABELS = sorted(
    [f"{m}/highway-manifest.json" for m in mirrors] + [f"{m}/standalone.js" for m in mirrors]
    + ["data/national-highways-source.json", "docs/SOURCES.md", "docs/sources.html",
       "tests/national_highway_routing_test.py", "tools/build-national-highways.py"]
)
check(label_files == EXPECTED_LABELS, f"historical source MD5 appears only as a provenance label (found {label_files})")
builder = text(ROOT / "tools/build-national-highways.py")
check("hashlib.md5" not in builder and "hashlib.sha256(data).hexdigest() == entry[\"sha256\"]" in builder,
      "catalog verification authenticates every tile by SHA-256, never MD5")
engine = text(ROOT / "static/standalone.js")
check('source.source_md5 !== "c5e0a62a1cb00c80d8c5948bf18370d7"' in engine
      and "digest !== resource.sha256" in engine,
      "runtime treats source_md5 as a fixed label and verifies tiles by SHA-256")

print(f"\nSEC-015 SOURCE DIGEST CONTRACT PASS ({checks} checks)")
