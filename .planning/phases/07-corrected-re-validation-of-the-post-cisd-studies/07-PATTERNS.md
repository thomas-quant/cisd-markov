# Phase 7: Corrected Re-Validation of the Post-CISD Studies - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 5 (4 modified, 1 possibly new script per D-09 discretion)
**Analogs found:** 5 / 5 (all patterns exist in-repo; this phase extends existing files rather than creating new modules, except optionally a new sibling verdict script)

All line numbers below were confirmed live against the current tree (2026-07-11) and match CONTEXT.md's canonical_refs almost exactly (`barrier_hit_forward` at line 63, `compute_candle1_followthrough` at line 547, `compute_post_cisd_context` at line 596, `chart_post_cisd_context` at line 336, `determine_verdict` at line 69 — all confirmed exact).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `cisd_barriers.py` (new `barrier_hit_reversal`-style function, sibling of `barrier_hit_forward`) | utility/compute | transform (row-window scan) | `cisd_barriers.py:63` `barrier_hit_forward` | exact (same file, same window semantics, D-05) |
| `cisd_barriers.py` (`compute_post_cisd_context`, modified to add reversal/neither tags to `failed_gap_against`) | service/compute | CRUD-like aggregation (transform) | `cisd_barriers.py:596` `compute_post_cisd_context` itself (in-place extension) | exact — modifying existing function, not writing a new one |
| `cisd_charts.py` (`chart_post_cisd_context`, modified `_TAGS` list) | component/chart | transform | `cisd_charts.py:336` `chart_post_cisd_context` itself | exact — in-place `_TAGS` extension |
| `scripts/build_validation.py` (no changes needed to dispatch; D-09 verdict computation may live here or in a new sibling script) | service (batch/CLI) | batch | `scripts/build_reconcile_findings.py` (`determine_verdict`, `reconcile`) | exact — same "read manifests, compute verdict, write CSV" shape |
| New verdict script (if Claude's-discretion choice per D-09, e.g. `scripts/build_post_cisd_verdict.py`) OR scoped addition inside `build_reconcile_findings.py` | service (batch/CLI) | batch | `scripts/build_reconcile_findings.py` (whole file, ~192 lines) | exact — this is the direct template to clone/extend |
| `README.md` (new "Post-CISD Context — Corrected Re-Validation (v2.0)" section + D-04 disclaimer) | doc/config | transform (hand-authored from script output) | `README.md:378-396` "Validation Methodology — Harder Evidence Bar (v2.0)" + `README.md:12-26` "Key Findings" badge legend | exact — both are direct structural templates |

## Pattern Assignments

### `cisd_barriers.py` — new reversal-barrier check (sibling of `barrier_hit_forward`)

**Analog:** `cisd_barriers.py:63-80` (`barrier_hit_forward`)

**Full source to clone/adapt** (lines 63-80):
```python
def barrier_hit_forward(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> bool:
    """Re-anchored forward barrier: same candle[0] target/stop but lookahead starts at idx+2.

    Equivalent to barrier_hit but the window covers candle[2]+candle[3] instead of
    candle[1]+candle[2].  Returns False when idx+2 is out of range (no hit recorded).
    Used by compute_candle1_followthrough for the leakage-free forward window.
    """
    for j in range(2, LOOKAHEAD + 2):
        if idx + j >= len(df):
            break
        bar = df.iloc[idx + j]
        if ct == "bullish":
            if bar["low"] <= row["low"]:    return False   # stop
            if bar["high"] >= row["high"]:  return True    # target
        else:
            if bar["high"] >= row["high"]:  return False   # stop
            if bar["low"] <= row["low"]:    return True    # target
    return False
```

**D-06 requirement:** the reversal check needs THREE outcomes (continuation / reversal / neither), not the boolean collapse above. Per D-05/D-06, write a new function (e.g. `barrier_outcome_forward(df, idx, row, ct) -> str` returning `"continuation" | "reversal" | "neither"`) that walks the identical `range(2, LOOKAHEAD + 2)` window and returns on first touch of either side, defaulting to `"neither"` if the loop exhausts. `barrier_hit_forward` itself should NOT be modified (behavior-preservation invariant — other callers like `compute_candle1_followthrough` depend on its current bool contract); add a new sibling function instead. `compute_post_cisd_context`'s existing `failed_gap_against` call site can then derive `runs` (continuation) from this same three-way function without a second df scan, or call the existing `barrier_hit_forward` for continuation and a new stop-check for reversal — either is compatible with the `{total, runs}` dict shape provided the new reversal/neither tags are separate dict keys (Claude's discretion in CONTEXT.md).

**Imports pattern** (`cisd_barriers.py:17-21`, already present, no new imports needed for this function — pure `numpy`/`pandas` row access):
```python
import numpy as np
import pandas as pd
from typing import NamedTuple

from cisd_data import LOOKAHEAD, MAX_CONSEC, FVG_HOLD_LOOKAHEAD
```

---

### `cisd_barriers.py` — `compute_post_cisd_context` (modify in place)

**Analog:** itself, `cisd_barriers.py:596-650` (read in full above). Key excerpt showing the `failed_gap_against` bucket that needs the new reversal/neither tags wired in (lines 609-642):
```python
    _GAP_TAGS = {
        "gap_with":    "failed_gap_with",
        "gap_against": "failed_gap_against",
        "flat":        "failed_gap_flat",
    }
    stats = {
        ct: {
            "failed_gap_with":           {"total": 0, "runs": 0},
            "failed_gap_against":        {"total": 0, "runs": 0},
            "failed_gap_flat":           {"total": 0, "runs": 0},
            "candle2_past_candle1_wick": {"total": 0, "runs": 0},
        }
        for ct in ("bullish", "bearish")
    }
    ...
    for pos in event_pos:
        ...
        # Gap buckets — only if candle[1] failed (precondition)
        if failed_arr[pos]:
            gap_tag = _GAP_TAGS.get(gap_dir_arr[pos], "failed_gap_flat")
            stats[ct][gap_tag]["total"] += 1
            if barrier_hit_forward(df, pos, row, ct):
                stats[ct][gap_tag]["runs"] += 1
```
Pattern to follow (per Claude's Discretion in CONTEXT.md): add new top-level dict keys (not nested under `failed_gap_against`) such as `failed_gap_against_reversal` and `failed_gap_against_neither`, each shaped `{"total": int, "runs": int}` to match the existing `{ct: {tag: {total, runs}}}` shape that `build_manifest_rows`'s generic `else` branch (`scripts/build_validation.py:299-304`) already consumes with zero changes needed. Populate them only inside the `if failed_arr[pos] and gap_tag == "failed_gap_against":` branch, using the new reversal-check function's three-way result.

**Data source columns already precomputed** (`cisd_data.py:206-308`, no changes needed — confirms the reversal barrier reuses existing annotation columns, nothing new to compute upstream):
```python
candle1_failed_followthrough_lst = [False] * n    # True when c[1] fails to close past c[0] extreme
candle2_gap_dir_lst              = ["flat"] * n   # "gap_with" | "gap_against" | "flat"
candle2_past_candle1_wick_lst    = [False] * n    # Reading B: c[2] closes past c[1] wick
```

---

### `cisd_charts.py` — `chart_post_cisd_context` (modify `_TAGS` list only)

**Analog:** itself, `cisd_charts.py:336-356`:
```python
def chart_post_cisd_context(ax, data_nq, data_es):
    # Tag order: gap_with (most aligned), gap_against (reversal context), gap_flat, Reading B
    _TAGS = [
        ("failed_gap_with",          1.0),
        ("failed_gap_against",       0.7),
        ("failed_gap_flat",          0.45),
        ("candle2_past_candle1_wick", 0.85),
    ]
    rows = []
    for instr, data in (("NQ", data_nq), ("ES", data_es)):
        for ct in ("bullish", "bearish"):
            for tag, alpha in _TAGS:
                d = data[ct][tag]
                rows.append((f"{instr} {ct.capitalize()} {tag}  (n={d['total']:,})",
                             pv(d["runs"], d["total"]),
                             COLORS[instr][ct],
                             alpha))
    bars = [ax.barh(r[0], r[1], color=r[2], alpha=r[3], height=0.55) for r in rows]
    for b in bars:
        _bar_label(ax, b)
    _style_ax(ax, "Post-CISD Context (Candle[1] Failed + Candle[2] Gap)")
```
Per CONTEXT.md's Established Patterns note (line 79), only the `_TAGS` list needs a new entry (or two) appended for the reversal outcome tag(s), e.g. `("failed_gap_against_reversal", 0.55)`. No restructuring of the render loop.

---

### D-09 verdict computation — new script or scoped addition

**Analog:** `scripts/build_reconcile_findings.py` (full file, 192 lines — read in full above). This is the direct template. Key excerpts:

**Imports/path-setup pattern** (lines 22-40):
```python
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import MIN_N

DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
OOS_MANIFEST_PATH       = REPO_ROOT / "output" / "validation_manifest_oos.csv"
FINDINGS_PATH           = REPO_ROOT / "output" / "validation_findings.csv"
```
For the D-09 script, this becomes a THREE-way read (discovery + OOS + walkforward manifests, all already populated per CONTEXT.md's Integration Points), scoped with a `analysis.isin(["post_cisd_context", "candle1_followthrough"])` filter (D-01) before any verdict logic runs.

**Verdict function pattern** (lines 57-113, `_side` + `determine_verdict`) — this is the template for the new D-02 three-condition verdict (`corrected_pass AND wf_verdict == "wf-robust" AND same-side OOS`):
```python
def _side(r: float) -> int:
    """Return 1 if r > 0.50, -1 if r < 0.50, 0 if r == 0.50 exactly.

    Exact 0.50 is treated as neither side — no directional evidence.
    """
    if r > 0.50:
        return 1
    if r < 0.50:
        return -1
    return 0  # exact tie — neither side


def determine_verdict(
    discovery_rate: float,
    discovery_n: float | None,
    oos_rate: float,
    oos_n: float | None,
) -> str:
    # D-01: eligibility gate — discovery sample size
    if pd.isna(discovery_n) or float(discovery_n) < MIN_N:
        return "below-n"
    # D-03 / D-02: eligible bucket — check OOS evidence
    if pd.isna(oos_n) or float(oos_n) == 0 or pd.isna(oos_rate):
        return "not-confirmed"
    # D-02: confirmed iff both rates are on the same non-boundary side of 0.50.
    if _side(discovery_rate) != 0 and _side(oos_rate) != 0 and _side(discovery_rate) == _side(oos_rate):
        return "confirmed"
    return "not-confirmed"
```
Note there is an identical `_side` helper already duplicated in `scripts/build_validation.py:393` — the D-09 script should import/reuse one of these rather than triplicating it (project has no shared `utils.py`; either import from `build_reconcile_findings` or from `build_validation`, matching existing precedent of scripts importing each other's helpers where needed — check for existing cross-script imports before choosing).

**Merge + write pattern** (lines 118-186, `reconcile()`) — template for the D-09 script's I/O shape (outer merge on bucket keys, apply verdict row-wise, write CSV with summary print):
```python
    disc = pd.read_csv(DISCOVERY_MANIFEST_PATH)
    oos  = pd.read_csv(OOS_MANIFEST_PATH)
    disc_cols = _MERGE_KEYS + ["rate", "n", "ci_low", "ci_high"]
    disc_sel  = disc[disc_cols].rename(columns={...})
    oos_cols = _MERGE_KEYS + ["rate", "n"]
    oos_sel  = oos[oos_cols].rename(columns={...})
    merged = disc_sel.merge(oos_sel, on=_MERGE_KEYS, how="outer")
    merged["verdict"] = merged.apply(lambda row: determine_verdict(...), axis=1)
    result = merged[_OUTPUT_COLS]
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(FINDINGS_PATH, index=False)
    verdict_counts = result["verdict"].value_counts()
    total = len(result)
    print(f"[ok] wrote {FINDINGS_PATH} ({total} rows)")
    for verdict, count in verdict_counts.items():
        print(f"     {verdict:20s}: {count}")
```
For D-09, the merge needs to additionally pull `corrected_pass` from the discovery manifest (already present per Phase 6, confirmed by CONTEXT.md's Integration Points) and `wf_verdict` from `output/validation_manifest_walkforward.csv` (already present, confirmed live: 640 rows for `post_cisd_context`), then apply D-02's three-condition AND and D-03's per-tag majority roll-up (group by `analysis`+`bucket`-prefix-tag, count individually-cleared buckets, majority wins).

**Walk-forward source functions to read (no changes needed, already generic across all ANALYSES keys):**
- `bh_correct` — `scripts/build_validation.py:129-190`
- `apply_bh_correction` — `scripts/build_validation.py:309-348`
- `evaluate_fold` — `scripts/build_validation.py:406-445`
- `walk_forward_verdict` — `scripts/build_validation.py:448-479`

`build_manifest_rows`'s generic dispatch branch (`scripts/build_validation.py:299-304`) needs NO changes — it already handles the `{ct: {tag: {total, runs}}}` shape that the new reversal tags will use:
```python
            else:
                # Generic: smt_cisd, cisd_fvg, sweep, sssf_swing
                # shape: {dir: {tag: {"total", "runs"}}}
                for ct in ("bullish", "bearish"):
                    for tag, d in data[ct].items():
                        emit(key, instrument, ct, tag, d["total"], d["runs"])
```

---

### `README.md` — new corrected-verdict section + D-04 disclaimer

**Analog A — badge/legend convention** (`README.md:16-26`, "How to read these tables"):
```markdown
### How to read these tables

All rates are **discovery-slice rates** (oldest ~70% of data; OOS boundary = `2024-04-30`). Full-history rates are not reported — every number went through the validation harness.

- **N** = discovery sample size
- **95% CI** = Wilson score interval on the discovery slice (pure-Python, no dependencies)
- **✓ CONFIRMED** = eligible (n ≥ 50 on discovery) and the OOS rate held the same side of 50%
- **✗ NOT CONFIRMED** = eligible but the OOS rate did not hold — a retired hypothesis, not a finding
- **below-n / not a finding** = discovery n < 50; shown so the bucket can be watched as n grows

**`below-n` and `✗ NOT CONFIRMED` are different states.** `below-n` means the bucket never had enough data to evaluate — it may be real or may not. `✗ NOT CONFIRMED` means the bucket was fully evaluated and the edge did not replicate out-of-sample; it should not be published as a finding.
```
D-08 says the new section should extend this vocabulary with a 4th tier (e.g. `✓✓ CLEARS CORRECTED BAR` / whatever wording matches D-02's three-way AND) rather than inventing an unrelated one.

**Analog B — methodology writeup structure** (`README.md:378-396`, "Validation Methodology — Harder Evidence Bar (v2.0)") is the direct template for how Phase 7's own methodology prose should be structured (bold sub-heads, bullet list of mechanics, explicit column names, explicit script invocation). The natural home for the D-04 transparency disclaimer is either inside this existing section (append a bullet) or in the "Key Findings" intro (`README.md:12-14`) — both are Claude's-discretion per CONTEXT.md.

---

## Shared Patterns

### Barrier window semantics (D-05)
**Source:** `cisd_barriers.py:63-80` (`barrier_hit_forward`)
**Apply to:** the new reversal-check function — MUST reuse the identical `range(2, LOOKAHEAD + 2)` loop bounds and `idx + j >= len(df)` bounds guard so continuation/reversal/neither are measured on the exact same window and population (D-05/D-06).

### `{ct: {tag: {total, runs}}}` dict shape
**Source:** every `compute_*` function in `cisd_barriers.py` (e.g. `compute_post_cisd_context`, `compute_sweep`)
**Apply to:** any new reversal-outcome tags added to `compute_post_cisd_context`'s return dict — must stay flat `{ct: {new_tag: {"total": int, "runs": int}}}`, not nested, so `build_manifest_rows`'s generic dispatch branch requires zero changes.

### Same-side-of-0.50 verdict logic
**Source:** `scripts/build_reconcile_findings.py:57-66` (`_side`) and `:69-113` (`determine_verdict`); duplicated already in `scripts/build_validation.py` for `evaluate_fold`.
**Apply to:** the new D-09 verdict script's per-condition checks (discovery vs OOS same-side is one of the three ANDed conditions in D-02).

### Script CLI/path-setup boilerplate
**Source:** `scripts/build_reconcile_findings.py:22-40` and `scripts/build_validation.py:1-20`
**Apply to:** any new sibling script — `REPO_ROOT` sys.path injection, module-level `Path` constants for each manifest, `from cisd_analysis import ...` for shared constants (`MIN_N`, etc.).

## No Analog Found

None. All target files/functions have a direct, in-repo analog — this phase is purely extension of existing patterns (reversal barrier mirrors `barrier_hit_forward`; verdict script mirrors `build_reconcile_findings.py`; README section mirrors the existing "Validation Methodology" + "Key Findings" sections).

## Metadata

**Analog search scope:** `cisd_barriers.py`, `cisd_charts.py`, `cisd_data.py`, `scripts/build_validation.py`, `scripts/build_reconcile_findings.py`, `README.md`
**Files scanned:** 6 (all files explicitly named in CONTEXT.md's canonical_refs and code_context)
**Pattern extraction date:** 2026-07-11
</content>
