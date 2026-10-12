# -*- coding: utf-8 -*-
"""DATA-001: one road event followed through every step a report takes, in a real browser,
checking the stored shape and the privacy of what leaves each step:
native import -> stored record -> duplicate merge -> refusals -> label -> export ->
road warnings -> community payloads -> progress -> delete."""
import base64
import io
import json
import zipfile

from playwright.sync_api import sync_playwright

APP = "http://localhost:8765/"
NOW = 1_800_000_000


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


# A small real JPEG made here, so the export really decodes and packs an image.
from PIL import Image  # noqa: E402

_buffer = io.BytesIO()
Image.new("RGB", (8, 6), (90, 92, 96)).save(_buffer, "JPEG", quality=80)
JPEG = "data:image/jpeg;base64," + base64.b64encode(_buffer.getvalue()).decode()


def native(native_id, drive, lat, lng, **extra):
    row = {"id": native_id, "created_at": NOW + native_id, "lat": lat, "lng": lng, "address": "Amir Temur",
           "photo_data_url": JPEG, "photo_full_data_url": JPEG, "is_reportable": 0, "is_pothole": 0,
           "damage_type": "road_shock", "decision": "sensor_candidate", "capture_source": "drive_sensor",
           "assessment": "sensor", "description": "Road shock felt by the phone sensor.", "drive_id": drive,
           "source_event_key": f"sensor:{drive}:{native_id}", "captured_at": NOW + native_id,
           "source_offset_s": 12.5, "gps_accuracy": 4.0, "speed_mps": 9.5, "heading": 450.0,
           "schema_version": 1, "prompt_version": "sensor-shock-v1", "seen_count": 1,
           "last_seen_at": NOW + native_id, "debug_capture": False}
    row.update(extra)
    return row


REQUIRED = {"id": int, "created_at": (int, float), "lat": float, "lng": float, "status": str,
            "issue_type": str, "report_origin": str, "damage_type": str, "decision": str,
            "capture_source": str, "drive_id": str, "source_event_key": str, "source_event_keys": list,
            "captured_at": (int, float), "gps_accuracy": (int, float), "speed_mps": (int, float),
            "heading": (int, float), "event_sightings": list, "seen_count": int}

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.add_init_script("window.fetch = ((real) => (url, init) => /^https?:\\/\\/(localhost|127\\.0\\.0\\.1)/.test(String(url))"
                         " || !/^https?:/.test(String(url)) ? real(url, init) : Promise.reject(new TypeError('offline')))(window.fetch.bind(window));")
    page.goto(APP)
    page.wait_for_function("() => window.StandaloneAPI && window.TripStats")

    def call(path, method="GET", body=None):
        return page.evaluate("([path, method, body]) => window.StandaloneAPI.handle(path, body == null"
                             " ? { method } : { method, body: JSON.stringify(body) })", [path, method, body])

    def reports():
        rows = call("/api/reports")
        return rows if isinstance(rows, list) else rows.get("reports", [])

    # 1. import
    first = call("/api/native-report", "POST", native(1, "drive-a", 41.311000, 69.279000))
    rec = next(r for r in reports() if r["id"] == first["id"])
    require("an imported report has every required field with the right type",
            all(k in rec and isinstance(rec[k], t) for k, t in REQUIRED.items()))
    require("its values are what the phone measured, normalised",
            rec["lat"] == 41.311 and rec["lng"] == 69.279 and rec["gps_accuracy"] == 4.0
            and rec["speed_mps"] == 9.5 and rec["heading"] == 90.0 and rec["status"] == "draft"
            and rec["drive_id"] == "drive-a" and rec["source_event_keys"] == ["sensor:drive-a:1"]
            and len(rec["event_sightings"]) == 1 and rec["seen_count"] == 1)
    require("it is an unverified candidate, never a confirmed pothole",
            rec["is_pothole"] is None and rec["decision"] == "sensor_candidate" and rec["size"] is None)
    require("the photo is kept and readable", page.evaluate(
        "async (id) => { const r = (await StandaloneAPI.handle('/api/reports', {method:'GET'})).find(x => x.id === id);"
        " return !!(r.photo_url || r.photo_data_url || r.photo); }", rec["id"]))

    # 2. the same place on a later drive merges
    again = call("/api/native-report", "POST", native(2, "drive-b", 41.311010, 69.279012))
    rows = reports()
    merged = next(r for r in rows if r["id"] == first["id"])
    require("the same pothole seen again merges into one report and remembers both drives",
            again.get("duplicate") is True and len([r for r in rows if r.get("capture_source") == "drive_sensor"]) == 1
            and merged["seen_count"] >= 2 and set(merged.get("sighting_drive_ids", [])) >= {"drive-a", "drive-b"})
    other = call("/api/native-report", "POST", native(3, "drive-b", 41.320000, 69.290000))
    require("a pothole 1.3 km away is a separate report", not other.get("duplicate") and other["id"] != first["id"])

    # 3. refusals
    refused = [call("/api/native-report", "POST", native(10 + i, "drive-c", 41.33, 69.30, **bad)) for i, bad in enumerate([
        {"photo_data_url": None}, {"decision": "accept"}, {"damage_type": "pothole_cavity"},
        {"capture_source": "drive_ondevice"}])]
    require("rows that are incomplete or claim more than the sensor knows are refused",
            all(r.get("ignored") for r in refused))
    bad_location = page.evaluate("""(row) => StandaloneAPI.handle('/api/native-report', {method:'POST', body: JSON.stringify(row)})
        .then(() => 'stored', (e) => String(e && e.message))""", native(20, "drive-c", 95.0, 69.30))
    require("an impossible location is an error, not a report",
            bad_location != "stored" and len(reports()) == 2)

    # 4. label and export
    call(f"/api/reports/{first['id']}/label", "POST", {"label": "pothole_cavity"})
    exported = call("/api/export", "POST")
    require("a labelled report is exported exactly once", exported.get("count") == 1)
    z = zipfile.ZipFile(io.BytesIO(base64.b64decode(exported["base64"])))
    labels = json.loads(z.read("labels.json"))
    item = labels["images"][0]
    require("the export holds the image and a labels.json entry with the human label and place",
            labels["count"] == 1 and item["path"] in z.namelist() and z.read(item["path"])[:2] == b"\xff\xd8"
            and item["label"] == "pothole_cavity" and item["labelled_by"] == "owner"
            and item["lat"] == 41.311 and item["drive_id"] == "drive-a"
            and item["model_said"]["decision"] == "sensor_candidate")

    # 5. warnings
    hazards = call("/api/road-hazards")["hazards"]
    own = {h["id"]: h for h in hazards if h["id"].startswith("r")}
    require("a pothole label turns the shock into a pothole warning; the unlabelled one stays a road shock",
            own[f"r{first['id']}"]["kind"] == "pothole" and own[f"r{other['id']}"]["kind"] == "road_shock")

    # 6. community payloads: only coordinates and kind, and a later "not a pothole" is taken back
    pure = "window.StandaloneAPI.__pure"
    points = page.evaluate(f"async () => {pure}.communityPotholePayloads(await StandaloneAPI.handle('/api/reports', {{method:'GET'}}), [])")
    require("shared points carry only an id, coordinates and kind, rounded to 6 decimals",
            len(points) == 2 and all(set(pt) == {"id", "lat", "lng", "kind"} for pt in points)
            and all(round(pt["lat"], 6) == pt["lat"] for pt in points))
    call(f"/api/reports/{other['id']}/label", "POST", {"label": "not_pothole"})
    gone = page.evaluate(f"async (sent) => {pure}.communityGonePayloads(await StandaloneAPI.handle('/api/reports', {{method:'GET'}}), sent, [])",
                         [pt["id"] for pt in points])
    require("relabelling a shared report as not a pothole produces exactly one take-back",
            [g["id"] for g in gone] == [f"r{other['id']}"])
    require("and it leaves the warnings",
            f"r{other['id']}" not in {h["id"] for h in call("/api/road-hazards")["hazards"]})

    # 7. progress counts what was really found
    progress = page.evaluate("async () => TripStats.progressSummary(await StandaloneAPI.handle('/api/reports', {method:'GET'}), [], Date.now() / 1000)")
    require("progress counts both found reports and both labels",
            progress["points"] == 2 * 10 + 2 * 3)

    # 8. delete
    call(f"/api/reports/{other['id']}", "DELETE")
    require("a deleted report is gone from the list and the warnings",
            [r["id"] for r in reports()] == [first["id"]]
            and f"r{other['id']}" not in {h["id"] for h in call("/api/road-hazards")["hazards"]})
    browser.close()

print("report data flow checks passed")
