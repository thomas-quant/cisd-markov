import pandas as pd
import pytest

import cisd_analysis


def _research_frame_for_fvg():
    index = pd.date_range("2026-01-01 09:30", periods=16, freq="15min")
    return pd.DataFrame(
        {
            "open": [
                9.2,
                8.8,
                10.1,
                12.2,
                11.4,
                12.1,
                12.4,
                12.6,
                12.8,
                13.0,
                13.2,
                13.4,
                13.6,
                13.8,
                14.0,
                14.2,
            ],
            "high": [
                9.8,
                10.0,
                12.0,
                15.0,
                12.2,
                14.0,
                14.2,
                14.4,
                14.6,
                14.8,
                15.0,
                15.2,
                15.4,
                15.6,
                15.8,
                16.0,
            ],
            "low": [
                8.9,
                8.0,
                9.5,
                10.6,
                10.2,
                11.5,
                12.6,
                12.2,
                12.4,
                12.6,
                12.8,
                13.0,
                13.2,
                13.4,
                13.6,
                13.8,
            ],
            "close": [
                9.4,
                9.1,
                11.0,
                13.0,
                11.8,
                12.7,
                13.1,
                13.3,
                13.5,
                13.7,
                13.9,
                14.1,
                14.3,
                14.5,
                14.7,
                14.9,
            ],
            "volume": [100] * 16,
            "cisd_type": [
                None,
                None,
                "bullish",
                None,
                "bullish",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ],
        },
        index=index,
    )


def _research_frame_for_sweep_and_swing():
    index = pd.date_range("2026-01-02 09:30", periods=11, freq="15min")
    return pd.DataFrame(
        {
            "open": [12, 11, 12, 13, 11, 12, 13, 14, 17, 14, 13],
            "high": [13, 12, 13, 14, 13, 15, 14, 16, 18, 15, 14],
            "low": [11, 9, 10, 11, 8, 12, 11, 13, 14, 13, 12],
            "close": [12.5, 10, 12.5, 13.5, 12, 14.5, 13.5, 15.5, 15, 14, 13],
            "volume": [100] * 11,
            "cisd_type": [None, None, None, None, None, "bullish", None, None, "bearish", None, None],
        },
        index=index,
    )


def test_compute_three_bar_swings_marks_local_extrema():
    df = _research_frame_for_fvg()

    swing_low, swing_high = cisd_analysis._compute_three_bar_swings(df)

    assert swing_low.iloc[1] == True
    assert swing_low.iloc[2] == False
    assert swing_high.iloc[3] == True


def test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns():
    df = _research_frame_for_fvg()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated.loc[df.index[2], "has_dir_fvg_mid0"] == True
    assert annotated.loc[df.index[2], "fvg_mid0_hold_close_near"] == "held"
    assert annotated.loc[df.index[2], "fvg_mid0_hold_wick_far"] == "held"

    assert annotated.loc[df.index[4], "has_dir_fvg_mid1"] == True
    assert annotated.loc[df.index[4], "fvg_mid1_hold_close_near"] == "held"
    assert annotated.loc[df.index[4], "fvg_mid1_hold_wick_far"] == "held"


def test_prepare_returns_research_annotation_columns():
    df = _research_frame_for_fvg().drop(columns=["cisd_type"])

    prepared = cisd_analysis.prepare(df)

    expected_columns = {
        "cisd_type",
        "has_dir_fvg_mid0",
        "has_dir_fvg_mid1",
        "fvg_mid0_hold_close_near",
        "fvg_mid0_hold_wick_far",
        "fvg_mid1_hold_close_near",
        "fvg_mid1_hold_wick_far",
        "has_dir_sweep",
        "prev_bar_is_dir_swing",
        "cisd_bar_is_dir_swing",
    }

    assert expected_columns <= set(prepared.columns)


def test_annotate_cisd_research_raises_on_missing_cisd_type():
    df = _research_frame_for_fvg().drop(columns=["cisd_type"])

    with pytest.raises(ValueError, match="cisd_type"):
        cisd_analysis._annotate_cisd_research(df)


def test_research_annotation_flags_use_boolean_dtype():
    df = _research_frame_for_fvg()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated["has_dir_sweep"].dtype == bool
    assert annotated["prev_bar_is_dir_swing"].dtype == bool
    assert annotated["cisd_bar_is_dir_swing"].dtype == bool
    assert not annotated["has_dir_sweep"].any()


def test_classify_fvg_hold_returns_none_when_window_is_incomplete():
    df = _research_frame_for_fvg().iloc[:12]

    result = cisd_analysis._classify_fvg_hold(df, 2, "bullish", "close_near")

    assert result == "none"


@pytest.mark.parametrize("direction", ["sideways", ""])
def test_classify_fvg_hold_rejects_invalid_direction(direction):
    df = _research_frame_for_fvg()

    with pytest.raises(ValueError, match="direction"):
        cisd_analysis._classify_fvg_hold(df, 2, direction, "close_near")


@pytest.mark.parametrize("failure_mode", ["invalid", "held"])
def test_classify_fvg_hold_rejects_invalid_failure_mode(failure_mode):
    df = _research_frame_for_fvg()

    with pytest.raises(ValueError, match="failure_mode"):
        cisd_analysis._classify_fvg_hold(df, 2, "bullish", failure_mode)


def test_annotate_cisd_research_tags_directional_sweeps_and_swing_positions():
    df = _research_frame_for_sweep_and_swing()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated.loc[df.index[5], "has_dir_sweep"]
    assert annotated.loc[df.index[5], "prev_bar_is_dir_swing"]
    assert not annotated.loc[df.index[5], "cisd_bar_is_dir_swing"]

    assert annotated.loc[df.index[8], "cisd_bar_is_dir_swing"]
    assert not annotated.loc[df.index[8], "prev_bar_is_dir_swing"]
