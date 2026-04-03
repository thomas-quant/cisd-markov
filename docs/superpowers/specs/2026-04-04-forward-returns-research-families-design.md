# Forward Returns Research Families Design

## Goal

Upgrade `output/forward_returns.html` so the forward-returns explorer can slice CISD events by the newly added research dimensions:

- CISD-linked FVG creation
- FVG hold and fail outcomes
- sweep presence
- direction-specific swing position

The page should remain a forward-returns explorer for parent CISDs rather than a duplicate of the standalone barrier-rate charts.

## Scope

This design covers:

- replacing the current hand-maintained HTML artifact with a generated one
- reusing the existing `cisd_analysis.py` preparation and annotation semantics
- preserving the current "core" forward-returns filters
- adding grouped filter families for FVG and structure research
- adding tests for the forward-return bucketing and generated HTML surface

This design does not cover:

- changing the underlying CISD, FVG, sweep, or swing semantics
- adding new research definitions beyond the ones already implemented
- redesigning the visual layout beyond what is needed to expose the new families

## Existing Context

`output/forward_returns.html` currently exists as a checked-in standalone artifact with embedded Plotly data and hard-coded filter rows for:

- timeframe
- SMT
- size cross
- wick position
- consecutive count

There is no checked-in generator for that file today. The newer research analyses were added in `cisd_analysis.py`, but the forward-returns explorer was not updated alongside them, so it has drifted from the current research surface.

## Chosen Approach

Generate `forward_returns.html` from a dedicated builder script and organize the UI by research family.

This is preferred over continuing to hand-edit the output file because:

- the data model becomes reproducible
- the explorer can reuse the same annotations as the analysis charts
- future filter additions become incremental instead of rewriting embedded JSON manually
- the UI avoids an unreadable all-dimensions-at-once filter matrix

## Interaction Model

The page remains a single self-contained HTML file, but gains a top-level family selector.

Global controls:

- `timeframe`
- `family`

Families:

- `core`
- `fvg`
- `structure`

Only the active family's filter rows are visible and applied. Inactive-family filters do not affect the result set.

This keeps the page readable while avoiding a combinatorial explosion of mostly empty filter combinations.

## Filter Families

### Core

The existing forward-returns filters remain under `core`:

- `smt`
- `size_cross`
- `wick`
- `consec`

These should preserve the current page behavior.

### FVG

The `fvg` family exposes CISD-linked FVG metadata:

- `fvg_bucket`
- `fvg_mode`
- `fvg_state`

Allowed values:

- `fvg_bucket`: `all`, `mid0`, `mid1`, `no_fvg`
- `fvg_mode`: `all`, `close_through_near_edge`, `wick_break_far_extreme`
- `fvg_state`: `all`, `held`, `failed`, `none`

Semantics:

- `mid0` means the CISD bar is the FVG middle candle
- `mid1` means the next bar is the FVG middle candle
- `no_fvg` means neither same-direction `mid0` nor `mid1` exists for the parent CISD
- `none` means there was no linked FVG for the selected bucket or there was insufficient future context to classify hold/fail

### Structure

The `structure` family exposes same-direction structural tags attached to the parent CISD:

- `sweep`
- `prev_swing`
- `cisd_swing`

Allowed values:

- `sweep`: `all`, `w/ sweep`, `no sweep`
- `prev_swing`: `all`, `yes`, `no`
- `cisd_swing`: `all`, `yes`, `no`

`prev_swing` maps to `prev_bar_is_dir_swing`. `cisd_swing` maps to `cisd_bar_is_dir_swing`.

## Data Model

Add a dedicated builder script, expected at `scripts/build_forward_returns.py`.

The builder should:

1. load the instrument parquet data once
2. prepare each timeframe using the existing preparation path from `cisd_analysis.py`
3. derive per-CISD forward-return series for the fixed forward horizon
4. aggregate percentile fans for each family-specific filter combination
5. render a self-contained HTML file to `output/forward_returns.html`

The builder must not reimplement CISD, FVG, sweep, or swing semantics. It should consume the same prepared columns already used by the analysis charts.

## Forward-Return Semantics

The page continues to show direction-normalized forward returns for parent CISD events.

Requirements:

- keep the existing forward horizon of `7` bars for parity with the current page
- expose that horizon from one generator constant so the page subtitle and data stay aligned
- aggregate the same percentile bands the current page uses:
  - `5`
  - `25`
  - `50`
  - `75`
  - `95`

Each chart remains:

- `NQ bullish`
- `NQ bearish`
- `ES bullish`
- `ES bearish`

## Aggregation Rules

The builder should generate nested data keyed by:

- timeframe
- family
- instrument
- CISD direction
- family-specific combination key

### Core Aggregation

Use the current dimensions:

- SMT tag
- size cross bucket
- wick group
- consecutive count

This family should match the existing page's event selection semantics.

### FVG Aggregation

The parent CISD set is filtered by:

- creation bucket
- hold-failure mode
- hold/fail state

Rules:

- if `fvg_bucket = mid0`, only use rows where `has_dir_fvg_mid0` is true
- if `fvg_bucket = mid1`, only use rows where `has_dir_fvg_mid1` is true
- if `fvg_bucket = no_fvg`, only use rows where both linked FVG buckets are false
- if `fvg_bucket = all`, allow all parent CISDs
- `fvg_mode` selects which hold-classification column is consulted
- `fvg_state` filters by `held`, `failed`, or `none` under the selected mode

When `fvg_bucket = all`, `fvg_state` still applies against the selected mode using each row's available FVG bucket status. `no_fvg` rows naturally appear as `none`.

When `fvg_mode = all`, the UI should keep `fvg_state = all` and not attempt to merge hold states across both failure modes. State-specific slicing only applies once a concrete mode is selected.

### Structure Aggregation

The parent CISD set is filtered by:

- binary same-direction sweep tag
- binary direction-specific `candle[-1]` swing tag
- binary direction-specific `candle[0]` swing tag

## Rendering Design

`forward_returns.html` stays a self-contained Plotly page.

The page should contain:

- a header with the current subtitle describing the forward horizon
- a global timeframe row
- a global family row
- only the active family's filter rows
- the existing 2x2 chart grid

Client-side rendering should use:

- one state object containing `tf`, `family`, and family filter values
- one key builder per family
- a small embedded `CONFIG` object defining valid filter dimensions and labels
- a nested `DATA` object containing the percentile payloads

If a selected combination has zero events, the cell should render a `No events` annotation rather than failing.

## Testing

Add coverage for the generated forward-returns path rather than only snapshotting the full HTML blob.

Required tests:

- family key generation for `core`, `fvg`, and `structure`
- fixed-fixture aggregation parity for the current `core` behavior
- FVG bucketing across `mid0`, `mid1`, `no_fvg`, and `none`
- structure bucketing for `sweep`, `prev_swing`, and `cisd_swing`
- zero-count combinations returning `n = 0` with no percentile payload
- HTML smoke test confirming the generated file includes the new family config and filter labels

## Edge Cases

- `mid1` and FVG hold-state filters naturally lose rows near the dataset end when future context is insufficient
- `none` must remain distinguishable from `failed`; it includes both no-linked-FVG and insufficient-context cases
- if SMT data is unavailable for a run, the builder may hide the SMT row or mark the config accordingly, matching the current page behavior
- the builder should tolerate empty combinations without emitting invalid Plotly traces

## Output

This change should leave the repo with:

- a checked-in builder script for the forward-returns artifact
- updated tests for the forward-returns aggregation path
- a regenerated `output/forward_returns.html`

The generated page should preserve the old core exploration path and add first-class FVG and structure research slicing on top.
