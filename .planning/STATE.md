---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Rigorous Validation & Post-CISD Modeling
current_phase: 7
current_phase_name: Corrected Re-Validation of the Post-CISD Studies
status: executing
stopped_at: Completed 06-02-PLAN.md (walk-forward validation, WF-01)
last_updated: "2026-07-10T19:36:42.208Z"
last_activity: 2026-07-10
last_activity_desc: Phase 06 complete, transitioned to Phase 7
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-10)

**Core value:** A reported edge can be trusted — every published rate is sample-size gated, carries a confidence interval, and is confirmed out-of-sample.
**Current focus:** Phase 06 — harder-evidence-bar-multiple-comparisons-correction-walk-for

## Current Position

Phase: 7 — Corrected Re-Validation of the Post-CISD Studies
Plan: Not started
Status: Ready to execute
Last activity: 2026-07-10 — Phase 06 complete, transitioned to Phase 7

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 2 (v1.0)
- Average duration: -
- Total execution time: 0 hours (v2.0)

**By Phase (v2.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 06 | 2 | - | - |
| 7 | TBD | - | - |
| 8 | TBD | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 06 P02 | 13min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.0 scope = MHT-01 + WF-01 (harness upgrade) → RES-04 + RES-05 (corrected re-validation of post-CISD studies) → ML-01 (conditional model); ML-01 is strictly gated on RES-05's corrected evidence
- New methodology is additive/parallel output — existing published numbers must not silently move; any change in how a prior finding reads must be deliberate and visible (carried from v1.0 behavior-lock)
- RES-04 (reversal barrier) folded into Phase 7 with RES-05 because both operate on the same `post_cisd_context` study; it does not block or get blocked by the Phase 6 harness upgrade
- ML-01's phase may validly conclude "no model warranted" — the roadmap does not presuppose the post-CISD tags clear the corrected bar
- [Phase 05-02]: post_cisd_context uses barrier_hit_forward (continuation target = candle[0] extreme in CISD direction); RES-04 adds the opposite-extreme reversal measurement
- [Phase 06]: WF-01: WALK_FORWARD_FOLDS frozen at 4 discovery-percentile calendar dates (20th/40th/60th/80th); slice_fold anchors folds to the discovery region only; evaluate_fold uses a per-fold MIN_N gate; walk_forward_verdict requires a strict majority (>50%) of folds to pass
- [Phase 06]: walk-forward CLI branch takes precedence over --oos if both are passed, and writes output/validation_manifest_walkforward.csv as a purely additive sibling artifact without touching the discovery/OOS manifests or the sacred OOS banner

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- SMT integration path remains untested in CI (hardcoded WSL path); known limitation carried from v1.0
- Phase 6 correction/walk-forward math is net-new (no prior MHT/walk-forward code in `scripts/build_validation.py`); needs its own characterization tests

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Advanced validation | Multiple-comparisons correction (MHT-01) | promoted to Phase 6 | 2026-07-10 |
| Advanced validation | Walk-forward / rolling-window validation (WF-01) | promoted to Phase 6 | 2026-07-10 |
| Modeling | `post_cisd_ml` post-CISD ML model (ML-01) | promoted to Phase 8 (conditional) | 2026-07-10 |
| Verification gap | Phase 03 — `03-VERIFICATION.md` human QA checks | human_needed (out of v2.0 scope) | 2026-07-10 |
| Verification gap | Phase 05 — formal verification report missing | missing (out of v2.0 scope) | 2026-07-10 |
| Traceability | VALID-01 through VALID-05 source checklist stale at closeout | normalized in archive | 2026-07-10 |

## Session Continuity

Last session: 2026-07-10T18:01:31.759Z
Stopped at: Completed 06-02-PLAN.md (walk-forward validation, WF-01)
Resume file: None

## Operator Next Steps

- Plan Phase 6 with /gsd-plan-phase 6
