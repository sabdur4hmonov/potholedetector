# -*- coding: utf-8 -*-
"""Raw GPS tracks: 30-day auto-delete, per-drive deletion and an opt-out; reports keep coordinates."""
import sys

from playwright.sync_api import sync_playwright

APP = "http://localhost:8765/"
DAY = 86400

SCENARIO = r"""
async ({day}) => {
  const now = Date.now() / 1000;
  const point = (i) => [i, 41.3 + i * 0.0001, 69.28, 5, 8, 90];
  const track = [point(0), point(1), point(2)];
  await StandaloneAPI.handle("/api/reports", { method: "DELETE" });
  const post = (id, endedDaysAgo) => StandaloneAPI.handle("/api/drives", {
    method: "POST", body: JSON.stringify({ id, started_at: now - endedDaysAgo * day - 600,
      checked: 3, found: 0, already: 0, gps_track: track }),
  });
  // POST stamps ended_at = now, so age the stored rows directly through the same store.
  const age = async (id, endedDaysAgo) => {
    const db = await new Promise((res, rej) => { const r = indexedDB.open("potholes"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
    await new Promise((res, rej) => {
      const tx = db.transaction("drives", "readwrite"); const store = tx.objectStore("drives");
      const get = store.get(id);
      get.onsuccess = () => { const d = get.result; d.ended_at = now - endedDaysAgo * day; store.put(d); };
      tx.oncomplete = res; tx.onabort = () => rej(tx.error);
    });
    db.close();
  };
  await post("fresh", 1); await age("fresh", 1);
  await post("edge", 29); await age("edge", 29);
  await post("old", 31); await age("old", 31);
  const afterPrune = await StandaloneAPI.handle("/api/drives");
  const byId = Object.fromEntries(afterPrune.map((d) => [d.id, d]));

  await StandaloneAPI.handle("/api/drives/fresh/track", { method: "DELETE" });
  const afterDelete = Object.fromEntries((await StandaloneAPI.handle("/api/drives")).map((d) => [d.id, d]));

  localStorage.setItem("keep_tracks", "0");
  await post("optout", 0);
  const optOut = Object.fromEntries((await StandaloneAPI.handle("/api/drives")).map((d) => [d.id, d]));
  localStorage.removeItem("keep_tracks");
  return {
    fresh: byId.fresh.gps_track.length, edge: byId.edge.gps_track.length, old: byId.old.gps_track.length,
    oldStillListed: !!byId.old && byId.old.checked === 3,
    deleted: afterDelete.fresh.gps_track.length, edgeAfterDelete: afterDelete.edge.gps_track.length,
    optOutTrack: optOut.optout.gps_track.length, optOutKept: optOut.optout.checked === 3,
    retention: StandaloneAPI.__pure.TRACK_RETENTION_S,
    expiredFn: [
      StandaloneAPI.__pure.trackExpired({ gps_track: [1], ended_at: now - 31 * day }, now),
      StandaloneAPI.__pure.trackExpired({ gps_track: [1], ended_at: now - 29 * day }, now),
      StandaloneAPI.__pure.trackExpired({ gps_track: [], ended_at: now - 99 * day }, now),
      StandaloneAPI.__pure.trackExpired({ gps_track: [1], ended_at: now }, now, false),
    ],
  };
}
"""

failures = []
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_context(viewport={"width": 390, "height": 844}).new_page()
    page.goto(APP)
    page.wait_for_load_state("networkidle")
    page.wait_for_function("() => typeof StandaloneAPI !== 'undefined'", timeout=30000)
    r = page.evaluate(SCENARIO, {"day": DAY})
    browser.close()

if r["retention"] != 30 * DAY:
    failures.append(f"retention is not 30 days: {r['retention']}")
if r["fresh"] != 3 or r["edge"] != 3:
    failures.append(f"tracks younger than 30 days were removed: {r}")
if r["old"] != 0 or not r["oldStillListed"]:
    failures.append(f"a track older than 30 days was kept, or its drive summary was lost: {r}")
if r["deleted"] != 0 or r["edgeAfterDelete"] != 3:
    failures.append(f"per-drive track deletion missed its target or hit another drive: {r}")
if r["optOutTrack"] != 0 or not r["optOutKept"]:
    failures.append(f"opt-out still stored a track, or dropped the drive summary: {r}")
if r["expiredFn"] != [True, False, False, True]:
    failures.append(f"trackExpired decisions are wrong: {r['expiredFn']}")

if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("TRACK RETENTION TEST PASS")
