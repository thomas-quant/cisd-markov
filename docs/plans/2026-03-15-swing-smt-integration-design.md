# Swing SMT Integration Design

## Goal

Restore Swing SMT support in this repo by using the external SMT library's historical backtesting API instead of per-row detector calls.

## Scope

This design covers:

- using `scan_smts_historical(...)` from `/mnt/e/backup/code/Finance/Misc/SMT`
- integrating only `Swing SMT` events
- annotating CISD bars with left-only SMT tolerance
- restoring the barrier-style SMT split (`smt_cisd`)
- making the annotation reusable for later `fan_smt` and `export_html` work

Out of scope for this pass:

- integrating `micro` or `fvg` SMTs
- rebuilding the full fan chart and HTML report stack
- changing SMT library behavior
- changing the existing CISD or barrier definitions

## Current State

The checked-in `cisd_analysis.py` no longer contains SMT logic. The docs still describe SMT-dependent outputs, but the live code only runs local barrier analyses.

The SMT library now exposes `scan_smts_historical(...)`, which is the correct backtesting path for this research repo.

## Requirements

- Use only `Swing SMT` events from the SMT library.
- Match a CISD at bar `t` to same-direction Swing SMT events created in `[t-2, t]`.
- Do not use right-side tolerance.
- Ignore `sweeping_asset` for the main `w/ SMT` vs `no SMT` classification.
- Preserve instrument-relative role metadata so each row can still say whether that instrument swept or failed to sweep.
- Fail clearly for SMT-dependent commands if the external package cannot be imported or if the paired indices are not aligned.

## Approaches Considered

### 1. Precompute historical Swing SMT events once per timeframe and annotate CISD rows

Run the external historical scanner once on the paired timeframe data, then vectorize the CISD-to-SMT join.

Pros:

- Uses the library's intended backtesting API
- Keeps SMT definitions in one place
- Fast enough for repeated slicing and charting
- Reusable for future SMT fan and HTML features

Cons:

- Requires a paired-data helper instead of instrument-isolated processing
- Needs explicit handling for uppercase OHLC columns required by the SMT library

### 2. Call the detector on each CISD bar with a rolling window

Recreate the old per-event logic with `check_swing_smt(...)`.

Pros:

- Small conceptual change

Cons:

- Throws away the vectorized historical path
- Slower and less aligned with the current SMT library design
- More likely to drift from the library's historical/backtesting semantics

### 3. Keep SMT out of the code path and rely on precomputed artifacts

Pros:

- No implementation effort

Cons:

- Not maintainable
- Not reproducible
- Does not satisfy the requirement

## Chosen Design

Use approach 1.

## Architecture

Add a paired-timeframe preparation path that:

1. resamples NQ and ES to the requested timeframe
2. prepares the lowercase CISD DataFrames as today
3. builds uppercase OHLC copies for the SMT library
4. runs `scan_smts_historical(...)` once with:
   - `asset_names=("NQ", "ES")` or the repo-standard pair ordering
   - `lookback_period=20`
   - `enable_micro=False`
   - `enable_swing=True`
   - `enable_fvg=False`
5. filters the returned event table to `Bullish Swing SMT` and `Bearish Swing SMT`
6. annotates both prepared DataFrames with reusable Swing SMT columns

The annotation helper becomes the single source for all repo-level Swing SMT usage.

## Annotation Semantics

For a CISD on bar `t`:

- `has_swing_smt` is `True` if a same-direction Swing SMT exists with `created_ts` in `[t-2, t]`
- `swing_smt_tag` is:
  - `"w/ SMT"` when `has_swing_smt=True`
  - `"no SMT"` otherwise
- `swing_smt_match_ts` is the latest matching `created_ts` in `[t-2, t]`, else `NaT`
- `swing_smt_role` is:
  - `"swept"` if the instrument matches the event's `sweeping_asset`
  - `"failed_to_sweep"` if the instrument matches the event's `failing_asset`
  - `"none"` if no event matched

If multiple same-direction events fall in `[t-2, t]`, the latest one wins for `match_ts` and `role`.

The main SMT classification is pair-level. Sweeper identity is only retained as an auxiliary instrument-relative tag.

## Data Flow

1. Load minute data for both instruments.
2. Resample both to the target timeframe.
3. Run existing CISD preparation on each instrument.
4. Create uppercase OHLC views with identical aligned `DatetimeIndex` values.
5. Scan historical Swing SMT events once for the pair.
6. Build per-bar directional event markers from `created_ts`.
7. Apply a left-looking 3-bar window over those markers.
8. Annotate each prepared instrument DataFrame with the Swing SMT fields.
9. Feed those annotated frames into SMT-aware analyses.

## Failure Handling

- If the SMT package path is missing or import fails, only SMT-dependent commands should raise, with a clear error naming the missing dependency.
- If the resampled NQ/ES indices do not align exactly, fail before calling the SMT library.
- If no Swing SMT matches a CISD row in `[t-2, t]`, emit the default non-match tags:
  - `has_swing_smt=False`
  - `swing_smt_tag="no SMT"`
  - `swing_smt_match_ts=NaT`
  - `swing_smt_role="none"`

## Testing Strategy

Add tests for the annotation helper and the restored SMT barrier analysis.

### Annotation tests

- same-direction match on `t`
- same-direction match on `t-1`
- same-direction match on `t-2`
- no match on `t-3`
- role resolution to `swept`
- role resolution to `failed_to_sweep`
- no-match default tags

### Integration test

- restore `smt_cisd` and verify its split counts come from the vectorized annotation, not detector calls

### Residual Risks

- The current repo has no existing test harness, so adding focused regression tests may require light restructuring first.
- The repo docs currently describe features that are not present in code; implementation should either restore them or narrow the docs in a follow-up.
