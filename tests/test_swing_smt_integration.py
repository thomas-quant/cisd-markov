import cisd_analysis
import pytest
import pandas as pd

from cisd_analysis import _SMT_PKG_PATH, _annotate_swing_smt_from_events


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

    assert nq.loc[index[1], "has_swing_smt"]
    assert nq.loc[index[1], "swing_smt_tag"] == "w/ SMT"
    assert nq.loc[index[1], "swing_smt_match_ts"] == index[1]
    assert nq.loc[index[1], "swing_smt_role"] == "swept"
    assert es.loc[index[1], "swing_smt_role"] == "failed_to_sweep"

    assert nq.loc[index[3], "has_swing_smt"]
    assert nq.loc[index[3], "swing_smt_tag"] == "w/ SMT"   # t-2 match still counts
    assert nq.loc[index[3], "swing_smt_match_ts"] == index[1]
    assert not nq.loc[index[4], "has_swing_smt"]
    assert nq.loc[index[4], "swing_smt_tag"] == "no SMT"   # t-4 bearish event must not count
    assert nq.loc[index[4], "swing_smt_match_ts"] is pd.NaT
    assert nq.loc[index[4], "swing_smt_role"] == "none"
    assert es.loc[index[1], "swing_smt_role"] == "failed_to_sweep"


def test_annotate_swing_smt_raises_on_missing_cisd_type():
    index = pd.date_range("2026-01-01 09:30", periods=2, freq="15min")
    df = pd.DataFrame({"open": [1, 2]}, index=index)
    events = pd.DataFrame(
        [
            {
                "signal_type": "Bullish Swing SMT",
                "created_ts": index[1],
                "sweeping_asset": "NQ",
                "failing_asset": "ES",
            }
        ]
    )

    with pytest.raises(ValueError, match="cisd_type"):
        _annotate_swing_smt_from_events(df, events, instrument="NQ")


@pytest.mark.parametrize("missing_column", ["signal_type", "created_ts", "sweeping_asset", "failing_asset"])
def test_annotate_swing_smt_raises_on_missing_event_columns(missing_column):
    index = pd.date_range("2026-01-01 09:30", periods=2, freq="15min")
    df = pd.DataFrame({"cisd_type": [None, "bullish"]}, index=index)
    events = pd.DataFrame(
        [
            {
                "signal_type": "Bullish Swing SMT",
                "created_ts": index[1],
                "sweeping_asset": "NQ",
                "failing_asset": "ES",
            }
        ]
    ).drop(columns=[missing_column])

    with pytest.raises(ValueError, match=missing_column):
        _annotate_swing_smt_from_events(df, events, instrument="NQ")


def test_prepare_pair_applies_vectorized_swing_smt_annotations(monkeypatch):
    index = pd.date_range("2026-01-01 09:30", periods=6, freq="15min")
    minute = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5, 6],
            "high": [2, 3, 4, 5, 6, 7],
            "low": [0, 1, 2, 3, 4, 5],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
            "volume": [10, 10, 10, 10, 10, 10],
        },
        index=index,
    )

    monkeypatch.setattr(
        cisd_analysis,
        "_scan_swing_smt_events",
        lambda df_nq, df_es: pd.DataFrame(
            [
                {
                    "signal_type": "Bullish Swing SMT",
                    "created_ts": index[2],
                    "sweeping_asset": "NQ",
                    "failing_asset": "ES",
                }
            ]
        ),
    )

    df_nq, df_es = cisd_analysis.prepare_pair(minute, minute, "15min", with_swing_smt=True)

    assert "swing_smt_tag" in df_nq.columns
    assert "swing_smt_tag" in df_es.columns


def test_prepare_pair_aligns_misaligned_resampled_frames(monkeypatch):
    nq_index = pd.date_range("2026-01-01 09:30", periods=120, freq="15min")
    es_index = pd.date_range("2026-01-01 09:30", periods=60, freq="15min")
    nq_1m = pd.DataFrame(
        {
            "open": range(len(nq_index)),
            "high": [value + 1 for value in range(len(nq_index))],
            "low": [value - 1 for value in range(len(nq_index))],
            "close": [value + 0.5 for value in range(len(nq_index))],
            "volume": [100] * len(nq_index),
        },
        index=nq_index,
    )
    es_1m = pd.DataFrame(
        {
            "open": range(len(es_index)),
            "high": [value + 1 for value in range(len(es_index))],
            "low": [value - 1 for value in range(len(es_index))],
            "close": [value + 0.5 for value in range(len(es_index))],
            "volume": [100] * len(es_index),
        },
        index=es_index,
    )

    seen = {}

    def fake_scan(df_nq, df_es):
        seen["nq_index"] = df_nq.index
        seen["es_index"] = df_es.index
        return pd.DataFrame(
            columns=["signal_type", "created_ts", "sweeping_asset", "failing_asset"]
        )

    monkeypatch.setattr(cisd_analysis, "_scan_swing_smt_events", fake_scan)

    df_nq, df_es = cisd_analysis.prepare_pair(nq_1m, es_1m, "1H", with_swing_smt=True)
    expected_nq = cisd_analysis.resample_ohlcv(nq_1m, "1H")
    expected_es = cisd_analysis.resample_ohlcv(es_1m, "1H")
    expected_shared = expected_nq.index.intersection(expected_es.index)

    assert df_nq.index.equals(expected_nq.index)
    assert df_es.index.equals(expected_es.index)
    assert seen["nq_index"].equals(expected_shared)
    assert seen["es_index"].equals(expected_shared)
    assert seen["nq_index"].equals(seen["es_index"])


def test_prepare_pair_swing_smt_columns_exist_when_scanner_runs():
    if not _SMT_PKG_PATH.exists():
        pytest.skip("SMT package not available")

    index = pd.date_range("2026-01-01 09:30", periods=40, freq="15min")
    base = pd.Series(range(len(index)), index=index, dtype=float)
    df_nq_1m = pd.DataFrame(
        {
            "open": 100 + base * 0.2,
            "high": 100.5 + base * 0.2,
            "low": 99.5 + base * 0.2,
            "close": 100.1 + base * 0.2,
            "volume": 1000 + base.astype(int),
        },
        index=index,
    )
    df_es_1m = pd.DataFrame(
        {
            "open": 200 + base * 0.15,
            "high": 200.4 + base * 0.15,
            "low": 199.6 + base * 0.15,
            "close": 200.05 + base * 0.15,
            "volume": 1200 + base.astype(int),
        },
        index=index,
    )

    df_nq, df_es = cisd_analysis.prepare_pair(df_nq_1m, df_es_1m, "15min", with_swing_smt=True)

    expected_columns = {"has_swing_smt", "swing_smt_tag", "swing_smt_match_ts", "swing_smt_role"}
    assert expected_columns <= set(df_nq.columns)
    assert expected_columns <= set(df_es.columns)
    assert set(df_nq["swing_smt_tag"].unique()) <= {"w/ SMT", "no SMT"}


def test_compute_smt_cisd_splits_runs_by_swing_smt_tag():
    index = pd.date_range("2026-01-01 09:30", periods=5, freq="15min")
    df = pd.DataFrame(
        {
            "open": [10, 9, 11, 12, 12],
            "high": [11, 10, 13, 13, 14],
            "low": [9, 8, 10, 11, 11],
            "close": [9, 11, 12, 12, 13],
            "direction": ["bearish", "bullish", "bullish", "neutral", "bullish"],
            "prev_close": [None, 9, 11, 12, 12],
            "prev_direction": [None, "bearish", "bullish", "bullish", "neutral"],
            "prev_high": [None, 11, 10, 13, 13],
            "prev_low": [None, 9, 8, 10, 11],
            "cisd_type": [None, "bullish", None, None, None],
            "swing_smt_tag": ["no SMT", "w/ SMT", "no SMT", "no SMT", "no SMT"],
        },
        index=index,
    )

    stats = cisd_analysis.compute_smt_cisd(df)

    assert stats["bullish"]["w/ SMT"]["total"] == 1
    assert stats["bullish"]["no SMT"]["total"] == 0
