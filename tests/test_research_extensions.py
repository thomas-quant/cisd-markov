import pandas as pd

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


def test_compute_three_bar_swings_marks_local_extrema():
    df = _research_frame_for_fvg()

    swing_low, swing_high = cisd_analysis._compute_three_bar_swings(df)

    assert swing_low.iloc[1] is True
    assert swing_low.iloc[2] is False
    assert swing_high.iloc[3] is True


def test_annotate_cisd_research_sets_mid0_mid1_fvg_and_hold_columns():
    df = _research_frame_for_fvg()

    annotated = cisd_analysis._annotate_cisd_research(df)

    assert annotated.loc[df.index[2], "has_dir_fvg_mid0"] is True
    assert annotated.loc[df.index[2], "fvg_mid0_hold_close_near"] == "held"
    assert annotated.loc[df.index[2], "fvg_mid0_hold_wick_far"] == "held"

    assert annotated.loc[df.index[4], "has_dir_fvg_mid1"] is True
    assert annotated.loc[df.index[4], "fvg_mid1_hold_close_near"] == "held"
    assert annotated.loc[df.index[4], "fvg_mid1_hold_wick_far"] == "held"
