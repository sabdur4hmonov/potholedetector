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
  // ---------- per-trip driving analysis (TRIP-003) ----------
  // Smoothness events from GPS speed and course only. They describe how the car was
  // driven, never how fast relative to a limit: the app has no speed-limit map, and the
  // score must never reward speed.
  const DRIVING = Object.freeze({ version: 'drive-score-v1',
    minScoreDistanceM: 1000, hardBrakeMps2: 3.5, hardAccelMps2: 3.0, sharpTurnMps2: 4.0,
    minEventSpeedMps: 5, minTurnSpeedMps: 2, turnDegrees: 60, turnWindowS: 20,
    eventGapS: 5, minDtS: 0.5, maxDtS: 3, stopSpeedMps: 0.8, stopMinS: 5,
    penaltyPer10km: Object.freeze({ hard_brake: 8, hard_accel: 5, sharp_turn: 5 }),
    green: 85, yellow: 65, routeTrimM: 300, maxRoutePoints: 400 });

  function bearing(a, b) {
    const rad = Math.PI / 180;
    const y = Math.sin((b[2] - a[2]) * rad) * Math.cos(b[1] * rad);
    const x = Math.cos(a[1] * rad) * Math.sin(b[1] * rad)
      - Math.sin(a[1] * rad) * Math.cos(b[1] * rad) * Math.cos((b[2] - a[2]) * rad);
    return (Math.atan2(y, x) / rad + 360) % 360;
  }
  const angleDiff = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; };

  function analyseDrive(track) {
    const base = deriveTripStats(track);
    const rows = (Array.isArray(track) ? track : []).slice(0, POLICY.maxPoints).filter(valid);
    const counts = { hard_brake: 0, hard_accel: 0, sharp_turn: 0, turns: 0, stops: 0 };
    const lastEvent = { hard_brake: -Infinity, hard_accel: -Infinity, sharp_turn: -Infinity };
    let prev = null, prevCourse = null, turnStartCourse = null, turnStartT = 0;
    let stoppedSince = null, stopCounted = false, wasMoving = false;
    // Trip distance for the card: full displacement while the car is really moving. (The
    // dashboard total above deliberately subtracts GPS error and is a lower bound.)
    let distance = 0, moving = 0;
    const speedOf = (p, q) => {
      if (finite(p[4]) && p[4] >= 0 && p[4] <= POLICY.maxSpeedMps) return p[4];
      if (!q) return null;
      const dt = p[0] - q[0];
      return dt > 0 ? meters(q, p) / dt : null;
    };
    for (const point of rows) {
      const speed = speedOf(point, prev);
      if (prev) {
        const dt = point[0] - prev[0];
        const prevSpeed = speedOf(prev, null) ?? speed;
        const step = meters(prev, point);
        if (dt > 0 && dt <= POLICY.maxGapSeconds && step / dt <= POLICY.maxSpeedMps
          && ((speed != null && speed >= 1) || step > prev[3] + point[3])) {
          distance += step; moving += dt;
        }
        if (dt >= DRIVING.minDtS && dt <= DRIVING.maxDtS && speed != null && prevSpeed != null) {
          const accel = (speed - prevSpeed) / dt;
          const t = point[0];
          if (-accel >= DRIVING.hardBrakeMps2 && prevSpeed >= DRIVING.minEventSpeedMps
            && t - lastEvent.hard_brake >= DRIVING.eventGapS) { counts.hard_brake++; lastEvent.hard_brake = t; }
          if (accel >= DRIVING.hardAccelMps2 && speed >= DRIVING.minEventSpeedMps
            && t - lastEvent.hard_accel >= DRIVING.eventGapS) { counts.hard_accel++; lastEvent.hard_accel = t; }
        }
        // Course: GPS heading when moving, otherwise the bearing between fixes.
        let course = null;
        if (speed != null && speed >= DRIVING.minTurnSpeedMps) {
          course = finite(point[5]) ? point[5] : (meters(prev, point) >= 5 ? bearing(prev, point) : null);
        }
        if (course != null) {
          if (prevCourse != null && dt > 0 && dt <= DRIVING.maxDtS) {
            const yaw = angleDiff(course, prevCourse) * Math.PI / 180 / dt;
            const t = point[0];
            if (speed >= DRIVING.minEventSpeedMps && speed * yaw >= DRIVING.sharpTurnMps2
              && t - lastEvent.sharp_turn >= DRIVING.eventGapS) { counts.sharp_turn++; lastEvent.sharp_turn = t; }
          }
          if (turnStartCourse == null || point[0] - turnStartT > DRIVING.turnWindowS) {
            turnStartCourse = course; turnStartT = point[0];
          } else if (angleDiff(course, turnStartCourse) >= DRIVING.turnDegrees) {
            counts.turns++; turnStartCourse = course; turnStartT = point[0];
          }
          prevCourse = course;
        }
      }
      if (speed != null) {
        if (speed <= DRIVING.stopSpeedMps) {
          if (stoppedSince == null) { stoppedSince = point[0]; stopCounted = false; }
          if (wasMoving && !stopCounted && point[0] - stoppedSince >= DRIVING.stopMinS) {
            counts.stops++; stopCounted = true;
          }
        } else {
          stoppedSince = null;
          if (speed >= DRIVING.minTurnSpeedMps) wasMoving = true;
        }
      }
      prev = point;
    }
    let score = null, grade = null;
    if (distance >= DRIVING.minScoreDistanceM) {
      const per10km = 10000 / distance;
      const penalty = Object.entries(DRIVING.penaltyPer10km)
        .reduce((sum, [kind, weight]) => sum + counts[kind] * per10km * weight, 0);
      score = Math.max(0, Math.min(100, Math.round(100 - penalty)));
      grade = score >= DRIVING.green ? 'green' : score >= DRIVING.yellow ? 'yellow' : 'red';
    }
    return Object.freeze({ policy_version: DRIVING.version,
      distance_m: moving ? distance : null, moving_time_s: moving || null,
      avg_moving_speed_mps: moving ? distance / moving : null,
      coverage: base.coverage, ...counts, score, grade });
  }

  // A route sketch for sharing: the first and last few hundred metres are cut off so a
  // shared picture never shows where the driver lives or works.
  function shareRoute(track) {
    const rows = (Array.isArray(track) ? track : []).slice(0, POLICY.maxPoints).filter(valid);
    if (rows.length < 2) return [];
    const along = [0];
    for (let i = 1; i < rows.length; i++) along.push(along[i - 1] + meters(rows[i - 1], rows[i]));
    const total = along[along.length - 1];
    if (total <= DRIVING.routeTrimM * 2 + 100) return [];
    const kept = rows.filter((_, i) => along[i] >= DRIVING.routeTrimM && along[i] <= total - DRIVING.routeTrimM);
    const step = Math.max(1, Math.ceil(kept.length / DRIVING.maxRoutePoints));
    return kept.filter((_, i) => i % step === 0 || i === kept.length - 1).map((p) => [p[1], p[2]]);
  }

  const api = Object.freeze({ POLICY, DRIVING, deriveTripStats, summarizeDrives, analyseDrive, shareRoute });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TripStats = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
