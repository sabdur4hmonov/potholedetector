"""Synthetic tool tests only. No ADB invocation and no Android acceptance evidence."""
import importlib.util
import unittest
import tempfile
import zipfile
import sys
import subprocess
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location("evidence", Path(__file__).resolve().parents[1] / "tools/report-local-device-evidence.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class EvidenceTest(unittest.TestCase):
    def test_existing_evidence_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("keep original", encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(Path(tool.__file__)), "prepare", "--output", str(output)],
                                    capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep original")

    def test_subprocess_limits_are_enforced(self):
        with patch.object(tool.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"x" * (512 * 1024 + 1))) as mocked:
            with self.assertRaises(ValueError): tool.run(["synthetic"])
            self.assertEqual(mocked.call_args.kwargs["timeout"], 20)
            self.assertTrue(mocked.call_args.kwargs["check"])

    def test_apk_assets_must_match_baseline_and_still_do_not_pass_device(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / "synthetic.apk"
            for content in (b"stale", b"baseline\r\n"):
                with zipfile.ZipFile(apk, "w") as archive:
                    for name in ("AndroidManifest.xml", "classes.dex"):
                        archive.writestr(name, b"synthetic, not an Android artifact")
                    for name in ("index.html", "standalone.js"):
                        archive.writestr("assets/public/" + name, content)
                with patch.object(tool, "run", return_value=b"baseline\n"):
                    if content == b"stale":
                        with self.assertRaises(ValueError): tool.prepare(apk)
                    else:
                        record = tool.prepare(apk)
                        self.assertEqual(record["apk"]["baseline_web_assets"], "MATCH")
                        self.assertEqual(record["device_gate"], "OPEN/PENDING")

    def test_template_cannot_pass_device_gate(self):
        record = tool.prepare(None)
        self.assertEqual(record["device_gate"], "OPEN/PENDING")
        self.assertFalse(record["physical_device_verified"])
        self.assertTrue(all(row["status"] == "PENDING" for row in record["checks"].values()))

    def test_android_formats_and_unknown_values(self):
        self.assertEqual(tool.metrics("TOTAL PSS: 1200", "Total frames rendered: 30\nJanky frames: 2"),
                         {"total_pss_kib": 1200, "frames_since_process_start": 30, "janky_frames_since_process_start": 2})
        self.assertEqual(tool.metrics("  TOTAL 1400 42 10", "")["total_pss_kib"], 1400)
        self.assertIsNone(tool.metrics("unsupported", "")["total_pss_kib"])

    def test_read_only_bounded_collection_remains_pending(self):
        calls, sleeps = [], []
        def runner(command):
            calls.append(command)
            self.assertEqual(command[:3], ["adb", "-s", "synthetic-device"])
            if command[3:] == ["get-state"]: return b"device\n"
            if command[3:] == ["shell", "getprop", "ro.kernel.qemu"]: return b"0\n"
            if command[3:] == ["shell", "dumpsys", "meminfo", tool.PACKAGE]: return b"TOTAL PSS: 1234\n"
            if command[3:] == ["shell", "dumpsys", "gfxinfo", tool.PACKAGE]: return b"Total frames rendered: 10\nJanky frames: 1"
            self.fail("Unexpected command")
        record = tool.collect("adb", "synthetic-device", "save", 3, 2, runner, sleeps.append)
        self.assertEqual(len(calls), 8)
        self.assertEqual(sleeps, [2, 2])
        self.assertEqual(record["device_gate"], "OPEN/PENDING")
        self.assertEqual(len(record["samples"]), 3)

    def test_invalid_bounds_run_no_commands(self):
        for serial, count, interval in [("", 1, 0), ("-bad", 1, 0), ("x", 21, 0), ("x", 0, 0), ("x", 1, 31)]:
            with self.assertRaises(ValueError):
                tool.collect("adb", serial, "idle", count, interval, lambda _: self.fail("Command must not run"))

    def test_emulator_offline_and_missing_process_fail(self):
        with self.assertRaises(ValueError):
            tool.collect("adb", "x", "idle", 1, 0, lambda _: b"offline")
        with self.assertRaises(ValueError):
            tool.collect("adb", "x", "idle", 1, 0, lambda c: b"device" if c[-1] == "get-state" else b"1")
        with self.assertRaises(ValueError):
            tool.collect("adb", "x", "idle", 1, 0, lambda c: b"device" if c[-1] == "get-state" else b"0" if c[-1] == "ro.kernel.qemu" else b"No process found")


if __name__ == "__main__":
    unittest.main()
