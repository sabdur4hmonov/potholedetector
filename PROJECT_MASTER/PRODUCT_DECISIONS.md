# Product decisions

## 2026-10-06 — Uzbekistan refocus decisions (human-approved in chat)

- **India removed.** All India routing, authority packs, tender matching, complaint/handoff flows and the Kannada/Marathi/Bengali UI are removed. Languages: **English and Uzbek (Latin)**; Russian may come later. Accepted detections are saved as local drafts; nothing is sent to any authority.
- **D0 reopened — on-device detection.** The human chose a detector that runs inside the phone. The earlier "no on-device integration at this stage" line of D0 is superseded. Constraints stay: full-frame input (no crop/tile/mask/ROI), license-compatible model (no AGPL weights/code), commit-before-native-ack, and no accuracy claim without validation on real roads. Cloud/BYOK remains an optional second opinion until the on-device model is validated.
- **FRESH-001 approved:** fresh 0–7 days after last seen, aging 8–30 days, stale after 30 days. Stale potholes are never deleted; "fixed" still requires separate before/after evidence. Implemented as display chips and a dashboard summary (the existing scoring model and its Kotlin parity are unchanged).
- **TRIP-002 / D1 approved:** raw GPS tracks are deleted automatically after 30 days, any single drive's track can be deleted, and the user can turn track keeping off. Pothole reports keep their own coordinates.

## FRESH-001 freshness policy — pending human decision (2026-10-01)

**NOT APPROVED.** [FRESHNESS_DECISION.md](FRESHNESS_DECISION.md) prepares the required fresh/aging cutoffs and planned expired-state choice, evidence, consequences and contracts. No product freshness window or expiry semantics have been selected. Existing one-day/seven-day fixture values remain test parameters. This pending entry does not change D0, manual-first eligibility, condition/repair rules or authorize FRESH-001 implementation.

## D0 — DETECT-001: manual-first detection path (2026-09-30)

**Status: COMPLETE — human decision and acceptance contract recorded.** This completes the decision task, not REPORT-LOCAL-001 implementation or production verification. The user explicitly approved the following direction in this chat:

- Detection path: **Manual-first**.
- Primary product flow: **private, offline photo reporting**.
- On-device detection: **do not integrate as the primary detection path at this stage**.
- Existing cloud/BYOK functionality: **RETAIN as optional**.
- Do not remove existing cloud/BYOK functionality unless the task's acceptance criteria explicitly require removal.

CORE-002 and FUTURE-DEDUP-001 are complete at source/contract-test level. No model integration, new dependency, cloud removal, privacy-policy rewrite or production behavior change is required to record D0. Optional cloud functionality retains existing credential, consent, quota, image and network boundaries; this decision authorizes no paid calls or photo transfer. Browser paid-inference refusal remains intact. D1 retention, D2 Uzbekistan sources and NEW-002 release/provenance work remain separate.

### Acceptance targets for the selected path

These are pass/fail requirements for the next separately authorized implementation task, REPORT-LOCAL-001; they are not claims about current behavior.

| Target | Required behavior and validation |
| --- | --- |
| Primary offline flow | With network unavailable and no API key, a user can capture/import a pothole photo, explicitly confirm the issue, save it locally, reopen it after restart and review it. No cloud, geocoder, map tile, routing service, pack download or account may be a prerequisite. Exercise capture/import, save, restart and review with network blocked. |
| Honest quality evidence | A manual report is identified as user-reported, not model-confirmed. Unknown detection confidence, physical severity and AI model fields remain unknown. User confirmation establishes the reported issue, not automatic detector accuracy. Test missing/invalid photo and cancelled confirmation; neither produces a completed report. No numerical AI accuracy target is applicable to this path. |
| Whole-frame evidence | Original evidence and every derived detection/replay/export view preserve the complete field of view. Only existing whole-frame orientation, resize, compression and enhancement are allowed. Run full_frame_invariant_test.py and existing bounded-image tests. |
| Private persistence | Photo and report remain local by default. No inference/upload/send occurs automatically. Consent precedes camera/location use; missing location must be represented honestly and must not prevent a private draft. Reuse IndexedDB transaction completion and native acknowledgement boundaries; test aborted save/retry and existing Delete All coverage. No new retention policy is selected. |
| Manual identity and review | Manual reports must not be silently merged into another event. Preserve capture provenance and separate user selection from AI assessment. Test same-photo/repeated-location manual inputs, review and local evidence reopening using existing matching contracts. |
| Optional cloud/BYOK | Retain existing functionality, limits and credential handling. Manual save/review needs no configured credential. Cloud analysis is a separate explicit user choice requiring connectivity and existing consent/quota checks; failure, cancellation or exhausted quota must not erase a saved manual report. Do not enable browser paid inference. Test manual behavior with no key and cloud unavailable, plus existing AI-budget regressions. |
| Saved-frame replay | Existing cloud replay remains optional and governed by its existing limits. Manual-first does not make autonomous Drive detection or on-device replay available. Any future replay evidence must be full-frame; no automatic paid replay is authorized by D0. |
| Resource and device evidence | Keep existing image bounds and bounded persistence; no model asset/runtime is added. Model/data licence review, hard-negative detector accuracy and detector latency/memory/battery measurements are not applicable to this decision. Capture/import resource handling and actual offline restart behavior still require browser/device evidence in REPORT-LOCAL-001; no arbitrary numerical performance budget is invented here. |
| Handoff and release | Review/export is user initiated. Sending or official-channel handoff requires explicit confirmation and connectivity where needed; offline drafts do not imply submission or Uzbekistan routing coverage. Existing source/security/release gates stay unchanged. |

### DETECT-001 validation boundary

Source inspection confirms createCivicReport currently rejects road_damage; the existing pothole analysis path is not evidence of a complete manual offline pothole workflow. The choice is implementable through the existing private photo/report storage and review architecture, but the primary manual pothole flow still needs REPORT-LOCAL-001. No on-device candidate is selected, so model/data licensing and representative detector evaluation are not applicability gaps for DETECT-001. No new model or runtime licence is introduced by this documentation task.

Validation for this record checks the human decision against the DETECT-001 task card, source evidence and existing deterministic full-frame, bounded-image, manual non-merge, outbox and optional-cloud budget contracts. Test results and limitations are recorded in AGENT_WORKLOG.md. This task does not claim browser/device offline verification, measured device performance, release readiness or a new detector.

**Exact next future product task:** REPORT-LOCAL-001 — implement and verify the selected manual-first private offline pothole report path while retaining cloud/BYOK as optional. Do not start it in DETECT-001.

## 2026-09-30 implementation evidence — REPORT-LOCAL-001

The selected path now passes real Chromium/IndexedDB offline/no-key capture-source/import save and review, aborted write retry, independent manual reports, evidence export, browser restart and Delete All checks on canonical and packaged assets. UI input requires data consent and explicit issue confirmation; automated coverage includes refusal/cancellation/invalid input. Tests confirm zero attempted network calls during manual creation and no-key cloud refusal. Optional cloud analysis still uses the existing constrained implementation and retains the original manual report; no live paid call was made. New labels use the existing English fallback pending translation review. Actual Android camera, native lifecycle restart and device performance remain unverified; these keep REPORT-LOCAL-001 partially complete overall. D0 and all other human decisions are unchanged.
