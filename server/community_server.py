#!/usr/bin/env python3
"""Community server for the pothole app: profiles, regional rankings, a shared pothole map,
anonymous road speeds and traffic-aware routing. Python standard library only.

Privacy by design:
* A device is identified only by a random token; no phone number, e-mail or name is
  required. The display name is whatever the driver types.
* Trips are uploaded as totals (distance, time, score, event counts), never GPS tracks.
* Potholes are uploaded as coordinates and a kind; no photos.
* Road speeds are stored without any device identifier, aggregated into ~110 m cells,
  8 heading sectors and 15-minute bins.

Run behind an HTTPS reverse proxy (see server/README.md):

    DB_PATH=/var/lib/pothole/community.db OSRM_URL=http://127.0.0.1:5000 \\
        ALLOWED_ORIGINS=https://localhost,capacitor://localhost \\
        python3 server/community_server.py --host 127.0.0.1 --port 8080
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_VERSION = "community-v1"
MAX_BODY_BYTES = 256 * 1024
REGIONS = {
    "andijon": "Andijon viloyati", "buxoro": "Buxoro viloyati", "fargona": "Farg'ona viloyati",
    "jizzax": "Jizzax viloyati", "xorazm": "Xorazm viloyati", "namangan": "Namangan viloyati",
    "navoiy": "Navoiy viloyati", "qashqadaryo": "Qashqadaryo viloyati",
    "qoraqalpogiston": "Qoraqalpog'iston Respublikasi", "samarqand": "Samarqand viloyati",
    "sirdaryo": "Sirdaryo viloyati", "surxondaryo": "Surxondaryo viloyati",
    "toshkent_viloyati": "Toshkent viloyati", "toshkent_shahri": "Toshkent shahri",
}
LEVELS = ("village", "district", "region", "country")
POTHOLE_KINDS = ("pothole", "road_shock")
POTHOLE_MERGE_M = 15.0
RANKING_MIN_KM = 20.0
LIVE_SPEED_MAX_AGE_S = 30 * 60
LIVE_SPEED_MIN_SAMPLES = 3
DAILY_LIMITS = {"trips": 50, "potholes": 2_000, "speeds": 20_000, "register_ip": 10}

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
  region TEXT NOT NULL, district TEXT NOT NULL, village TEXT NOT NULL,
  created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS trips (
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE, client_id TEXT NOT NULL,
  started_day TEXT NOT NULL, distance_m REAL NOT NULL, moving_s REAL NOT NULL,
  score INTEGER NOT NULL, hard_brake INTEGER NOT NULL, hard_accel INTEGER NOT NULL,
  sharp_turn INTEGER NOT NULL, turns INTEGER NOT NULL, submitted_at INTEGER NOT NULL,
  PRIMARY KEY (device_id, client_id));
CREATE INDEX IF NOT EXISTS trips_by_time ON trips(submitted_at);
CREATE TABLE IF NOT EXISTS potholes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, lat REAL NOT NULL, lng REAL NOT NULL, kind TEXT NOT NULL,
  cell_lat INTEGER NOT NULL, cell_lng INTEGER NOT NULL,
  first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL, confirmations INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS potholes_by_cell ON potholes(cell_lat, cell_lng);
CREATE TABLE IF NOT EXISTS pothole_sightings (
  pothole_id INTEGER NOT NULL REFERENCES potholes(id) ON DELETE CASCADE,
  device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  observed_at INTEGER NOT NULL, PRIMARY KEY (pothole_id, device_id));
CREATE TABLE IF NOT EXISTS speed_cells (
  cell_lat INTEGER NOT NULL, cell_lng INTEGER NOT NULL, sector INTEGER NOT NULL, bin INTEGER NOT NULL,
  samples INTEGER NOT NULL, sum_kmh REAL NOT NULL, PRIMARY KEY (cell_lat, cell_lng, sector, bin));
CREATE TABLE IF NOT EXISTS usage (
  subject TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL,
  PRIMARY KEY (subject, kind, day));
"""


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- validation helpers ----------

def normalise_place(value, field: str, required: bool = True) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[ʻʼ‘’`´]", "'", text)
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    if required and not text:
        raise ApiError(400, f"{field} is required")
    if len(text) > 60:
        raise ApiError(400, f"{field} is too long")
    return text


def display_name(value) -> str:
    text = re.sub(r"[\x00-\x1f\x7f<>]", "", unicodedata.normalize("NFKC", str(value or ""))).strip()
    text = re.sub(r"\s+", " ", text)
    if not 2 <= len(text) <= 24:
        raise ApiError(400, "display_name must be 2-24 characters")
    return text


def number(value, field: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ApiError(400, f"{field} must be a number")
    if not low <= value <= high:
        raise ApiError(400, f"{field} must be between {low} and {high}")
    return float(value)


def integer(value, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, f"{field} must be a whole number")
    if not low <= value <= high:
        raise ApiError(400, f"{field} must be between {low} and {high}")
    return value


def distance_m(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1.0, h)))


def speed_cell(lat: float, lng: float) -> tuple[int, int]:
    return round(lat * 1000), round(lng * 1000)


def sector(heading: float) -> int:
    return int(((heading % 360) + 22.5) // 45) % 8


# ---------- store ----------

class Store:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA)

    def tx(self):
        store = self

        class _Tx:
            def __enter__(self):
                store.lock.acquire()
                store.db.execute("BEGIN IMMEDIATE")
                return store.db

            def __exit__(self, kind, value, tb):
                try:
                    store.db.execute("ROLLBACK" if kind else "COMMIT")
                finally:
                    store.lock.release()
                return False
        return _Tx()

    def charge(self, db, subject: str, kind: str, amount: int, now: int) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        row = db.execute("SELECT used FROM usage WHERE subject=? AND kind=? AND day=?",
                         (subject, kind, day)).fetchone()
        used = (row["used"] if row else 0) + amount
        if used > DAILY_LIMITS[kind]:
            raise ApiError(429, f"daily {kind} limit reached")
        db.execute("INSERT INTO usage(subject, kind, day, used) VALUES(?,?,?,?) "
                   "ON CONFLICT(subject, kind, day) DO UPDATE SET used=excluded.used",
                   (subject, kind, day, used))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- API ----------

class Api:
    def __init__(self, store: Store, osrm_url: str | None = None, clock=time.time):
        self.store = store
        self.osrm_url = (osrm_url or "").rstrip("/") or None
        self.clock = clock

    def now(self) -> int:
        return int(self.clock())

    def device(self, db, headers) -> sqlite3.Row:
        auth = headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise ApiError(401, "missing device token")
        token = auth[7:].strip()
        if not 20 <= len(token) <= 100:
            raise ApiError(401, "invalid device token")
        row = db.execute("SELECT * FROM devices WHERE token_hash=?", (token_hash(token),)).fetchone()
        if row is None or not hmac.compare_digest(row["token_hash"], token_hash(token)):
            raise ApiError(401, "unknown device token")
        db.execute("UPDATE devices SET last_seen=? WHERE id=?", (self.now(), row["id"]))
        return row

    def profile_fields(self, body, partial=False) -> dict:
        out = {}
        if not partial or "display_name" in body:
            out["display_name"] = display_name(body.get("display_name"))
        if not partial or "region" in body:
            region = str(body.get("region") or "")
            if region not in REGIONS:
                raise ApiError(400, "region must be one of " + ", ".join(REGIONS))
            out["region"] = region
        if not partial or "district" in body:
            out["district"] = normalise_place(body.get("district"), "district")
        if not partial or "village" in body:
            out["village"] = normalise_place(body.get("village"), "village")
        return out

    # --- handlers: (method, path) -> function(query, body, headers, client_ip) ---

    def health(self, *_):
        return {"ok": True, "api": API_VERSION, "routing": bool(self.osrm_url)}

    def regions(self, *_):
        return {"regions": [{"id": k, "name": v} for k, v in REGIONS.items()]}

    def register(self, query, body, headers, ip):
        fields = self.profile_fields(body)
        token = secrets.token_urlsafe(32)
        device_id = secrets.token_hex(12)
        now = self.now()
        with self.store.tx() as db:
            self.store.charge(db, "ip:" + hashlib.sha256(ip.encode()).hexdigest()[:16], "register_ip", 1, now)
            db.execute("INSERT INTO devices(id, token_hash, display_name, region, district, village, "
                       "created_at, last_seen) VALUES(?,?,?,?,?,?,?,?)",
                       (device_id, token_hash(token), fields["display_name"], fields["region"],
                        fields["district"], fields["village"], now, now))
        return {"device_id": device_id, "token": token, **fields}

    def me(self, query, body, headers, ip):
        with self.store.tx() as db:
            row = self.device(db, headers)
            return {k: row[k] for k in ("display_name", "region", "district", "village")}

    def update_me(self, query, body, headers, ip):
        fields = self.profile_fields(body, partial=True)
        with self.store.tx() as db:
            row = self.device(db, headers)
            if fields:
                sets = ", ".join(f"{k}=?" for k in fields)
                db.execute(f"UPDATE devices SET {sets} WHERE id=?", (*fields.values(), row["id"]))
            row = db.execute("SELECT * FROM devices WHERE id=?", (row["id"],)).fetchone()
            return {k: row[k] for k in ("display_name", "region", "district", "village")}

    def delete_me(self, query, body, headers, ip):
        with self.store.tx() as db:
            row = self.device(db, headers)
            affected = [r["pothole_id"] for r in db.execute(
                "SELECT pothole_id FROM pothole_sightings WHERE device_id=?", (row["id"],))]
            db.execute("DELETE FROM devices WHERE id=?", (row["id"],))
            for pothole_id in affected:
                count = db.execute("SELECT COUNT(*) AS n FROM pothole_sightings WHERE pothole_id=?",
                                   (pothole_id,)).fetchone()["n"]
                if count == 0:
                    db.execute("DELETE FROM potholes WHERE id=?", (pothole_id,))
                else:
                    db.execute("UPDATE potholes SET confirmations=? WHERE id=?", (count, pothole_id))
        return {"deleted": True}

    def submit_trip(self, query, body, headers, ip):
        client_id = str(body.get("client_id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", client_id):
            raise ApiError(400, "client_id is invalid")
        day = str(body.get("started_day") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ApiError(400, "started_day must be YYYY-MM-DD")
        distance = number(body.get("distance_m"), "distance_m", 1000, 2_000_000)
        moving = number(body.get("moving_s"), "moving_s", 60, 24 * 3600)
        if distance / moving * 3.6 > 200:
            raise ApiError(400, "trip average speed is implausible")
        score = integer(body.get("score"), "score", 0, 100)
        counts = {k: integer(body.get(k), k, 0, 10_000) for k in ("hard_brake", "hard_accel", "sharp_turn", "turns")}
        now = self.now()
        with self.store.tx() as db:
            device = self.device(db, headers)
            exists = db.execute("SELECT 1 FROM trips WHERE device_id=? AND client_id=?",
                                (device["id"], client_id)).fetchone()
            if exists:
                return {"stored": False, "duplicate": True}
            self.store.charge(db, device["id"], "trips", 1, now)
            db.execute("INSERT INTO trips VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                       (device["id"], client_id, day, distance, moving, score, counts["hard_brake"],
                        counts["hard_accel"], counts["sharp_turn"], counts["turns"], now))
        return {"stored": True, "duplicate": False}

    def rankings(self, query, body, headers, ip):
        level = query.get("level", "country")
        if level not in LEVELS:
            raise ApiError(400, "level must be village, district, region or country")
        try:
            period = int(query.get("period_days", "30"))
        except ValueError:
            raise ApiError(400, "period_days must be a whole number")
        if not 1 <= period <= 365:
            raise ApiError(400, "period_days must be 1-365")
        with self.store.tx() as db:
            me = self.device(db, headers) if headers.get("Authorization") else None
            where, params = [], []
            area = {"level": level}
            scope = {"village": ("region", "district", "village"), "district": ("region", "district"),
                     "region": ("region",), "country": ()}[level]
            for key in scope:
                value = me[key] if me is not None else query.get(key)
                if not value:
                    raise ApiError(400, f"{key} is required for a {level} ranking")
                value = value if key == "region" else normalise_place(value, key)
                where.append(f"d.{key}=?")
                params.append(value)
                area[key] = value
            since = self.now() - period * 86400
            sql = ("SELECT d.id, d.display_name, SUM(t.distance_m) AS m, "
                   "SUM(t.score * t.distance_m) / SUM(t.distance_m) AS s "
                   "FROM trips t JOIN devices d ON d.id = t.device_id WHERE t.submitted_at >= ? "
                   + "".join(" AND " + w for w in where) +
                   " GROUP BY d.id HAVING m >= ? ORDER BY s DESC, m DESC, d.created_at ASC")
            rows = db.execute(sql, (since, *params, RANKING_MIN_KM * 1000)).fetchall()
        entries = [{"rank": i + 1, "name": r["display_name"], "score": round(r["s"], 1),
                    "km": round(r["m"] / 1000, 1)} for i, r in enumerate(rows)]
        mine = None
        if me is not None:
            mine = next((e for e, r in zip(entries, rows) if r["id"] == me["id"]), None)
        return {"area": area, "period_days": period, "min_km": RANKING_MIN_KM,
                "total": len(entries), "entries": entries[:50], "me": mine}

    def submit_potholes(self, query, body, headers, ip):
        points = body.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= 200:
            raise ApiError(400, "points must be a list of 1-200 items")
        cleaned = []
        for i, p in enumerate(points):
            if not isinstance(p, dict):
                raise ApiError(400, f"points[{i}] must be an object")
            kind = p.get("kind")
            if kind not in POTHOLE_KINDS:
                raise ApiError(400, f"points[{i}].kind must be pothole or road_shock")
            lat = number(p.get("lat"), f"points[{i}].lat", 37.0, 46.0)  # Uzbekistan and borders
            lng = number(p.get("lng"), f"points[{i}].lng", 55.0, 74.0)
            cleaned.append((lat, lng, kind))
        now = self.now()
        added = merged = 0
        with self.store.tx() as db:
            device = self.device(db, headers)
            self.store.charge(db, device["id"], "potholes", len(cleaned), now)
            for lat, lng, kind in cleaned:
                cell_lat, cell_lng = round(lat * 10_000), round(lng * 10_000)
                near = db.execute(
                    "SELECT * FROM potholes WHERE kind=? AND cell_lat BETWEEN ? AND ? AND cell_lng BETWEEN ? AND ?",
                    (kind, cell_lat - 2, cell_lat + 2, cell_lng - 3, cell_lng + 3)).fetchall()
                best = min(near, key=lambda r: distance_m(lat, lng, r["lat"], r["lng"]), default=None)
                if best is not None and distance_m(lat, lng, best["lat"], best["lng"]) <= POTHOLE_MERGE_M:
                    pothole_id = best["id"]
                    merged += 1
                else:
                    pothole_id = db.execute(
                        "INSERT INTO potholes(lat, lng, kind, cell_lat, cell_lng, first_seen, last_seen, "
                        "confirmations) VALUES(?,?,?,?,?,?,?,0)",
                        (lat, lng, kind, cell_lat, cell_lng, now, now)).lastrowid
                    added += 1
                db.execute("INSERT INTO pothole_sightings VALUES(?,?,?) ON CONFLICT(pothole_id, device_id) "
                           "DO UPDATE SET observed_at=excluded.observed_at", (pothole_id, device["id"], now))
                count = db.execute("SELECT COUNT(*) AS n FROM pothole_sightings WHERE pothole_id=?",
                                   (pothole_id,)).fetchone()["n"]
                db.execute("UPDATE potholes SET confirmations=?, last_seen=? WHERE id=?", (count, now, pothole_id))
        return {"added": added, "merged": merged}

    def list_potholes(self, query, body, headers, ip):
        try:
            minimum = int(query.get("min_confirmations", "1"))
            since_days = int(query.get("since_days", "180"))
        except ValueError:
            raise ApiError(400, "min_confirmations and since_days must be whole numbers")
        if not 1 <= minimum <= 100 or not 1 <= since_days <= 730:
            raise ApiError(400, "min_confirmations 1-100, since_days 1-730")
        sql = "SELECT id, lat, lng, kind, confirmations, last_seen FROM potholes WHERE confirmations>=? AND last_seen>=?"
        params = [minimum, self.now() - since_days * 86400]
        if "bbox" in query:
            try:
                min_lat, min_lng, max_lat, max_lng = (float(v) for v in query["bbox"].split(","))
            except ValueError:
                raise ApiError(400, "bbox must be minLat,minLng,maxLat,maxLng")
            sql += " AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?"
            params += [min_lat, max_lat, min_lng, max_lng]
        sql += " ORDER BY confirmations DESC, last_seen DESC LIMIT 20000"
        with self.store.tx() as db:
            rows = db.execute(sql, params).fetchall()
        return {"potholes": [dict(r) for r in rows]}

    def submit_speeds(self, query, body, headers, ip):
        samples = body.get("samples")
        if not isinstance(samples, list) or not 1 <= len(samples) <= 500:
            raise ApiError(400, "samples must be a list of 1-500 items")
        now = self.now()
        rows = []
        for i, s in enumerate(samples):
            if not isinstance(s, dict):
                raise ApiError(400, f"samples[{i}] must be an object")
            lat = number(s.get("lat"), f"samples[{i}].lat", 37.0, 46.0)
            lng = number(s.get("lng"), f"samples[{i}].lng", 55.0, 74.0)
            heading = number(s.get("heading"), f"samples[{i}].heading", 0, 360)
            kmh = number(s.get("speed_kmh"), f"samples[{i}].speed_kmh", 0, 200)
            at = int(number(s.get("at"), f"samples[{i}].at", now - 3600, now + 120))
            rows.append((*speed_cell(lat, lng), sector(heading), at // 900, kmh))
        with self.store.tx() as db:
            device = self.device(db, headers)
            self.store.charge(db, device["id"], "speeds", len(rows), now)
            for cell_lat, cell_lng, sec, time_bin, kmh in rows:
                # No device id is stored with a speed.
                db.execute("INSERT INTO speed_cells VALUES(?,?,?,?,1,?) ON CONFLICT(cell_lat, cell_lng, "
                           "sector, bin) DO UPDATE SET samples=samples+1, sum_kmh=sum_kmh+excluded.sum_kmh",
                           (cell_lat, cell_lng, sec, time_bin, kmh))
            db.execute("DELETE FROM speed_cells WHERE bin < ?", ((now - 7 * 86400) // 900,))
        return {"stored": len(rows)}

    def live_speed_kmh(self, db, lat, lng, heading, now) -> float | None:
        cell_lat, cell_lng = speed_cell(lat, lng)
        row = db.execute("SELECT SUM(samples) AS n, SUM(sum_kmh) AS s FROM speed_cells WHERE cell_lat=? "
                         "AND cell_lng=? AND sector=? AND bin>=?",
                         (cell_lat, cell_lng, sector(heading), (now - LIVE_SPEED_MAX_AGE_S) // 900)).fetchone()
        if not row or not row["n"] or row["n"] < LIVE_SPEED_MIN_SAMPLES:
            return None
        return row["s"] / row["n"]

    def route(self, query, body, headers, ip):
        if not self.osrm_url:
            raise ApiError(503, "routing is not configured on this server")

        def point(name):
            try:
                lat, lng = (float(v) for v in query.get(name, "").split(","))
            except ValueError:
                raise ApiError(400, f"{name} must be lat,lng")
            number(lat, name, 37.0, 46.0)
            number(lng, name, 55.0, 74.0)
            return lat, lng
        start, end = point("from"), point("to")
        url = (f"{self.osrm_url}/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}"
               "?alternatives=3&overview=full&geometries=geojson&steps=false&annotations=distance,duration")
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read(5 * 1024 * 1024))
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise ApiError(502, f"routing engine unavailable: {error}")
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ApiError(404, "no route found")
        now = self.now()
        results = []
        with self.store.tx() as db:
            for index, r in enumerate(data["routes"][:4]):
                coords = r["geometry"]["coordinates"]
                distances, durations = [], []
                for leg in r.get("legs", []):
                    ann = leg.get("annotation") or {}
                    distances += ann.get("distance", [])
                    durations += ann.get("duration", [])
                adjusted, live_m = 0.0, 0.0
                if len(distances) == len(coords) - 1 and len(durations) == len(distances):
                    for i, (seg_m, seg_s) in enumerate(zip(distances, durations)):
                        (lng1, lat1), (lng2, lat2) = coords[i], coords[i + 1]
                        heading = math.degrees(math.atan2(
                            math.sin(math.radians(lng2 - lng1)) * math.cos(math.radians(lat2)),
                            math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
                            - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2))
                            * math.cos(math.radians(lng2 - lng1)))) % 360
                        live = self.live_speed_kmh(db, (lat1 + lat2) / 2, (lng1 + lng2) / 2, heading, now)
                        if live is not None and seg_m > 0:
                            adjusted += seg_m / max(live, 3.0) * 3.6
                            live_m += seg_m
                        else:
                            adjusted += seg_s
                else:
                    adjusted = float(r["duration"])
                results.append({"index": index, "distance_m": round(r["distance"]),
                                "free_flow_s": round(r["duration"]), "duration_s": round(adjusted),
                                "live_share": round(live_m / r["distance"], 2) if r["distance"] else 0,
                                "geometry": [[c[1], c[0]] for c in coords]})
        results.sort(key=lambda x: x["duration_s"])
        return {"routes": results, "best": results[0]["index"],
                "traffic": "live speeds from drivers where available, otherwise the map's typical speed"}

    ROUTES = {
        ("GET", "/v1/health"): "health", ("GET", "/v1/regions"): "regions",
        ("POST", "/v1/devices"): "register", ("GET", "/v1/devices/me"): "me",
        ("PATCH", "/v1/devices/me"): "update_me", ("DELETE", "/v1/devices/me"): "delete_me",
        ("POST", "/v1/trips"): "submit_trip", ("GET", "/v1/rankings"): "rankings",
        ("POST", "/v1/potholes"): "submit_potholes", ("GET", "/v1/potholes"): "list_potholes",
        ("POST", "/v1/speeds"): "submit_speeds", ("GET", "/v1/route"): "route",
    }

    def dispatch(self, method, path, query, body, headers, ip):
        name = self.ROUTES.get((method, path))
        if name is None:
            raise ApiError(404, "not found")
        return getattr(self, name)(query, body, headers, ip)


def make_handler(api: Api, allowed_origins: set[str], trust_proxy: bool = False):
    class Handler(BaseHTTPRequestHandler):
        server_version = "pothole-community"
        sys_version = ""

        def log_message(self, *args):  # no request logs: they would contain IPs and paths
            return

        def cors(self):
            origin = self.headers.get("Origin")
            if origin and origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
                self.send_header("Access-Control-Max-Age", "600")

        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.cors()
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.cors()
            self.end_headers()

        def handle_api(self, method):
            parsed = urllib.parse.urlsplit(self.path)
            query = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}
            body = {}
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY_BYTES:
                    raise ApiError(413, "request body too large")
                if length:
                    if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                        raise ApiError(415, "JSON body required")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ApiError(400, "JSON object required")
                # Only a trusted reverse proxy may name the client address; otherwise anyone
                # could dodge the per-address registration limit with a forged header.
                forwarded = self.headers.get("X-Forwarded-For") if trust_proxy else None
                ip = (forwarded or self.client_address[0]).split(",")[-1].strip()
                self.reply(200, api.dispatch(method, parsed.path, query, body, self.headers, ip))
            except ApiError as error:
                self.reply(error.status, {"error": error.message})
            except json.JSONDecodeError:
                self.reply(400, {"error": "invalid JSON"})
            except Exception:  # never leak internals
                self.reply(500, {"error": "internal error"})

        def do_GET(self):
            self.handle_api("GET")

        def do_POST(self):
            self.handle_api("POST")

        def do_PATCH(self):
            self.handle_api("PATCH")

        def do_DELETE(self):
            self.handle_api("DELETE")

    return Handler


def serve(host: str, port: int, db_path: str, osrm_url: str | None, origins: set[str],
          trust_proxy: bool = False):
    api = Api(Store(db_path), osrm_url)
    server = ThreadingHTTPServer((host, port), make_handler(api, origins, trust_proxy))
    server.daemon_threads = True
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    origins = {o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS", "https://localhost,capacitor://localhost,http://localhost").split(",") if o.strip()}
    server = serve(args.host, args.port, os.environ.get("DB_PATH", "community.db"),
                   os.environ.get("OSRM_URL"), origins, os.environ.get("TRUST_PROXY") == "1")
    print(f"community server on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
