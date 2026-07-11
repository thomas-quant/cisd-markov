"""
cisd_barriers.py — Barrier Logic and Compute Functions
=======================================================
Contains the core barrier hit evaluation, 14 compute_* functions,
the ANALYSES registry, and the ANALYSIS_META single-source-of-truth
registry that drives all per-TF heights, standalone flags, standalone
heights, and PNG filenames.

Import chain (one-directional, no cycles):
    cisd_barriers -> cisd_charts -> cisd_data

ANALYSES references chart functions from cisd_charts (imported at module
load), and compute functions defined in this module.  cisd_charts imports
ANALYSES lazily inside its builder functions to break the cycle.
"""

import numpy as np
import pandas as pd
from typing import NamedTuple

from cisd_data import LOOKAHEAD, MAX_CONSEC, FVG_HOLD_LOOKAHEAD
from cisd_charts import (
    chart_basic,
    chart_mc,
    chart_significance,
    chart_wick,
    chart_combined,
    chart_volume,
    chart_candle_size,
    chart_size_cross,
    chart_smt_cisd,
    chart_cisd_fvg,
    chart_fvg_hold,
    chart_cisd_fvg_interaction,
    chart_sweep,
    chart_sssf_swing,
    chart_candle1_followthrough,
    chart_post_cisd_context,
)


# ── Core Barrier Logic ────────────────────────────────────────────────────────

def barrier_hit(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> bool:
    """
    Returns True if the TARGET is hit before the STOP within LOOKAHEAD bars.
      Bullish: target = CISD high, stop = CISD low
      Bearish: target = CISD low,  stop = CISD high
    """
    for j in range(1, LOOKAHEAD + 1):
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


def barrier_outcome_forward(df: pd.DataFrame, idx: int, row: pd.Series, ct: str) -> str:
    """Return "continuation", "reversal", or "neither" for the forward barrier window."""
    for j in range(2, LOOKAHEAD + 2):
        if idx + j >= len(df):
            break
        bar = df.iloc[idx + j]
        if ct == "bullish":
            if bar["low"] <= row["low"]:    return "reversal"
            if bar["high"] >= row["high"]:  return "continuation"
        else:
            if bar["high"] >= row["high"]:  return "reversal"
            if bar["low"] <= row["low"]:    return "continuation"
    return "neither"


def _count_consecutive(idx: int, directions: pd.Series, target: str, max_n: int) -> int:
    count = 0
    for i in range(1, max_n + 1):
        pos = idx - i
        if pos < 0 or directions.iloc[pos] != target:
            break
        count += 1
    return count


# ── Compute Functions ─────────────────────────────────────────────────────────

def compute_basic(df: pd.DataFrame) -> dict:
    """Barrier run rate across all CISDs."""
    ct_arr    = df["cisd_type"].to_numpy(dtype=object)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}
    for pos in event_pos:
        ct = ct_arr[pos]
        totals[ct] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            runs[ct] += 1
    return {"totals": totals, "runs": runs}


def compute_mc(df: pd.DataFrame) -> dict:
    """Barrier run rate bucketed by consecutive opposite candles before CISD."""
    directions = df["direction"]
    ct_arr     = df["cisd_type"].to_numpy(dtype=object)
    event_pos  = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {n: {"total": 0, "runs": 0} for n in range(1, MAX_CONSEC + 1)}
             for ct in ("bullish", "bearish")}
    for pos in event_pos:
        ct     = ct_arr[pos]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(pos, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        stats[ct][consec]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][consec]["runs"] += 1
    return stats


def compute_significance(df: pd.DataFrame) -> dict:
    """Barrier run rate using a stricter CISD definition: close past prev high/low.

    **Intentional cisd_type bypass** — this is the only compute_* function that
    does NOT consume the precomputed ``cisd_type`` column.

    (a) Stricter definition: a CISD here requires the close to surpass the
        *previous bar's high* (bullish: ``close > prev_high``) or fall below
        the *previous bar's low* (bearish: ``close < prev_low``).  This is
        materially stricter than the standard ``cisd_type`` column, which fires
        when ``close > prev_close`` / ``close < prev_close`` with an opposite
        previous direction — a much weaker condition that does not require the
        close to clear the prior candle's wick.

    (b) Why ``cisd_type`` is not consumed: the two definitions measure different
        event populations.  Using ``cisd_type`` here would count bars that close
        past the prior close but not past the prior high/low, changing the
        measured population and the resulting rate.

    (c) This divergence is intentional and behavior-locked, not a bug.  It is
        the sole analysis that defines its own event set; altering the detection
        logic would shift characterization numbers and invalidate any OOS
        validation based on this metric.  Do not "fix" it to use ``cisd_type``.
    """
    idx_arr = df.index
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}
    for i in range(1, len(df) - LOOKAHEAD):
        ph, pl, cc = df["high"].iloc[i-1], df["low"].iloc[i-1], df["close"].iloc[i]
        row = df.iloc[i]
        if cc > ph:
            totals["bullish"] += 1
            if barrier_hit(df, i, row, "bullish"):
                runs["bullish"] += 1
        if cc < pl:
            totals["bearish"] += 1
            if barrier_hit(df, i, row, "bearish"):
                runs["bearish"] += 1
    return {"totals": totals, "runs": runs}


def compute_wick(df: pd.DataFrame) -> dict:
    """Barrier run rate split by wick position of the CISD close."""
    stats = {
        "bullish": {"past_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
        "bearish": {"past_wick": {"total": 0, "runs": 0}, "within_wick": {"total": 0, "runs": 0}},
    }
    prev_dir  = df["prev_direction"].to_numpy(dtype=object)
    close_arr = df["close"].to_numpy(dtype=float)
    prev_close_arr = df["prev_close"].to_numpy(dtype=float)
    prev_high_arr  = df["prev_high"].to_numpy(dtype=float)
    prev_low_arr   = df["prev_low"].to_numpy(dtype=float)

    bull_mask = (
        np.isin(prev_dir, ["bearish"]) &
        (close_arr > prev_close_arr)
    )
    for pos in np.flatnonzero(bull_mask):
        grp = "past_wick" if close_arr[pos] > prev_high_arr[pos] else "within_wick"
        stats["bullish"][grp]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], "bullish"):
            stats["bullish"][grp]["runs"] += 1

    bear_mask = (
        np.isin(prev_dir, ["bullish"]) &
        (close_arr < prev_close_arr)
    )
    for pos in np.flatnonzero(bear_mask):
        grp = "past_wick" if close_arr[pos] < prev_low_arr[pos] else "within_wick"
        stats["bearish"][grp]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], "bearish"):
            stats["bearish"][grp]["runs"] += 1

    return stats


def compute_combined(df: pd.DataFrame) -> dict:
    """Barrier run rate cross-tabulated: wick position x consecutive candle count."""
    directions     = df["direction"]
    ct_arr         = df["cisd_type"].to_numpy(dtype=object)
    close_arr      = df["close"].to_numpy(dtype=float)
    prev_high_arr  = df["prev_high"].to_numpy(dtype=float)
    prev_low_arr   = df["prev_low"].to_numpy(dtype=float)
    event_pos      = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {n: {"past_wick": {"total": 0, "runs": 0},
                       "within_wick": {"total": 0, "runs": 0}}
                  for n in range(1, MAX_CONSEC + 1)} for ct in ("bullish", "bearish")}
    for pos in event_pos:
        ct     = ct_arr[pos]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(pos, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        above = close_arr[pos] > prev_high_arr[pos] if ct == "bullish" else close_arr[pos] < prev_low_arr[pos]
        grp = "past_wick" if above else "within_wick"
        stats[ct][consec][grp]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][consec][grp]["runs"] += 1
    return stats


def compute_volume(df: pd.DataFrame) -> dict:
    """
    Barrier run rate segmented by volume ratio (CISD candle / previous candle).
    Buckets: <1x  |  1-1.5x  |  1.5-2.5x  |  >2.5x
    """
    prev_vol = df["volume"].shift(1)
    BINS = [
        (0,    1.0,  "<1x (lower vol)"),
        (1.0,  1.5,  "1x-1.5x"),
        (1.5,  2.5,  "1.5x-2.5x"),
        (2.5,  1e18, ">2.5x (spike)"),
    ]
    ct_arr     = df["cisd_type"].to_numpy(dtype=object)
    vol_arr    = df["volume"].to_numpy(dtype=float)
    prev_vol_arr = prev_vol.to_numpy(dtype=float)
    event_pos  = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {lbl: {"total": 0, "runs": 0} for _, _, lbl in BINS}
             for ct in ("bullish", "bearish")}
    for pos in event_pos:
        pv = prev_vol_arr[pos]
        if not pv or pd.isna(pv) or pv <= 0:
            continue
        ratio = vol_arr[pos] / pv
        ct    = ct_arr[pos]
        for lo, hi, lbl in BINS:
            if lo <= ratio < hi:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, pos, df.iloc[pos], ct):
                    stats[ct][lbl]["runs"] += 1
                break
    return stats


def compute_candle_size(df: pd.DataFrame) -> dict:
    """
    Barrier run rate segmented by CISD body size as multiple of ATR(14).
    Buckets: <0.5x  |  0.5-1x  |  1-1.5x  |  >1.5x
    """
    atr = (df["high"] - df["low"]).rolling(14).mean()
    BINS = [
        (0,    0.5,  "<0.5x ATR"),
        (0.5,  1.0,  "0.5x-1x ATR"),
        (1.0,  1.5,  "1x-1.5x ATR"),
        (1.5,  1e18, ">1.5x ATR"),
    ]
    ct_arr    = df["cisd_type"].to_numpy(dtype=object)
    close_arr = df["close"].to_numpy(dtype=float)
    open_arr  = df["open"].to_numpy(dtype=float)
    atr_arr   = atr.to_numpy(dtype=float)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {lbl: {"total": 0, "runs": 0} for _, _, lbl in BINS}
             for ct in ("bullish", "bearish")}
    for pos in event_pos:
        atr_val = atr_arr[pos]
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        body  = abs(close_arr[pos] - open_arr[pos])
        ratio = body / atr_val
        ct    = ct_arr[pos]
        for lo, hi, lbl in BINS:
            if lo <= ratio < hi:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, pos, df.iloc[pos], ct):
                    stats[ct][lbl]["runs"] += 1
                break
    return stats


def compute_size_cross(df: pd.DataFrame) -> dict:
    """
    Cross-tab: CISD body size vs previous candle body size, both vs ATR(14).
    Threshold = 1x ATR for each candle.
    4 quadrants:
      big_cisd + small_prev  (CISD >= ATR, prev < ATR)
      big_cisd + big_prev    (both >= ATR)
      small_cisd + small_prev(both < ATR)
      small_cisd + big_prev  (CISD < ATR, prev >= ATR)
    """
    atr       = (df["high"] - df["low"]).rolling(14).mean()
    prev_body = (df["close"].shift(1) - df["open"].shift(1)).abs()

    BUCKETS = [
        (True,  False, "Big CISD / Small prev"),
        (True,  True,  "Big CISD / Big prev"),
        (False, False, "Small CISD / Small prev"),
        (False, True,  "Small CISD / Big prev"),
    ]
    ct_arr        = df["cisd_type"].to_numpy(dtype=object)
    close_arr     = df["close"].to_numpy(dtype=float)
    open_arr      = df["open"].to_numpy(dtype=float)
    atr_arr       = atr.to_numpy(dtype=float)
    prev_body_arr = prev_body.to_numpy(dtype=float)
    event_pos     = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    stats = {ct: {lbl: {"total": 0, "runs": 0}
                  for _, _, lbl in BUCKETS}
             for ct in ("bullish", "bearish")}

    for pos in event_pos:
        atr_val = atr_arr[pos]
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        cisd_big = abs(close_arr[pos] - open_arr[pos]) >= atr_val
        prev_big = prev_body_arr[pos] >= atr_val
        ct = ct_arr[pos]
        for bc, bp, lbl in BUCKETS:
            if cisd_big == bc and prev_big == bp:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, pos, df.iloc[pos], ct):
                    stats[ct][lbl]["runs"] += 1
                break
    return stats


def compute_smt_cisd(df: pd.DataFrame) -> dict:
    """Barrier run rate split by whether a matching Swing SMT co-occurs."""
    if "swing_smt_tag" not in df.columns:
        raise ValueError("df must contain swing_smt_tag column")

    stats = {
        "bullish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
        "bearish": {"w/ SMT": {"total": 0, "runs": 0}, "no SMT": {"total": 0, "runs": 0}},
    }

    ct_arr  = df["cisd_type"].to_numpy(dtype=object)
    tag_arr = df["swing_smt_tag"].to_numpy(dtype=object)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct  = ct_arr[pos]
        tag = tag_arr[pos]
        if ct not in stats or tag not in stats[ct]:
            continue
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][tag]["runs"] += 1
    return stats


def compute_cisd_fvg(df: pd.DataFrame) -> dict:
    """Barrier run rate split by directional FVG presence at CISD bar (mid0) or next bar (mid1)."""
    stats = {
        "bullish": {
            "mid0_fvg": {"total": 0, "runs": 0},
            "mid1_fvg": {"total": 0, "runs": 0},
            "no_fvg": {"total": 0, "runs": 0},
        },
        "bearish": {
            "mid0_fvg": {"total": 0, "runs": 0},
            "mid1_fvg": {"total": 0, "runs": 0},
            "no_fvg": {"total": 0, "runs": 0},
        },
    }
    ct_arr   = df["cisd_type"].to_numpy(dtype=object)
    mid0_arr = df["has_dir_fvg_mid0"].to_numpy(dtype=bool)
    mid1_arr = df["has_dir_fvg_mid1"].to_numpy(dtype=bool)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct  = ct_arr[pos]
        hit = barrier_hit(df, pos, df.iloc[pos], ct)
        if mid0_arr[pos]:
            stats[ct]["mid0_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid0_fvg"]["runs"] += 1
        if mid1_arr[pos]:
            stats[ct]["mid1_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid1_fvg"]["runs"] += 1
        if not mid0_arr[pos] and not mid1_arr[pos]:
            stats[ct]["no_fvg"]["total"] += 1
            if hit:
                stats[ct]["no_fvg"]["runs"] += 1
    return stats


def compute_fvg_hold(df: pd.DataFrame) -> dict:
    """FVG hold rate: how often a directional FVG holds across mid0/mid1 and two failure modes."""
    stats = {
        "bullish": {
            "mid0": {
                "close_through_near_edge": {"total": 0, "held": 0},
                "wick_break_far_extreme": {"total": 0, "held": 0},
            },
            "mid1": {
                "close_through_near_edge": {"total": 0, "held": 0},
                "wick_break_far_extreme": {"total": 0, "held": 0},
            },
        },
        "bearish": {
            "mid0": {
                "close_through_near_edge": {"total": 0, "held": 0},
                "wick_break_far_extreme": {"total": 0, "held": 0},
            },
            "mid1": {
                "close_through_near_edge": {"total": 0, "held": 0},
                "wick_break_far_extreme": {"total": 0, "held": 0},
            },
        },
    }
    ct_arr             = df["cisd_type"].to_numpy(dtype=object)
    mid0_close_arr     = df["fvg_mid0_hold_close_near"].to_numpy(dtype=object)
    mid0_wick_arr      = df["fvg_mid0_hold_wick_far"].to_numpy(dtype=object)
    mid1_close_arr     = df["fvg_mid1_hold_close_near"].to_numpy(dtype=object)
    mid1_wick_arr      = df["fvg_mid1_hold_wick_far"].to_numpy(dtype=object)
    event_pos          = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct = ct_arr[pos]
        for bucket, close_state, wick_state in (
            ("mid0", mid0_close_arr[pos], mid0_wick_arr[pos]),
            ("mid1", mid1_close_arr[pos], mid1_wick_arr[pos]),
        ):
            if close_state != "none":
                stats[ct][bucket]["close_through_near_edge"]["total"] += 1
                if close_state == "held":
                    stats[ct][bucket]["close_through_near_edge"]["held"] += 1
            if wick_state != "none":
                stats[ct][bucket]["wick_break_far_extreme"]["total"] += 1
                if wick_state == "held":
                    stats[ct][bucket]["wick_break_far_extreme"]["held"] += 1
    return stats


def compute_cisd_fvg_interaction(df: pd.DataFrame) -> dict:
    """Barrier run rate cross-tabulated by FVG hold state (held/failed) x mode x bucket."""
    stats = {
        "bullish": {
            "mid0": {
                "close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
            },
            "mid1": {
                "close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
            },
        },
        "bearish": {
            "mid0": {
                "close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
            },
            "mid1": {
                "close_through_near_edge": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
                "wick_break_far_extreme": {"held": {"total": 0, "runs": 0}, "failed": {"total": 0, "runs": 0}},
            },
        },
    }
    ct_arr              = df["cisd_type"].to_numpy(dtype=object)
    mid0_close_arr      = df["fvg_mid0_hold_close_near"].to_numpy(dtype=object)
    mid0_wick_arr       = df["fvg_mid0_hold_wick_far"].to_numpy(dtype=object)
    mid1_close_arr      = df["fvg_mid1_hold_close_near"].to_numpy(dtype=object)
    mid1_wick_arr       = df["fvg_mid1_hold_wick_far"].to_numpy(dtype=object)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct  = ct_arr[pos]
        hit = barrier_hit(df, pos, df.iloc[pos], ct)
        for bucket, close_state, wick_state in (
            ("mid0", mid0_close_arr[pos], mid0_wick_arr[pos]),
            ("mid1", mid1_close_arr[pos], mid1_wick_arr[pos]),
        ):
            if close_state in ("held", "failed"):
                stats[ct][bucket]["close_through_near_edge"][close_state]["total"] += 1
                if hit:
                    stats[ct][bucket]["close_through_near_edge"][close_state]["runs"] += 1
            if wick_state in ("held", "failed"):
                stats[ct][bucket]["wick_break_far_extreme"][wick_state]["total"] += 1
                if hit:
                    stats[ct][bucket]["wick_break_far_extreme"][wick_state]["runs"] += 1
    return stats


def compute_sweep(df: pd.DataFrame) -> dict:
    """Barrier run rate split by presence of a directional sweep before the CISD."""
    stats = {
        "bullish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
        "bearish": {"w/ sweep": {"total": 0, "runs": 0}, "no sweep": {"total": 0, "runs": 0}},
    }
    ct_arr    = df["cisd_type"].to_numpy(dtype=object)
    sweep_arr = df["has_dir_sweep"].to_numpy(dtype=bool)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct  = ct_arr[pos]
        tag = "w/ sweep" if sweep_arr[pos] else "no sweep"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][tag]["runs"] += 1
    return stats


def compute_sssf_swing(df: pd.DataFrame) -> dict:
    """Barrier run rate split by whether prev bar or CISD bar is a directional swing."""
    stats = {
        "bullish": {
            "prev_bar_is_swing": {"total": 0, "runs": 0},
            "cisd_bar_is_swing": {"total": 0, "runs": 0},
            "neither": {"total": 0, "runs": 0},
        },
        "bearish": {
            "prev_bar_is_swing": {"total": 0, "runs": 0},
            "cisd_bar_is_swing": {"total": 0, "runs": 0},
            "neither": {"total": 0, "runs": 0},
        },
    }
    ct_arr       = df["cisd_type"].to_numpy(dtype=object)
    prev_swing   = df["prev_bar_is_dir_swing"].to_numpy(dtype=bool)
    cisd_swing   = df["cisd_bar_is_dir_swing"].to_numpy(dtype=bool)
    event_pos = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())
    for pos in event_pos:
        ct = ct_arr[pos]
        if prev_swing[pos]:
            tag = "prev_bar_is_swing"
        elif cisd_swing[pos]:
            tag = "cisd_bar_is_swing"
        else:
            tag = "neither"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, pos, df.iloc[pos], ct):
            stats[ct][tag]["runs"] += 1
    return stats


def compute_candle1_followthrough(df: pd.DataFrame) -> dict:
    """Barrier run rate split by candle[1] close direction and wick position (two windows).

    Returns {direction: {tag: {total, runs}}} with six tags per direction:
      against_inwindow / with_within_wick_inwindow / with_past_wick_inwindow
      against_forward  / with_within_wick_forward  / with_past_wick_forward

    The _inwindow variants use the standard barrier_hit (lookahead over candle[1]+[2]).
    The _forward variants use barrier_hit_forward (same target/stop, window over candle[2]+[3]).
    Both windows measure the same population: every CISD event, split by candle[1] behaviour.
    """
    _TAGS = ("against", "with_within_wick", "with_past_wick")
    stats = {
        ct: {f"{tag}_{suffix}": {"total": 0, "runs": 0}
             for tag in _TAGS for suffix in ("inwindow", "forward")}
        for ct in ("bullish", "bearish")
    }

    ct_arr      = df["cisd_type"].to_numpy(dtype=object)
    c1dir_arr   = df["candle1_close_dir"].to_numpy(dtype=object)
    c1wick_arr  = df["candle1_past_candle0_wick"].to_numpy(dtype=bool)
    event_pos   = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())

    for pos in event_pos:
        ct = ct_arr[pos]
        if ct not in stats:
            continue

        # Classify core bucket from precomputed columns
        if c1dir_arr[pos] == "with":
            core = "with_past_wick" if c1wick_arr[pos] else "with_within_wick"
        else:
            core = "against"

        row = df.iloc[pos]

        # In-window count (barrier_hit unchanged: lookahead over candle[1]+[2])
        stats[ct][f"{core}_inwindow"]["total"] += 1
        if barrier_hit(df, pos, row, ct):
            stats[ct][f"{core}_inwindow"]["runs"] += 1

        # Forward count (re-anchored: lookahead over candle[2]+[3])
        stats[ct][f"{core}_forward"]["total"] += 1
        if barrier_hit_forward(df, pos, row, ct):
            stats[ct][f"{core}_forward"]["runs"] += 1

    return stats


def compute_post_cisd_context(df: pd.DataFrame) -> dict:
    """Barrier continuation rate after failed candle[1] bucketed by candle[2] gap direction.

    Precondition (D-06): candle[1] fails to close past candle[0]'s extreme.
    Buckets per direction: failed_gap_with / failed_gap_against / failed_gap_flat
    (from precomputed candle2_gap_dir).

    Reading-B (D-04) additional cut: candle2_past_candle1_wick — separate bucket,
    not multiplied into the gap buckets.

    Continuation is measured from idx+2 (no in-window variant, D-06). The
    failed_gap_against population is also partitioned into reversal and neither.
    Returns {dir: {tag: {total, runs}}}.
    """
    _GAP_TAGS = {
        "gap_with":    "failed_gap_with",
        "gap_against": "failed_gap_against",
        "flat":        "failed_gap_flat",
    }
    stats = {
        ct: {
            "failed_gap_with":           {"total": 0, "runs": 0},
            "failed_gap_against":        {"total": 0, "runs": 0},
            "failed_gap_against_reversal": {"total": 0, "runs": 0},
            "failed_gap_against_neither":  {"total": 0, "runs": 0},
            "failed_gap_flat":           {"total": 0, "runs": 0},
            "candle2_past_candle1_wick": {"total": 0, "runs": 0},
        }
        for ct in ("bullish", "bearish")
    }

    ct_arr      = df["cisd_type"].to_numpy(dtype=object)
    failed_arr  = df["candle1_failed_followthrough"].to_numpy(dtype=bool)
    gap_dir_arr = df["candle2_gap_dir"].to_numpy(dtype=object)
    c2wick_arr  = df["candle2_past_candle1_wick"].to_numpy(dtype=bool)
    event_pos   = np.flatnonzero(pd.notna(df["cisd_type"]).to_numpy())

    for pos in event_pos:
        ct = ct_arr[pos]
        if ct not in stats:
            continue

        row = df.iloc[pos]

        # Gap buckets — only if candle[1] failed (precondition)
        if failed_arr[pos]:
            gap_tag = _GAP_TAGS.get(gap_dir_arr[pos], "failed_gap_flat")
            stats[ct][gap_tag]["total"] += 1
            if gap_tag == "failed_gap_against":
                reversal = stats[ct]["failed_gap_against_reversal"]
                neither = stats[ct]["failed_gap_against_neither"]
                reversal["total"] += 1
                neither["total"] += 1
                outcome = barrier_outcome_forward(df, pos, row, ct)
                if outcome == "continuation":
                    stats[ct][gap_tag]["runs"] += 1
                elif outcome == "reversal":
                    reversal["runs"] += 1
                else:
                    neither["runs"] += 1
            elif barrier_hit_forward(df, pos, row, ct):
                stats[ct][gap_tag]["runs"] += 1

        # Reading B — separate, no precondition on failed
        if c2wick_arr[pos]:
            stats[ct]["candle2_past_candle1_wick"]["total"] += 1
            if barrier_hit_forward(df, pos, row, ct):
                stats[ct]["candle2_past_candle1_wick"]["runs"] += 1

    return stats


# ── ANALYSES Registry ─────────────────────────────────────────────────────────

ANALYSES = {
    "basic":        ("Basic Barrier Run Rate",               compute_basic,        chart_basic),
    "mc":           ("Consecutive Candles (Markov)",         compute_mc,           chart_mc),
    "significance": ("Significance Test",                    compute_significance, chart_significance),
    "wick":         ("Wick Position",                        compute_wick,         chart_wick),
    "combined":     ("Combined: Wick x Consecutive",         compute_combined,     chart_combined),
    "volume":       ("Volume Ratio",                         compute_volume,       chart_volume),
    "candle_size":  ("Candle Body vs ATR(14)",               compute_candle_size,  chart_candle_size),
    "size_cross":   ("CISD Body x Prev Body vs ATR",         compute_size_cross,   chart_size_cross),
    "smt_cisd":     ("Swing SMT Confirmation",               compute_smt_cisd,     chart_smt_cisd),
    "cisd_fvg":     ("CISD FVG Creation",                    compute_cisd_fvg,     chart_cisd_fvg),
    "fvg_hold":     ("FVG Hold",                             compute_fvg_hold,     chart_fvg_hold),
    "cisd_fvg_interaction": ("CISD FVG Interaction",         compute_cisd_fvg_interaction, chart_cisd_fvg_interaction),
    "sweep":        ("Sweep Confirmation",                   compute_sweep,        chart_sweep),
    "sssf_swing":   ("SSSF Swing",                           compute_sssf_swing,   chart_sssf_swing),
    "candle1_followthrough": ("Candle[1] Follow-Through",    compute_candle1_followthrough, chart_candle1_followthrough),
    "post_cisd_context":    ("Post-CISD Context",            compute_post_cisd_context,     chart_post_cisd_context),
}


# ── ANALYSIS_META Registry ────────────────────────────────────────────────────
# Single source of truth for the four previously-synchronized sites:
#   1. build_figure base_h dict        (per_tf_height)
#   2. build_standalone_figure base_h  (standalone_height)
#   3. main() STANDALONE_KEYS set      (standalone == True)
#   4. main() FILENAMES dict           (filename)
#
# Adding a new standalone analysis requires editing only this dict.

class _AnalysisMeta(NamedTuple):
    """Metadata record for a single analysis key."""
    per_tf_height:    int         # subplot height hint for build_figure
    standalone:       bool        # True → gets its own all-TF figure
    standalone_height: int | None # subplot height hint for build_standalone_figure; None if not standalone
    filename:         str | None  # output PNG filename for standalone figures; None if not standalone


ANALYSIS_META: dict[str, _AnalysisMeta] = {
    # Non-standalone analyses (per-TF figure only)
    "basic":                _AnalysisMeta(per_tf_height=3,  standalone=False, standalone_height=None, filename=None),
    "significance":         _AnalysisMeta(per_tf_height=3,  standalone=False, standalone_height=None, filename=None),
    "mc":                   _AnalysisMeta(per_tf_height=6,  standalone=False, standalone_height=None, filename=None),
    "wick":                 _AnalysisMeta(per_tf_height=5,  standalone=False, standalone_height=None, filename=None),
    "combined":             _AnalysisMeta(per_tf_height=10, standalone=False, standalone_height=None, filename=None),
    # Standalone analyses (per-TF figure + their own all-TF figure)
    "volume":               _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="Volume_All_Timeframes.png"),
    "candle_size":          _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="CandleSize_All_Timeframes.png"),
    "size_cross":           _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="SizeCross_All_Timeframes.png"),
    "smt_cisd":             _AnalysisMeta(per_tf_height=4,  standalone=True,  standalone_height=6,  filename="SMT_CISD_All_Timeframes.png"),
    "cisd_fvg":             _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="CISD_FVG_All_Timeframes.png"),
    "fvg_hold":             _AnalysisMeta(per_tf_height=8,  standalone=True,  standalone_height=8,  filename="FVG_Hold_All_Timeframes.png"),
    "cisd_fvg_interaction": _AnalysisMeta(per_tf_height=10, standalone=True,  standalone_height=10, filename="CISD_FVG_Interaction_All_Timeframes.png"),
    "sweep":                _AnalysisMeta(per_tf_height=4,  standalone=True,  standalone_height=4,  filename="Sweep_CISD_All_Timeframes.png"),
    "sssf_swing":           _AnalysisMeta(per_tf_height=5,  standalone=True,  standalone_height=5,  filename="SSSF_Swing_All_Timeframes.png"),
    "candle1_followthrough": _AnalysisMeta(per_tf_height=8,  standalone=True,  standalone_height=8,  filename="Candle1_Followthrough_All_Timeframes.png"),
    "post_cisd_context":    _AnalysisMeta(per_tf_height=6,  standalone=True,  standalone_height=6,  filename="PostCISD_Context_All_Timeframes.png"),
}


__all__ = [
    # Barrier logic
    "barrier_hit",
    "_count_consecutive",
    # Compute functions
    "compute_basic",
    "compute_mc",
    "compute_significance",
    "compute_wick",
    "compute_combined",
    "compute_volume",
    "compute_candle_size",
    "compute_size_cross",
    "compute_smt_cisd",
    "compute_cisd_fvg",
    "compute_fvg_hold",
    "compute_cisd_fvg_interaction",
    "compute_sweep",
    "compute_sssf_swing",
    # Registries
    "ANALYSES",
    "ANALYSIS_META",
    # New RES-01 symbols
    "barrier_hit_forward",
    "compute_candle1_followthrough",
    # New RES-04 symbols
    "barrier_outcome_forward",
    # New RES-02 symbols
    "compute_post_cisd_context",
]
