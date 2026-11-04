// Real Chromium with the shared native credential mock; never reaches a provider.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const jpeg = require('./fixtures/sec010-images.json').jpeg;
const credentials = fs.readFileSync(path.join(__dirname, 'browser_test_utils.py'), 'utf8')
  .match(/SECURE_CREDENTIALS_MOCK = r"""([\s\S]*?)"""/)[1];
const init = () => {
  localStorage.setItem('initial_setup_complete', '1');
  window.alert = x => (window.alerts ||= []).push(String(x));
  window.confirm = () => true;
  const probe = window.sensorProbe = { calls: [], deleted: [], shares: [], listeners: {},
    status: { isRunning: false, isStarting: false, isStopping: false, isPaused: false } };
  const plugin = {
    addListener: async (name, fn) => { (probe.listeners[name] ||= []).push(fn); },
    requestDrivePermissions: async () => ({ granted: true, notificationsGranted: true }),
    getStatus: async () => ({ ...probe.status }),
    getDriveEndSummary: async () => ({ available: false }),
    startDrive: async options => {
      probe.calls.push(options);
      probe.status = { ...probe.status, isRunning: true, sessionId: 'sensor-test',
        startRequestId: options.startRequestId, detectionMode: options.detectionMode,
        bumpCount: 3, bumpsWithoutFrame: 1, cameraActive: true, videoSupported: true,
        captureSource: 'phone_camera', status: 'Scanning live' };
      return { ...probe.status };
    },
    attachPreview: async () => {}, detachPreview: async () => {},
    syncReports: async () => ({ reports: [], remaining: 0 }),
    getDrives: async () => ({ drives: probe.history || [] }),
    deleteSensorReport: async ({ id }) => { probe.deleted.push(id); },
    shareSensorLog: async ({ sessionId }) => { probe.shares.push(sessionId); },
  };
  Object.defineProperty(window, 'Capacitor', { configurable: true, value: {
    isNativePlatform: () => true, Plugins: { DriveMode: plugin },
    registerPlugin: name => name === 'DriveMode' ? plugin : {},
  } });
};
const server = http.createServer((req, res) => {
  const relative = new URL(req.url, 'http://localhost').pathname.replace(/^\//, '');
  let file = path.resolve(root, relative);
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ ...(process.platform === 'win32' ? {channel: 'chrome'} : {}), headless: true,
    env: { ...process.env, SystemDrive: process.env.SystemDrive || 'C:' } });
  let assertions = 0;
  const check = (value, message) => { assert.ok(value, message); assertions++; };
  const start = async surface => {
    const context = await browser.newContext();
    await context.route('**/*', r => r.request().url().startsWith(origin) ? r.continue() : r.abort());
    await context.addInitScript(`(${init.toString()})();\n${credentials}`);
    const page = await context.newPage();
    await page.goto(`${origin}/${surface}/`);
    await page.waitForFunction(() => window.StandaloneAPI && window.CredentialBroker);
    await page.evaluate(async () => { await CredentialBroker.ready(); localStorage.setItem('data_notice_version', DATA_NOTICE_VERSION); });
    return { context, page };
  };
  try {
    for (const surface of ['static', 'android-app/www']) {
      for (const configured of [false, true]) {
        const { context, page } = await start(surface);
        try {
          if (configured) await page.evaluate(() => CredentialBroker.storeCredentials({ openAiKey: 'test-fixture-not-a-credential' }));
          if (configured) {
            await page.evaluate(() => openSettings());
            await page.locator('#setBumpSensitivity').selectOption('low');
            await page.locator('#setSave').click();
            await page.waitForFunction(() => localStorage.getItem('bump_sensitivity') === 'low');
          }
          await page.locator('#driveBtn').click();
          await page.waitForFunction(() => sensorProbe.calls.length === 1);
          const call = await page.evaluate(() => sensorProbe.calls[0]);
          check(call.detectionMode === (configured ? 'cloud' : 'sensor'), 'explicit mode');
          check(call.bumpSensitivity === (configured ? 'low' : 'medium'), 'default medium and persisted sensitivity');
          check(await page.locator('#settings').isHidden(), 'no Settings redirect');
          if (!configured) {
            check((await page.locator('#nativeDriveStatus').innerText()).includes('Sensor mode (no AI)'), 'sensor HUD');
            check((await page.locator('#nativeDriveCount').innerText()).includes('3 bumps'), 'bump count');
            check((await page.locator('#nativeDriveCount').innerText()).includes('1 bumps without frame'), 'missing frame count');
          }
        } finally { await context.close(); }
      }
      const { context, page } = await start(surface);
      try {
        const report = { id: 42, capture_source: 'drive_sensor', detection_model: 'sensor-accelerometer-v1',
          decision: 'needs_review', lat: 41.3, lng: 69.2, drive_id: 'test', created_at: 1700000000,
          captured_at: 1700000000, photo_data_url: 'data:image/jpeg;base64,' + jpeg,
          photo_full_data_url: 'data:image/jpeg;base64,' + jpeg, seen_count: 1,
          description: 'Unconfirmed bump. Peak vertical: 7 m/s²; speed: 10 m/s.' };
        const aborted = await page.evaluate(async r => {
          const original = IDBDatabase.prototype.transaction;
          IDBDatabase.prototype.transaction = function(...args) {
            const tx = original.apply(this, args);
            if (args[1] === 'readwrite') queueMicrotask(() => tx.abort());
            return tx;
          };
          try {
            await StandaloneAPI.handle('/api/native-report', {method: 'POST', body: JSON.stringify(r)});
            return false;
          } catch (_) { return true; }
          finally { IDBDatabase.prototype.transaction = original; }
        }, report);
        check(aborted && (await page.evaluate(() => StandaloneAPI.handle('/api/reports'))).length === 0, 'aborted sensor commit stays retryable');
        const imported = await page.evaluate(r => StandaloneAPI.handle('/api/native-report', { method: 'POST', body: JSON.stringify(r) }), report);
        await page.evaluate(async () => { expandedDrives.add('test'); await loadReports(); openDetail(loadReports.latest[0]); });
        check((await page.locator('#detail').innerText()).includes('Bump — unconfirmed'), 'unconfirmed detail');
        check((await page.locator('#list').textContent()).includes('Bump — unconfirmed'), 'unconfirmed list badge');
        check((await page.locator('#detail').innerText()).includes('41.30000, 69.20000'), 'coordinates');
        check((await page.locator('#detail').innerText()).includes('7 m/s²'), 'peak');
        const evidence = await page.evaluate(id => StandaloneAPI.handle(`/api/reports/${id}/evidence`), imported.id);
        check(evidence.text.includes('unconfirmed') && evidence.text.includes('not AI verified'), 'honest export');
        await page.locator('#confirmSensorBtn').click();
        await page.waitForFunction(() => document.querySelector('#detail').textContent.includes('User-reported pothole'));
        check(await page.locator('#confirmSensorBtn').count() === 0, 'confirm action');
        report.seen_count = 2;
        await page.evaluate(r => StandaloneAPI.handle('/api/native-report', { method: 'POST', body: JSON.stringify(r) }), report);
        const records = await page.evaluate(() => StandaloneAPI.handle('/api/reports'));
        check(records.length === 1 && records[0].decision === 'manual' && records[0].seen_count === 2, 'idempotent merge preserves confirmation');
        await page.locator('#discardBtn').click();
        await page.waitForFunction(async () => (await StandaloneAPI.handle('/api/reports')).length === 0);
        check(JSON.stringify(await page.evaluate(() => sensorProbe.deleted)) === '[42]', 'native deletion');
        await page.evaluate(async () => {
          sensorProbe.history = [{id: 'sensor-history', status: 'stopped', started_at: 1700000000,
            sensor_log: true, sensor_bumps: 3, sensor_without_frame: 1, gps_track: []}];
          invalidateNativeDriveHistory(); expandedDrives.add('sensor-history');
          await loadReports(); show('home');
        });
        await page.locator('[data-sharesensor="sensor-history"]').click();
        check(JSON.stringify(await page.evaluate(() => sensorProbe.shares)) === '["sensor-history"]', 'share calibration log');
        check((await page.locator('#list').textContent()).includes('3 bumps · 1 bumps without frame'), 'sensor summary');
        await page.evaluate(() => { LANG = 'uz'; applyLang(); });
        check((await page.locator('#keyLabel').textContent()).includes('ixtiyoriy'), 'Uzbek optional key');
        check(await page.evaluate(() => t('sensor_badge')) === 'Silkinish — tasdiqlanmagan', 'Uzbek badge');
      } finally { await context.close(); }
      console.log(`PASS ${surface}: sensor/cloud admission, review, evidence and delete`);
    }
    console.log(`SENSOR DRIVE BROWSER PASS (${assertions} assertions)`);
  } finally { await browser.close(); server.close(); }
})().catch(e => { console.error(e); server.close(); process.exitCode = 1; });
