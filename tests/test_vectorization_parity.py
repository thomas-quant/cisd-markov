"""Fast synthetic per-function parity locks for the two Phase 08 hot functions.

This module pins the trickier per-column semantics of `_annotate_cisd_research`
and `_annotate_swing_smt_from_events` on small, hand-constructed DataFrames —
NO real parquet data and NO SMT package required, so it runs in every suite
invocation (unlike `tests/test_perf_characterization.py`, which is the heavy,
opt-in, real-data bit-equality gate).

Expected values below were derived by running the CURRENT (pre-vectorization)
functions once during authoring and hard-coding the observed outputs — this is
the legitimate "behavior-lock" pattern used throughout this test suite (see
`tests/test_characterization.py`'s module docstring for the same convention
applied to real-data numbers). If a future vectorized rewrite changes any of
these values, that is a regression this test is designed to catch.

Both hot functions are imported via `cisd_analysis` (not `cisd_data` directly)
to preserve the public import surface other tests in this repo rely on.
"""
from __future__ import annotations

import pandas as pd
import pytest

from cisd_analysis import _annotate_cisd_research, _annotate_swing_smt_from_events


# ── Shared fixture helpers for the SMT lifecycle columns (Phase 09 Plan 01) ─

_EVENT_LIFECYCLE_DEFAULTS = {
    "reference_price": 100.0,
    "invalidation_asset": "ES",
    "invalidation_direction": "above",
    "invalidation_level": 9999.0,
    "broken_ts": pd.NaT,
    "status": "active",
}


def _event(signal_type, created_ts, sweeping_asset, failing_asset, reference_timestamp=None, **overrides):
    row = {
        "signal_type": signal_type,
        "created_ts": created_ts,
        "sweeping_asset": sweeping_asset,
        "failing_asset": failing_asset,
        "reference_timestamp": created_ts if reference_timestamp is None else reference_timestamp,
    }
    row.update(_EVENT_LIFECYCLE_DEFAULTS)
    row.update(overrides)
    return row


def _ohlc_df(cisd_types, index):
    n = len(index)
    opens = [10.0 + i for i in range(n)]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [o + 1.0 for o in opens],
            "low": [o - 1.0 for o in opens],
            "close": [o + 0.5 for o in opens],
            "cisd_type": cisd_types,
        },
        index=index,
    )


_EMPTY_EVENT_COLUMNS = [
    "signal_type", "created_ts", "sweeping_asset", "failing_asset",
    "reference_price", "invalidation_asset", "invalidation_direction",
    "invalidation_level", "broken_ts", "status", "reference_timestamp",
]


# ══════════════════════════════════════════════════════════════════════════
# _annotate_swing_smt_from_events
# ══════════════════════════════════════════════════════════════════════════

def test_swing_smt_last_matching_event_in_window_wins():
    """When TWO same-direction events both fall inside a CISD bar's [t-2, t]
    window, the LATEST created_ts wins — its match_ts and role are written,
    even though the earlier event was iterated first (event_rows are sorted
    ascending by created_ts, and each subsequent match overwrites the prior
    best_event). This is the load-bearing "last matching event overwrites"
    semantic a vectorized rewrite must preserve.
    """
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = _ohlc_df([None, "bullish", "bullish", "bullish", "bearish", None], index)
    events = pd.DataFrame(
        [
            _event("Bullish Swing SMT", index[1], "NQ", "ES"),
            _event("Bullish Swing SMT", index[2], "ES", "NQ"),
        ]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = nq.loc[index[3]]

    assert bool(row["has_swing_smt"]) is True
    assert row["swing_smt_tag"] == "w/ SMT"
    assert row["swing_smt_match_ts"] == index[2]  # later event (idx[2]) wins over idx[1]
    assert row["swing_smt_role"] == "failed_to_sweep"  # NQ is failing_asset on the WINNING event


def test_swing_smt_opposite_direction_event_ignored():
    """An event whose direction does not match the CISD bar's cisd_type is
    never a candidate, regardless of timestamp proximity."""
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = _ohlc_df([None, "bullish", "bullish", "bullish", "bearish", None], index)
    events = pd.DataFrame(
        [_event("Bearish Swing SMT", index[2], "NQ", "ES")]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = nq.loc[index[3]]  # bullish CISD bar

    assert bool(row["has_swing_smt"]) is False
    assert row["swing_smt_tag"] == "no SMT"
    assert row["swing_smt_match_ts"] is pd.NaT
    assert row["swing_smt_role"] == "none"


def test_swing_smt_event_outside_left_window_does_not_match():
    """An event created at t-3 (outside the [t-2, t] left window) must NOT
    match, even when same-direction."""
    index = pd.date_range("2026-01-01 09:30", periods=5, freq="15min")
    df = _ohlc_df([None, None, None, "bullish", None], index)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", index[0], "NQ", "ES")]  # t-3 relative to idx[3]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = nq.loc[index[3]]

    assert bool(row["has_swing_smt"]) is False
    assert row["swing_smt_tag"] == "no SMT"
    assert row["swing_smt_match_ts"] is pd.NaT
    assert row["swing_smt_role"] == "none"


def test_swing_smt_role_resolves_to_none_when_instrument_is_neither_asset():
    """swing_smt_role resolves to "none" when the instrument matches neither
    the sweeping_asset nor the failing_asset of the matching event, even
    though has_swing_smt/swing_smt_tag still register the match."""
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = _ohlc_df([None, "bullish", "bullish", "bullish", "bearish", None], index)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", index[1], "ES", "GC")]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = nq.loc[index[1]]

    assert bool(row["has_swing_smt"]) is True
    assert row["swing_smt_tag"] == "w/ SMT"
    assert row["swing_smt_role"] == "none"


def test_swing_smt_role_swept_vs_failed_to_sweep():
    """swing_smt_role is 'swept' when instrument == sweeping_asset and
    'failed_to_sweep' when instrument == failing_asset, for the SAME event."""
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = _ohlc_df([None, "bullish", "bullish", "bullish", "bearish", None], index)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", index[1], "NQ", "ES")]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    es = _annotate_swing_smt_from_events(df, events, instrument="ES")

    assert nq.loc[index[1], "swing_smt_role"] == "swept"
    assert es.loc[index[1], "swing_smt_role"] == "failed_to_sweep"


def test_swing_smt_empty_events_returns_all_default_columns():
    """An empty events frame returns the all-default columns for every row:
    has_swing_smt=False, swing_smt_tag='no SMT', match_ts=NaT, role='none'."""
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = _ohlc_df([None, "bullish", "bullish", "bullish", "bearish", None], index)
    empty_events = pd.DataFrame(columns=_EMPTY_EVENT_COLUMNS)

    nq = _annotate_swing_smt_from_events(df, empty_events, instrument="NQ")

    assert (~nq["has_swing_smt"]).all()
    assert (nq["swing_smt_tag"] == "no SMT").all()
    assert nq["swing_smt_match_ts"].isna().all()
    assert (nq["swing_smt_role"] == "none").all()


def test_swing_smt_empty_frame_returns_empty_with_default_columns():
    """An empty df (0 rows) returns an empty frame that still carries the
    four default-value columns (no KeyError / IndexError on empty input)."""
    empty_df = pd.DataFrame({"cisd_type": []})
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", pd.Timestamp("2026-01-01"), "NQ", "ES")]
    )

    nq = _annotate_swing_smt_from_events(empty_df, events, instrument="NQ")

    assert len(nq) == 0
    expected_cols = {"has_swing_smt", "swing_smt_tag", "swing_smt_match_ts", "swing_smt_role"}
    assert expected_cols <= set(nq.columns)


# ══════════════════════════════════════════════════════════════════════════
# _annotate_cisd_research
# ══════════════════════════════════════════════════════════════════════════

def _make_candle_df(n, cisd_idx, ct, c0, c1=None, c2=None):
    """Build a minimal OHLC + cisd_type frame with one CISD event at cisd_idx,
    with optional explicit (open, high, low, close) tuples for the CISD bar
    (c0) and the following two bars (c1, c2)."""
    index = pd.date_range("2026-01-01", periods=n, freq="1h")
    open_ = [10.0] * n
    high = [11.0] * n
    low = [9.0] * n
    close = [10.0] * n
    cisd_type = [None] * n
    cisd_type[cisd_idx] = ct
    open_[cisd_idx], high[cisd_idx], low[cisd_idx], close[cisd_idx] = c0
    if c1 is not None:
        open_[cisd_idx + 1], high[cisd_idx + 1], low[cisd_idx + 1], close[cisd_idx + 1] = c1
    if c2 is not None:
        open_[cisd_idx + 2], high[cisd_idx + 2], low[cisd_idx + 2], close[cisd_idx + 2] = c2
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    ), index


def test_has_dir_sweep_true_when_prior_swing_low_exceeded_in_window():
    """has_dir_sweep is True when a prior 3-bar swing low is exceeded by a
    later bar's low inside the [t-4, t] sweep window (SWEEP_TOLERANCE=5),
    within SWEEP_SWING_LOOKBACK=20 bars of history."""
    index = pd.date_range("2026-01-01", periods=10, freq="1h")
    n = len(index)
    open_ = [10] * n
    high = [12] * n
    low = [8] * n
    close = [10] * n
    low[1], high[1] = 10, 12
    low[2], high[2] = 5, 8    # swing low candidate (low[1]=10 > 5 < low[3]=10)
    low[3], high[3] = 10, 12
    low[5], high[5] = 3, 6   # sweeps below swing low of 5, inside [idx-4, idx]=[3,7]
    cisd_type = [None] * n
    cisd_type[7] = "bullish"
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    )

    out = _annotate_cisd_research(df)

    assert bool(out.loc[index[7], "has_dir_sweep"]) is True


def test_has_dir_sweep_false_when_no_swing_exceeded_in_window():
    """has_dir_sweep is False when no prior swing low/high is exceeded
    anywhere in the [t-4, t] window."""
    index = pd.date_range("2026-01-01", periods=10, freq="1h")
    n = len(index)
    open_ = [10] * n
    high = [12] * n
    low = [8] * n
    close = [10] * n
    cisd_type = [None] * n
    cisd_type[8] = "bullish"
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    )

    out = _annotate_cisd_research(df)

    assert bool(out.loc[index[8], "has_dir_sweep"]) is False


def test_fvg_mid1_hold_held_when_future_window_never_violates():
    """has_dir_fvg_mid1 detects a FVG on the bar AFTER the CISD bar, and both
    close_near/wick_far hold classifications resolve to "held" when neither
    is violated across the FVG_HOLD_LOOKAHEAD=10 window."""
    n = 16
    index = pd.date_range("2026-01-01", periods=n, freq="1h")
    open_ = [10.0] * n
    high = [11.0] * n
    low = [9.0] * n
    close = [10.0] * n
    cisd_idx = 3
    high[cisd_idx] = 10.0  # left bar of the mid1 FVG (== CISD bar)
    low[5] = 20.0  # right bar of the mid1 FVG: right.low(20) > left.high(10)
    cisd_type = [None] * n
    cisd_type[cisd_idx] = "bullish"
    for i in range(5, 15):
        open_[i], high[i], low[i], close[i] = 14.0, 16.0, 12.0, 15.0
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    )

    out = _annotate_cisd_research(df)
    row = out.loc[index[cisd_idx]]

    assert bool(row["has_dir_fvg_mid1"]) is True
    assert row["fvg_mid1_hold_close_near"] == "held"
    assert row["fvg_mid1_hold_wick_far"] == "held"


def test_fvg_mid1_hold_failed_when_future_window_violates():
    """Both close_near and wick_far resolve to "failed" when the future
    window dips back through the left bar's high/low respectively."""
    n = 16
    index = pd.date_range("2026-01-01", periods=n, freq="1h")
    open_ = [10.0] * n
    high = [11.0] * n
    low = [9.0] * n
    close = [10.0] * n
    cisd_idx = 3
    high[cisd_idx] = 10.0
    low[5] = 20.0
    cisd_type = [None] * n
    cisd_type[cisd_idx] = "bullish"
    for i in range(5, 15):
        open_[i], high[i], low[i], close[i] = 14.0, 16.0, 12.0, 15.0
    close[8] = 5.0   # violates close_near (close < left.high=10)
    low[9] = 2.0     # violates wick_far (low < left.low=9)
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    )

    out = _annotate_cisd_research(df)
    row = out.loc[index[cisd_idx]]

    assert bool(row["has_dir_fvg_mid1"]) is True
    assert row["fvg_mid1_hold_close_near"] == "failed"
    assert row["fvg_mid1_hold_wick_far"] == "failed"


def test_fvg_mid1_hold_none_when_lookahead_window_does_not_fit():
    """fvg_mid1_hold_* classifications default to "none" when the frame is
    too short for the full FVG_HOLD_LOOKAHEAD=10 window to fit, even though
    has_dir_fvg_mid1 itself is still True."""
    n = 6  # too short: mid1_idx(4) + FVG_HOLD_LOOKAHEAD(10) = 14 >= len(df)=6
    index = pd.date_range("2026-01-01", periods=n, freq="1h")
    open_ = [10.0] * n
    high = [11.0] * n
    low = [9.0] * n
    close = [10.0] * n
    cisd_idx = 3
    high[cisd_idx] = 10.0
    low[5] = 20.0
    cisd_type = [None] * n
    cisd_type[cisd_idx] = "bullish"
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "cisd_type": cisd_type},
        index=index,
    )

    out = _annotate_cisd_research(df)
    row = out.loc[index[cisd_idx]]

    assert bool(row["has_dir_fvg_mid1"]) is True
    assert row["fvg_mid1_hold_close_near"] == "none"
    assert row["fvg_mid1_hold_wick_far"] == "none"


def test_candle1_bullish_with_and_past_wick():
    """Bullish CISD: candle[1] closing above candle[0]'s close is "with"; if
    it also closes above candle[0]'s high, candle1_past_candle0_wick=True and
    candle1_failed_followthrough=False."""
    df, index = _make_candle_df(6, 1, "bullish", c0=(9, 12, 8, 10), c1=(13, 14, 12, 13))
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle1_close_dir"] == "with"
    assert bool(row["candle1_past_candle0_wick"]) is True
    assert bool(row["candle1_failed_followthrough"]) is False


def test_candle1_bullish_with_but_not_past_wick_marks_failed_followthrough():
    """Bullish CISD: candle[1] closes above candle[0]'s close ("with") but
    not above candle[0]'s high -> past_candle0_wick=False and
    candle1_failed_followthrough=True."""
    df, index = _make_candle_df(6, 1, "bullish", c0=(9, 12, 8, 10), c1=(10.5, 11, 10, 10.5))
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle1_close_dir"] == "with"
    assert bool(row["candle1_past_candle0_wick"]) is False
    assert bool(row["candle1_failed_followthrough"]) is True


def test_candle1_bullish_against():
    """Bullish CISD: candle[1] closing below candle[0]'s close is "against"."""
    df, index = _make_candle_df(6, 1, "bullish", c0=(9, 12, 8, 10), c1=(9, 10, 8, 9))
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle1_close_dir"] == "against"
    assert bool(row["candle1_past_candle0_wick"]) is False


def test_candle1_bearish_with_and_past_wick():
    """Bearish CISD: candle[1] closing below candle[0]'s close is "with"; if
    it also closes below candle[0]'s low, candle1_past_candle0_wick=True."""
    df, index = _make_candle_df(6, 1, "bearish", c0=(11, 12, 8, 10), c1=(7, 7.5, 6, 7))
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle1_close_dir"] == "with"
    assert bool(row["candle1_past_candle0_wick"]) is True
    assert bool(row["candle1_failed_followthrough"]) is False


def test_candle1_bearish_with_but_not_past_wick():
    """Bearish CISD: candle[1] closes below candle[0]'s close ("with") but
    not below candle[0]'s low -> past_candle0_wick=False,
    candle1_failed_followthrough=True."""
    df, index = _make_candle_df(6, 1, "bearish", c0=(11, 12, 8, 10), c1=(9.5, 10, 9, 9.5))
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle1_close_dir"] == "with"
    assert bool(row["candle1_past_candle0_wick"]) is False
    assert bool(row["candle1_failed_followthrough"]) is True


@pytest.mark.parametrize(
    "ct, c0, c1, c2, expected_gap_dir, expected_past_wick",
    [
        # Bullish: gap = c2.open - c1.close
        ("bullish", (9, 12, 8, 10), (13, 14, 12, 13), (15, 16, 14, 15), "gap_with", True),
        ("bullish", (9, 12, 8, 10), (13, 14, 12, 13), (11, 15, 10, 15), "gap_against", True),
        ("bullish", (9, 12, 8, 10), (13, 14, 12, 13), (13, 15, 10, 15), "flat", True),
        ("bullish", (9, 12, 8, 10), (13, 14, 12, 13), (13, 14, 9, 13.5), "flat", False),
        # Bearish: sign convention flips (gap = c2.open - c1.close, negative == "gap_with")
        ("bearish", (11, 12, 8, 10), (7, 7.5, 6, 7), (5, 6, 4, 5), "gap_with", True),
    ],
)
def test_candle2_gap_dir_mapping_and_past_candle1_wick(ct, c0, c1, c2, expected_gap_dir, expected_past_wick):
    df, index = _make_candle_df(6, 1, ct, c0=c0, c1=c1, c2=c2)
    out = _annotate_cisd_research(df)
    row = out.loc[index[1]]

    assert row["candle2_gap_dir"] == expected_gap_dir
    assert bool(row["candle2_past_candle1_wick"]) is expected_past_wick


def test_candle_columns_default_when_idx_plus_1_out_of_range():
    """When the CISD bar is the LAST bar in the frame (idx+1 out of range),
    all candle[1]/candle[2] columns retain their defaults:
    candle1_close_dir="against", candle1_past_candle0_wick=False,
    candle1_failed_followthrough=False, candle2_gap_dir="flat",
    candle2_past_candle1_wick=False."""
    df, index = _make_candle_df(3, 2, "bullish", c0=(9, 12, 8, 10))
    out = _annotate_cisd_research(df)
    row = out.loc[index[2]]

    assert row["candle1_close_dir"] == "against"
    assert bool(row["candle1_past_candle0_wick"]) is False
    assert bool(row["candle1_failed_followthrough"]) is False
    assert row["candle2_gap_dir"] == "flat"
    assert bool(row["candle2_past_candle1_wick"]) is False


def test_candle2_columns_default_when_idx_plus_2_out_of_range():
    """When candle[1] exists but candle[2] is out of range, candle1_* columns
    are populated normally while candle2_gap_dir stays "flat" and
    candle2_past_candle1_wick stays False."""
    df, index = _make_candle_df(4, 2, "bullish", c0=(9, 12, 8, 10), c1=(13, 14, 12, 13))
    out = _annotate_cisd_research(df)
    row = out.loc[index[2]]

    assert row["candle1_close_dir"] == "with"
    assert bool(row["candle1_past_candle0_wick"]) is True
    assert row["candle2_gap_dir"] == "flat"
    assert bool(row["candle2_past_candle1_wick"]) is False
