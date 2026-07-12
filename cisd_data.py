"""
cisd_data.py — Data Loading, Resampling, Enrichment, and SMT helpers
=====================================================================
Contains all functions for reading raw parquet data, resampling to target
timeframes, and computing the single enriched DataFrame consumed by all
downstream compute functions.

This module intentionally imports NO matplotlib so it can be used in
headless / CI environments without a display.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
DATA_DIR    = Path(__file__).parent / "data"
INSTRUMENTS = {
    "NQ": DATA_DIR / "nq_1m.parquet",
    "ES": DATA_DIR / "es_1m.parquet",
}
TIMEFRAMES = {
    "Daily": "1D",
    "4H":    "4h",
    "1H":    "1h",
    "15min": "15min",
}
LOOKAHEAD  = 2   # bars to look ahead after a CISD
MAX_CONSEC = 3   # max consecutive opposite candles to segment by
SMT_LOOKBACK = 20
FVG_HOLD_LOOKAHEAD = 10
SWEEP_TOLERANCE = 5
SWEEP_SWING_LOOKBACK = 20
_SMT_PKG_PATH = Path(os.environ.get("SMT_PKG_PATH", "/mnt/e/backup/code/Finance/Misc/SMT"))

# OOS_START: 70th-percentile date of the shared NQ∩ES daily calendar.
# Derived: len(shared)=1627, idx=int(0.70*1627)=1138. Frozen 2024-04-30.
# Do NOT recompute at runtime — appending data must not silently shift the OOS boundary.
OOS_START  = "2024-04-30"  # IS/OOS split: events before this date are discovery
MIN_N      = 50             # minimum sample size for a reportable finding (stricter than n≥30)
CI_LEVEL   = 0.95           # Wilson score CI confidence level

# WALK_FORWARD_FOLDS: 20th/40th/60th/80th-percentile dates of the discovery
# portion (index < OOS_START) of the shared NQ∩ES daily calendar.
# Derived: discovery len=1138 (shared len=1627, boundary idx=1138 per OOS_START
# derivation above). idx=int(pct*1138) for pct in (0.20, 0.40, 0.60, 0.80) ->
# 227, 455, 682, 910 -> 2021-05-25, 2022-02-16, 2022-11-09, 2023-08-04.
# These 4 frozen interior boundaries define 4 anchored (expanding) walk-forward
# folds within the discovery slice (D-05/D-06): fold k trains on all discovery
# history from the start up to the fold's chunk start, then tests on the next
# chunk, e.g. [start,b1) is training-only seed, test chunks are
# [b1,b2), [b2,b3), [b3,b4), [b4,OOS_START).
# Do NOT recompute at runtime — appending data must not silently shift these
# fold boundaries, mirroring the OOS_START convention above.
WALK_FORWARD_FOLDS = ("2021-05-25", "2022-02-16", "2022-11-09", "2023-08-04")


# ── Data Loading & Resampling ─────────────────────────────────────────────────

def load_1m(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.set_index("DateTime_ET").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = [c.lower() for c in df.columns]
    return df


def _normalize_resample_rule(rule: str) -> str:
    if rule.endswith("H"):
        return f"{rule[:-1]}h"
    return rule


def resample_ohlcv(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df_1m.resample(_normalize_resample_rule(rule)).agg(agg).dropna(subset=["open"])


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["direction"] = np.where(
        df["close"] > df["open"], "bullish",
        np.where(df["close"] < df["open"], "bearish", "neutral"),
    )
    df["prev_close"]     = df["close"].shift(1)
    df["prev_direction"] = df["direction"].shift(1)
    df["prev_high"]      = df["high"].shift(1)
    df["prev_low"]       = df["low"].shift(1)
    df["cisd_type"] = np.select(
        [
            (df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"]),
            (df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"]),
        ],
        ["bullish", "bearish"],
        default=None,
    )
    return _annotate_cisd_research(df)


def _compute_three_bar_swings(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    swing_low = pd.Series(False, index=df.index, dtype=bool)
    swing_high = pd.Series(False, index=df.index, dtype=bool)

    if len(df) < 3:
        return swing_low, swing_high

    low_mask = (df["low"] < df["low"].shift(1)) & (df["low"] < df["low"].shift(-1))
    high_mask = (df["high"] > df["high"].shift(1)) & (df["high"] > df["high"].shift(-1))

    for idx in df.index[low_mask.fillna(False)]:
        swing_low.at[idx] = True
    for idx in df.index[high_mask.fillna(False)]:
        swing_high.at[idx] = True

    return swing_low, swing_high


def _has_directional_fvg(df: pd.DataFrame, middle_idx: int, direction: str) -> bool:
    if middle_idx <= 0 or middle_idx >= len(df) - 1:
        return False

    left = df.iloc[middle_idx - 1]
    right = df.iloc[middle_idx + 1]
    if direction == "bullish":
        return left["high"] < right["low"]
    if direction == "bearish":
        return left["low"] > right["high"]
    return False


def _classify_fvg_hold(df: pd.DataFrame, middle_idx: int, direction: str, failure_mode: str) -> str:
    if direction not in ("bullish", "bearish"):
        raise ValueError("direction must be 'bullish' or 'bearish'")
    if failure_mode not in ("close_near", "wick_far"):
        raise ValueError("failure_mode must be 'close_near' or 'wick_far'")

    if middle_idx + FVG_HOLD_LOOKAHEAD >= len(df):
        return "none"

    left = df.iloc[middle_idx - 1]
    future = df.iloc[middle_idx + 1 : middle_idx + 1 + FVG_HOLD_LOOKAHEAD]

    if direction == "bullish":
        if failure_mode == "close_near":
            failed = (future["close"] < left["high"]).any()
        else:
            failed = (future["low"] < left["low"]).any()
    else:
        if failure_mode == "close_near":
            failed = (future["close"] > left["low"]).any()
        else:
            failed = (future["high"] > left["high"]).any()

    return "failed" if failed else "held"


def _has_directional_sweep(
    df: pd.DataFrame,
    idx: int,
    direction: str,
    swing_low: pd.Series,
    swing_high: pd.Series,
) -> bool:
    start = max(0, idx - (SWEEP_TOLERANCE - 1))
    for sweep_idx in range(start, idx + 1):
        history_start = max(0, sweep_idx - SWEEP_SWING_LOOKBACK)
        if direction == "bullish":
            mask = swing_low.iloc[history_start:sweep_idx]
            prior_lows = df["low"].iloc[history_start:sweep_idx][mask]
            if not prior_lows.empty and df["low"].iloc[sweep_idx] < prior_lows.min():
                return True
        else:
            mask = swing_high.iloc[history_start:sweep_idx]
            prior_highs = df["high"].iloc[history_start:sweep_idx][mask]
            if not prior_highs.empty and df["high"].iloc[sweep_idx] > prior_highs.max():
                return True
    return False


def _annotate_cisd_research(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized re-expression of the per-event annotation loop.

    Behavior-preserving rewrite (Phase 08 Plan 02): every column below is
    produced via whole-frame numpy/pandas operations instead of a Python
    `for idx in event_pos` loop with nested `.iloc`/`.iat` window scans. The
    private helpers `_compute_three_bar_swings`, `_has_directional_fvg`,
    `_classify_fvg_hold`, and `_has_directional_sweep` are left untouched
    (they are independently unit-tested and part of the public re-export
    surface) — this function no longer calls them, but reproduces their exact
    documented semantics using array-level equivalents. See
    `.planning/phases/08-performance-vectorize-the-enrichment-validation-hot-path/08-02-SUMMARY.md`
    for the derivation of each equivalence (in particular the "any value in
    a future/past window crosses a threshold" -> "window min/max vs
    threshold" reduction used for the sweep and FVG-hold checks).
    """
    if "cisd_type" not in df.columns:
        raise ValueError("df must contain cisd_type column")

    annotated = df.copy()
    swing_low, swing_high = _compute_three_bar_swings(annotated)

    idx_ax = annotated.index
    ct_arr = annotated["cisd_type"].to_numpy(dtype=object)
    is_bullish = ct_arr == "bullish"
    is_bearish = ct_arr == "bearish"

    open_ = annotated["open"].to_numpy(dtype=float)
    high  = annotated["high"].to_numpy(dtype=float)
    low   = annotated["low"].to_numpy(dtype=float)
    close = annotated["close"].to_numpy(dtype=float)

    open_s  = pd.Series(open_, index=idx_ax)
    high_s  = pd.Series(high, index=idx_ax)
    low_s   = pd.Series(low, index=idx_ax)
    close_s = pd.Series(close, index=idx_ax)

    # ── prev-bar / cisd-bar swing flags (direction-specific) ────────────────
    swing_low_np       = swing_low.to_numpy(dtype=bool)
    swing_high_np      = swing_high.to_numpy(dtype=bool)
    prev_swing_low_np  = swing_low.shift(1).fillna(False).to_numpy(dtype=bool)
    prev_swing_high_np = swing_high.shift(1).fillna(False).to_numpy(dtype=bool)

    cisd_bar_is_dir_swing = np.where(is_bullish, swing_low_np, np.where(is_bearish, swing_high_np, False))
    prev_bar_is_dir_swing = np.where(is_bullish, prev_swing_low_np, np.where(is_bearish, prev_swing_high_np, False))

    # ── directional sweep ────────────────────────────────────────────────────
    # `_has_directional_sweep` (per event idx) scans sweep_idx in
    # [idx-(SWEEP_TOLERANCE-1), idx] and, for each candidate sweep_idx, looks
    # back up to SWEEP_SWING_LOOKBACK bars for a prior direction-appropriate
    # swing extreme that the candidate bar's low/high undercuts/exceeds.
    # Equivalent bar-independent form: for every bar p, compute whether
    # low[p] undercuts the rolling min of prior swing-low values in the
    # trailing SWEEP_SWING_LOOKBACK window ending at p-1 (mask non-swing bars
    # to +/-inf so they never win the rolling reduction, and treat a
    # non-finite reduction — no swing point yet in range — as "no trigger",
    # matching the original's `prior_lows.empty` short-circuit). Then
    # has_dir_sweep at a CISD bar idx is just "any per-bar trigger in the
    # trailing SWEEP_TOLERANCE-bar window ending at idx" (a rolling any()).
    masked_low_for_swing  = np.where(swing_low_np, low, np.inf)
    masked_high_for_swing = np.where(swing_high_np, high, -np.inf)

    roll_min_prior_swing_low = (
        pd.Series(masked_low_for_swing, index=idx_ax)
        .rolling(window=SWEEP_SWING_LOOKBACK, min_periods=1)
        .min()
        .shift(1)
        .to_numpy()
    )
    roll_max_prior_swing_high = (
        pd.Series(masked_high_for_swing, index=idx_ax)
        .rolling(window=SWEEP_SWING_LOOKBACK, min_periods=1)
        .max()
        .shift(1)
        .to_numpy()
    )

    bullish_sweep_trigger = np.isfinite(roll_min_prior_swing_low) & (low < roll_min_prior_swing_low)
    bearish_sweep_trigger = np.isfinite(roll_max_prior_swing_high) & (high > roll_max_prior_swing_high)

    bullish_sweep_any = (
        pd.Series(bullish_sweep_trigger, index=idx_ax)
        .rolling(window=SWEEP_TOLERANCE, min_periods=1)
        .max()
        .fillna(0)
        .to_numpy()
        > 0
    )
    bearish_sweep_any = (
        pd.Series(bearish_sweep_trigger, index=idx_ax)
        .rolling(window=SWEEP_TOLERANCE, min_periods=1)
        .max()
        .fillna(0)
        .to_numpy()
        > 0
    )

    has_dir_sweep = np.where(is_bullish, bullish_sweep_any, np.where(is_bearish, bearish_sweep_any, False))

    # ── FVG mid0 (middle = CISD bar) / mid1 (middle = idx+1) detection ──────
    # `_has_directional_fvg(df, middle_idx, direction)` compares
    # df.iloc[middle_idx-1] against df.iloc[middle_idx+1], returning False at
    # the middle_idx<=0 / >=len-1 boundary. shift(1)/shift(-1) naturally
    # produce NaN at those boundaries, and NaN comparisons evaluate False —
    # reproducing the boundary guard without an explicit bounds check.
    left_high_mid0  = high_s.shift(1).to_numpy()
    left_low_mid0   = low_s.shift(1).to_numpy()
    right_low_mid0  = low_s.shift(-1).to_numpy()
    right_high_mid0 = high_s.shift(-1).to_numpy()

    bull_fvg_mid0 = left_high_mid0 < right_low_mid0
    bear_fvg_mid0 = left_low_mid0 > right_high_mid0
    has_dir_fvg_mid0 = np.where(is_bullish, bull_fvg_mid0, np.where(is_bearish, bear_fvg_mid0, False))

    # mid1: middle_idx = idx+1, so "left" = df.iloc[idx] (the CISD bar itself)
    # and "right" = df.iloc[idx+2].
    right_low_mid1  = low_s.shift(-2).to_numpy()
    right_high_mid1 = high_s.shift(-2).to_numpy()

    bull_fvg_mid1 = high < right_low_mid1
    bear_fvg_mid1 = low > right_high_mid1
    has_dir_fvg_mid1 = np.where(is_bullish, bull_fvg_mid1, np.where(is_bearish, bear_fvg_mid1, False))

    # ── Magnitude conditioning columns (Phase 10 Plan 01, D-04/D-05/D-06a) ──
    # ATR(14) computed once here, identical to compute_candle_size's
    # (high-low).rolling(14).mean() convention (D-04) — do not invent a
    # true-range variant. Reused by every magnitude column below.
    atr = (annotated["high"] - annotated["low"]).rolling(14).mean()
    atr_arr = atr.to_numpy(dtype=float)
    atr_valid = np.isfinite(atr_arr) & (atr_arr > 0)
    safe_atr = np.where(atr_valid, atr_arr, np.nan)
    prev_high_arr = annotated["prev_high"].to_numpy(dtype=float)
    prev_low_arr  = annotated["prev_low"].to_numpy(dtype=float)

    # wick_distance_atr: signed, ALL CISDs (D-05/D-06). Positive = closed past
    # the prior bar's wick; negative/zero = closed within it. This single
    # feature subsumes the binary compute_wick past/within split — the bin
    # edge at exactly 0 (Plan 02) recovers that split.
    wick_distance_bull = (close - prev_high_arr) / safe_atr
    wick_distance_bear = (prev_low_arr - close) / safe_atr
    wick_distance_atr = np.where(
        is_bullish, wick_distance_bull,
        np.where(is_bearish, wick_distance_bear, np.nan),
    )

    # swept_level / sweep_depth_atr: gated on has_dir_sweep (D-05/D-06a).
    # roll_min_prior_swing_low / roll_max_prior_swing_high (computed above,
    # sweep block) ARE the nearest prior directional swing level as of each
    # bar — reused here rather than re-derived. Anchoring convention (frozen,
    # planner's call under D-06a): the depth is measured at the CISD bar t
    # against the nearest prior swing extreme as-of-t (not the specific
    # sweep_idx within the trailing SWEEP_TOLERANCE window) — swings move
    # slowly relative to the 5-bar tolerance window, so this equals the
    # triggered level in the overwhelming majority of cases while staying
    # fully vectorized.
    swept_level = np.where(
        is_bullish, roll_min_prior_swing_low,
        np.where(is_bearish, roll_max_prior_swing_high, np.nan),
    )
    swept_level = np.where(has_dir_sweep & np.isfinite(swept_level), swept_level, np.nan)

    sweep_depth_bull = (swept_level - low) / safe_atr
    sweep_depth_bear = (high - swept_level) / safe_atr
    sweep_depth_atr = np.where(
        has_dir_sweep & atr_valid & np.isfinite(swept_level),
        np.where(is_bullish, sweep_depth_bull, np.where(is_bearish, sweep_depth_bear, np.nan)),
        np.nan,
    )

    # fvg_gap_width / fvg_size_atr: gated on has_dir_fvg_mid0/mid1 (D-05/
    # D-06a). Reuses the gap-boundary arrays already computed in the FVG
    # mid0/mid1 detection block above. mid0-priority union (frozen, planner's
    # resolution of the mid0-vs-mid1 open question in PATTERNS): where both a
    # mid0 and mid1 FVG exist, the CISD-bar (mid0) FVG takes precedence — a
    # single flat population keeps the compute layer flat and hits the
    # generic manifest dispatch with zero harness change.
    mid0_gap_bull = right_low_mid0 - left_high_mid0
    mid0_gap_bear = left_low_mid0 - right_high_mid0
    mid0_gap = np.where(is_bullish, mid0_gap_bull, np.where(is_bearish, mid0_gap_bear, np.nan))

    mid1_gap_bull = right_low_mid1 - high
    mid1_gap_bear = low - right_high_mid1
    mid1_gap = np.where(is_bullish, mid1_gap_bull, np.where(is_bearish, mid1_gap_bear, np.nan))

    fvg_gap_width = np.where(has_dir_fvg_mid0, mid0_gap, np.where(has_dir_fvg_mid1, mid1_gap, np.nan))
    fvg_size_atr = np.where(
        atr_valid & np.isfinite(fvg_gap_width),
        fvg_gap_width / safe_atr,
        np.nan,
    )

    # ── FVG hold classification ──────────────────────────────────────────────
    # `_classify_fvg_hold` returns "none" when the FVG_HOLD_LOOKAHEAD window
    # doesn't fit, else checks `any(...)` over the future window against a
    # left-bar threshold. Since each check is a one-sided inequality, "any
    # future value violates threshold" is equivalent to "the future window's
    # min (for `<` checks) or max (for `>` checks) violates threshold" — so a
    # per-bar forward-looking rolling min/max reduction reproduces `.any()`
    # exactly, without scanning the window per event.
    close_roll_min = close_s.rolling(window=FVG_HOLD_LOOKAHEAD, min_periods=FVG_HOLD_LOOKAHEAD).min()
    low_roll_min   = low_s.rolling(window=FVG_HOLD_LOOKAHEAD, min_periods=FVG_HOLD_LOOKAHEAD).min()
    close_roll_max = close_s.rolling(window=FVG_HOLD_LOOKAHEAD, min_periods=FVG_HOLD_LOOKAHEAD).max()
    high_roll_max  = high_s.rolling(window=FVG_HOLD_LOOKAHEAD, min_periods=FVG_HOLD_LOOKAHEAD).max()

    # For middle_idx m, the future window [m+1, m+1+FVG_HOLD_LOOKAHEAD) is the
    # rolling window ending at position m+FVG_HOLD_LOOKAHEAD; shift(-k) brings
    # that value back to position m. mid0: m=idx (k=LOOKAHEAD).
    # mid1: m=idx+1 (k=LOOKAHEAD+1).
    mid0_future_min_close = close_roll_min.shift(-FVG_HOLD_LOOKAHEAD).to_numpy()
    mid0_future_min_low   = low_roll_min.shift(-FVG_HOLD_LOOKAHEAD).to_numpy()
    mid0_future_max_close = close_roll_max.shift(-FVG_HOLD_LOOKAHEAD).to_numpy()
    mid0_future_max_high  = high_roll_max.shift(-FVG_HOLD_LOOKAHEAD).to_numpy()

    mid1_future_min_close = close_roll_min.shift(-(FVG_HOLD_LOOKAHEAD + 1)).to_numpy()
    mid1_future_min_low   = low_roll_min.shift(-(FVG_HOLD_LOOKAHEAD + 1)).to_numpy()
    mid1_future_max_close = close_roll_max.shift(-(FVG_HOLD_LOOKAHEAD + 1)).to_numpy()
    mid1_future_max_high  = high_roll_max.shift(-(FVG_HOLD_LOOKAHEAD + 1)).to_numpy()

    mid0_none_mask = ~np.isfinite(mid0_future_min_close)
    mid1_none_mask = ~np.isfinite(mid1_future_min_close)

    def _hold_str(failed: np.ndarray, none_mask: np.ndarray) -> np.ndarray:
        return np.where(none_mask, "none", np.where(failed, "failed", "held"))

    # mid0 left = bar at idx-1; mid1 left = bar at idx (the CISD bar itself).
    fvg_mid0_hold_close_near_bull = _hold_str(mid0_future_min_close < left_high_mid0, mid0_none_mask)
    fvg_mid0_hold_wick_far_bull   = _hold_str(mid0_future_min_low < left_low_mid0, mid0_none_mask)
    fvg_mid0_hold_close_near_bear = _hold_str(mid0_future_max_close > left_low_mid0, mid0_none_mask)
    fvg_mid0_hold_wick_far_bear   = _hold_str(mid0_future_max_high > left_high_mid0, mid0_none_mask)

    fvg_mid1_hold_close_near_bull = _hold_str(mid1_future_min_close < high, mid1_none_mask)
    fvg_mid1_hold_wick_far_bull   = _hold_str(mid1_future_min_low < low, mid1_none_mask)
    fvg_mid1_hold_close_near_bear = _hold_str(mid1_future_max_close > low, mid1_none_mask)
    fvg_mid1_hold_wick_far_bear   = _hold_str(mid1_future_max_high > high, mid1_none_mask)

    fvg_mid0_hold_close_near = np.select(
        [is_bullish & has_dir_fvg_mid0, is_bearish & has_dir_fvg_mid0],
        [fvg_mid0_hold_close_near_bull, fvg_mid0_hold_close_near_bear],
        default="none",
    )
    fvg_mid0_hold_wick_far = np.select(
        [is_bullish & has_dir_fvg_mid0, is_bearish & has_dir_fvg_mid0],
        [fvg_mid0_hold_wick_far_bull, fvg_mid0_hold_wick_far_bear],
        default="none",
    )
    fvg_mid1_hold_close_near = np.select(
        [is_bullish & has_dir_fvg_mid1, is_bearish & has_dir_fvg_mid1],
        [fvg_mid1_hold_close_near_bull, fvg_mid1_hold_close_near_bear],
        default="none",
    )
    fvg_mid1_hold_wick_far = np.select(
        [is_bullish & has_dir_fvg_mid1, is_bearish & has_dir_fvg_mid1],
        [fvg_mid1_hold_wick_far_bull, fvg_mid1_hold_wick_far_bear],
        default="none",
    )

    # ── candle[1] / candle[2] follow-through features ───────────────────────
    # All comparisons use shift(-1)/shift(-2) values that are NaN when the
    # bar is out of range; NaN comparisons evaluate False in numpy, which
    # reproduces the original's "idx+1 < n" / "idx+2 < n" guards (out-of-range
    # rows fall through to the same defaults: "against"/False/"flat"/False).
    close_shift1 = close_s.shift(-1).to_numpy()
    open_shift2  = open_s.shift(-2).to_numpy()
    high_shift1  = high_s.shift(-1).to_numpy()
    low_shift1   = low_s.shift(-1).to_numpy()
    close_shift2 = close_s.shift(-2).to_numpy()

    bull_with      = close_shift1 > close
    bull_past_wick = bull_with & (close_shift1 > high)
    bear_with      = close_shift1 < close
    bear_past_wick = bear_with & (close_shift1 < low)

    candle1_close_dir = np.where(
        is_bullish, np.where(bull_with, "with", "against"),
        np.where(is_bearish, np.where(bear_with, "with", "against"), "against"),
    )
    candle1_past_candle0_wick = np.where(
        is_bullish, bull_past_wick,
        np.where(is_bearish, bear_past_wick, False),
    )

    # candle1_failed_followthrough: c1 fails to close past c0's extreme.
    bull_failed_followthrough = close_shift1 <= high
    bear_failed_followthrough = close_shift1 >= low
    candle1_failed_followthrough = np.where(
        is_bullish, bull_failed_followthrough,
        np.where(is_bearish, bear_failed_followthrough, False),
    )

    # candle2_gap_dir: signed gap = c2.open - c1.close, mapped by CISD
    # direction; NaN (out-of-range c1/c2) and a literal zero gap both fall
    # through to "flat", matching the original's explicit else branch.
    gap = open_shift2 - close_shift1

    candle2_gap_dir_bull = np.where(gap > 0, "gap_with", np.where(gap < 0, "gap_against", "flat"))
    candle2_gap_dir_bear = np.where(gap < 0, "gap_with", np.where(gap > 0, "gap_against", "flat"))
    candle2_gap_dir = np.where(
        is_bullish, candle2_gap_dir_bull,
        np.where(is_bearish, candle2_gap_dir_bear, "flat"),
    )

    # Reading B: candle[2] closes past candle[1]'s wick in the CISD direction.
    bull_c2_past_wick = close_shift2 > high_shift1
    bear_c2_past_wick = close_shift2 < low_shift1
    candle2_past_candle1_wick = np.where(
        is_bullish, bull_c2_past_wick,
        np.where(is_bearish, bear_c2_past_wick, False),
    )

    # ── Bulk-assign vectorized results to columns ────────────────────────────
    annotated["has_dir_fvg_mid0"]         = has_dir_fvg_mid0.astype(bool)
    annotated["has_dir_fvg_mid1"]         = has_dir_fvg_mid1.astype(bool)
    annotated["fvg_mid0_hold_close_near"] = fvg_mid0_hold_close_near
    annotated["fvg_mid0_hold_wick_far"]   = fvg_mid0_hold_wick_far
    annotated["fvg_mid1_hold_close_near"] = fvg_mid1_hold_close_near
    annotated["fvg_mid1_hold_wick_far"]   = fvg_mid1_hold_wick_far
    annotated["has_dir_sweep"]            = has_dir_sweep.astype(bool)
    annotated["prev_bar_is_dir_swing"]    = prev_bar_is_dir_swing.astype(bool)
    annotated["cisd_bar_is_dir_swing"]    = cisd_bar_is_dir_swing.astype(bool)
    annotated["candle1_close_dir"]              = candle1_close_dir
    annotated["candle1_past_candle0_wick"]      = candle1_past_candle0_wick.astype(bool)
    annotated["candle1_failed_followthrough"]   = candle1_failed_followthrough.astype(bool)
    annotated["candle2_gap_dir"]                = candle2_gap_dir
    annotated["candle2_past_candle1_wick"]      = candle2_past_candle1_wick.astype(bool)

    # ── Magnitude conditioning columns (Phase 10 Plan 01) ────────────────────
    annotated["wick_distance_atr"] = wick_distance_atr
    annotated["swept_level"]       = swept_level
    annotated["sweep_depth_atr"]   = sweep_depth_atr
    annotated["fvg_gap_width"]     = fvg_gap_width
    annotated["fvg_size_atr"]      = fvg_size_atr

    return annotated


def _direction_for_signal_type(signal_type: object) -> str | None:
    text = str(signal_type)
    if text.startswith("Bullish"):
        return "bullish"
    if text.startswith("Bearish"):
        return "bearish"
    return None


def _annotate_swing_smt_from_events(df: pd.DataFrame, events: pd.DataFrame, instrument: str) -> pd.DataFrame:
    """Vectorized re-expression of the per-bar SMT-matching loop.

    Behavior-preserving rewrite (Phase 08 Plan 03): reproduces the original
    O(bars x events) nested loop's exact semantics — left-only window
    `[index[max(0, idx-2)], index[idx]]` (inclusive, by timestamp) and
    latest-created-event-wins (with ties broken by original event order) —
    via a per-direction `searchsorted` lookup instead of a per-bar Python
    scan over every event. See
    `.planning/phases/08-performance-vectorize-the-enrichment-validation-hot-path/08-03-PLAN.md`
    for the derivation: sorting each direction's events by `created_ts` with
    a STABLE sort preserves original-order ties, so `searchsorted(...,
    side="right") - 1` against each CISD bar's timestamp lands on exactly the
    same "last event in ascending-created_ts, then original-order,
    iteration" winner the original loop's unconditional overwrite produced.

    Widened (Phase 09 Plan 01, see
    `.planning/phases/09-smt-geometry-invalidation-honesty/09-01-PLAN.md`):
    the matched SMT's lifecycle fields are carried through, the matched
    SMT's validity at the CISD bar `t` is checked (`broken_ts` NaT or
    strictly greater than `t`) and used to split the tag into a three-way
    `"w/ SMT"` / `"expired SMT"` / `"no SMT"` (D-01/D-02/D-03/D-03a — the
    validity check NEVER reads `status`, and only the single latest-created
    matched SMT is checked, matching the existing selection rule), the
    survived-vs-broke-in-window horizon flag `smt_broke_in_window` is
    computed (D-06), and the block-geometry columns `smt_block_size_atr` /
    `cisd_in_smt_block` are computed over the matched population (D-04/D-05/
    D-05a).
    """
    required_event_columns = (
        "signal_type", "created_ts", "sweeping_asset", "failing_asset",
        "reference_price", "invalidation_asset", "invalidation_direction",
        "invalidation_level", "broken_ts", "status", "reference_timestamp",
    )
    if "cisd_type" not in df.columns:
        raise ValueError("df must contain cisd_type column")

    missing_event_columns = [column for column in required_event_columns if column not in events.columns]
    if missing_event_columns:
        raise ValueError(f"events must contain columns: {', '.join(missing_event_columns)}")

    annotated = df.copy()
    annotated["has_swing_smt"] = False
    annotated["swing_smt_tag"] = "no SMT"
    annotated["swing_smt_match_ts"] = pd.NaT
    annotated["swing_smt_role"] = "none"
    annotated["smt_reference_price"] = np.nan
    annotated["smt_invalidation_level"] = np.nan
    annotated["smt_broken_ts"] = pd.NaT
    annotated["smt_status"] = "none"
    annotated["smt_reference_timestamp"] = pd.NaT
    annotated["smt_invalidation_asset"] = "none"
    annotated["smt_invalidation_direction"] = "none"
    annotated["smt_broke_in_window"] = False
    annotated["smt_block_size_atr"] = np.nan
    annotated["cisd_in_smt_block"] = False

    if annotated.empty or events.empty:
        return annotated

    # Filter: drop events with NaT created_ts (mirrors `pd.isna(created_ts)`);
    # signal_type values that are None/NaN/unrecognized fall through to
    # `_direction_for_signal_type` returning None and are dropped below —
    # matching the original's `signal_type is None` short-circuit plus its
    # `direction is None` fallback for any other non-matching value.
    filtered = events.loc[events["created_ts"].notna()].copy()
    filtered["_direction"] = filtered["signal_type"].map(_direction_for_signal_type)
    filtered = filtered.loc[filtered["_direction"].notna()]

    if filtered.empty:
        return annotated

    n = len(annotated)
    idx_ax = annotated.index
    ct_arr = annotated["cisd_type"].to_numpy(dtype=object)
    ts_arr = idx_ax.to_numpy()
    lower_pos = np.maximum(np.arange(n) - 2, 0)
    lower_ts_arr = ts_arr[lower_pos]
    upper_pos = np.minimum(np.arange(n) + 2, n - 1)
    upper_ts_arr = ts_arr[upper_pos]

    # ATR(14) and OHLC arrays for the D-04/D-05 geometry columns, computed
    # once over the whole annotated frame (same convention as
    # `compute_candle_size`: `(high - low).rolling(14).mean()`, evaluated at
    # bar t).
    atr_arr = (annotated["high"] - annotated["low"]).rolling(14).mean().to_numpy(dtype=float)
    open_arr = annotated["open"].to_numpy(dtype=float)
    close_arr = annotated["close"].to_numpy(dtype=float)

    has_swing_smt = np.zeros(n, dtype=bool)
    swing_smt_tag = np.full(n, "no SMT", dtype=object)
    swing_smt_match_ts = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    swing_smt_role = np.full(n, "none", dtype=object)
    smt_reference_price = np.full(n, np.nan, dtype=float)
    smt_invalidation_level = np.full(n, np.nan, dtype=float)
    smt_broken_ts = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    smt_status = np.full(n, "none", dtype=object)
    smt_reference_timestamp = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    smt_invalidation_asset = np.full(n, "none", dtype=object)
    smt_invalidation_direction = np.full(n, "none", dtype=object)
    smt_broke_in_window = np.zeros(n, dtype=bool)
    smt_block_size_atr = np.full(n, np.nan, dtype=float)
    cisd_in_smt_block = np.zeros(n, dtype=bool)

    for direction in ("bullish", "bearish"):
        dir_events = filtered.loc[filtered["_direction"] == direction]
        if dir_events.empty:
            continue

        # Stable sort by created_ts: ties preserve original event order,
        # reproducing the original loop's ascending-created_ts iteration
        # (event_rows.sort(key=...)) exactly, including its tie behavior.
        dir_events = dir_events.sort_values("created_ts", kind="mergesort")
        event_ts       = dir_events["created_ts"].to_numpy()
        event_sweeping = dir_events["sweeping_asset"].to_numpy()
        event_failing  = dir_events["failing_asset"].to_numpy()
        event_reference_price = dir_events["reference_price"].to_numpy(dtype=float)
        event_invalidation_asset = dir_events["invalidation_asset"].to_numpy(dtype=object)
        event_invalidation_direction = dir_events["invalidation_direction"].to_numpy(dtype=object)
        event_invalidation_level = dir_events["invalidation_level"].to_numpy(dtype=float)
        event_broken_ts = pd.to_datetime(dir_events["broken_ts"]).to_numpy(dtype="datetime64[ns]")
        event_status = dir_events["status"].to_numpy(dtype=object)
        event_reference_ts = pd.to_datetime(dir_events["reference_timestamp"]).to_numpy(dtype="datetime64[ns]")

        row_mask = ct_arr == direction
        if not row_mask.any():
            continue
        row_positions = np.flatnonzero(row_mask)
        row_ts        = ts_arr[row_positions]
        row_lower_ts  = lower_ts_arr[row_positions]

        # Rightmost event with created_ts <= row_ts. For tied created_ts
        # values this lands on the LAST tied event in `event_ts` (per the
        # stable sort above), matching the original's "keep overwriting on
        # every ascending-order match" tie outcome.
        candidate_pos = np.searchsorted(event_ts, row_ts, side="right") - 1
        found = candidate_pos >= 0
        safe_pos = np.clip(candidate_pos, 0, len(event_ts) - 1)
        candidate_ts = np.where(found, event_ts[safe_pos], np.datetime64("NaT"))
        in_window = found & (candidate_ts >= row_lower_ts)

        if not in_window.any():
            continue

        match_positions      = row_positions[in_window]
        matched_candidate_pos = safe_pos[in_window]
        matched_row_ts   = row_ts[in_window]
        matched_upper_ts = upper_ts_arr[match_positions]
        matched_ts       = event_ts[matched_candidate_pos]
        matched_sweeping = event_sweeping[matched_candidate_pos]
        matched_failing  = event_failing[matched_candidate_pos]
        matched_reference_price = event_reference_price[matched_candidate_pos]
        matched_invalidation_asset = event_invalidation_asset[matched_candidate_pos]
        matched_invalidation_direction = event_invalidation_direction[matched_candidate_pos]
        matched_invalidation_level = event_invalidation_level[matched_candidate_pos]
        matched_broken_ts = event_broken_ts[matched_candidate_pos]
        matched_status = event_status[matched_candidate_pos]
        matched_reference_ts = event_reference_ts[matched_candidate_pos]

        # D-01/D-02: validity is broken_ts vs t only, never status. Checked
        # only on the single latest-created matched SMT (D-03a) — no
        # re-search for an earlier still-valid same-direction event.
        still_valid = pd.isna(matched_broken_ts) | (matched_broken_ts > matched_row_ts)

        has_swing_smt[match_positions] = True
        swing_smt_tag[match_positions] = np.where(still_valid, "w/ SMT", "expired SMT")
        swing_smt_match_ts[match_positions] = matched_ts
        swing_smt_role[match_positions] = np.where(
            matched_sweeping == instrument, "swept",
            np.where(matched_failing == instrument, "failed_to_sweep", "none"),
        )
        smt_reference_price[match_positions] = matched_reference_price
        smt_invalidation_level[match_positions] = matched_invalidation_level
        smt_broken_ts[match_positions] = matched_broken_ts
        smt_status[match_positions] = matched_status
        smt_reference_timestamp[match_positions] = matched_reference_ts
        smt_invalidation_asset[match_positions] = matched_invalidation_asset
        smt_invalidation_direction[match_positions] = matched_invalidation_direction

        # D-06: broke-in-window horizon flag, meaningful only for still-valid
        # ("w/ SMT") matches — expired rows have broken_ts <= t so are never
        # "broke in window" by construction.
        smt_broke_in_window[match_positions] = (
            still_valid
            & pd.notna(matched_broken_ts)
            & (matched_broken_ts > matched_row_ts)
            & (matched_broken_ts <= matched_upper_ts)
        )

        # D-04/D-05: block geometry, computed for the WHOLE matched
        # population (w/ SMT and expired SMT alike, D-05a) from the
        # reference_timestamp bar's own high/low on the annotated
        # instrument. `reindex` yields NaN on a miss, propagating gracefully.
        block_high = annotated["high"].reindex(matched_reference_ts).to_numpy(dtype=float)
        block_low = annotated["low"].reindex(matched_reference_ts).to_numpy(dtype=float)
        atr_t = atr_arr[match_positions]
        open_t = open_arr[match_positions]
        close_t = close_arr[match_positions]
        block_range = block_high - block_low

        smt_block_size_atr[match_positions] = np.where(
            (atr_t > 0) & np.isfinite(block_range), block_range / atr_t, np.nan,
        )
        contained = (
            (open_t >= block_low) & (open_t <= block_high)
            & (close_t >= block_low) & (close_t <= block_high)
        )
        cisd_in_smt_block[match_positions] = np.where(np.isfinite(block_range), contained, False)

    annotated["has_swing_smt"]      = has_swing_smt
    annotated["swing_smt_tag"]      = swing_smt_tag
    annotated["swing_smt_match_ts"] = swing_smt_match_ts
    annotated["swing_smt_role"]     = swing_smt_role
    annotated["smt_reference_price"] = smt_reference_price
    annotated["smt_invalidation_level"] = smt_invalidation_level
    annotated["smt_broken_ts"] = smt_broken_ts
    annotated["smt_status"] = smt_status
    annotated["smt_reference_timestamp"] = smt_reference_timestamp
    annotated["smt_invalidation_asset"] = smt_invalidation_asset
    annotated["smt_invalidation_direction"] = smt_invalidation_direction
    annotated["smt_broke_in_window"] = smt_broke_in_window
    annotated["smt_block_size_atr"] = smt_block_size_atr
    annotated["cisd_in_smt_block"] = cisd_in_smt_block

    return annotated


def _to_smt_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = ("open", "high", "low", "close")
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"df must contain columns: {', '.join(missing_columns)}")
    return df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )[["Open", "High", "Low", "Close"]].copy()


def _load_scan_smts_historical():
    if not _SMT_PKG_PATH.exists():
        raise FileNotFoundError(f"SMT package path does not exist: {_SMT_PKG_PATH}")
    pkg_path = str(_SMT_PKG_PATH)
    if pkg_path not in sys.path:
        sys.path.insert(0, pkg_path)
    try:
        from smt import scan_smts_historical
    except ImportError as exc:
        raise ImportError(f"Could not import scan_smts_historical from {_SMT_PKG_PATH}") from exc
    return scan_smts_historical


def _scan_swing_smt_events(df_nq: pd.DataFrame, df_es: pd.DataFrame) -> pd.DataFrame:
    if not df_nq.index.equals(df_es.index):
        raise ValueError("df_nq and df_es must share the same index")
    scan_smts_historical = _load_scan_smts_historical()
    events = scan_smts_historical(
        _to_smt_ohlc(df_nq),
        _to_smt_ohlc(df_es),
        asset_names=("NQ", "ES"),
        lookback_period=SMT_LOOKBACK,
        enable_micro=False,
        enable_swing=True,
        enable_fvg=False,
    )
    return events[events["signal_type"].isin(("Bullish Swing SMT", "Bearish Swing SMT"))].reset_index(drop=True)


def prepare_pair(
    df_nq_1m: pd.DataFrame,
    df_es_1m: pd.DataFrame,
    rule: str,
    with_swing_smt: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    resampled_nq = resample_ohlcv(df_nq_1m, rule)
    resampled_es = resample_ohlcv(df_es_1m, rule)
    df_nq = prepare(resampled_nq)
    df_es = prepare(resampled_es)

    if not with_swing_smt:
        return df_nq, df_es

    shared_index = resampled_nq.index.intersection(resampled_es.index)
    events = _scan_swing_smt_events(
        resampled_nq.loc[shared_index],
        resampled_es.loc[shared_index],
    )
    return (
        _annotate_swing_smt_from_events(df_nq, events, instrument="NQ"),
        _annotate_swing_smt_from_events(df_es, events, instrument="ES"),
    )


__all__ = [
    # Config constants
    "DATA_DIR",
    "INSTRUMENTS",
    "TIMEFRAMES",
    "LOOKAHEAD",
    "MAX_CONSEC",
    "SMT_LOOKBACK",
    "FVG_HOLD_LOOKAHEAD",
    "SWEEP_TOLERANCE",
    "SWEEP_SWING_LOOKBACK",
    "_SMT_PKG_PATH",
    "OOS_START",
    "MIN_N",
    "CI_LEVEL",
    "WALK_FORWARD_FOLDS",
    # Data loading & resampling
    "load_1m",
    "_normalize_resample_rule",
    "resample_ohlcv",
    # Enrichment
    "prepare",
    "_compute_three_bar_swings",
    "_has_directional_fvg",
    "_classify_fvg_hold",
    "_has_directional_sweep",
    "_annotate_cisd_research",
    # SMT helpers
    "_annotate_swing_smt_from_events",
    "_to_smt_ohlc",
    "_load_scan_smts_historical",
    "_scan_swing_smt_events",
    "prepare_pair",
]
