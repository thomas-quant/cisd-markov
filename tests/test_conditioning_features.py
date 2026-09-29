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
`_annotate_cisd_research` is called directly with a minimal
`open`/`high`/`low`/`close`/`cisd_type`/`volume` frame; `prev_high`/
`prev_low` are derived internally from `high`/`low`.shift(1) (matching
`prepare()`'s own definition) rather than read from a pre-supplied column,
so fixtures control wick-distance scenarios via the actual preceding bar's
`high`/`low`, not an overridable `prev_high`/`prev_low` column.
"""

import numpy as np
import pandas as pd
import pytest

from cisd_data import _annotate_cisd_research

# NOTE: RTH_OPEN_START_MIN/RTH_OPEN_END_MIN/RTH_END_MIN (Task 2) and
# RVOL_SLOT_K (Task 3) are imported locally inside the tests that need them,
# not at module level — this plan implements the three column families
# (magnitude / session / volume) across three sequential commits, and a
# module-level import of a not-yet-defined constant would break collection
# of the earlier task's already-passing tests (`-k` selection still needs
# the module to import cleanly).


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
        "volume":    [1000.0] * n,
    }
    data.update(overrides)
    return pd.DataFrame(data, index=idx)


# ── Task 1: wick_distance_atr (signed, all CISDs) ───────────────────────────

def test_wick_distance_atr_signed_past_vs_within_wick():
    n = 18
    cisd_types = [None] * n
    highs      = [101.0] * n
    lows       = [99.0] * n
    closes     = [100.0] * n

    # Row 13 (0-indexed): the "reference" bar whose high (100.0) becomes
    # row 14's prev_high via high.shift(1). Keep high-low=2.0 so ATR(14)
    # (warmed up by row 13) stays exactly 2.0 throughout.
    highs[13] = 100.0
    lows[13]  = 98.0

    # Row 14: bullish CISD closing ABOVE prev_high (100.0) -> strictly
    # positive wick_distance_atr ("past the wick").
    cisd_types[14] = "bullish"
    closes[14]     = 105.0
    highs[14]      = 106.0
    lows[14]       = 104.0

    # Row 15: a second "reference" bar (high=100.0) for row 16's prev_high.
    highs[15] = 100.0
    lows[15]  = 98.0

    # Row 16: bullish CISD closing AT-OR-BELOW prev_high (100.0) -> <=0
    # ("within the prior wick").
    cisd_types[16] = "bullish"
    closes[16]     = 99.0
    highs[16]      = 100.0
    lows[16]       = 98.0

    df = _fixture(n, cisd_type=cisd_types, high=highs, low=lows, close=closes)
    out = _annotate_cisd_research(df)

    assert out["wick_distance_atr"].iloc[14] == pytest.approx(2.5)
    assert out["wick_distance_atr"].iloc[14] > 0
    assert out["wick_distance_atr"].iloc[16] == pytest.approx(-0.5)
    assert out["wick_distance_atr"].iloc[16] <= 0
    # non-CISD rows are NaN
    non_cisd = out["wick_distance_atr"].drop(out.index[[14, 16]])
    assert non_cisd.isna().all()


def test_wick_distance_atr_bearish_mirror():
    n = 16
    cisd_types = [None] * n
    highs      = [101.0] * n
    lows       = [99.0] * n
    closes     = [100.0] * n

    # Row 13: reference bar whose low (100.0) becomes row 14's prev_low.
    highs[13] = 102.0
    lows[13]  = 100.0

    # Row 14: bearish CISD closing BELOW prev_low (100.0) -> positive
    # (past the wick).
    cisd_types[14] = "bearish"
    closes[14]     = 95.0
    highs[14]      = 96.0
    lows[14]       = 94.0

    df = _fixture(n, cisd_type=cisd_types, high=highs, low=lows, close=closes)
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
    from cisd_data import RTH_OPEN_START_MIN, RTH_OPEN_END_MIN, RTH_END_MIN
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
    from cisd_data import RVOL_SLOT_K
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


# ── Phase 10 Plan 02, Task 1: compute_wick_distance / compute_sweep_depth /
#    compute_fvg_size (magnitude compute functions) ─────────────────────────

def test_wick_distance_population_all_cisds_and_nan_atr_skipped():
    """Population is ALL CISDs; a row whose wick_distance_atr is NaN (e.g.
    ATR not yet warmed up) is skipped, not counted in any bucket."""
    from cisd_barriers import compute_wick_distance

    n = 20
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    cisd_types = [None] * n
    cisd_types[2] = "bullish"    # NaN wick_distance_atr -> excluded
    cisd_types[16] = "bearish"   # real value -> counted
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n, "close": [100.0] * n,
        "cisd_type": cisd_types,
        "wick_distance_atr": [np.nan] * n,
    }, index=idx)
    df.loc[df.index[16], "wick_distance_atr"] = 0.8  # positive -> "past wick" bin

    out = compute_wick_distance(df)
    total = sum(d["total"] for ct in out for d in out[ct].values())
    assert total == 1
    assert out["bearish"]["0-1x ATR (past wick)"]["total"] == 1


def test_wick_distance_reconciles_with_compute_wick():
    """The signed 0-edge bins recover compute_wick's past_wick/within_wick
    split exactly (D-06) — this is a structural identity: wick_distance_atr
    is (close - prev_high)/ATR (bullish) / (prev_low - close)/ATR (bearish),
    so its sign decomposes the same close-vs-prior-wick comparison compute_wick
    already makes, as long as ratio == 0 (close exactly at the prior wick) is
    classified "within" on both sides (compute_wick uses strict `>`/`<`)."""
    from cisd_data import prepare
    from cisd_barriers import compute_wick, compute_wick_distance

    rng = np.random.default_rng(7)
    n = 120
    opens, highs, lows, closes = [], [], [], []
    price = 100.0
    for i in range(n):
        if i < 20:
            # Strict monotonic uptrend warm-up: guarantees no CISD fires
            # before ATR(14) warms up (rolling(14) needs 14 full rows).
            o = price
            c = price + 1.0
        else:
            o = price
            c = price + rng.normal(0, 1.5)
        h = max(o, c) + abs(rng.normal(0, 0.5)) + 0.1
        l = min(o, c) - abs(rng.normal(0, 0.5)) - 0.1
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        price = c

    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [1000.0] * n,
    }, index=idx)

    out = prepare(df)
    wick_stats = compute_wick(out)
    wd_stats = compute_wick_distance(out)

    total_events = 0
    for ct in ("bullish", "bearish"):
        past_total = wick_stats[ct]["past_wick"]["total"]
        within_total = wick_stats[ct]["within_wick"]["total"]
        total_events += past_total + within_total

        nonneg_total = (wd_stats[ct]["0-1x ATR (past wick)"]["total"]
                        + wd_stats[ct][">1x ATR (far past wick)"]["total"])
        neg_total = (wd_stats[ct]["<-1x ATR (deep within wick)"]["total"]
                     + wd_stats[ct]["-1x-0 ATR (within wick)"]["total"])

        assert nonneg_total == past_total
        assert neg_total == within_total

    assert total_events > 0  # sanity: the synthetic series actually produced CISDs


def test_sweep_depth_and_fvg_size_gate_on_nan_ratio():
    """compute_sweep_depth / compute_fvg_size trust the annotation's NaN
    gating (D-05) — rows with a NaN ratio contribute to no bucket, and
    rows with a non-CISD cisd_type are excluded regardless of ratio."""
    from cisd_barriers import compute_sweep_depth, compute_fvg_size

    # Rows 1 and 4 (the FVG events) are wide bars and the rest stay inside
    # them, so both are still unresolved at the confirm-then-enter entry
    # close[t+2] that compute_fvg_size scores from (quick task 260929-mkg).
    n = 10
    wide = {1, 4}
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": [100.0] * n,
        "high": [105.0 if i in wide else 101.0 for i in range(n)],
        "low":  [95.0 if i in wide else 99.0 for i in range(n)],
        "close": [100.0] * n,
        "cisd_type": ["bullish", "bearish", None, "bullish", "bearish"] + [None] * 5,
        "sweep_depth_atr": [0.8, np.nan, 999.0, 1.2, np.nan] + [np.nan] * 5,
        "fvg_size_atr":    [np.nan, 0.3, 999.0, np.nan, 1.8] + [np.nan] * 5,
    }, index=idx)

    sweep_stats = compute_sweep_depth(df)
    fvg_stats = compute_fvg_size(df)

    sweep_total = sum(d["total"] for ct in sweep_stats for d in sweep_stats[ct].values())
    fvg_total = sum(d["total"] for ct in fvg_stats for d in fvg_stats[ct].values())

    assert sweep_total == 2   # rows 0, 3 (row 2 has a ratio but no cisd_type)
    assert fvg_total == 2     # rows 1, 4


def test_magnitude_compute_functions_in_all():
    import cisd_barriers
    for name in ("compute_wick_distance", "compute_sweep_depth", "compute_fvg_size"):
        assert name in cisd_barriers.__all__


# ── Phase 10 Plan 02, Task 2: compute_effort_result / compute_rvol /
#    compute_volume_zscore (volume-anomaly compute functions, frozen bins) ──

def test_volume_anomaly_compute_functions_flat_shape_and_bin_boundaries():
    """Frozen bins (discovery-slice percentiles, outcome-blind, 2026-07-12):
      vol_per_range: [81, 156, 268, 552, 968, 1500, 5192]
      rvol:          [0.49, 0.66, 0.74, 0.90, 1.07, 1.21, 1.65]
      volume_zscore: [-1.07, -0.69, -0.54, -0.23, 0.17, 0.48, 1.48]
    """
    from cisd_barriers import compute_effort_result, compute_rvol, compute_volume_zscore

    n = 6
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n, "close": [100.0] * n,
        "cisd_type":      ["bullish", "bearish", None,    "bullish", "bearish", "bullish"],
        "vol_per_range":  [100.0,    np.nan,    999999.0, 2000.0,   np.nan,    np.nan],
        "rvol":           [np.nan,   0.5,       np.nan,   np.nan,   1.0,       np.nan],
        "volume_zscore":  [np.nan,   np.nan,    np.nan,   -1.2,     np.nan,    2.0],
    }, index=idx)

    effort = compute_effort_result(df)
    rvol = compute_rvol(df)
    zscore = compute_volume_zscore(df)

    effort_total = sum(d["total"] for ct in effort for d in effort[ct].values())
    rvol_total = sum(d["total"] for ct in rvol for d in rvol[ct].values())
    zscore_total = sum(d["total"] for ct in zscore for d in zscore[ct].values())

    assert effort_total == 2   # rows 0, 3 (row 2 excluded: cisd_type is None)
    assert rvol_total == 2     # rows 1, 4
    assert zscore_total == 2   # rows 3, 5

    assert effort["bullish"]["<150"]["total"] == 1          # row 0: 100
    assert effort["bullish"][">1500"]["total"] == 1          # row 3: 2000
    assert rvol["bearish"]["<0.7x slot"]["total"] == 1        # row 1: 0.5
    assert rvol["bearish"]["1x-1.5x slot (elevated)"]["total"] == 1  # row 4: 1.0 boundary
    assert zscore["bullish"]["<-0.5 sigma"]["total"] == 1     # row 3: -1.2
    assert zscore["bullish"][">1.5 sigma (spike)"]["total"] == 1  # row 5: 2.0


def test_volume_anomaly_compute_functions_in_all():
    import cisd_barriers
    for name in ("compute_effort_result", "compute_rvol", "compute_volume_zscore"):
        assert name in cisd_barriers.__all__


# ── Phase 10 Plan 02, Task 3: registry wiring for all six new analyses ─────

# ── Phase 10 Plan 03, Task 1: compute_session (flat 3-tag, TF-agnostic) ────

def test_compute_session_flat_shape_and_totals_sum_to_all_cisds():
    """compute_session returns the flat {ct: {rth_open|rth|overnight: {total,
    runs}}} shape; every CISD contributes to exactly one bucket per its
    session_tag, so bucket totals sum to the total CISD count (D-01/D-14)."""
    from cisd_barriers import compute_session

    n = 6
    idx = pd.date_range("2026-01-01", periods=n, freq="15min")
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n, "close": [100.0] * n,
        "cisd_type":   ["bullish", "bearish", None,        "bullish", "bearish", "bullish"],
        "session_tag": ["rth_open", "rth",    "overnight", "overnight", "rth_open", "rth"],
    }, index=idx)

    out = compute_session(df)

    for ct in ("bullish", "bearish"):
        assert set(out[ct].keys()) == {"rth_open", "rth", "overnight"}
        for tag in ("rth_open", "rth", "overnight"):
            assert set(out[ct][tag].keys()) == {"total", "runs"}

    total = sum(d["total"] for ct in out for d in out[ct].values())
    assert total == 5  # rows 0,1,3,4,5 (row 2 has no cisd_type)
    assert out["bullish"]["rth_open"]["total"] == 1   # row 0
    assert out["bearish"]["rth"]["total"] == 1        # row 1
    assert out["bullish"]["overnight"]["total"] == 1  # row 3
    assert out["bearish"]["rth_open"]["total"] == 1   # row 4
    assert out["bullish"]["rth"]["total"] == 1        # row 5


def test_compute_session_all_three_buckets_populated_on_15min_frame():
    """On a 15min frame spanning all three sessions, all three buckets are
    populated for a direction with CISDs in each session."""
    from cisd_barriers import compute_session

    n = 3
    idx = pd.date_range("2026-01-01 09:45", periods=n, freq="1D")
    df = pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n, "low": [99.0] * n, "close": [100.0] * n,
        "cisd_type":   ["bullish", "bullish", "bullish"],
        "session_tag": ["rth_open", "rth", "overnight"],
    }, index=idx)

    out = compute_session(df)

    assert out["bullish"]["rth_open"]["total"] == 1
    assert out["bullish"]["rth"]["total"] == 1
    assert out["bullish"]["overnight"]["total"] == 1


def test_compute_session_registered_in_analyses_and_all():
    import cisd_barriers
    from cisd_barriers import ANALYSES

    assert "session" in ANALYSES
    assert "compute_session" in cisd_barriers.__all__


# ── Phase 10 Plan 03, Task 2: applies_to field + figure-dispatch scoping ───

def test_analysis_meta_applies_to_scope():
    from cisd_barriers import ANALYSIS_META

    assert ANALYSIS_META["session"].applies_to == ("1H", "15min")
    assert all(m.applies_to is None for k, m in ANALYSIS_META.items() if k != "session")


def test_applies_to_helper_scopes_session_to_intraday():
    from cisd_barriers import ANALYSIS_META
    from cisd_charts import _applies_to

    session_meta = ANALYSIS_META["session"]
    assert _applies_to(session_meta, "Daily") is False
    assert _applies_to(session_meta, "4H") is False
    assert _applies_to(session_meta, "1H") is True
    assert _applies_to(session_meta, "15min") is True

    # Non-session (applies_to is None) always applies.
    wick_distance_meta = ANALYSIS_META["wick_distance"]
    assert _applies_to(wick_distance_meta, "Daily") is True
    assert _applies_to(None, "Daily") is True


def test_import_cisd_analysis_still_works_with_trailing_default():
    # All existing 4-field constructor calls (19 pre-existing rows + 6
    # Plan-02 rows) must still be valid with applies_to's trailing default.
    import cisd_analysis  # noqa: F401


def test_new_analyses_registered_and_dispatch_generically():
    from cisd_barriers import ANALYSES, ANALYSIS_META
    from cisd_data import prepare
    from scripts.build_validation import build_manifest_rows

    keys = ["wick_distance", "sweep_depth", "fvg_size",
            "effort_result", "rvol", "volume_zscore"]
    for key in keys:
        assert key in ANALYSES
        assert key in ANALYSIS_META
        assert ANALYSIS_META[key].standalone is True
        assert ANALYSIS_META[key].filename

    rng = np.random.default_rng(3)
    n = 60
    opens, highs, lows, closes = [], [], [], []
    price = 100.0
    for i in range(n):
        step = 1.0 if i < 20 else rng.normal(0, 1.5)
        o = price
        c = price + step
        h = max(o, c) + abs(rng.normal(0, 0.5)) + 0.1
        l = min(o, c) - abs(rng.normal(0, 0.5)) - 0.1
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        price = c
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": np.linspace(500, 1500, n),
    }, index=idx)

    prepared = prepare(df)
    rows = build_manifest_rows(keys, prepared, prepared, "1H", "discovery")
    analyses_seen = {r["analysis"] for r in rows}
    assert set(keys) <= analyses_seen


# ── Phase 10 Plan 03, Task 3: build_validation.py TF-scoping ───────────────

def _tf_keys_for(tf_label):
    """Mirrors scripts/build_validation.py's tf_keys filter construction
    (both all_keys sites), used directly to avoid a full pipeline run."""
    from cisd_barriers import ANALYSES, ANALYSIS_META

    all_keys = list(ANALYSES.keys())
    return [k for k in all_keys
            if (ANALYSIS_META[k].applies_to is None) or (tf_label in ANALYSIS_META[k].applies_to)]


def _synthetic_prepared_frame(seed, n=60):
    from cisd_data import prepare

    rng = np.random.default_rng(seed)
    opens, highs, lows, closes = [], [], [], []
    price = 100.0
    for i in range(n):
        step = 1.0 if i < 20 else rng.normal(0, 1.5)
        o = price
        c = price + step
        h = max(o, c) + abs(rng.normal(0, 0.5)) + 0.1
        l = min(o, c) - abs(rng.normal(0, 0.5)) - 0.1
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        price = c
    idx = pd.date_range("2026-01-01", periods=n, freq="1h")
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": np.linspace(500, 1500, n),
    }, index=idx)
    return prepare(df)


def test_tf_scope_excludes_session_on_daily_and_4h():
    from scripts.build_validation import build_manifest_rows

    for tf_label in ("Daily", "4H"):
        prepared = _synthetic_prepared_frame(seed=11)
        rows = build_manifest_rows(_tf_keys_for(tf_label), prepared, prepared, tf_label, "discovery")
        assert not any(r["analysis"] == "session" for r in rows)


def test_session_manifest_rows_present_on_intraday_timeframes():
    from scripts.build_validation import build_manifest_rows

    for tf_label in ("1H", "15min"):
        prepared = _synthetic_prepared_frame(seed=13)
        rows = build_manifest_rows(_tf_keys_for(tf_label), prepared, prepared, tf_label, "discovery")
        assert any(r["analysis"] == "session" for r in rows)


def test_non_session_analyses_unaffected_across_all_timeframes():
    from scripts.build_validation import build_manifest_rows

    for tf_label in ("Daily", "4H", "1H", "15min"):
        prepared = _synthetic_prepared_frame(seed=17)
        rows = build_manifest_rows(_tf_keys_for(tf_label), prepared, prepared, tf_label, "discovery")
        analyses_seen = {r["analysis"] for r in rows}
        assert "wick_distance" in analyses_seen


def test_build_validation_imports_analysis_meta():
    from scripts.build_validation import build_manifest_rows  # noqa: F401
    from cisd_analysis import ANALYSIS_META  # noqa: F401
