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
    if "cisd_type" not in df.columns:
        raise ValueError("df must contain cisd_type column")

    annotated = df.copy()
    swing_low, swing_high = _compute_three_bar_swings(annotated)

    n = len(annotated)
    ct_arr = annotated["cisd_type"].to_numpy(dtype=object)

    # Pre-initialise result lists with defaults (bool columns → False; hold columns → "none")
    has_dir_fvg_mid0_lst          = [False] * n
    has_dir_fvg_mid1_lst          = [False] * n
    fvg_mid0_hold_close_near_lst  = ["none"] * n
    fvg_mid0_hold_wick_far_lst    = ["none"] * n
    fvg_mid1_hold_close_near_lst  = ["none"] * n
    fvg_mid1_hold_wick_far_lst    = ["none"] * n
    has_dir_sweep_lst             = [False] * n
    prev_bar_is_dir_swing_lst     = [False] * n
    cisd_bar_is_dir_swing_lst     = [False] * n

    event_pos = np.flatnonzero(pd.notna(ct_arr) & np.isin(ct_arr, ["bullish", "bearish"]))

    for idx in event_pos:
        ct = ct_arr[idx]

        if ct == "bullish":
            prev_bar_is_dir_swing_lst[idx] = bool(swing_low.iloc[idx - 1]) if idx > 0 else False
            cisd_bar_is_dir_swing_lst[idx] = bool(swing_low.iloc[idx])
        else:
            prev_bar_is_dir_swing_lst[idx] = bool(swing_high.iloc[idx - 1]) if idx > 0 else False
            cisd_bar_is_dir_swing_lst[idx] = bool(swing_high.iloc[idx])

        has_dir_sweep_lst[idx] = _has_directional_sweep(
            annotated,
            idx,
            ct,
            swing_low,
            swing_high,
        )

        if _has_directional_fvg(annotated, idx, ct):
            has_dir_fvg_mid0_lst[idx]         = True
            fvg_mid0_hold_close_near_lst[idx]  = _classify_fvg_hold(annotated, idx, ct, "close_near")
            fvg_mid0_hold_wick_far_lst[idx]    = _classify_fvg_hold(annotated, idx, ct, "wick_far")

        mid1_idx = idx + 1
        if _has_directional_fvg(annotated, mid1_idx, ct):
            has_dir_fvg_mid1_lst[idx]         = True
            fvg_mid1_hold_close_near_lst[idx]  = _classify_fvg_hold(annotated, mid1_idx, ct, "close_near")
            fvg_mid1_hold_wick_far_lst[idx]    = _classify_fvg_hold(annotated, mid1_idx, ct, "wick_far")

    # Bulk-assign accumulated lists to columns
    annotated["has_dir_fvg_mid0"]         = has_dir_fvg_mid0_lst
    annotated["has_dir_fvg_mid1"]         = has_dir_fvg_mid1_lst
    annotated["fvg_mid0_hold_close_near"] = fvg_mid0_hold_close_near_lst
    annotated["fvg_mid0_hold_wick_far"]   = fvg_mid0_hold_wick_far_lst
    annotated["fvg_mid1_hold_close_near"] = fvg_mid1_hold_close_near_lst
    annotated["fvg_mid1_hold_wick_far"]   = fvg_mid1_hold_wick_far_lst
    annotated["has_dir_sweep"]            = has_dir_sweep_lst
    annotated["prev_bar_is_dir_swing"]    = prev_bar_is_dir_swing_lst
    annotated["cisd_bar_is_dir_swing"]    = cisd_bar_is_dir_swing_lst

    return annotated


def _annotate_swing_smt_from_events(df: pd.DataFrame, events: pd.DataFrame, instrument: str) -> pd.DataFrame:
    required_event_columns = ("signal_type", "created_ts", "sweeping_asset", "failing_asset")
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

    if annotated.empty or events.empty:
        return annotated

    event_rows = []
    for row in events.itertuples(index=False):
        signal_type = getattr(row, "signal_type", None)
        created_ts = getattr(row, "created_ts", None)
        sweeping_asset = getattr(row, "sweeping_asset", None)
        failing_asset = getattr(row, "failing_asset", None)
        if pd.isna(created_ts) or signal_type is None:
            continue
        direction = "bullish" if str(signal_type).startswith("Bullish") else "bearish" if str(signal_type).startswith("Bearish") else None
        if direction is None:
            continue
        event_rows.append(
            {
                "created_ts": created_ts,
                "direction": direction,
                "sweeping_asset": sweeping_asset,
                "failing_asset": failing_asset,
            }
        )

    if not event_rows:
        return annotated

    event_rows.sort(key=lambda r: r["created_ts"])

    for idx, ts in enumerate(annotated.index):
        ct = annotated.iat[idx, annotated.columns.get_loc("cisd_type")]
        if ct not in ("bullish", "bearish"):
            continue

        lower_idx = max(0, idx - 2)
        lower_ts = annotated.index[lower_idx]
        best_event = None
        for event in event_rows:
            if event["direction"] != ct:
                continue
            if lower_ts <= event["created_ts"] <= ts:
                best_event = event

        if best_event is None:
            continue

        annotated.iat[idx, annotated.columns.get_loc("has_swing_smt")] = True
        annotated.iat[idx, annotated.columns.get_loc("swing_smt_tag")] = "w/ SMT"
        annotated.iat[idx, annotated.columns.get_loc("swing_smt_match_ts")] = best_event["created_ts"]
        if instrument == best_event["sweeping_asset"]:
            annotated.iat[idx, annotated.columns.get_loc("swing_smt_role")] = "swept"
        elif instrument == best_event["failing_asset"]:
            annotated.iat[idx, annotated.columns.get_loc("swing_smt_role")] = "failed_to_sweep"

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
