const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const source = fs.readFileSync(path.join(__dirname, '../static/standalone.js'), 'utf8');
const helpers = source.slice(source.indexOf('  // SEC-005:'), source.indexOf('  // Reconstructed from the closed fields'));
const start = source.indexOf('  async function oai(body)');
const jsonPath = source.slice(start, source.indexOf('\n  }', start) + 4);
const encode = value => new TextEncoder().encode(value);
const event = value => `data: ${JSON.stringify(value)}\n\n`;
const delta = value => event({ type: 'response.output_text.delta', delta: value });
let response, requests = 0, headerDelay = 0;
const allocations = [];
function BudgetArray(value) {
  if (typeof value === 'number') { allocations.push(value); assert.ok(value <= 65536); }
  return new Uint8Array(value);
}
BudgetArray.prototype = Uint8Array.prototype;
const sandbox = { AbortController, Uint8Array: BudgetArray, TextEncoder, TextDecoder, performance,
  setTimeout, clearTimeout, console, NATIVE: false,
  withSpeedDefaults: body => body, peekVerdict: () => null, peekReject: text => text.includes('"reject":true'),
  rejectedVerdict: () => ({ rejected: true }), statusError: async () => new Error('HTTP failure'),
  CredentialBroker: { request: async () => {
    requests++; const current = response;
    if (headerDelay) await new Promise(resolve => setTimeout(resolve, headerDelay));
    return current;
  } },
};
vm.createContext(sandbox);
vm.runInContext(helpers + '\n' + jsonPath, sandbox);
function mock(chunks, { stall = false, interrupt = false, length = null, encoding = null, noStream = false, ok = true } = {}) {
  const probe = { reads: 0, cancelled: 0, released: 0, httpCancelled: 0, disarmed: 0, textReads: 0 };
  let index = 0;
  const reader = { read: async () => {
    probe.reads++;
    if (index < chunks.length) return { value: typeof chunks[index] === 'string' ? encode(chunks[index++]) : chunks[index++], done: false };
    if (interrupt) throw new Error('Synthetic interruption');
    if (stall) return new Promise(() => {});
    return { done: true };
  }, cancel: () => { probe.cancelled++; return Promise.resolve(); }, releaseLock: () => { probe.released++; } };
  return { ok, status: ok ? 200 : 500, probe,
    body: noStream ? null : { getReader: () => reader, cancel: reader.cancel },
    headers: { get: name => name === 'content-length' ? length : name === 'content-encoding' ? encoding : 'text/event-stream' },
    __cancel: () => { probe.httpCancelled++; }, __disarm: () => { probe.disarmed++; },
    __rearm: () => { throw new Error('Absolute deadline must not rearm'); },
    text: async () => { probe.textReads++; return chunks.join(''); },
    json: () => { throw new Error('Unbounded .json() helper must not run'); },
  };
}
const limits = { responseBytes: 65536, lineBytes: 32768, eventBytes: 49152, events: 512, deadlineMs: 35000 };
async function stream(options = {}) {
  return sandbox.oaiStream({}, null, false, options.signal || null, { ...limits, ...options.limits });
}
async function rejected(chunks, options = {}, overrides = {}) {
  response = mock(chunks, options);
  await assert.rejects(stream(overrides));
  assert.ok(response.probe.httpCancelled); assert.ok(response.probe.disarmed);
  if (response.body) { assert.ok(response.probe.cancelled); if (response.probe.reads) assert.equal(response.probe.released, 1); }
}
let tests = 0;
async function test(name, run) { await run(); tests++; console.log('PASS ' + name); }
(async () => {
  await test('normal multiple deltas and done succeeds then closes reader', async () => {
    response = mock([delta('{"ok":'), delta('true}'), 'data: [DONE]\n\n'], { stall: true });
    assert.equal((await stream()).ok, true);
    assert.equal(response.probe.reads, 3); assert.equal(response.probe.released, 1);
    assert.ok(response.probe.cancelled); assert.ok(response.probe.httpCancelled);
  });
  await test('terminal completed event stops before hostile trailing chunks', async () => {
    response = mock([delta('{"ok":true}'), event({ type: 'response.completed' }), 'x'.repeat(100000)]);
    assert.equal((await stream()).ok, true); assert.equal(response.probe.reads, 2);
  });
  await test('one oversized line rejected while fixed destination arrays remain bounded', async () => {
    const before = allocations.length;
    await rejected(['data: ' + 'x'.repeat(32768)]);
    assert.ok(allocations.slice(before).every(n => n <= 49152));
  });
  await test('cumulative byte cap includes comments without Content-Length', async () => {
    await rejected(Array(18).fill(':' + 'a'.repeat(4093) + '\n'));
    assert.equal(response.probe.reads, 17);
  });
  await test('UTF-8 bytes not characters control cumulative budget', async () => {
    await rejected([': ' + '界'.repeat(20) + '\n'], {}, { limits: { responseBytes: 32 } });
  });
  await test('many tiny valid events hit count while under byte cap', async () => {
    await rejected([event({ type: 'response.created' }).repeat(513)]);
  });
  await test('multiline event cannot evade its aggregate limit', async () => {
    await rejected(['data: 12345\ndata: 67890\n\n'], {}, { limits: { eventBytes: 10 } });
  });
  await test('invalid UTF-8 rejected before JSON dispatch', async () => {
    await rejected([new Uint8Array([100, 97, 116, 97, 58, 32, 195, 40, 10, 10])]);
  });
  await test('malformed framing JSON and required fields rejected safely', async () => {
    for (const value of ['garbage\n', 'unknown: x\n', 'data: {bad}\n\n', 'data: []\n\n',
      'data: {}\n\n', event({ type: 1 }), event({ type: 'response.output_text.delta' }),
      event({ type: 'response.output_text.delta', delta: 1 }), 'retry: -1\n']) await rejected([value]);
  });
  await test('unterminated event and missing terminal never become a verdict', async () => {
    await rejected([delta('{"ok":true}')]); await rejected(['data: {}']);
  });
  await test('deadline cancels stalled stream and releases resources', async () => {
    response = mock([], { stall: true });
    await assert.rejects(stream({ limits: { deadlineMs: 10 } }), error => error.timeout === true);
    assert.equal(response.probe.released, 1); assert.ok(response.probe.httpCancelled);
  });
  await test('active tiny chunks cannot rearm overall deadline', async () => {
    response = mock([], { stall: true });
    response.body.getReader = () => ({ read: async () => {
      await new Promise(resolve => setTimeout(resolve, 2)); return { value: encode(': a\n'), done: false };
    }, cancel: () => { response.probe.cancelled++; }, releaseLock: () => { response.probe.released++; } });
    await assert.rejects(stream({ limits: { deadlineMs: 10 } }), error => error.timeout === true);
    assert.equal(response.probe.released, 1);
  });
  await test('explicit cancellation stops parsing and closes body', async () => {
    const ctl = new AbortController(); response = mock([], { stall: true });
    const task = stream({ signal: ctl.signal }); setTimeout(() => ctl.abort(), 5);
    await assert.rejects(task, error => error.name === 'AbortError');
    assert.equal(response.probe.released, 1); assert.ok(response.probe.cancelled);
  });
  await test('pre-cancellation sends no request', async () => {
    const before = requests; const ctl = new AbortController(); ctl.abort();
    await assert.rejects(stream({ signal: ctl.signal })); assert.equal(requests, before);
  });
  await test('cancelled pending headers never admit a late body reader', async () => {
    response = mock([delta('{"ok":true}')]); headerDelay = 15;
    const ctl = new AbortController(); const task = stream({ signal: ctl.signal }); ctl.abort();
    await assert.rejects(task); await new Promise(resolve => setTimeout(resolve, 20)); headerDelay = 0;
    assert.equal(response.probe.reads, 0); assert.ok(response.probe.cancelled); assert.ok(response.probe.httpCancelled);
  });
  await test('early-negative path closes immediately without terminal or EOF', async () => {
    response = mock([delta('{"reject":true}')], { stall: true });
    assert.equal((await sandbox.oaiStream({}, null, true)).rejected, true);
    assert.equal(response.probe.reads, 1); assert.ok(response.probe.cancelled);
  });
  await test('transport interruption always cleans up', async () => {
    await rejected([delta('{"ok":true}')], { interrupt: true });
  });
  await test('declared oversized malformed negative and early EOF fail closed', async () => {
    for (const length of ['65537', '-1', '1.5', '1, 1', '9007199254740993']) {
      await rejected([], { length }); assert.equal(response.probe.reads, 0);
    }
    await rejected([delta('{"ok":true}')], { length: '1000' });
  });
  await test('non-success response never reads error body', async () => {
    await rejected(['x'.repeat(100000)], { ok: false }); assert.equal(response.probe.reads, 0);
  });
  await test('browser missing-stream response cannot trigger unbounded text fallback', async () => {
    await rejected(['x'.repeat(100000)], { noStream: true }); assert.equal(response.probe.textReads, 0);
  });
  await test('native prebounded envelope uses equivalent cap and rejects replacement UTF-8', async () => {
    sandbox.NATIVE = true;
    response = mock([delta('{"ok":true}') + 'data: [DONE]\n\n'], { noStream: true });
    assert.equal((await stream()).ok, true);
    await rejected(['x'.repeat(65537)], { noStream: true });
    await rejected([delta('{"bad":"\ufffd"}') + 'data: [DONE]\n\n'], { noStream: true });
    sandbox.NATIVE = false;
  });
  await test('nonstream inference JSON also uses streaming byte and UTF-8 limits', async () => {
    const body = JSON.stringify({ output: [{ type: 'message', content: [{ type: 'output_text', text: '{"ok":true}' }] }] });
    response = mock([body]); assert.equal((await sandbox.oai({})).ok, true);
    response = mock(['x'.repeat(65537)]); await assert.rejects(sandbox.oai({}));
    assert.equal(response.probe.released, 1);
  });
  await test('limit arithmetic rejects overflow relaxation and unpaired surrogate', async () => {
    for (const key of Object.keys(limits)) {
      await assert.rejects(stream({ limits: { [key]: Number.MAX_SAFE_INTEGER } }));
    }
    assert.throws(() => sandbox.inferenceUtf8Size('\ud800', 65536));
    assert.equal(sandbox.inferenceUtf8Size('界😀', 7), 7);
    assert.throws(() => sandbox.inferenceUtf8Size('界😀', 6));
  });
  await test('hostile JSON nesting is rejected before materializing an object tree', async () => {
    const nested = '{"type":"response.created","extra":' + '['.repeat(40) + '0' + ']'.repeat(40) + '}';
    await rejected([`data: ${nested}\n\n`]);
    response = mock([JSON.stringify({ output: [{ type: 'message', content: [{ type: 'output_text',
      text: '['.repeat(40) + '0' + ']'.repeat(40) }] }] })]);
    await assert.rejects(sandbox.oai({}));
    assert.ok(response.probe.cancelled); assert.equal(response.probe.released, 1);
  });
  console.log(`SEC005 INFERENCE STREAM PASS (${tests} deterministic JS tests)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
