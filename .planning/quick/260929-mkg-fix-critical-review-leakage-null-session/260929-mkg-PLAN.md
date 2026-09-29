---
quick_id: 260929-mkg
slug: fix-critical-review-leakage-null-session
date: 2026-09-29
mode: quick (executed inline by orchestrator — see Deviations in SUMMARY)
---

# Quick Task 260929-mkg: Fix critical review findings (leakage, null, session, loader)

Source: code review of 2026-09-29 (conversation), empirically checked on NQ 1H
discovery (2020-01..OOS_START, 12,848 CISDs).

## User decisions (locked)

- **Leak fix frame = confirm-then-enter.** A conditioner known only at the close of
  bar t+k is scored from entry at close[t+k], same CISD-candle target/stop,
  LOOKAHEAD-bar window t+k+1..t+k+LOOKAHEAD; events that touched target or stop
  on bars t+1..t+k are dropped (not tradeable). All buckets inside one analysis
  share one k (the comparison bucket must share the frame).
- **Null = corridor-position baseline.** Per event, expected hit probability =
  hit rate of all CISDs in the same slice/TF/instrument/direction/frame whose
  entry sits in the same fixed 10% bin of the stop→target corridor. Bucket tested
  on observed vs expected hits (lift + z, Poisson-binomial variance). Legacy 0.5
  columns kept; new geo_* columns drive BH, walk-forward and OOS verdicts.

## Tasks

### T1 — Data loader (blocking: pipeline cannot run)
- `load_1m` accepts legacy `DateTime_ET` and new `datetime_utc` (UTC → America/New_York, tz-naive).
- Pin to frozen snapshot window `DATA_START=2020-08-31`, `DATA_END=2025-11-21` (inclusive);
  reconstruction reproduces OOS_START idx 1138 and all 4 WALK_FORWARD_FOLDS exactly.
- Verify: characterization tests (pinned README numbers) pass.

### T2 — Look-ahead leakage → confirm-then-enter
- New `barrier_hit_after(df, idx, row, ct, k)` → True/False/None (None = resolved
  before entry or incomplete window → excluded).
- k per analysis: `cisd_fvg` k=2, `fvg_size` k=2, `sssf_swing` k=1,
  post_cisd `candle2_past_candle1_wick` k=2 (close[t+2]).
- Outcome-defined buckets that cannot be made tradeable are flagged diagnostic
  (excluded from BH family and verdicts): `cisd_fvg_interaction` (hold over
  t+1..t+10), `smt_cisd` "w/ SMT & survived/broke", `candle1_followthrough` *_inwindow.
- `build_expectancy.py`: FVG/swing cases use the same per-case entry offset.

### T3 — Corridor-position null
- `attach_geo_baseline(df)` adds per-event `geo_p_k{0,1,2}` (and forward frame) on a slice.
- Compute cells carry `expected` / `expected_var`; manifest adds `geo_expected_rate`,
  `geo_lift`, `geo_z`, `geo_p_value`; discovery adds `geo_bh_q_value`,
  `geo_bh_significant`, `geo_corrected_pass`; walk-forward adds geo fold/wf verdicts
  (same sign of lift); reconcile adds geo-based OOS verdict.

### T4 — Session labelling
- Tag by bar midpoint (label + bar_span/2), bar span inferred from modal index diff;
  fixes 1H 09:00 bar (contains 09:30 open) being tagged overnight.

## Verification
- Full pytest green (update behavior-lock tests only where the fix deliberately moves numbers; document each).
- New unit tests: barrier_hit_after, leak regression (no conditioner reads bars inside its scoring window), geo baseline math, session midpoint.
