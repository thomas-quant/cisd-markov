import numpy as np
import pandas as pd
import pytest

from scripts import build_expectancy as ex


def _frame(rows: list[dict]) -> pd.DataFrame:
    index = pd.date_range("2026-02-01 09:30", periods=len(rows), freq="15min")
    df = pd.DataFrame(rows, index=index)
    for col, default in ex.CASE_FLAG_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
    return df


def _bar(close, high, low, cisd_type=None, **flags):
    return {"open": close, "close": close, "high": high, "low": low, "cisd_type": cisd_type, **flags}


def test_bullish_never_stopped_marks_to_close_in_r_units():
    # entry close=100, invalidation(low)=98 -> risk=2. Lows stay above 98.
    rows = [_bar(100, 101, 98, "bullish")]
    for c in (101, 102, 103, 104, 105, 106, 107):
        rows.append(_bar(c, c + 1, 100))  # low=100 > 98, never stops
    events = ex.build_event_r_multiples(_frame(rows), "NQ")

    assert len(events) == 1
    row = events.iloc[0]
    assert row["risk"] == pytest.approx(2.0)
    assert row["stop_bar"] == 0
    expected = [(c - 100) / 2 for c in (101, 102, 103, 104, 105, 106, 107)]
    assert [row[f"r_{h}"] for h in ex.HORIZONS] == pytest.approx(expected)


def test_bullish_stop_locks_minus_one_r_from_stop_bar_onward():
    # Stop on bar 2 (low 97 <= invalidation 98); bar 1 marks to close first.
    rows = [_bar(100, 101, 98, "bullish")]
    rows.append(_bar(101, 102, 99))   # bar 1: not stopped -> r_1 = (101-100)/2 = 0.5
    rows.append(_bar(99, 100, 97))    # bar 2: low 97 <= 98 -> stop
    for c in (98, 99, 100, 101, 102):
        rows.append(_bar(c, c + 1, c - 1))
    events = ex.build_event_r_multiples(_frame(rows), "NQ")

    row = events.iloc[0]
    assert row["stop_bar"] == 2
    assert row["r_1"] == pytest.approx(0.5)
    assert [row[f"r_{h}"] for h in range(2, ex.HORIZON + 1)] == pytest.approx([-1.0] * 6)


def test_bearish_risk_uses_high_and_returns_are_sign_flipped():
    # entry close=100, invalidation(high)=102 -> risk=2. Highs stay below 102.
    rows = [_bar(100, 102, 99, "bearish")]
    for c in (99, 98, 97, 96, 95, 94, 93):
        rows.append(_bar(c, 101, c - 1))  # high=101 < 102, never stops
    events = ex.build_event_r_multiples(_frame(rows), "ES")

    row = events.iloc[0]
    assert row["risk"] == pytest.approx(2.0)
    assert row["stop_bar"] == 0
    expected = [(100 - c) / 2 for c in (99, 98, 97, 96, 95, 94, 93)]
    assert [row[f"r_{h}"] for h in ex.HORIZONS] == pytest.approx(expected)


def test_zero_risk_event_is_excluded():
    rows = [_bar(100, 101, 100, "bullish")]  # close == low -> risk 0
    for c in (101, 102, 103, 104, 105, 106, 107):
        rows.append(_bar(c, c + 1, 100))
    events = ex.build_event_r_multiples(_frame(rows), "NQ")
    assert events.empty


def test_incomplete_forward_window_is_excluded():
    # Event with fewer than HORIZON bars after it is dropped.
    rows = [_bar(100, 101, 98, "bullish")] + [_bar(101, 102, 100) for _ in range(ex.HORIZON - 1)]
    events = ex.build_event_r_multiples(_frame(rows), "NQ")
    assert events.empty


def test_case_masks_partition_fvg_buckets():
    events = pd.DataFrame(
        {
            "cisd_type": ["bullish", "bearish", "bullish"],
            "has_dir_fvg_mid0": [True, False, False],
            "has_dir_fvg_mid1": [False, True, False],
            "has_dir_sweep": [True, False, False],
            "prev_bar_is_dir_swing": [False, False, False],
            "cisd_bar_is_dir_swing": [False, False, False],
            "swing_smt_tag": ["w/ SMT", "no SMT", "no SMT"],
        }
    )
    masks = ex.case_masks(events)
    assert masks["fvg_mid0"].tolist() == [True, False, False]
    assert masks["fvg_mid1"].tolist() == [False, True, False]
    assert masks["fvg_any"].tolist() == [True, True, False]
    assert masks["fvg_none"].tolist() == [False, False, True]
    assert masks["sweep"].tolist() == [True, False, False]
    assert masks["smt"].tolist() == [True, False, False]
    assert masks["all_cisd"].tolist() == [True, True, True]


def test_summarize_horizon_expectancy_and_rates():
    events = pd.DataFrame(
        {
            "stop_bar": [0, 3, 0, 0],
            "r_7": [2.0, -1.0, 0.5, -0.5],
        }
    )
    stats = ex.summarize_horizon(events, 7)
    assert stats["n"] == 4
    assert stats["mean_r"] == pytest.approx((2.0 - 1.0 + 0.5 - 0.5) / 4)
    assert stats["win_rate"] == pytest.approx(50.0)   # 2.0 and 0.5 are > 0
    assert stats["stop_rate"] == pytest.approx(25.0)  # one stop_bar within 1..7


def test_summarize_horizon_stop_rate_respects_horizon_window():
    events = pd.DataFrame({"stop_bar": [3, 5], "r_2": [-1.0, 0.4]})
    # Neither stop happened by horizon 2.
    assert ex.summarize_horizon(events, 2)["stop_rate"] == pytest.approx(0.0)
