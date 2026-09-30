const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { scoreHazardReport } = require('../static/hazard-model.js');

const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,
  '../android-app/android/app/src/test/resources/hazard-scoring-v1.json'), 'utf8'));
assert.equal(fixture.version, 1);
for (const row of fixture.cases) {
  const report = { ...fixture.defaults, ...row.report };
  const window = {
    freshThroughSeconds: fixture.window.fresh_through_s,
    staleAfterSeconds: fixture.window.stale_after_s,
  };
  const first = scoreHazardReport(report, fixture.reference_at_s, window);
  const second = scoreHazardReport(report, fixture.reference_at_s, window);
  assert.deepEqual(first, row.expect, row.id);
  assert.deepEqual(second, first, `${row.id}: repeated execution`);
  assert.ok(Object.isFrozen(first), `${row.id}: immutable result`);
  assert.ok(first.confidence_rank >= 0 && first.confidence_rank <= 2, row.id);
  assert.ok(first.freshness_rank >= 0 && first.freshness_rank <= 2, row.id);
  assert.ok(first.severity_rank >= 0 && first.severity_rank <= 3, row.id);
}
assert.throws(() => scoreHazardReport(fixture.defaults, fixture.reference_at_s,
  { freshThroughSeconds: 10, staleAfterSeconds: 10 }), RangeError);
console.log(`hazard scoring parity: ${fixture.cases.length} shared JS cases passed`);
