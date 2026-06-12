---
phase: 02-validation-harness
verified: 2026-06-12T11:46:29Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 2: Validation Harness — Verification Report

**Phase Goal:** Every reported rate can be gated by sample size, carries a confidence interval, and lives inside a sacred discovery/OOS holdout that the tooling defaults to keeping sacred.
**Verified:** 2026-06-12T11:46:29Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Chronological date holdout splits history into discovery (~70%) and OOS (~30%); discovery runs operate on train slice only | VERIFIED | `OOS_START = "2024-04-30"` in `cisd_analysis.py:72` (70th-percentile of 1627-bar shared NQ/ES calendar, idx=1138). `slice_df(df, oos=False)` returns `df[df.index < OOS_START].copy()`. Tests lock partition and boundary. |
| 2 | OOS confirmation is a separate, deliberate, single-evaluation path; default run path is discovery-on-train | VERIFIED | `build_validation.py` is a separate entry point from `cisd_analysis.py`. Default `args.oos=False`. `--oos` flag required. Loud ASCII banner prints before any data load. `cisd_analysis.py` main() has no OOS path — no slicing, no `OOS_START` reference beyond the constant definition. |
| 3 | Every reported barrier/hit rate carries a binomial confidence interval | VERIFIED | `wilson_ci(n, k)` computed in `emit()` inner function of `build_manifest_rows` for every bucket across all 14 analysis types. Manifest rows carry `ci_low`, `ci_high`, `ci_method="wilson"`. Spot-check: `wilson_ci(100, 60) = (0.5020, 0.6906)` — correct. |
| 4 | Buckets below minimum-n threshold are flagged rather than reported as findings | VERIFIED | `n_gate(n) -> bool` returns `True` iff `n >= 50`. Every manifest row has `min_n_pass = n_gate(n)`. Rows with `n < 50` have `min_n_pass=False` and are never dropped. `test_build_manifest_below_min_n_flagged_not_dropped` locks this. |
| 5 | A results manifest records n, confidence interval, and IS/OOS status for each reported bucket | VERIFIED | `build_manifest_rows` produces 13-column tidy rows: `analysis, timeframe, instrument, direction, bucket, rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice`. `slice` is `"discovery"` or `"oos"`. Written to `output/validation_manifest.csv`. `test_build_manifest_rows_schema` verifies all 13 columns. |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/build_validation.py` | Harness entry point with `wilson_ci`, `n_gate`, `build_manifest_rows`, `slice_df`, discovery/OOS flag | VERIFIED | 285-line file exists; all four functions present and substantive; wired into `main()`; imports `OOS_START`, `MIN_N`, `CI_LEVEL` from `cisd_analysis`. |
| `tests/test_validation_harness.py` | 14 data-free tests covering slicing contract, Wilson CI formula, n-gate boundary, manifest schema | VERIFIED | 203-line file; 14 tests confirmed by test run (14 PASSED, 0.90s). |
| `cisd_analysis.py` (modified) | `OOS_START`, `MIN_N`, `CI_LEVEL` constants at module level, no other changes | VERIFIED | Lines 72-74 contain all three constants; no existing compute path altered (additive only). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cisd_analysis.OOS_START` | `build_validation.slice_df` | `pd.Timestamp(OOS_START)` boundary on DatetimeIndex | WIRED | `boundary = pd.Timestamp(OOS_START)` at line 211 of `build_validation.py`; used in both discovery and OOS branches. |
| `slice_df` | `main()` default path | `args.oos` flag controlling slice direction | WIRED | `nq_sl = slice_df(df_nq, oos=args.oos)` / `es_sl = slice_df(df_es, oos=args.oos)` at lines 259-260; `args.oos` defaults to `False`. |
| `compute_*` nested-dict output | `build_manifest_rows` | Key-dispatch block extracting `total/runs` (or `held` for `fvg_hold`) | WIRED | 14-branch dispatch at lines 143-195; covers all 14 `ANALYSES` keys; each branch calls `emit(key, instrument, direction, bucket, n, k)`. |
| `wilson_ci(n, k)` | every manifest row | `emit()` inner function calling `wilson_ci` | WIRED | `lo, hi = wilson_ci(n, k)` at line 116; `ci_low`/`ci_high` in every emitted row. |
| `build_manifest_rows` | `output/validation_manifest.csv` | `pd.DataFrame(manifest_rows).to_csv(MANIFEST_PATH, index=False)` | WIRED | Line 279 of `build_validation.py`; `MANIFEST_PATH` defined at line 22. |

---

## Data-Flow Trace (Level 4)

`build_manifest_rows` does not render dynamic data from a DB/fetch — it consumes return values from in-process `compute_*` functions. The functions are called live with the sliced DataFrame and return real barrier counts. No static/hardcoded returns. Data-flow is: `parquet -> load_1m -> prepare_pair -> slice_df -> compute_* -> emit -> CSV row`. No hollow props or disconnected state variables.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `build_manifest_rows` | `total`, `runs`/`held` | `compute_*(df)` called on sliced enriched DataFrame | Yes — real barrier counts from OHLCV data | FLOWING |
| `slice_df` | DatetimeIndex slice | `OOS_START` constant + DataFrame index | Yes — deterministic partition on real timestamps | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `wilson_ci(100, 60)` returns correct Wilson CI | `python3 -c "from scripts.build_validation import wilson_ci; print(wilson_ci(100,60))"` | `(0.5020, 0.6906)` — within expected range [0.495-0.510] × [0.685-0.705] | PASS |
| `n_gate` boundary at MIN_N=50 | `python3 -c "from scripts.build_validation import n_gate; print(n_gate(49), n_gate(50), n_gate(51))"` | `False True True` | PASS |
| `wilson_ci(0, 0)` sentinel | `python3 -c "from scripts.build_validation import wilson_ci; print(wilson_ci(0,0))"` | `(0.0, 0.0)` | PASS |
| Constants importable from `cisd_analysis` | `python3 -c "import cisd_analysis; print(cisd_analysis.OOS_START, cisd_analysis.MIN_N, cisd_analysis.CI_LEVEL)"` | `2024-04-30 50 0.95` | PASS |

---

## Probe Execution

No probe scripts declared in PLAN files for this phase. Step 7c: SKIPPED (no `scripts/*/tests/probe-*.sh` convention used).

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| VALID-01 | 02-01 | Sacred date holdout, ~70%/~30% split | SATISFIED | `OOS_START`, `slice_df`, slicing tests |
| VALID-02 | 02-01 | OOS is separate deliberate path; default is discovery-on-train | SATISFIED | `--oos` flag, sacred banner, no OOS in `cisd_analysis.py` main() |
| VALID-03 | 02-02 | Every reported rate carries binomial CI | SATISFIED | `wilson_ci` in `build_manifest_rows`, `ci_low`/`ci_high` in all manifest rows |
| VALID-04 | 02-02 | Rates are sample-size gated; below-n buckets flagged/suppressed | SATISFIED | `n_gate`, `min_n_pass` flag on every row, never dropped |
| VALID-05 | 02-02 | Results manifest records n, CI, IS/OOS status | SATISFIED | 13-column `validation_manifest.csv` with `n`, `ci_low`, `ci_high`, `slice` |

**Note:** `REQUIREMENTS.md` checkboxes for VALID-01 through VALID-05 remain `[ ]` (unchecked), while Phase 1 requirements show `[x]`. This is a documentation tracking oversight — the implementations are complete and verified. The status table in REQUIREMENTS.md also still shows these as "Pending." Updating to `[x]` is a housekeeping task.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No debt markers (TBD/FIXME/XXX), no stubs, no placeholders found in `scripts/build_validation.py` or `tests/test_validation_harness.py`. |

---

## Human Verification Required

None. All success criteria are fully verifiable from the codebase and test suite. No visual rendering, real-time behavior, or external service integration is involved in this phase.

---

## Commits

All 6 phase commits verified as present and correctly attributed:

| Commit | Message | Files |
|--------|---------|-------|
| `d132558` | feat(02-01): add OOS_START, MIN_N, CI_LEVEL constants | `cisd_analysis.py` |
| `2f78bbc` | feat(02-01): create scripts/build_validation.py with discovery/OOS slicing | `scripts/build_validation.py` |
| `ee13c84` | test(02-01): add data-free unit tests for holdout slicing contract | `tests/test_validation_harness.py` |
| `f98916c` | feat(02-02): implement wilson_ci and n_gate in pure stdlib math | `scripts/build_validation.py` |
| `0b980b1` | feat(02-02): implement build_manifest_rows and manifest CSV | `scripts/build_validation.py` |
| `cb0592b` | test(02-02): add 8 unit tests for Wilson CI, n_gate, and manifest schema | `tests/test_validation_harness.py` |

---

## Test Results

```
tests/test_validation_harness.py::test_slice_df_partition           PASSED
tests/test_validation_harness.py::test_slice_df_no_overlap          PASSED
tests/test_validation_harness.py::test_slice_df_all_discovery       PASSED
tests/test_validation_harness.py::test_slice_df_all_oos             PASSED
tests/test_validation_harness.py::test_slice_df_returns_copy        PASSED
tests/test_validation_harness.py::test_oos_start_and_constants      PASSED
tests/test_validation_harness.py::test_wilson_ci_known_value        PASSED
tests/test_validation_harness.py::test_wilson_ci_zero_n             PASSED
tests/test_validation_harness.py::test_wilson_ci_all_successes      PASSED
tests/test_validation_harness.py::test_wilson_ci_small_n            PASSED
tests/test_validation_harness.py::test_wilson_ci_bounds_in_unit_interval PASSED
tests/test_validation_harness.py::test_n_gate_boundary              PASSED
tests/test_validation_harness.py::test_build_manifest_rows_schema   PASSED
tests/test_validation_harness.py::test_build_manifest_below_min_n_flagged_not_dropped PASSED

14 passed in 0.90s
```

---

## Gaps Summary

No gaps. All 5 success criteria are achieved by concrete, tested, wired implementations. The only note is a documentation housekeeping item (REQUIREMENTS.md checkboxes), which does not affect phase goal achievement.

---

_Verified: 2026-06-12T11:46:29Z_
_Verifier: Claude (gsd-verifier)_
