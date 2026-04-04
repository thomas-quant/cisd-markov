import pytest
import pandas as pd

from scripts import build_forward_returns as fr


def test_combo_key_builders_use_family_specific_dimensions():
    assert fr.core_combo_key(
        {"smt": "w/ SMT", "size_cross": "Big CISD / Small prev", "wick": "past_wick", "consec": "2"}
    ) == "w/ SMT|Big CISD / Small prev|past_wick|2"
    assert fr.fvg_combo_key(
        {"fvg_bucket": "mid1", "fvg_mode": "close_through_near_edge", "fvg_state": "failed"}
    ) == "mid1|close_through_near_edge|failed"
    assert fr.structure_combo_key(
        {"sweep": "w/ sweep", "prev_swing": "yes", "cisd_swing": "no"}
    ) == "w/ sweep|yes|no"


def test_percentile_payload_returns_none_for_empty_series():
    assert fr.percentile_payload(pd.Series(dtype=float)) is None


def test_percentile_payload_returns_expected_bands():
    series = pd.Series([1.0, 2.0, 3.0, 4.0])

    payload = fr.percentile_payload(series)

    assert payload["25"] == pytest.approx(1.75)
    assert payload["50"] == pytest.approx(2.5)
    assert payload["75"] == pytest.approx(3.25)
    assert payload["5"] == pytest.approx(1.15)
    assert payload["95"] == pytest.approx(3.85)


def _prepared_fixture() -> pd.DataFrame:
    index = pd.date_range("2026-02-01 09:30", periods=12, freq="15min")
    return pd.DataFrame(
        {
            "open": [99, 100, 102, 106, 105, 104, 107, 108, 109, 110, 111, 112],
            "close": [100, 101, 103, 104, 106, 105, 108, 109, 110, 111, 112, 113],
            "high": [101, 102, 104, 105, 107, 106, 109, 110, 111, 112, 113, 114],
            "low": [99, 100, 102, 103, 104, 104, 107, 108, 109, 110, 111, 112],
            "cisd_type": [None, "bullish", None, "bearish", None, "bullish", None, None, None, None, None, None],
            "swing_smt_tag": [
                "no SMT",
                "w/ SMT",
                "no SMT",
                "no SMT",
                "no SMT",
                "w/ SMT",
                "no SMT",
                "no SMT",
                "no SMT",
                "no SMT",
                "no SMT",
                "no SMT",
            ],
            "direction": [
                None,
                "bullish",
                "bullish",
                "bearish",
                "bullish",
                "bearish",
                "bullish",
                "bullish",
                "bullish",
                "bullish",
                "bullish",
                "bullish",
            ],
            "prev_direction": [
                None,
                "bearish",
                "bullish",
                "bullish",
                "bearish",
                "bullish",
                "bearish",
                "bullish",
                "bullish",
                "bullish",
                "bullish",
                "bullish",
            ],
            "prev_close": [None, 100, 101, 103, 104, 106, 105, 108, 109, 110, 111, 112],
            "prev_high": [None, 101, 102, 104, 105, 107, 106, 109, 110, 111, 112, 113],
            "prev_low": [None, 99, 100, 102, 103, 104, 104, 107, 108, 109, 110, 111],
            "has_dir_fvg_mid0": [False, True, False, False, False, False, False, False, False, False, False, False],
            "has_dir_fvg_mid1": [False, False, False, True, False, False, False, False, False, False, False, False],
            "fvg_mid0_hold_close_near": ["none", "held", "none", "none", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid0_hold_wick_far": ["none", "held", "none", "none", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid1_hold_close_near": ["none", "none", "none", "failed", "none", "none", "none", "none", "none", "none", "none", "none"],
            "fvg_mid1_hold_wick_far": ["none", "none", "none", "failed", "none", "none", "none", "none", "none", "none", "none", "none"],
            "has_dir_sweep": [False, True, False, False, False, False, False, False, False, False, False, False],
            "prev_bar_is_dir_swing": [False, True, False, False, False, False, False, False, False, False, False, False],
            "cisd_bar_is_dir_swing": [False, False, False, True, False, False, False, False, False, False, False, False],
        },
        index=index,
    )


def test_build_forward_return_rows_adds_normalized_returns_and_core_tags():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    assert set(["instrument", "cisd_type", "forward_return_pct", "smt", "size_cross", "wick", "consec"]) <= set(rows.columns)
    assert rows.loc[rows.index[0], "instrument"] == "NQ"
    assert rows.loc[rows.index[0], "forward_return_pct"] > 0
    assert rows.loc[rows.index[1], "forward_return_pct"] < 0


def test_apply_fvg_filters_respects_bucket_mode_and_state():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "fvg",
        {
            "fvg_bucket": "mid0",
            "fvg_mode": "close_through_near_edge",
            "fvg_state": "held",
        },
    )

    assert filtered["fvg_bucket"].unique().tolist() == ["mid0"]
    assert filtered["fvg_state_close_through_near_edge"].unique().tolist() == ["held"]


def test_apply_fvg_filters_does_not_filter_state_when_mode_is_all():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "fvg",
        {
            "fvg_bucket": "all",
            "fvg_mode": "all",
            "fvg_state": "held",
        },
    )

    assert len(filtered) == len(rows)


def test_apply_structure_filters_respects_sweep_and_swing_flags():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "structure",
        {"sweep": "w/ sweep", "prev_swing": "yes", "cisd_swing": "no"},
    )

    assert len(filtered) == 1


def test_apply_core_filters_respects_core_tags():
    rows = fr.build_forward_return_rows(_prepared_fixture(), "NQ")

    filtered = fr.apply_family_filters(
        rows,
        "core",
        {"smt": "w/ SMT", "size_cross": "all", "wick": "all", "consec": "all"},
    )

    assert filtered["smt"].unique().tolist() == ["w/ SMT"]
