const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { deriveHazardEvidence, scoreHazardReport } = require('../static/hazard-model.js');
const resources = '../android-app/android/app/src/test/resources/';
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, resources, 'hazard-evidence-v1.json'), 'utf8'));
assert.equal(fixture.version, 1);
for (const row of fixture.cases) {
  const report = { ...fixture.defaults, ...row.report };
  const before = JSON.stringify(report);
  const result = deriveHazardEvidence(report);
  assert.deepEqual(result, {
    policy_version: 'hazard-evidence-v1', confidence: row.confidence,
    confidence_rank: { unknown: 0, single_observation: 1, independent_reobservation: 2 }[row.confidence],
    severity: row.severity, severity_rank: { unknown: 0, small: 1, medium: 2, large: 3 }[row.severity],
    independent_drive_count: row.drives, is_fixed: row.fixed,
  }, row.id);
  assert.deepEqual(deriveHazardEvidence(report), result, row.id);
  assert.equal(JSON.stringify(report), before, `${row.id}: no mutation`);
  assert.ok(Object.isFrozen(result), row.id);
}
// The new API is exactly the confidence/severity portion of the existing contract.
const previous = JSON.parse(fs.readFileSync(path.join(__dirname, resources, 'hazard-scoring-v1.json'), 'utf8'));
for (const row of previous.cases) {
  const report = { ...previous.defaults, ...row.report };
  const score = scoreHazardReport(report, previous.reference_at_s, {
    freshThroughSeconds: previous.window.fresh_through_s,
    staleAfterSeconds: previous.window.stale_after_s,
  });
  const { policy_version, ...evidence } = deriveHazardEvidence(report);
  const { freshness, freshness_rank, ...expected } = score;
  assert.deepEqual(evidence, expected, row.id);
}
assert.equal(deriveHazardEvidence(null).confidence, 'unknown');
console.log(`hazard evidence parity: ${fixture.cases.length} shared cases and ${previous.cases.length} original contract cases passed`);
