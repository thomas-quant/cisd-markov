# CISD-Markov Research Engine

## What This Is

A quantitative research engine that tests **CISD** (Change in State of Delivery) barrier-hit patterns across NQ and ES futures, on multiple timeframes, using a strict first-touch barrier model (target before stop within a lookahead window). It already produces per-timeframe charts, CSVs, an interactive forward-returns report, and a stop-censored expectancy study. This milestone upgrades it from a single-pass, in-sample filter-mining script into a **reproducible, test-gated research engine whose findings carry honest statistics** (in-sample/out-of-sample validation, confidence intervals, sample-size gating).

## Core Value

A reported edge can be trusted: every published rate is gated by sample size, carries a confidence interval, and is confirmed on out-of-sample data — not discovered and reported in-sample on a lucky bucket.

## Requirements

### Validated

<!-- Inferred from existing code (codebase map 2026-06-12). Shipped and relied upon. -->

- ✓ CISD detection + strict barrier-hit evaluation (target before stop, `LOOKAHEAD=2`) across NQ/ES — existing
- ✓ Multi-timeframe resampling (Daily / 4H / 1H / 15min) from 1-minute parquet — existing
- ✓ Single-pass enriched-DataFrame annotation pipeline (`direction`, `prev_*`, `cisd_type`, FVG, sweep, swing, SMT columns) consumed by all analyses — existing
- ✓ 14 barrier analyses (`basic`, `mc`, `significance`, `wick`, `combined`, `volume`, `candle_size`, `size_cross`, `smt_cisd`, `cisd_fvg`, `fvg_hold`, `cisd_fvg_interaction`, `sweep`, `sssf_swing`) — existing
- ✓ Per-TF + standalone chart/CSV output via the `ANALYSES` registry — existing
- ✓ Interactive forward-returns HTML report (core / fvg / structure families) — existing
- ✓ Stop-censored R-multiple expectancy study (`build_expectancy.py`) — existing
- ✓ Swing SMT confirmation via the external SMT package — existing

### Active

<!-- This milestone. Sequenced by dependency; test-gated throughout. -->

- [ ] **Reproducibility/infra**: dependency manifest (`requirements.txt`/pyproject), env-var SMT path with graceful fallback, CI running the test suite, deterministic runs
- [ ] **Characterization tests**: lock the current published headline numbers before any refactor or harness work can move them
- [ ] **Validation harness (foundational)**: sacred date holdout (newest ~30% OOS evaluated once; oldest ~70% discovery) + binomial confidence intervals + sample-size gating on every reported rate
- [ ] **Re-validate existing findings**: re-run README headline results through the harness and republish with n + CI + OOS confirmation; treat existing findings as hypotheses, retire any that don't survive
- [ ] **Modular refactor**: split the god-file into `cisd_data` / `cisd_barriers` / `cisd_charts`, consolidate the 4-edit standalone-analysis registry, vectorize the `iterrows` hot loops (follow `build_expectancy.py`'s `np.flatnonzero` pattern)
- [ ] **New research — `candle[1]` follow-through**: does the bar after a CISD predict continuation (close in CISD direction, close beyond `candle[1]`'s wick)
- [ ] **New research — multi-bar post-CISD context**: `candle2_gap_context` / `post_cisd_reversal_context` (failed `candle[1]` + gap on `candle[2]` regime)

### Out of Scope

<!-- Explicit boundaries with reasoning, to prevent re-adding. -->

- `post_cisd_ml` (small ML model over post-CISD features) — deferred until the discrete tags prove promising; keeps this milestone focused on the validation foundation
- Formal multiple-comparisons / data-snooping correction (Benjamini-Hochberg, Bonferroni, White's Reality Check) — this is the *next* rigor tier; foundational round ships CIs + n-gating only
- Walk-forward / rolling-window validation — deferred; foundational round is a single sacred holdout split
- Live signaling / productization / alerting — this is a historical-research tool, not a trading system
- New instruments beyond NQ/ES — out of scope for this milestone
- Output artifacts in git history — generated `output/` files should stop being committed, not be re-architected into a release pipeline this round

## Context

- Existing single-file engine (`cisd_analysis.py`, ~1,380 lines) plus `scripts/build_forward_returns.py` and `scripts/build_expectancy.py`. Full codebase map lives in `.planning/codebase/` (refreshed 2026-06-12).
- **The trust problem this milestone fixes:** every number in the current README is in-sample, single-pass, with no confidence intervals and no multiple-comparisons control, while dozens of buckets are tested across 2 instruments × 4 timeframes × 2 directions. Headline extremes sit at tiny n (e.g. Daily ES bear w/ SMT = 27.8% at n=18; NQ bear w/ SMT at n=11) — exactly where data-snooping artifacts hide.
- `build_expectancy.py`'s `np.flatnonzero` + array-indexing approach is the in-repo reference implementation for vectorizing the slow `iterrows`/`get_loc` loops.
- Concerns audit (`.planning/codebase/CONCERNS.md`) flagged the infra gaps this milestone closes: no `requirements.txt`/CI, hardcoded WSL SMT path, `build_forward_returns.py` hard-requires SMT, god-file with a 4-edit registry, dead `smt_cisd` branch in `build_csv_rows`, and no unit tests on the core `compute_basic/mc/significance/wick/combined` analyses the headline findings come from.
- Research backlog (`docs/research_backlog.md`): near-term CISD extensions are all done; open ideas are the `candle[1]` follow-through and multi-bar post-CISD context studies (in this milestone) and `post_cisd_ml` (deferred).

## Constraints

- **Tech stack**: Python 3.10+, pandas / numpy / matplotlib / pyarrow (plotly via CDN for the HTML report). Keep dependencies minimal — research must run offline and deterministically.
- **Data**: 1-minute OHLCV parquet for NQ + ES in `data/` (`DateTime_ET` index). A fixed data snapshot is assumed so the OOS boundary date is stable across runs.
- **External dependency**: SMT package (currently a hardcoded WSL path) is optional — every entry point must degrade gracefully when it is absent.
- **Determinism**: results must be reproducible — pinned dependencies, no wall-clock or RNG dependence in computed numbers.
- **Behavior-preserving**: the refactor and the validation harness must not silently alter existing computed numbers. Characterization tests lock current behavior *before* those changes land.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Sacred date holdout (newest ~30% OOS, evaluated once; oldest ~70% discovery) | Chronological split is the only leakage-safe option for time series; "sacred" is hardest to fool yourself with | — Pending |
| Re-validate existing findings as hypotheses, not facts | They were discovered in-sample on data that includes the now-OOS slice; must be confirmed OOS | — Pending |
| Test-gated / behavior-preserving refactor (lock numbers first) | The modular split and harness must not move published results underneath us | — Pending |
| Foundational validation depth: CIs + n-gating, no MHT correction yet | Tractable honest baseline this round; correction is the next milestone | — Pending |
| Modular split into `cisd_data` / `cisd_barriers` / `cisd_charts` | God-file + 4-edit registry blocks safe extension and invites silent omissions | — Pending |
| Defer the post-CISD ML model | Keep scope tight; validate discrete tags before modeling on top of them | — Pending |
| Harness makes single-evaluation the default path | A "sacred" holdout only stays sacred if the tool nudges toward evaluating it once, not relying on discipline | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-12 after initialization*
