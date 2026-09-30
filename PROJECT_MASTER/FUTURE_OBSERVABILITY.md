# FUTURE-OBS-001: local detection diagnostics

The native Drive burst analyzer accepts an optional `onDiagnostic` callback. It emits a small,
ordered lifecycle for one `analyzeBurst` call. No callback is installed by default, and events
are not persisted, uploaded, or written to a device log. Tests can collect the events directly.

## Contract

1. `PROCESSING_STARTED` carries the input frame count.
2. The existing two-to-three-frame gate emits `INPUT_ACCEPTED` or `INPUT_REJECTED`. Rejected
   input produces the existing unanalyzed `reject` outcome, then `RESULT_PRODUCED` with
   `NOT_ANALYZED` and `PROCESSING_COMPLETED`.
3. Accepted input emits `DETECTION_ENTERED` immediately before the bounded detection attempts.
   `DETECTION_COMPLETED` follows only when those attempts return an assessment. The attempts may
   include up to three model requests under the existing temporary-surface voting policy.
4. A returned `InferenceOutcome` emits `RESULT_PRODUCED` with `ACCEPTED`, `REJECTED`, or
   `NOT_ANALYZED`, followed by `PROCESSING_COMPLETED`. The result event follows evidence/report
   construction for accepted assessments.
5. A thrown error emits `PROCESSING_FAILED` with a class-based category (`INFERENCE`,
   `IMAGE_MEMORY`, `CANCELLED`, or `OTHER`), then `PROCESSING_COMPLETED`; the original error
   continues to the caller. A failed diagnostic callback is ignored so it cannot change the
   detection result.

Event order, frame count, result category, and failure category are deterministic for a given
execution path. Events contain no clock time, random ID, coordinates, model text, error message,
API credential, image bytes, or frame payload. The existing binary detector produces an
assessment rather than a candidate list, so no candidate count is claimed. `OTHER` is deliberately
coarse; error messages and transport details are excluded. Existing `DetectionRejectionReason`
values remain the policy-level explanation for parsed model verdicts, separate from this lifecycle.

`NativeDetectionDiagnosticsTest` exercises normal, rejected, invalid-input, repeat, callback-failure,
and thrown-inference paths using the same wrapper invoked by `NativeInferenceEngine`. The web
browser has no active paid detection path, so this contract currently covers native Drive bursts;
it does not claim browser parity or device/runtime verification. Repair verification and later
deduplication/storage are separate flows and are not included in these events.
