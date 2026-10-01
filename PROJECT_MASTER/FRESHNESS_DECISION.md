# FRESH-001 — freshness policy decision preparation

**Status: PREPARATION COMPLETE; HUMAN DECISION PENDING.** No freshness policy is approved or implemented by this record. CONF-001 is complete. REPORT-LOCAL-001 remains PARTIALLY COMPLETE and DEFERRED/BLOCKED on physical-device validation; NEW-002 remains separate.

## Decision required

The product owner must specify the maximum age for `fresh`, the maximum age for `aging` (after which `stale` starts), and whether the planned `expired` state is included in this implementation. If included, specify its boundary and visible behavior. Supply the policy rationale/evidence; this repository contains no observed repair-duration or detector-recall corpus that validates product cutoffs. No default is selected here.

Documented state choices are:

| Choice grounded in the roadmap | Consequence |
| --- | --- |
| Use the existing `fresh` / `aging` / `stale` / `unknown` classifier | Two approved boundaries can parameterize the existing pure policy. Old reports remain stale after the second boundary; no expiry rule exists. Integrating user-visible categories still requires the decision and tests. |
| Include the roadmap's planned `expired` state | Requires a third approved boundary, explicit semantics and updated versioned native/web policy and parity expectations. The roadmap does not specify whether expired evidence is shown differently or excluded from a particular consumer; this must be decided explicitly. Age cannot set fixed or delete evidence. |

The one-day/seven-day test window is not a third product option or a recommendation. The human may explicitly approve those values with rationale or provide different supported values; elapsed time, a test fixture and a matching horizon are not approval.

## Repository evidence

* `MASTER_EXECUTION_PLAN.md`, FRESH-001: define display states, keep the matching horizon distinct from freshness, expose unknown timestamps, test clock boundaries/stale cache/condition/parity, and never set fixed or conceal uncertainty.
* `PRODUCT_IMPLEMENTATION_ROADMAP.md`, F8: the foundation exists; product decay boundaries, expired behavior and negative-pass evidence are missing. Future expiry/weighting is conditional on selected thresholds. Negative-pass collection belongs to WARN-NEG-001 and must not be smuggled into FRESH-001.
* `FUTURE_SCORING.md` and `hazard-scoring-v1.json`: 86,400 and 604,800 seconds are fixture parameters only. Existing categories are ordinal, not a combined score.
* `PRODUCT_DECISIONS.md`: D0 is recorded; no freshness policy is recorded. Latest CONF-001 status/next steps/worklog explicitly require a separate freshness decision.

## Exact existing behavior

`scoreHazardReport` and `NativeHazardScoringPolicy.score` accept an explicit reference time and caller-supplied window. The first boundary is inclusive (`age <= freshThroughSeconds`); the second is inclusive (`age <= staleAfterSeconds`); greater ages are stale. The window must satisfy `0 <= freshThroughSeconds < staleAfterSeconds`. Unknown, missing, zero/invalid or future last-seen timestamps yield unknown. Ineligible reports also yield unknown. A clock moving behind the observation therefore cannot manufacture a fresh classification.

`last_seen_at` / `lastSeenAt` is in Unix seconds. Native inference seeds it from captured time; canonical deduplication updates it from observation/capture time, and web matching takes the maximum event time. It is not the time a cache was opened, a report was reviewed or a sync was received. Some existing web imports/manual records use creation-time fallbacks when capture time is unavailable; those are existing provenance limits, not permission to assert a new verified sighting. FRESH-001 must preserve or explicitly review those semantics rather than silently reinterpret them.

The 30-day deduplication horizon is a matching constraint, not freshness, expiry or repair evidence. Condition remains separately fixed/open/review/unknown; freshness cannot make an old pothole repaired. Current manual-first reports remain unknown under scoring eligibility. Any change to manual eligibility needs an explicit additional decision consistent with D0.

## Affected components and required implementation checks

After approval, reuse `static/hazard-model.js` and `drive/NativeHazardScoringPolicy.kt`, their versioned fixtures/JVM/Node tests, and report/map display in `static/index.html` with Android/hosted mirrors and CSP hashes. CONF-001 observation-support/severity APIs and original scoring outputs must remain compatible, or any expiry extension must introduce an explicit versioned contract. Do not persist derived categories initially. Keep private/offline operation and existing report/native bridge schemas.

Validate each approved boundary just below, exactly at and just above it; repeated evaluation; timestamp missing/invalid/future states; advancing/backward reference time; stale cached reports after reopening; fixed/open/review/unknown conditions; actual manual/debug/rejected records; native/web parity; and browser display/CSP/mirror coverage. Use current reference time when recomputing local presentation, without network or new trip retention. Fixed reports retain historical evidence with a clear condition label. Expiry must not erase records or imply repair. Existing evidence/scoring, matching, outbox, full-frame and resource contracts remain protected.

Warning integration, combined health weighting, negative passes, route retention, model changes and physical validation are not part of this decision-preparation package. No representative field evidence, browser freshness implementation, JVM freshness extension or performance verification is claimed.

## Human response needed to unblock FRESH-001

1. What maximum observation age counts as **fresh**, and what maximum age counts as **aging** before **stale**, with what rationale/evidence?
2. Should this implementation use the existing four states, or include the planned **expired** state? If included, at what age and with what explicit display/consumer behavior?

Until that response is recorded as approved, FRESH-001 implementation remains BLOCKED. Preparation completion does not complete FRESH-001.
