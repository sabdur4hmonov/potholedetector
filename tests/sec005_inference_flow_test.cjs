const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.env.POTHOLE_TEST_CHROME ? { executablePath: process.env.POTHOLE_TEST_CHROME } : {}) });
  let scenarios = 0;
  try {
    // Browser builds refuse paid inference outright (SEC-006, covered by the SEC006 flow test),
    // so the response-hardening scenarios exercise the native gateway path only.
    for (const native of [true]) {
      const context = await browser.newContext();
      await context.addInitScript(native => {
        window.__inferenceFixture = { text: '', cancelled: 0, requests: 0 };
        const fixture = window.__inferenceFixture;
        if (native) {
          const status = () => ({ openAiConfigured: true, dashcamRtspConfigured: false });
          window.Capacitor = { isNativePlatform: () => true, Plugins: {
            SecureCredentials: { getStatus: async () => status(), migrateLegacyCredentials: async () => status(),
              openAiRequest: async () => { fixture.requests++; return { status: 200, ok: true, body: fixture.text }; } },
          } };
        } else {
          const original = window.fetch.bind(window);
          window.fetch = (url, options) => {
            if (!String(url).startsWith('https://api.openai.com/')) return original(url, options);
            fixture.requests++;
            const data = new TextEncoder().encode(fixture.text);
            let sent = false;
            return Promise.resolve(new Response(new ReadableStream({
              pull(controller) { if (!sent) { sent = true; controller.enqueue(data); } },
              cancel() { fixture.cancelled++; },
            }), { headers: { 'content-type': 'text/event-stream' } }));
          };
        }
      }, native);
      await context.route('**/standalone.js', route => {
        const text = fs.readFileSync(path.join(root, 'static/standalone.js'), 'utf8')
          .replace('  window.StandaloneAPI =', '  window.__sec005 = { oaiStream, oai, drainSSE, createInferenceSseState, CredentialBroker };\n  window.StandaloneAPI =');
        return route.fulfill({ contentType: 'application/javascript', body: text });
      });
      const page = await context.newPage();
      await page.goto(process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/');
      await page.waitForFunction(() => window.__sec005);
      if (!native) await page.evaluate(() => __sec005.CredentialBroker.storeCredentials({ openAiKey: 'test-key-never-sent' }));
      const result = await page.evaluate(async () => {
        const event = value => `data: ${JSON.stringify(value)}\n\n`;
        __inferenceFixture.text = event({ type: 'response.output_text.delta', delta: '{"ok":true}' }) + 'data: [DONE]\n\n';
        return __sec005.oaiStream({ model: 'gpt-5-mini' }, null, false);
      });
      assert.equal(result.ok, true); scenarios++;
      for (const text of ['data: ' + 'x'.repeat(32768), 'data: {bad}\n\n',
        'data: {"type":"response.output_text.delta","delta":1}\n\n']) {
        const rejected = await page.evaluate(async text => {
          __inferenceFixture.text = text;
          try { await __sec005.oaiStream({ model: 'gpt-5-mini' }, null, false); return false; }
          catch (error) { return error.inferenceSafety === true; }
        }, text);
        assert.equal(rejected, true); scenarios++;
      }
      assert.equal(await page.evaluate(() => __inferenceFixture.requests), 4);
      if (!native) assert.equal(await page.evaluate(() => __inferenceFixture.cancelled), 4);
      scenarios++;
      await context.close();
    }
    console.log(`SEC005 INFERENCE FLOW PASS (${scenarios} browser/native-gateway-mock scenarios)`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
