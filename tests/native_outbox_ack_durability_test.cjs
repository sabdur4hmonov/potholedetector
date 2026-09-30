// Runs the production page loop and native-report dedupe write with controlled transactions.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static/index.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'static/standalone.js'), 'utf8');
const syncStart = html.indexOf('const NATIVE_IMAGE_BATCH_SIZE = 2;');
const syncEnd = html.indexOf('function refreshNativeRepairData(', syncStart);
const importStart = script.indexOf('  async function importNativeReport(native)');
const importEnd = script.indexOf('  async function verifiedDirectEmailRoute(', importStart);
const matchStart = script.indexOf('  function addReportUnlessDuplicate(rec, dedupe)');
const matchEnd = script.indexOf('  // SEC-010: bound encoded bytes', matchStart);
assert.ok(syncStart >= 0 && syncEnd > syncStart);
assert.ok(importStart >= 0 && importEnd > importStart && matchStart >= 0 && matchEnd > matchStart);
assert.match(script.slice(importStart, importEnd), /const committed = await addReportUnlessDuplicate\(rec, !debug\)/);
assert.match(script.slice(matchStart, matchEnd), /tx\.oncomplete = \(\) => result \? resolve\(result\)/);

let active;
const context = vm.createContext({
  idb: async () => active.database,
  finiteCoord: Number.isFinite,
  DEDUPE_HISTORY_RADIUS_M: 12,
  IDBKeyRange: { bound: () => ({}) },
  storageError: (error) => error || new Error('storage failed'),
  nativeDrivePlugin: () => active.plugin,
  requireNativeDataSyncCurrent: () => {},
  refreshNativeRepairData: async () => ({ observations: 0 }),
  getNativeDriveHistory: async () => ({ drives: [] }),
});
vm.runInContext(script.slice(matchStart, matchEnd) + '\n' + html.slice(syncStart, syncEnd)
  + '\nglobalThis.persist = addReportUnlessDuplicate; globalThis.runSync = performNativeDataSync;', context);
context.api = async (route, options) => {
  assert.equal(route, '/api/native-report');
  const row = JSON.parse(options.body);
  return context.persist(row, true);
};

function scenario(count, { failAck = false } = {}) {
  const rows = Array.from({ length: count }, (_, index) => ({ id: index + 1, lat: 41.3, lng: 69.2 }));
  const remaining = new Set(rows.map((row) => row.id));
  const stored = new Map();
  const writes = [];
  const pages = [];
  const acks = [];
  const events = [];
  const database = {
    transaction(name, mode) {
      assert.equal(name, 'reports');
      assert.equal(mode, 'readwrite');
      const tx = { error: null, objectStore(storeName) {
        assert.equal(storeName, 'reports');
        return { index(indexName) {
          assert.equal(indexName, 'by_lat');
          return { openCursor() {
            const request = { result: null, error: null };
            setImmediate(() => request.onsuccess());
            return request;
          } };
        }, add(row) {
          const request = { result: row.id, error: null };
          writes.push({ tx, request, row });
          events.push(`write:${row.id}`);
          return request;
        } };
      } };
      return tx;
    },
  };
  const plugin = {
    async syncReports({ limit }) {
      assert.equal(limit, 2);
      const pending = rows.filter((row) => remaining.has(row.id));
      const page = pending.slice(0, limit);
      pages.push(page.map((row) => row.id));
      events.push(`page:${page.map((row) => row.id).join(',')}`);
      return { reports: page, remaining: pending.length };
    },
    async acknowledgeReports({ ids }) {
      acks.push([...ids]);
      events.push(`ack:${ids.join(',')}`);
      if (failAck) { failAck = false; throw new Error('native acknowledgement failed'); }
      ids.forEach((id) => remaining.delete(id));
      return { acknowledged: ids.length };
    },
  };
  return { database, plugin, stored, writes, pages, acks, events, remaining };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));
async function nextWrite(state) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (state.writes.length) return state.writes.shift();
    await tick();
  }
  throw new Error('write did not start');
}
async function finishWrite(state, disposition) {
  const write = await nextWrite(state);
  const priorAckCount = state.acks.length;
  write.request.onsuccess();
  await tick();
  assert.equal(state.acks.length, priorAckCount, 'request success must not acknowledge before transaction end');
  if (disposition === 'commit') {
    state.stored.set(write.row.id, write.row);
    state.events.push(`commit:${write.row.id}`);
    write.tx.oncomplete();
  } else {
    write.tx.error = new Error('transaction aborted');
    state.events.push(`abort:${write.row.id}`);
    write.tx.onabort();
  }
  await tick();
}

async function test(name, run) {
  await run();
  console.log(`PASS ${name}`);
}

(async () => {
  await test('three pages acknowledge only after each committed page', async () => {
    active = scenario(5);
    const run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    for (const id of [1, 2, 3, 4, 5]) {
      await finishWrite(active, 'commit');
      assert.ok(active.stored.has(id));
      if (id === 2) assert.deepEqual(active.acks, [[1, 2]]);
      if (id === 4) assert.deepEqual(active.acks, [[1, 2], [3, 4]]);
    }
    assert.equal((await run).reports, 5);
    assert.deepEqual(active.pages, [[1, 2], [3, 4], [5]]);
    assert.deepEqual(active.acks, [[1, 2], [3, 4], [5]]);
    assert.equal(active.remaining.size, 0);
    for (const [first, last] of [['commit:2', 'ack:1,2'], ['commit:4', 'ack:3,4'], ['commit:5', 'ack:5']]) {
      assert.ok(active.events.indexOf(first) < active.events.indexOf(last));
    }
  });

  await test('aborted transaction leaves native page retryable', async () => {
    active = scenario(1);
    let run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    await finishWrite(active, 'abort');
    assert.equal((await run).reports, 0);
    assert.equal(active.acks.length, 0);
    assert.equal(active.stored.size, 0);
    assert.deepEqual([...active.remaining], [1]);
    run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    await finishWrite(active, 'commit');
    assert.equal((await run).reports, 1);
    assert.deepEqual(active.acks, [[1]]);
    assert.equal(active.stored.size, 1);
  });

  await test('partial page acknowledges only committed report', async () => {
    active = scenario(2);
    const run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    await finishWrite(active, 'commit');
    await finishWrite(active, 'abort');
    assert.equal((await run).reports, 1);
    assert.deepEqual(active.acks, [[1]]);
    assert.deepEqual([...active.remaining], [2]);
  });

  await test('failed native acknowledgement keeps web commit and retries', async () => {
    active = scenario(2, { failAck: true });
    let run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    await finishWrite(active, 'commit');
    await finishWrite(active, 'commit');
    assert.equal((await run).reports, 0);
    assert.equal(active.stored.size, 2);
    assert.deepEqual([...active.remaining], [1, 2]);
    run = context.runSync({ syncEpoch: 0, repairEpoch: 0 });
    await finishWrite(active, 'commit');
    await finishWrite(active, 'commit');
    assert.equal((await run).reports, 2);
    assert.equal(active.stored.size, 2);
    assert.deepEqual(active.acks, [[1, 2], [1, 2]]);
  });
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
