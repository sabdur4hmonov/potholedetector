#!/usr/bin/env python3
"""Prepare evidence or collect bounded, read-only metrics. Never passes a device gate."""
import argparse
import hashlib
import json
import re
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "92ccf4aa97c821fe5f0183ef281c2c506392237a"
PACKAGE = "dev.aiengg.potholereporter"


def run(command, max_output_bytes=512 * 1024):
    result = subprocess.run(command, capture_output=True, timeout=20, check=True)
    if len(result.stdout) > max_output_bytes:
        raise ValueError("Command output exceeds the evidence bound")
    return result.stdout


def prepare(apk):
    evidence = {
        "task": "REPORT-LOCAL-001", "device_gate": "OPEN/PENDING",
        "source_commit": BASELINE, "package": PACKAGE,
        "physical_device_verified": False,
        "operator": None, "device_model": None, "android_webview_versions": None,
        "physical_observation_time": None,
        "checks": {name: {"status": "PENDING", "evidence": None} for name in (
            "physical_camera", "offline_save_review", "android_force_stop_restart",
            "whole_frame_export", "device_resources_performance")},
    }
    if apk:
        with zipfile.ZipFile(apk) as archive:
            if archive.testzip() is not None:
                raise ValueError("APK CRC check failed")
            for name in ("AndroidManifest.xml", "classes.dex"):
                if name not in archive.namelist():
                    raise ValueError("APK missing " + name)
            for asset in ("index.html", "standalone.js"):
                expected = run(["git", "-c", "safe.directory=" + ROOT.as_posix(),
                                "-C", str(ROOT), "show", BASELINE + ":static/" + asset],
                               max_output_bytes=4 * 1024 * 1024)
                if archive.read("assets/public/" + asset).replace(b"\r\n", b"\n") != expected.replace(b"\r\n", b"\n"):
                    raise ValueError("APK does not package baseline " + asset)
        evidence["apk"] = {"sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                           "bytes": apk.stat().st_size, "baseline_web_assets": "MATCH",
                           "baseline_comparison": "LF/CRLF normalized text; no other differences allowed",
                           "signature_verification": "PENDING separate apksigner evidence",
                           "native_source_provenance": "requires build log/source-state review"}
    return evidence


def metrics(memory, graphics):
    def number(pattern, text):
        match = re.search(pattern, text, re.MULTILINE)
        return int(match[1]) if match else None
    return {
        "total_pss_kib": number(r"TOTAL PSS:\s*(\d+)", memory)
        or number(r"^\s*TOTAL\s+(\d+)", memory),
        "frames_since_process_start": number(r"Total frames rendered:\s*(\d+)", graphics),
        "janky_frames_since_process_start": number(r"Janky frames:\s*(\d+)", graphics),
    }


def collect(adb, serial, label, samples, interval, runner=run, sleeper=time.sleep):
    if not serial.strip() or serial.startswith("-"):
        raise ValueError("An explicit authorized device serial is required")
    if not 1 <= samples <= 20 or not 0 <= interval <= 30:
        raise ValueError("Samples must be 1..20 and interval 0..30 seconds")
    prefix = [str(adb), "-s", serial]
    if runner(prefix + ["get-state"]).decode().strip() != "device":
        raise ValueError("Selected device is not authorized/online")
    if runner(prefix + ["shell", "getprop", "ro.kernel.qemu"]).decode().strip() == "1":
        raise ValueError("Emulator metrics cannot satisfy the physical-device gate")
    rows = []
    started = time.monotonic()
    for index in range(samples):
        memory = runner(prefix + ["shell", "dumpsys", "meminfo", PACKAGE]).decode("utf-8", "replace")
        graphics = runner(prefix + ["shell", "dumpsys", "gfxinfo", PACKAGE]).decode("utf-8", "replace")
        if "No process found" in memory or "No process found" in graphics:
            raise ValueError("App process is not running")
        row = metrics(memory, graphics)
        if row["total_pss_kib"] is None:
            raise ValueError("Unsupported/missing PSS output; no resource result is claimed")
        rows.append({"sample": index + 1, "elapsed_seconds": round(time.monotonic() - started, 3), **row})
        if index + 1 < samples:
            sleeper(interval)
    return {"task": "REPORT-LOCAL-001", "device_gate": "OPEN/PENDING", "label": label,
            "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "package": PACKAGE, "samples": rows,
            "limits": "Snapshots are not peak memory, camera proof, persistence proof or an automatic performance pass. "
                      "gfxinfo is cumulative and may omit WebView rendering. Human evidence review is required."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--apk", type=Path)
    capture = commands.add_parser("collect")
    capture.add_argument("--adb", type=Path, required=True)
    capture.add_argument("--serial", required=True)
    capture.add_argument("--label", choices=("idle", "capture", "save", "review", "export", "restart"), required=True)
    capture.add_argument("--samples", type=int, default=3)
    capture.add_argument("--interval", type=float, default=2)
    for command in (prep, capture):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Refusing to overwrite existing evidence")
        evidence = prepare(args.apk) if args.action == "prepare" else collect(
            args.adb, args.serial, args.label, args.samples, args.interval)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(evidence, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        parser.exit(1, "Evidence preparation/collection failed: " + str(error) + "\n")
    print("Evidence written; physical-device gate remains OPEN/PENDING")


if __name__ == "__main__":
    main()
