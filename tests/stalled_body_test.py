# -*- coding: utf-8 -*-
"""A response that sends headers and then goes silent must be abandoned, not waited on.

The timeout used to be cleared as soon as the headers arrived, so it only covered the
handshake. A stalled body was never aborted: the drive filled every slot, stopped
detecting, and the HUD went on reporting a healthy drive.
"""
import sys
from playwright.sync_api import sync_playwright
from browser_test_utils import NATIVE_AI_PAGE_SCRIPT, open_app

# The page runs as a native app whose OpenAI bridge call never completes (mocked below;
# browser builds refuse paid AI calls). No real key is used and nothing is transmitted.
KEY = "test-key-never-sent"
BUDGET_MS = 45000        # the engine's own response deadline is 35s; this allows for it

with sync_playwright() as p:
    b = p.chromium.launch(args=["--disable-web-security", "--allow-running-insecure-content"])
    ctx = b.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script(NATIVE_AI_PAGE_SCRIPT)
    pg = ctx.new_page()
    open_app(pg, KEY)
    pg.wait_for_function("() => typeof StandaloneAPI !== 'undefined'", timeout=30000)

    r = pg.evaluate("""async () => {
      // The native bridge accepts the request and then never answers.
      const realFetch = window.fetch;
      window.fetch = (url, init) => {
        if (!String(url).includes("api.openai.com")) return realFetch(url, init);
        return new Promise(() => {});
      };
      const c = document.createElement("canvas"); c.width = 64; c.height = 64;
      const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.8));
      const fd = new FormData();
      fd.append("photo", blob, "f.jpg");
      fd.append("lat", "12.9115"); fd.append("lng", "77.6427"); fd.append("drive_id", "stall");
      const t0 = performance.now();
      let outcome;
      try { await StandaloneAPI.handle("/api/frame", {method: "POST", body: fd}); outcome = "RESOLVED"; }
      catch (e) { outcome = "rejected: " + (e.message || "").slice(0, 60); }
      const ms = Math.round(performance.now() - t0);
      window.fetch = realFetch;
      return { outcome, ms };
    }""")
    b.close()

print(f"  outcome        : {r['outcome']}")
print(f"  took           : {r['ms']} ms")
fails = []
if r["outcome"] == "RESOLVED":
    fails.append("a stalled body resolved, so the frame silently produced a verdict from nothing")
if r["ms"] > BUDGET_MS:
    fails.append(f"took {r['ms']} ms, beyond the {BUDGET_MS} ms budget")
print()
if fails:
    print("FAIL"); [print("  -", f) for f in fails]; sys.exit(1)
print("STALLED BODY TEST PASS")
