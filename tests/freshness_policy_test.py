# -*- coding: utf-8 -*-
"""FRESH-001: fresh 0-7 days, aging 8-30 days, stale after that; never deleted or auto-fixed."""
import sys

from playwright.sync_api import sync_playwright

APP = "http://localhost:8765/"
DAY = 86400

SCENARIO = r"""
async ({day}) => {
  const f = StandaloneAPI.__pure.freshnessFor;
  const now = 1_800_000_000;
  const bounds = {
    justNow: f(now, now), sixDays: f(now - 6 * day, now), sevenDays: f(now - 7 * day, now),
    sevenDaysPlus: f(now - 7 * day - 1, now), eightDays: f(now - 8 * day, now),
    thirtyDays: f(now - 30 * day, now), thirtyDaysPlus: f(now - 30 * day - 1, now),
    year: f(now - 365 * day, now), clockSkew: f(now + 120, now),
    future: f(now + 3600, now), missing: f(undefined, now), zero: f(0, now), nan: f(NaN, now),
  };
  // Rendering: chips follow the report's last-seen time; stale reports are still listed.
  await StandaloneAPI.handle("/api/reports", { method: "DELETE" });
  const db = await new Promise((res, rej) => { const r = indexedDB.open("potholes"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
  const real = Date.now() / 1000;
  const mk = (daysAgo, extra = {}) => ({ created_at: real - daysAgo * day, last_seen_at: real - daysAgo * day,
    status: "draft", damage_type: "pothole_cavity", assessment: "clear", lat: 41.3, lng: 69.28,
    address: "Test Road", description: "d", ...extra });
  await new Promise((res, rej) => {
    const tx = db.transaction("reports", "readwrite"); const s = tx.objectStore("reports");
    s.add(mk(1)); s.add(mk(20)); s.add(mk(90)); s.add(mk(90, { condition_status: "fixed" }));
    tx.oncomplete = res; tx.onabort = () => rej(tx.error);
  });
  db.close();
  const reports = await StandaloneAPI.handle("/api/reports");
  const states = reports.map((r) => ({ days: Math.round((real - r.created_at) / day),
    fixed: r.condition_status === "fixed", chip: freshnessOf(r) }));
  return { bounds, states, count: reports.length, chipHtml: freshnessChip(reports.find((r) => Math.round((real - r.created_at) / day) === 1)) };
}
"""

failures = []
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
    page.goto(APP)
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => typeof StandaloneAPI !== 'undefined' && typeof freshnessOf === 'function'",
                           timeout=30000)
    r = page.evaluate(SCENARIO, {"day": DAY})
    browser.close()

b = r["bounds"]
expected = {"justNow": "fresh", "sixDays": "fresh", "sevenDays": "fresh", "sevenDaysPlus": "aging",
            "eightDays": "aging", "thirtyDays": "aging", "thirtyDaysPlus": "stale", "year": "stale",
            "clockSkew": "fresh", "future": "unknown", "missing": "unknown", "zero": "unknown",
            "nan": "unknown"}
for key, want in expected.items():
    if b[key] != want:
        failures.append(f"{key}: expected {want}, got {b[key]}")
if r["count"] != 4:
    failures.append(f"a stale report was dropped: {r['count']} of 4 remain")
chips = {(s["days"], s["fixed"]): s["chip"] for s in r["states"]}
if chips.get((1, False)) != "fresh" or chips.get((20, False)) != "aging" or chips.get((90, False)) != "stale":
    failures.append(f"freshness chips wrong: {chips}")
if chips.get((90, True)) != "":
    failures.append(f"a fixed report showed a freshness chip: {chips}")
if "fresh-fresh" not in r["chipHtml"]:
    failures.append(f"chip markup missing: {r['chipHtml']}")

if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("FRESHNESS POLICY TEST PASS")
