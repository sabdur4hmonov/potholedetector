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

# Read the page state through the WebView debugger (debug builds only).
APPPID0=$(adb shell pidof $PKG | tr -d '\r')
if [ -n "$APPPID0" ]; then
  adb forward tcp:9222 localabstract:webview_devtools_remote_$APPPID0 > /dev/null 2>&1
  pip install --quiet websocket-client > /dev/null 2>&1 || true
  python3 - "$OUT" <<'PY' || true
import json, sys, urllib.request, pathlib
out = pathlib.Path(sys.argv[1])
res = []
try:
    import websocket
    tabs = json.load(urllib.request.urlopen("http://localhost:9222/json", timeout=10))
    res.append("targets: " + ", ".join(t.get("url", "?") for t in tabs))
    page = [t for t in tabs if t.get("type") == "page"][0]
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15)
    def ev(expr, i):
        ws.send(json.dumps({"id": i, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == i:
                return m.get("result", {}).get("result", {}).get("value", m)
    res.append("homeHidden: %s" % ev("(function(){var h=document.getElementById('home');return h?String(h.hidden)+' display='+getComputedStyle(h).display:'no #home'})()", 1))
    res.append("bootError: %s" % ev("(function(){var b=document.getElementById('bootErrorBox');return b?b.innerText:'none'})()", 2))
    res.append("bodyText: %s" % str(ev("document.body.innerText.slice(0,1500)", 3)))
    res.append("title: %s" % ev("document.title", 4))
except Exception as e:
    res.append("devtools failed: %r" % (e,))
(out / "page-state.txt").write_text("\n".join(res) + "\n")
PY
fi
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
adb logcat -b crash -d -v time > "$OUT/crash-buffer.txt" 2>&1
APPPID=$(grep -oE "Start proc [0-9]+:$PKG" "$OUT/logcat-full.txt" | head -1 | grep -oE "[0-9]+" | head -1)
{
  echo "app pid: ${APPPID:-unknown}"
  echo "--- crash buffer ---"
  head -60 "$OUT/crash-buffer.txt"
  echo "--- process death / signals ---"
  grep -E "$PKG.*(died|crash|ANR)|am_crash|am_proc_died|Fatal signal|SIGSEGV|SIGABRT|Force finishing|Exception thrown" "$OUT/logcat-full.txt" | head -20
} > "$OUT/crash.txt"
if [ -n "${APPPID:-}" ]; then
  grep -E "\( *$APPPID\)" "$OUT/logcat-full.txt" | grep -vE "BoundaryInterfaceReflectionUtil|WebMessageListenerHolder|cr_AWNetworkFetcherTask" | tail -70 > "$OUT/webview.txt"
else
  grep -E "chromium|Capacitor|CONSOLE|Uncaught|SecurityError|Refused to" "$OUT/logcat-full.txt" | head -60 > "$OUT/webview.txt"
fi
echo "pid after launch: $(cat "$OUT/pid.txt")" >> "$OUT/start.txt"
exit 0
