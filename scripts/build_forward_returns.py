from __future__ import annotations

import numpy as np
import pandas as pd

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
