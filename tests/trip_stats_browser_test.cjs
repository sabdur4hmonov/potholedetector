// Real dashboard/IndexedDB consumer, canonical and packaged surfaces, offline.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const canonical = url.pathname.startsWith('/web-app/');
  const base = path.join(root, canonical ? 'static' : 'android-app/www');
  const file = path.resolve(base, url.pathname.slice(canonical ? 9 : 1) || 'index.html');
  if (!file.startsWith(base + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'text/javascript' }[path.extname(file)] || 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ channel: 'chrome', headless: true,
      env: { ...process.env, SystemDrive: process.env.SystemDrive || path.parse(os.homedir()).root.replace(/[\\/]$/, '') } });
    for (const suffix of ['/', '/web-app/']) {
      const context = await browser.newContext();
      try {
        await context.addInitScript(() => localStorage.setItem('app_lang', 'en'));
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto(`http://127.0.0.1:${server.address().port}${suffix}`);
        await page.waitForFunction(() => window.TripStats && window.StandaloneAPI);
        await context.setOffline(true);
        let attempts = 0;
        await context.route('**/*', route => { attempts++; return route.abort(); });
        await page.evaluate(() => openDash());
        assert.equal(await page.locator('[data-trip-coverage]').getAttribute('data-trip-coverage'), 'unavailable');
        assert.match(await page.locator('#dashStats').textContent(), /Unavailable/);
        const result = await page.evaluate(async () => {
          const tracks = [
            [[0, 41, 69, 0], [10, 41.001, 69, 0], [20, 41.002, 69, 0]],
            [[0, 41, 69, 10, 100], [10, 41.000001, 69, 10, 100]],
            [[0, 41, 69, 40], [10, 41.1, 69, 40]],
          ];
          for (let i = 0; i < tracks.length; i++) await api('/api/drives', {
            method: 'POST', body: JSON.stringify({ id: `trip-test-${i}`, gps_track: tracks[i] }) });
          const before = JSON.stringify(await api('/api/drives'));
          await openDash();
          const text = document.querySelector('#dashStats').textContent;
          await openDash();
          return { before, after: JSON.stringify(await api('/api/drives')), text,
            repeat: document.querySelector('#dashStats').textContent };
        });
        assert.equal(result.before, result.after, 'rendering does not persist derived statistics or mutate tracks');
        assert.equal(result.text, result.repeat, 'repeated rendering is deterministic');
        assert.match(result.text, /0\.2\s+Estimated sampled km/);
        assert.match(result.text, /0\.3\s+Estimated moving minutes/);
        assert.match(result.text, /40\.0\s+Estimated moving km\/h/);
        assert.match(result.text, /40\.0\s+Peak sampled km\/h \(private\)/);
        assert.match(result.text, /Partial GPS coverage/);
        assert.match(result.text, /not total journey distance or measured peak speed/);
        assert.equal(await page.locator('[data-trip-coverage]').getAttribute('data-trip-coverage'), 'partial');
        assert.equal(attempts, 0, 'private statistics perform no network request');
        assert.deepEqual(errors, [], 'dashboard executes under enforced CSP');
        console.log(`PASS ${suffix}: offline dashboard, unknown/partial/estimates, deterministic rendering, IndexedDB unchanged and CSP`);
      } finally { await context.close(); }
    }
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
