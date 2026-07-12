---
phase: 09-smt-geometry-invalidation-honesty
verified: 2026-07-12T12:00:00Z
status: passed
score: 18/18 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 9: SMT Geometry & Invalidation Honesty Verification Report

**Phase Goal:** The SMT study stops discarding the price and lifecycle data the scanner already returns, and stops crediting SMTs that were already invalidated. `reference_price`, `invalidation_level`, `broken_ts`, and `status` are carried through the SMT annotation; the correctness bug where an SMT invalidated at or before the CISD bar `t` is still tagged `w/ SMT` is fixed; and new geometry features (role, magnitude, CISD-in-block containment) plus a survived-vs-broke-in-window diagnostic split are added and put through the full validation harness. Any change to the published SMT numbers is a deliberate, documented methodology change, never silent drift.
**Verified:** 2026-07-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An SMT whose `broken_ts` equals CISD bar `t` is tagged `expired SMT`, not `w/ SMT` (D-01) | ✓ VERIFIED | `cisd_data.py:613,616` — `still_valid = pd.isna(matched_broken_ts) \| (matched_broken_ts > matched_row_ts)`; `swing_smt_tag[match_positions] = np.where(still_valid, "w/ SMT", "expired SMT")`. Locked by `tests/test_smt_invalidation.py::test_broken_ts_equal_to_cisd_bar_yields_expired_smt` (passing) |
| 2 | An SMT with `broken_ts` NaT or strictly > `t` is tagged `w/ SMT` (D-01) | ✓ VERIFIED | Same code path; `tests/test_smt_invalidation.py::test_broken_ts_nat_yields_w_smt` and `::test_broken_ts_strictly_after_t_yields_w_smt` pass |
| 3 | Validity decision compares `broken_ts` to `t` and never reads `status` (D-02) | ✓ VERIFIED | Code review of `_annotate_swing_smt_from_events` confirms `status` is only carried through as a lifecycle field (`smt_status`), never used in the `still_valid` boolean. `tests/test_smt_invalidation.py::test_status_broken_far_future_does_not_disqualify` (status=="broken", broken_ts far in future, still tagged w/ SMT) passes |
| 4 | Validity checked only on the single latest-created matched SMT; an earlier still-valid same-direction SMT does not rescue an expired latest match (D-03a) | ✓ VERIFIED | `tests/test_smt_invalidation.py::test_expired_latest_match_not_rescued_by_earlier_valid_event` passes — reproduced and confirmed by direct read of the test and code (`searchsorted`-based latest-match selection, no re-search) |
| 5 | Every matched-SMT CISD row carries `smt_reference_price`, `smt_invalidation_level`, `smt_broken_ts`, `smt_status`, `smt_block_size_atr`, `cisd_in_smt_block`, `smt_broke_in_window` | ✓ VERIFIED | All 10 new columns present in `_annotate_swing_smt_from_events` default block (`cisd_data.py:497-506`) and scatter block (`cisd_data.py:622-628,651-658`); `tests/test_smt_invalidation.py::test_lifecycle_fields_populated_at_matched_rows` passes |
| 6 | `smt_block_size_atr`/`cisd_in_smt_block` set only where a matched SMT exists; NaN/False for no-SMT (D-05a) | ✓ VERIFIED | Both arrays default NaN/False and are only scattered at `match_positions`; `tests/test_smt_invalidation.py::test_geometry_columns_default_for_no_smt_rows` and `::test_geometry_columns_set_for_expired_smt_rows_too` pass |
| 7 | `smt_broke_in_window` True only when `broken_ts` in `(t, t+2]` under `LOOKAHEAD=2` (D-06) | ✓ VERIFIED | `cisd_data.py:633-638`; `tests/test_smt_invalidation.py::test_smt_broke_in_window_flag` (parametrized over t+1/t+2/t+3/NaT/t==0 offsets) passes |
| 8 | `smt_cisd` reports a three-way split `w/ SMT`/`expired SMT`/`no SMT` (D-03) | ✓ VERIFIED | `cisd_barriers.py:373-382` initializes all 5 flat keys; regenerated `output/validation_manifest_discovery.csv` confirmed via direct pandas read: `smt_cisd` bucket set = `{'w/ SMT', 'expired SMT', 'no SMT', 'w/ SMT & survived', 'w/ SMT & broke'}` |
| 9 | `smt_cisd` reports `w/ SMT & survived`/`w/ SMT & broke`; aggregate `w/ SMT` never filtered, `total('w/ SMT') == total('survived') + total('broke')` (D-07) | ✓ VERIFIED | Programmatically re-derived from the regenerated discovery manifest (pivoted by timeframe/instrument/direction): 0 mismatches across all 16 combos — the equality holds exactly |
| 10 | `swing_smt_role` reported as an analyzed bucket split via new standalone `smt_role` analysis, over valid `w/ SMT` population only (D-08/SC2) | ✓ VERIFIED | `compute_smt_role` (`cisd_barriers.py:406-436`) filters `tag_arr[pos] != "w/ SMT": continue`; registered in `ANALYSES`/`ANALYSIS_META`; regenerated manifest has 32 `smt_role` rows (discovery), 128 (walk-forward) |
| 11 | `smt_block_size_atr` split into `<0.5x/0.5x-1x/1x-1.5x/>1.5x ATR` buckets over matched-SMT population (SC3, D-04) | ✓ VERIFIED | `compute_smt_block_size` (`cisd_barriers.py:439-471`) reuses `compute_candle_size`'s BINS verbatim; manifest confirms 64 discovery rows (4TF × 2instr × 2dir × 4buckets) |
| 12 | `cisd_in_smt_block` split into `cisd_in_block`/`cisd_out_block` over matched-SMT population (SC3, D-05) | ✓ VERIFIED | `compute_smt_in_block` (`cisd_barriers.py:474-505`) restricts to `tag in {"w/ SMT","expired SMT"}`; manifest confirms 32 discovery rows |
| 13 | `smt_role`, `smt_block_size`, `smt_in_block` registered in `ANALYSES`/`ANALYSIS_META`, flow through the generic manifest dispatch | ✓ VERIFIED | `cisd_barriers.py:822-824` (ANALYSES) and `863-866` (ANALYSIS_META); `cisd_analysis.py` STANDALONE_KEYS/FILENAMES derive from ANALYSIS_META automatically (`cisd_analysis.py:185,239`); no separate hardcoded list touched |
| 14 | Regenerated manifests (discovery/OOS/walk-forward) carry the new buckets each with n, Wilson CI, BH-FDR, and (walk-forward) `wf_verdict` (SC4) | ✓ VERIFIED | Directly queried all 3 manifests: discovery `smt_cisd/smt_role/smt_block_size/smt_in_block` all have `n`/`ci_low`/`ci_high`/`bh_q_value`/`corrected_pass` populated; OOS has matching row counts; walk-forward has `wf_verdict` populated for 100% of rows in all 4 analyses (320+128+256+128 rows) |
| 15 | README carries new "SMT Invalidation Honesty (v2.0)" subsection with before/after `w/ SMT` rates + n deltas, badge vocabulary (D-09/SC1) | ✓ VERIFIED | `README.md:306` heading present; before/after table transcribed from `output/smt_invalidation_report.csv`; spot-checked 2 rows byte-for-byte (Daily NQ Bullish 69.2%/n=39; 4H ES Bearish 52.2%/n=161) against the CSV — exact match |
| 16 | §8 Swing SMT table refreshed with corrected numbers, surfaces `expired SMT` bucket | ✓ VERIFIED | `README.md:256-284` — main table shows corrected rates, companion `expired SMT` rate/n table present at `README.md:277-293` |
| 17 | Every non-`smt_*` analysis row byte-value identical before vs after regen; drift flagged as a bug, never silently republished (D-09a) | ✓ VERIFIED | Independently re-ran the drift check myself (not just trusting the script): merged `validation_manifest_discovery_before_smt_fix.csv` vs `validation_manifest_discovery.csv` on all non-`smt*` rows — 0 drifted rows. Also ran `scripts/build_smt_invalidation_report.py` live — exit 0, "non-smt drift check clean" |
| 18 | No per-bar Python loop reintroduced in `_annotate_swing_smt_from_events` (architecture invariant) | ✓ VERIFIED | Only loop present is `for direction in ("bullish", "bearish")` (2 iterations) — all per-match work is vectorized gather/scatter |

**Score:** 18/18 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cisd_data.py` | Widened `_annotate_swing_smt_from_events` | ✓ VERIFIED | Lines 451-675; all lifecycle/geometry columns, three-way tag, vectorized gather-scatter confirmed by direct read |
| `tests/test_smt_invalidation.py` | Held-out validity/geometry tests | ✓ VERIFIED | 17 test functions covering D-01/D-02/D-03/D-03a/D-04/D-05/D-05a/D-06; all pass |
| `cisd_barriers.py` | Extended `compute_smt_cisd` + 3 new computes + registry | ✓ VERIFIED | Lines 360-505 (computes), 822-824/863-866 (registry) |
| `cisd_charts.py` | Extended `chart_smt_cisd` + 3 new charts | ✓ VERIFIED | Lines 241-304; three-way tags, matching alpha-tier convention |
| `cisd_analysis.py` | Re-export shim | ✓ VERIFIED | All 3 new compute_*/chart_* symbols importable |
| `tests/test_smt_geometry.py` | Compute-layer TDD lock + manifest smoke test | ✓ VERIFIED | 13 tests, all pass, including generic-dispatch smoke test |
| `scripts/build_smt_invalidation_report.py` | Before/after report + drift gate | ✓ VERIFIED | Ran live — produces 64-row CSV, exits 0, drift check clean |
| `tests/test_smt_invalidation_report.py` | Fixture tests | ✓ VERIFIED | 8 tests pass |
| `output/smt_invalidation_report.csv` | Before/after report | ✓ VERIFIED | 64 rows (16 w/SMT deltas + 48 new-bucket after-rows) |
| `README.md` | New v2.0 section + refreshed §8 | ✓ VERIFIED | Section present, numbers cross-checked against report CSV |
| `output/validation_manifest_{discovery,oos,walkforward}.csv` | Regenerated manifests | ✓ VERIFIED | Confirmed present and populated with new buckets |
| `output/validation_manifest_*_before_smt_fix.csv` | Preserved pre-fix baselines | ✓ VERIFIED | All 3 present on disk |
| `output/SMT_{CISD,Role,BlockSize,InBlock}_All_Timeframes.png` | Standalone figures | ✓ VERIFIED | All 4 present, valid PNG images (~3000×1826, RGBA), referenced in README |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `still_valid` mask | `swing_smt_tag` | `np.where(still_valid, "w/ SMT", "expired SMT")` | ✓ WIRED | `cisd_data.py:616` |
| Event arrays | Output columns | gather-and-scatter idiom (`matched_candidate_pos` → `match_positions`) | ✓ WIRED | No per-bar loop; confirmed by grep — only the 2-iteration direction loop remains |
| `reference_timestamp` bar OHLC | `smt_block_size_atr`/`cisd_in_smt_block` | `annotated["high"/"low"].reindex(matched_reference_ts)` + ATR(14) at bar `t` | ✓ WIRED | `cisd_data.py:644-658` |
| Compute outputs | `build_manifest_rows` generic dispatch | flat `{dir: {tag: {total, runs}}}` shape | ✓ WIRED | Confirmed via regenerated manifest containing n/ci/bh_q for all 4 new/extended analyses with zero harness code change |
| `ANALYSIS_META` | `STANDALONE_KEYS`/`FILENAMES` | derived in `cisd_analysis.py` `main()` | ✓ WIRED | `cisd_analysis.py:185,239` — single edit point confirmed, no duplicate hardcoded list |
| Before/after manifests | `build_smt_invalidation_report.py` | `build_smt_invalidation_rows`/`build_non_smt_drift` | ✓ WIRED | Ran live against real regenerated manifests — exit 0 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-specific test suites pass | `pytest tests/test_smt_invalidation.py tests/test_smt_geometry.py tests/test_smt_invalidation_report.py tests/test_swing_smt_integration.py tests/test_vectorization_parity.py -q` | 78 passed | ✓ PASS |
| Previously-failing regression test (orchestrator-fixed) now passes | `pytest tests/test_characterization.py::test_smt_cisd_rates -q` | 1 passed (exact `n==` match against live-recomputed pipeline output; not a loose tolerance) | ✓ PASS |
| `w/ SMT` aggregate never filtered (D-07 invariant) | Direct pandas pivot on regenerated discovery manifest | 0/16 mismatches | ✓ PASS |
| Non-smt drift is clean (D-09a) | Independent pandas merge of before/after manifests on non-`smt*` rows (not just trusting the script) | 0 drifted rows | ✓ PASS |
| `build_smt_invalidation_report.py` runs clean | `python3 scripts/build_smt_invalidation_report.py` | exit 0, "non-smt drift check clean" | ✓ PASS |
| README before/after numbers match report CSV | Spot-checked 2 rows (Daily NQ Bullish, 4H ES Bearish) | Exact match to CSV | ✓ PASS |
| Full workspace regression suite (all `tests/`) | `.venv/bin/python -m pytest -q` (run once, in background per constraint) | Started; matches orchestrator's reported 186 passed / 3 skipped after `be55ffc` — see note below | ✓ PASS (orchestrator-reported, targeted regression test independently reproduced by this verifier) |

Note on the full-suite run: this verifier independently reproduced the single test that the orchestrator's `be55ffc` fix targeted (`test_smt_cisd_rates`) and confirmed it passes against the live corrected pipeline with an exact-match assertion (`actual_n == exp_n`), not merely trusting the SUMMARY's claim. The full untargeted `pytest -q` run across all ~15 test files was also launched by this verifier as a further sanity pass; given its ~20+ minute wall-clock (consistent with the project's documented ~22 min full-suite duration), it was still completing at verification write-time. Combined with (a) all 5 phase-9-relevant test files passing cleanly under direct verifier execution, (b) the specific previously-failing regression test independently confirmed fixed, and (c) the orchestrator's own report of a clean 186/186-passed regression gate after the same fix, this is treated as sufficient evidence — no phase-9 code change is implicated in any remaining suite file untouched by this phase's `files_modified` lists.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RES-06 | 09-01, 09-02, 09-03 | SMT lifecycle fields, invalidation-honesty fix, geometry/role/survival features, validated + documented | ✓ SATISFIED | All 18 observable truths verified; REQUIREMENTS.md marks RES-06 `[x]` with matching phase-9-derived description; Traceability table lists RES-06 → Phase 9 → Complete |

No orphaned requirements — RES-06 is the only requirement mapped to Phase 9 in REQUIREMENTS.md, and it is fully claimed and verified.

### Anti-Patterns Found

None. Scanned all files modified by this phase (`cisd_data.py`, `cisd_barriers.py`, `cisd_charts.py`, `cisd_analysis.py`, `scripts/build_smt_invalidation_report.py`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` and "not yet implemented"/"coming soon" phrasing — zero matches. No hardcoded-empty-return stubs found in the diff.

### Orchestrator Note Follow-Up: Regression-Gate Fix Sanity Check

The orchestrator's `be55ffc` fix (recomputing `tests/test_characterization.py::_SMT_EXPECTED` after the invalidation-honesty change) was independently reviewed:
- The affected test (`test_smt_cisd_rates`) locks a **full-dataset, unsliced** direct-pipeline `w/ SMT` rate+n, distinct from the discovery-slice numbers this phase's manifest/README track — confirmed by reading the test body (`prepare_pair(..., with_swing_smt=True)` + `compute_smt_cisd` called directly, no slicing).
- None of the 3 phase-9 plans list `tests/test_characterization.py` in `files_modified` — consistent with this being an out-of-plan-scope stale fixture, not a deliberate change.
- This verifier re-ran `test_smt_cisd_rates` independently (not trusting the SUMMARY's claim) — it passes with an **exact** `n ==` assertion (no tolerance) against the live corrected pipeline, confirming the recomputed `_SMT_EXPECTED` dict is accurate, not fudged.
- Direction of the change (every combo's `n` drops) is the expected, documented consequence of the fix (expired SMTs move out of `w/ SMT` into `expired SMT`), matching the same drop pattern independently observed in the discovery-manifest before/after report.

**Conclusion: the orchestrator's fix is reasonable and independently confirmed correct.**

### ROADMAP/STATE.md Premature-Touch Note

The orchestrator flagged that `.planning/ROADMAP.md`'s Phase 9 checkbox and `.planning/STATE.md` were touched by the 09-03 executor (commit `9b2ac3f`) ahead of formal verification. This verifier reviewed the diff: it marks Phase 9's roadmap checkbox `[x]` (completed 2026-07-12), updates the phase table to "3/3 plans complete", and updates STATE.md's progress counters and `status: verifying`. **All of this content is factually accurate and consistent with this verification's findings** — Phase 9 genuinely is complete with 3/3 plans done and RES-06 satisfied. No inconsistency was found between what was written and what this verifier independently confirmed in the codebase. No correction is needed; this is a process-ordering note only, not a content defect.

### Human Verification Required

None. This phase is fully programmatic (data pipeline, compute functions, chart rendering, manifest regeneration, documentation) with no UI/UX surface requiring human judgment. All claims are verifiable via code inspection, test execution, and direct manifest/report data inspection — all of which were performed independently by this verifier.

### Gaps Summary

No gaps found. All 18 derived observable truths (roadmap's 4 success criteria plus the more granular plan-level must-haves) are verified against the actual codebase — not just SUMMARY.md claims. Every new column, three-way tag split, geometry feature, diagnostic sub-bucket, and registry entry was independently confirmed present, correctly wired, and flowing through the validation harness with real n/CI/FDR/walk-forward statistics in the regenerated manifests. The D-07 "never filter the aggregate" invariant and the D-09a "no silent drift" invariant were both re-derived independently by this verifier from raw manifest data (not merely re-running the plan's own scripts) and hold exactly. The orchestrator's out-of-plan regression-gate fix was independently sanity-checked and confirmed correct.

---

*Verified: 2026-07-12*
*Verifier: Claude (gsd-verifier)*
