"""
tests/test_conditioning_features.py — Phase 10 Plan 01 conditioning-feature columns
====================================================================================
Held-out assertions for the new annotation columns added to
`_annotate_cisd_research` in `cisd_data.py` (`.planning/phases/10-new-
conditioning-features-magnitude-session-volume-anomaly/10-01-PLAN.md`):

- Task 1 (magnitude): `wick_distance_atr` (signed, all CISDs), `swept_level` +
  `sweep_depth_atr` (gated on `has_dir_sweep`), `fvg_gap_width` +
  `fvg_size_atr` (gated on `has_dir_fvg_mid0`/`mid1`, mid0-priority union).
- Task 2 (session): `session_tag` partitioning every bar into `rth_open` /
  `rth` / `overnight` from the frozen `RTH_OPEN_START_MIN` /
  `RTH_OPEN_END_MIN` / `RTH_END_MIN` minute-of-day constants.
- Task 3 (volume anomaly): `vol_per_range` (effort-vs-result), `rvol` /
  `volume_zscore` (same-time-of-day-slot trailing baseline, frozen
  `RVOL_SLOT_K`).

All fixtures are synthetic (hand-built annotation-input frames, bypassing
`prepare()`/`resample_ohlcv` entirely — the same style as
`tests/test_smt_geometry.py`) — no data files or SMT package required.
`_annotate_cisd_research` is called directly, so fixtures must supply every
column `prepare()` would normally set before calling it: `open`, `high`,
`low`, `close`, `volume`, `cisd_type`, `prev_high`, `prev_low`.
"""

import numpy as np
import pandas as pd
import pytest

from cisd_data import (
    _annotate_cisd_research,
    RTH_OPEN_START_MIN,
    RTH_OPEN_END_MIN,
    RTH_END_MIN,
    RVOL_SLOT_K,
)


# ── Fixture helper ───────────────────────────────────────────────────────────

def _fixture(n, freq="15min", start="2026-01-01 09:00", **overrides):
    """A flat, no-swing, no-FVG base frame: constant high-low=2.0 range (so
    ATR(14) stabilizes at 2.0 once 14 rows have accumulated) and flat
    open/close (so no 3-bar swings, no FVGs form by construction unless a
    row is explicitly overridden). `cisd_type` defaults to None everywhere.
    """
    idx = pd.date_range(start, periods=n, freq=freq)
    data = {
        "open":      [100.0] * n,
        "high":      [101.0] * n,
        "low":       [99.0] * n,
        "close":     [100.0] * n,
        "cisd_type": [None] * n,
        "prev_high": [np.nan] * n,
        "prev_low":  [np.nan] * n,
        "volume":    [1000.0] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data, index=idx)


# ── Task 1: wick_distance_atr (signed, all CISDs) ───────────────────────────

def test_wick_distance_atr_signed_past_vs_within_wick():
    n = 16
    cisd_types = [None] * n
    prev_high  = [np.nan] * n
    highs      = [101.0] * n
    lows       = [99.0] * n
    closes     = [100.0] * n

    # Row 14 (0-indexed, ATR window already warmed up): bullish CISD closing
    # ABOVE prev_high -> strictly positive wick_distance_atr ("past the wick").
    cisd_types[14] = "bullish"
    prev_high[14]  = 100.0
    closes[14]     = 105.0
    highs[14]      = 106.0
    lows[14]       = 104.0  # keep high-low=2.0 so ATR stays 2.0

    # Row 15: bullish CISD closing AT-OR-BELOW prev_high -> <=0 ("within the
    # prior wick").
    cisd_types[15] = "bullish"
    prev_high[15]  = 100.0
    closes[15]     = 99.0
    highs[15]      = 100.0
    lows[15]       = 98.0

    df = _fixture(n, cisd_type=cisd_types, prev_high=prev_high,
                  high=highs, low=lows, close=closes)
    out = _annotate_cisd_research(df)

    assert out["wick_distance_atr"].iloc[14] == pytest.approx(2.5)
    assert out["wick_distance_atr"].iloc[14] > 0
    assert out["wick_distance_atr"].iloc[15] == pytest.approx(-0.5)
    assert out["wick_distance_atr"].iloc[15] <= 0
    # non-CISD rows are NaN
    assert out["wick_distance_atr"].iloc[:14].isna().all()


def test_wick_distance_atr_bearish_mirror():
    n = 16
    cisd_types = [None] * n
    prev_low   = [np.nan] * n
    highs      = [101.0] * n
    lows       = [99.0] * n
    closes     = [100.0] * n

    # Bearish CISD closing BELOW prev_low -> positive (past the wick).
    cisd_types[14] = "bearish"
    prev_low[14]   = 100.0
    closes[14]     = 95.0
    highs[14]      = 96.0
    lows[14]       = 94.0

    df = _fixture(n, cisd_type=cisd_types, prev_low=prev_low,
                  high=highs, low=lows, close=closes)
    out = _annotate_cisd_research(df)

    assert out["wick_distance_atr"].iloc[14] == pytest.approx(2.5)
    assert out["wick_distance_atr"].iloc[14] > 0


# ── Task 1: sweep_depth_atr / fvg_size_atr NaN off-population ──────────────

def test_sweep_and_fvg_magnitudes_nan_off_population():
    n = 16
    cisd_types = [None] * n
    cisd_types[14] = "bullish"  # a CISD with no sweep and no FVG (flat data)
    df = _fixture(n, cisd_type=cisd_types)

    out = _annotate_cisd_research(df)

    # Flat high/low series -> no 3-bar swings -> has_dir_sweep is False
    # everywhere -> sweep_depth_atr / swept_level are NaN everywhere.
    assert out["sweep_depth_atr"].isna().all()
    assert out["swept_level"].isna().all()
    # Flat data -> left_high >= right_low (no gap) -> no FVG anywhere.
    assert out["fvg_gap_width"].isna().all()
    assert out["fvg_size_atr"].isna().all()


# ── Task 1: dtype / presence ────────────────────────────────────────────────

def test_magnitude_columns_present_and_float_dtype():
    df = _fixture(16, cisd_type=[None] * 16)
    out = _annotate_cisd_research(df)
    for col in ("wick_distance_atr", "swept_level", "sweep_depth_atr",
                "fvg_gap_width", "fvg_size_atr"):
        assert col in out.columns
        assert out[col].dtype == float


# ── Task 2: session_tag frozen minute-of-day boundaries ─────────────────────

def test_frozen_session_constants():
    assert RTH_OPEN_START_MIN == 570
    assert RTH_OPEN_END_MIN == 630
    assert RTH_END_MIN == 960


def test_session_tag_partitions_every_bar():
    idx = pd.to_datetime([
        "2026-01-05 09:45",   # rth_open (09:30-10:30)
        "2026-01-05 11:00",   # rth (10:30-16:00)
        "2026-01-05 20:00",   # overnight
        "2026-01-06 02:00",   # overnight
    ])
    n = len(idx)
    df = pd.DataFrame({
        "open":      [100.0] * n,
        "high":      [101.0] * n,
        "low":       [99.0] * n,
        "close":     [100.0] * n,
        "cisd_type": [None] * n,
        "prev_high": [np.nan] * n,
        "prev_low":  [np.nan] * n,
        "volume":    [1000.0] * n,
    }, index=idx)

    out = _annotate_cisd_research(df)

    assert list(out["session_tag"]) == ["rth_open", "rth", "overnight", "overnight"]
    assert set(out["session_tag"].unique()) <= {"rth_open", "rth", "overnight"}
    assert not out["session_tag"].isna().any()


# ── Task 3: vol_per_range (effort-vs-result, baseline-free) ────────────────

def test_vol_per_range_matches_volume_over_range_and_nan_when_flat():
    n = 3
    df = _fixture(n, cisd_type=[None] * n)
    df.loc[df.index[0], ["high", "low", "volume"]] = [110.0, 100.0, 500.0]  # range=10
    df.loc[df.index[1], ["high", "low", "volume"]] = [100.0, 100.0, 500.0]  # range=0 -> NaN

    out = _annotate_cisd_research(df)

    assert out["vol_per_range"].iloc[0] == pytest.approx(50.0)
    assert pd.isna(out["vol_per_range"].iloc[1])


# ── Task 3: rvol / volume_zscore same-time-of-day-slot trailing baseline ───

def test_rvol_and_zscore_slot_baseline_trailing_and_warmup_nan():
    K = RVOL_SLOT_K
    n = K + 5
    # Same clock time every day -> single time-of-day slot (degenerates to a
    # plain trailing baseline, matching the Daily-frame behavior in D-08).
    idx = pd.date_range("2026-01-01 09:30", periods=n, freq="1D")
    volumes = [100.0] * K + [200.0] * 5
    df = pd.DataFrame({
        "open":      [100.0] * n,
        "high":      [101.0] * n,
        "low":       [99.0] * n,
        "close":     [100.0] * n,
        "cisd_type": [None] * n,
        "prev_high": [np.nan] * n,
        "prev_low":  [np.nan] * n,
        "volume":    volumes,
    }, index=idx)

    out = _annotate_cisd_research(df)

    # Warm-up: fewer than K prior same-slot observations -> NaN.
    assert out["rvol"].iloc[:K].isna().all()
    assert out["volume_zscore"].iloc[:K].isna().all()

    # Row K (K+1-th row): trailing mean of the prior K rows (all 100.0) = 100.0.
    assert out["rvol"].iloc[K] == pytest.approx(200.0 / 100.0)

    # Row K+1: trailing mean of rows [1..K] = (19*100 + 200) / 20.
    expected_mean = (19 * 100.0 + 200.0) / 20.0
    assert out["rvol"].iloc[K + 1] == pytest.approx(200.0 / expected_mean)


def test_volume_columns_present_and_float_dtype():
    df = _fixture(5, cisd_type=[None] * 5)
    out = _annotate_cisd_research(df)
    for col in ("vol_per_range", "rvol", "volume_zscore"):
        assert col in out.columns
        assert out[col].dtype == float
