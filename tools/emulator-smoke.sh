#!/usr/bin/env bash
# Installs the debug APK on a running emulator, starts the app, and writes what happened to
# text files: crash traces, WebView console output and the visible on-screen text.
# Used by CI only; it never touches signing material and needs no network service.
set -u
APK=${1:?apk path}
OUT=${2:?output directory}
PKG=dev.aiengg.potholereporter
mkdir -p "$OUT"

adb install -r "$APK" > "$OUT/install.txt" 2>&1
adb logcat -c
adb shell pm grant $PKG android.permission.CAMERA > /dev/null 2>&1 || true
adb shell pm grant $PKG android.permission.ACCESS_FINE_LOCATION > /dev/null 2>&1 || true
adb shell am start -W -n $PKG/.MainActivity > "$OUT/start.txt" 2>&1
sleep 20

adb shell uiautomator dump /sdcard/ui.xml > /dev/null 2>&1
adb pull /sdcard/ui.xml "$OUT/ui.xml" > /dev/null 2>&1 || true
python3 - "$OUT" <<'PY'
import re, sys, pathlib
out = pathlib.Path(sys.argv[1])
xml = (out / "ui.xml").read_text(errors="replace") if (out / "ui.xml").exists() else ""
texts = [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]
descs = [t for t in re.findall(r'content-desc="([^"]*)"', xml) if t.strip()]
(out / "ui-text.txt").write_text("VISIBLE TEXT:\n" + "\n".join(texts) + "\nCONTENT-DESC:\n" + "\n".join(descs) + "\n")
PY
adb shell pidof $PKG > "$OUT/pid.txt" 2>&1
adb logcat -d -v time > "$OUT/logcat-full.txt" 2>&1
grep -E "AndroidRuntime|FATAL|Process: $PKG|Caused by|at dev\.aiengg" "$OUT/logcat-full.txt" | head -80 > "$OUT/crash.txt"
grep -E "chromium|Capacitor|CONSOLE|Uncaught|SecurityError|Refused to" "$OUT/logcat-full.txt" | head -80 > "$OUT/webview.txt"
echo "pid after launch: $(cat "$OUT/pid.txt")" >> "$OUT/start.txt"
exit 0
