#!/usr/bin/env python3
"""Point this build at a community server, or remove it.

The web engine only talks to the origin in COMMUNITY_SERVER, and the page's CSP must allow
exactly that origin in connect-src. This tool changes both together, then mirrors the web
assets, so the security policy never gets a wildcard.

    python3 tools/set-community-server.py https://api.example.uz
    python3 tools/set-community-server.py --clear
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "static" / "standalone.js"
PAGE = ROOT / "static" / "index.html"
BASE_CONNECT = "connect-src 'self' blob: data: https://api.openai.com https://nominatim.openstreetmap.org"
ORIGIN = re.compile(r"^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d{1,5})?$")


def apply(origin: str) -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    engine, count = re.subn(r'const COMMUNITY_SERVER = "[^"]*";', f'const COMMUNITY_SERVER = "{origin}";', engine)
    if count != 1:
        raise SystemExit("COMMUNITY_SERVER constant not found exactly once")
    page = PAGE.read_text(encoding="utf-8")
    page, count = re.subn(re.escape(BASE_CONNECT) + r"( https://[^;\s]+)?", BASE_CONNECT + (f" {origin}" if origin else ""), page)
    if count != 1:
        raise SystemExit("CSP connect-src not found in its expected form")
    ENGINE.write_text(engine, encoding="utf-8")
    PAGE.write_text(page, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("origin", nargs="?", help="https://host[:port] with no path")
    group.add_argument("--clear", action="store_true")
    parser.add_argument("--no-sync", action="store_true", help="do not mirror the web assets")
    args = parser.parse_args(argv)
    origin = "" if args.clear else args.origin.lower().rstrip("/")
    if origin and not ORIGIN.match(origin):
        raise SystemExit("the server must be an https origin such as https://api.example.uz")
    apply(origin)
    if not args.no_sync:
        subprocess.run([sys.executable, str(ROOT / "tools" / "sync-web-assets.py")], check=True)
    print(f"community server {'cleared' if not origin else 'set to ' + origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
