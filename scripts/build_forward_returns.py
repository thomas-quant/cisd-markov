from __future__ import annotations

import numpy as np
import pandas as pd

from cisd_analysis import MAX_CONSEC, _count_consecutive

FORWARD_RETURNS_LOOKAHEAD = 7
PERCENTILE_LEVELS = [5, 25, 50, 75, 95]


def core_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["smt"], state["size_cross"], state["wick"], state["consec"]])


def fvg_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["fvg_bucket"], state["fvg_mode"], state["fvg_state"]])


def structure_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["sweep"], state["prev_swing"], state["cisd_swing"]])


def percentile_payload(series: pd.Series) -> dict[str, float] | None:
    if series.empty:
        return None
    values = series.to_numpy(dtype=float)
    return {str(level): float(np.percentile(values, level)) for level in PERCENTILE_LEVELS}


def _ensure_column(frame: pd.DataFrame, column: str, default) -> None:
    if column not in frame.columns:
        frame[column] = default


def _classify_wick(prepared: pd.DataFrame, idx: int, cisd_type: str) -> str:
    row = prepared.iloc[idx]
    if cisd_type == "bullish":
        return "past_wick" if row["close"] > row["prev_high"] else "within_wick"
    if cisd_type == "bearish":
        return "past_wick" if row["close"] < row["prev_low"] else "within_wick"
    return "all"


def _classify_size_cross(prepared: pd.DataFrame, idx: int, atr_series: pd.Series) -> str:
    atr = atr_series.iloc[idx]
    if pd.isna(atr) or atr <= 0:
        return "all"

    row = prepared.iloc[idx]
    prev_row = prepared.iloc[idx - 1] if idx > 0 else None
    cisd_big = abs(row["close"] - row["open"]) >= atr
    prev_big = bool(prev_row is not None and abs(prev_row["close"] - prev_row["open"]) >= atr)

    if cisd_big and not prev_big:
        return "Big CISD / Small prev"
    if cisd_big and prev_big:
        return "Big CISD / Big prev"
    if not cisd_big and not prev_big:
        return "Small CISD / Small prev"
    return "Small CISD / Big prev"


def build_forward_return_rows(prepared: pd.DataFrame, instrument: str) -> pd.DataFrame:
    rows = prepared[prepared["cisd_type"].notna()].copy()

    for column, default in (
        ("swing_smt_tag", "no SMT"),
        ("has_dir_fvg_mid0", False),
        ("has_dir_fvg_mid1", False),
        ("fvg_mid0_hold_close_near", "none"),
        ("fvg_mid1_hold_close_near", "none"),
        ("fvg_mid0_hold_wick_far", "none"),
        ("fvg_mid1_hold_wick_far", "none"),
        ("has_dir_sweep", False),
        ("prev_bar_is_dir_swing", False),
        ("cisd_bar_is_dir_swing", False),
    ):
        _ensure_column(rows, column, default)

    rows["instrument"] = instrument
    rows["smt"] = rows["swing_smt_tag"]
    rows["size_cross"] = "all"
    rows["wick"] = "all"
    rows["consec"] = "all"

    rows["fvg_bucket"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        ["mid0", "mid1"],
        default="no_fvg",
    )
    rows["fvg_state_close_through_near_edge"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_close_near"], rows["fvg_mid1_hold_close_near"]],
        default="none",
    )
    rows["fvg_state_wick_break_far_extreme"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_wick_far"], rows["fvg_mid1_hold_wick_far"]],
        default="none",
    )
    rows["sweep"] = np.where(rows["has_dir_sweep"], "w/ sweep", "no sweep")
    rows["prev_swing"] = np.where(rows["prev_bar_is_dir_swing"], "yes", "no")
    rows["cisd_swing"] = np.where(rows["cisd_bar_is_dir_swing"], "yes", "no")

    atr_series = (prepared["high"] - prepared["low"]).rolling(14).mean()
    directions = prepared["direction"] if "direction" in prepared.columns else pd.Series(index=prepared.index, dtype=object)
    for ts, row in rows.iterrows():
        idx = prepared.index.get_loc(ts)
        rows.at[ts, "size_cross"] = _classify_size_cross(prepared, idx, atr_series)
        rows.at[ts, "wick"] = _classify_wick(prepared, idx, row["cisd_type"])
        opposite = "bearish" if row["cisd_type"] == "bullish" else "bullish"
        rows.at[ts, "consec"] = str(_count_consecutive(idx, directions, opposite, MAX_CONSEC))

    future_close = prepared["close"].shift(-FORWARD_RETURNS_LOOKAHEAD).reindex(rows.index)
    raw_return = (future_close / rows["close"] - 1.0) * 100.0
    rows["forward_return_pct"] = np.where(rows["cisd_type"] == "bearish", -raw_return, raw_return)
    return rows[rows["forward_return_pct"].notna()].copy()


def apply_family_filters(rows: pd.DataFrame, family: str, state: dict[str, str]) -> pd.DataFrame:
    filtered = rows

    if family == "core":
        for column, key in (("smt", "smt"), ("size_cross", "size_cross"), ("wick", "wick"), ("consec", "consec")):
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered.copy()

    if family == "fvg":
        if state["fvg_bucket"] != "all":
            filtered = filtered[filtered["fvg_bucket"] == state["fvg_bucket"]]
        if state["fvg_mode"] != "all" and state["fvg_state"] != "all":
            filtered = filtered[filtered[f"fvg_state_{state['fvg_mode']}"] == state["fvg_state"]]
        return filtered.copy()

    if family == "structure":
        for column, key in (("sweep", "sweep"), ("prev_swing", "prev_swing"), ("cisd_swing", "cisd_swing")):
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered.copy()

    raise ValueError(f"unknown family: {family}")
