"""Data-free and fixture tests for the SMT invalidation before/after report builder."""
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


import scripts.build_smt_invalidation_report as report_mod
from scripts.build_smt_invalidation_report import build_non_smt_drift, build_smt_invalidation_rows


# ── Fixture helpers ────────────────────────────────────────────────────────

def _row(analysis: str, timeframe: str, instrument: str, direction: str, bucket: str,
         rate: float, n: int) -> dict:
    return {
        "analysis": analysis, "timeframe": timeframe, "instrument": instrument,
        "direction": direction, "bucket": bucket, "rate": rate, "n": n,
    }


def _before_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("smt_cisd", "1H", "NQ", "bullish", "w/ SMT", 0.60, 500),
        _row("smt_cisd", "1H", "NQ", "bullish", "no SMT", 0.55, 4000),
        _row("basic", "1H", "NQ", "bullish", "all", 0.58, 6000),
        _row("wick", "1H", "NQ", "bullish", "past_wick", 0.70, 2000),
    ])


def _after_df() -> pd.DataFrame:
    return pd.DataFrame([
        _row("smt_cisd", "1H", "NQ", "bullish", "w/ SMT", 0.59, 503),
        _row("smt_cisd", "1H", "NQ", "bullish", "expired SMT", 0.72, 225),
        _row("smt_cisd", "1H", "NQ", "bullish", "w/ SMT & survived", 0.70, 377),
        _row("smt_cisd", "1H", "NQ", "bullish", "w/ SMT & broke", 0.27, 126),
        _row("smt_cisd", "1H", "NQ", "bullish", "no SMT", 0.61, 4734),
        _row("basic", "1H", "NQ", "bullish", "all", 0.58, 6000),
        _row("wick", "1H", "NQ", "bullish", "past_wick", 0.70, 2000),
    ])


# ── build_smt_invalidation_rows: before/after w/ SMT delta ──────────────────

def test_w_smt_row_computes_rate_delta_pp_and_n_delta() -> None:
    rows = build_smt_invalidation_rows(_before_df(), _after_df())
    w_smt_row = next(
        r for r in rows
        if r["bucket"] == "w/ SMT" and r["timeframe"] == "1H"
        and r["instrument"] == "NQ" and r["direction"] == "bullish"
    )
    assert w_smt_row["before_rate"] == pytest.approx(0.60)
    assert w_smt_row["after_rate"] == pytest.approx(0.59)
    assert w_smt_row["before_n"] == 500
    assert w_smt_row["after_n"] == 503
    assert w_smt_row["rate_delta_pp"] == pytest.approx(-1.0)
    assert w_smt_row["n_delta"] == 3


def test_new_bucket_after_only_rows_appear() -> None:
    rows = build_smt_invalidation_rows(_before_df(), _after_df())
    by_bucket = {r["bucket"]: r for r in rows if r["bucket"] != "w/ SMT"}

    assert set(by_bucket) == {"expired SMT", "w/ SMT & survived", "w/ SMT & broke"}
    for bucket, expected_rate, expected_n in (
        ("expired SMT", 0.72, 225),
        ("w/ SMT & survived", 0.70, 377),
        ("w/ SMT & broke", 0.27, 126),
    ):
        row = by_bucket[bucket]
        assert row["after_rate"] == pytest.approx(expected_rate)
        assert row["after_n"] == expected_n
        assert pd.isna(row["before_rate"])
        assert pd.isna(row["before_n"])
        assert pd.isna(row["rate_delta_pp"])
        assert pd.isna(row["n_delta"])


# ── build_non_smt_drift: D-09a behavior-preservation invariant ──────────────

def test_non_smt_drift_empty_when_rows_unchanged() -> None:
    assert build_non_smt_drift(_before_df(), _after_df()) == []


def test_non_smt_drift_flags_perturbed_non_smt_row() -> None:
    before_df = _before_df()
    after_df  = _after_df().copy()
    after_df.loc[after_df["analysis"] == "wick", "rate"] = 0.71  # perturb a non-smt rate

    drift = build_non_smt_drift(before_df, after_df)

    assert len(drift) == 1
    assert drift[0]["analysis"] == "wick"
    assert drift[0]["before_rate"] == pytest.approx(0.70)
    assert drift[0]["after_rate"] == pytest.approx(0.71)


def test_non_smt_drift_ignores_smt_role_and_other_smt_prefixed_analyses() -> None:
    before_df = _before_df()  # no smt_role rows pre-fix (new analysis)
    after_df = pd.concat([
        _after_df(),
        pd.DataFrame([_row("smt_role", "1H", "NQ", "bullish", "swept", 0.65, 300)]),
    ], ignore_index=True)

    assert build_non_smt_drift(before_df, after_df) == []


# ── build_report: fixture-CSV integration (path constants patched) ──────────

def test_build_report_writes_csv_and_returns_zero_when_clean(tmp_path: Path) -> None:
    before_path = tmp_path / "validation_manifest_discovery_before_smt_fix.csv"
    after_path  = tmp_path / "validation_manifest_discovery.csv"
    report_path = tmp_path / "smt_invalidation_report.csv"
    _before_df().to_csv(before_path, index=False)
    _after_df().to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_MANIFEST_PATH", before_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
        patch.object(report_mod, "REPORT_PATH", report_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 0
    assert report_path.exists()
    written = pd.read_csv(report_path)
    assert len(written) == 4  # w/ SMT + 3 new-bucket rows
    assert set(written["bucket"]) == {
        "w/ SMT", "expired SMT", "w/ SMT & survived", "w/ SMT & broke",
    }


def test_build_report_returns_nonzero_when_non_smt_drift_present(tmp_path: Path) -> None:
    before_path = tmp_path / "validation_manifest_discovery_before_smt_fix.csv"
    after_path  = tmp_path / "validation_manifest_discovery.csv"
    report_path = tmp_path / "smt_invalidation_report.csv"
    _before_df().to_csv(before_path, index=False)
    drifted = _after_df().copy()
    drifted.loc[drifted["analysis"] == "basic", "n"] = 6001  # perturb a non-smt n
    drifted.to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_MANIFEST_PATH", before_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
        patch.object(report_mod, "REPORT_PATH", report_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 1
    assert report_path.exists()  # report still written before the drift gate fires


def test_build_report_returns_nonzero_when_manifest_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist.csv"
    after_path   = tmp_path / "validation_manifest_discovery.csv"
    _after_df().to_csv(after_path, index=False)

    with (
        patch.object(report_mod, "BEFORE_DISCOVERY_MANIFEST_PATH", missing_path),
        patch.object(report_mod, "AFTER_DISCOVERY_MANIFEST_PATH", after_path),
    ):
        exit_code = report_mod.build_report()

    assert exit_code == 1
