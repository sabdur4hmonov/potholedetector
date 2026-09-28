const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// Reuse the existing native mock. It deliberately accepts start requests so that
// this suite detects a WebView bypass; native authorization is tested on the JVM.
const fixture = fs.readFileSync(path.join(__dirname, 'dashcam_capture_source_test.py'), 'utf8');
const mock = fixture.match(/NATIVE_MOCK = r"""([\s\S]*?)"""/)[1];
(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.POTHOLE_TEST_CHROME ? { executablePath: process.env.POTHOLE_TEST_CHROME } : {}) });
  let scenarios = 0;
  try {
    for (const source of ['dashcam', 'phone_camera']) {
      const context = await browser.newContext();
      await context.addInitScript(mock);
      await context.addInitScript((source) => {
        localStorage.setItem('openai_key', 'test-key-never-sent');
        localStorage.setItem('initial_setup_complete', '1');
        localStorage.setItem('drive_capture_source', source);
        localStorage.setItem('dashcam_rtsp_url', 'rtsp://camera.example/live');
        window.alert = () => {};
      }, source);
      const page = await context.newPage();
      await page.route('https://api.openai.com/**', route => route.abort());
      await page.goto(process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/');
      await page.waitForFunction(() => typeof validateDashcamRtspUrl === 'function' && !nativeInitialRestorePending);
      await page.evaluate(() => localStorage.setItem('data_notice_version', DATA_NOTICE_VERSION));
      if (source === 'dashcam') {
        await page.locator('#driveBtn').click();
        await page.locator('#settings').waitFor({ state: 'visible' });
        assert.deepEqual(await page.evaluate(() => ({
          source: localStorage.getItem(CAPTURE_SOURCE_KEY),
          starts: __captureSourceProbe.startArgs.length,
          permissions: __captureSourceProbe.permissionArgs.length,
          disabled: document.querySelector('#dashcamOption').disabled,
          fieldDisabled: document.querySelector('#setDashcamRtspUrl').disabled,
          noPlaintext: localStorage.getItem('dashcam_rtsp_url') === null,
          message: document.querySelector('#dashcamRtspNote').textContent.includes('verified secure RTSP'),
        })), { source: 'dashcam', starts: 0, permissions: 0, disabled: true,
          fieldDisabled: true, noPlaintext: true, message: true });
        scenarios++;
        assert.equal(await page.evaluate(() => ['rtsp://camera.example/live', 'rtsps://camera.example/live',
          'rtsps:///live', 'https://camera.example/live', ''].every(value => validateDashcamRtspUrl(value) === null)), true);
        scenarios++;
        for (const retained of [true, false]) {
          const result = await page.evaluate(async retained => {
            __captureSourceProbe.secure.dashcamRtspUrl = retained ? 'rtsp://camera.example/live' : '';
            await CredentialBroker.ready();
            document.querySelector('#setCaptureSource').value = 'dashcam';
            document.querySelector('#setDashcamRtspUrl').value = 'rtsps://camera.example/live';
            await document.querySelector('#setSave').onclick();
            return { settingsVisible: !document.querySelector('#settings').classList.contains('hidden'),
              source: localStorage.getItem(CAPTURE_SOURCE_KEY), starts: __captureSourceProbe.startArgs.length,
              unchanged: __captureSourceProbe.secure.dashcamRtspUrl === (retained ? 'rtsp://camera.example/live' : '') };
          }, retained);
          assert.deepEqual(result, { settingsVisible: true, source: 'dashcam', starts: 0, unchanged: true });
          scenarios++;
        }
      } else {
        await page.locator('#driveBtn').click();
        await page.waitForFunction(() => __captureSourceProbe.startArgs.length === 1);
        assert.deepEqual(await page.evaluate(() => ({
          source: __captureSourceProbe.startArgs[0].captureSource,
          credentialsAbsent: !Object.hasOwn(__captureSourceProbe.startArgs[0], 'dashcamRtspUrl') &&
            !Object.hasOwn(__captureSourceProbe.startArgs[0], 'apiKey'),
        })), { source: 'phone_camera', credentialsAbsent: true });
        scenarios++;
      }
      await context.close();
    }
    console.log(`SEC003 DASHCAM FLOW PASS (${scenarios} scenarios)`);
  } finally { await browser.close(); }
})().catch(() => { console.error('SEC003 DASHCAM FLOW FAILED (credential-safe output)'); process.exitCode = 1; });
