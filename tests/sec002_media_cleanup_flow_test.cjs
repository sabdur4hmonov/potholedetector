const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.POTHOLE_TEST_CHROME ? { executablePath: process.env.POTHOLE_TEST_CHROME } : {}),
    args: ['--disable-web-security'] });
  try {
    const context = await browser.newContext();
    await context.addInitScript(() => {
      window.__media = { active: null, events: [], outcome: 'success', cleanupFail: false };
      const media = window.__media;
      const ManagedMedia = {
        beginOperation: async ({ kind }) => {
          if (media.active) throw new Error('Active media operation');
          media.active = crypto.randomUUID(); media.events.push(`begin:${kind}`);
          return { token: media.active };
        },
        endOperation: async ({ token }) => {
          if (token !== media.active) throw new Error('Invalid operation');
          media.events.push('end'); media.active = null;
          if (media.cleanupFail) throw new Error('Temporary media cleanup incomplete');
          return { cleaned: true };
        },
      };
      const status = () => ({ openAiConfigured: false, dashcamRtspConfigured: false });
      window.Capacitor = { isNativePlatform: () => true, Plugins: {
        ManagedMedia,
        SecureCredentials: { getStatus: async () => status(), migrateLegacyCredentials: async () => status() },
        DriveMode: {
          getStatus: async () => ({ active: false }), getDrives: async () => ({ drives: [] }),
          clearNativeData: async () => {
            if (media.active) throw new Error('Finish the active media operation before retrying');
            if (media.wipeFail) return { cleared: false };
            media.events.push('wipe'); return { cleared: true };
          },
        },
      } };
      window.alert = () => {};
    });
    const page = await context.newPage();
    await page.goto(process.env.POTHOLE_TEST_APP || 'http://localhost:8765/');
    await page.waitForFunction(() => window.withManagedMediaOperation && window.StandaloneAPI);
    let scenarios = 0;
    for (const kind of ['camera', 'email', 'share']) {
      for (const outcome of ['success', 'cancel', 'failure']) {
        const result = await page.evaluate(async ({ kind, outcome }) => {
          __media.events = [];
          let failed = false;
          try { await withManagedMediaOperation(kind, async () => {
            __media.events.push(outcome);
            if (outcome !== 'success') throw new Error('Synthetic outcome');
          }); } catch (_) { failed = true; }
          return { events: __media.events, active: __media.active, failed };
        }, { kind, outcome });
        assert.deepEqual(result, { events: [`begin:${kind}`, outcome, 'end'], active: null,
          failed: outcome !== 'success' });
        scenarios++;
      }
    }
    for (const outcome of ['success', 'cancel', 'failure', 'import-failure']) {
      const events = await page.evaluate(async (outcome) => {
        __media.events = [];
        requestNativeCapturePermissions = async () => {};
        startCapturePositionSampler = () => ({ positionAt: async () => null, stop: () => {} });
        StandaloneAPI.prewarm = () => {};
        handleFile = async () => {
          __media.events.push('import');
          if (outcome === 'import-failure') throw new Error('Synthetic import failure');
        };
        Capacitor.Plugins.Camera = { getPhoto: async () => {
          __media.events.push('camera');
          if (outcome === 'cancel') throw { code: 'OS-PLUG-CAMR-0006', message: 'Cancelled' };
          if (outcome === 'failure') throw new Error('Synthetic capture failure');
          return { webPath: 'data:image/jpeg;base64,/9j/2Q==', format: 'jpeg' };
        } };
        await beginPotholeCapture();
        return __media.events;
      }, outcome);
      assert.deepEqual(events, outcome === 'cancel' || outcome === 'failure'
        ? ['begin:camera', 'camera', 'end'] : ['begin:camera', 'camera', 'import', 'end']);
      scenarios++;
    }
    const shareEvents = await page.evaluate(async () => {
      __media.events = [];
      Capacitor.Plugins.Filesystem = {
        mkdir: async () => {}, writeFile: async () => { __media.events.push('write'); return { uri: 'file://test-only' }; },
      };
      Capacitor.Plugins.Share = { share: async () => { __media.events.push('share'); } };
      await shareZip({ name: 'test-only.zip', base64: 'AA==' });
      return __media.events;
    });
    assert.deepEqual(shareEvents, ['begin:share', 'write', 'share', 'end']); scenarios++;
    const overlap = await page.evaluate(async () => {
      localStorage.setItem('sec002-probe', 'test-only');
      await StandaloneAPI.handle('/api/reports', { method: 'DELETE' });
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open('potholes', 7);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      await new Promise((resolve, reject) => {
        const tx = db.transaction(['reports', 'drives', 'footage'], 'readwrite');
        tx.objectStore('reports').put({ id: 9001, photo: new Blob(['test-only-photo']) });
        tx.objectStore('drives').put({ id: 'sec002-test-drive' });
        tx.objectStore('footage').put({ key: 'sec002-test-drive#1', drive_id: 'sec002-test-drive', blob: new Blob(['test-only-video']) });
        tx.oncomplete = resolve; tx.onabort = () => reject(tx.error);
      });
      const cache = await caches.open('sec002-test-cache');
      await cache.put('/sec002-test-probe', new Response('test-only'));
      let release;
      const pending = withManagedMediaOperation('email', () => new Promise(resolve => { release = resolve; }));
      while (!release) await new Promise(resolve => setTimeout(resolve, 0));
      let failed = false;
      try { await deleteAllAppData(); } catch (_) { failed = true; }
      const retained = localStorage.getItem('sec002-probe');
      release(); await pending;
      const result = await deleteAllAppData();
      const remaining = await Promise.all(['reports', 'drives', 'footage'].map(name =>
        new Promise(resolve => { const request = db.transaction(name).objectStore(name).count(); request.onsuccess = () => resolve(request.result); })));
      db.close();
      return { failed, retained, cleared: result.cleared,
        local: localStorage.length, session: sessionStorage.length, remaining, caches: await caches.keys() };
    });
    assert.deepEqual(overlap, { failed: true, retained: 'test-only', cleared: true, local: 0, session: 0,
      remaining: [0, 0, 0, 0], caches: [] }); scenarios++;
    const failure = await page.evaluate(async () => {
      nativeWipeInProgress = false;
      __media.wipeFail = true;
      localStorage.setItem('sec002-retry', 'test-only');
      let failed = false;
      try { await deleteAllAppData(); } catch (_) { failed = true; }
      __media.wipeFail = false;
      return { failed, retained: localStorage.getItem('sec002-retry'), gateOpen: !nativeWipeInProgress };
    });
    assert.deepEqual(failure, { failed: true, retained: 'test-only', gateOpen: true }); scenarios++;
    const endFailure = await page.evaluate(async () => {
      __media.cleanupFail = true;
      let failed = false;
      try { await withManagedMediaOperation('email', async () => {}); } catch (_) { failed = true; }
      __media.cleanupFail = false;
      return { failed, active: __media.active };
    });
    assert.deepEqual(endFailure, { failed: true, active: null }); scenarios++;
    const lateWriter = await page.evaluate(async () => {
      nativeWipeInProgress = true;
      __media.events = [];
      let failed = false;
      try { await withManagedMediaOperation('email', async () => { __media.events.push('late-write'); }); }
      catch (_) { failed = true; }
      nativeWipeInProgress = false;
      return { failed, events: __media.events };
    });
    assert.deepEqual(lateWriter, { failed: true, events: [] }); scenarios++;
    console.log(`SEC002 browser flow PASS: ${scenarios} scenarios (native operations mocked)`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
