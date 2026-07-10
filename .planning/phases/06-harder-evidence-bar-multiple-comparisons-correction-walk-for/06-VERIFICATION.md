---
phase: 06-harder-evidence-bar-multiple-comparisons-correction-walk-for
verified: 2026-07-10T19:50:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Characterization/unit tests cover the new math and the full pre-existing test suite still passes green (ROADMAP success criterion 4)"
    status: resolved
    reason: >
      The new significance/FDR/walk-forward math IS covered by characterization
      tests (51 tests in tests/test_validation_harness.py + tests/test_reconcile_findings.py,
      all passing). The full pre-existing suite initially failed (2 failed, 160
      passed in 1605.34s): two pre-existing Phase-5 tests in
      tests/test_research_extensions.py asserted an EXACT column-set equality
      (`set(row.keys()) == expected_columns`) that did not include the new
      additive `p_value` column emitted by build_manifest_rows() on every row.
      RESOLVED (commit 8d43e68, applied via Codex rescue at the user's request,
      bypassing the formal gap-closure plan cycle): both assertions were
      updated from exact-set equality to a missing-columns subset check
      (`missing = expected_columns - row.keys(); assert not missing`), mirroring
      the already-correct pattern in
      tests/test_validation_harness.py::test_build_manifest_rows_schema_still_subset_after_p_value.
      No production code was touched. Full suite re-run after the fix:
      162 passed in 2041.80s (0:34:01) — 0 failures.
    artifacts:
      - path: "tests/test_research_extensions.py"
        issue: >
          RESOLVED — test_build_manifest_rows_candle1_followthrough_has_tidy_long_columns
          (line 648) and test_build_manifest_rows_post_cisd_context_has_tidy_long_columns
          (line 973) now assert a subset check tolerant of the additive
          `p_value` column instead of exact set equality (commit 8d43e68).
    missing: []
---

# Phase 6: Harder Evidence Bar — Multiple-Comparisons Correction & Walk-Forward Validation Verification Report

**Phase Goal:** The validation harness measures every edge against a harder, honest bar — a bucket's "confirmed" status accounts for how many buckets were tested (FDR control across the full grid), and its robustness is re-confirmed across multiple sequential walk-forward windows rather than a single fixed split. The new methodology is additive/parallel; existing published numbers do not move.
**Verified:** 2026-07-10T19:50:00Z
**Status:** passed
**Re-verification:** No — initial verification; gap resolved directly post-verification (see Truth #7 and Gaps Summary)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Discovery manifest carries a multiple-comparisons-corrected column set (p_value, bh_rank, bh_q_value, bh_significant, corrected_pass) computed across the full bucket grid in one global family (ROADMAP SC1) | ✓ VERIFIED | Real `python3 scripts/build_validation.py` run produced `output/validation_manifest_discovery.csv` (912 rows, 18 columns) with all 5 new columns present. One global family of 912 rows (all n≥1); bh_q_value monotone non-decreasing along ascending p_value (confirmed programmatically); bh_rank spans 1..912 (whole family, not per-analysis); 0 rows violate `corrected_pass == (min_n_pass AND bh_significant)`. bh_significant: 734 True / 178 False; corrected_pass: 674 True / 238 False. |
| 2 | Running the harness produces walk-forward output: per-window pass/fail plus an aggregate walk-forward robustness verdict (ROADMAP SC2) | ✓ VERIFIED | Real `python3 scripts/build_validation.py --walk-forward` run produced `output/validation_manifest_walkforward.csv` (3648 rows = 912 buckets × 4 folds, 14 columns: fold_index, train_end, test_end, train_rate/n, test_rate/n, fold_verdict, wf_verdict). fold_verdict counts: pass 2170 / below-n 1326 / fail 152. Every bucket has exactly one consistent wf_verdict across its 4 fold rows (0 inconsistencies, confirmed programmatically). wf_verdict counts: wf-robust 2104 / wf-fragile 1544. |
| 3 | The FDR correction fires at the discovery stage only — an --oos run carries p_value but no bh_* columns; the reconciler is unaffected | ✓ VERIFIED | Code: `apply_bh_correction(manifest_rows)` is called in `main()` only inside `if slice_label == "discovery":` (grep-confirmed at scripts/build_validation.py:703-704); build_manifest_rows emits `p_value` unconditionally for every slice. Unit tests confirm the wiring (`test_apply_bh_correction_...`, `test_build_manifest_rows_emits_p_value`). Real run: reconciler (`scripts/build_reconcile_findings.py`) executed successfully against the new additive discovery manifest, writing 912 rows (611 confirmed / 201 not-confirmed / 100 below-n) with no errors. A live `--oos` re-run was intentionally NOT performed to avoid spending the project's one sacred OOS evaluation on a verification pass — the discovery-only gate is fully evidenced by source code + passing unit tests instead. |
| 4 | Existing discovery/OOS manifest columns (rate, n, successes, ci_low, ci_high, ci_method, min_n_pass, slice) are unchanged in name, order, and value; new results are additive columns/artifacts (ROADMAP SC3) | ✓ VERIFIED | Diffed the freshly-generated `validation_manifest_discovery.csv` against a pre-phase-6 backup (Jun 13 snapshot). All 8 pre-existing columns are byte-identical for all 752 pre-existing (analysis, timeframe, instrument, direction, bucket) rows — 0 mismatches. The 160 additional rows in the new file belong to `candle1_followthrough`/`post_cisd_context` — analyses added in Phase 5 (commits 1186417, 5b8b2b4, both before Phase 6), not new output from this phase. File mtimes confirm the `--walk-forward` run did not rewrite `validation_manifest_discovery.csv` or `validation_manifest_oos.csv` (their timestamps predate the walk-forward run). |
| 5 | Every walk-forward fold is carved entirely from the discovery slice; the sacred OOS slice is never touched by walk-forward (D-04) | ✓ VERIFIED | `slice_fold()` always calls `slice_df(df, oos=False)` before sub-slicing (scripts/build_validation.py:383), clamping every fold to `df.index < OOS_START` even when `test_end` is the literal `OOS_START` value (last fold). Unit test `test_slice_fold_clamps_to_discovery_even_if_test_end_after_oos` passes. Code review (06-REVIEW.md) independently traced this by hand across all 4 fold boundaries. Real walk-forward manifest's max `test_end` value is `OOS_START` ("2024-04-30"), never beyond it. |
| 6 | Fold boundaries are frozen calendar-date constants (D-06) and windows are expanding/anchored (D-05) | ✓ VERIFIED | `WALK_FORWARD_FOLDS = ("2021-05-25", "2022-02-16", "2022-11-09", "2023-08-04")` declared in cisd_data.py with a "do not recompute at runtime" comment, re-exported through cisd_analysis.py's explicit import list + `__all__` (grep-confirmed both files). `cisd_analysis.WALK_FORWARD_FOLDS` resolves. Anchored-superset property confirmed by `test_slice_fold_anchored_superset`. |
| 7 | Characterization/unit tests cover the new math (known bucket grid → known adjusted q-values; known window schedule → known per-window splits) and the full pre-existing test suite still passes green (ROADMAP SC4) | ✓ VERIFIED (post-fix) | New-math tests exist and pass: `tests/test_validation_harness.py` (51 tests covering p_value_vs_half, bh_correct, apply_bh_correction, slice_fold, evaluate_fold, walk_forward_verdict, build_walkforward_rows — all pass, including known-value/boundary cases). The full suite initially failed (2 failed, 160 passed in 1605.34s) due to two Phase-5 tests in tests/test_research_extensions.py asserting exact column-set equality against the new additive p_value column. Fixed in commit 8d43e68 (subset-check pattern, no production code touched); full suite re-run: **162 passed in 2041.80s, 0 failures**. See Gaps Summary below. |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/build_validation.py` — `p_value_vs_half()`, `bh_correct()`, `apply_bh_correction()` | New pure-math significance/correction helpers | ✓ VERIFIED | All three defined, pure `math`-only (no scipy/statsmodels imports added), full docstrings, unit-tested with known values. |
| `scripts/build_validation.py` — `slice_fold()`, `evaluate_fold()`, `walk_forward_verdict()`, `build_walkforward_rows()` | Walk-forward fold slicing/evaluation/aggregation | ✓ VERIFIED | All four defined and wired; `build_walkforward_rows` performs no I/O itself (pure aggregation, confirmed by `test_build_walkforward_rows_never_writes_csv`). |
| `cisd_data.py` / `cisd_analysis.py` — `WALK_FORWARD_FOLDS` | Frozen 4-tuple constant, re-exported | ✓ VERIFIED | Declared in cisd_data.py `__all__`, re-exported via cisd_analysis.py's explicit import list + own `__all__`; `import cisd_analysis; cisd_analysis.WALK_FORWARD_FOLDS` resolves. |
| `output/validation_manifest_walkforward.csv` | Generated artifact | ✓ VERIFIED | Freshly generated with real data: 3648 rows, correct schema, sane verdict distributions. |
| `tests/test_validation_harness.py` | Known-value + wiring tests for new math | ✓ VERIFIED | 41 new test functions added across both plans (significance, BH correction, fold slicing, fold evaluation, aggregate verdict, walkforward-rows wiring); all pass. |
| `README.md` | Methodology section (FDR + walk-forward, additive) | ✓ VERIFIED | "## Validation Methodology — Harder Evidence Bar (v2.0)" section (line 378) documents both bh_significant/corrected_pass and wf_verdict as additive, explicitly stating no existing column/rate changes. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `emit()` closure in `build_manifest_rows` | `p_value` column | Direct dict-key append | ✓ WIRED | `"p_value": round(p_value_vs_half(n, k), 6)` present in emit()'s row dict (line 235), confirmed on every emitted row in the real discovery run. |
| `main()` | `apply_bh_correction()` | `if slice_label == "discovery":` guard | ✓ WIRED | Grep-confirmed the call is inside the discovery-only branch (line 703-704), not unconditional. |
| `slice_fold()` | `slice_df(df, oos=False)` | Discovery-region clamp | ✓ WIRED | slice_fold always restricts to discovery before sub-slicing (line 383); confirmed by test and real-data max test_end == OOS_START. |
| `main()` `--walk-forward` branch | `walk_forward_verdict()` | `build_walkforward_rows()` aggregation | ✓ WIRED | Real run produced a consistent per-bucket wf_verdict across all fold rows (0 inconsistencies). |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MHT-01 | 06-01-PLAN.md | FDR correction across full bucket grid | ✓ SATISFIED | `bh_correct`/`apply_bh_correction` implemented, tested, and verified against real data (Truth #1, #3). REQUIREMENTS.md updated to `[x]`/"Complete" (was previously left unchecked — a documentation-tracking gap, now closed). |
| WF-01 | 06-02-PLAN.md | Walk-forward validation across sequential windows | ✓ SATISFIED | REQUIREMENTS.md already reflects `[x]` Complete. Fully implemented and verified against real data (Truth #2, #5, #6). |

No orphaned requirements — REQUIREMENTS.md maps only MHT-01 and WF-01 to Phase 6, and both are declared in the two plans' `requirements:` frontmatter.

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any file modified by this phase (`scripts/build_validation.py`, `tests/test_validation_harness.py`, `cisd_data.py`, `cisd_analysis.py`).

Carried forward from `06-REVIEW.md` (code review, 0 critical / 1 warning / 3 info — none blocking the phase goal):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| scripts/build_validation.py | 626-634, 667-673 | Duplicated SMT-availability probe block in `main()` | ⚠️ Warning | Maintainability only; both branches behave correctly. |
| scripts/build_validation.py | 493-495 | Docstring ambiguity: fold-index 0- vs 1-based mapping | ℹ️ Info | Cosmetic; behavior is correct and test-covered. |
| scripts/build_validation.py | 235, 334 | BH correction operates on rounded (6dp) p-values | ℹ️ Info | Second-order precision concern only; negligible for this dataset. |
| scripts/build_validation.py | 23 | `MANIFEST_PATH` dead code (pre-existing, unrelated to this phase) | ℹ️ Info | Pre-dates Phase 6; unused legacy constant. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Discovery manifest gains FDR columns, values sane | `python3 scripts/build_validation.py` (real data, 26m15s) | 912 rows, 18 cols, monotone q-values, 0 corrected_pass-logic violations | ✓ PASS |
| Walk-forward manifest produced with correct schema | `python3 scripts/build_validation.py --walk-forward` (real data, ~52 min) | 3648 rows, 14 cols, consistent per-bucket wf_verdict | ✓ PASS |
| Existing manifest columns byte-identical pre/post phase | Diff vs. pre-phase-6 backup (752 shared rows) | 0 mismatches on rate/n/successes/ci_low/ci_high/ci_method/min_n_pass/slice | ✓ PASS |
| Walk-forward run does not touch discovery/oos manifests | File mtime comparison | discovery.csv/oos.csv mtimes predate the walk-forward run's writes | ✓ PASS |
| Reconciler unaffected by additive columns (real run, not just unit test) | `python3 scripts/build_reconcile_findings.py` | 912 rows written (611 confirmed / 201 not-confirmed / 100 below-n), no errors | ✓ PASS |
| `--help` lists `--walk-forward` | `python3 scripts/build_validation.py --help` | Flag listed with correct help text and `--oos` precedence note | ✓ PASS |
| Full pre-existing test suite green (ROADMAP SC4) | `.venv/bin/python -m pytest tests/ -q` (26m45s, then re-run after fix in 34m01s) | Initial: **2 failed, 160 passed**. Post-fix (commit 8d43e68): **162 passed, 0 failed** | ✓ PASS |

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` convention exists in this project and neither PLAN nor SUMMARY references probes. Step 7c: SKIPPED (no runnable probe entry points).

### Human Verification Required

None. All must-haves are objectively verifiable via code inspection, unit tests, and real-data execution — no visual, UX, or subjective-judgment components in this phase.

### Gaps Summary

**One regression found, since resolved.** The full pre-existing test suite (`tests/`) was initially not green: `.venv/bin/python -m pytest tests/ -q` produced **2 failed, 160 passed** (1605.34s):

- `tests/test_research_extensions.py::test_build_manifest_rows_candle1_followthrough_has_tidy_long_columns`
- `tests/test_research_extensions.py::test_build_manifest_rows_post_cisd_context_has_tidy_long_columns`

Both are pre-existing Phase-5 tests (authored 2026-06-14, before Phase 6 began) that asserted `set(row.keys()) == expected_columns` — an exact column-set equality that did not include `p_value`. Phase 6 intentionally (and correctly, per its own must-haves) added `p_value` to every emitted row regardless of analysis or slice, so these two strict-equality assertions failed with "Extra items in the left set: 'p_value'".

This was not a design flaw in the Phase 6 implementation — the additive-`p_value`-on-every-row behavior is exactly what the plan specifies (D-01, and `test_build_manifest_rows_emits_p_value` correctly asserts it). The gap was that the phase's own plan updated `tests/test_validation_harness.py`'s schema-lock test to a subset check (`test_build_manifest_rows_schema_still_subset_after_p_value`) but did not search for and update the two equivalent strict-equality tests living in `tests/test_research_extensions.py` (a Phase-5 file, outside this phase's `files_modified` list). 06-02-SUMMARY.md explicitly flagged that the full suite had not yet been run at phase-completion time — this verification's mandated full-suite run is what surfaced the regression.

**Resolution:** at the user's direction, the fix was applied directly via Codex rescue (bypassing the formal `/gsd-plan-phase --gaps` gap-closure plan cycle, since the fix was small, mechanical, and fully scoped by this report). Commit `8d43e68` updated both assertions in `tests/test_research_extensions.py` (lines 666, 991) from exact-set equality to a subset check (`missing = expected_columns - row.keys(); assert not missing`), mirroring the already-correct pattern in `tests/test_validation_harness.py`. No production code was touched. Full suite re-run to confirm: **162 passed in 2041.80s, 0 failures**.

`.planning/REQUIREMENTS.md` was also updated: MHT-01 changed from `[ ]`/"Pending" to `[x]`/"Complete" (a documentation-tracking gap noted above, now closed).

Overall status: `passed` (7/7 truths verified). All truths — FDR correction, walk-forward validation, additive-only column/artifact behavior, sacred-OOS non-consumption, and the full-suite regression — are verified against real data and a real full-suite run, not just SUMMARY.md claims.

---

_Verified: 2026-07-10T19:50:00Z_
_Verifier: Claude (gsd-verifier)_
