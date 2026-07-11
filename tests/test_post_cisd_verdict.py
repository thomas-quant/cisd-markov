"""Data-free and fixture tests for the corrected post-CISD verdict builder."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import scripts.build_post_cisd_verdict as verdict_mod
from scripts.build_post_cisd_verdict import _bucket_clears, rollup_by_tag


# ── _bucket_clears: D-02 three-condition AND ────────────────────────────────

def test_bucket_clears_all_three_conditions_above_half() -> None:
    assert _bucket_clears(0.62, True, "wf-robust", 0.58, 20) is True


def test_bucket_clears_persistent_weakness_below_half() -> None:
    assert _bucket_clears(0.40, True, "wf-robust", 0.44, 20) is True


def test_bucket_clears_rejects_failed_corrected_pass() -> None:
    assert _bucket_clears(0.62, False, "wf-robust", 0.58, 20) is False
    assert _bucket_clears(0.62, float("nan"), "wf-robust", 0.58, 20) is False


@pytest.mark.parametrize("wf_verdict", ["wf-fragile", "no-folds", "pass", None])
def test_bucket_clears_rejects_non_robust_walkforward(wf_verdict: str | None) -> None:
    assert _bucket_clears(0.62, True, wf_verdict, 0.58, 20) is False


def test_bucket_clears_rejects_opposite_oos_side() -> None:
    assert _bucket_clears(0.62, True, "wf-robust", 0.48, 20) is False


@pytest.mark.parametrize("oos_n", [0, float("nan"), None])
def test_bucket_clears_rejects_absent_oos(oos_n: float | None) -> None:
    assert _bucket_clears(0.62, True, "wf-robust", 0.58, oos_n) is False


def test_bucket_clears_rejects_missing_oos_rate() -> None:
    assert _bucket_clears(0.62, True, "wf-robust", float("nan"), 20) is False


def test_bucket_clears_rejects_discovery_boundary() -> None:
    assert _bucket_clears(0.50, True, "wf-robust", 0.58, 20) is False


# ── rollup_by_tag: D-03 strict majority ─────────────────────────────────────

def _bucket_rows(analysis: str, tag: str, n_cleared: int, total: int = 16) -> list[dict]:
    return [
        {"analysis": analysis, "bucket": tag, "clears_bar": i < n_cleared}
        for i in range(total)
    ]


def test_rollup_by_tag_requires_strict_majority() -> None:
    rows = (
        _bucket_rows("post_cisd_context", "nine_of_sixteen", 9)
        + _bucket_rows("post_cisd_context", "eight_of_sixteen", 8)
    )

    by_tag = {(row["analysis"], row["tag"]): row for row in rollup_by_tag(rows)}

    assert by_tag[("post_cisd_context", "nine_of_sixteen")] == {
        "analysis": "post_cisd_context",
        "tag": "nine_of_sixteen",
        "n_buckets": 16,
        "n_cleared": 9,
        "verdict": "cleared",
    }
    assert by_tag[("post_cisd_context", "eight_of_sixteen")]["verdict"] == "not-cleared"


def test_rollup_by_tag_groups_by_analysis_and_tag() -> None:
    rows = [
        {"analysis": "post_cisd_context", "bucket": "shared", "clears_bar": True},
        {"analysis": "candle1_followthrough", "bucket": "shared", "clears_bar": False},
    ]

    result = rollup_by_tag(rows)

    assert len(result) == 2
    assert {(row["analysis"], row["verdict"]) for row in result} == {
        ("post_cisd_context", "cleared"),
        ("candle1_followthrough", "not-cleared"),
    }


def test_rollup_failed_gap_against_reversal_uses_generic_path() -> None:
    rows = _bucket_rows(
        "post_cisd_context",
        "failed_gap_against_reversal",
        n_cleared=2,
        total=3,
    )

    assert rollup_by_tag(rows) == [{
        "analysis": "post_cisd_context",
        "tag": "failed_gap_against_reversal",
        "n_buckets": 3,
        "n_cleared": 2,
        "verdict": "cleared",
    }]


# ── build_verdict: fixture-CSV integration ──────────────────────────────────

def test_build_verdict_joins_scopes_deduplicates_and_writes(tmp_path: Path) -> None:
    keys = [
        ("post_cisd_context", "1H", "NQ", "bullish", "failed_gap_against_reversal"),
        ("post_cisd_context", "4H", "ES", "bearish", "failed_gap_against_reversal"),
        ("post_cisd_context", "15min", "NQ", "bearish", "failed_gap_against_reversal"),
        ("candle1_followthrough", "1H", "NQ", "bullish", "candle1_failed"),
        ("candle1_followthrough", "4H", "ES", "bearish", "candle1_failed"),
        ("basic", "1H", "NQ", "bullish", "all"),
    ]
    discovery_rates = [0.62, 0.40, 0.61, 0.63, 0.65, 0.70]
    oos_rates       = [0.58, 0.44, 0.48, 0.60, 0.45, 0.68]
    corrected       = [True, True, True, True, True, True]
    wf_verdicts     = ["wf-robust", "wf-robust", "wf-robust", "wf-robust", "wf-robust", "wf-robust"]

    discovery_rows = [
        dict(zip(["analysis", "timeframe", "instrument", "direction", "bucket"], key))
        | {"rate": rate, "corrected_pass": corrected_pass}
        for key, rate, corrected_pass in zip(keys, discovery_rates, corrected)
    ]
    oos_rows = [
        dict(zip(["analysis", "timeframe", "instrument", "direction", "bucket"], key))
        | {"rate": rate, "n": 20}
        for key, rate in zip(keys, oos_rates)
    ]
    walkforward_rows = []
    for key, wf_verdict in zip(keys, wf_verdicts):
        repeats = 4 if key == keys[0] else 1
        for fold_index in range(1, repeats + 1):
            walkforward_rows.append(
                dict(zip(["analysis", "timeframe", "instrument", "direction", "bucket"], key))
                | {
                    "fold_index": fold_index,
                    "train_end": "2022-01-01",
                    "test_end": "2023-01-01",
                    "wf_verdict": wf_verdict,
                }
            )

    disc_path    = tmp_path / "validation_manifest_discovery.csv"
    oos_path     = tmp_path / "validation_manifest_oos.csv"
    wf_path      = tmp_path / "validation_manifest_walkforward.csv"
    buckets_path = tmp_path / "post_cisd_verdict.csv"
    rollup_path  = tmp_path / "post_cisd_verdict_rollup.csv"
    pd.DataFrame(discovery_rows).to_csv(disc_path, index=False)
    pd.DataFrame(oos_rows).to_csv(oos_path, index=False)
    pd.DataFrame(walkforward_rows).to_csv(wf_path, index=False)

    with (
        patch.object(verdict_mod, "DISCOVERY_MANIFEST_PATH", disc_path),
        patch.object(verdict_mod, "OOS_MANIFEST_PATH", oos_path),
        patch.object(verdict_mod, "WALKFORWARD_MANIFEST_PATH", wf_path),
        patch.object(verdict_mod, "VERDICT_BUCKETS_PATH", buckets_path),
        patch.object(verdict_mod, "VERDICT_ROLLUP_PATH", rollup_path),
    ):
        verdict_mod.build_verdict()

    buckets = pd.read_csv(buckets_path)
    rollup  = pd.read_csv(rollup_path)

    assert list(buckets.columns) == [
        "analysis", "timeframe", "instrument", "direction", "bucket",
        "discovery_rate", "corrected_pass", "wf_verdict", "oos_rate",
        "oos_n", "same_side", "clears_bar",
    ]
    assert list(rollup.columns) == [
        "analysis", "tag", "n_buckets", "n_cleared", "verdict",
    ]

    # D-01: the third-analysis fixture row is proven absent from BOTH outputs.
    assert "basic" not in set(buckets["analysis"])
    assert "basic" not in set(rollup["analysis"])
    assert set(buckets["analysis"]) == set(verdict_mod.POST_CISD_ANALYSES)
    assert set(rollup["analysis"]) == set(verdict_mod.POST_CISD_ANALYSES)

    # Four repeated walk-forward folds must still yield one merged bucket row.
    repeated = buckets[
        (buckets["analysis"] == "post_cisd_context")
        & (buckets["timeframe"] == "1H")
        & (buckets["bucket"] == "failed_gap_against_reversal")
    ]
    assert len(repeated) == 1
    assert len(buckets) == 5

    reversal = rollup[
        (rollup["analysis"] == "post_cisd_context")
        & (rollup["tag"] == "failed_gap_against_reversal")
    ].iloc[0]
    assert (reversal["n_buckets"], reversal["n_cleared"], reversal["verdict"]) == (
        3, 2, "cleared",
    )

    followthrough = rollup[
        (rollup["analysis"] == "candle1_followthrough")
        & (rollup["tag"] == "candle1_failed")
    ].iloc[0]
    assert (followthrough["n_buckets"], followthrough["n_cleared"], followthrough["verdict"]) == (
        2, 1, "not-cleared",
    )
