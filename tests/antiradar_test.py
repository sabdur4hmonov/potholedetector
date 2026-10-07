# -*- coding: utf-8 -*-
"""Antiradar: official camera list import (JS and the Python pack builder agree), camera
hazards for warnings, the GPS-only warning service wiring, and the Settings import flow.
The fixture is synthetic; none of its points is a real camera."""
import importlib.util
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"
FIXTURE = ROOT / "tests/fixtures/cameras-synthetic.csv"
DRIVE = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive"
PLUGIN = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


spec = importlib.util.spec_from_file_location("build_camera_pack", ROOT / "tools/build-camera-pack.py")
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)

csv_text = FIXTURE.read_text(encoding="utf-8")
pack, rejected = builder.build(csv_text, "synthetic", "2026-10-07")
EXPECTED = [("SYNTH-1", "speed", 90.0, 60), ("SYNTH-2", "seatbelt", None, None),
            ("SYNTH-3", "red_light", 270.0, None), ("speed:41.318000,69.287000:180", "speed", 180.0, 70)]
require("the pack builder keeps the valid rows and normalises aliases",
        [(c["id"], c["type"], c["heading"], c["limit"]) for c in pack["cameras"]] == EXPECTED)
require("the pack builder names every rejected row",
        [r.split(":")[1].strip() for r in rejected] == [
            "bad coordinates", "unknown type 'ufo'", "heading must be 0-360 degrees",
            "limit must be a whole number from 5 to 200 km/h", "duplicate id 'SYNTH-1'"])
require("the pack declares its schema", pack["schema"] == "uz-road-cameras-v1")

service = (DRIVE / "RoadAlertService.kt").read_text()
plugin = PLUGIN.read_text()
manifest = (ROOT / "android-app/android/app/src/main/AndroidManifest.xml").read_text()
web = (ROOT / "static/index.html").read_text()
require("antiradar is a location-only foreground service",
        'android:name=".drive.RoadAlertService"' in manifest
        and 'android:foregroundServiceType="location"' in manifest.split('.drive.RoadAlertService"')[1][:200]
        and "ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION" in service)
require("antiradar uses no camera and no network",
        all(term not in service for term in ("androidx.camera", "android.hardware.camera", "CameraManager", "okhttp", "java.net.URL", "HttpURLConnection")))
require("its notification can always stop it",
        ".setDeleteIntent(stop)" in service and "ACTION_STOP" in service)
require("antiradar refuses to start without location or while Drive runs, and Drive stops it",
        'call.reject("Precise Location permission is required for road warnings")' in plugin
        and 'call.reject("Drive is running and already gives these warnings")' in plugin
        and plugin.index("RoadAlertService.stop(context)") < plugin.index("DriveForegroundService.stageRoadHazards(hazards)"))
require("the home screen asks only for location and notification permission",
        "requestNativeDrivePermissions(DASHCAM_CAPTURE_SOURCE)" in web)
require("both languages describe antiradar and camera import",
        web.count("cameras_note:") == 2 and web.count("alerts_empty:") == 2)

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.goto(APP)
    page.wait_for_function("() => !!(window.StandaloneAPI && window.StandaloneAPI.__pure)")
    js = page.evaluate("(text) => window.StandaloneAPI.__pure.parseCameraPack(text, 'cameras.csv')", csv_text)
    require("the app parses the same CSV to the same cameras as the builder",
            [(c["id"], c["type"], c["heading"], c["limit"]) for c in js["cameras"]] == EXPECTED
            and len(js["skipped"]) == len(rejected))
    from_json = page.evaluate("(text) => window.StandaloneAPI.__pure.parseCameraPack(text, 'pack.json')",
                              json.dumps(pack, ensure_ascii=False))
    require("the app accepts the builder's JSON pack",
            [c["id"] for c in from_json["cameras"]] == [c[0] for c in EXPECTED]
            and from_json["source"] == "synthetic" and from_json["updated"] == "2026-10-07")
    semicolon = "lat;lng;type;limit\n41,3111;69,2797;speed;60\n"
    parsed = page.evaluate("(text) => window.StandaloneAPI.__pure.parseCameraPack(text, 'excel.csv')", semicolon)
    require("a semicolon Excel export with decimal commas is read correctly",
            parsed["cameras"][0]["lat"] == 41.3111 and parsed["cameras"][0]["limit"] == 60)

    def error_of(text):
        return page.evaluate("""(text) => { try { window.StandaloneAPI.__pure.parseCameraPack(text, 'x');
            return null; } catch (e) { return e.message; } }""", text)
    require("files without the required columns, broken JSON or the wrong schema are refused",
            "lat, lng and type" in (error_of("a,b,c\n1,2,3\n") or "")
            and "not valid JSON" in (error_of("{broken") or "")
            and "uz-road-cameras-v1" in (error_of('{"schema":"other","cameras":[]}') or "")
            and "No usable cameras" in (error_of("lat,lng,type\n0,0,speed\n") or ""))

    def call(path, method="GET", body=None):
        return page.evaluate(
            "([path, method, body]) => window.StandaloneAPI.handle(path, body == null"
            " ? { method } : { method, body: JSON.stringify(body) })", [path, method, body])

    require("no list is stored at first", call("/api/cameras") == {"count": 0})
    page.on("dialog", lambda dialog: dialog.accept())
    page.set_input_files("#cameraFile", str(FIXTURE))
    page.wait_for_function("() => /4/.test(document.getElementById('camerasSummary').textContent)")
    summary = call("/api/cameras")
    require("importing the file from Settings stores the list on the phone",
            summary["count"] == 4 and summary["source"] == "cameras-synthetic.csv"
            and summary["by_type"] == {"speed": 2, "seatbelt": 1, "red_light": 1})
    hazards = call("/api/road-hazards")["hazards"]
    by_id = {h["id"]: h for h in hazards}
    require("cameras become warnings with their type, direction and limit",
            by_id["cSYNTH-1"] == {"id": "cSYNTH-1", "kind": "speed_camera", "lat": 41.3111,
                                  "lng": 69.2797, "heading": 90, "speed_limit": 60}
            and by_id["cSYNTH-2"]["kind"] == "seatbelt_camera" and by_id["cSYNTH-2"]["heading"] is None
            and by_id["cSYNTH-3"]["kind"] == "red_light_camera")
    call("/api/cameras", "DELETE")
    require("the list can be removed", call("/api/cameras") == {"count": 0}
            and call("/api/road-hazards") == {"hazards": []})
    browser.close()

print("antiradar checks passed")
