---
phase: 07-corrected-re-validation-of-the-post-cisd-studies
plan: 01
subsystem: research
tags: [pandas, barrier-analysis, cisd, post-cisd-context]

requires:
  - phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for
    provides: corrected discovery/OOS/walk-forward validation harness that 07-03 will re-run
provides:
  - barrier_outcome_forward — 3-way (continuation/reversal/neither) sibling to barrier_hit_forward
  - failed_gap_against_reversal / failed_gap_against_neither tags on compute_post_cisd_context
  - chart_post_cisd_context renders the two new tags
affects: [07-02, 07-03]

tech-stack:
  added: []
  patterns:
    - "Sibling-function pattern: add barrier_outcome_forward beside barrier_hit_forward instead of modifying it, to preserve the existing bool contract byte-for-byte"

key-files:
  created: []
  modified:
    - cisd_barriers.py
    - cisd_charts.py
    - cisd_analysis.py
    - tests/test_research_extensions.py

key-decisions:
  - "barrier_outcome_forward duplicates barrier_hit_forward's window/tie-break logic rather than refactoring barrier_hit_forward to call it, per the plan's explicit behavior-preservation invariant (barrier_hit_forward and barrier_hit must stay byte-identical)"
  - "barrier_outcome_forward re-exported from cisd_analysis.py (deviation, see below) — required by acceptance criteria for importability"

patterns-established:
  - "Reversal/neither tags are flat {ct: {tag: {total, runs}}} keys, not nested under failed_gap_against, so the manifest generic dispatch branch needs zero changes"

requirements-completed: [RES-04]

coverage:
  - id: D1
    description: "barrier_outcome_forward returns the correct 3-way outcome over the identical LOOKAHEAD window as barrier_hit_forward, with continuation provably equivalent to barrier_hit_forward==True"
    requirement: RES-04
    verification:
      - kind: unit
        ref: "tests/test_research_extensions.py -k barrier_outcome (5 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "compute_post_cisd_context exposes failed_gap_against_reversal / failed_gap_against_neither, scoped to failed_gap_against only, with the published continuation rate unchanged"
    requirement: RES-04
    verification:
      - kind: unit
        ref: "tests/test_research_extensions.py -k 'post_cisd or reversal or neither' (19 tests)"
        status: pass
    human_judgment: false

duration: ~10min (Codex implementation) + orchestrator verification/commit
completed: 2026-07-11
status: complete
---

# Phase 07 Plan 01: Reversal-Barrier Measurement Summary

**Added `barrier_outcome_forward` and wired distinct reversal/neither tags into `compute_post_cisd_context`'s `failed_gap_against` bucket, with the existing continuation rate provably unchanged.**

## Performance

- **Duration:** ~10 min Codex implementation (task-mrgekh1u-41rehx, 5m40s wall) + orchestrator review/commit
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `barrier_outcome_forward(df, idx, row, ct) -> str` in `cisd_barriers.py`, returning "continuation" | "reversal" | "neither" over the identical `range(2, LOOKAHEAD + 2)` window as `barrier_hit_forward`, with the same stop-checked-first tie-break ordering.
- `compute_post_cisd_context` now reports `failed_gap_against_reversal` and `failed_gap_against_neither` (each `{total, runs}`), scoped strictly to the `failed_gap_against` bucket; the other three gap tags are untouched.
- `chart_post_cisd_context`'s `_TAGS` list extended with the two new tags (alpha 0.55 / 0.4).
- `barrier_outcome_forward` re-exported from `cisd_analysis.py` so it is importable as `cisd_analysis.barrier_outcome_forward`.
- 10 new tests in `tests/test_research_extensions.py`, including a behavior-lock test proving `failed_gap_against["runs"]` (continuation) is unchanged versus calling `barrier_hit_forward` directly.

## Task Commits

1. **Task 1: barrier_outcome_forward — 3-way continuation/reversal/neither check (D-05/D-06)** - `1a0971d` (feat)
2. **Task 2: Wire reversal/neither tags into compute_post_cisd_context + chart (D-06/D-07)** - `dd39150` (feat)

## Files Created/Modified
- `cisd_barriers.py` - new `barrier_outcome_forward` function; `compute_post_cisd_context` wiring for the two new tags; `__all__` export
- `cisd_charts.py` - `chart_post_cisd_context._TAGS` extended
- `cisd_analysis.py` - re-exports `barrier_outcome_forward`
- `tests/test_research_extensions.py` - 10 new tests

## Decisions Made
- Execution was delegated to Codex (`codex:codex-rescue`) per explicit user instruction to bypass `gsd-executor` for this phase, while the orchestrator (this session) retained ownership of verification, committing, and all `.planning/` bookkeeping.
- `barrier_outcome_forward` was implemented as a standalone sibling function duplicating `barrier_hit_forward`'s loop rather than having one call the other, to make the byte-identical-source acceptance criterion trivially satisfiable and eliminate any risk of behavior drift.

## Deviations from Plan

### Auto-fixed Issues

**1. [Acceptance criteria] Re-exported `barrier_outcome_forward` from `cisd_analysis.py`**
- **Found during:** Task 1
- **Issue:** Acceptance criteria require `barrier_outcome_forward` to be "importable as `cisd_analysis.barrier_outcome_forward`," but the plan's `<action>` only specified adding it to `cisd_barriers.py`.
- **Fix:** Added the import and `__all__` entry in `cisd_analysis.py`, mirroring how `barrier_hit_forward` is already re-exported.
- **Files modified:** `cisd_analysis.py`
- **Verification:** Import path exercised by the new tests; full suite green.
- **Committed in:** `1a0971d` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (missing-critical for acceptance criteria satisfaction). No scope creep.

## Issues Encountered
Codex (`codex:codex-rescue`) could not run `git commit` itself — its sandbox mounts `.git` read-only in this environment (`fatal: Unable to create '.../.git/index.lock': Read-only file system`). The orchestrator verified the working-tree diff and test results, then split the diff into two task-scoped commits via `git add -p` and committed them directly using the repo's existing git author config.

## Next Phase Readiness
- `barrier_outcome_forward` and the two new tags are in place and tested — 07-02 (verdict script) and 07-03 (real-data regeneration + README) can proceed.
- No blockers.

---
*Phase: 07-corrected-re-validation-of-the-post-cisd-studies*
*Completed: 2026-07-11*
