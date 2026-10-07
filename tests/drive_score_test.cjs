'use strict';
// TRIP-003: per-trip driving analysis, safe-driving score and the privacy-trimmed share route.
const assert = require('assert');
const T = require('../static/trip-stats.js');

const LAT0 = 41.3111, LNG0 = 69.2797;
const mPerDegLng = 111320 * Math.cos(LAT0 * Math.PI / 180);

/** Builds a 1 Hz track from [seconds, speed m/s, heading deg] segments. */
function drive(segments, accuracy = 5) {
  const track = [];
  let t = 0, x = 0, y = 0;
  for (const [seconds, speed, heading] of segments) {
    for (let i = 0; i < seconds; i++) {
      const v = typeof speed === 'function' ? speed(i) : speed;
      const h = typeof heading === 'function' ? heading(i) : heading;
      track.push([t, LAT0 + y / 111320, LNG0 + x / mPerDegLng, accuracy, v, h]);
      x += v * Math.sin(h * Math.PI / 180);
      y += v * Math.cos(h * Math.PI / 180);
      t++;
    }
  }
  return track;
}

let passed = 0;
function check(name, fn) { fn(); passed++; console.log(`  ok   ${name}`); }

check('a smooth 3 km drive scores 100 and is green', () => {
  const a = T.analyseDrive(drive([[250, 12, 90]]));
  assert.ok(a.distance_m > 2900 && a.distance_m < 3100, a.distance_m);
  assert.strictEqual(a.hard_brake, 0); assert.strictEqual(a.hard_accel, 0);
  assert.strictEqual(a.sharp_turn, 0); assert.strictEqual(a.turns, 0);
  assert.strictEqual(a.score, 100); assert.strictEqual(a.grade, 'green');
});

check('hard braking is counted once per event and lowers the score', () => {
  const brake = (i) => Math.max(4, 14 - 4.5 * i); // 4.5 m/s^2 for two seconds
  const a = T.analyseDrive(drive([[100, 14, 90], [3, brake, 90], [60, 4, 90], [100, 14, 90],
    [3, brake, 90], [60, 4, 90], [100, 14, 90]]));
  assert.strictEqual(a.hard_brake, 2);
  assert.ok(a.score < 100 && a.score >= 0, a.score);
});

check('gentle braking is not an event', () => {
  const gentle = (i) => Math.max(4, 14 - 1.5 * i);
  assert.strictEqual(T.analyseDrive(drive([[100, 14, 90], [8, gentle, 90], [100, 4, 90]])).hard_brake, 0);
});

check('hard acceleration is counted', () => {
  const launch = (i) => Math.min(16, 6 + 4 * i);
  const a = T.analyseDrive(drive([[60, 6, 0], [4, launch, 0], [100, 16, 0]]));
  assert.strictEqual(a.hard_accel, 1);
});

check('a right-angle corner is one turn; a fast one is also a sharp turn', () => {
  const slowCorner = (i) => 90 + i * 15; // 90 deg over 6 s at 6 m/s
  const slow = T.analyseDrive(drive([[100, 6, 90], [6, 6, slowCorner], [100, 6, 180]]));
  assert.strictEqual(slow.turns, 1); assert.strictEqual(slow.sharp_turn, 0);
  const fastCorner = (i) => 90 + i * 45; // 90 deg in 2 s at 15 m/s = 11.8 m/s^2
  const fast = T.analyseDrive(drive([[100, 15, 90], [2, 15, fastCorner], [100, 15, 180]]));
  assert.strictEqual(fast.turns, 1); assert.strictEqual(fast.sharp_turn, 1);
});

check('a full stop after moving is counted', () => {
  const a = T.analyseDrive(drive([[60, 10, 0], [30, 0, 0], [60, 10, 0]]));
  assert.strictEqual(a.stops, 1);
});

check('a short or inaccurate trip has no score', () => {
  assert.strictEqual(T.analyseDrive(drive([[50, 10, 0]])).score, null);
  const blurry = T.analyseDrive(drive([[300, 12, 0]], 40));
  assert.strictEqual(blurry.score, null); assert.strictEqual(blurry.grade, null);
  assert.strictEqual(T.analyseDrive([]).score, null);
});

check('grades follow the score bands', () => {
  assert.strictEqual(T.DRIVING.green, 85); assert.strictEqual(T.DRIVING.yellow, 65);
  const brake = (i) => Math.max(4, 14 - 4.5 * i);
  const segments = [];
  for (let k = 0; k < 6; k++) segments.push([40, 14, 0], [3, brake, 0], [20, 4, 0]);
  const rough = T.analyseDrive(drive(segments));
  assert.strictEqual(rough.grade, rough.score >= 85 ? 'green' : rough.score >= 65 ? 'yellow' : 'red');
  assert.ok(rough.score < 85, rough.score);
});

check('the score never rewards speed', () => {
  const slow = T.analyseDrive(drive([[400, 8, 90]]));
  const fast = T.analyseDrive(drive([[150, 30, 90]]));
  assert.ok(fast.score <= slow.score);
});

check('the share route hides the first and last 300 m', () => {
  const track = drive([[200, 10, 90]]); // 2 km straight east
  const route = T.shareRoute(track);
  assert.ok(route.length > 10);
  const startX = (route[0][1] - LNG0) * mPerDegLng;
  const endX = (route[route.length - 1][1] - LNG0) * mPerDegLng;
  assert.ok(startX >= 300 && startX < 320, startX);
  assert.ok(endX <= 2000 - 300 + 1 && endX > 1650, endX);
  assert.deepStrictEqual(T.shareRoute(drive([[60, 10, 90]])), []); // 600 m: nothing safe to show
  assert.ok(T.shareRoute(drive([[3000, 10, 90]])).length <= T.DRIVING.maxRoutePoints + 1);
});

console.log(`drive score checks passed (${passed})`);
