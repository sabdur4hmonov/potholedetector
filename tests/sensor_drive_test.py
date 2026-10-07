# -*- coding: utf-8 -*-
"""AI-free sensor Drive: native wiring contract plus real-browser import/display/export.

Drive must start without an AI key in the native app and then use only the phone's
accelerometer and complete camera frames. A sensor report is stored as an unverified
road shock, never as a confirmed pothole, deduplicates with later shocks at the same
place, and becomes training data once the owner labels it. No external service is
contacted.
"""
import base64
import io
import json
import pathlib
import re

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"
DRIVE = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive"
PLUGIN = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


# ---------- native source contract ----------
plugin = PLUGIN.read_text()
service = (DRIVE / "DriveForegroundService.kt").read_text()
sensor = (DRIVE / "SensorDriveDetector.kt").read_text()
monitor = (DRIVE / "RoadBumpMonitor.kt").read_text()
detector_api = (DRIVE / "DriveDetector.kt").read_text()
web = (ROOT / "static/index.html").read_text()
engine = (ROOT / "static/standalone.js").read_text()

require("Drive no longer refuses to start without an OpenAI key",
        'call.reject("An OpenAI API key is required")' not in plugin
        and "DriveDetectionMode.resolve(call.getString(\"detectionMode\"), apiKey.isNotBlank())" in plugin)
require("sensor mode never hands the stored key to the service",
        "if (detectionMode == DriveDetectionMode.CLOUD) apiKey else \"\"" in plugin)
require("without a key the only possible mode is sensor",
        "if (!hasApiKey || requested == SENSOR) SENSOR else CLOUD" in detector_api)
require("the service picks the sensor detector and starts the accelerometer only in sensor mode",
        "if (detectionMode == DriveDetectionMode.SENSOR) SensorDriveDetector(" in service
        and "if (sensorDetector != null) {" in service
        and "RoadBumpMonitor(" in service)
require("the accelerometer is released on Stop, failed start and service destruction",
        service.count("stopBumpMonitor()") >= 4)
require("the sensor detector has no network path",
        not re.search(r"okhttp|HttpURLConnection|java\.net\.URL|NativeInferenceTransport", sensor))
require("sensor evidence is the complete primary frame, downscaled only",
        "FrameQualityEvaluator.bitmapToBoundedJpegBytes(\n            primary.bitmap," in sensor
        and "createBitmap" not in sensor and "crop" not in sensor.lower().replace("no crop", ""))
require("sensor mode never claims a repair",
        "): RepairVerificationResult? = null" in sensor)
require("sensor reports are marked as unverified candidates",
        'const val SENSOR_DECISION = "sensor_candidate"' in sensor
        and "isPothole = 0," in sensor and "size = null," in sensor)
require("the accelerometer needs no permission and runs at 50 Hz",
        "SAMPLING_PERIOD_US = 20_000" in monitor and "TYPE_ACCELEROMETER" in monitor)
require("the web app lets native Drive start without a key but keeps browser Drive gated",
        "if (!window.CredentialBroker.hasOpenAi() && !nativePlugin) {" in web
        and 'detectionMode: savedDetectionMode() === "sensor" ? "sensor" : "cloud",' in web)
require("both languages describe the sensor mode",
        web.count("sensor_verdict:") == 2 and web.count("sensor_note:") == 2
        and web.count("damage_road_shock:") == 2)
require("mirrors carry the same web assets",
        (ROOT / "android-app/www/index.html").read_text() == web
        and (ROOT / "android-app/www/standalone.js").read_text() == engine
        and (ROOT / "docs/standalone.js").read_text() == engine)


# ---------- browser behaviour ----------
def jpeg_data_url():
    out = io.BytesIO()
    Image.new("RGB", (64, 36), (90, 90, 90)).save(out, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


PHOTO = jpeg_data_url()


def sensor_payload(native_id, drive, lat, lng, **extra):
    payload = {
        "id": native_id, "created_at": 1_800_000_000, "lat": lat, "lng": lng,
        "address": "Road coordinates", "photo_data_url": PHOTO, "photo_full_data_url": PHOTO,
        "is_reportable": 0, "is_pothole": 0, "looks_like_speed_breaker": False,
        "damage_type": "road_shock", "decision": "sensor_candidate",
        "capture_source": "drive_sensor", "assessment": "sensor", "size": None,
        "description": "Road shock felt by the phone sensor (9.4 m/s², 32 km/h). Not verified.",
        "drive_id": drive, "source_event_key": f"sensor:{drive}:{native_id}",
        "captured_at": 1_800_000_000 + native_id, "source_offset_s": 12.0,
        "gps_accuracy": 5.0, "speed_mps": 9.0, "heading": 90.0,
        "schema_version": 1, "prompt_version": "sensor-shock-v1",
        "seen_count": 1, "last_seen_at": 1_800_000_000 + native_id,
        "debug_capture": False,
    }
    payload.update(extra)
    return payload


BLOCK_NETWORK = r"""
(() => {
  const realFetch = window.fetch.bind(window);
  window.__externalCalls = 0;
  window.fetch = (url, init) => {
    const target = String(url);
    if (/^https?:\/\/(localhost|127\.0\.0\.1)/.test(target) || !/^https?:/.test(target)) {
      return realFetch(url, init);
    }
    window.__externalCalls++;
    return Promise.reject(new TypeError("offline test"));
  };
})();
"""

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.add_init_script(BLOCK_NETWORK)
    page.goto(APP)
    page.wait_for_function("() => !!(window.StandaloneAPI && window.StandaloneAPI.handle)")

    def call(path, method="GET", body=None):
        return page.evaluate(
            "([path, method, body]) => window.StandaloneAPI.handle(path, body == null"
            " ? { method } : { method, body: JSON.stringify(body) })",
            [path, method, body],
        )

    first = call("/api/native-report", "POST", sensor_payload(1, "drive-a", 41.311000, 69.279000))
    require("a sensor candidate is imported", not first.get("ignored") and first.get("id"))
    reports = call("/api/reports")
    rows = reports if isinstance(reports, list) else reports.get("reports", [])
    rec = next(r for r in rows if r["id"] == first["id"])
    require("it is stored as an unverified road shock, not a pothole",
            rec["report_origin"] == "sensor_detected" and rec["is_pothole"] is None
            and rec["damage_type"] == "road_shock" and rec["decision"] == "sensor_candidate"
            and rec["status"] == "draft" and rec["size"] is None
            and rec["capture_source"] == "drive_sensor")
    require("the UI calls it a phone-felt shock, never 'Pothole: YES'",
            page.evaluate("(r) => detectionVerdict(r)", rec)
            == page.evaluate("() => t('sensor_verdict')")
            and page.evaluate("(r) => tDamage(r)", rec) == page.evaluate("() => t('sensor_verdict')"))

    again = call("/api/native-report", "POST", sensor_payload(2, "drive-b", 41.311012, 69.279010))
    require("a later shock at the same place merges into the same event", again.get("duplicate") is True
            and again.get("id") == first["id"])
    elsewhere = call("/api/native-report", "POST", sensor_payload(3, "drive-b", 41.320000, 69.290000))
    require("a shock elsewhere is a separate event",
            not elsewhere.get("duplicate") and elsewhere.get("id") != first["id"])

    bad = call("/api/native-report", "POST",
               sensor_payload(4, "drive-c", 41.33, 69.30, decision="accept"))
    require("a sensor row that claims an AI accept is refused",
            bad.get("ignored") is True and bad.get("reason") == "invalid_sensor_candidate")
    no_photo = call("/api/native-report", "POST",
                    sensor_payload(5, "drive-c", 41.34, 69.31, photo_data_url=None))
    require("a sensor row without its frame is refused", no_photo.get("ignored") is True)

    call(f"/api/reports/{first['id']}/label", "POST", {"label": "pothole_cavity"})
    exported = call("/api/export", "POST")
    require("once labelled, the shock frame becomes exportable training data",
            exported.get("count") == 1)
    browser.close()

print("sensor drive checks passed")
