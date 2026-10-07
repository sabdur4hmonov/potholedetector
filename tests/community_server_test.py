# -*- coding: utf-8 -*-
"""Community server end to end over real HTTP: profiles, regional rankings, the shared
pothole map, anonymous speeds, deletion, limits, CORS and traffic-aware routing against
a fake OSRM. Standard library only; no external service is contacted."""
import importlib.util
import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("community_server", ROOT / "server/community_server.py")
cs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cs
spec.loader.exec_module(cs)


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


# ---- fake OSRM: two alternatives; route 0 is shorter in free flow ----
def osrm_route(coords, seg_m, seg_s):
    n = len(coords) - 1
    return {"distance": seg_m * n, "duration": seg_s * n,
            "geometry": {"type": "LineString", "coordinates": coords},
            "legs": [{"annotation": {"distance": [seg_m] * n, "duration": [seg_s] * n}}]}


MAIN = [[69.2700 + i * 0.002, 41.3000] for i in range(11)]           # straight east
SIDE = [[69.2700, 41.3000]] + [[69.2700 + i * 0.002, 41.3030] for i in range(11)] + [[69.2900, 41.3000]]
OSRM = {"code": "Ok", "routes": [osrm_route(MAIN, 167.0, 12.0), osrm_route(SIDE, 160.0, 14.0)]}


class FakeOsrm(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def do_GET(self):
        FakeOsrm.last_path = self.path
        data = json.dumps(OSRM).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


osrm = ThreadingHTTPServer(("127.0.0.1", 0), FakeOsrm)
threading.Thread(target=osrm.serve_forever, daemon=True).start()

clock = {"now": 1_800_000_000}
api = cs.Api(cs.Store(":memory:"), f"http://127.0.0.1:{osrm.server_address[1]}", clock=lambda: clock["now"])
server = ThreadingHTTPServer(("127.0.0.1", 0), cs.make_handler(api, {"https://localhost"}, trust_proxy=True))
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}"


def call(method, path, body=None, token=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        request.add_header(k, v)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}"), dict(error.headers)


status, health, _ = call("GET", "/v1/health")
require("health reports the API and routing", status == 200 and health == {"ok": True, "api": "community-v1", "routing": True})
require("the 14 regions are listed", len(call("GET", "/v1/regions")[1]["regions"]) == 14)


def register(name, region="fargona", district="Bag'dod tumani", village="Sho'rariq", ip="10.0.0.1"):
    status, body, _ = call("POST", "/v1/devices", {"display_name": name, "region": region,
                                                   "district": district, "village": village},
                           headers={"X-Forwarded-For": ip})
    assert status == 200, body
    return body


ali = register("Ali", village="Shoʻrariq")          # typographic apostrophe
vali = register("Vali", village="SHO'RARIQ  ")
sami = register("Sami", district="Bag‘dod tumani", village="Boshqa qishloq")
tosh = register("Toshkentlik", region="toshkent_shahri", district="Yunusobod", village="Mahalla 1")
require("registration returns a token and normalises places",
        len(ali["token"]) >= 40 and ali["village"] == vali["village"] == "sho'rariq"
        and sami["district"] == "bag'dod tumani")
require("the server stores only a hash of the token",
        api.store.db.execute("SELECT COUNT(*) FROM devices WHERE token_hash=?", (ali["token"],)).fetchone()[0] == 0)
status, err, _ = call("POST", "/v1/devices", {"display_name": "X", "region": "mars", "district": "a", "village": "b"})
require("bad profiles are refused", status == 400)
require("unknown tokens are refused", call("GET", "/v1/devices/me", token="x" * 43)[0] == 401
        and call("GET", "/v1/devices/me")[0] == 401)
status, me, _ = call("PATCH", "/v1/devices/me", {"display_name": "Ali aka"}, token=ali["token"])
require("a profile can be renamed", status == 200 and me["display_name"] == "Ali aka")


def trip(token, client_id, km, score):
    return call("POST", "/v1/trips", {"client_id": client_id, "started_day": "2027-01-15",
                                      "distance_m": km * 1000, "moving_s": km * 90, "score": score,
                                      "hard_brake": 0, "hard_accel": 0, "sharp_turn": 0, "turns": 3}, token=token)


require("a trip is stored once", trip(ali["token"], "t1", 30, 90)[1] == {"stored": True, "duplicate": False}
        and trip(ali["token"], "t1", 30, 90)[1] == {"stored": False, "duplicate": True})
trip(vali["token"], "v1", 25, 95)
trip(sami["token"], "s1", 40, 70)
trip(tosh["token"], "k1", 60, 80)
trip(ali["token"], "t2", 5, 100)                     # Ali: 35 km, weighted 91.4
trip(vali["token"], "short", 1.5, 100)
require("implausible trips are refused",
        call("POST", "/v1/trips", {"client_id": "x", "started_day": "2027-01-15", "distance_m": 100000,
                                   "moving_s": 600, "score": 50, "hard_brake": 0, "hard_accel": 0,
                                   "sharp_turn": 0, "turns": 0}, token=ali["token"])[0] == 400)

_, village, _ = call("GET", "/v1/rankings?level=village", token=ali["token"])
require("the village ranking compares only neighbours, weighted by distance",
        [e["name"] for e in village["entries"]] == ["Vali", "Ali aka"]
        and village["area"] == {"level": "village", "region": "fargona", "district": "bag'dod tumani", "village": "sho'rariq"}
        and village["me"]["rank"] == 2 and village["me"]["km"] == 35.0)
_, district, _ = call("GET", "/v1/rankings?level=district", token=ali["token"])
require("the district ranking adds the other village", [e["name"] for e in district["entries"]] == ["Vali", "Ali aka", "Sami"])
_, country, _ = call("GET", "/v1/rankings?level=country")
require("the country ranking includes every region and needs no token",
        [e["name"] for e in country["entries"]] == ["Vali", "Ali aka", "Toshkentlik", "Sami"] and country["me"] is None)
require("a ranking without a place is refused", call("GET", "/v1/rankings?level=region")[0] == 400)
clock["now"] += 40 * 86400
require("old trips leave the 30-day ranking", call("GET", "/v1/rankings?level=country")[1]["entries"] == [])
clock["now"] -= 40 * 86400

pt = {"lat": 41.31110, "lng": 69.27970, "kind": "pothole"}
status, first, _ = call("POST", "/v1/potholes", {"points": [pt]}, token=ali["token"])
near = {**pt, "lat": 41.31117}                       # ~8 m away
_, second, _ = call("POST", "/v1/potholes", {"points": [near]}, token=vali["token"])
_, again, _ = call("POST", "/v1/potholes", {"points": [pt]}, token=ali["token"])
_, other, _ = call("POST", "/v1/potholes", {"points": [{**pt, "lat": 41.3120}, {**pt, "kind": "road_shock"}]}, token=sami["token"])
_, listed, _ = call("GET", "/v1/potholes?min_confirmations=1")
by_kind = sorted((p["kind"], p["confirmations"]) for p in listed["potholes"])
require("nearby reports merge and count distinct drivers",
        first == {"added": 1, "merged": 0} and second == {"added": 0, "merged": 1} and again["merged"] == 1
        and by_kind == [("pothole", 1), ("pothole", 2), ("road_shock", 1)])
require("confirmed-only and bbox filters work",
        len(call("GET", "/v1/potholes?min_confirmations=2")[1]["potholes"]) == 1
        and len(call("GET", "/v1/potholes?bbox=41.3119,69.27,41.3125,69.29")[1]["potholes"]) == 1)
require("points outside Uzbekistan are refused",
        call("POST", "/v1/potholes", {"points": [{"lat": 51.5, "lng": -0.1, "kind": "pothole"}]}, token=ali["token"])[0] == 400)

# Route 0 (main road) is faster in free flow; drivers report it jammed at 8 km/h.
jam = [{"lat": 41.3000, "lng": 69.2710 + i * 0.002, "heading": 90, "speed_kmh": 8, "at": clock["now"]}
       for i in range(10) for _ in range(3)]
require("anonymous speeds are stored", call("POST", "/v1/speeds", {"samples": jam}, token=vali["token"])[1] == {"stored": 30})
require("speeds carry no device id",
        "device" not in " ".join(r[1] for r in api.store.db.execute("PRAGMA table_info(speed_cells)")))
_, routed, _ = call("GET", "/v1/route?from=41.3,69.27&to=41.3,69.29")
require("routing asks OSRM for alternatives with per-segment annotations",
        "alternatives=3" in FakeOsrm.last_path and "annotations=distance,duration" in FakeOsrm.last_path)
require("live speeds move the best route to the free side street",
        routed["best"] == 1 and routed["routes"][0]["index"] == 1
        and routed["routes"][1]["duration_s"] > routed["routes"][1]["free_flow_s"] * 3
        and routed["routes"][1]["live_share"] == 1.0)
require("route geometry is lat,lng for the map", routed["routes"][0]["geometry"][0] == [41.3, 69.27])
clock["now"] += 3600
_, later, _ = call("GET", "/v1/route?from=41.3,69.27&to=41.3,69.29")
require("old speeds expire and the free-flow choice returns", later["best"] == 0)
require("routing outside Uzbekistan is refused", call("GET", "/v1/route?from=51,0&to=41.3,69.29")[0] == 400)

for i in range(9):
    register(f"Spam{i}", ip="10.9.9.9")
require("registrations per address are limited", call("POST", "/v1/devices", {
    "display_name": "Spam10", "region": "fargona", "district": "a", "village": "b"},
    headers={"X-Forwarded-For": "10.9.9.9"})[0] == 200
    and call("POST", "/v1/devices", {"display_name": "Spam11", "region": "fargona", "district": "a",
                                     "village": "b"}, headers={"X-Forwarded-For": "10.9.9.9"})[0] == 429)

status, _, headers = call("GET", "/v1/health", headers={"Origin": "https://localhost"})
_, _, foreign = call("GET", "/v1/health", headers={"Origin": "https://evil.example"})
untrusted = ThreadingHTTPServer(("127.0.0.1", 0), cs.make_handler(api, set(), trust_proxy=False))
threading.Thread(target=untrusted.serve_forever, daemon=True).start()
forged = [urllib.request.urlopen(urllib.request.Request(
    f"http://127.0.0.1:{untrusted.server_address[1]}/v1/devices", method="POST",
    data=json.dumps({"display_name": f"F{i}", "region": "fargona", "district": "a", "village": "b"}).encode(),
    headers={"Content-Type": "application/json", "X-Forwarded-For": f"10.1.{i}.1"})).status
    if i < 5 else None for i in range(5)]
require("without a trusted proxy a forged X-Forwarded-For is ignored",
        api.store.db.execute("SELECT used FROM usage WHERE kind='register_ip' AND subject LIKE 'ip:%' "
                             "ORDER BY used DESC LIMIT 1").fetchone()[0] >= 5)
untrusted.shutdown()
require("CORS allows only the app's origin",
        headers.get("Access-Control-Allow-Origin") == "https://localhost"
        and "Access-Control-Allow-Origin" not in foreign)
big = urllib.request.Request(BASE + "/v1/trips", data=b"{" + b" " * (300 * 1024) + b"}", method="POST",
                             headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(big, timeout=10)
    too_big = None
except urllib.error.HTTPError as error:
    too_big = error.code
except (ConnectionError, urllib.error.URLError):
    too_big = 413  # the server may close the socket after refusing the body
require("oversized bodies are refused", too_big == 413)

require("deleting a profile removes its trips and its pothole confirmations",
        call("DELETE", "/v1/devices/me", token=vali["token"])[1] == {"deleted": True}
        and call("GET", "/v1/devices/me", token=vali["token"])[0] == 401
        and sorted(p["confirmations"] for p in call("GET", "/v1/potholes")[1]["potholes"]) == [1, 1, 1])

server.shutdown()
osrm.shutdown()
print("community server checks passed")
