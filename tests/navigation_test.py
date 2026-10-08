# -*- coding: utf-8 -*-
"""Voice navigation: native wiring contract plus the Route screen's panel, start and
automatic reroute in a real browser with a stand-in native plugin and route API."""
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = "http://localhost:8765/"
DRIVE = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive"
PLUGIN = ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


service = (DRIVE / "RoadAlertService.kt").read_text()
guide = (DRIVE / "NavigationGuide.kt").read_text()
plugin = PLUGIN.read_text()
server = (ROOT / "server/community_server.py").read_text()
web = (ROOT / "static/index.html").read_text()

require("the server asks OSRM for turn steps", "steps=true" in server and '"steps": steps' in server)
require("navigation runs in the GPS-only service, offline and without the camera",
        "NavigationGuide(line, steps)" in service and "okhttp" not in guide and "java.net" not in guide)
require("a turn instruction is spoken first; a hazard warning in the same second waits",
        'speaker?.say("nav", interrupt = true)' in service
        and "announce(alert, interrupt = navEvent == null)" in service)
require("route input from the page is bounded",
        "minOf(geometry.length(), NavigationGuide.MAX_POINTS)" in plugin
        and "minOf(steps?.length() ?: 0, NavigationGuide.MAX_MANEUVERS)" in plugin)
require("a running service gets the new route in place instead of stop-and-start",
        "RoadAlertService.reroute(context, route)" in plugin and "ACTION_REROUTE" in service)
require("both languages label navigation", web.count("nav_start:") == 2 and web.count("nav_off_route:") == 2)

ROUTE = {"index": 0, "distance_m": 2500, "duration_s": 300, "free_flow_s": 280, "live_share": 0.4,
         "geometry": [[41.30, 69.27], [41.30, 69.29], [41.31, 69.29]],
         "steps": [{"lat": 41.30, "lng": 69.29, "type": "turn", "modifier": "left", "exit": None,
                    "name": "Amir Temur", "distance_m": 1200}]}

FAKE = r"""
(route) => {
  window.__calls = [];
  const plugin = {
    addListener: async () => ({ remove() {} }),
    getRoadAlertStatus: async () => ({ running: false }),
    requestDrivePermissions: async () => ({ granted: true, notificationsGranted: true }),
    startNavigation: async (args) => { window.__calls.push(['start', args]);
      return { running: true, navigating: true, navNext: 'chapga buriling · Amir Temur', distanceToNextM: 1200,
               remainingM: 2500, cameraCount: 0, potholeCount: 1 }; },
    stopRoadAlerts: async () => { window.__calls.push(['stop']); return { running: false }; },
  };
  window.nativeDrivePlugin = () => plugin;
  window.api = async (path) => {
    window.__calls.push(['api', path]);
    if (path.startsWith('/api/road-hazards')) return { hazards: [{ id: 'r1', kind: 'pothole', lat: 41.3, lng: 69.28 }] };
    if (path.startsWith('/api/community/route')) return { routes: [route], best: 0 };
    throw new Error('unexpected ' + path);
  };
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-web-security"])
    page = browser.new_page()
    page.goto(APP)
    page.wait_for_function("() => typeof updateNavPanel === 'function' && typeof startNavigation === 'function'")
    page.evaluate(FAKE, ROUTE)
    status = page.evaluate("(r) => startNavigation(r)", ROUTE)
    calls = page.evaluate("() => window.__calls")
    start = next(c for c in calls if c[0] == "start")[1]
    require("starting sends the route line, the turns and the saved hazards to native",
            status["navigating"] and start["geometry"] == ROUTE["geometry"]
            and start["steps"][0]["modifier"] == "left" and start["hazards"][0]["id"] == "r1" and start["voice"])
    page.evaluate("() => updateNavPanel({ running: true, navigating: true, navNext: 'chapga buriling · Amir Temur', distanceToNextM: 340, remainingM: 2140 })")
    require("the panel shows the next turn, its distance and what is left",
            page.locator("#navDistance").text_content() == "340 m"
            and page.locator("#navAction").text_content() == "chapga buriling · Amir Temur"
            and "2.1" in page.locator("#navRemaining").text_content())
    page.evaluate("(r) => { navPlan = { place: { lat: 41.31, lng: 69.29 }, route: r }; window.__calls = []; }", ROUTE)
    page.evaluate("() => updateNavPanel({ running: true, navigating: true, offRoute: true, lat: 41.305, lng: 69.275, remainingM: 2000 })")
    page.wait_for_function("() => window.__calls.some(c => c[0] === 'start')")
    calls = page.evaluate("() => window.__calls")
    require("leaving the route asks for a new route from the car's position and swaps it in",
            any(c[0] == "api" and c[1].startswith("/api/community/route?from=41.305,69.275&to=41.31,69.29") for c in calls)
            and any(c[0] == "start" for c in calls))
    page.evaluate("() => updateNavPanel({ running: true, navigating: true, offRoute: true, lat: 41.305, lng: 69.275 })")
    require("a second off-route update right away does not ask again",
            sum(1 for c in page.evaluate("() => window.__calls") if c[0] == "api") == 1)
    page.evaluate("() => updateNavPanel({ running: true, navigating: true, arrived: true })")
    require("arrival is shown", page.locator("#navAction").text_content() == "You have arrived.")
    page.evaluate("() => document.getElementById('navStop').click()")
    page.wait_for_function("() => window.__calls.some(c => c[0] === 'stop')")
    require("stop ends navigation", "hidden" in (page.locator("#navPanel").get_attribute("class") or ""))
    browser.close()

print("navigation checks passed")
