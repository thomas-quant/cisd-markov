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
    df_cisd = df[df["cisd_type"].notna()]
    idx_index = df.index
    totals = {"bullish": 0, "bearish": 0}
    runs   = {"bullish": 0, "bearish": 0}
    for ts, row in df_cisd.iterrows():
        ct = row["cisd_type"]
        totals[ct] += 1
        if barrier_hit(df, idx_index.get_loc(ts), row, ct):
            runs[ct] += 1
    return {"totals": totals, "runs": runs}


def compute_mc(df: pd.DataFrame) -> dict:
    """Barrier run rate bucketed by consecutive opposite candles before CISD."""
    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index
    stats = {ct: {n: {"total": 0, "runs": 0} for n in range(1, MAX_CONSEC + 1)}
             for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx    = idx_index.get_loc(ts)
        ct     = row["cisd_type"]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        stats[ct][consec]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][consec]["runs"] += 1
    return stats


def compute_significance(df: pd.DataFrame) -> dict:
    """Barrier run rate using stricter CISD (close vs prev high/low).

    This function intentionally uses a stricter close-past-prev-high/low
    definition rather than the precomputed ``cisd_type`` column.  The
    standard ``cisd_type`` fires when ``close > prev_close`` (for bullish),
    whereas this function requires ``close > prev_high`` — a materially
    different condition that tests whether the close pushed *past* the
    prior candle's wick, not merely past its close.  The semantic
    distinction is preserved intentionally: this is NOT a bug.
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
    idx_index = df.index
    for ts, row in df[(df["prev_direction"] == "bearish") & (df["close"] > df["prev_close"])].iterrows():
        idx = idx_index.get_loc(ts)
        grp = "past_wick" if row["close"] > row["prev_high"] else "within_wick"
        stats["bullish"][grp]["total"] += 1
        if barrier_hit(df, idx, row, "bullish"):
            stats["bullish"][grp]["runs"] += 1
    for ts, row in df[(df["prev_direction"] == "bullish") & (df["close"] < df["prev_close"])].iterrows():
        idx = idx_index.get_loc(ts)
        grp = "past_wick" if row["close"] < row["prev_low"] else "within_wick"
        stats["bearish"][grp]["total"] += 1
        if barrier_hit(df, idx, row, "bearish"):
            stats["bearish"][grp]["runs"] += 1
    return stats


def compute_combined(df: pd.DataFrame) -> dict:
    """Barrier run rate cross-tabulated: wick position x consecutive candle count."""
    df_cisd    = df[df["cisd_type"].notna()]
    directions = df["direction"]
    idx_index  = df.index
    stats = {ct: {n: {"past_wick": {"total": 0, "runs": 0},
                       "within_wick": {"total": 0, "runs": 0}}
                  for n in range(1, MAX_CONSEC + 1)} for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx    = idx_index.get_loc(ts)
        ct     = row["cisd_type"]
        tgt    = "bearish" if ct == "bullish" else "bullish"
        consec = _count_consecutive(idx, directions, tgt, MAX_CONSEC)
        if consec < 1 or consec > MAX_CONSEC:
            continue
        above = row["close"] > row["prev_high"] if ct == "bullish" else row["close"] < row["prev_low"]
        grp = "past_wick" if above else "within_wick"
        stats[ct][consec][grp]["total"] += 1
        if barrier_hit(df, idx, row, ct):
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
    df_cisd    = df[df["cisd_type"].notna()]
    idx_index  = df.index
    stats = {ct: {lbl: {"total": 0, "runs": 0} for _, _, lbl in BINS}
             for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx   = idx_index.get_loc(ts)
        pv    = prev_vol.iloc[idx]
        if not pv or pd.isna(pv) or pv <= 0:
            continue
        ratio = row["volume"] / pv
        ct    = row["cisd_type"]
        for lo, hi, lbl in BINS:
            if lo <= ratio < hi:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, idx, row, ct):
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
    df_cisd   = df[df["cisd_type"].notna()]
    idx_index = df.index
    stats = {ct: {lbl: {"total": 0, "runs": 0} for _, _, lbl in BINS}
             for ct in ("bullish", "bearish")}
    for ts, row in df_cisd.iterrows():
        idx     = idx_index.get_loc(ts)
        atr_val = atr.iloc[idx]
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        body  = abs(row["close"] - row["open"])
        ratio = body / atr_val
        ct    = row["cisd_type"]
        for lo, hi, lbl in BINS:
            if lo <= ratio < hi:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, idx, row, ct):
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
    atr      = (df["high"] - df["low"]).rolling(14).mean()
    prev_body = (df["close"].shift(1) - df["open"].shift(1)).abs()

    BUCKETS = [
        (True,  False, "Big CISD / Small prev"),
        (True,  True,  "Big CISD / Big prev"),
        (False, False, "Small CISD / Small prev"),
        (False, True,  "Small CISD / Big prev"),
    ]
    df_cisd   = df[df["cisd_type"].notna()]
    idx_index = df.index
    stats = {ct: {lbl: {"total": 0, "runs": 0}
                  for _, _, lbl in BUCKETS}
             for ct in ("bullish", "bearish")}

    for ts, row in df_cisd.iterrows():
        idx     = idx_index.get_loc(ts)
        atr_val = atr.iloc[idx]
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        cisd_big = abs(row["close"] - row["open"]) >= atr_val
        prev_big = prev_body.iloc[idx] >= atr_val
        ct = row["cisd_type"]
        for bc, bp, lbl in BUCKETS:
            if cisd_big == bc and prev_big == bp:
                stats[ct][lbl]["total"] += 1
                if barrier_hit(df, idx, row, ct):
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

    df_cisd = df[df["cisd_type"].notna()]
    idx_index = df.index
    for ts, row in df_cisd.iterrows():
        ct = row["cisd_type"]
        tag = row["swing_smt_tag"]
        if ct not in stats or tag not in stats[ct]:
            continue
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, idx_index.get_loc(ts), row, ct):
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
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        hit = barrier_hit(df, idx, row, ct)
        if row["has_dir_fvg_mid0"]:
            stats[ct]["mid0_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid0_fvg"]["runs"] += 1
        if row["has_dir_fvg_mid1"]:
            stats[ct]["mid1_fvg"]["total"] += 1
            if hit:
                stats[ct]["mid1_fvg"]["runs"] += 1
        if not row["has_dir_fvg_mid0"] and not row["has_dir_fvg_mid1"]:
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
    for _, row in df[df["cisd_type"].notna()].iterrows():
        ct = row["cisd_type"]
        for bucket, close_col, wick_col in (
            ("mid0", "fvg_mid0_hold_close_near", "fvg_mid0_hold_wick_far"),
            ("mid1", "fvg_mid1_hold_close_near", "fvg_mid1_hold_wick_far"),
        ):
            close_state = row[close_col]
            if close_state != "none":
                stats[ct][bucket]["close_through_near_edge"]["total"] += 1
                if close_state == "held":
                    stats[ct][bucket]["close_through_near_edge"]["held"] += 1
            wick_state = row[wick_col]
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
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        hit = barrier_hit(df, idx, row, ct)
        for bucket, close_col, wick_col in (
            ("mid0", "fvg_mid0_hold_close_near", "fvg_mid0_hold_wick_far"),
            ("mid1", "fvg_mid1_hold_close_near", "fvg_mid1_hold_wick_far"),
        ):
            close_state = row[close_col]
            if close_state in ("held", "failed"):
                stats[ct][bucket]["close_through_near_edge"][close_state]["total"] += 1
                if hit:
                    stats[ct][bucket]["close_through_near_edge"][close_state]["runs"] += 1
            wick_state = row[wick_col]
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
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        tag = "w/ sweep" if row["has_dir_sweep"] else "no sweep"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, idx, row, ct):
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
    idx_index = df.index
    for ts, row in df[df["cisd_type"].notna()].iterrows():
        idx = idx_index.get_loc(ts)
        ct = row["cisd_type"]
        if row["prev_bar_is_dir_swing"]:
            tag = "prev_bar_is_swing"
        elif row["cisd_bar_is_dir_swing"]:
            tag = "cisd_bar_is_swing"
        else:
            tag = "neither"
        stats[ct][tag]["total"] += 1
        if barrier_hit(df, idx, row, ct):
            stats[ct][tag]["runs"] += 1
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
]
