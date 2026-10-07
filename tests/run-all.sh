#!/usr/bin/env bash
# Local checks that guard shipped behaviour. Some mocked checks still read the test key
# from .env, but no live service is contacted unless RUN_LIVE_TESTS=1 is explicit.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
if [ ! -x "$PY" ]; then
  # Git worktrees do not copy ignored virtualenvs. Reuse the main checkout's venv when
  # available so this exact suite remains runnable on release branches/worktrees.
  COMMON_GIT_DIR=$(git rev-parse --git-common-dir 2>/dev/null || true)
  MAIN_CHECKOUT=$(cd "$COMMON_GIT_DIR/.." 2>/dev/null && pwd || true)
  [ -x "$MAIN_CHECKOUT/.venv/bin/python3" ] && PY="$MAIN_CHECKOUT/.venv/bin/python3" || PY=python3
fi

start_server() {
  (nohup python3 tests/serve_app.py --port 8765 >/tmp/pothole-srv.log 2>&1 &)
  for _ in $(seq 1 20); do
    curl -s -o /dev/null http://localhost:8765/index.html && return 0
    sleep 0.5
  done
  return 1
}
# The suite launches a browser per test and the little server has died mid-run before,
# which reads as a test failure and is not one. Check it before each test, restart if gone.
ensure_server() {
  curl -s -o /dev/null --max-time 3 http://localhost:8765/index.html && return 0
  echo "    (restarting the static server)"
  pkill -f "tests/serve_app.py --port 8765" >/dev/null 2>&1
  start_server
}

pkill -f "http.server 8765" >/dev/null 2>&1
pkill -f "tests/serve_app.py --port 8765" >/dev/null 2>&1
start_server || { echo "could not start the static server"; exit 1; }
trap 'pkill -f "tests/serve_app.py --port 8765" >/dev/null 2>&1' EXIT

LOCAL_TESTS="unit_test android_release_optimization_test pages_assets_test home_actions_test first_run_settings_test dashcam_capture_source_test eval_contract_test media_regression_manifest_test private_release_gate_test private_drive_corpus_test full_frame_invariant_test image_enhancement_parity_test prepared_eval_contract_test persistent_dedupe_test repair_status_test native_bridge_paging_test native_keyframe_reconciliation_paging_test native_keyframe_replay_scheduler_test native_background_drive_test hybrid_drive_contract_test native_keyframe_transaction_test native_duplicate_revisit_contract_test footage_metadata_test footage_failure_accounting_test drive_start_stop_test orphan_footage_test capture_cadence_test storage_commit_test stalled_body_test stream_completion_test contribution_map_test native_background_lifecycle_contract_test native_camera_redteam_contract_test native_stop_control_plane_contract_test native_terminal_summary_contract_test native_analyzer_sampling_gate_test native_location_control_plane_contract_test native_cleanup_retry_contract_test native_inference_evidence_ownership_test native_report_evidence_recovery_test native_inference_resource_contract_test native_report_evidence_quota_test native_capture_safety_contract_test native_durable_replay_test stored_xss_test privacy_consent_test photo_pothole_only_test delete_all_data_test ui_text_test rad_dataset_test rad_eval_contract_test"
LOCAL_TESTS="$LOCAL_TESTS private_eval_dataset_test exhaustive_video_eval_test"
LOCAL_TESTS="$LOCAL_TESTS native_dashcam_contract_test track_retention_test freshness_policy_test"
LOCAL_TESTS="$LOCAL_TESTS ondevice_detector_contract_test sensor_drive_test road_alerts_test"
LIVE_TESTS="footage_test"
TESTS="$LOCAL_TESTS"
if [ "${RUN_LIVE_TESTS:-0}" = "1" ]; then
  TESTS="$TESTS $LIVE_TESTS"
else
  echo "Live OpenAI checks skipped (set RUN_LIVE_TESTS=1 to include them)."
fi

fail=0
for t in $TESTS; do
  ensure_server || { echo "$t SKIPPED, no server"; fail=1; continue; }
  printf "%-24s " "$t"
  if out=$($PY "tests/$t.py" 2>&1); then
    echo "${out##*$'\n'}"
  else
    echo "FAIL"; echo "$out" | tail -12 | sed 's/^/    /'; fail=1
  fi
done
echo
[ "$fail" = "0" ] && echo "ALL TESTS PASS" || { echo "SOME TESTS FAILED"; exit 1; }
