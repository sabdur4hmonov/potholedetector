#!/usr/bin/env python3
"""Serve the packaged app and the current web build for browser tests."""

from __future__ import annotations

import argparse
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (ROOT / "android-app" / "www").resolve()
WEB_ROOT = (ROOT / "static").resolve()
WEB_PREFIX = "/web-app/"


class AppHandler(SimpleHTTPRequestHandler):
    """Map Android and current-web URLs to explicit roots."""

    def translate_path(self, path: str) -> str:
        request_path = unquote(urlsplit(path).path)
        if request_path.startswith(WEB_PREFIX):
            base = WEB_ROOT
            relative = request_path[len(WEB_PREFIX) :] or "index.html"
        else:
            base = APP_ROOT
            relative = request_path.lstrip("/") or "index.html"

        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            # A path outside either explicit root must never be served.
            return str(base / "__not_found__")
        return str(candidate)

    def end_headers(self) -> None:
        # Normal suite requests are same-origin and therefore do not rely on a security
        # bypass; the header only keeps an optional cross-origin harness usable.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path: str):  # type: ignore[override]
        self.send_error(404, "Directory listing disabled")
        return None

    def log_message(self, format: str, *args: object) -> None:
        # The suite already reports failed requests; keep its server log useful.
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    mimetypes.add_type("application/json", ".json")
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
