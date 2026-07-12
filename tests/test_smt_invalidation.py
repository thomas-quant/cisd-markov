"""
tests/test_smt_invalidation.py — SMT invalidation-honesty + geometry tests
============================================================================
Held-out assertions for Phase 09 Plan 01 (`.planning/phases/09-smt-geometry-
invalidation-honesty/09-01-PLAN.md`): the widened `_annotate_swing_smt_from_
events` must (a) carry the scanner's lifecycle fields, (b) fix the already-
invalidated-at-`t` tagging bug (D-01/D-02/D-03/D-03a), and (c) compute the
`smt_block_size_atr` / `cisd_in_smt_block` geometry columns (D-04/D-05/D-05a)
and the `smt_broke_in_window` survived/broke horizon flag (D-06).

All fixtures are synthetic (df + events) — no SMT package required.
"""

import numpy as np
import pandas as pd
import pytest

from cisd_data import _annotate_swing_smt_from_events


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _make_df(index, cisd_types, opens=None, highs=None, lows=None, closes=None):
    n = len(index)
    if opens is None:
        opens = [100.0 + i for i in range(n)]
    if closes is None:
        closes = [o + 0.5 for o in opens]
    if highs is None:
        highs = [o + 1.0 for o in opens]
    if lows is None:
        lows = [o - 1.0 for o in opens]
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "cisd_type": cisd_types,
        },
        index=index,
    )


def _event(
    signal_type,
    created_ts,
    *,
    reference_timestamp=None,
    sweeping_asset="NQ",
    failing_asset="ES",
    reference_price=100.0,
    invalidation_asset="ES",
    invalidation_direction="above",
    invalidation_level=9999.0,
    broken_ts=pd.NaT,
    status="active",
):
    return {
        "signal_type": signal_type,
        "created_ts": created_ts,
        "reference_timestamp": created_ts if reference_timestamp is None else reference_timestamp,
        "sweeping_asset": sweeping_asset,
        "failing_asset": failing_asset,
        "reference_price": reference_price,
        "invalidation_asset": invalidation_asset,
        "invalidation_direction": invalidation_direction,
        "invalidation_level": invalidation_level,
        "broken_ts": broken_ts,
        "status": status,
    }


def _cisd_types(n, position, direction="bullish"):
    types = [None] * n
    types[position] = direction
    return types


# ── Task 1: validity semantics (D-01/D-02/D-03/D-03a) ──────────────────────

def test_broken_ts_equal_to_cisd_bar_yields_expired_smt():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[1], broken_ts=index[cisd_pos])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["has_swing_smt"]
    assert row["swing_smt_tag"] == "expired SMT"
    assert row["swing_smt_tag"] != "w/ SMT"


def test_broken_ts_nat_yields_w_smt():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[1], broken_ts=pd.NaT)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert result.iloc[cisd_pos]["swing_smt_tag"] == "w/ SMT"


def test_broken_ts_strictly_after_t_yields_w_smt():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[1], broken_ts=index[cisd_pos + 1])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert result.iloc[cisd_pos]["swing_smt_tag"] == "w/ SMT"


def test_event_created_at_t_is_always_w_smt():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos], broken_ts=index[cisd_pos + 1])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert result.iloc[cisd_pos]["swing_smt_tag"] == "w/ SMT"


def test_status_broken_far_future_does_not_disqualify():
    """D-02: validity never reads `status`, only broken_ts vs t."""
    index = pd.date_range("2026-01-01 09:30", periods=10, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [
            _event(
                "Bullish Swing SMT",
                created_ts=index[1],
                broken_ts=index[9],
                status="broken",
            )
        ]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert result.iloc[cisd_pos]["swing_smt_tag"] == "w/ SMT"


def test_expired_latest_match_not_rescued_by_earlier_valid_event():
    """D-03a: validity is checked only on the latest-created matched SMT."""
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [
            _event("Bullish Swing SMT", created_ts=index[1], broken_ts=pd.NaT),   # still valid, but not latest
            _event("Bullish Swing SMT", created_ts=index[2], broken_ts=index[cisd_pos]),  # latest, expired at t
        ]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]
    assert row["swing_smt_tag"] == "expired SMT"
    assert row["swing_smt_match_ts"] == index[2]
    assert row["smt_broken_ts"] == index[cisd_pos]


def test_no_same_direction_match_in_window_yields_no_smt():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos, direction="bullish"))
    events = pd.DataFrame(
        [_event("Bearish Swing SMT", created_ts=index[1], broken_ts=pd.NaT)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]
    assert not row["has_swing_smt"]
    assert row["swing_smt_tag"] == "no SMT"


@pytest.mark.parametrize(
    "broken_offset,expected_tag,expected_broke_in_window",
    [
        (1, "w/ SMT", True),        # t+1: within (t, t+2]
        (2, "w/ SMT", True),        # t+2: within (t, t+2]
        (3, "w/ SMT", False),       # t+3: beyond horizon
        (None, "w/ SMT", False),    # NaT: never breaks
        (0, "expired SMT", False),  # t: expired, not w/ SMT, never "broke in window"
    ],
)
def test_smt_broke_in_window_flag(broken_offset, expected_tag, expected_broke_in_window):
    index = pd.date_range("2026-01-01 09:30", periods=10, freq="15min")
    cisd_pos = 4
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    broken_ts = pd.NaT if broken_offset is None else index[cisd_pos + broken_offset]
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], broken_ts=broken_ts)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]
    assert row["swing_smt_tag"] == expected_tag
    assert bool(row["smt_broke_in_window"]) == expected_broke_in_window


def test_lifecycle_fields_populated_at_matched_rows():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [
            _event(
                "Bullish Swing SMT",
                created_ts=index[1],
                reference_timestamp=index[0],
                sweeping_asset="NQ",
                failing_asset="ES",
                reference_price=123.25,
                invalidation_asset="ES",
                invalidation_direction="below",
                invalidation_level=456.5,
                broken_ts=pd.NaT,
                status="active",
            )
        ]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["swing_smt_tag"] == "w/ SMT"
    assert row["smt_reference_price"] == pytest.approx(123.25)
    assert row["smt_invalidation_level"] == pytest.approx(456.5)
    assert pd.isna(row["smt_broken_ts"])
    assert row["smt_status"] == "active"
    assert row["smt_reference_timestamp"] == index[0]
    assert row["smt_invalidation_asset"] == "ES"
    assert row["smt_invalidation_direction"] == "below"


def test_lifecycle_fields_default_at_no_smt_rows():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos, direction="bullish"))
    events = pd.DataFrame(
        [_event("Bearish Swing SMT", created_ts=index[1], broken_ts=pd.NaT)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["swing_smt_tag"] == "no SMT"
    assert pd.isna(row["smt_reference_price"])
    assert pd.isna(row["smt_invalidation_level"])
    assert pd.isna(row["smt_broken_ts"])
    assert row["smt_status"] == "none"
    assert pd.isna(row["smt_reference_timestamp"])
    assert row["smt_invalidation_asset"] == "none"
    assert row["smt_invalidation_direction"] == "none"


# ── Task 2: geometry columns (D-04/D-05/D-05a) ──────────────────────────────

def _make_geometry_df(n, cisd_pos, ref_pos, cisd_open, cisd_close, ref_high=106.0, ref_low=100.0):
    index = pd.date_range("2026-01-01 09:30", periods=n, freq="15min")
    opens = [100.0 + i * 0.1 for i in range(n)]
    highs = [o + 2.0 for o in opens]
    lows = [o - 2.0 for o in opens]
    closes = [o + 0.5 for o in opens]

    highs[ref_pos] = ref_high
    lows[ref_pos] = ref_low

    opens[cisd_pos] = cisd_open
    closes[cisd_pos] = cisd_close

    cisd_types = [None] * n
    cisd_types[cisd_pos] = "bullish"

    df = _make_df(index, cisd_types, opens=opens, highs=highs, lows=lows, closes=closes)
    return index, df


def test_smt_block_size_atr_matches_reference_bar_range_over_atr():
    n, cisd_pos, ref_pos = 20, 15, 10
    index, df = _make_geometry_df(n, cisd_pos, ref_pos, cisd_open=101.0, cisd_close=105.0)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], reference_timestamp=index[ref_pos])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    atr_series = (df["high"] - df["low"]).rolling(14).mean()
    atr_t = atr_series.iloc[cisd_pos]
    expected = (df["high"].iloc[ref_pos] - df["low"].iloc[ref_pos]) / atr_t

    assert atr_t > 0
    assert row["smt_block_size_atr"] == pytest.approx(expected)


def test_cisd_in_smt_block_true_when_body_fully_contained():
    n, cisd_pos, ref_pos = 20, 15, 10
    # ref block is [100, 106]; body [101, 105] is fully inside.
    index, df = _make_geometry_df(n, cisd_pos, ref_pos, cisd_open=101.0, cisd_close=105.0)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], reference_timestamp=index[ref_pos])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert bool(result.iloc[cisd_pos]["cisd_in_smt_block"]) is True


def test_cisd_in_smt_block_false_when_body_partially_outside():
    n, cisd_pos, ref_pos = 20, 15, 10
    # ref block is [100, 106]; open (99) falls outside.
    index, df = _make_geometry_df(n, cisd_pos, ref_pos, cisd_open=99.0, cisd_close=105.0)
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], reference_timestamp=index[ref_pos])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    assert bool(result.iloc[cisd_pos]["cisd_in_smt_block"]) is False


def test_geometry_columns_default_for_no_smt_rows():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    cisd_pos = 3
    df = _make_df(index, _cisd_types(len(index), cisd_pos, direction="bullish"))
    events = pd.DataFrame(
        [_event("Bearish Swing SMT", created_ts=index[1], broken_ts=pd.NaT)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["swing_smt_tag"] == "no SMT"
    assert pd.isna(row["smt_block_size_atr"])
    assert bool(row["cisd_in_smt_block"]) is False


def test_geometry_columns_set_for_expired_smt_rows_too():
    """D-05a: geometry is written for the matched population (w/ SMT AND expired SMT)."""
    n, cisd_pos, ref_pos = 20, 15, 10
    index, df = _make_geometry_df(n, cisd_pos, ref_pos, cisd_open=101.0, cisd_close=105.0)
    events = pd.DataFrame(
        [
            _event(
                "Bullish Swing SMT",
                created_ts=index[cisd_pos - 1],
                reference_timestamp=index[ref_pos],
                broken_ts=index[cisd_pos],  # expired exactly at t
            )
        ]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["swing_smt_tag"] == "expired SMT"
    assert not pd.isna(row["smt_block_size_atr"])
    assert bool(row["cisd_in_smt_block"]) is True


def test_smt_block_size_atr_nan_when_atr_not_yet_available():
    index = pd.date_range("2026-01-01 09:30", periods=8, freq="15min")
    cisd_pos = 5  # fewer than 14 bars have elapsed -> ATR(14) is NaN here
    df = _make_df(index, _cisd_types(len(index), cisd_pos))
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], reference_timestamp=index[0])]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    atr_t = (df["high"] - df["low"]).rolling(14).mean().iloc[cisd_pos]
    assert pd.isna(atr_t)
    assert pd.isna(row["smt_block_size_atr"])


def test_smt_block_size_atr_nan_and_containment_false_on_reindex_miss():
    """Graceful degradation: reference_timestamp not present in the annotated frame's index."""
    n, cisd_pos, ref_pos = 20, 15, 10
    index, df = _make_geometry_df(n, cisd_pos, ref_pos, cisd_open=101.0, cisd_close=105.0)
    missing_ts = pd.Timestamp("2099-01-01 00:00")
    assert missing_ts not in df.index
    events = pd.DataFrame(
        [_event("Bullish Swing SMT", created_ts=index[cisd_pos - 1], reference_timestamp=missing_ts)]
    )

    result = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    row = result.iloc[cisd_pos]

    assert row["swing_smt_tag"] == "w/ SMT"
    assert pd.isna(row["smt_block_size_atr"])
    assert bool(row["cisd_in_smt_block"]) is False
