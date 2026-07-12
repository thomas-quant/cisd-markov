# Phase 10: New Conditioning Features — Magnitude, Session & Volume Anomaly - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 10-new-conditioning-features-magnitude-session-volume-anomaly
**Areas discussed:** Session taxonomy & TF scope, Magnitude bins & population, Volume-anomaly measures, Registration & no-drift

---

## Session taxonomy & timeframe scope

| Option | Description | Selected |
|--------|-------------|----------|
| ICT kill zones | Named windows (Asia/London/NY-AM/NY-PM/lunch) — matches CISD/SMT/FVG vocabulary; opinionated boundaries, many low-n buckets | |
| RTH vs overnight (+ open) | `rth_open`/`rth`/`overnight` — fewest buckets, highest n, best odds of clearing the FDR/walk-forward bar | ✓ |
| Raw hour buckets | Model-agnostic N-hour bins — no baked-in opinion, but harsh FDR penalty and many below-n cells | |
| Kill zones + RTH-open flag | Both a granular kill-zone analysis and a coarse robust split | |

**User's choice:** Pure 3-bucket (`rth_open` / `rth` / `overnight`).
**Notes:** Claude recommended a lean hybrid; user preferred the pure 3-way for maximum statistical power. Sub-decisions resolved via follow-up: **intraday only (15m + 1H)** — not registered on 4H/Daily (a session tag on a multi-session bar is meaningless); **`rth_open` = first 60 min (09:30–10:30 ET)**. Boundaries frozen in one documented constant block, never tuned to results. Index verified tz-naive ET wall-clock → clean hour slicing, no DST math.

---

## Magnitude features — bins & population

| Option | Description | Selected |
|--------|-------------|----------|
| Bins: fixed ATR-multiple | Reuse frozen `candle_size` convention; same bucket meaning in discovery/OOS/walk-forward; no leakage | ✓ |
| Bins: data-driven quantile | Balanced n per bucket, but boundaries differ across the holdout / leak — breaks harness comparability | |
| Pop: per-feature natural population | Signed wick distance over ALL CISDs; sweep depth & FVG size only where the event exists | ✓ |
| Pop: strictly sub-population, all three | Uniform unsigned magnitudes within each event population; throws away the within-wick half | |

**User's choice:** Fixed ATR-multiple bins + per-feature natural population.
**Notes:** User asked for Claude's opinion before deciding; endorsed the recommendation ("yeah, sounds good"). Locked nuances: fixed bin cut points may be shape-informed **once** from the discovery-slice histogram but chosen **outcome-blind** and frozen; signed `wick_distance_atr` bins must place an edge at **0** so the past/within split stays recoverable; sweep depth and FVG size require the annotation to newly carry the pierced swing **level** and the FVG gap **width** (currently only booleans exist).

---

## Volume-anomaly measures

| Option | Description | Selected |
|--------|-------------|----------|
| effort-vs-result | Within-bar `vol ÷ range`/`÷ body` — baseline-free, seasonality-free anchor | ✓ |
| RVOL/z-score — simple trailing baseline | Cheapest; confounded by intraday time-of-day profile (caveated) | |
| RVOL/z-score — session-bucket baseline | Removes coarse seasonality only; overnight bucket keeps its own internal profile | |
| RVOL/z-score — same-time-of-day-slot baseline | Conventional relative-volume; removes the intraday profile fully, incl. inside overnight | ✓ |
| Cross-asset NQ↔ES divergence | SC3-optional; fiddly normalize-then-difference; extra FDR grid cost | (deferred) |

**User's choice:** effort-vs-result + rolling RVOL/z-score with a **same-time-of-day-slot** baseline; **defer** cross-asset divergence.
**Notes:** User led with "normalizing is more honest" re: the time-of-day profile. Claude distinguished the coarse session-bucket baseline from the fine same-time-of-day-slot baseline; user's honesty framing pointed to the fine slot baseline (standard RVOL), confirmed via menu. `K` frozen (~20 slot occurrences); Daily degenerates to a plain rolling baseline. Existing negligible 1-bar `compute_volume` stays untouched. OHLCV-only (no signed/delta order flow) caveat mandatory.

---

## Registration & no-drift

| Option | Description | Selected |
|--------|-------------|----------|
| New standalone analyses, additive-only | Phase 9 pattern; existing binary analyses untouched → base rates byte-stable | ✓ |
| Augment existing compute_wick/sweep/volume in place | Risks moving published rates; breaks characterization tests | |

**User's choice:** Lock the additive-standalone approach & write context.
**Notes:** Grounded in `apply_bh_correction` being **one global BH family** — so existing base rates (`rate/n/successes/ci_low/ci_high/min_n_pass`) are byte-stable when we only add analyses, but existing buckets' `bh_q_value`/`corrected_pass` legitimately shift (expected MHT-01 behavior, documented, not a bug). One new mechanism required: TF-scoping the session analysis to intraday (ANALYSIS_META allow-list preferred, or frequency inference).

---

## Claude's Discretion

- Exact fixed bin cut points per magnitude/volume feature (shape-informed once from discovery, outcome-blind, frozen); signed wick bins with an edge at 0.
- Exact `K` and slot key for the RVOL baseline; whether RVOL+z-score are one analysis or two; effort ratio `÷ range` vs `÷ body` vs both.
- ATR anchoring (default ATR(14) at bar `t`); new column/bucket/analysis names.
- Chart/figure layout; forward-returns & expectancy filter-family wiring (graceful degradation).
- README methodology writeup structure (Phase 7/9 pattern).
- TF-scoping mechanism (ANALYSIS_META allow-list vs frequency inference).

## Deferred Ideas

- ICT kill-zone taxonomy — rejected for the robust 3-bucket split; revisit only if the coarse split shows a pulse.
- Cross-asset NQ↔ES volume divergence — SC3-optional; revisit only if core volume measures clear the bar.
- Session features on Daily/4H — deliberately unregistered (meaningless on multi-session bars).
