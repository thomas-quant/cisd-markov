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

    assert payload["50"] == 2.5
    assert payload["5"] == 1.15
    assert payload["95"] == 3.8499999999999996
