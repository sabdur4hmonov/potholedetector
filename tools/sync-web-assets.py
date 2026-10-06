#!/usr/bin/env python3
"""Refresh the CSP hashes in static/index.html and mirror the web files.

static/ is the source of truth. The packaged Android app (android-app/www) and the
hosted copy (docs/) must be byte-identical copies, and the inline <script>/<style>
blocks of index.html are allowed by hash in its Content-Security-Policy, so every edit
to those blocks needs the hashes recomputed. Run this after editing anything in static/.

  python3 tools/sync-web-assets.py          # update hashes and copy
  python3 tools/sync-web-assets.py --check  # exit 1 if anything is out of date
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
MIRRORS = [ROOT / "android-app" / "www", ROOT / "docs"]
WEB_FILES = ["index.html", "standalone.js", "hazard-model.js", "trip-stats.js"]


def digest(text: str) -> str:
    raw = hashlib.sha256(text.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(raw).decode("ascii")


def with_current_hashes(html: str) -> str:
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    styles = re.findall(r"<style>(.*?)</style>", html, re.S)
    if len(scripts) != 1 or len(styles) != 1:
        raise SystemExit(f"expected exactly one inline script and style, found {len(scripts)}/{len(styles)}")
    script_hash, style_hash = digest(scripts[0]), digest(styles[0])

    def swap(directive: str, new_hash: str, text: str) -> str:
        pattern = re.compile(r"(" + re.escape(directive) + r" [^;]*?)'sha256-[A-Za-z0-9+/=]+'")
        if not pattern.search(text):
            raise SystemExit(f"CSP directive {directive} has no sha256 source to update")
        return pattern.sub(lambda m: m.group(1) + "'" + new_hash + "'", text, count=1)

    html = swap("script-src", script_hash, html)
    html = swap("style-src-elem", style_hash, html)
    return html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    index = STATIC / "index.html"
    current = index.read_text(encoding="utf-8")
    updated = with_current_hashes(current)
    stale = []
    if updated != current:
        stale.append("static/index.html CSP hashes")
        if not args.check:
            index.write_text(updated, encoding="utf-8")
    for mirror in MIRRORS:
        for name in WEB_FILES:
            source = STATIC / name
            target = mirror / name
            want = updated.encode("utf-8") if name == "index.html" else source.read_bytes()
            if not target.exists() or target.read_bytes() != want:
                stale.append(f"{mirror.relative_to(ROOT)}/{name}")
                if not args.check:
                    shutil.copyfile(source, target)
    if args.check:
        if stale:
            print("out of date:", ", ".join(stale))
            return 1
        print("web assets are in sync")
        return 0
    print("updated:" if stale else "already in sync", ", ".join(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
