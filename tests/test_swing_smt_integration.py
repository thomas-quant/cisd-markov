import pandas as pd

from cisd_analysis import _annotate_swing_smt_from_events


def test_annotate_swing_smt_uses_left_window_and_sets_role():
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    df = pd.DataFrame(
        {
            "cisd_type": [None, "bullish", "bullish", "bullish", "bearish", None],
        },
        index=index,
    )
    events = pd.DataFrame(
        [
            {
                "signal_type": "Bullish Swing SMT",
                "created_ts": index[1],
                "sweeping_asset": "NQ",
                "failing_asset": "ES",
            },
            {
                "signal_type": "Bearish Swing SMT",
                "created_ts": index[0],
                "sweeping_asset": "ES",
                "failing_asset": "NQ",
            },
        ]
    )

    nq = _annotate_swing_smt_from_events(df, events, instrument="NQ")
    es = _annotate_swing_smt_from_events(df, events, instrument="ES")

    assert nq.loc[index[1], "swing_smt_tag"] == "w/ SMT"
    assert nq.loc[index[3], "swing_smt_tag"] == "w/ SMT"   # t-2 match still counts
    assert nq.loc[index[4], "swing_smt_tag"] == "no SMT"   # t-4 bearish event must not count
    assert nq.loc[index[1], "swing_smt_role"] == "swept"
    assert es.loc[index[1], "swing_smt_role"] == "failed_to_sweep"
