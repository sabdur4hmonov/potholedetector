// Executes the production JS matcher against the same fixture as NativeRoadEventMatcherParityTest.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static/standalone.js'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(root,
  'android-app/android/app/src/test/resources/road-event-match-v1.json'), 'utf8'));
const nativeEngine = fs.readFileSync(path.join(root,
  'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive/NativeDeduplicationEngine.kt'), 'utf8');
assert.match(nativeEngine, /NativeRoadEventMatcher\.match\(/);
assert.equal(fixture.version, 1);
assert.equal(fixture.cases.length, 20);

const constants = source.slice(source.indexOf('  const DEDUPE_ADJACENT_RADIUS_M ='),
  source.indexOf('  const REPAIR_MAX_ACCURACY_M ='));
const manual = source.slice(source.indexOf('  const isManualCaptureSource ='),
  source.indexOf('\n  function normaliseModel(', source.indexOf('  const isManualCaptureSource =')));
const matcher = source.slice(source.indexOf('  function distMeters('),
  source.indexOf('  const sameRoadEvent =', source.indexOf('  function distMeters(')));
assert.ok(constants.includes('DEDUPE_HISTORY_RADIUS_M'));
assert.ok(matcher.includes('function roadEventMatch(candidate, prior)'));
const context = vm.createContext({});
vm.runInContext(constants + manual + matcher + '\nglobalThis.match = roadEventMatch;', context);

const base = {
  created_at: 1800000000, lat: 0, lng: 0, status: 'draft', decision: 'accept',
  capture_source: 'drive_live', captured_at: 1800000000, source_offset_s: 100,
  gps_accuracy: 5, speed_mps: 8, heading: 90, damage_type: 'pothole_cavity',
  size: 'medium', dedupe_eligible: true,
};
for (const row of fixture.cases) {
  const candidate = { ...base, drive_id: 'drive-b', ...row.candidate };
  const prior = { ...base, drive_id: 'drive-a', ...row.prior,
    source_event_keys: row.prior_keys || [], event_sightings: row.sightings || [] };
  const actual = context.match(candidate, prior)?.kind || null;
  assert.equal(actual, row.expect, row.name);
}
console.log(`road event match parity: ${fixture.cases.length} shared JS cases passed`);
