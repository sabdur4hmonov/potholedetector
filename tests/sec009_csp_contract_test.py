"""SEC-009 contracts for the actual WebView entry point and its asset mirrors."""
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = [ROOT / p for p in (
    "static/index.html", "android-app/www/index.html", "docs/index.html",
    "android-app/android/app/src/main/assets/public/index.html",
)]


class EntryParser(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.tags = []
        self.blocks = {"script": [], "style": []}
        self.active = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in self.blocks:
            self.active = tag
            self.blocks[tag].append("")

    def handle_endtag(self, tag):
        if self.active == tag:
            self.active = None

    def handle_data(self, data):
        if self.active:
            self.blocks[self.active][-1] += data


def policy(text):
    parsed = EntryParser(text)
    metas = [a for t, a in parsed.tags if t == "meta"
             and a.get("http-equiv", "").lower() == "content-security-policy"]
    if len(metas) != 1:
        raise AssertionError("Exactly one enforced CSP meta is required")
    directives = {}
    for directive in metas[0]["content"].split(";"):
        fields = directive.split()
        if fields:
            if fields[0] in directives:
                raise AssertionError("Duplicate CSP directive")
            directives[fields[0]] = fields[1:]
    return parsed, directives


class Sec009CspTest(unittest.TestCase):
    def setUp(self):
        self.text = ENTRIES[0].read_text(encoding="utf-8")
        self.parsed, self.csp = policy(self.text)

    def test_csp_precedes_resources_and_mirrors_match(self):
        position = self.text.index('http-equiv="Content-Security-Policy"')
        for marker in ("<link", "<style", "<script"):
            self.assertLess(position, self.text.index(marker))
        for entry in ENTRIES[1:]:
            self.assertEqual(ENTRIES[0].read_bytes(), entry.read_bytes(), str(entry))

    def test_script_hash_matches_browser_normalized_content(self):
        scripts = [b for b in self.parsed.blocks["script"] if b.strip()]
        self.assertEqual(len(scripts), 1)
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode()).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", self.csp["script-src"])
        self.assertIn("'self'", self.csp["script-src"])
        self.assertTrue(all(v == "'self'" or v.startswith("'sha256-")
                            for v in self.csp["script-src"]))
        self.assertEqual(self.csp["script-src-attr"], ["'none'"])
        for values in self.csp.values():
            self.assertNotIn("'unsafe-eval'", values)
            self.assertNotIn("'wasm-unsafe-eval'", values)
        for _, attrs in self.parsed.tags:
            self.assertFalse(any(name.lower().startswith("on") for name in attrs))

    def test_default_objects_frames_base_and_forms_deny(self):
        for directive in ("default-src", "object-src", "frame-src", "child-src",
                          "worker-src", "base-uri", "form-action"):
            self.assertEqual(self.csp[directive], ["'none'"], directive)

    def test_app_execution_needs_no_dynamic_code_or_remote_scripts(self):
        javascript = "\n".join(self.parsed.blocks["script"]) + (ROOT / "static/standalone.js").read_text(encoding="utf-8")
        for pattern in (r"\beval\s*\(", r"\bnew\s+Function\s*\(", r"\bWebSocket\s*\(",
                        r"\bEventSource\s*\(", r"createElement\(\s*['\"]script['\"]"):
            self.assertNotRegex(javascript, pattern)
        self.assertEqual([attrs["src"] for tag, attrs in self.parsed.tags
                          if tag == "script" and "src" in attrs],
                         ["vendor/leaflet.js", "standalone.js"])

    def test_connections_are_explicit_and_cover_actual_requirements(self):
        values = self.csp["connect-src"]
        self.assertIn("'self'", values)  # APIs, converted camera files, native GET proxy
        self.assertIn("blob:", values)
        self.assertIn("data:", values)  # legacy photos fetched before base64 export
        for value in values:
            self.assertNotIn("*", value)
            self.assertNotIn(value, ("https:", "http:", "ws:", "wss:"))
            if value.startswith("https://"):
                self.assertTrue(urlsplit(value).hostname)
        for origin in ("https://api.openai.com", "https://nominatim.openstreetmap.org",
                       "https://kgis.ksrsac.in", "https://tgrac.telangana.gov.in",
                       "https://coding-parrot.github.io/pothole-reporter/"):
            self.assertIn(origin, values)
        # Trusted pack metadata supplies the Telangana point-query destinations.
        for pack in (ROOT / "docs/packs").rglob("*.json"):
            for url in re.findall(r'"query_url"\s*:\s*"([^"]+)"', pack.read_text(encoding="utf-8")):
                parts = urlsplit(url)
                self.assertIn(f"{parts.scheme}://{parts.netloc}", values)

    def test_styles_images_media_and_bridge_remain_compatible(self):
        styles = [b for b in self.parsed.blocks["style"] if b.strip()]
        self.assertEqual(len(styles), 1)
        digest = base64.b64encode(hashlib.sha256(styles[0].encode()).digest()).decode()
        self.assertEqual(set(self.csp["style-src-elem"]), {"'self'", f"'sha256-{digest}'"})
        # Existing static/dynamic style attributes require this scoped compatibility allowance.
        self.assertGreater(sum("style" in a for _, a in self.parsed.tags), 20)
        self.assertEqual(self.csp["style-src-attr"], ["'unsafe-inline'"])
        self.assertEqual(set(self.csp["style-src"]), {"'self'", "'unsafe-inline'"})
        self.assertEqual(set(self.csp["img-src"]),
                         {"'self'", "blob:", "data:", "https://tile.openstreetmap.org"})
        self.assertEqual(set(self.csp["media-src"]), {"'self'", "blob:", "data:"})
        self.assertEqual(self.csp["font-src"], ["'self'"])
        config = json.loads((ROOT / "android-app/capacitor.config.json").read_text())
        self.assertEqual(config["webDir"], "www")
        self.assertEqual(config["server"]["androidScheme"], "https")
        self.assertNotIn("url", config["server"])
        self.assertNotIn("allowNavigation", config["server"])
        injector = (ROOT / "android-app/node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/JSInjector.java").read_text()
        self.assertIn('html.indexOf("<head>") + "<head>".length()', injector)
        bridge = (ROOT / "android-app/node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/Bridge.java").read_text()
        self.assertIn("addDocumentStartJavaScript", bridge)


if __name__ == "__main__":
    unittest.main()
