const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const source = fs.readFileSync(path.join(__dirname, '../static/standalone.js'), 'utf8');
function productionFunction(name) {
  const start = source.search(new RegExp(`  (?:async )?function ${name}\\(`));
  assert.ok(start >= 0, `Missing production function ${name}`);
  return source.slice(start, source.indexOf('\n  }', start) + 4);
}
const helper = source.slice(source.indexOf('  // SEC-004:'), source.indexOf('  const STATE_PACK_MAX_BYTES'));
let allocations = [], response, fetches = 0, validations = 0;
function BudgetArray(value) {
  if (typeof value === 'number') { allocations.push(value); assert.ok(value <= 16 * 1024 * 1024); }
  return new Uint8Array(value);
}
BudgetArray.prototype = Uint8Array.prototype;
const sandbox = { AbortController, Uint8Array: BudgetArray, ArrayBuffer, TextDecoder, URL, crypto: webcrypto,
  setTimeout, clearTimeout, Promise, Blob, console, NATIVE: false,
  window: { crypto: webcrypto, TextDecoder }, location: { href: 'https://localhost/', origin: 'https://localhost' },
  fetch: async () => { fetches++; return response; },
  resolvePackUrl: r => r.url,
  STATE_PACK_MAX_BYTES: 16 * 1024 * 1024, CONTRACT_PACK_MAX_BYTES: 8 * 1024 * 1024,
  ROAD_NOTICE_PACK_MAX_BYTES: 8 * 1024 * 1024, ROAD_AGREEMENT_PACK_MAX_BYTES: 8 * 1024 * 1024,
  HIGHWAY_TILE_MAX_BYTES: 8 * 1024 * 1024, STATE_PACK_FETCH_TIMEOUT_MS: 30000,
  OPTIONAL_CATALOG_TIMEOUT_MS: 1500, HIGHWAY_FETCH_TIMEOUT_MS: 30000,
  validateHighwayContractPack: (_r, pack) => { validations++; return pack; },
};
vm.createContext(sandbox);
vm.runInContext(helper + '\n' + ['sha256Bytes', 'validateDecodedContractPack', 'fetchContractPack',
  'loadHighwayContractPack', 'fetchOptionalCatalogManifest'].map(productionFunction).join('\n'), sandbox);
function mock({ length = null, chunks = [], ok = true, encoding = null, interrupt = false, stall = false } = {}) {
  const probe = { reads: 0, acquired: 0, cancelled: 0, released: 0, headerReads: 0 };
  let index = 0;
  const reader = {
    read: async () => {
      probe.reads++;
      if (stall) return new Promise(() => {});
      if (interrupt && index === chunks.length) throw new Error('Synthetic interruption');
      return index < chunks.length ? { value: new Uint8Array(chunks[index++]), done: false } : { done: true };
    },
    cancel: () => { probe.cancelled++; return Promise.resolve(); },
    releaseLock: () => { probe.released++; },
  };
  return { ok, probe, headers: { get: name => {
    probe.headerReads++;
    return name === 'content-length' ? length : name === 'content-encoding' ? encoding : 'application/json';
  } }, body: { getReader: () => { probe.acquired++; return reader; }, cancel: reader.cancel },
  arrayBuffer: () => { throw new Error('Unbounded body helper invoked'); },
  text: () => { throw new Error('Unbounded text helper invoked'); } };
}
async function download(options = {}) {
  return sandbox.downloadPackResource('https://example.invalid/pack', { maxBytes: 4, timeoutMs: 1000,
    validate: bytes => ({ length: bytes.byteLength }), ...options });
}
let tests = 0;
async function test(name, fn) { await fn(); tests++; console.log('PASS ' + name); }

(async () => {
  await test('declared length below maximum accepted', async () => {
    response = mock({ length: '3', chunks: [[1], [2, 3]] });
    assert.equal((await download()).bytes.byteLength, 3);
    assert.equal(response.probe.released, 1);
  });
  await test('exact inclusive maximum accepted only after EOF', async () => {
    response = mock({ length: '4', chunks: [[1, 2], [3, 4]] });
    assert.equal((await download()).bytes.byteLength, 4);
    assert.equal(response.probe.reads, 3);
  });
  await test('oversized declared body cancelled without reader or buffer allocation', async () => {
    response = mock({ length: '5', chunks: [[1, 2, 3, 4, 5]] });
    const before = allocations.length;
    assert.equal(await download(), null);
    assert.equal(response.probe.acquired, 0); assert.equal(allocations.length, before);
    assert.equal(response.probe.cancelled, 1);
  });
  await test('missing length under maximum accepted', async () => {
    response = mock({ chunks: [[1], [2]] }); assert.equal((await download()).bytes.byteLength, 2);
  });
  await test('missing length excess rejected before copying excess chunk', async () => {
    response = mock({ chunks: [[1, 2, 3, 4], [5], [6]] });
    assert.equal(await download(), null); assert.equal(response.probe.reads, 2);
    assert.ok(response.probe.cancelled); assert.equal(response.probe.released, 1);
  });
  await test('smaller declaration with larger streamed body rejected', async () => {
    response = mock({ length: '2', chunks: [[1, 2], [3], [4]] });
    assert.equal(await download(), null); assert.equal(response.probe.reads, 2);
  });
  await test('malformed negative signed duplicate and unsafe lengths fail before reading', async () => {
    for (const length of ['', '-1', '-0', '+2', '2.0', 'NaN', '2, 2', ' 2 ', '2e0', '9007199254740993']) {
      response = mock({ length }); assert.equal(await download(), null); assert.equal(response.probe.reads, 0);
    }
  });
  await test('bad status rejected before inspecting headers', async () => {
    response = mock({ ok: false }); assert.equal(await download(), null);
    assert.equal(response.probe.headerReads, 0);
  });
  await test('early EOF and interruption leave no accepted bytes', async () => {
    for (const interrupt of [false, true]) {
      response = mock({ length: '4', chunks: [[1, 2]], interrupt });
      assert.equal(await download(), null); assert.ok(response.probe.cancelled);
    }
  });
  await test('missing stream fails closed without arrayBuffer fallback', async () => {
    response = mock(); response.body = null; assert.equal(await download(), null);
  });
  await test('stalled body timeout cancels and releases reader', async () => {
    response = mock({ stall: true }); assert.equal(await download({ timeoutMs: 10 }), null);
    assert.ok(response.probe.cancelled); assert.equal(response.probe.released, 1);
  });
  await test('explicit cancellation during read cancels and releases', async () => {
    const ctl = new AbortController(); response = mock({ stall: true });
    const task = download({ signal: ctl.signal }); setTimeout(() => ctl.abort(), 5);
    assert.equal(await task, null); assert.ok(response.probe.cancelled); assert.equal(response.probe.released, 1);
  });
  await test('pre-cancellation performs no request', async () => {
    const ctl = new AbortController(); ctl.abort(); const before = fetches;
    assert.equal(await download({ signal: ctl.signal }), null); assert.equal(fetches, before);
  });
  await test('decoded compression expansion and excessive encoded declaration rejected', async () => {
    response = mock({ length: '2', encoding: 'gzip', chunks: [[1, 2, 3, 4], [5]] });
    assert.equal(await download(), null);
    response = mock({ length: '5', encoding: 'gzip', chunks: [[1]] });
    assert.equal(await download(), null); assert.equal(response.probe.acquired, 0);
  });
  await test('valid decoded compressed body accepts differing wire length', async () => {
    response = mock({ length: '2', encoding: 'br', chunks: [[1, 2, 3, 4]] });
    assert.equal((await download()).bytes.byteLength, 4);
  });
  await test('unrecognized encoding rejected', async () => {
    response = mock({ encoding: 'custom' }); assert.equal(await download(), null);
  });
  await test('signed expected size checked before buffering', async () => {
    response = mock({ length: '3' });
    assert.equal(await download({ expectedBytes: 4, expectedSha256: 'a'.repeat(64) }), null);
    assert.equal(response.probe.acquired, 0);
  });
  await test('malformed hash and invalid configured limits cause no request', async () => {
    const before = fetches;
    for (const options of [{ maxBytes: Infinity }, { maxBytes: 0 }, { maxBytes: 17 * 1024 * 1024 },
      { expectedBytes: 5, expectedSha256: 'a'.repeat(64) }, { expectedBytes: 4, expectedSha256: 'bad' }]) {
      assert.equal(await download(options), null);
    }
    assert.equal(fetches, before);
  });
  const payload = Buffer.from('{"verified":true}');
  const hash = Buffer.from(await webcrypto.subtle.digest('SHA-256', payload)).toString('hex');
  const resource = { url: 'https://example.invalid/pack', bytes: payload.length, sha256: hash,
    pack_id: 'in-nh-contracts-ka', pack_version: 1, state_code: 'KA', kind: 'highway_contracts' };
  await test('actual production hash validator accepts matching bytes and rejects mismatch before schema', async () => {
    response = mock({ length: String(payload.length), chunks: [payload] });
    assert.equal((await sandbox.fetchContractPack(resource)).pack.verified, true);
    const before = validations;
    response = mock({ length: String(payload.length), chunks: [payload] });
    assert.equal(await sandbox.fetchContractPack({ ...resource, sha256: 'a'.repeat(64) }), null);
    assert.equal(validations, before);
  });
  await test('failed replacement preserves existing memory/cache and removes pending request', async () => {
    const oldPack = { safe: true }, oldEntry = { cache_key: 'old-version', pack: oldPack };
    const memory = new Map([[resource.pack_id, oldEntry]]), pending = new Map(), records = new Map([['old-version', oldPack]]);
    Object.assign(sandbox, { _contractPackMemory: memory, _contractPackPromises: pending,
      getContractPackManifest: async () => ({ resources: { [resource.pack_id]: resource } }),
      catalogResourceWithinReview: () => true, statePackCacheKey: r => r.sha256,
      getCachedStatePack: async key => records.get(key), putCachedStatePack: async () => { throw new Error('Unexpected write'); },
      deleteCachedStatePack: async () => { throw new Error('Unexpected deletion'); } });
    response = mock({ length: String(payload.length + 1) });
    assert.equal(await sandbox.loadHighwayContractPack('KA'), null);
    assert.equal(memory.get(resource.pack_id), oldEntry); assert.equal(records.get('old-version'), oldPack);
    assert.equal(pending.size, 0);
  });
  await test('temporary cache failure cannot accept an unvalidated pack', async () => {
    response = mock({ length: String(payload.length), chunks: [payload] });
    sandbox.getCachedStatePack = async () => { throw new Error('Synthetic cache failure'); };
    sandbox.putCachedStatePack = async () => { throw new Error('Synthetic storage failure'); };
    sandbox.pruneStatePacks = async () => {};
    assert.equal((await sandbox.loadHighwayContractPack('KA')).verified, true);
  });
  await test('repeated excess has fixed allocations and released readers without retry', async () => {
    const before = allocations.length, requests = fetches;
    for (let i = 0; i < 100; i++) {
      response = mock({ chunks: [[1, 2, 3, 4], [5]] }); assert.equal(await download(), null);
      assert.equal(response.probe.released, 1);
    }
    assert.equal(fetches - requests, 100); assert.equal(allocations.length - before, 100);
    assert.ok(allocations.slice(before).every(n => n === 4));
  });
  await test('native download uses streaming GET proxy and never buffered plugin/fetch path', async () => {
    sandbox.NATIVE = true;
    sandbox.Capacitor = { getServerUrl: () => 'https://localhost' };
    let endpoint, options;
    sandbox.window.CapacitorWebFetch = async (url, init) => { endpoint = new URL(url); options = init; return mock({ length: '1', chunks: [[1]] }); };
    const requests = fetches;
    assert.equal((await download()).bytes.byteLength, 1);
    assert.equal(endpoint.pathname, '/_capacitor_http_interceptor_');
    assert.equal(endpoint.searchParams.get('u'), 'https://example.invalid/pack');
    assert.equal(options.method, 'GET'); assert.equal(options.credentials, 'omit'); assert.equal(fetches, requests);
    delete sandbox.window.CapacitorWebFetch; assert.equal(await download(), null); assert.equal(fetches, requests);
  });
  console.log(`SEC004 BOUNDED DOWNLOAD PASS (${tests} deterministic tests)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
