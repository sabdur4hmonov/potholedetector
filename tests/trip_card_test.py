# -*- coding: utf-8 -*-
"""TRIP-003 in a real browser: the dashboard lists trips with a coloured safe-driving score,
and Share produces a story-sized PNG without exact start/end places."""
import math
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


def track(seconds, speed=12.0, brake_every=None):
    lat0, lng0 = 41.3111, 69.2797
    per_lng = 111320 * math.cos(math.radians(lat0))
    rows, x, v = [], 0.0, speed
    for t in range(seconds):
        if brake_every and t % brake_every in (1, 2):
            v = max(3.0, v - 4.5)
        elif v < speed:
            v = min(speed, v + 1.0)
        rows.append([t, lat0, lng0 + x / per_lng, 5, v, 90])
        x += v
    return rows


DRIVES = [
    {"id": "smooth", "started_at": 1_800_000_000, "gps_track": track(300)},
    {"id": "rough", "started_at": 1_800_090_000, "gps_track": track(300, brake_every=25)},
    {"id": "short", "started_at": 1_800_100_000, "gps_track": track(30)},
    {"id": "no-track", "started_at": 1_800_200_000, "gps_track": []},
]
REPORTS = [{"id": 1, "drive_id": "smooth", "status": "draft"},
           {"id": 2, "drive_id": "smooth", "status": "rejected"}]

source = (ROOT / "static/index.html").read_text()
require("the card never draws a top speed", "max_interval_speed" not in source.split("function drawTripCard")[1].split("async function shareTripCard")[0])
require("both languages label the card", source.count("card_privacy:") == 2 and source.count("grade_green:") == 2)

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page(accept_downloads=True)
    page.goto(APP)
    page.wait_for_function("() => typeof renderTrips === 'function' && window.TripStats")
    page.evaluate("([d, r]) => renderTrips(d, r)", [DRIVES, REPORTS])
    rows = page.locator("#dashTrips [data-trip]")
    require("only trips with a GPS track are listed, newest first",
            rows.evaluate_all("els => els.map(e => e.dataset.trip)") == ["short", "rough", "smooth"])
    smooth = page.locator('#dashTrips [data-trip="smooth"]').inner_text()
    rough = page.locator('#dashTrips [data-trip="rough"]').inner_text()
    require("a smooth trip is scored 100 and excellent", "100" in smooth and "Excellent" in smooth)
    require("hard braking is shown and lowers the grade",
            "hard brakes" in rough and "Excellent" not in rough)
    require("a trip too short to score has no share button",
            "too short to score" in page.locator('#dashTrips [data-trip="short"]').inner_text()
            and page.locator('#dashTrips [data-trip="short"] [data-sharetrip]').count() == 0)
    size = page.evaluate("() => { const c = drawTripCard(tripCards.get('smooth')); return [c.width, c.height]; }")
    require("the card is story sized", size == [1080, 1920])
    with page.expect_download() as info:
        page.locator('#dashTrips [data-sharetrip="smooth"]').dispatch_event('click')
    download = info.value
    path = download.path()
    data = pathlib.Path(path).read_bytes()
    require("Share produces a PNG file", download.suggested_filename == "trip-2027-01-15.png"
            and data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 10_000)
    browser.close()

print("trip card checks passed")
