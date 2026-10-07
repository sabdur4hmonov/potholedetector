# -*- coding: utf-8 -*-
"""The app's community client against the real community server (in-process) and a fake
OSRM. The page is served with COMMUNITY_SERVER and its CSP pointed at https://api.test.uz,
whose requests Playwright forwards to the local server. Checks opt-in, what is sent,
rankings, shared potholes in warnings, routing, deletion, and the build tool."""
import importlib.util
import json
import math
import pathlib
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"
ORIGIN = "https://api.test.uz"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


cs = load("community_server", ROOT / "server/community_server.py")
tool = load("set_community_server", ROOT / "tools/set-community-server.py")

# ---- the build tool changes the constant and the CSP together, and can undo it ----
with tempfile.TemporaryDirectory() as tmp:
    engine = pathlib.Path(tmp, "standalone.js")
    page = pathlib.Path(tmp, "index.html")
    shutil.copy(ROOT / "static/standalone.js", engine)
    shutil.copy(ROOT / "static/index.html", page)
    original_engine, original_page = engine.read_text(), page.read_text()
    tool.ENGINE, tool.PAGE = engine, page
    tool.apply("https://api.example.uz")
    require("the tool sets the server and allows exactly that origin in the CSP",
            'const COMMUNITY_SERVER = "https://api.example.uz";' in engine.read_text()
            and tool.BASE_CONNECT + " https://api.example.uz;" in page.read_text())
    tool.apply("")
    require("the tool can remove it again", engine.read_text() == original_engine and page.read_text() == original_page)
    require("the tool refuses http and wildcard origins",
            all(tool.ORIGIN.match(o) is None for o in ("http://api.example.uz", "https://*.example.uz", "https://a.uz/path")))
require("this repository ships with no server configured",
        'const COMMUNITY_SERVER = "";' in (ROOT / "static/standalone.js").read_text())

# ---- servers ----
class FakeOsrm(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def do_GET(self):
        coords = [[69.27 + i * 0.002, 41.30] for i in range(6)]
        body = json.dumps({"code": "Ok", "routes": [{"distance": 1000, "duration": 90,
            "geometry": {"type": "LineString", "coordinates": coords},
            "legs": [{"annotation": {"distance": [200] * 5, "duration": [18] * 5}}]}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


osrm = ThreadingHTTPServer(("127.0.0.1", 0), FakeOsrm)
threading.Thread(target=osrm.serve_forever, daemon=True).start()
api = cs.Api(cs.Store(":memory:"), f"http://127.0.0.1:{osrm.server_address[1]}")
server = ThreadingHTTPServer(("127.0.0.1", 0), cs.make_handler(api, {"http://localhost:8765"}))
threading.Thread(target=server.serve_forever, daemon=True).start()
LOCAL = f"http://127.0.0.1:{server.server_address[1]}"
SENT = []


def forward(route, request):
    path = request.url[len(ORIGIN):]
    body = request.post_data_buffer
    SENT.append((request.method, path.split("?")[0], json.loads(body) if body else None))
    if request.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "http://localhost:8765",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS"})
    upstream = urllib.request.Request(LOCAL + path, data=body or None, method=request.method,
                                      headers={k: v for k, v in request.headers.items()
                                               if k.lower() in ("authorization", "content-type")})
    try:
        with urllib.request.urlopen(upstream, timeout=10) as r:
            status, payload = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, payload = e.code, e.read()
    route.fulfill(status=status, body=payload, headers={"Content-Type": "application/json",
                                                         "Access-Control-Allow-Origin": "http://localhost:8765"})


def serve_patched(route, request):
    name = "standalone.js" if request.url.endswith("standalone.js") else "index.html"
    text = (ROOT / "static" / name).read_text()
    if name == "standalone.js":
        text = text.replace('const COMMUNITY_SERVER = "";', f'const COMMUNITY_SERVER = "{ORIGIN}";')
        ctype = "application/javascript"
    else:
        text = text.replace(tool.BASE_CONNECT, tool.BASE_CONNECT + " " + ORIGIN)
        ctype = "text/html"
    route.fulfill(status=200, body=text, headers={"Content-Type": ctype})


def drive_track(seconds=300, speed=12.0):
    lat0, lng0 = 41.3111, 69.2797
    per = 111320 * math.cos(math.radians(lat0))
    return [[t, lat0, lng0 + t * speed / per, 5, speed, 90] for t in range(seconds)]


now = time.time()
DRIVE = {"id": "1800000000000", "started_at": now - 2400, "ended_at": now - 600, "gps_track": drive_track(1800)}
PHOTO = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP////////////////////////////////////////////////////////////////////////////////////8A//8AAAAAAAAAAAAAAAAA"

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.route(APP, serve_patched)
    page.route(APP + "index.html", serve_patched)
    page.route(APP + "standalone.js", serve_patched)
    page.route(ORIGIN + "/**", forward)
    page.goto(APP)
    page.wait_for_function("() => !!(window.StandaloneAPI && window.StandaloneAPI.handle)")

    def call(path, method="GET", body=None):
        return page.evaluate("([path, method, body]) => window.StandaloneAPI.handle(path, body == null"
                             " ? { method } : { method, body: JSON.stringify(body) })", [path, method, body])

    status = call("/api/community/status")
    require("a configured build shows community features but is not registered",
            status["configured"] is True and status["registered"] is False and not status["rank"])
    page.wait_for_function("() => !document.getElementById('communityHome').classList.contains('hidden')")
    require("nothing is sent before a profile is saved",
            call("/api/community/sync", "POST", {"drives": [DRIVE]}) == {"skipped": True} and SENT == [])

    saved = call("/api/community/profile", "POST", {"display_name": "Ali", "region": "fargona",
        "district": "Bag'dod", "village": "Sho'rariq", "rank": True, "share_potholes": True, "share_speeds": True})
    require("saving a profile registers the device", saved["registered"] and saved["rank"]
            and saved["profile"]["village"] == "sho'rariq")
    call("/api/native-report", "POST", {"id": 9, "created_at": now, "lat": 41.3115, "lng": 69.2805,
        "photo_data_url": PHOTO, "photo_full_data_url": PHOTO, "damage_type": "road_shock",
        "decision": "sensor_candidate", "capture_source": "drive_sensor", "drive_id": DRIVE["id"],
        "source_event_key": "sensor:x:1", "captured_at": now - 700, "gps_accuracy": 5, "speed_mps": 12, "heading": 90})
    SENT.clear()
    result = call("/api/community/sync", "POST", {"drives": [DRIVE]})
    require("sync uploads the trip, the shock location and anonymous speeds",
            result["trips"] == 1 and result["potholes"] == 1 and result["speeds"] > 0)
    bodies = {path: body for method, path, body in SENT if method == "POST"}
    require("the trip upload has totals only, never coordinates or a track",
            set(bodies["/v1/trips"]) == {"client_id", "started_day", "distance_m", "moving_s", "score",
                                         "hard_brake", "hard_accel", "sharp_turn", "turns"})
    require("the pothole upload has only coordinates and a kind",
            all(set(pt) == {"lat", "lng", "kind"} for pt in bodies["/v1/potholes"]["points"]))
    speeds = bodies["/v1/speeds"]["samples"]
    lng0 = 69.2797
    per = 111320 * math.cos(math.radians(41.3111))
    require("speed samples carry no drive id and skip the first and last 300 m",
            all(set(s) == {"lat", "lng", "heading", "speed_kmh", "at"} for s in speeds)
            and min((s["lng"] - lng0) * per for s in speeds) >= 299
            and max((s["lng"] - lng0) * per for s in speeds) <= 1800 * 12 - 299)
    require("a second sync sends nothing new",
            (lambda r: r["trips"] == 0 and r["potholes"] == 0)(call("/api/community/sync", "POST", {"drives": [DRIVE]})))

    # Two other drivers confirm a pothole elsewhere; it comes back for offline warnings.
    for name in ("Vali", "Sami"):
        req = urllib.request.Request(LOCAL + "/v1/devices", method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"display_name": name, "region": "fargona", "district": "bag'dod", "village": "sho'rariq"}).encode())
        token = json.loads(urllib.request.urlopen(req).read())["token"]
        urllib.request.urlopen(urllib.request.Request(LOCAL + "/v1/potholes", method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            data=json.dumps({"points": [{"lat": 41.32, "lng": 69.30, "kind": "pothole"}]}).encode()))
    require("confirmed community potholes are downloaded", call("/api/community/sync", "POST", {"drives": []})["downloaded"] == 1)
    hazards = call("/api/road-hazards")["hazards"]
    require("they join the offline warnings next to the driver's own reports",
            any(h["id"].startswith("s") and h["lat"] == 41.32 for h in hazards)
            and any(h["id"] == "r1" or h["id"].startswith("r") for h in hazards))

    ranking = call("/api/community/rankings?level=village")
    require("the village ranking shows the driver", ranking["entries"][0]["name"] == "Ali" and ranking["me"]["rank"] == 1)
    page.evaluate("() => renderRanking('village')")
    page.wait_for_function("() => document.getElementById('rankList').textContent.includes('Ali')")
    route = call("/api/community/route?from=41.3,69.27&to=41.3,69.28")
    require("routing works through the server", route["routes"][0]["distance_m"] == 1000)
    page.evaluate("""(r) => drawRoute(r.routes, {lat: 41.3, lng: 69.27}, {lat: 41.3, lng: 69.28})""", route)
    require("the route is drawn on the map", page.locator("#routeMap path.leaflet-interactive").count() >= 1)

    gone = call("/api/community/profile", "DELETE")
    require("deleting removes the profile on the server and locally",
            gone["registered"] is False and not gone["rank"]
            and api.store.db.execute("SELECT COUNT(*) FROM devices WHERE display_name='Ali'").fetchone()[0] == 0)
    browser.close()

server.shutdown()
osrm.shutdown()
print("community client checks passed")
