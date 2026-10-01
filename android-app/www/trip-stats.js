/* Private, in-memory estimates from existing [offset_s, lat, lng, accuracy_m, speed, heading] tracks. */
(function (root) {
  'use strict';
  // Engineering admission bounds, not legal speed limits or product freshness cutoffs.
  const POLICY = Object.freeze({ version: 'trip-stats-v1', maxPoints: 20000, maxDrives: 200,
    maxAccuracyM: 15, maxGapSeconds: 30, maxSpeedMps: 100 });
  const finite = Number.isFinite;
  function meters(a, b) {
    const rad = Math.PI / 180;
    const sinLat = Math.sin((b[1] - a[1]) * rad / 2);
    const sinLng = Math.sin((b[2] - a[2]) * rad / 2);
    const h = sinLat * sinLat + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * sinLng * sinLng;
    return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))));
  }
  function valid(p) {
    return Array.isArray(p) && finite(p[0]) && p[0] >= 0 && finite(p[1]) && Math.abs(p[1]) <= 90
      && finite(p[2]) && Math.abs(p[2]) <= 180 && finite(p[3]) && p[3] >= 0 && p[3] <= POLICY.maxAccuracyM;
  }
  function deriveTripStats(track) {
    const rows = Array.isArray(track) ? track : [];
    const length = Math.min(rows.length, POLICY.maxPoints);
    let previous = null, distance = 0, moving = 0, observed = 0, peak = 0, intervals = 0, rejected = 0;
    for (let i = 0; i < length; i++) {
      const point = rows[i];
      if (!valid(point)) { previous = null; rejected++; continue; }
      if (previous) {
        const dt = point[0] - previous[0];
        const displacement = meters(previous, point);
        if (dt <= 0 || dt > POLICY.maxGapSeconds || displacement / dt > POLICY.maxSpeedMps) {
          rejected++; previous = null; continue;
        }
        // Discount displacement by the two reported accuracy radii (an estimate,
        // not a guaranteed physical lower bound).
        // Speed fields alone cannot make a parked/jittering track appear to move.
        const lower = Math.max(0, displacement - previous[3] - point[3]);
        distance += lower; observed += dt; intervals++;
        if (lower > 0) { moving += dt; peak = Math.max(peak, lower / dt); }
      }
      previous = point;
    }
    return Object.freeze({ policy_version: POLICY.version,
      distance_m: intervals ? distance : null, moving_time_s: intervals ? moving : null,
      observed_time_s: intervals ? observed : null,
      avg_moving_speed_mps: moving ? distance / moving : null,
      max_interval_speed_mps: moving ? peak : null,
      accepted_intervals: intervals, rejected_samples_or_intervals: rejected,
      truncated: rows.length > length, coverage: !intervals ? 'unavailable'
        : rejected || rows.length > length ? 'partial' : 'sampled' });
  }
  function summarizeDrives(drives) {
    // Dashboard input is existing stored drives; do not retain tracks in the output.
    let distance = 0, moving = 0, peak = null, usable = 0, partial = false;
    const rows = Array.isArray(drives) ? drives : [];
    if (rows.length > POLICY.maxDrives) partial = true;
    for (let i = 0; i < Math.min(rows.length, POLICY.maxDrives); i++) {
      const drive = rows[i];
      const stats = deriveTripStats(drive && drive.gps_track);
      if (stats.distance_m == null) { partial = true; continue; }
      usable++; distance += stats.distance_m; moving += stats.moving_time_s;
      if (stats.max_interval_speed_mps != null) peak = Math.max(peak || 0, stats.max_interval_speed_mps);
      if (stats.coverage === 'partial') partial = true;
    }
    return Object.freeze({ policy_version: POLICY.version, distance_m: usable ? distance : null,
      moving_time_s: usable ? moving : null, avg_moving_speed_mps: moving ? distance / moving : null,
      max_interval_speed_mps: peak, coverage: !usable ? 'unavailable' : partial ? 'partial' : 'sampled' });
  }
  const api = Object.freeze({ POLICY, deriveTripStats, summarizeDrives });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TripStats = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
