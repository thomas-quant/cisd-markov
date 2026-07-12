"""Data-free and fixture tests for the Phase 10 conditioning-features report
and its existing-analysis byte-stability drift gate (D-12/D-13)."""
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

import scripts.build_conditioning_report as report_mod
from scripts.build_conditioning_report import build_existing_analysis_drift, build_new_features_report


# ── Fixture helpers ────────────────────────────────────────────────────────

def _row(analysis: str, timeframe: str, instrument: str, direction: str, bucket: str,
         rate: float, n: int, successes: int, ci_low: float, ci_high: float,
         min_n_pass: bool, bh_rank, bh_q_value, bh_significant: bool,
         corrected_pass: bool, p_value: float) -> dict:
    return {
        "analysis": analysis, "timeframe": timeframe, "instrument": instrument,
        "direction": direction, "bucket": bucket,
        "rate": rate, "n": n, "successes": successes,
        "ci_low": ci_low, "ci_high": ci_high, "ci_method": "wilson",
        "min_n_pass": min_n_pass, "slice": "discovery", "p_value": p_value,
        "bh_rank": bh_rank, "bh_q_value": bh_q_value,
        "bh_significant": bh_significant, "corrected_pass": corrected_pass,
    }


def _before_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("basic", "1H", "NQ", "bullish", "all", 0.58, 6000, 3480, 0.55, 0.61,
             True, 10, 0.001, True, True, 0.0002),
        _row("wick", "1H", "NQ", "bullish", "past_wick", 0.70, 2000, 1400, 0.66, 0.74,
             True, 3, 0.0003, True, True, 0.00001),
    ])


def _after_df_bh_moved_only() -> pd.DataFrame:
    """After regen: existing base columns unchanged, but bh_rank/bh_q_value/
    bh_significant/corrected_pass moved because the global BH family grew
    (D-13) -- new-analysis rows joined the family."""
    return pd.DataFrame([
        _row("basic", "1H", "NQ", "bullish", "all", 0.58, 6000, 3480, 0.55, 0.61,
             True, 25, 0.004, True, True, 0.0002),  # bh_rank/q_value moved
        _row("wick", "1H", "NQ", "bullish", "past_wick", 0.70, 2000, 1400, 0.66, 0.74,
             True, 8, 0.0009, True, True, 0.00001),  # bh_rank/q_value moved
        # a brand-new analysis row -- must be ignored by the drift check
        _row("session", "1H", "NQ", "bullish", "rth_open", 0.55, 40, 22, 0.40, 0.69,
             False, "", "", False, False, 0.5),
    ])


# ── build_existing_analysis_drift: D-12/D-13 ────────────────────────────────

def test_moved_bh_columns_are_not_flagged_as_drift() -> None:
    """Base columns identical; only bh_rank/bh_q_value moved -> not drift (D-13)."""
    drift = build_existing_analysis_drift(_before_df(), _after_df_bh_moved_only())
    assert drift == []


def test_changed_base_rate_is_flagged() -> None:
    before_df = _before_df()
    after_df = _after_df_bh_moved_only().copy()
    after_df.loc[after_df["analysis"] == "wick", "rate"] = 0.71  # perturb a base column

    drift = build_existing_analysis_drift(before_df, after_df)

    assert len(drift) == 1
    assert drift[0]["analysis"] == "wick"
    assert drift[0]["before_rate"] == pytest.approx(0.70)
    assert drift[0]["after_rate"] == pytest.approx(0.71)


def test_new_analysis_rows_are_ignored_by_drift_check() -> None:
    """The new 'session' row only exists in 'after' and is one of the 7 new
    analysis keys -- it must never surface in the drift gate."""
    drift = build_existing_analysis_drift(_before_df(), _after_df_bh_moved_only())
    assert all(row["analysis"] != "session" for row in drift)
    assert drift == []


@pytest.mark.parametrize("column", ["n", "successes", "ci_low", "ci_high", "min_n_pass"])
def test_each_base_column_change_is_flagged(column) -> None:
    before_df = _before_df()
    after_df = _after_df_bh_moved_only().copy()
    perturbation = {"n": 6001, "successes": 3481, "ci_low": 0.50, "ci_high": 0.70, "min_n_pass": False}
    after_df.loc[after_df["analysis"] == "basic", column] = perturbation[column]

    drift = build_existing_analysis_drift(before_df, after_df)

    assert len(drift) == 1
    assert drift[0]["analysis"] == "basic"


# ── build_new_features_report: SC4 (never drop below-n / not-confirmed) ────

def test_new_features_report_keeps_below_n_bucket() -> None:
    after_df = _after_df_bh_moved_only()

    rows = build_new_features_report(after_df)

    assert len(rows) == 1
    session_row = rows[0]
    assert session_row["analysis"] == "session"
    assert session_row["bucket"] == "rth_open"
    assert session_row["min_n_pass"] is False
    assert session_row["corrected_pass"] is False


def test_new_features_report_excludes_existing_analysis_rows() -> None:
    after_df = _after_df_bh_moved_only()

    rows = build_new_features_report(after_df)

    assert all(row["analysis"] not in ("basic", "wick") for row in rows)


# ── build_report: fixture-CSV integration (path constants patched) ─────────

def test_build_report_writes_report_and_returns_zero_when_clean(tmp_path: Path) -> None:
    before_path = tmp_path / "manifest_discovery_golden.csv.gz"
    after_path  = tmp_path / "validation_manifest_discovery.csv"
    report_path = tmp_path / "conditioning_features_report.csv"
    _before_df().to_csv(before_path, index=False)
    _after_df_bh_moved_only().to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_GOLDEN_PATH", before_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
        patch.object(report_mod, "REPORT_PATH", report_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 0
    assert report_path.exists()
    written = pd.read_csv(report_path)
    assert len(written) == 1
    assert written.iloc[0]["analysis"] == "session"


def test_build_report_returns_nonzero_when_existing_analysis_drift_present(tmp_path: Path) -> None:
    before_path = tmp_path / "manifest_discovery_golden.csv.gz"
    after_path  = tmp_path / "validation_manifest_discovery.csv"
    report_path = tmp_path / "conditioning_features_report.csv"
    _before_df().to_csv(before_path, index=False)
    drifted = _after_df_bh_moved_only().copy()
    drifted.loc[drifted["analysis"] == "basic", "n"] = 6001  # perturb an existing base column
    drifted.to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_GOLDEN_PATH", before_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
        patch.object(report_mod, "REPORT_PATH", report_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 1


def test_build_report_returns_nonzero_when_before_manifest_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist.csv.gz"
    after_path   = tmp_path / "validation_manifest_discovery.csv"
    _after_df_bh_moved_only().to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_GOLDEN_PATH", missing_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 1
