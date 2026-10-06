// Exercise the production detail consumer in Chromium, with networking disabled after load.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const fixture = JSON.parse(fs.readFileSync(path.join(root,
  'android-app/android/app/src/test/resources/hazard-evidence-v1.json'), 'utf8'));
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const canonical = url.pathname.startsWith('/web-app/');
  const base = path.join(root, canonical ? 'static' : 'android-app/www');
  const file = path.resolve(base, url.pathname.slice(canonical ? 9 : 1) || 'index.html');
  if (!file.startsWith(base + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); res.end(); return;
  }
  res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'text/javascript',
    '.css': 'text/css', '.json': 'application/json' }[path.extname(file)] || 'application/octet-stream');
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
        await page.waitForFunction(() => window.HazardModel && window.StandaloneAPI);
        await context.setOffline(true);
        let attempts = 0;
        await context.route('**/*', route => { attempts++; return route.abort(); });
        const results = await page.evaluate(fixture => fixture.cases.map((row, index) => {
          const report = { ...fixture.defaults, ...row.report, id: index + 1,
            issue_type: 'road_damage', status: 'draft',
            photo_url: null };
          const before = JSON.stringify(report);
          openDetail(report);
          const text = document.querySelector('[data-hazard-evidence]').textContent;
          return { id: row.id, text, mutated: JSON.stringify(report) !== before };
        }), fixture);
        for (const result of results) {
          assert.equal(result.mutated, false, result.id);
          assert.match(result.text, /Visual severity estimate/, result.id);
          assert.match(result.text, /no physical depth, area or safety rating/, result.id);
        }
        const text = id => results.find(r => r.id === id).text;
        assert.match(text('distinct_drives'), /Reobserved across distinct drives/);
        assert.match(text('distinct_drives'), /do not establish independent people or a probability/);
        assert.match(text('extreme_replay_count'), /Single observation/);
        assert.match(text('manual_private'), /User-reported.*remain unknown/);
        assert.match(text('conflicting_binary_gate'), /Unknown \/ insufficient/);
        assert.match(text('fixed_historical'), /Historical observation evidence/);
        // All three detail branches consume the same policy, including review/rejected.
        for (const status of ['review', 'rejected', 'draft']) {
          await page.evaluate(status => openDetail({ id: 100, issue_type: 'road_damage',
            status, decision: 'reject', is_pothole: 0, is_reportable: 0,
            delivery_channel: null, email_body: '', email_subject: '' }), status);
          assert.match(await page.locator('[data-hazard-evidence]').textContent(), /Unknown \/ insufficient/);
        }
        assert.equal(attempts, 0, 'detail derivation performs no network request');
        assert.deepEqual(errors, [], 'production scripts execute under CSP');
        console.log(`PASS ${suffix}: ${results.length} evidence cases, detail branches, offline/CSP and no mutation`);
      } finally { await context.close(); }
    }
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
