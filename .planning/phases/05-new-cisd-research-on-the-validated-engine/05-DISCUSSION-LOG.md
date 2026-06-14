# Phase 5: New CISD Research on the Validated Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-14
**Phase:** 5-New CISD Research on the Validated Engine
**Areas discussed:** Success metric & barrier anchoring, candle[1] bucket definitions, RES-02 regime structure, "Gap" definition on resampled futures

---

## Success metric & barrier anchoring

Mid-discussion the user noted they were out of context and asked for the candle-index convention (`candle[-1]` prev / `candle[0]` CISD / `candle[1]` next / `candle[2]` two-after). After re-orientation the anchoring question was re-asked.

### Q1 — Forward barrier levels (target/stop)

| Option | Description | Selected |
|--------|-------------|----------|
| candle[1]'s own extremes | Self-contained "act at candle[1] close"; risk against candle[1]'s range | |
| candle[0]'s extremes | Keep the CISD's original target/stop; R-unit identical to existing engine | ✓ |
| You decide | Defer to planner | |

**User's choice:** candle[0]'s extremes.

### Q2 — When the candle[0] barrier starts counting (re-asked after re-orientation)

| Option | Description | Selected |
|--------|-------------|----------|
| Start after candle[1] (re-anchor forward) | Evaluate over candle[2]+candle[3]; leakage-free | |
| Keep existing window (candle[1]+candle[2]) | Reuse barrier_hit as the 14 analyses do; comparable but partly mechanical | |
| Both — report side by side | Compute in-window AND re-anchored so the tautology gap is visible | ✓ |

**User's choice:** Both — report side by side.
**Notes:** Claude flagged the near-tautology (candle[1] conditioning bar sits inside the in-window measurement → mechanically inflated). Success metric resolved as barrier-hit (not directional-close) with candle[0] extremes.

---

## candle[1] bucket definitions

### Q1 — "Close beyond candle[1]'s wick" meaning

| Option | Description | Selected |
|--------|-------------|----------|
| candle[1] closes past candle[0]'s high/low | Forward-analog of existing 'wick' analysis | |
| candle[2] closes beyond candle[1]'s high/low | Later bar clears candle[1]'s range | |
| Something else | User-described | |

**User's choice:** "try both i forget" — test both readings.
**Notes:** candle[2]-beyond-candle[1] overlaps RES-02; planner may home it there to avoid double-counting.

### Q2 — Primary bucket structure

| Option | Description | Selected |
|--------|-------------|----------|
| 3-way core + extra cut | against / with-within-candle[0]-wick / with-past-candle[0]-wick, plus candle[2] cut separately | ✓ |
| Simple 2-way headline | with-CISD vs against, wick refinements as sub-tables | |
| Full cross-tab | direction × candle[0]-wick × candle[2]-vs-candle[1] | |

**User's choice:** 3-way core + extra cut.

---

## RES-02 regime structure

### Q1 — One analysis or two

| Option | Description | Selected |
|--------|-------------|----------|
| One analysis with regime buckets | reversal context = a bucket of candle2_gap_context | ✓ |
| Two separate analyses | distinct ANALYSES keys | |
| You decide | Defer to planner | |

**User's choice:** One analysis with regime buckets.

### Q2 — Outcome metric

| Option | Description | Selected |
|--------|-------------|----------|
| Continuation hit-rate only | depressed rate in reversal bucket IS the finding | (Claude's call) |
| Continuation AND explicit reversal barrier | also measure opposite extreme hit first | |
| You decide | Defer to planner | ✓ |

**User's choice:** You decide → Claude chose **continuation hit-rate only** for the first pass; explicit reversal barrier deferred as optional extension.

---

## "Gap" definition on resampled futures

### Q1 — Gap definition

| Option | Description | Selected |
|--------|-------------|----------|
| candle[2].open vs candle[1].close, signed | Captures the Daily/weekend boundary; ~zero intraday | ✓ |
| True non-overlapping gap | candle[2].low > candle[1].high; near-empty on continuous futures | |
| ATR-scaled gap threshold | tunable threshold; still degenerates intraday | |

**User's choice:** Signed candle[2].open − candle[1].close.

### Q2 — Timeframe scope

| Option | Description | Selected |
|--------|-------------|----------|
| All 4 TFs, let the gate tell the truth | no special-casing; Daily/4H carry the signal | ✓ |
| Daily-only | restrict to where gaps exist | |
| You decide | Defer to planner | |

**User's choice:** All 4 TFs.

---

## Claude's Discretion

- **RES-02 outcome metric** — user deferred; Claude chose continuation hit-rate only for the first pass (explicit reversal barrier = optional later extension).
- Neutral / doji candle[1] handling — implementer's call, consistent with the `direction` column's `"neutral"`.
- Standalone vs per-TF charts for the new analyses — default standalone, consistent with peer research analyses.
- Exact bucket-tag strings, `build_manifest_rows` branch shape, `ANALYSIS_META` heights/filenames, new annotation column names.
- Placement of the candle[2]-beyond-candle[1] cut (RES-01 vs RES-02) — planner decides; no double-counting.

## Deferred Ideas

- `post_cisd_ml` (v2, ML-01) — ML model over post-CISD tags.
- Explicit reversal barrier for RES-02 — optional extension, not first pass.
- Multiple-comparisons correction (v2, MHT-01); walk-forward validation (v2, WF-01).
