# Phase 9: SMT Geometry & Invalidation Honesty - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 9-SMT Geometry & Invalidation Honesty
**Areas discussed:** Validity cutoff, Block geometry, Survived/broke split, Buckets & docs

---

## Validity cutoff (the invalidation fix)

### Boundary — SMT breaking exactly on bar `t`

| Option | Description | Selected |
|--------|-------------|----------|
| Strict: exclude break-on-t (`broken_ts > t`) | Require `broken_ts` strictly after `t`; if it's dying as the CISD forms, don't credit it. Matches roadmap "invalidated at or before t" wording and the honesty theme. | ✓ |
| Inclusive: keep break-on-t (`broken_ts >= t`) | SMT still standing at the open of bar `t`, so credit it; only exclude breaks strictly before `t`. Keeps more w/ SMT samples. | |

**User's choice:** Strict — exclude break-on-t.
**Notes:** Framing established up front that the validity test compares `broken_ts` to `t`, never the `status` flag (status filtering would be look-ahead bias).

### Where the now-excluded (broke-before-t) CISDs land

| Option | Description | Selected |
|--------|-------------|----------|
| Fold into `no SMT` | Treat as a no-valid-SMT event; keeps the clean binary split. | |
| Separate `expired SMT` bucket | Give broke-by-t CISDs their own reported bucket for transparency; shows how many were being mis-credited. | ✓ |

**User's choice:** Separate `expired SMT` bucket → three-way split `w/ SMT` / `expired SMT` / `no SMT`.

### Matching semantics — latest-created dead but earlier one valid

| Option | Description | Selected |
|--------|-------------|----------|
| Check only the matched (latest-created) SMT | If the latest-created in-window SMT is dead → expired. Minimal change, faithful to SC1's "the matched SMT." | ✓ |
| Any still-valid in-window SMT → w/ SMT | Re-search the window for the latest still-valid SMT; new selection rule beyond fixing the bug. | |

**User's choice:** Check only the matched (latest-created) SMT.

---

## Block geometry (magnitude + containment)

### `smt_block_size_atr` definition

| Option | Description | Selected |
|--------|-------------|----------|
| SMT swing-bar range (high−low of the reference bar) | `block_high`/`block_low` = high/low of the `reference_timestamp` bar on the annotated instrument, /ATR(14). Most literal, same-instrument, role-independent. | ✓ |
| Sweep displacement (extreme vs the instrument's SMT level) | Distance from the instrument's own SMT level to the actual extreme, /ATR. "SMT strength," role-dependent. | |
| Researcher picks the most faithful computable definition | Defer to the phase researcher, user reviews before lock. | |

**User's choice:** SMT swing-bar range (high−low of the reference bar).
**Notes:** Surfaced that the roadmap's `block_high − block_low` cannot be a cross-asset `reference_price − invalidation_level` subtraction (~10× scale difference between NQ and ES).

### `cisd_in_smt_block` containment strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Body fully inside the zone | Both open and close within `[block_low, block_high]`. Cleanest reading. | ✓ |
| Body overlaps the zone | Any overlap between body range and block range. Lenient. | |
| Body midpoint inside the zone | Body 50% level within the block. Middle ground. | |

**User's choice:** Body fully inside the zone (open–close, wicks excluded).

---

## Survived-vs-broke diagnostic split (SC4)

### Window defining "broke in window"

| Option | Description | Selected |
|--------|-------------|----------|
| Barrier lookahead t..t+2 (LOOKAHEAD) | Broke = `broken_ts` in `(t, t+2]`; same horizon as the barrier outcome, directly comparable. | ✓ |
| Fixed longer window (e.g. 10 bars) | Independent horizon (like FVG_HOLD_LOOKAHEAD); catches slower breaks but decouples survival from outcome. | |
| Until the barrier resolves | Break before target/stop hit; variable per event. | |

**User's choice:** Barrier lookahead t..t+2.

### Reporting shape

| Option | Description | Selected |
|--------|-------------|----------|
| Two full validated sub-buckets alongside aggregate w/ SMT | `w/ SMT & survived` + `w/ SMT & broke` each first-class (full n/CI/FDR/WF); aggregate w/ SMT also reported; population never filtered. | ✓ |
| Descriptive counts only on the aggregate row | Lighter annotation without the full corrected harness. | |

**User's choice:** Two full validated sub-buckets alongside the un-split aggregate.

---

## Buckets & docs

### Where the `swing_smt_role` split lives

| Option | Description | Selected |
|--------|-------------|----------|
| New standalone analysis (e.g. `smt_role`) | Own ANALYSES entry + standalone figure; keeps smt_cisd's clean triple; one-analysis-one-question convention. | ✓ |
| Extra dimension inside smt_cisd | Fewer files but multiplies buckets and shrinks per-cell n. | |

**User's choice:** New standalone analysis (`smt_role`).

### Documenting the before/after SMT rate change

| Option | Description | Selected |
|--------|-------------|----------|
| New README methodology section + refresh section 8 | Dedicated "SMT Invalidation Honesty (v2.0)" subsection (before/after rates & n deltas, Phase 7 pattern) + updated section 8 table. Before = current numbers, no snapshot ceremony. | ✓ |
| Update section 8 in place with a before/after note | More compact; methodology change less prominent. | |

**User's choice:** New README methodology section + refresh section 8.

---

## Claude's Discretion

- Exact ATR anchoring for `smt_block_size_atr` (bar `t` vs reference bar — default bar `t`).
- Bucket thresholds for continuous `smt_block_size_atr` (follow existing candle_size convention).
- Whether `expired SMT` / `smt_role` buckets also carry geometry features.
- How the new columns thread through `build_forward_returns.py` / `build_expectancy.py`.
- Exact file/function structure for the before/after documentation script.
- Column/bucket naming for the new features and buckets.

## Deferred Ideas

None — discussion stayed within phase scope. Continuous-magnitude / session / volume families (Phase 10, RES-07) and micro/FVG SMT signals were explicitly kept out.
