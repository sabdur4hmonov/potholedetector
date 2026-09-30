// Real Chromium/IndexedDB tests: no provider calls, no API key, network disabled during reporting.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { chromium } = require('playwright');
const fixture = require('./fixtures/sec010-images.json').jpeg;
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const web = url.pathname.startsWith('/web-app/');
  const base = path.join(root, web ? 'static' : 'android-app/www');
  const relative = url.pathname.slice(web ? 9 : 1) || 'index.html';
  const file = path.resolve(base, relative);
  if (!file.startsWith(base + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
  res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const app = `http://127.0.0.1:${server.address().port}`;
  const profiles = [];
  try {
    for (const suffix of ['/', '/web-app/']) {
      const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'pothole-manual-test-'));
      profiles.push(profile);
      let context;
      const start = async () => {
        context = await chromium.launchPersistentContext(profile, { channel: 'chrome', headless: true,
          env: { ...process.env, SystemDrive: process.env.SystemDrive || path.parse(os.homedir()).root.replace(/[\\/]$/, '') } });
        await context.route('**/*', route => new URL(route.request().url()).origin === app
          ? route.continue() : route.abort());
        await context.addInitScript(() => {
          window.alerts = [];
          window.alert = text => window.alerts.push(String(text));
          window.confirm = () => true;
        });
        const page = await context.newPage();
        await page.goto(app + suffix);
        await page.waitForFunction(() => window.StandaloneAPI && window.CredentialBroker);
        return page;
      };
      try {
        let page = await start();
        await page.locator('#setSave').click();
        await page.waitForFunction(() => localStorage.getItem('initial_setup_complete') === '1');
        assert.equal(await page.evaluate(() => CredentialBroker.hasOpenAi()), false);
        await page.evaluate(jpeg => {
          window.consentProbe = handleFile(new File([Uint8Array.from(atob(jpeg), c => c.charCodeAt(0))], 'road.jpg',
            { type: 'image/jpeg' }), { locationConfirmed: false });
        }, fixture);
        await page.waitForFunction(() => !document.getElementById('dataConsent').classList.contains('hidden'));
        await page.evaluate(async () => { finishDataConsent(false); await window.consentProbe; });
        assert.equal(await page.evaluate(async () => (await StandaloneAPI.handle('/api/reports')).length), 0);
        await page.evaluate(() => localStorage.setItem('data_notice_version', '2026-08-31-v17-dashcam-network'));
        await context.setOffline(true);
        const result = await page.evaluate(async jpeg => {
          const api = StandaloneAPI.handle;
          const fetch = window.fetch;
          let networkAttempts = 0;
          window.fetch = (...args) => {
            if (!/^(data:|blob:)/.test(String(args[0]))) networkAttempts++;
            return fetch(...args);
          };
          const file = () => new File([Uint8Array.from(atob(jpeg), c => c.charCodeAt(0))], 'road.jpg',
            { type: 'image/jpeg', lastModified: 1000000 });
          const fd = (confirmed = true) => {
            const f = new FormData(); f.append('photo', file()); f.append('issue_type', 'road_damage');
            f.append('capture_source', 'manual_import');
            if (confirmed) f.append('issue_confirmed', 'true');
            return f;
          };
          const fails = async action => { try { await action(); return false; } catch (_) { return true; } };
          const before = (await api('/api/reports')).length;
          window.confirm = () => false;
          await handleFile(file(), { locationConfirmed: false });
          const cancelled = (await api('/api/reports')).length === before;
          window.confirm = () => true;
          const noConfirmation = await fails(() => api('/api/manual-report', { method: 'POST', body: fd(false) }));
          const empty = await fails(() => api('/api/manual-report', { method: 'POST', body: new FormData() }));
          const corrupt = fd(); corrupt.set('photo', new Blob(['not an image'], { type: 'image/jpeg' }));
          const invalid = await fails(() => api('/api/manual-report', { method: 'POST', body: corrupt }));
          const transaction = IDBDatabase.prototype.transaction;
          IDBDatabase.prototype.transaction = function(...args) {
            const tx = transaction.apply(this, args);
            if (args[1] === 'readwrite') queueMicrotask(() => tx.abort());
            return tx;
          };
          let aborted;
          try { aborted = await fails(() => api('/api/manual-report', { method: 'POST', body: fd() })); }
          finally { IDBDatabase.prototype.transaction = transaction; }
          await handleFile(file(), { locationConfirmed: false });
          const first = (await api('/api/reports'))[0];
          const second = await api('/api/manual-report', { method: 'POST', body: fd() });
          const camera = fd(); camera.set('capture_source', 'manual_camera');
          camera.set('lat', '41.3'); camera.set('lng', '69.2');
          await api('/api/manual-report', { method: 'POST', body: camera });
          const cloudFailed = await fails(() => api(`/api/reports/${first.id}/cloud-analysis`, {
            method: 'POST', body: JSON.stringify({ confirmed: true }),
          }));
          const cloudUnconfirmed = await fails(() => api(`/api/reports/${first.id}/cloud-analysis`, { method: 'POST' }));
          const evidence = await api(`/api/reports/${first.id}/evidence`);
          await api(`/api/reports/${first.id}/label`, { method: 'POST', body: JSON.stringify({ label: 'pothole' }) });
          const dataset = await api('/api/export', { method: 'POST' });
          return { cancelled, noConfirmation, empty, invalid, aborted, cloudFailed, cloudUnconfirmed,
            first, second, count: (await api('/api/reports')).length, evidence, dataset,
            detail: document.getElementById('detail').textContent, alerts: window.alerts, networkAttempts };
        }, fixture);
        for (const key of ['cancelled', 'noConfirmation', 'empty', 'invalid', 'aborted', 'cloudFailed', 'cloudUnconfirmed']) assert.equal(result[key], true, key);
        assert.equal(result.count, 3);
        assert.notEqual(result.first.id, result.second.id);
        assert.equal(result.first.lat, null);
        assert.equal(result.first.detection_model, null);
        assert.equal(result.first.damage_type, null);
        assert.equal(result.first.size, null);
        assert.equal(result.first.is_pothole, null);
        assert.equal(result.first.report_origin, 'user_reported');
        assert.equal(result.first.dedupe_eligible, false);
        assert.match(result.detail, /User-reported pothole/);
        assert.match(result.evidence.text, /not AI verified/);
        assert.ok(result.evidence.base64.length > 0);
        const zip = Buffer.from(result.dataset.base64, 'base64');
        let index;
        for (let offset = 0; zip.readUInt32LE(offset) === 0x04034b50;) {
          const size = zip.readUInt32LE(offset + 18), names = zip.readUInt16LE(offset + 26), extra = zip.readUInt16LE(offset + 28);
          const name = zip.subarray(offset + 30, offset + 30 + names).toString();
          const start = offset + 30 + names + extra;
          if (name.endsWith('.json')) index = JSON.parse(zip.subarray(start, start + size).toString());
          offset = start + size;
        }
        assert.ok(index, 'dataset index exists');
        assert.equal(index.images[0].model_said, null, 'manual labels must not manufacture model evidence');
        assert.equal(index.images[0].detector, null);
        assert.deepEqual(result.alerts, []);
        assert.equal(result.networkAttempts, 0, 'manual flow and no-key cloud refusal must attempt no network call');
        await context.close(); context = null;
        page = await start(); // packaged assets load locally; report operations remain offline.
        await context.setOffline(true);
        const reopened = await page.evaluate(() => StandaloneAPI.handle('/api/reports'));
        assert.equal(reopened.length, 3);
        assert.ok(reopened.every(row => row.report_origin === 'user_reported' && row.photo_url));
        await page.evaluate(() => StandaloneAPI.handle('/api/reports', { method: 'DELETE' }));
        assert.equal(await page.evaluate(async () => (await StandaloneAPI.handle('/api/reports')).length), 0);
        console.log(`PASS ${suffix}: no-key onboarding, cancelled/invalid input, abort/retry, independent manual saves, optional-cloud failure, evidence and browser restart`);
      } finally { if (context) await context.close(); }
    }
  } finally {
    server.close();
    for (const profile of profiles) {
      assert.ok(profile.startsWith(path.join(os.tmpdir(), 'pothole-manual-test-')));
      fs.rmSync(profile, { recursive: true, force: true });
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; server.close(); });
