# -*- coding: utf-8 -*-
"""Offline road warnings: the page hands its own open potholes to native Drive, which
announces the ones ahead. Source contract plus real-browser hazard selection and banner."""
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"
DRIVE = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive"
PLUGIN = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt"
MANIFEST = ROOT / "android-app/android/app/src/main/AndroidManifest.xml"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


engine = (DRIVE / "RoadAlertEngine.kt").read_text()
speaker = (DRIVE / "RoadAlertSpeaker.kt").read_text()
service = (DRIVE / "DriveForegroundService.kt").read_text()
plugin = PLUGIN.read_text()
web = (ROOT / "static/index.html").read_text()
js = (ROOT / "static/standalone.js").read_text()

require("the alert engine and speaker have no network path",
        all(term not in engine + speaker for term in ("okhttp", "HttpURLConnection", "java.net.URL")))
require("speech uses the phone's offline engine with Uzbek, then Russian, then English",
        'listOf(language, "ru", "en").distinct()' in speaker
        and "USAGE_ASSISTANCE_NAVIGATION_GUIDANCE" in speaker)
require("Android 11+ can see the text-to-speech engine",
        "android.intent.action.TTS_SERVICE" in MANIFEST.read_text())
require("every location fix is checked against the hazards while Drive is active",
        "handleRoadAlert(fix)" in service
        and "if (!sessionRunning || isPaused || isStopping) return" in service)
require("alerts are released with the rest of Drive",
        service.count("stopRoadAlerts()") >= 4)
require("the hazard list is bounded and staged in-process, not in an Intent extra",
        "DriveForegroundService.stageRoadHazards(hazards)" in plugin
        and "minOf(array.length(), RoadAlertEngine.MAX_HAZARDS)" in plugin
        and "const val MAX_HAZARDS = 20_000" in engine)
require("the page sends its hazards and both switches to native Drive",
        "hazards: roadHazards," in web and "roadAlerts: roadAlertsEnabled()," in web
        and "voiceAlerts: voiceAlertsEnabled()," in web)
require("both languages describe the warnings",
        web.count("road_alerts_label:") == 2 and web.count("road_alerts_note:") == 2)
require("mirrors carry the same web assets",
        (ROOT / "android-app/www/index.html").read_text() == web
        and (ROOT / "docs/standalone.js").read_text() == js)

REPORTS = [
    {"id": 1, "status": "draft", "issue_type": "road_damage", "lat": 41.31, "lng": 69.28,
     "report_origin": "ai_detection", "created_at": 100},
    {"id": 2, "status": "draft", "issue_type": "road_damage", "lat": 41.32, "lng": 69.29,
     "report_origin": "sensor_detected", "created_at": 200},
    {"id": 3, "status": "draft", "issue_type": "road_damage", "lat": 41.33, "lng": 69.30,
     "report_origin": "sensor_detected", "human_label": "pothole_cavity", "created_at": 300},
    {"id": 4, "status": "draft", "issue_type": "road_damage", "lat": 41.34, "lng": 69.31,
     "report_origin": "sensor_detected", "human_label": "not_reportable", "created_at": 400},
    {"id": 5, "status": "draft", "issue_type": "road_damage", "lat": 41.35, "lng": 69.32,
     "condition_status": "fixed", "created_at": 500},
    {"id": 6, "status": "rejected", "issue_type": "road_damage", "lat": 41.36, "lng": 69.33,
     "created_at": 600},
    {"id": 7, "status": "draft", "issue_type": "road_damage", "lat": None, "lng": None,
     "report_origin": "user_reported", "created_at": 700},
    {"id": 8, "status": "draft", "issue_type": "road_damage", "lat": 41.38, "lng": 69.35,
     "report_origin": "user_reported", "created_at": 800},
]

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.goto(APP)
    page.wait_for_function("() => !!(window.StandaloneAPI && window.StandaloneAPI.__pure)")
    hazards = page.evaluate("(r) => window.StandaloneAPI.__pure.roadHazardsFrom(r)", REPORTS)
    require("open, located, not-rejected reports become hazards, newest first",
            [h["id"] for h in hazards] == ["r8", "r3", "r2", "r1"])
    kinds = {h["id"]: h["kind"] for h in hazards}
    require("an unlabelled shock warns as rough road; a confirmed one as a pothole",
            kinds == {"r8": "pothole", "r3": "pothole", "r2": "road_shock", "r1": "pothole"})
    require("hazards carry only an id, kind and coordinates",
            all(set(h) == {"id", "kind", "lat", "lng"} for h in hazards))
    empty = page.evaluate("() => window.StandaloneAPI.handle('/api/road-hazards', { method: 'GET' })")
    require("the endpoint answers from local storage", empty == {"hazards": []})

    page.evaluate("() => showNativeRoadAlert({ alertText: '500 metrdan keyin chuqur. Sekinlang.', alertAgeMs: 1000 })")
    banner = page.locator("#nativeAlertBanner")
    require("a fresh alert shows on the Drive screen",
            "hidden" not in (banner.get_attribute("class") or "")
            and banner.text_content() == "500 metrdan keyin chuqur. Sekinlang.")
    page.evaluate("() => showNativeRoadAlert({ alertText: 'old', alertAgeMs: 9000 })")
    require("an old alert is hidden", "hidden" in (banner.get_attribute("class") or ""))
    page.evaluate("() => showNativeRoadAlert({ alertText: 'x', alertAgeMs: 100, isPaused: true })")
    require("no alert while paused", "hidden" in (banner.get_attribute("class") or ""))
    browser.close()

print("road alert checks passed")
