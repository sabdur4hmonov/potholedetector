const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const app = process.env.POTHOLE_TEST_APP || 'http://localhost:8765/';

(async () => {
  const browser = await chromium.launch({
    ...(process.env.POTHOLE_TEST_CHROME ? { executablePath: process.env.POTHOLE_TEST_CHROME } : {}),
    headless: true,
    args: ['--disable-web-security'],
  });
  const logs = [];
  const newContext = async () => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await context.route('https://api.openai.com/**', (route) => route.fulfill({
      status: 200, contentType: 'application/json', body: '{"data":[],"output":[]}',
    }));
    context.on('page', (page) => page.on('console', (entry) => logs.push(entry.text())));
    return context;
  };
  try {
    let context = await newContext();
    let page = await context.newPage();
    await page.goto(app);
    await page.waitForFunction(() => window.CredentialBroker && typeof initialSettingsRequired === 'boolean');
    await page.locator('#settings').waitFor({ state: 'visible' });
    await page.locator('#setKey').fill('unit-browser-credential-123');
    await page.locator('#setSave').click();
    await page.locator('#home').waitFor({ state: 'visible' });
    let state = await page.evaluate(() => ({
      local: localStorage.getItem('openai_key'),
      session: sessionStorage.getItem('openai_key'),
      configured: CredentialBroker.hasOpenAi(),
    }));
    assert.deepEqual(state, { local: null, session: null, configured: true });
    assert.equal(await page.locator('#setKey').inputValue(), '');
    await page.reload();
    await page.waitForFunction(() => window.CredentialBroker);
    state = await page.evaluate(() => ({
      local: localStorage.getItem('openai_key'),
      configured: CredentialBroker.hasOpenAi(),
    }));
    assert.deepEqual(state, { local: null, configured: false });
    state = await page.evaluate(async () => {
      await CredentialBroker.storeCredentials({ openAiKey: 'unit-delete-credential-123' });
      const result = await deleteAllAppData();
      return { cleared: result.cleared, configured: CredentialBroker.hasOpenAi(),
        localCount: localStorage.length, sessionCount: sessionStorage.length };
    });
    assert.deepEqual(state, { cleared: true, configured: false, localCount: 0, sessionCount: 0 });
    await context.close();

    context = await newContext();
    await context.addInitScript(() => {
      localStorage.setItem('openai_key', 'unit-legacy-credential-123');
      localStorage.setItem('dashcam_rtsp_url', 'rtsp://legacy:credential@192.0.2.4/live');
    });
    page = await context.newPage();
    await page.goto(app);
    await page.waitForFunction(() => window.CredentialBroker && CredentialBroker.hasOpenAi());
    state = await page.evaluate(() => ({
      openAi: localStorage.getItem('openai_key'),
      rtsp: localStorage.getItem('dashcam_rtsp_url'),
      configured: CredentialBroker.hasOpenAi(),
      dashcam: CredentialBroker.hasDashcamRtsp(),
    }));
    assert.deepEqual(state, { openAi: null, rtsp: null, configured: true, dashcam: false });
    await context.close();

    context = await newContext();
    page = await context.newPage();
    // SEC-016: a credential-bearing link is stripped but never imported.
    await page.goto(app + '#key=unit-fragment-credential-123');
    await page.waitForFunction(() => window.CredentialBroker);
    state = await page.evaluate(async () => {
      await CredentialBroker.ready();
      return { local: localStorage.getItem('openai_key'), configured: CredentialBroker.hasOpenAi(), hash: location.hash };
    });
    assert.deepEqual(state, { local: null, configured: false, hash: '' });
    await context.close();

    context = await newContext();
    await context.addInitScript(() => {
      localStorage.setItem('openai_key', 'unit-native-legacy-credential-123');
      localStorage.setItem('dashcam_rtsp_url', 'rtsp://native:credential@192.0.2.5/live');
      const secure = window.__secureProbe = { openAi: '', rtsp: '', request: null };
      const status = () => ({ openAiConfigured: !!secure.openAi, dashcamRtspConfigured: !!secure.rtsp });
      const SecureCredentials = {
        migrateLegacyCredentials: async (value) => {
          secure.openAi ||= value.openAiKey || '';
          secure.rtsp ||= value.dashcamRtspUrl || '';
          return status();
        },
        getStatus: async () => status(),
        storeCredentials: async (value) => {
          if (value.openAiKey) secure.openAi = value.openAiKey;
          if (value.dashcamRtspUrl) secure.rtsp = value.dashcamRtspUrl;
          return status();
        },
        clearCredentials: async () => {
          secure.openAi = ''; secure.rtsp = ''; return status();
        },
        openAiRequest: async (value) => {
          secure.request = value;
          return { status: 200, ok: true, body: '{"output":[]}' };
        },
      };
      const DriveMode = {
        getStatus: async () => ({ isRunning: false, isStarting: false, isStopping: false }),
        getDriveEndSummary: async () => ({ available: false }),
        syncReports: async () => ({ reports: [], count: 0 }),
        syncRepairObservations: async () => ({ observations: [], count: 0 }),
        getDrives: async () => ({ drives: [] }),
        addListener: async () => {},
      };
      Object.defineProperty(window, 'Capacitor', { configurable: true, value: {
        isNativePlatform: () => true,
        registerPlugin: (name) => name === 'SecureCredentials' ? SecureCredentials : DriveMode,
        Plugins: { SecureCredentials, DriveMode, App: { addListener: async () => {} } },
      }});
    });
    page = await context.newPage();
    await page.goto(app);
    await page.waitForFunction(() => window.CredentialBroker && CredentialBroker.hasOpenAi() && CredentialBroker.hasDashcamRtsp());
    state = await page.evaluate(() => ({
      openAiLocal: localStorage.getItem('openai_key'),
      rtspLocal: localStorage.getItem('dashcam_rtsp_url'),
      openAiInput: document.querySelector('#setKey').value,
      rtspInput: document.querySelector('#setDashcamRtspUrl').value,
      migratedOpenAi: __secureProbe.openAi === 'unit-native-legacy-credential-123',
      migratedRtsp: __secureProbe.rtsp === 'rtsp://native:credential@192.0.2.5/live',
    }));
    assert.deepEqual(state, {
      openAiLocal: null, rtspLocal: null, openAiInput: '', rtspInput: '',
      migratedOpenAi: true, migratedRtsp: true,
    });
    await page.evaluate(async () => {
      await CredentialBroker.request({ model: 'gpt-5-mini', input: 'unit', store: false }, false);
    });
    state = await page.evaluate(() => ({
      requestHasCredential: /credential-123|rtsp:\/\//.test(JSON.stringify(__secureProbe.request)),
      stream: __secureProbe.request.stream,
    }));
    assert.deepEqual(state, { requestHasCredential: false, stream: false });
    state = await page.evaluate(async () => {
      await CredentialBroker.clear();
      return { openAi: CredentialBroker.hasOpenAi(), rtsp: CredentialBroker.hasDashcamRtsp(),
        nativeCleared: !__secureProbe.openAi && !__secureProbe.rtsp };
    });
    assert.deepEqual(state, { openAi: false, rtsp: false, nativeCleared: true });
    await context.close();

    context = await newContext();
    await context.addInitScript(() => {
      localStorage.setItem('openai_key', 'invalid');
      let configured = false;
      const plugin = {
        migrateLegacyCredentials: async () => { throw new Error('Invalid legacy credential'); },
        getStatus: async () => ({ openAiConfigured: configured, dashcamRtspConfigured: false }),
        storeCredentials: async () => {
          configured = true;
          return { openAiConfigured: true, dashcamRtspConfigured: false };
        },
      };
      window.Capacitor = { isNativePlatform: () => true, Plugins: { SecureCredentials: plugin } };
    });
    page = await context.newPage();
    await page.goto(app);
    await page.waitForFunction(() => window.CredentialBroker);
    state = await page.evaluate(async () => {
      await CredentialBroker.ready();
      await CredentialBroker.storeCredentials({ openAiKey: 'unit-recovery-credential-123' });
      return { local: localStorage.getItem('openai_key'), configured: CredentialBroker.hasOpenAi() };
    });
    assert.deepEqual(state, { local: null, configured: true });
    await context.close();
    assert.equal(logs.some((entry) => /unit-.*credential|rtsp:\/\/[^\s]*@/.test(entry)), false);
    console.log('SEC-001 CREDENTIAL FLOW TEST PASS');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error && error.stack || error);
  process.exit(1);
});
