"""Verify the model-bearing build, including the real ONNX JVM test, before reporting ready."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--gradle-exit', type=int, required=True)
    p.add_argument('--since', type=int, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    android = root / 'android-app/android'
    xmls = list((android / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
    if not xmls:
        raise ValueError('Missing JVM test results')
    totals = dict(tests=0, failures=0, skipped=0, errors=0)
    runtime_ran = False
    known_failure = False
    for file in xmls:
        if file.stat().st_mtime < args.since:
            raise ValueError('Stale JVM results cannot verify this model build')
        suite = ET.parse(file).getroot()
        for key in totals:
            totals[key] += int(suite.get(key, 0))
        if suite.get('name', '').endswith('.NativePotholeRuntimeTest'):
            runtime_ran = int(suite.get('tests', 0)) > 0 and all(int(suite.get(k, 0)) == 0 for k in ('skipped', 'errors', 'failures'))
        for case in suite.findall('testcase'):
            for failure in list(case.findall('failure')) + list(case.findall('error')):
                if (case.get('classname', '').endswith('.FootagePathPolicyTest') and
                    case.get('name') == 'sessionDirectoryMustRemainAStrictCanonicalChild' and
                    'A required privilege is not held' in ''.join(failure.itertext())):
                    known_failure = True
                else:
                    raise ValueError('Unexpected JVM failure')
    if not runtime_ran:
        raise ValueError('Real ONNX JVM fixtures must pass without skipping')
    if args.gradle_exit and not (known_failure and totals['failures'] == 1 and totals['errors'] == 0):
        raise ValueError('Gradle failed beyond the allowed symlink case')
    java = android / '.gradle/toolchain/jdk/bin/java.exe'
    signer = android / '.gradle/toolchain/android-sdk/build-tools/36.0.0/lib/apksigner.jar'
    manifest = json.loads((android / 'app/src/main/assets/ml/pothole_model.json').read_text())
    apks = []
    for abi in ('arm64-v8a', 'armeabi-v7a', 'x86_64'):
        apk = android / f'app/build/outputs/apk/debug/app-{abi}-debug.apk'
        subprocess.run([sys.executable, str(root / 'tools/verify-release-assets.py'), '--static', str(root/'static'),
            '--www', str(root/'android-app/www'), '--docs', str(root/'docs'), '--packaged', str(android/'app/src/main/assets/public'), '--apk', str(apk)], check=True)
        subprocess.run([str(java), '-jar', str(signer), 'verify', str(apk)], check=True)
        with zipfile.ZipFile(apk) as archive:
            if archive.testzip() or {n.split('/')[1] for n in archive.namelist() if n.startswith('lib/')} != {abi}:
                raise ValueError('APK CRC or ABI mismatch')
            if hashlib.sha256(archive.read('assets/ml/pothole_yolox_nano.onnx')).hexdigest() != manifest['sha256']:
                raise ValueError('APK model digest mismatch')
        apks.append(dict(path=str(apk), bytes=apk.stat().st_size, sha256=hashlib.sha256(apk.read_bytes()).hexdigest()))
    (args.output / 'build_report.json').write_text(json.dumps(dict(status='ready', tests=totals, real_runtime_passed=True, apks=apks), indent=2))


if __name__ == '__main__':
    main()
