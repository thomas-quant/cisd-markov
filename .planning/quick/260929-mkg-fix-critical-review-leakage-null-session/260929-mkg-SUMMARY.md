---
quick_id: 260929-mkg
slug: fix-critical-review-leakage-null-session
date: 2026-09-29
status: complete
commits: [56addde]
---

# Quick Task 260929-mkg — Summary

Fixes the critical findings of the 2026-09-29 code review. User decisions:
confirm-then-enter frame for late-known conditioners; corridor-position
(close-location-stratified) baseline as the null.

## What changed

| Fix | Code | Effect |
|---|---|---|
| Data loader | `load_1m` accepts `datetime_utc` (UTC → ET), pins `DATA_START..DATA_END` = 2020-08-31..2025-11-21 | Pipeline runs again; frozen OOS_START / folds reproduced exactly. Old snapshot lost → characterization re-pinned (intraday n ≤ 0.3%, rates ≤ 0.2 pp; Daily ≤ 0.8 pp, one n=72 cell 3.7 pp) |
| Look-ahead leakage | `barrier_hit_after(k)`; `cisd_fvg`, `fvg_size`, Reading B k=2; `sssf_swing` k=1; expectancy/forward-returns FVG & structure cases re-anchored; `is_diagnostic()` for outcome-defined buckets | Leaky "edges" collapse (see below) |
| Null | `attach_geo_baseline()`, `_tally()` expected/var accumulation; manifest `geo_*` + `diagnostic`; geo BH, geo walk-forward, reconcile + post-CISD geo verdicts | Verdicts measured against corridor geometry instead of 0.5 |
| Session | tag at bar midpoint; session intraday-only in expectancy / forward returns (WR-01) | 1H 09:00 bar (contains the open) now `rth_open` |

Tests: 312 passed / 5 skipped (full suite incl. data-backed characterization). New
`tests/test_leakage_and_geo.py` (18 tests) includes a causality test that perturbs
all bars after each tag's known-at bar and asserts the tag is unchanged.

## Corrected evidence (discovery; regenerated without SMT)

- Legacy 0.5-null `corrected_pass`: 851 / 1,320. Corridor null: 48 above-baseline,
  38 below-baseline; 73 of those 86 also geo walk-forward-robust.
- **Retracted:** `cisd_fvg` (NQ 15min bull mid0 90.6% n=2,581 → 29.8% n=198, below
  its 39.9% baseline; mid1 empty by construction — a mid1 FVG means the target was
  already hit), `fvg_size`, `sssf_swing` CISD-bar swing (89% → at baseline),
  Reading B, `session` (one surviving cell).
- **Survive, 2–8 pp:** candle body size / size_cross, wick / wick_distance (past-wick
  +2 to +5 pp, not 55→76%), low-volume penalty (rvol/zscore −2 to −3.5 pp),
  post-CISD `failed_gap_with` (+) / `failed_gap_against` (−).

## Caveats (carried into README)

- `geo_z` assumes independence; overlapping windows, NQ/ES duplication and nested
  buckets uncorrected → 86 is an upper bound. No effective-n yet.
- Corridor baseline controls entry position only, not volatility/timeouts.
- "not-significant" ≠ no effect; no equivalence tests run.

## Deviations

- Executed inline by the orchestrator instead of planner + executor subagents:
  the design was fixed by the user's two decisions, and the 8 GiB WSL cap made
  parallel data-backed test/regeneration runs risky.
- Not done (need user decisions / missing inputs): sacred OOS re-run, reconcile +
  post-CISD verdict regeneration (would mix new discovery with stale OOS), golden
  refresh, SMT re-evaluation (package missing).
