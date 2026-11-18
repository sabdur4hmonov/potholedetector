// Production IndexedDB and UI with the shared native bridge credential mock, no provider.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const credentials = fs.readFileSync(path.join(__dirname, 'browser_test_utils.py'), 'utf8')
  .match(/SECURE_CREDENTIALS_MOCK = r"""([\s\S]*?)"""/)[1];
const jpeg = require('./fixtures/sec010-images.json').jpeg;
const init = () => {
  localStorage.setItem('initial_setup_complete', '1');
  window.alert = value => (window.alerts ||= []).push(String(value));
  window.confirm = () => true;
  const p = window.hazardProbe = {order: [], snapshots: [], starts: [], tests: [], status: {isRunning: false}};
  const plugin = {
    addListener: async () => {},
    requestDrivePermissions: async () => ({granted: true, notificationsGranted: true}),
    getStatus: async () => ({...p.status}),
    getDriveEndSummary: async () => ({available: false}),
    setHazards: async snapshot => {p.order.push('hazards'); p.snapshots.push(snapshot); return {loaded: snapshot.hazards.length};},
    testWarning: async options => p.tests.push(options),
    startDrive: async options => {
      p.order.push('start'); p.starts.push(options);
      return p.status = {isRunning: true, sessionId: 'warning-test', startRequestId: options.startRequestId,
        detectionMode: 'sensor', captureSource: 'phone_camera', cameraActive: true, hazardsLoaded: 3,
        lastHazardAlert: 'Possible pothole in 250 meters', status: 'Scanning live'};
    },
    attachPreview: async () => {}, detachPreview: async () => {},
    syncReports: async () => ({reports: [], remaining: 0}), getDrives: async () => ({drives: []}),
    deleteSensorReport: async () => {},
  };
  Object.defineProperty(window, 'Capacitor', {configurable: true, value: {
    isNativePlatform: () => true, Plugins: {DriveMode: plugin}, registerPlugin: () => plugin,
  }});
};
(async () => {
  const browser = await chromium.launch({...(process.platform === 'win32' ? {channel: 'chrome'} : {}), headless: true});
  let count = 0;
  const check = (value, reason) => {assert.ok(value, reason); count++;};
  try {
    for (const surface of ['web-app/', '']) {
      const context = await browser.newContext();
      const app = process.env.POTHOLE_TEST_APP || 'http://localhost:8765/';
      await context.route('**/*', r => r.request().url().startsWith(new URL(app).origin) ? r.continue() : r.abort());
      await context.addInitScript(`(${init.toString()})();\n${credentials}`);
      const page = await context.newPage();
      const violations = [];
      page.on('console', msg => { if (/Refused to (execute|load)/.test(msg.text())) violations.push(msg.text()); });
      try {
        await page.goto(app + surface);
        await page.evaluate(async () => {await CredentialBroker.ready(); localStorage.setItem('data_notice_version', DATA_NOTICE_VERSION);});
        // Seed representative existing web-only/manual, accepted AI and excluded records.
        await page.evaluate(async () => {
          await StandaloneAPI.handle('/api/hazards');
          const db = await new Promise((resolve, reject) => {const q = indexedDB.open('potholes', 7); q.onsuccess = () => resolve(q.result); q.onerror = () => reject(q.error);});
          await new Promise((resolve, reject) => {
            const tx = db.transaction('reports', 'readwrite'); const store = tx.objectStore('reports');
            const base = {created_at: 1700000000, lat: 41.3, lng: 69.2, decision: 'manual', is_pothole: 1, status: 'draft', report_origin: 'user_reported',
              condition_status: 'repair_review', repair_current_condition: 'repaired', repair_same_location_visible: true, repair_completed_visible: true,
              repair_image_quality: 'usable', repair_photo: new Blob(['synthetic repair evidence'])};
            for (const record of [
              {...base, id: 1, capture_source: 'manual_camera'},
              {...base, id: 2, decision: 'accept', report_origin: 'ai_detection'},
              {...base, id: 3, condition_status: 'fixed'}, {...base, id: 4, debug_capture: true},
              {...base, id: 5, lat: null}, {...base, id: 6, lng: 181}, {...base, id: 7, deleted: true},
              {...base, id: 8, decision: 'reject', is_pothole: 0}, {...base, id: 9, human_label: 'not_pothole'},
            ]) store.put(record);
            tx.oncomplete = resolve; tx.onabort = () => reject(tx.error);
          }); db.close();
        });
        const report = {id: 42, capture_source: 'drive_sensor', detection_model: 'sensor-accelerometer-v1', decision: 'needs_review',
          lat: 41.31, lng: 69.21, drive_id: 'old-drive', created_at: 1700000000, captured_at: 1700000000,
          photo_data_url: 'data:image/jpeg;base64,' + jpeg, description: 'Unconfirmed bump. Peak: 7 m/s²; speed: 10 m/s.'};
        const imported = await page.evaluate(r => StandaloneAPI.handle('/api/native-report', {method: 'POST', body: JSON.stringify(r)}), report);
        await page.locator('#driveBtn').click();
        await page.waitForFunction(() => hazardProbe.starts.length === 1);
        const state = await page.evaluate(() => hazardProbe);
        check(state.order.indexOf('hazards') < state.order.indexOf('start'), 'snapshot commits before startDrive');
        const hazards = state.snapshots.at(-1).hazards;
        check(hazards.length === 3 && hazards.filter(h => h.kind === 'confirmed').length === 2, 'accepted/manual plus unconfirmed only');
        check(hazards.some(h => h.id === 'native:42' && h.kind === 'unconfirmed'), 'native identity matches current-drive overlay');
        check(state.starts[0].warningsEnabled && state.starts[0].warningLeadSeconds === 20 && state.starts[0].warningUnconfirmed, 'owner defaults');
        check((await page.locator('#nativeHazardStatus').textContent()).includes('Warnings: 3 potholes loaded'), 'loaded HUD');
        check((await page.locator('#nativeHazardStatus').textContent()).includes('Possible pothole'), 'last native alert HUD');
        await page.evaluate(id => StandaloneAPI.handle(`/api/reports/${id}/confirm-sensor`, {method: 'POST', body: '{"confirmed":true}'}), imported.id);
        await page.waitForFunction(() => hazardProbe.snapshots.at(-1).hazards.some(h => h.id === 'native:42' && h.kind === 'confirmed'));
        check(true, 'confirmation resends authoritative snapshot');
        await page.evaluate(id => StandaloneAPI.handle(`/api/reports/${id}`, {method: 'DELETE'}), imported.id);
        await page.waitForFunction(() => !hazardProbe.snapshots.at(-1).hazards.some(h => h.id === 'native:42'));
        check(true, 'deletion removes warning');
        report.id = 43;
        await page.evaluate(r => StandaloneAPI.handle('/api/native-report', {method: 'POST', body: JSON.stringify(r)}), report);
        await page.waitForFunction(() => hazardProbe.snapshots.at(-1).hazards.some(h => h.id === 'native:43'));
        check(true, 'native outbox import resends snapshot');
        await page.evaluate(() => StandaloneAPI.handle('/api/reports/1/condition', {method: 'POST', body: '{"condition_status":"fixed"}'}));
        await page.waitForFunction(() => !hazardProbe.snapshots.at(-1).hazards.some(h => h.id === 'web:1'));
        check(true, 'marking fixed removes warning after commit');
        await page.evaluate(() => openSettings());
        check(await page.locator('#setWarnings').isChecked(), 'warning default on');
        await page.locator('#setWarnings').uncheck(); await page.locator('#setWarningLead').selectOption('30');
        await page.locator('#setWarningUnconfirmed').uncheck(); await page.locator('#setDriveLimit').selectOption('180');
        await page.locator('#testWarningBtn').click();
        await page.waitForFunction(() => hazardProbe.tests.length === 1);
        check(true, 'Test warning calls real native entry point');
        await page.locator('#setSave').click();
        await page.waitForFunction(() => localStorage.getItem('warning_lead_seconds') === '30');
        await page.evaluate(() => openSettings());
        check(!(await page.locator('#setWarnings').isChecked()) && !(await page.locator('#setWarningUnconfirmed').isChecked())
          && await page.locator('#setWarningLead').inputValue() === '30' && await page.locator('#setDriveLimit').inputValue() === '180', 'settings round-trip');
        check(await page.locator('#setDriveLimit option[value="120"]').count() === 1, '120 minute option');
        await page.evaluate(() => {LANG = 'uz'; applyLang();});
        check((await page.locator('#warningsLabel').textContent()).includes('ogohlantirish'), 'Uzbek warning controls');
        await page.evaluate(() => {hazardProbe.status = {isRunning: false}; drive = null; show('home');});
        await page.locator('#driveBtn').click();
        await page.waitForFunction(() => hazardProbe.starts.length === 2);
        const next = await page.evaluate(() => hazardProbe.starts[1]);
        check(!next.warningsEnabled && next.warningLeadSeconds === 30 && !next.warningUnconfirmed
          && next.maxDurationMinutes === 180, 'persisted options passed on next Drive');
        check(violations.length === 0, 'CSP enforced without blocked code');
        // Failure is all-or-nothing rather than silently dropping >5,000 reports.
        const oversized = await page.evaluate(async () => {
          const db = await new Promise(resolve => {const q = indexedDB.open('potholes', 7); q.onsuccess = () => resolve(q.result);});
          await new Promise(resolve => {const tx = db.transaction('reports', 'readwrite'); const s = tx.objectStore('reports');
            s.clear(); for (let i = 1; i <= 5001; i++) s.put({id: i, lat: 41, lng: 69, decision: 'manual', is_pothole: 1}); tx.oncomplete = resolve;});
          db.close(); try {await StandaloneAPI.handle('/api/hazards'); return false;} catch (_) {return true;}
        });
        check(oversized, 'oversize web list rejects before native start');
        console.log(`PASS ${surface || 'android-app/www'}: snapshots, confirmation/deletion, HUD and settings`);
      } finally {await context.close();}
    }
    console.log(`HAZARD ALERTS BROWSER PASS (${count} assertions)`);
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exitCode = 1;});
