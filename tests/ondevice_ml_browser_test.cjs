// Chromium coverage of the production web UI, IndexedDB and full-frame dataset ZIP.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const credentials = fs.readFileSync(path.join(__dirname, 'browser_test_utils.py'), 'utf8')
  .match(/SECURE_CREDENTIALS_MOCK = r"""([\s\S]*?)"""/)[1];
const jpeg = require('./fixtures/sec010-images.json').jpeg;

function init() {
  localStorage.setItem('initial_setup_complete', '1');
  window.alert = value => (window.alerts ||= []).push(String(value));
  const plugin = {
    getDetectorStatus: async () => ({status: window.detectorStatus || 'not_installed'}),
    getStatus: async () => ({isRunning: false}),
    addListener: async () => {}, getDriveEndSummary: async () => ({available: false}),
    getDrives: async () => ({drives: []}), syncReports: async () => ({reports: [], remaining: 0}),
    setHazards: async () => ({}),
  };
  Object.defineProperty(window, 'Capacitor', {configurable: true, value: {
    isNativePlatform: () => true, Plugins: {DriveMode: plugin}, registerPlugin: () => plugin,
  }});
}

function unzipStored(base64) {
  const data = Buffer.from(base64, 'base64');
  const entries = new Map();
  let at = 0;
  while (data.readUInt32LE(at) === 0x04034b50) {
    const size = data.readUInt32LE(at + 18);
    const nameSize = data.readUInt16LE(at + 26);
    const extra = data.readUInt16LE(at + 28);
    const start = at + 30 + nameSize + extra;
    entries.set(data.toString('utf8', at + 30, at + 30 + nameSize), data.subarray(start, start + size));
    at = start + size;
  }
  return entries;
}

(async () => {
  const browser = await chromium.launch({...(process.platform === 'win32' ? {channel: 'chrome'} : {}), headless: true});
  try {
    for (const surface of ['web-app/', '']) {
      const context = await browser.newContext();
      try {
        await context.addInitScript(`(${init.toString()})();\n${credentials}`);
        const app = process.env.POTHOLE_TEST_APP || 'http://localhost:8765/';
        await context.route('**/*', route => route.request().url().startsWith(new URL(app).origin) ? route.continue() : route.abort());
        const page = await context.newPage();
        await page.goto(app + surface);
        await page.evaluate(async () => { await CredentialBroker.ready(); openSettings(); });
        await page.waitForFunction(() => document.querySelector('#cameraDetectorStatus').textContent === 'Camera detector: not installed');
        assert.equal(await page.locator('#setOnDevice').isChecked(), true);
        await page.evaluate(() => { window.detectorStatus = 'ready'; openSettings(); });
        await page.waitForFunction(() => document.querySelector('#cameraDetectorStatus').textContent === 'Camera detector: ready');
        const native = {id: 41, capture_source: 'drive_camera', detection_model: 'yolox-nano-rdd2022-v1',
          decision: 'needs_review', lat: 41.3, lng: 69.2, drive_id: 'camera-drive', created_at: 1700000000,
          captured_at: 1700000000, photo_data_url: 'data:image/jpeg;base64,' + jpeg,
          photo_full_data_url: 'data:image/jpeg;base64,' + jpeg};
        const importRow = report => page.evaluate(r => StandaloneAPI.handle('/api/native-report', {method: 'POST', body: JSON.stringify(r)}), report);
        const hazards = () => page.evaluate(async () => (await StandaloneAPI.handle('/api/hazards')).hazards);
        const imported = await importRow(native);
        assert.equal((await hazards())[0].kind, 'unconfirmed');
        await page.evaluate(async () => { await loadReports(); openDetail(loadReports.latest[0]); });
        assert.match(await page.locator('#detail .verdict').textContent(), /Pothole — camera/);
        native.capture_source = 'drive_camera_bump';
        assert.equal((await importRow(native)).id, imported.id);
        assert.equal((await hazards())[0].kind, 'confirmed');
        await page.evaluate(async () => { await loadReports(); openDetail(loadReports.latest[0]); });
        assert.match(await page.locator('#detail .verdict').textContent(), /Pothole — camera \+ bump/);
        await page.locator('#wrongOfflineBtn').click();
        await page.waitForFunction(() => document.querySelector('#detail .verdict').textContent.includes('No — corrected'));
        assert.equal((await hazards()).length, 0);
        await importRow(native);
        assert.equal((await hazards()).length, 0, 'retry preserves owner No label');
        const exportRows = async include => {
          const zip = await page.evaluate(include_location => StandaloneAPI.handle('/api/export', {method: 'POST', body: JSON.stringify({include_location})}), include);
          const entries = unzipStored(zip.base64);
          const row = JSON.parse(entries.get('labels.json')).images[0];
          assert.ok(entries.get(row.path).length > 100);
          return row;
        };
        const no = await exportRows(false);
        assert.equal(no.label_yes_no, 'No');
        assert.equal(no.model_version, native.detection_model);
        for (const key of ['lat', 'lng', 'address', 'drive_id']) assert.equal(key in no, false);
        assert.equal((await exportRows(true)).lat, 41.3);
        await page.locator('#correctOfflineBtn').click();
        await page.waitForFunction(async () => (await StandaloneAPI.handle('/api/hazards')).hazards.length === 1);
        assert.equal((await exportRows(false)).label_yes_no, 'Yes');
      } finally { await context.close(); }
    }
    console.log('ON-DEVICE ML BROWSER PASS (2 surfaces: status, fusion, labels, full-frame ZIP, GPS opt-in)');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
