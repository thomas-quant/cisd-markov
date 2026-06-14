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
- ✓ **Reproducibility/infra**: pinned `requirements.txt`, env-var `SMT_PKG_PATH` with graceful fallback across all entry points, GitHub Actions CI running pytest, working-directory-independent imports, deterministic runs — Phase 1
- ✓ **Characterization tests**: README headline barrier/SMT rates locked against the live pipeline (data-skip guarded), plus unit tests on the 5 core compute functions — Phase 1

### Active

<!-- This milestone. Sequenced by dependency; test-gated throughout. -->

- ✓ **Validation harness (foundational)**: sacred date holdout (`OOS_START = "2024-04-30"`, ~30% OOS, evaluated once; ~70% discovery) + Wilson score binomial CIs (pure stdlib, Python 3.12 compatible) + n≥50 gating + tidy `validation_manifest.csv` with n/CI/IS-OOS per bucket — `scripts/build_validation.py` + `tests/test_validation_harness.py` (14 tests) — Phase 2
- ✓ **Re-validate existing findings**: re-ran all 14 analyses on the discovery slice, spent the one sacred OOS evaluation (616 confirmed / 48 not-confirmed / 88 below-n across 752 buckets); primary OOS casualties were bearish Daily edges across most analyses; README republished with discovery-slice rates, Wilson CIs, and IS/OOS verdict badges — Phase 3
- ✓ **Modular refactor**: split the 1,380-line god-file into `cisd_data` / `cisd_barriers` / `cisd_charts` + thin re-export shim, consolidated the 4-edit standalone-analysis registry into a single `ANALYSIS_META` source of truth, vectorized the `_annotate_cisd_research` outer loop + all 14 `compute_*` functions to the `build_expectancy.py` `np.flatnonzero` pattern; removed the dead `smt_cisd` CSV branch and documented `compute_significance`'s intentional `cisd_type` bypass — all 94 characterization/unit tests still green (bit-identical numbers) — Phase 4 (REFAC-01/02/03/04)
- [ ] **New research — `candle[1]` follow-through**: does the bar after a CISD predict continuation (close in CISD direction, close beyond `candle[1]`'s wick)
- [ ] **New research — multi-bar post-CISD context**: `candle2_gap_context` / `post_cisd_reversal_context` (failed `candle[1]` + gap on `candle[2]` regime)
- ✓ **Regenerate README headline tables** (WR-04 closed in Phase 3): §8 SMT table and §3 within-wick label regenerated from live output; ES Daily bearish corrected from 27.8% n=18 → 52.3% n=65; §3 NQ/ES label corrected — Phase 3

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
| Sacred date holdout (newest ~30% OOS, evaluated once; oldest ~70% discovery) | Chronological split is the only leakage-safe option for time series; "sacred" is hardest to fool yourself with | Implemented — `OOS_START = "2024-04-30"` hardcoded with "Do NOT recompute" guard (Phase 2) |
| Re-validate existing findings as hypotheses, not facts | They were discovered in-sample on data that includes the now-OOS slice; must be confirmed OOS | — Phase 3 |
| Test-gated / behavior-preserving refactor (lock numbers first) | The modular split and harness must not move published results underneath us | Implemented — characterization suite (94 tests) gated each task; bit-identical numbers confirmed post-merge (Phase 4) |
| Foundational validation depth: CIs + n-gating, no MHT correction yet | Tractable honest baseline this round; correction is the next milestone | Implemented — Wilson score CI + n≥50 gate (Phase 2) |
| Modular split into `cisd_data` / `cisd_barriers` / `cisd_charts` | God-file + 4-edit registry blocks safe extension and invites silent omissions | Implemented — one-directional import chain (shim → barriers → charts → data), `ANALYSIS_META` single registry; zero importer changes in scripts/tests (Phase 4) |
| Defer the post-CISD ML model | Keep scope tight; validate discrete tags before modeling on top of them | — Phase 5+ |
| Harness makes single-evaluation the default path | A "sacred" holdout only stays sacred if the tool nudges toward evaluating it once, not relying on discipline | Implemented — `--oos` flag required; default is discovery-on-train with loud ASCII banner on OOS path (Phase 2) |
| `math.erfinv` is Python 3.13+ only | Winitzki+Halley shim needed for project's Python 3.12.3 runtime | Implemented inline in `build_validation.py` `_erfinv()` — no external dependency added (Phase 2) |
| Slice-suffixed manifest filenames (`_discovery.csv` / `_oos.csv`) | OOS run must never clobber the discovery manifest; suffix makes the invariant structurally impossible to violate | Implemented — `build_validation.py` writes to the suffixed path; `validation_manifest.csv` is a legacy alias only (Phase 3) |
| Bearish Daily edges are not publishable findings | 24 of 48 not-confirmed buckets were Daily/bearish across 10 of 14 analyses — failed OOS comprehensively; bullish intraday (15min, 1H) confirmed robustly | Applied in README §1–§8 — all not-confirmed buckets labeled ✗ NOT CONFIRMED; none silently dropped (Phase 3) |
| SMT lift is confirmed at 15min but not established at Daily bearish / 4H ES bearish | OOS run evaluated all 32 smt_cisd buckets; 26/32 confirmed; 4H ES bear and Daily ES bear not-confirmed | Applied in README §8 — those buckets labeled ✗ NOT CONFIRMED; 15min w/ SMT (+2–4pp lift) published as confirmed (Phase 3) |

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
*Last updated: 2026-06-14 after Phase 4 (Test-Gated Modular Refactor) completion*
