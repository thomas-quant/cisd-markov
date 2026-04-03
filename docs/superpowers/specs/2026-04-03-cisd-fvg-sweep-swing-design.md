# CISD FVG, Sweep, and Swing Extension Design

## Goal

Add the next CISD research extensions as reusable annotations plus five analyses:

- `cisd_fvg`
- `fvg_hold`
- `cisd_fvg_interaction`
- `sweep`
- `sssf_swing`

The implementation should follow the current repo pattern where event semantics are computed once in the preparation layer and the analysis functions only consume prepared tags.

## Scope

This design covers:

- same-direction FVG creation tags linked to CISD bars
- FVG hold and fail outcomes under two failure modes
- same-direction sweep tags near CISD bars
- direction-specific swing tags on `candle[-1]` and `candle[0]`
- new compute and chart functions
- CSV flattening and standalone figure registration
- focused regression tests for the new annotation and analysis paths

This design does not cover:

- non-direction-matched FVG or sweep links
- sweep timing breakdowns beyond the current binary split
- additional post-CISD follow-through or machine-learning ideas from the backlog

## Existing Context

The current repo computes CISD features in `prepare()` and uses `prepare_pair()` only when a paired external dependency is needed for SMT. Existing analyses either:

- measure CISD barrier success rate with `LOOKAHEAD = 2`, or
- split those CISDs by precomputed tags such as `swing_smt_tag`

That same shape should be preserved here. The new FVG, sweep, and swing research should be computed from a single prepared instrument DataFrame and should not require paired processing.

## Definitions

### CISD Indexing

- `candle[0]` is the CISD candle at index `t`
- `candle[-1]` is the previous bar
- `candle[1]` is the next bar

### FVG Formation

Use the standard 3-candle wick-to-wick rule with the middle candle indexed as `m`.

- bullish FVG: `high[m-1] < low[m+1]`
- bearish FVG: `low[m-1] > high[m+1]`

Only same-direction FVGs may link to a CISD.

Two CISD-linked FVG buckets are required:

- `mid0`: the CISD bar itself is the FVG middle candle, so `m = t`
- `mid1`: the next bar is the FVG middle candle, so `m = t+1`

### FVG Hold Window

FVG hold is evaluated over `10` bars starting from the FVG middle candle, not from the CISD bar.

### FVG Failure Modes

Each FVG is evaluated under two separate failure modes.

`close_through_near_edge`

- bullish: fail if a later bar closes below FVG candle 1 high
- bearish: fail if a later bar closes above FVG candle 1 low

`wick_break_far_extreme`

- bullish: fail if a later bar's low breaks FVG candle 1 low
- bearish: fail if a later bar's high breaks FVG candle 1 high

Here, "FVG candle 1" means the left candle in the 3-bar FVG pattern, i.e. `m-1`.

### Sweep Definition

Sweep is direction-specific relative to the CISD:

- bullish CISD links only to low sweeps
- bearish CISD links only to high sweeps

The CISD bar itself does not need to be the sweep bar. A CISD is tagged `w/ sweep` if a qualifying same-direction sweep occurs anywhere in the inclusive window `[t-4, t]`.

The swept level must come from a swing point detected using a `20`-bar lookback. The sweep event is currently binary only; no timing breakdown is included in this pass.

### Swing Definition

Use a 3-candle swing rule with `N = 1`.

- swing high: a bar high is higher than the bar on its left and right
- swing low: a bar low is lower than the bar on its left and right

The swing checks are direction-specific:

- bullish CISD uses swing lows
- bearish CISD uses swing highs

Two CISD-linked buckets are required:

- `prev_bar_is_swing`: `candle[-1]` is the relevant swing point
- `cisd_bar_is_swing`: `candle[0]` is the relevant swing point

## Chosen Approach

Use reusable annotation helpers in the preparation layer.

This is preferred over rediscovering events inside each `compute_*` function because:

- event semantics live in one place
- multiple analyses can share the same tags
- CSV and chart code stay simple
- the design matches the existing `smt_cisd` pattern

## Architecture

Extend the single-instrument preparation path after `prepare()` creates the core CISD columns.

Add an annotation pass that computes:

- direction-specific swing points
- FVG creation tags for `mid0` and `mid1`
- FVG hold/fail outcomes for both failure modes and both FVG buckets
- same-direction sweep presence in `[t-4, t]`
- direction-specific swing tags for `candle[-1]` and `candle[0]`

The analysis functions then read only those prepared columns.

## Annotation Surface

The prepared DataFrame should expose a stable set of columns for downstream analyses.

### FVG Creation Tags

- `has_dir_fvg_mid0`
- `has_dir_fvg_mid1`

These are true only when the linked FVG direction matches `cisd_type`.

### FVG Hold Outcome Tags

Each column stores one of:

- `"held"`
- `"failed"`
- `"none"`

Columns:

- `fvg_mid0_hold_close_near`
- `fvg_mid0_hold_wick_far`
- `fvg_mid1_hold_close_near`
- `fvg_mid1_hold_wick_far`

`"none"` means that the CISD row did not have a same-direction FVG for that bucket or there was insufficient future context to evaluate it.

### Sweep Tag

- `has_dir_sweep`

This is a binary same-direction tag derived from swing levels and the `[t-4, t]` search window.

### Swing Tags

- `prev_bar_is_dir_swing`
- `cisd_bar_is_dir_swing`

These are direction-specific relative to `cisd_type`.

## Analysis Design

### `cisd_fvg`

Measure CISD barrier success rate split by:

- `mid0_fvg`
- `mid1_fvg`
- baseline `no_fvg`

This answers whether CISDs that create same-direction FVGs have different barrier success rates, while keeping the two FVG creation buckets separate.

### `fvg_hold`

Measure FVG hold rate over the 10-bar window from the FVG middle candle.

Report results separately for:

- `mid0`
- `mid1`

and for each failure mode:

- `close_through_near_edge`
- `wick_break_far_extreme`

This analysis is not a CISD barrier analysis. It reports FVG survival outcomes directly.

### `cisd_fvg_interaction`

Measure parent CISD barrier success rate split by whether the linked same-direction FVG:

- `held`
- `failed`

Report results separately for:

- `mid0`
- `mid1`

and for each failure mode:

- `close_through_near_edge`
- `wick_break_far_extreme`

### `sweep`

Measure CISD barrier success rate split by:

- `w/ sweep`
- `no sweep`

This uses the binary same-direction sweep tag only.

### `sssf_swing`

Measure CISD barrier success rate split by:

- `prev_bar_is_swing`
- `cisd_bar_is_swing`
- baseline `neither`

The swing tags remain direction-specific.

## Output Integration

All five new analyses should be registered in `ANALYSES`.

Recommended output placement:

- `cisd_fvg`: standalone
- `fvg_hold`: standalone
- `cisd_fvg_interaction`: standalone
- `sweep`: standalone
- `sssf_swing`: standalone

This avoids overcrowding the mixed per-timeframe figures and keeps the FVG-heavy outputs readable.

`build_csv_rows()` must be extended so the new nested result shapes flatten cleanly into the existing long-format CSV schema.

`main()` should register the new standalone keys and filenames in the same way the repo currently does for `volume`, `candle_size`, `size_cross`, and `smt_cisd`.

## Data Flow

1. Load 1-minute data.
2. Resample to each timeframe.
3. Run `prepare()` to compute CISD fields.
4. Run a new single-instrument annotation pass to attach FVG, sweep, and swing research columns.
5. Feed those prepared frames into the new compute functions.
6. Render standalone figures and emit CSV output through the existing paths.

No paired processing or external package dependency is needed for these new analyses.

## Edge Handling

- `mid0` FVG checks require `t-1` and `t+1` to exist.
- `mid1` FVG checks require `t`, `t+1`, and `t+2` to exist.
- Swing tags that require right-side confirmation are false when confirmation bars do not exist.
- FVG hold outcomes return `"none"` when there is no matching same-direction FVG bucket or when future context is insufficient for evaluation.
- If multiple qualifying sweep events occur in `[t-4, t]`, the CISD still remains a single binary `w/ sweep`.

## Testing Strategy

Add focused regression tests for both annotations and compute functions.

### Annotation tests

- 3-candle swing-high and swing-low detection
- `mid0` same-direction FVG tagging
- `mid1` same-direction FVG tagging
- `close_through_near_edge` failure mode
- `wick_break_far_extreme` failure mode
- binary sweep detection within `[t-4, t]`
- `prev_bar_is_dir_swing`
- `cisd_bar_is_dir_swing`

### Analysis tests

- `compute_cisd_fvg`
- `compute_fvg_hold`
- `compute_cisd_fvg_interaction`
- `compute_sweep`
- `compute_sssf_swing`

Each regression test should verify the nested output shape and at least one non-zero bucket.

### Verification

After implementation:

- run targeted `pytest` for the new tests
- run a CLI smoke command for the new analysis keys
- verify the expected PNG and CSV outputs are created without runtime errors

## Risks

- `mid1` FVG semantics depend on future bars by design, so the tag is not contemporaneously knowable at the CISD bar. That is acceptable because this repo is doing historical research, not live signaling.
- FVG hold outcomes may have small sample sizes on higher timeframes, especially once split by bucket and failure mode.
- Sweep semantics depend on the exact swing-point implementation. Keeping the swing detector isolated in helpers reduces the risk of inconsistent results between sweep and `sssf_swing`.

## Implementation Boundary

This design is scoped to a single implementation pass in `cisd_analysis.py` plus tests and docs updates. It should not pull in unrelated backlog items such as `candle[1]` follow-through or post-CISD reversal context.
