// SEC-016: a URL fragment must never supply, configure or transmit a credential.
// Executes the production CredentialBroker block in node:vm; no browser or network.
// SEC016_SOURCE may point at another standalone.js copy (used for mutation probes).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const sourcePath = process.env.SEC016_SOURCE || path.join(ROOT, 'static/standalone.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const start = source.indexOf('  const CredentialBroker = (() => {');
const end = source.indexOf('  window.CredentialBroker = CredentialBroker;');
assert.ok(start > 0 && end > start, 'CredentialBroker block not found');
const block = source.slice(start, end);
let checks = 0;
const ok = (value, label) => { assert.ok(value, label); checks++; };
const eq = (got, want, label) => { assert.deepEqual(got, want, label); checks++; };

async function broker({ hash = '', native = false } = {}) {
  const calls = { replaceState: [], fetch: [], migrate: [] };
  const store = new Map();
  const nativePlugin = {
    getStatus: async () => ({ openAiConfigured: false, dashcamRtspConfigured: false }),
    migrateLegacyCredentials: async (value) => { calls.migrate.push(value); return { openAiConfigured: true }; },
    storeCredentials: async () => ({ openAiConfigured: true, dashcamRtspConfigured: false }),
  };
  const sandbox = {
    NATIVE: native,
    URLSearchParams,
    window: {},
    location: { hash, pathname: '/pothole-reporter/', search: '?lang=en' },
    history: { replaceState: (...args) => calls.replaceState.push(args) },
    localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), removeItem: (k) => store.delete(k) },
    fetch: async (url, init) => { calls.fetch.push({ url, init }); return { ok: true }; },
    Capacitor: native ? { registerPlugin: () => nativePlugin } : undefined,
    boundedAiRequest: (body) => body,
    aiUsageLimitError: () => new Error('limit'),
  };
  vm.createContext(sandbox);
  vm.runInContext(block + '\nglobalThis.__broker = CredentialBroker;', sandbox);
  const api = sandbox.__broker;
  await api.ready();
  return { api, calls, store };
}

const SECRET = 'sk-attacker-supplied-fragment-123';
(async () => {
  // 1. Credential-bearing fragment: stripped, never configured, never sent.
  let { api, calls, store } = await broker({ hash: `#key=${SECRET}` });
  eq(api.hasOpenAi(), false, 'fragment key does not configure OpenAI');
  eq(calls.replaceState, [[null, '', '/pothole-reporter/?lang=en']], 'fragment removed from the address bar');
  eq(store.size, 0, 'fragment key is not persisted');
  await api.prewarm();
  eq(calls.fetch, [], 'no authenticated request is made with a fragment key');
  await assert.rejects(api.request({ model: 'gpt-5-mini' }, false), /OpenAI API key missing/); checks++;

  // 2. Explicit Settings entry still works and is the only credential source.
  await api.storeCredentials({ openAiKey: ' typed-in-settings-123 ' });
  eq(api.hasOpenAi(), true, 'explicit Settings entry still configures the browser credential');
  await api.prewarm();
  eq(calls.fetch.length, 1, 'explicit credential prewarm still runs');
  const auth = calls.fetch[0].init.headers.Authorization;
  ok(auth === 'Bearer typed-in-settings-123' && !auth.includes(SECRET), 'only the typed credential is used');

  // 3. Fragment variants.
  ({ api, calls } = await broker({ hash: `#lang=en&key=${SECRET}` }));
  ok(!api.hasOpenAi() && calls.replaceState.length === 1, 'key parameter mixed with others is stripped, not imported');
  ({ api, calls } = await broker({ hash: '#key=' }));
  ok(!api.hasOpenAi() && calls.replaceState.length === 1, 'empty key parameter is stripped');
  ({ api, calls } = await broker({ hash: '#report-12' }));
  ok(!api.hasOpenAi() && calls.replaceState.length === 0, 'non-credential report deep link is left intact');
  ({ api, calls } = await broker({ hash: '' }));
  ok(!api.hasOpenAi() && calls.replaceState.length === 0, 'plain load does not touch history');

  // 4. Native mode never reads the fragment and never migrates it into secure storage.
  ({ api, calls } = await broker({ hash: `#key=${SECRET}`, native: true }));
  ok(!api.hasOpenAi() && calls.replaceState.length === 0 && calls.migrate.length === 0,
    'native mode ignores the fragment entirely');

  // 5. Static contract across every shipped copy.
  if (!process.env.SEC016_SOURCE) {
    const copies = ['static', 'docs', 'android-app/www', 'android-app/android/app/src/main/assets/public']
      .map((dir) => path.join(ROOT, dir, 'standalone.js'));
    const bytes = copies.map((file) => fs.readFileSync(file));
    ok(bytes.every((b) => b.equals(bytes[0])), 'all four shipped standalone.js copies are identical');
    const text = bytes[0].toString('utf8');
    ok(!/fragmentKey|location\.hash[^\n]*\.get\(\s*["']key["']\s*\)/.test(text), 'no fragment credential reader remains');
    ok(!/legacyOpenAiKey\s*=\s*[^"'\n]*hash/.test(text), 'no hash-derived value reaches the credential state');
    for (const html of ['static/index.html', 'docs/index.html']) {
      ok(!/location\.hash[^\n]*key/i.test(fs.readFileSync(path.join(ROOT, html), 'utf8')), `${html} has no fragment credential path`);
    }
  }
  console.log(`SEC-016 FRAGMENT CREDENTIAL TEST PASS (${checks} checks)`);
})().catch((error) => {
  console.error(error && error.stack || error);
  process.exit(1);
});
