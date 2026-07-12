---
phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
plan: 04
subsystem: research-analysis
tags: [pandas, validation, bh-fdr, walk-forward, golden-fixtures, drift-gate, readme]

requires:
  - phase: 10-new-conditioning-features-magnitude-session-volume-anomaly
    provides: "the 7 new conditioning analyses (Plans 01-03) registered and flowing through build_validation.py's generic manifest dispatch"
provides:
  - "column-tolerant session filter families in build_forward_returns.py / build_expectancy.py (safe defaults + presence guards; SMT-absent graceful-degradation contract preserved)"
  - "scripts/build_conditioning_report.py: D-12 byte-stability drift gate (build_existing_analysis_drift, exits non-zero on any existing-analysis base-column change; bh_*/p_value excluded per D-13) + per-bucket new-features report (output/conditioning_features_report.csv)"
  - "regenerated golden fixtures (tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz) carrying all 7 new analyses' additive rows with n + Wilson CI + BH-FDR + walk-forward (SC4)"
  - "README 'Conditioning Features — Magnitude, Session & Volume Anomaly (v2.0)' section: per-family results tables, D-11 OHLCV-only/slot-normalization caveats, D-13 moved-q-value note"
  - "go/no-go feature evidence for the Phase 11 model gate (which magnitude/session/volume features clear the corrected + walk-forward bar)"
affects: [11-conditional-post-cisd-model]

tech-stack:
  added: []
  patterns:
    - "orchestrator-run heavy compute: the ~70min 3-slice manifest regen (build_validation.py x3 with SMT scan) was run by the orchestrator via background Bash, not the sonnet executor (project constraint: executors botch >10min jobs). Executor did only the pure-code Tasks 1-2."
    - "drift gate mirrors build_smt_invalidation_report.py: subset to non-new-analysis rows, compare BASE columns only (rate/n/successes/ci_low/ci_high/min_n_pass), exclude the by-design-moving bh_*/corrected_pass/p_value (D-13)"

key-files:
  created:
    - scripts/build_conditioning_report.py
    - tests/test_conditioning_no_drift.py
  modified:
    - scripts/build_forward_returns.py
    - scripts/build_expectancy.py
    - tests/golden/manifest_discovery_golden.csv.gz
    - tests/golden/manifest_oos_golden.csv.gz
    - tests/golden/manifest_walkforward_golden.csv.gz
    - README.md

key-decisions:
  - "D-12 drift gate exited non-zero on first run — INVESTIGATED (per plan) and found to be a STALE-BASELINE false positive, not Phase-10 drift. The on-disk golden was the Phase-7/8 baseline (commit 9b04e7c test(08-01)), never refreshed after Phase 9. Phase-10 additivity proven independently: (1) Phase-10 diff is +1656/-5, touched no SMT/existing-compute code and removed no existing annotated[...] assignment; (2) 928/944 shared non-new buckets byte-identical vs even the stale golden; (3) the only 16 movers are smt_cisd w/-SMT with reduced n = Phase 9's documented SMT invalidation-honesty correction. User approved 'refresh golden + document'."
  - "Golden fixtures refreshed to the current post-Phase-10 manifest (absorbing Phase 9's already-documented smt_cisd/smt_* deltas). After refresh the drift gate exits 0 cleanly."
---

# Phase 10 Plan 04: Regen + Drift Gate + Golden Refresh + README Summary

## Performance

- Executor (sonnet) Tasks 1-2: ~7.5 min (pure code + fixture tests)
- Orchestrator manifest regen (background): ~70 min — discovery + OOS finished ~16:03, walk-forward (4 folds, the heaviest) finished 16:50 (START 15:40 UTC)
- Total wall-clock for Wave 4: ~75 min (executor code ran concurrently with the background regen)

## Accomplishments

- **Task 1 (executor, commit 1606d00):** `build_forward_returns.py` + `build_expectancy.py` now surface a session filter family (rth_open/rth/overnight) with safe defaults, guarded by the existing column-presence checks so a frame missing the new columns still runs (SMT-absent contract preserved). 27 builder tests green. No existing filter family renamed/removed.
- **Task 2 (executor, commit 788dd32):** `scripts/build_conditioning_report.py` (drift gate + new-features report) and `tests/test_conditioning_no_drift.py` (13 fixture tests). Base columns compared: rate/n/successes/ci_low/ci_high/min_n_pass; excluded (D-13): bh_rank/bh_q_value/bh_significant/corrected_pass/p_value, with an overlap-assert so they can never leak into the compared set.
- **Task 3 (orchestrator, commit 41ac873):** regenerated all 3 manifests, ran the drift gate (investigated the stale-baseline false positive), refreshed the golden fixtures, and wrote the README methodology section.

## Feature go/no-go evidence (Phase 11 gate consumes this)

408 new discovery buckets, all published. Discovery BH-FDR corrected + walk-forward robustness:

| feature | ✓ confirmed | ✗ not-conf | below-n | wf-robust | wf-fragile | verdict |
|---|--:|--:|--:|--:|--:|---|
| wick_distance | 44 | 12 | 8 | 32 | 32 | **STRONG** — monotonic, subsumes binary wick (deep-within→far-past ≈55%→76%+), OOS holds, wf-robust on high-n TFs |
| fvg_size | 44 | 0 | 20 | 16 | 48 | **STRONG** — small FVGs (<0.5x ATR) ≈90-95%; largest (>1.5x) softens + wf-fragile |
| session | 24 | 0 | 0 | 20 | 4 | **STRONG** — clean rth_open>rth>overnight on 1H/15min; first temporal edge |
| rvol | 45 | 13 | 6 | 37 | 27 | **MODEST** — monotonic slot-relative volume signal, wf-robust |
| volume_zscore | 47 | 13 | 4 | 36 | 28 | **MODEST** — agrees with rvol; monotonic |
| sweep_depth | 30 | 7 | 27 | 16 | 48 | **WEAK** — confirmed but FLAT across depth; adds little beyond the sweep flag |
| effort_result | 30 | 8 | 26 | 28 | 36 | **WEAK** — noisy, TF-scale-fragmented (D-07); Daily/4H mostly below-n |

## Honesty invariants proven

- **D-12 (no drift):** the 19 pre-existing analyses' base rates (rate/n/successes/ci_low/ci_high/min_n_pass) are byte-stable — Phase 10 is purely additive (proof above). Drift gate exits 0 against the refreshed baseline.
- **D-13 (moved q-values):** documented in README — one global BH family means adding ~408 buckets legitimately shifts existing buckets' corrected verdicts; that is correct, not drift (base rates unchanged).
- **D-11 (caveats):** README states the OHLCV-only limitation (unsigned effort/anomaly proxies, no order flow) and that slot-normalization is partial.
- **SC4:** every new bucket carries n + Wilson CI + BH-FDR + walk-forward; session scoped to 1H/15min only; non-confirming/below-n published, never dropped.

## Task Commits

- `1606d00` feat(10-04): column-tolerant session filter family in forward-returns/expectancy scripts
- `788dd32` feat(10-04): add conditioning-features report + existing-analysis drift gate
- `41ac873` feat(10-04): refresh golden manifests + README conditioning-features section

## Files Created/Modified

Created: scripts/build_conditioning_report.py, tests/test_conditioning_no_drift.py
Modified: scripts/build_forward_returns.py, scripts/build_expectancy.py, README.md, tests/golden/manifest_{discovery,oos,walkforward}_golden.csv.gz

## Decisions Made

See key-decisions frontmatter — the stale-golden investigation is the material one.

## Deviations from Plan

- **Plan structure:** Task 3's heavy regen was orchestrator-run via background Bash (as the plan's own runtime note instructs), so the executor was scoped to Tasks 1-2 only and the orchestrator finalized Task 3 + this SUMMARY + tracking.
- **Drift gate did not exit 0 on first run** as the plan assumed. The plan treated the on-disk golden as the "pre-Phase-10 (post-Phase-9)" baseline; it was actually the Phase-7/8 baseline (Phase 9 never refreshed tests/golden/). Resolved by investigation + user-approved golden refresh (see Issues).

## Issues Encountered

- **Phase-9 golden-refresh gap (discovered here):** `tests/golden/*.csv.gz` was last written by `test(08-01)` and was never refreshed after Phase 9 added `smt_block_size`/`smt_role`/`smt_in_block` and corrected `smt_cisd`. Consequence: `tests/test_perf_characterization.py` was almost certainly failing since Phase 9 (the golden lacked the new smt_* rows). Phase 10's golden refresh repairs this. **Flagged for the operator** — worth confirming the Phase-9 closeout and whether other Phase-9 artifacts assumed a refreshed golden.

## Next Phase Readiness

Phase 11 (conditional post-CISD model) can now consume the harness-validated conditioning features. Strongest inputs by this phase's evidence: `wick_distance` (magnitude), `fvg_size`, `session`; secondary `rvol`/`volume_zscore`. `sweep_depth` and `effort_result` clear the bar only weakly and should be included with low prior.

## Self-Check: PASSED
