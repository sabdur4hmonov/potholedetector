#!/usr/bin/env python3
"""Build a uz-road-cameras-v1 pack from an official camera list (CSV).

The app can also import the CSV directly (Settings -> Road cameras). This tool produces the
same validated JSON for shipping inside the app or publishing on the project's Pages site,
and prints every rejected row so the data owner can fix it.

CSV header (any order, case-insensitive): lat, lng, type; optional id, heading, limit, name.
type: speed | seatbelt | red_light | lane | phone | speed_bump (common Uzbek/Russian spellings
such as tezlik, remen, kamar, svetofor are accepted). heading is the travel direction the
camera watches, in degrees from north (0-360); leave it empty for both directions. limit is
the posted speed limit in km/h.

    python3 tools/build-camera-pack.py cameras.csv --source "Official list, 2026-10" \
        --updated 2026-10-07 --out cameras-uz.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

SCHEMA = "uz-road-cameras-v1"
MAX_CAMERAS = 20_000
TYPES = ("speed", "seatbelt", "red_light", "lane", "phone", "speed_bump")
ALIASES = {
    "speed_camera": "speed", "tezlik": "speed", "skorost": "speed", "скорость": "speed", "radar": "speed",
    "seatbelt_camera": "seatbelt", "belt": "seatbelt", "remen": "seatbelt", "kamar": "seatbelt", "ремень": "seatbelt",
    "red_light_camera": "red_light", "redlight": "red_light", "svetofor": "red_light", "светофор": "red_light",
    "lane_camera": "lane", "tasma": "lane", "polosa": "lane", "полоса": "lane",
    "phone_camera": "phone", "telefon": "phone", "телефон": "phone",
    "bump": "speed_bump", "lejachiy": "speed_bump", "лежачий": "speed_bump",
}
COLUMNS = {
    "id": ("id",), "lat": ("lat", "latitude", "kenglik"), "lng": ("lng", "lon", "longitude", "uzunlik"),
    "type": ("type", "turi", "kind"), "heading": ("heading", "direction", "yo'nalish", "yonalish"),
    "limit": ("limit", "speed_limit", "chegara"), "name": ("name", "nomi", "address"),
}


def camera_type(value) -> str | None:
    key = "_".join(str(value or "").strip().lower().replace("-", " ").split())
    if key in TYPES:
        return key
    return ALIASES.get(key)


def _number(value):
    text = str(value if value is not None else "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return float("nan")


def build(csv_text: str, source: str, updated: str | None):
    """Returns (pack, rejected rows). Mirrors parseCameraPack in static/standalone.js."""
    sample = csv_text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample.strip() else csv.excel
    reader = csv.reader(io.StringIO(csv_text.lstrip("﻿")), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("the CSV is empty")
    header = [cell.strip().lower() for cell in rows[0]]
    index = {key: next((i for i, h in enumerate(header) if h in names), -1) for key, names in COLUMNS.items()}
    if min(index["lat"], index["lng"], index["type"]) < 0:
        raise ValueError("the CSV needs a header row with lat, lng and type columns")

    cameras, rejected, seen = [], [], set()
    for number, row in enumerate(rows[1:], start=2):
        if len(cameras) >= MAX_CAMERAS:
            rejected.append(f"line {number}: more than {MAX_CAMERAS} cameras")
            break

        def get(key):
            i = index[key]
            return row[i] if 0 <= i < len(row) else None

        lat, lng = _number(get("lat")), _number(get("lng"))
        if lat is None or lng is None or lat != lat or lng != lng or abs(lat) > 90 or abs(lng) > 180 \
                or (lat == 0 and lng == 0):
            rejected.append(f"line {number}: bad coordinates")
            continue
        kind = camera_type(get("type"))
        if kind is None:
            rejected.append(f"line {number}: unknown type {get('type')!r}")
            continue
        heading = _number(get("heading"))
        if heading is not None and (heading != heading or not 0 <= heading <= 360):
            rejected.append(f"line {number}: heading must be 0-360 degrees")
            continue
        limit = _number(get("limit"))
        if limit is not None and (limit != limit or limit != int(limit) or not 5 <= limit <= 200):
            rejected.append(f"line {number}: limit must be a whole number from 5 to 200 km/h")
            continue
        raw_id = (get("id") or "").strip()
        camera_id = (raw_id or f"{kind}:{lat:.6f},{lng:.6f}:{'any' if heading is None else round(heading)}")[:60]
        if camera_id in seen:
            rejected.append(f"line {number}: duplicate id {camera_id!r}")
            continue
        seen.add(camera_id)
        name = get("name")
        cameras.append({
            "id": camera_id, "lat": lat, "lng": lng, "type": kind,
            "heading": None if heading is None else heading % 360,
            "limit": None if limit is None else int(limit),
            "name": None if name is None or not name.strip() else name.strip()[:80],
        })
    if not cameras:
        raise ValueError("no usable cameras were found")
    pack = {"schema": SCHEMA, "source": source[:120], "updated": updated, "cameras": cameras}
    return pack, rejected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("csv")
    parser.add_argument("--source", required=True, help="who provided the list, for the app's Settings")
    parser.add_argument("--updated", help="date of the official list, YYYY-MM-DD")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    pack, rejected = build(Path(args.csv).read_text(encoding="utf-8-sig"), args.source, args.updated)
    Path(args.out).write_text(json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pack['cameras'])} cameras written to {args.out}")
    for line in rejected:
        print("  rejected", line, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
