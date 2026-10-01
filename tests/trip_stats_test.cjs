const assert = require('node:assert/strict');
const { POLICY, deriveTripStats, summarizeDrives } = require('../static/trip-stats.js');
const point = (t, lng, accuracy = 0) => [t, 0, lng, accuracy, null, null];
const close = (a, b) => assert.ok(Math.abs(a - b) < 0.001, `${a} != ${b}`);
const run = (name, fn) => { fn(); console.log(`PASS ${name}`); };
run('known straight sampled path and repeated evaluation', () => {
  const track = [point(0, 0), point(10, 0.001), point(20, 0.002)];
  const before = JSON.stringify(track), stats = deriveTripStats(track);
  close(stats.distance_m, 222.389853);
  close(stats.avg_moving_speed_mps, 11.119493);
  close(stats.max_interval_speed_mps, 11.119493);
  assert.equal(stats.moving_time_s, 20);
  assert.equal(stats.coverage, 'sampled');
  assert.deepEqual(deriveTripStats(track), stats);
  assert.equal(JSON.stringify(track), before);
  assert.ok(Object.isFrozen(stats));
});
run('accuracy discount suppresses parked jitter and ignores reported speed', () => {
  const stats = deriveTripStats([[0, 0, 0, 15, 100, 0], [10, 0, 0.00001, 15, 100, 0]]);
  assert.equal(stats.distance_m, 0); assert.equal(stats.moving_time_s, 0);
  assert.equal(stats.avg_moving_speed_mps, null); assert.equal(stats.max_interval_speed_mps, null);
});
run('missing poor and invalid coordinates break continuity', () => {
  for (const bad of [point(5, 0.0005, null), point(5, 0.0005, 15.01), point(5, 0.0005, -1),
    point(5, NaN), [5, 91, 0, 0], [5, 0, 181, 0], null]) {
    assert.equal(deriveTripStats([point(0, 0), bad, point(10, 0.001)]).distance_m, null);
  }
  for (const track of [null, [], [point(0, 0)]]) assert.equal(deriveTripStats(track).coverage, 'unavailable');
});
run('timestamps duplicates disorder gaps and teleports do not bridge', () => {
  for (const middle of [point(0, 0.001), point(-1, 0.001), point(31, 0.001), point(1, 1)]) {
    const stats = deriveTripStats([point(0, 0), middle, point(40, 0.002)]);
    assert.equal(stats.distance_m, null);
  }
  assert.equal(deriveTripStats([point(0, 0), point(30, 0.001, 15)]).accepted_intervals, 1);
});
run('partial tracks expose omitted intervals', () => {
  const stats = deriveTripStats([point(0, 0), point(10, 0.001), null, point(20, 0.002)]);
  assert.equal(stats.coverage, 'partial'); assert.equal(stats.accepted_intervals, 1);
});
run('speed admission, antimeridian and weighted moving averages', () => {
  assert.equal(deriveTripStats([point(0, 0), point(1, 0.0008)]).accepted_intervals, 1);
  assert.equal(deriveTripStats([point(0, 0), point(1, 0.001)]).accepted_intervals, 0);
  close(deriveTripStats([point(0, 179.999), point(10, -179.999)]).distance_m, 222.389853);
  const summary = summarizeDrives([
    { gps_track: [point(0, 0), point(10, 0.001)] },
    { gps_track: [point(0, 0), point(20, 0.001)] },
  ]);
  close(summary.avg_moving_speed_mps, 222.389853 / 30);
  close(summary.max_interval_speed_mps, 11.119493);
});
run('bounded tracks and drive summaries retain no route', () => {
  const track = Array.from({ length: POLICY.maxPoints + 1 }, (_, i) => point(i, 0));
  assert.equal(deriveTripStats(track).truncated, true);
  const drive = { gps_track: [point(0, 0), point(10, 0.001)] };
  const stats = summarizeDrives([drive, { gps_track: [] }, drive]);
  assert.equal(stats.coverage, 'partial'); close(stats.distance_m, 222.389853);
  assert.equal(stats.moving_time_s, 20); close(stats.avg_moving_speed_mps, 11.119493);
  assert.equal(Object.hasOwn(stats, 'gps_track'), false);
  assert.equal(summarizeDrives(Array(POLICY.maxDrives + 1).fill(drive)).coverage, 'partial');
  assert.equal(summarizeDrives([]).distance_m, null);
});
