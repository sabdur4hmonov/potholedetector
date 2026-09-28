const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const root = path.resolve(__dirname, '..');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.POTHOLE_TEST_CHROME ? { executablePath: process.env.POTHOLE_TEST_CHROME } : {}) });
  let scenarios = 0;
  try {
    for (const native of [false, true]) {
      const context = await browser.newContext();
      await context.addInitScript(() => { Date.now = () => Date.parse("2026-08-29T12:00:00Z"); });
      const requests = [];
      let corrupted = null;
      if (native) await context.addInitScript(() => {
        window.CapacitorWebFetch = window.fetch.bind(window);
        window.Capacitor = { isNativePlatform: () => true, getServerUrl: () => location.origin, Plugins: {} };
        const original = window.fetch.bind(window);
        window.fetch = (url, options) => {
          if (/^https?:/.test(String(url))) throw new Error('Buffered/native fetch path forbidden in fixture');
          return original(url, options);
        };
      });
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        let resourcePath = url.pathname.replace(/^\/web-app\//, '/');
        if (url.pathname === '/_capacitor_http_interceptor_') {
          resourcePath = new URL(url.searchParams.get('u')).pathname.replace(/^\/pothole-reporter\//, '/');
        }
        if (resourcePath.startsWith('/packs/v1/')) {
          requests.push(resourcePath);
          const filename = path.join(root, 'docs', resourcePath);
          let body = Buffer.from(fs.readFileSync(filename, 'utf8').replace(/\r\n/g, '\n'));
          // Windows checkout converts fixture newlines; serve the original signed bytes.
          const pinnedHash = resourcePath.match(/-([0-9a-f]{64})\.json$/)[1];
          assert.equal(createHash('sha256').update(body).digest('hex'), pinnedHash);
          if (resourcePath === corrupted) { body = Buffer.from(body); body[body.length - 2] ^= 1; }
          await route.fulfill({ status: 200, contentType: 'application/json', body,
            headers: { 'Content-Length': String(body.length) } });
        } else await route.continue();
      });
      const page = await context.newPage();
      await page.goto(process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/web-app/');
      await page.waitForFunction(() => window.StandaloneAPI && StandaloneAPI.__pure);
      const results = await page.evaluate(async () => {
        const api = StandaloneAPI.__pure;
        const state = await api.getStatePackManifest();
        const highway = await api.getHighwayPackManifest();
        const contract = await api.getContractPackManifest();
        const notice = await api.getRoadNoticeManifest();
        const agreement = await api.getRoadAgreementManifest();
        const tile = Object.keys(highway.tiles)[0];
        const contractState = Object.values(contract.resources)[0].state_code;
        const noticeState = Object.values(notice.resources)[0].state_code;
        const agreementState = Object.values(agreement.resources)[0].state_code;
        return {
          state: !!(await api.loadStatePack('in-ka-tenders')),
          highway: !!(await api.loadHighwayTile(tile)),
          contract: !!(await api.loadHighwayContractPack(contractState)),
          notice: !!(await api.loadRoadNoticePack(noticeState)),
          agreement: !!(await api.loadRoadAgreementPack(agreementState)),
          savedPath: state.resources['in-ka-tenders'].path,
          rejectPath: state.resources['in-mh-routing'].path,
        };
      });
      for (const kind of ['state', 'highway', 'contract', 'notice', 'agreement']) {
        assert.equal(results[kind], true, `${native ? 'native proxy mock' : 'browser'} ${kind} fixture download`);
        scenarios++;
      }
      await page.evaluate(() => {
        window.__sec004CacheSnapshot = async () => {
          const rows = await new Promise((resolve, reject) => {
            const request = indexedDB.open('potholes', 6);
            request.onerror = () => reject(new Error('Fixture database unavailable'));
            request.onsuccess = () => {
              const db = request.result;
              const read = db.transaction('state_packs').objectStore('state_packs').getAll();
              read.onerror = () => { db.close(); reject(new Error('Fixture read failed')); };
              read.onsuccess = () => { db.close(); resolve(read.result); };
            };
          });
          return Promise.all(rows.map(async row => ({ key: row.cache_key,
            hash: [...new Uint8Array(await crypto.subtle.digest('SHA-256', await row.blob.arrayBuffer()))]
              .map(x => x.toString(16).padStart(2, '0')).join('') })));
        };
      });
      const snapshot = await page.evaluate(() => __sec004CacheSnapshot());
      corrupted = '/' + results.rejectPath;
      const before = requests.length;
      assert.equal(await page.evaluate(() => StandaloneAPI.__pure.loadStatePack('in-mh-routing')), null);
      assert.equal(requests.length, before + 1);
      assert.deepEqual(await page.evaluate(() => __sec004CacheSnapshot()), snapshot); scenarios++;
      assert.equal(await page.evaluate(() => StandaloneAPI.__pure.loadStatePack('in-mh-routing')), null);
      assert.equal(requests.length, before + 2); scenarios++;
      const file = Buffer.from(fs.readFileSync(path.join(root, 'docs', results.savedPath), 'utf8').replace(/\r\n/g, '\n'));
      assert.ok(snapshot.some(row => row.hash === createHash('sha256').update(file).digest('hex')));
      await context.close();
    }
    console.log(`SEC004 PACK FLOW PASS (${scenarios} browser/native-proxy-mock scenarios)`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

