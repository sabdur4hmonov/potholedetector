#!/usr/bin/env python3
"""Settings and native Drive must keep phone and RTSP capture sources isolated."""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright


APP = "http://localhost:8765/"

NATIVE_MOCK = r"""
(() => {
  const probe = window.__captureSourceProbe = {
    listeners: {}, permissionArgs: [], startArgs: [], attach: 0,
    secure: {openAiKey: "", dashcamRtspUrl: ""},
    status: {
      isRunning: false, isStarting: false, isPaused: false, isStopping: false,
      captureStopped: false, sessionId: null, startRequestId: null,
      checked: 0, found: 0, already: 0, queued: 0, dropped: 0,
      recordingEnabled: false, isRecording: false, videoSupported: true,
      cameraActive: false, sourceActive: false, sourceState: "idle",
      captureSource: "phone_camera", status: "Idle",
    },
  };
  const emit = (name, value) => (probe.listeners[name] || []).forEach((fn) => fn(value));
  probe.emitStatus = (changes) => {
    probe.status = {...probe.status, ...changes};
    emit("driveStatusChange", {...probe.status});
  };
  const DriveMode = {
    addListener: async (name, fn) => { (probe.listeners[name] ||= []).push(fn); },
    requestDrivePermissions: async (options = {}) => {
      probe.permissionArgs.push({...options});
      return {granted: true, notificationsGranted: true};
    },
    startDrive: async (options = {}) => {
      probe.startArgs.push({...options});
      probe.status = {...probe.status,
        isRunning: true, sessionId: "capture-source-test",
        startRequestId: options.startRequestId || null,
        captureSource: options.captureSource || "phone_camera",
        sourceActive: true, sourceState: "streaming", sourceIssue: null,
        cameraActive: true, status: options.captureSource === "dashcam"
          ? "Scanning dashcam stream" : "Scanning live"};
      queueMicrotask(() => emit("driveStatusChange", {...probe.status}));
      return {...probe.status};
    },
    getStatus: async () => ({...probe.status}),
    getDriveEndSummary: async () => ({available: false}),
    attachPreview: async () => { probe.attach++; },
    detachPreview: async () => {},
    syncReports: async () => ({reports: [], count: 0}),
    syncRepairObservations: async () => ({observations: [], count: 0}),
    acknowledgeReports: async ({ids = []} = {}) => ({acknowledged: ids.length}),
    getDrives: async () => ({drives: []}),
    beginRepairTargetSync: async ({ids = []} = {}) => {
      probe.repairIds = ids;
      return {token: "capture-source-repair"};
    },
    appendRepairTargetBatch: async () => ({appended: true}),
    commitRepairTargetSync: async () => ({replaced: (probe.repairIds || []).length}),
    abortRepairTargetSync: async () => ({aborted: true}),
  };
  const App = {addListener: async () => {}};
  const secureStatus = () => ({
    openAiConfigured: !!probe.secure.openAiKey,
    dashcamRtspConfigured: !!probe.secure.dashcamRtspUrl,
  });
  const SecureCredentials = {
    getStatus: async () => secureStatus(),
    migrateLegacyCredentials: async (options = {}) => {
      if (!probe.secure.openAiKey && options.openAiKey) probe.secure.openAiKey = options.openAiKey;
      if (!probe.secure.dashcamRtspUrl && options.dashcamRtspUrl) {
        probe.secure.dashcamRtspUrl = options.dashcamRtspUrl;
      }
      return secureStatus();
    },
    storeCredentials: async (options = {}) => {
      if (options.openAiKey) probe.secure.openAiKey = options.openAiKey;
      if (options.dashcamRtspUrl) probe.secure.dashcamRtspUrl = options.dashcamRtspUrl;
      return secureStatus();
    },
    clearCredentials: async () => {
      probe.secure = {openAiKey: "", dashcamRtspUrl: ""};
      return secureStatus();
    },
  };
  Object.defineProperty(window, "Capacitor", {configurable: true, value: {
    isNativePlatform: () => true,
    registerPlugin: (name) => name === "DriveMode" ? DriveMode
      : name === "SecureCredentials" ? SecureCredentials : {},
    Plugins: {DriveMode, SecureCredentials, App},
  }});
})();
"""


def make_context(browser, init: str):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    context.add_init_script(NATIVE_MOCK)
    context.add_init_script(init)
    return context


def wait_ready(page):
    page.goto(APP)
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        "typeof validateDashcamRtspUrl === 'function' && !nativeInitialRestorePending",
        timeout=30_000,
    )
    page.locator("#home").wait_for(state="visible")
    page.evaluate("localStorage.setItem('data_notice_version', DATA_NOTICE_VERSION)")


failures: list[str] = []
with sync_playwright() as playwright:
    launch_options = {"args": ["--disable-web-security"]}
    system_chrome = pathlib.Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if system_chrome.is_file():
        launch_options["executable_path"] = str(system_chrome)
    browser = playwright.chromium.launch(**launch_options)

    # The current Media3 client cannot provide verified secure RTSP. Even a
    # programmatic selection or an existing retained endpoint must fail closed.
    dashcam_context = make_context(browser, """
        localStorage.setItem('openai_key', 'test-key-never-sent');
        localStorage.setItem('initial_setup_complete', '1');
        localStorage.setItem('drive_capture_source', 'dashcam');
        localStorage.setItem('dashcam_rtsp_url', 'rtsp://camera.example/live');
    """)
    page = dashcam_context.new_page()
    wait_ready(page)
    page.locator("#driveBtn").click()
    page.locator("#settings").wait_for(state="visible")
    state = page.evaluate("""() => ({
        source: localStorage.getItem(CAPTURE_SOURCE_KEY),
        blocked: document.querySelector('#dashcamOption').disabled,
        fieldBlocked: document.querySelector('#setDashcamRtspUrl').disabled,
        noStart: __captureSourceProbe.startArgs.length === 0,
        noPermissions: __captureSourceProbe.permissionArgs.length === 0,
        safeMessage: document.querySelector('#dashcamRtspNote').textContent.includes('verified secure RTSP'),
        noPlaintext: localStorage.getItem('dashcam_rtsp_url') === null,
    })""")
    if state != dict(source="dashcam", blocked=True, fieldBlocked=True,
                     noStart=True, noPermissions=True, safeMessage=True, noPlaintext=True):
        failures.append("saved insecure dashcam did not fail closed")
    validation = page.evaluate("""() => [
        'rtsp://camera.example/live', 'rtsps://camera.example/live',
        'rtsps:///live', 'https://camera.example/live', ''
    ].every(value => validateDashcamRtspUrl(value) === null)""")
    if not validation:
        failures.append("unsupported dashcam endpoint accepted in WebView")
    # A disabled option is not the security boundary: exercise the handler directly.
    page.evaluate("document.querySelector('#setCaptureSource').value = 'dashcam'")
    page.locator("#setSave").click()
    page.wait_for_timeout(100)
    if page.evaluate("document.querySelector('#settings').classList.contains('hidden')"):
        failures.append("programmatic dashcam selection bypassed settings rejection")
    dashcam_context.close()

    # Existing installs and the browser/native phone path remain phone-camera-first.
    phone_context = make_context(
        browser,
        """localStorage.setItem('openai_key', 'test-key-never-sent');
        localStorage.setItem('initial_setup_complete', '1');
        localStorage.setItem('drive_capture_source', 'phone_camera');
        localStorage.setItem('dashcam_rtsp_url', 'rtsp://stale-user:stale-pass@10.0.0.1/live');""",
    )
    page = phone_context.new_page()
    wait_ready(page)
    page.locator("#driveBtn").click()
    page.locator("#nativeDrivePanel").wait_for(state="visible")
    page.wait_for_function("__captureSourceProbe.startArgs.length === 1 && __captureSourceProbe.attach > 0")
    phone = page.evaluate(
        """() => {
          const permission = __captureSourceProbe.permissionArgs[0] || {};
          const start = __captureSourceProbe.startArgs[0] || {};
          return {
            permissionSource: permission.captureSource,
            startSource: start.captureSource,
            noCredentialArgs: !Object.hasOwn(start, 'dashcamRtspUrl') &&
              !Object.hasOwn(start, 'apiKey'),
            badge: document.querySelector('#nativeCameraBadge').textContent,
            previewLabel: document.querySelector('#nativePreviewSlot').getAttribute('aria-label'),
            placeholderHidden: document.querySelector('#nativeSourceMessage').classList.contains('hidden'),
            recordControlHidden: document.querySelector('#nativeRecordBtn').classList.contains('hidden'),
            staleSecretVisible: document.body.innerText.includes('stale-user:stale-pass'),
          };
        }"""
    )
    expected_phone = {
        "permissionSource": "phone_camera", "startSource": "phone_camera",
        "noCredentialArgs": True, "badge": "● CAMERA ACTIVE · SAVING FRAMES",
        "previewLabel": "Live phone camera preview", "placeholderHidden": True,
        "recordControlHidden": False,
        "staleSecretVisible": False,
    }
    if phone != expected_phone:
        failures.append(f"phone-camera Drive contract regressed: {phone}")
    phone_context.close()
    browser.close()

if failures:
    print("FAIL")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print("DASHCAM CAPTURE SOURCE TEST PASS")
