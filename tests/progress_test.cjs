'use strict';
// MOTIV-001: levels, points, streaks, achievements and the last-trip card come only from
// the driver's real reports and drives, with the published rule and no speed reward.
process.env.TZ = 'Asia/Tashkent';
const assert = require('node:assert/strict');
const T = require('../static/trip-stats.js');

const LAT0 = 41.3111, LNG0 = 69.2797;
const PER_LNG = 111320 * Math.cos(LAT0 * Math.PI / 180);
// A straight, steady drive: n seconds at `speed` m/s.
const track = (n, speed = 12) => Array.from({ length: n }, (_, i) => [i, LAT0, LNG0 + (i * speed) / PER_LNG, 5, speed, 90]);
const at = (y, m, d, h) => new Date(y, m - 1, d, h).getTime() / 1000;
const drive = (id, start, seconds, speed) => ({ id, started_at: start, ended_at: start + seconds, gps_track: track(seconds, speed) });
const checks = [];
const check = (name, fn) => { fn(); checks.push(name); };

check('nothing yet: level 1, no points, no last trip, nothing unlocked', () => {
  const p = T.progressSummary([], [], at(2027, 1, 15, 12));
  assert.equal(p.points, 0); assert.equal(p.level, 0); assert.equal(p.nextLevelAt, 50);
  assert.equal(p.lastTrip, null); assert.equal(p.streak, 0);
  assert.ok(p.achievements.every((a) => !a.done && a.value === 0));
});

check('points follow the published rule exactly', () => {
  const now = at(2027, 1, 15, 18);
  const d = drive('a', at(2027, 1, 15, 9), 1000); // 12 km at a calm, steady speed
  const reports = [{ id: 1, status: 'draft', drive_id: 'a', created_at: now - 100 },
    { id: 2, status: 'sent', created_at: now - 200, human_label: 'pothole_cavity' },
    { id: 3, status: 'rejected', human_label: 'not_pothole' }];
  const p = T.progressSummary(reports, [d], now);
  const km = T.analyseDrive(d.gps_track).distance_m / 1000;
  const want = Math.round(2 * T.PROGRESS.pointsPerPothole + km * T.PROGRESS.pointsPerKm
    + 1 * T.PROGRESS.pointsPerGreenTrip + 2 * T.PROGRESS.pointsPerLabel);
  assert.equal(p.points, want);
  assert.equal(p.week.potholes, 2); assert.equal(p.week.trips, 1); assert.equal(p.week.calm, 1);
});

check('rejected reports never count as found potholes', () => {
  const p = T.progressSummary([{ id: 1, status: 'rejected' }, { id: 2, status: 'rejected' }], [], at(2027, 1, 15, 12));
  assert.equal(p.week.potholes, 0);
  assert.equal(p.achievements.find((a) => a.id === 'first_pothole').done, false);
});

check('driving faster never earns more points', () => {
  const now = at(2027, 1, 15, 18);
  const slow = T.progressSummary([], [drive('s', at(2027, 1, 15, 9), 1000, 12)], now);
  const fast = T.progressSummary([], [drive('f', at(2027, 1, 15, 9), 500, 24)], now); // same distance, twice the speed
  assert.ok(fast.points <= slow.points, `${fast.points} > ${slow.points}`);
});

check('levels climb at the thresholds and the bar shows progress to the next', () => {
  const reports = Array.from({ length: 6 }, (_, i) => ({ id: i, status: 'draft', created_at: 0 }));
  const p = T.progressSummary(reports, [], at(2027, 1, 15, 12)); // 60 points
  assert.equal(p.level, 1); assert.equal(p.levelFloor, 50); assert.equal(p.nextLevelAt, 200);
  assert.equal(p.toNext, 140); assert.ok(Math.abs(p.progress - 10 / 150) < 1e-9);
  const top = T.progressSummary(Array.from({ length: 500 }, (_, i) => ({ id: i, status: 'sent' })), [], 0);
  assert.equal(top.nextLevelAt, null); assert.equal(top.progress, 1); assert.equal(top.toNext, 0);
});

check('a streak counts local days in a row and survives until the end of the next day', () => {
  const days = [12, 13, 14].map((d, i) => drive(`d${i}`, at(2027, 1, d, 9), 600));
  assert.equal(T.progressSummary([], days, at(2027, 1, 14, 20)).streak, 3);
  assert.equal(T.progressSummary([], days, at(2027, 1, 15, 20)).streak, 3); // not driven yet today
  const broken = T.progressSummary([], days, at(2027, 1, 17, 9));
  assert.equal(broken.streak, 0); assert.equal(broken.bestStreak, 3);
  assert.equal(broken.achievements.find((a) => a.id === 'streak_3').done, true);
});

check('the last-trip card shows only a scored trip from the last few hours', () => {
  const d = drive('x', at(2027, 1, 15, 9), 1000);
  const fresh = T.progressSummary([{ id: 1, status: 'draft', drive_id: 'x' }], [d], at(2027, 1, 15, 12));
  assert.equal(fresh.lastTrip.id, 'x'); assert.equal(fresh.lastTrip.potholes, 1); assert.equal(fresh.lastTrip.grade, 'green');
  assert.equal(T.progressSummary([], [d], at(2027, 1, 16, 12)).lastTrip, null);
  // The newest trip by start time wins even if saved summaries share one end time.
  const older = { ...drive('old', at(2027, 1, 15, 6), 600), ended_at: at(2027, 1, 15, 11) };
  const newer = { ...drive('new', at(2027, 1, 15, 10), 600), ended_at: at(2027, 1, 15, 11) };
  assert.equal(T.progressSummary([], [older, newer], at(2027, 1, 15, 12)).lastTrip.id, 'new');
});

check('bad input is ignored, not counted', () => {
  const p = T.progressSummary([null, { status: 'draft' }, 'x'], [null, { id: 'n', gps_track: [] }, { id: 'm' }], at(2027, 1, 15, 12));
  assert.equal(p.week.potholes, 0); // the draft has no created_at, so it is not in this week
  assert.equal(p.points, T.PROGRESS.pointsPerPothole);
  assert.equal(p.week.trips, 0);
});

for (const name of checks) console.log(`PASS ${name}`);
console.log(`progress tests passed (${checks.length})`);
