---
phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for
plan: 01
subsystem: testing
tags: [statistics, fdr, benjamini-hochberg, hypothesis-testing, validation-harness, pandas]

# Dependency graph
requires:
  - phase: 02-validation-harness (v1.0)
    provides: build_validation.py's wilson_ci/n_gate pure-stdlib pattern, discovery/OOS slicing, manifest CSV schema
provides:
  - p_value_vs_half(n, k) — pure-math two-sided z-test against H0: rate=0.5 (D-01)
  - bh_correct(pvalues, fdr) — Benjamini-Hochberg step-up FDR correction over one global family (D-02)
  - apply_bh_correction(rows) — wires p_value/bh_rank/bh_q_value/bh_significant/corrected_pass onto discovery manifest rows only (D-03)
affects: [06-02 (walk-forward validation, same file), 07 (post-CISD re-validation will read corrected_pass)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-stdlib statistical helpers (math module only, no scipy/statsmodels) mirroring wilson_ci's _erfinv style"
    - "Additive-only manifest columns — new columns appended as dict keys, never renaming/reordering existing ones"
    - "Discovery-stage-only correction gating via `if slice_label == \"discovery\":` in main(), keeping the sacred OOS path untouched"

key-files:
  created: []
  modified:
    - scripts/build_validation.py
    - tests/test_validation_harness.py

key-decisions:
  - "D-01: p_value_vs_half tests H0 rate=0.5 (fixed coin-flip null), not a bucket's own baseline rate, matching README/determine_verdict's same-side-of-0.5 framing"
  - "D-02: bh_correct forms ONE global family across every analysis x timeframe x instrument x direction bucket in a single pass — never grouped per-analysis-key"
  - "D-03: apply_bh_correction is called in main() only when slice_label == 'discovery'; OOS rows carry p_value but no bh_*/corrected_pass columns"
  - "corrected_pass = min_n_pass AND bh_significant — the harder evidence bar requires clearing both the sample-size gate and FDR significance"

patterns-established:
  - "New significance/correction helpers live in scripts/build_validation.py's existing 'CI helpers' section, directly after n_gate, following wilson_ci's docstring-and-guard-clause depth"

requirements-completed: [MHT-01]

coverage:
  - id: D1
    description: "p_value_vs_half(n, k) — pure-math two-sided z-test against H0: rate=0.5, with n==0 guard returning 1.0"
    requirement: "MHT-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_p_value_vs_half_at_boundary"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_p_value_vs_half_known_value"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_p_value_vs_half_zero_n"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_p_value_vs_half_in_unit_interval"
        status: pass
    human_judgment: false
  - id: D2
    description: "bh_correct(pvalues, fdr) — Benjamini-Hochberg step-up correction over one global family, returning rank/q-value/significance in original input order, monotone q-values, empty-input guard"
    requirement: "MHT-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_bh_correct_known_value"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_bh_correct_preserves_input_order"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_bh_correct_q_values_monotone"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_bh_correct_empty_input"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_manifest_rows emits a p_value column on every row (all slices); pre-existing columns remain a strict subset (additive-only lock)"
    requirement: "MHT-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_build_manifest_rows_emits_p_value"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_build_manifest_rows_schema_still_subset_after_p_value"
        status: pass
    human_judgment: false
  - id: D4
    description: "apply_bh_correction adds bh_rank/bh_q_value/bh_significant/corrected_pass to discovery rows in one global family; corrected_pass requires both min_n_pass and bh_significant; rows outside the family (n<1) get default non-significant flags; main() gates the call to slice_label=='discovery' so OOS rows never get bh_*/corrected_pass"
    requirement: "MHT-01"
    verification:
      - kind: unit
        ref: "tests/test_validation_harness.py#test_apply_bh_correction_corrected_pass_requires_both_gates"
        status: pass
      - kind: unit
        ref: "tests/test_validation_harness.py#test_apply_bh_correction_excludes_zero_n_rows_from_family"
        status: pass
      - kind: other
        ref: "grep confirms apply_bh_correction(manifest_rows) is called inside `if slice_label == \"discovery\":` in scripts/build_validation.py main()"
        status: pass
    human_judgment: false
  - id: D5
    description: "Reconciler (scripts/build_reconcile_findings.py) is unaffected by the additive manifest columns — its fixed column selection continues to work"
    requirement: "MHT-01"
    verification:
      - kind: unit
        ref: "tests/test_reconcile_findings.py (full suite, 12 tests)"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-10
status: complete
---

# Phase 6 Plan 1: Significance Testing & BH Correction Summary

**Per-bucket p-values (H0: rate=0.5) and a discovery-only Benjamini-Hochberg FDR correction added to `scripts/build_validation.py`, gated behind a `corrected_pass` flag that requires both the existing min-n gate and FDR significance.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-10T17:31Z (approx, per STATE.md session start)
- **Completed:** 2026-07-10T17:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Introduced the first hypothesis test in the validation harness: `p_value_vs_half(n, k)`, a pure-`math` two-sided z-test against the fixed H0 `rate = 0.5` (no scipy/statsmodels dependency added).
- Implemented `bh_correct(pvalues, fdr=0.05)`, a from-scratch Benjamini-Hochberg step-up correction over one global bucket family, returning rank/q-value/significance in original input order with monotone, clamped q-values.
- Wired `p_value` into every manifest row via the existing `emit()` closure, and added `apply_bh_correction()` which appends `bh_rank`, `bh_q_value`, `bh_significant`, and `corrected_pass` to discovery-manifest rows only — the correction fires at the discovery stage, never on OOS or the reconciled findings table.
- All pre-existing manifest columns (`rate`, `n`, `successes`, `ci_low`, `ci_high`, `ci_method`, `min_n_pass`, `slice`) are byte-identical in name, order, and value; new columns are strictly additive.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pure-Python significance statistic and Benjamini-Hochberg correction** - `c06573e` (test)
2. **Task 2: Wire p_value emission and discovery-only BH correction into the manifest** - `b8099b0` (feat)

_Note: Task 1 was TDD-flagged in the plan; implementation and its characterization tests were developed together and landed in a single commit (see Deviations)._

## Files Created/Modified
- `scripts/build_validation.py` - Added `p_value_vs_half()`, `bh_correct()`, `apply_bh_correction()`; wired `p_value` into `emit()`; gated `apply_bh_correction()` call in `main()` to `slice_label == "discovery"`.
- `tests/test_validation_harness.py` - Added known-value tests for `p_value_vs_half` and `bh_correct`, a wiring test confirming every emitted row carries `p_value`, an additive-schema-lock test, and `apply_bh_correction` tests covering the corrected-pass gate and the n<1 family-exclusion default.

## Decisions Made
- Used a normal-approximation z-test (`z = (2k-n)/sqrt(n)`, two-sided `p = erfc(|z|/sqrt(2))`) for `p_value_vs_half`, per the plan's "Claude's discretion" clause — pure-`math`, no new dependency, matches `wilson_ci`'s erfinv/erfc style.
- `apply_bh_correction` defines the BH family as every row with `n >= 1`; rows with `n < 1` (never actually emitted by `emit()` in practice, since n=0 buckets would still pass through, but guarded defensively) get `bh_rank=""`, `bh_q_value=""`, `bh_significant=False`, `corrected_pass=False` rather than being included in the correction.
- `corrected_pass` intentionally requires both `min_n_pass` and `bh_significant` (AND, not OR) — this is the "harder evidence bar" the phase is named for.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Documentation of new p_value column in `build_manifest_rows` docstring**
- **Found during:** Task 2
- **Issue:** The plan's acceptance criteria didn't explicitly require updating `build_manifest_rows`'s docstring, but leaving the "Columns:" list stale after adding `p_value` would misdocument the function.
- **Fix:** Updated the docstring's column list and added a note pointing to `apply_bh_correction()` for the BH-correction columns.
- **Files modified:** scripts/build_validation.py
- **Verification:** Docstring-only change; full test suite for this file still passes.
- **Committed in:** b8099b0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical / documentation accuracy)
**Impact on plan:** Documentation-only; no behavior change, no scope creep.

**Process note (not a deviation, informational):** Task 1 was marked `tdd="true"` in the plan. Per the plan's own `<action>` instructions, the tests were written as known-value characterization tests encoding the `<behavior>` block's cases directly (not a strict fail-first RED gate against not-yet-written functions), and the implementation + its tests landed together in commit `c06573e` rather than as separate RED/GREEN commits. All behavior-block cases are covered and pass.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `p_value`, `bh_rank`, `bh_q_value`, `bh_significant`, and `corrected_pass` are available on `validation_manifest_discovery.csv` for any future re-run of `python3 scripts/build_validation.py`.
- Phase 6 Plan 2 (walk-forward validation, per the roadmap/context D-04–D-07) can proceed independently — it operates on the same file (`scripts/build_validation.py`) but touches the discovery-slice fold logic, not the BH correction path.
- Phase 7's corrected re-validation of `post_cisd_context` and `candle1_followthrough` can now read `corrected_pass` as the harder evidence bar, once the harness is re-run against real data (not part of this plan's scope — no data regeneration was performed here; only the pure functions and wiring were added/tested with mocked/synthetic inputs per the plan's TDD/unit-test scope).

---
*Phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: scripts/build_validation.py
- FOUND: tests/test_validation_harness.py
- FOUND: .planning/phases/06-harder-evidence-bar-multiple-comparisons-correction-walk-for/06-01-SUMMARY.md
- FOUND commit: c06573e
- FOUND commit: b8099b0
- FOUND commit: 2a8069e
