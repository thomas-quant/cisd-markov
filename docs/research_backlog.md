# Research Backlog

Planned research ideas for this repo live here instead of in the main README. Keep `README.md` focused on what the project does now and what the current results show.

## Status Format

Use one of these tags for each item:

- `[next]` ready to test soon
- `[idea]` worth exploring
- `[in_progress]` currently being implemented or analyzed
- `[done]` completed and reflected in the code or README
- `[dropped]` decided against

When an item graduates into the live analysis surface or published findings, move the result into `README.md` and trim the backlog entry here.

## Current Backlog

### Near-Term CISD Extensions

- `[next]` `cisd_fvg`: measure the hold rate of CISDs that create FVGs.
- `[next]` `fvg_hold`: measure the hold rate of FVGs created by CISDs.
- `[next]` `cisd_fvg_interaction`: test whether an FVG holding increases the hold rate of the parent CISD.
- `[next]` `sssf_swing`: measure the hold rate of CISDs where either `candle[0]` (the CISD candle) or `candle[-1]` creates a swing, and differentiate which candle created the swing.
- `[done]` `smt`: hold rate of CISDs that create an SMT. Implemented via `smt_cisd`.
- `[next]` `sweep`: measure the hold rate of CISDs that sweep a previous low.

### CISD Follow-Through on `candle[1]`

- `[idea]` Investigate whether `candle[1]` after a CISD helps predict continuation.
- `[idea]` Test whether continuation is more probable when `candle[1]` closes in the direction of the CISD.
- `[idea]` Test whether a CISD has weaker follow-through when `candle[1]` closes opposite to the CISD direction.
- `[idea]` Test whether closing beyond the wick of `candle[1]` further improves continuation probabilities.
- `[idea]` Consider related `candle[1]` follow-through variants if they can be expressed cleanly as feature tags or barrier buckets.

### Multi-Bar Post-CISD Context

- `[idea]` `candle2_gap_context`: with `candle[0]` indexed to the CISD candle, test whether `candle[1]` failing to close beyond `candle[0]`'s high/low plus the nature of the gap on `candle[2]` creates a strong reversal or continuation context.
- `[idea]` `post_cisd_reversal_context`: for a bullish CISD, test whether a bearish `candle[1]` that fails to close above `candle[0]`'s high, followed by a gap down on `candle[2]`, shifts expectancy bearish. Mirror the logic for bearish CISDs.
- `[idea]` `post_cisd_ml`: if the discrete tags above look promising, test a small machine-learning model over post-CISD context features instead of hand-built buckets alone.

## Inbox

Paste rough ideas from Discord here first, then promote them into the structured backlog above.

### Template

- `[idea]` Short research question
- Hypothesis:
- Possible feature/tag:
- Notes:
