---
phase: 05-new-cisd-research-on-the-validated-engine
plan: 02
subsystem: research
tags: [cisd, barrier-analysis, post-cisd-context, gap, reversal, validation-harness, tdd, wilson-ci]

# Dependency graph
requires:
  - phase: 05-new-cisd-research-on-the-validated-engine
    plan: 01
    provides: barrier_hit_forward re-anchored helper, candle1_close_dir/candle1_past_candle0_wick feature columns, generic-branch harness pattern
  - phase: 04-test-gated-modular-refactor
    provides: cisd_data/cisd_barriers/cisd_charts modular engine, ANALYSIS_META registry, re-export shim
  - phase: 02-validation-harness
    provides: build_validation.py, wilson_ci, n_gate, OOS_START, generic else dispatch branch

provides:
  - candle1_failed_followthrough, candle2_gap_dir, candle2_past_candle1_wick precomputed columns in _annotate_cisd_research
  - compute_post_cisd_context — failed-candle[1] + candle[2]-gap barrier study (forward-anchored) with a separate Reading-B cut
  - chart_post_cisd_context — horizontal bar chart with alpha layering
  - ANALYSES['post_cisd_context'] and ANALYSIS_META['post_cisd_context'] (standalone=True)
  - output/PostCISD_Context_All_Timeframes.png
  - post_cisd_context flows through build_manifest_rows (generic branch) and build_csv_rows on all 4 TFs

affects:
  - future research extending the candle[1]-failed / candle[2]-gap regime or the reversal-context bucket

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Precompute-in-prepare, consume-in-compute (3 multi-bar features added to _annotate_cisd_research)
    - Precondition-gated bucketing: failed_gap_* buckets only counted when candle[1] failed to close past candle[0]'s extreme (D-06)
    - Reading-B as a separate uncrossed cut (candle2_past_candle1_wick) — never multiplied into the gap buckets (D-04, no double-count)
    - Forward-anchored continuation only (barrier_hit_forward, idx+2) — no in-window variant (D-06)
    - {dir:{tag:{total,runs}}} shape slots into generic harness branch + build_csv_rows branch with no special-casing

key-files:
  created: []
  modified:
    - cisd_data.py — _annotate_cisd_research: 3 new precomputed columns (candle1_failed_followthrough, candle2_gap_dir, candle2_past_candle1_wick)
    - cisd_barriers.py — compute_post_cisd_context, ANALYSES, ANALYSIS_META, __all__
    - cisd_charts.py — chart_post_cisd_context, build_csv_rows branch extended, __all__
    - cisd_analysis.py — re-export imports and __all__ extended
    - tests/test_research_extensions.py — new post_cisd_context + feature-column tests (TDD RED batch)

key-decisions:
  - "ONE post_cisd_context analysis (D-05): the reversal context is the failed-candle[1] + gap-against BUCKET, not a separate analysis"
  - "Failed-candle[1] precondition gates the failed_gap_* buckets (D-06): candle1_failed_followthrough is the negation of 05-01's candle1_past_candle0_wick for events"
  - "Signed candle[2].open - candle[1].close mapped to gap_with/gap_against/flat relative to CISD direction (D-07); flat epsilon at 0 consistent with neutral direction convention"
  - "Continuation measured forward-anchored via barrier_hit_forward (idx+2), candle[0] high/low target/stop — no in-window variant (D-06)"
  - "Reading B (candle[2] beyond candle[1] wick, D-04) homed HERE as a separate uncrossed cut, NOT duplicated into 05-01's compute_candle1_followthrough"
  - "post_cisd_context is standalone (ANALYSIS_META.standalone=True); flows through generic build_manifest_rows + build_csv_rows branches — no build_validation.py change needed"

patterns-established:
  - "Precondition-partition pattern: sum of failed_gap_* totals equals the count of failed-candle[1] events"
  - "Reading-B side cut: an extra tag counted independently of the primary buckets, avoiding bucket explosion the n>=50 gate would suppress"

requirements-completed: [RES-02, RES-03]

# Metrics
duration: interrupted-and-resumed
completed: 2026-06-14
---

# Phase 5 Plan 02: Post-CISD Context Barrier Study Summary

**A single multi-bar `post_cisd_context` analysis — CISD with a failed candle[1], bucketed by candle[2]'s gap direction (gap-with / gap-against / flat), measured forward-anchored — plus a separate Reading-B cut, reported through the Wilson CI + n-gate + IS/OOS harness from the start.**

## Execution note (session-limit interruption)

The gsd-executor for this plan hit the provider session limit **mid-Task-2**. State at interruption:
- Task 1 (feature columns) — already committed (`268468b`), RED tests committed (`83276f7`).
- Task 2 (compute + chart + registry + re-export + build_csv_rows) — fully written in the working tree but **not yet committed**.
- Task 3 (harness wiring) — no code change required (generic branch), tests already present.

On resume, the orchestrator read the uncommitted Task 2 changes, verified them against the locked decisions (D-04/D-05/D-06/D-07) and the passing tests, and committed them as `5b8b2b4`. No code was rewritten — the executor's implementation was correct and complete.

## Accomplishments

- Precomputed three multi-bar feature columns in `_annotate_cisd_research`: `candle1_failed_followthrough` (bool, negation of 05-01's past-wick flag for events), `candle2_gap_dir` ("gap_with"/"gap_against"/"flat"), `candle2_past_candle1_wick` (bool), all with idx+1/idx+2 boundary guards.
- Added `compute_post_cisd_context` — `{dir:{tag:{total,runs}}}` with `failed_gap_with` / `failed_gap_against` / `failed_gap_flat` (gated on the failed-candle[1] precondition) plus a separate `candle2_past_candle1_wick` Reading-B tag; continuation measured with `barrier_hit_forward` (forward-anchored, no in-window variant).
- Added `chart_post_cisd_context`; registered `post_cisd_context` in ANALYSES + ANALYSIS_META (standalone=True); re-exported both symbols through `cisd_analysis`; extended the `build_csv_rows` branch.
- Standalone PNG produced via `cisd_analysis.py post_cisd_context`; harness emission verified through the generic `build_manifest_rows` branch (unit-tested) and `build_csv_rows` (16 rows emitted on a synthetic frame).

## Task Commits

1. **RED: failing tests for feature columns, compute, chart, harness wiring** - `83276f7` (test)
2. **Task 1 GREEN: precompute candle[1]-failed, candle[2]-gap, Reading-B columns** - `268468b` (feat)
3. **Task 2 GREEN: compute_post_cisd_context, chart, registry, re-export, build_csv_rows** - `5b8b2b4` (feat)
4. **Task 3: harness wiring** — no code change (generic branch auto-handles the registered key; tests from the RED commit pass).

## Files Created/Modified

- `cisd_data.py` — `_annotate_cisd_research`: 3 new precomputed columns with boundary guards
- `cisd_barriers.py` — `compute_post_cisd_context`, ANALYSES + ANALYSIS_META entries, `__all__`
- `cisd_charts.py` — `chart_post_cisd_context`, `build_csv_rows` branch extended, `__all__`
- `cisd_analysis.py` — import blocks and `__all__` extended
- `tests/test_research_extensions.py` — new post_cisd_context + feature-column tests (TDD RED batch)

## Decisions Made

- The reversal context is a **bucket** (`failed_gap_against`) of the single `post_cisd_context` analysis, not a separate analysis (D-05).
- Reading B (candle[2] beyond candle[1]'s wick, D-04) lives **only** here as a separate uncrossed cut — a test asserts no such bucket exists in `compute_candle1_followthrough` (no double-count).
- No `build_validation.py` change: the registered key flows through the existing generic `else` branch, and `main()` auto-includes it via `list(ANALYSES.keys())` across all 4 timeframes.

## Deviations from Plan

- **Task 2 was committed by the orchestrator, not the original executor**, because the executor was terminated by the provider session limit before it could commit (see "Execution note" above). The implementation is the executor's; only the commit was performed on resume after verification.

## Verification status

**Confirmed this session (fast / functional):**
- `pytest tests/test_research_extensions.py -q` → **57 passed** (via `.venv`, the pinned pandas 3.0.2 env)
- `cisd_analysis.py post_cisd_context` → `output/PostCISD_Context_All_Timeframes.png` produced (exit 0)
- Re-export shim: `import cisd_analysis; cisd_analysis.compute_post_cisd_context; cisd_analysis.chart_post_cisd_context` — OK
- Registry: `post_cisd_context` in ANALYSES + ANALYSIS_META with `standalone=True`
- `build_csv_rows(['post_cisd_context', ...])` emits 16 Post-CISD Context rows on a synthetic frame
- Implementation reviewed against D-04/D-05/D-06/D-07 — faithful

**DEFERRED (not run this session, by user decision — run before marking the phase verified):**
- Full behavior-preservation gate: `.venv/bin/python -m pytest tests/ -q` (~22–28 min; baseline after Wave 1 was 113 passed; this plan is additive so the target is 113 + the new post_cisd_context tests, all green)
- Full validation-manifest regen: `.venv/bin/python scripts/build_validation.py` (~20 min) — the current `output/validation_manifest_*.csv` are STALE (pre-phase-5) and do NOT yet contain `candle1_followthrough` or `post_cisd_context` rows end-to-end. Harness-emission correctness is proven by unit tests; only the on-disk artifact is pending.

## Known Stubs

None — the analysis is fully wired end-to-end (precomputed columns → compute → chart → ANALYSES → re-export → manifest + CSV). No placeholder data.

## Threat Flags

No new network endpoints, auth paths, file-access patterns, or schema changes. Purely additive: in-memory columns, pure-Python compute, CSV/PNG output.

## Self-Check: PASSED (implementation + unit tests; full-suite behavior gate DEFERRED per user decision)

- `cisd_data.py` 3 new columns: CONFIRMED
- `cisd_barriers.py` compute_post_cisd_context + registry: CONFIRMED
- `cisd_charts.py` chart_post_cisd_context + build_csv_rows: CONFIRMED
- `cisd_analysis.py` re-export shim: CONFIRMED
- `tests/test_research_extensions.py` 57 passed: CONFIRMED
- Standalone PNG produced: CONFIRMED
- Full `pytest tests/ -q` behavior-preservation gate: **DEFERRED (not run)**
- Full manifest regen: **DEFERRED (not run)**

---
*Phase: 05-new-cisd-research-on-the-validated-engine*
*Completed (implementation): 2026-06-14 — full-suite + manifest verification deferred*
