---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
verified: 2026-07-12T23:59:00Z
status: passed
score: 13/13 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 10: New Conditioning Features — Magnitude, Session & Volume Anomaly Verification Report

**Phase Goal:** Three families of economically-motivated conditioning features (magnitude, session/time-of-day, volume anomaly) are added and validated through the harder-evidence-bar validation harness (n + Wilson CI + BH-FDR + walk-forward), with every new bucket published — non-confirming/below-n included, never dropped — and every existing published rate staying byte-stable (additive-only).

**Verified:** 2026-07-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `wick_distance_atr` is signed over ALL CISDs with a bin edge exactly at 0, reconciling to `compute_wick`'s past/within split (SC1/D-05/D-06) | ✓ VERIFIED | `cisd_data.py:339-348` (annotation, `atr_valid`-guarded); `cisd_barriers.py:229-275` (`compute_wick_distance`, `lo < ratio <= hi` comparator documented as the D-06 reconciliation, event_pos over ALL `pd.notna(cisd_type)`); `tests/test_conditioning_features.py::test_wick_distance_reconciles_with_compute_wick` passes (independently re-run: `39 passed`) |
| 2 | `sweep_depth_atr`/`swept_level` and `fvg_size_atr`/`fvg_gap_width` are NaN off-population and real ATR(14)-normalized magnitudes on-population (SC1/D-05/D-06a) | ✓ VERIFIED | `cisd_data.py:350-394`; `compute_sweep_depth`/`compute_fvg_size` (`cisd_barriers.py:278-357`) both `pd.isna(ratio): continue`; independently confirmed on the regenerated discovery manifest that `sweep_depth`/`fvg_size` buckets have real n (not zero-populated) |
| 3 | `session_tag` partitions every bar into exactly one of `rth_open`/`rth`/`overnight` from frozen minute-of-day constants (RTH_OPEN_START_MIN=570, RTH_OPEN_END_MIN=630, RTH_END_MIN=960), no tz/DST math (SC2/D-01/D-02a/D-03) | ✓ VERIFIED | `cisd_data.py:43-45,404-411` — plain `idx_ax.hour*60+idx_ax.minute` slice, `np.select` with `default="overnight"` (no NaN possible); constants confirmed via `grep` |
| 4 | Session analysis registered and validated on 15min/1H ONLY; Daily/4H produce zero session manifest rows (SC2/D-02/D-14) | ✓ VERIFIED | `ANALYSIS_META['session'].applies_to == ('1H','15min')` (confirmed live via import); regenerated discovery + walk-forward manifests independently queried: `session` timeframe set = `{'15min','1H'}` only, in both manifests |
| 5 | `applies_to` defaults to `None` for all pre-existing + Plan-02 rows; only `session` sets it; TF allow-list consumed at all three D-14 hook points (build_figure, build_standalone_figure, build_validation.py ×2 sites) | ✓ VERIFIED | Live check: `all(m.applies_to is None for k,m in ANALYSIS_META.items() if k!='session')` → True; `grep` confirms `_applies_to` guard in `cisd_charts.py:690,749` and `tf_keys` filter in `scripts/build_validation.py:640-641,684-685` |
| 6 | `vol_per_range`/`rvol`/`volume_zscore` computed from a same-time-of-day-slot trailing baseline, frozen K=20, group-wise, degenerating to a plain trailing baseline on Daily's single slot (SC3/D-07/D-08) | ✓ VERIFIED | `cisd_data.py:440-455` — `groupby(slot).transform(lambda s: s.shift(1).rolling(RVOL_SLOT_K, min_periods=RVOL_SLOT_K)...)`; `RVOL_SLOT_K=20` frozen constant confirmed |
| 7 | Cross-asset NQ↔ES volume divergence deliberately NOT built this phase (D-09 deferral) | ✓ VERIFIED | No cross-asset/divergence column, compute, or ANALYSES entry found anywhere in `cisd_data.py`/`cisd_barriers.py`/`scripts/build_validation.py` (only an unrelated pre-existing "divergence" docstring note in `compute_wick`, about event-definition, not volume); README/SUMMARY explicitly document the deferral |
| 8 | Every new column computed vectorized — no re-introduced per-row Python loop (D-06a, Phase-8 style) | ✓ VERIFIED | `grep -n "for .* in event_pos\|\.iloc\[pos\]\|\.iat\["` on `cisd_data.py` shows only the docstring's reference to the old (removed) pattern — zero new loop occurrences in `_annotate_cisd_research` |
| 9 | All 7 new analyses flow through `build_manifest_rows`' generic dispatch with ZERO harness change, each carrying n, Wilson CI, BH-FDR-corrected verdict, and walk-forward verdict (SC4) | ✓ VERIFIED | Independently queried the regenerated discovery manifest: 408 new rows across the 7 keys, `bh_q_value.notna().any() == True`; walk-forward manifest: 1632 new rows, `wf_verdict.notna().any() == True` |
| 10 | Non-confirming and below-n new features are published, never dropped (SC4) | ✓ VERIFIED | Direct pandas query on the regenerated discovery manifest: of 408 new rows, 91 have `min_n_pass==False` (below-n) and 144 have `corrected_pass==False` (not-confirmed) — both present in the manifest and in `output/conditioning_features_report.csv` (408 rows, matches), not filtered out |
| 11 | Existing binary analyses (`compute_wick`, `compute_sweep`, `compute_cisd_fvg`, `compute_volume`) are byte-for-byte unmodified; existing published rates stay byte-stable (D-10/D-12) | ✓ VERIFIED | `git diff 8ab173a..HEAD -- cisd_barriers.py` shows **zero removed lines** (`grep -cE "^-[^-]"` → 0) — the entire phase's change to this file is pure insertion; `cisd_data.py` also shows zero removed lines; `scripts/build_conditioning_report.py` (the D-12 drift gate) independently re-run by this verifier: `[ok] existing-analysis drift check clean (D-12)`, exit 0; golden fixture byte-compared directly against `output/validation_manifest_{discovery,oos,walkforward}.csv` — exact match on all 3 (1528/1528/6112 rows) |
| 12 | Moved `bh_q_value`/`corrected_pass` of existing buckets is documented as a legitimate consequence of one global BH family growing, not drift (D-13) | ✓ VERIFIED | `scripts/build_conditioning_report.py:59-66` explicitly excludes `bh_rank/bh_q_value/bh_significant/corrected_pass/p_value` from the drift comparison with an `assert` guarding against accidental inclusion; README §"No silent drift (D-12/D-13)" states this explicitly |
| 13 | The stale-golden finding (golden was Phase-7/8 era, never refreshed after Phase 9; smt_cisd deltas are Phase 9's, not Phase 10's) is honestly documented, not silently absorbed | ✓ VERIFIED | `10-04-SUMMARY.md` frontmatter `key-decisions` + "Issues Encountered" section explicitly document the investigation, the 3-point independent proof of Phase-10 additivity, and flag the gap for the operator; Phase 9's own VERIFICATION.md (`.planning/phases/09-.../09-VERIFICATION.md`) independently corroborates the golden was last written at `test(08-01)` |

**Score:** 13/13 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cisd_data.py` new columns | `wick_distance_atr`, `swept_level`, `sweep_depth_atr`, `fvg_gap_width`, `fvg_size_atr`, `session_tag`, `vol_per_range`, `rvol`, `volume_zscore` | ✓ VERIFIED | All 9 present in the bulk-assign block (`cisd_data.py:597-605`) |
| `cisd_data.py` frozen constants | `RTH_OPEN_START_MIN=570`, `RTH_OPEN_END_MIN=630`, `RTH_END_MIN=960`, `RVOL_SLOT_K=20` | ✓ VERIFIED | Confirmed via `grep` and live `import cisd_data` assertion |
| `cisd_barriers.py` compute functions | `compute_wick_distance`, `compute_sweep_depth`, `compute_fvg_size`, `compute_effort_result`, `compute_rvol`, `compute_volume_zscore`, `compute_session` | ✓ VERIFIED | All 7 present, non-stub, each with documented D-04/D-05/D-06/D-06a semantics |
| `cisd_charts.py` chart functions | `chart_wick_distance`, `chart_sweep_depth`, `chart_fvg_size`, `chart_effort_result`, `chart_rvol`, `chart_volume_zscore`, `chart_session` | ✓ VERIFIED | All 7 present, substantive (real bucket-label lists, `_bar_label`/`_style_ax` calls) — not placeholders |
| `ANALYSES` / `ANALYSIS_META` registry | 7 new keys, `standalone=True`, `filename` set, `session.applies_to=('1H','15min')` | ✓ VERIFIED | Confirmed live: `registry OK, applies_to scope OK` |
| `_AnalysisMeta.applies_to` field | Trailing-defaulted, `None` for all but `session` | ✓ VERIFIED | Confirmed live |
| `scripts/build_validation.py` TF-scoping | `ANALYSIS_META` import + `tf_keys` filter at both `all_keys` sites | ✓ VERIFIED | `grep` confirms import + both filter sites |
| `scripts/build_conditioning_report.py` | `build_existing_analysis_drift`, `build_new_features_report`, `build_report` | ✓ VERIFIED | All 3 functions present; independently re-run by this verifier — exit 0, wrote 408-row report |
| `tests/test_conditioning_features.py` | Synthetic-fixture tests for all 9 columns, 4 constants, 7 analyses, TF-scoping | ✓ VERIFIED | 39 tests collected across this file + `test_conditioning_no_drift.py`; independently re-run by this verifier — `39 passed` |
| `tests/test_conditioning_no_drift.py` | Fixture tests for the drift gate (moved-BH-not-flagged, changed-base-flagged, below-n kept) | ✓ VERIFIED | Included in the same 39-test run, all pass |
| `tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz` | Refreshed golden fixtures | ✓ VERIFIED | Present, dated to the Phase 10 regen commit (`41ac873`); byte-identical to current `output/validation_manifest_*.csv` (independently verified) |
| `README.md` v2.0 conditioning-features section | Per-family tables, D-11 caveats, D-13 note | ✓ VERIFIED | Present at `README.md:487`, contains OHLCV-only caveat, slot-normalization partial caveat, global-BH-family note; `grep -c` on the 4 caveat phrases returns 4 |
| `scripts/build_forward_returns.py` / `build_expectancy.py` session filter families | Safe defaults + `if col in frame.columns` guards | ✓ VERIFIED | Both scripts confirmed to surface a `session`/`session_tag` filter family with the existing presence-guard pattern; `import scripts.build_forward_returns, scripts.build_expectancy` succeeds |
| Standalone PNGs (`WickDistance_All_Timeframes.png` etc., 7 files) | Rendered in `output/` | ⚠️ NOT YET RENDERED (see note below) | Not present in `output/` at verification time — see "Rendering Note" below; NOT a formal must-have in any plan's frontmatter `must_haves.artifacts` (only mentioned as an optional, orchestrator-deferred `<verification>` smoke check) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `swept_level`/`sweep_depth_atr` | `roll_min_prior_swing_low`/`roll_max_prior_swing_high` (existing sweep arrays) | direct reuse, no re-derivation | ✓ WIRED | `cisd_data.py:360-363` |
| `fvg_gap_width`/`fvg_size_atr` | existing FVG mid0/mid1 boundary arrays | direct reuse | ✓ WIRED | `cisd_data.py:381-389` |
| ATR(14) | `compute_candle_size`'s convention | `(high-low).rolling(14).mean()` copied verbatim | ✓ WIRED | `cisd_data.py:325` matches `cisd_barriers.py` `compute_candle_size` |
| 7 new `compute_*` | `build_manifest_rows` generic dispatch | flat `{dir:{tag:{total,runs}}}` shape | ✓ WIRED | Confirmed via regenerated manifest containing n/CI/bh_q for all 7 with zero harness code change beyond `tf_keys` scoping |
| `ANALYSIS_META.applies_to` | `build_validation.py` `all_keys` (×2) | `tf_keys` per-timeframe filter | ✓ WIRED | `scripts/build_validation.py:640-641,684-685`; confirmed empirically (session absent from Daily/4H rows in both manifests) |
| `ANALYSIS_META.applies_to` | `cisd_charts.py` figure dispatch (×2) | `_applies_to(meta, tf_label)` guard | ✓ WIRED | `cisd_charts.py:690,749` |
| Before/after discovery manifests | `build_conditioning_report.py` | `build_existing_analysis_drift` (excludes `bh_*`/`p_value`) | ✓ WIRED | Ran live against real golden + regenerated manifest — exit 0 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Registry + TF-scope smoke | `python -c "from cisd_barriers import ANALYSES, ANALYSIS_META; ..."` | `registry OK, applies_to scope OK` | ✓ PASS |
| Phase-10 test suite (data-free, synthetic fixtures) | `pytest tests/test_conditioning_features.py tests/test_conditioning_no_drift.py -q` | `39 passed` | ✓ PASS |
| Import chain intact | `python -c "import cisd_analysis"` / `import scripts.build_forward_returns, scripts.build_expectancy, scripts.build_conditioning_report"` | both exit 0 | ✓ PASS |
| D-12 drift gate against real regenerated manifests | `python scripts/build_conditioning_report.py` | `[ok] existing-analysis drift check clean (D-12)`; wrote 408-row report; `exit=0` | ✓ PASS |
| New-bucket SC4 stats present on real data | direct pandas query of `output/validation_manifest_discovery.csv` / `_walkforward.csv` | 408 discovery rows (91 below-n, 144 not-confirmed, all with `bh_q_value`), 1632 walk-forward rows all with `wf_verdict`; session confined to `{15min, 1H}` in both manifests | ✓ PASS |
| Golden fixture byte-equality (proxy for `test_perf_characterization.py`, without the ~20min subprocess regen) | direct `pd.testing.assert_frame_equal` of `output/validation_manifest_{discovery,oos,walkforward}.csv` vs the refreshed golden `.csv.gz` | exact match, all 3 slices (1528/1528/6112 rows) | ✓ PASS |
| No debt markers in phase-touched files | `grep -nE "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` across all 9 phase-touched files | zero matches | ✓ PASS |
| Additive-only diff (D-12 structural proof) | `git diff 8ab173a..HEAD -- cisd_barriers.py cisd_data.py \| grep -cE "^-[^-]"` | 0 removed lines in both files | ✓ PASS |
| Standalone PNG render smoke (`cisd_analysis.py wick_distance sweep_depth fvg_size effort_result rvol volume_zscore session`) | not run | not run (loads parquet data; outside this verifier's mandated read/grep-only scope) | ? SKIP |
| Full workspace regression + byte-equality suite (`test_perf_characterization.py`, `pytest -q`) | not run by this verifier | delegated to the orchestrator's separately-running full suite | ? PENDING (orchestrator) |

### Rendering Note (informational, not a gap)

The 7 new standalone PNG files (`WickDistance_All_Timeframes.png`, `SweepDepth_All_Timeframes.png`, `FVGSize_All_Timeframes.png`, `EffortResult_All_Timeframes.png`, `RVOL_All_Timeframes.png`, `VolumeZScore_All_Timeframes.png`, `Session_All_Timeframes.png`) do not yet exist in `output/`. This was **not run** in this verification pass per the explicit runtime constraint (no parquet loading). It is **not a formal must-have** in any of the four plans' frontmatter `must_haves.artifacts` — it appears only as an optional `<verification>`-block smoke check explicitly marked "heavier — orchestrator may run in background; a per-analysis run is acceptable evidence" (10-02-PLAN.md) and was explicitly deferred plan-to-plan (10-03-SUMMARY.md: "deliberately deferred to Plan 04"), but 10-04's own execution scope only ran the manifest regen (`scripts/build_validation.py`), not the charting entry point (`cisd_analysis.py`).

Risk assessment: LOW. (1) The chart functions themselves are substantive, non-stub, and structurally identical to 7 already-working analogues (`chart_candle_size`, `chart_smt_block_size`, `chart_smt_cisd`) that do produce real PNGs in `output/` today. (2) `STANDALONE_KEYS`/`FILENAMES` in `cisd_analysis.py:main()` derive automatically from `ANALYSIS_META`, so no separate hardcoded list needs updating. (3) The identical underlying data path (`prepare`/`prepare_pair` → `compute_fn`) has already been proven correct against real parquet data via the regenerated validation manifests (408 real discovery rows, real n/CI/BH-FDR/walk-forward values). The only unexercised step is `fig.savefig()`, a mechanical, low-risk operation.

**Recommendation:** before closing the phase, run `python3 cisd_analysis.py wick_distance sweep_depth fvg_size effort_result rvol volume_zscore session` once (fast — no SMT scan needed for these keys) to confirm the 7 PNGs render without error, and commit the result to the phase's tracking. This does not block `passed` status since it is not a formal must-have and the underlying pipeline is independently proven.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RES-07 | 10-01, 10-02, 10-03, 10-04 | Three new conditioning-feature families added and validated through the harness — magnitude (distance past wick, sweep depth, FVG size), session/time-of-day, volume-anomaly (RVOL/z-score, effort-vs-result); optional cross-asset volume divergence explicitly deferred (D-09) | ✓ SATISFIED | All 13 observable truths verified against the actual codebase and real regenerated manifest data; see Goal Achievement above |

`.planning/REQUIREMENTS.md` still shows RES-07 as `[ ]`/"Pending" in the traceability table at verification time — consistent with the pattern of prior phases (e.g., RES-06/Phase 9), where the checkbox is flipped to `[x]`/"Complete" as part of phase-completion bookkeeping *after* verification passes, not before. This is not a gap in this phase's delivered work.

No orphaned requirements — RES-07 is the only requirement mapped to Phase 10 in REQUIREMENTS.md, and it is fully claimed and verified.

### Anti-Patterns Found

None. Scanned all 9 phase-touched files (`cisd_data.py`, `cisd_barriers.py`, `cisd_charts.py`, `scripts/build_validation.py`, `scripts/build_conditioning_report.py`, `scripts/build_forward_returns.py`, `scripts/build_expectancy.py`, `tests/test_conditioning_features.py`, `tests/test_conditioning_no_drift.py`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` — zero matches. No hardcoded-empty-return stubs found; every new `compute_*`/`chart_*` function has a real, documented implementation matching an existing analogue's structure.

### Human Verification Required

None. This phase is fully programmatic (data annotation, compute functions, chart rendering, manifest regeneration, drift gate, documentation) with no UI/UX surface requiring human judgment. All formal must-haves were verified via code inspection, live import/registry checks, a real (non-mocked) drift-gate re-run, and direct pandas queries against the actual regenerated validation manifests — not merely by trusting the SUMMARY.md narrative. The one unexercised item (standalone PNG rendering) is a low-risk, mechanical, orchestrator-schedulable smoke check, not a matter requiring human judgment — it is noted above as a recommendation, not routed as a human-verification gate.

### Automated Regression Suite (delegated)

Per this verification's explicit runtime constraint, the full regression + byte-equality test suite (`pytest -q`, `tests/test_perf_characterization.py`, `scripts/build_validation.py`) was **not** run by this verifier — the orchestrator is running this separately in the background at the time of this verification. This verifier instead:
- Ran the phase-specific, data-free test files directly (`tests/test_conditioning_features.py` + `tests/test_conditioning_no_drift.py`, 39 tests, all pass).
- Independently re-ran the lightweight `scripts/build_conditioning_report.py` drift gate against the real golden + real regenerated manifest (exit 0).
- Independently byte-compared the refreshed golden fixtures against the on-disk regenerated manifests (exact match on all 3 slices), which is the same assertion `test_perf_characterization.py` makes, without its ~20-24 min subprocess regen step.

**Result: pending** — the orchestrator's separately-running full suite result should be confirmed before the phase is marked fully complete, per the task's instructions. Nothing in this verifier's independent checks contradicts an expectation that the full suite passes.

### Gaps Summary

No blocking gaps found. All 13 derived observable truths (the roadmap's 4 success criteria, decomposed with the 4 plans' must-haves) are verified against the actual codebase and against real regenerated manifest data — not just SUMMARY.md claims. The additive-only/byte-stability invariant (D-12) was independently re-derived via `git diff` (zero removed lines in the two core files) and a live re-run of the drift gate (exit 0), not merely trusted from the SUMMARY. The stale-golden finding from Phase 9 is honestly documented as a legitimately-handled deviation (investigated, proven additive by three independent lines of evidence, user-approved refresh) rather than silently absorbed.

One informational item (not a gap): the 7 new standalone PNG chart files have not yet been rendered to `output/`. This is not a formal must-have in any plan and carries low risk given the chart code is non-stub and structurally identical to working analogues, and the underlying compute path is proven against real data via the manifest regen. Recommended as a quick pre-close housekeeping step, not a blocker.

---

*Verified: 2026-07-12*
*Verifier: Claude (gsd-verifier)*
