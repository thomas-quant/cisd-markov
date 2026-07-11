"""End-to-end golden bit-equality gate for the full validation pipeline (SC2).

This is the AUTHORITATIVE proof that a vectorization of `_annotate_cisd_research`
/ `_annotate_swing_smt_from_events` (Plans 08-02/08-03) has not changed the
published manifests. It regenerates all three validation manifests (discovery,
OOS, walk-forward) by invoking `scripts/build_validation.py` exactly as a
human would (`--oos`, `--walk-forward`, and the bare default), then compares
each freshly written `output/validation_manifest_*.csv` against the
corresponding pre-committed golden fixture in `tests/golden/`.

EQUALITY CRITERION (bit-preservation, NOT the reporting tolerance):
    PRIMARY: `pandas.testing.assert_frame_equal(regenerated, golden,
    check_exact=True)` after (a) aligning both frames to the same column
    order and (b) sorting both frames by the five bucket keys
    (`analysis, timeframe, instrument, direction, bucket`) to neutralize any
    incidental row-ordering difference between runs. This is achievable
    exactly (not approximately) because the two vectorized functions only
    ever produce bool/str/timestamp columns and integer counts; every
    downstream float column (`rate`, `ci_low`, `ci_high`, `p_value`,
    `bh_q_value`, `train_rate`, `test_rate`) is integer-derived and rounded to
    6 decimal places by `build_validation.py`, so two runs over identical
    input data produce identical floats bit-for-bit.

    FALLBACK (should not be needed — kept only as a documented escape hatch
    in case a genuine sub-ULP float reordering ever appears): relax to
    `check_exact=False, atol=1e-9, rtol=0` on the float columns only, while
    keeping int/str/timestamp columns exact.

    This bit-preservation check is DELIBERATELY far tighter than the ±0.05pp
    REPORTING tolerance used in `tests/test_characterization.py` (which
    exists to tolerate 1-decimal README rounding, not to certify byte-for-byte
    reproducibility). The two tolerances serve different purposes and must
    never be conflated: this module proves "nothing changed", while
    `test_characterization.py` proves "the headline numbers still match the
    published README figures within reporting precision".

Skip gates (all three must be satisfied for this module's tests to run):
    1. Real parquet data files present (`data/nq_1m.parquet`, `data/es_1m.parquet`).
    2. The local SMT package present at `_SMT_PKG_PATH` (or `SMT_PKG_PATH` env override).
    3. The opt-in `CISD_PERF_CHAR=1` environment variable is set.
A bare `.venv/bin/python -m pytest tests/` SKIPS this entire module (gate 3
alone guarantees that) so the routine suite stays fast. Run explicitly via:
    CISD_PERF_CHAR=1 .venv/bin/python -m pytest tests/test_perf_characterization.py -q
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from cisd_analysis import DATA_DIR, _SMT_PKG_PATH

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_VALIDATION = REPO_ROOT / "scripts" / "build_validation.py"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
OUTPUT_DIR = REPO_ROOT / "output"

BUCKET_KEYS = ["analysis", "timeframe", "instrument", "direction", "bucket"]

# ── Module-level triple skip gate ────────────────────────────────────────────
_NQ_FILE = DATA_DIR / "nq_1m.parquet"
_ES_FILE = DATA_DIR / "es_1m.parquet"
_DATA_PRESENT = _NQ_FILE.exists() and _ES_FILE.exists()
_SMT_PRESENT = _SMT_PKG_PATH.exists()
_ENV_ENABLED = os.environ.get("CISD_PERF_CHAR") == "1"

pytestmark = [
    pytest.mark.skipif(
        not _DATA_PRESENT,
        reason="Parquet data files not present — perf characterization skipped",
    ),
    pytest.mark.skipif(
        not _SMT_PRESENT,
        reason="SMT package not available — perf characterization skipped",
    ),
    pytest.mark.skipif(
        not _ENV_ENABLED,
        reason="Opt-in heavy test — set CISD_PERF_CHAR=1 to run (deliberately excluded from routine suite)",
    ),
]

_MANIFESTS = {
    "discovery": {
        "cli_args": [],
        "output": OUTPUT_DIR / "validation_manifest_discovery.csv",
        "golden": GOLDEN_DIR / "manifest_discovery_golden.csv.gz",
    },
    "oos": {
        "cli_args": ["--oos"],
        "output": OUTPUT_DIR / "validation_manifest_oos.csv",
        "golden": GOLDEN_DIR / "manifest_oos_golden.csv.gz",
    },
    "walkforward": {
        "cli_args": ["--walk-forward"],
        "output": OUTPUT_DIR / "validation_manifest_walkforward.csv",
        "golden": GOLDEN_DIR / "manifest_walkforward_golden.csv.gz",
    },
}


def _run_build_validation(cli_args: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(BUILD_VALIDATION), *cli_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"scripts/build_validation.py {' '.join(cli_args)} failed "
        f"(exit {result.returncode}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@pytest.fixture(scope="module")
def regenerated_manifests() -> dict[str, pd.DataFrame]:
    """Regenerate all three manifests by invoking build_validation.py exactly
    as a human/CI would, then load each into a DataFrame. Runs once per
    module (not once per test) since this is the slow (~20-24 min) step.
    """
    frames: dict[str, pd.DataFrame] = {}
    for slice_label, spec in _MANIFESTS.items():
        _run_build_validation(spec["cli_args"])
        assert spec["output"].exists(), f"{spec['output']} was not written by build_validation.py"
        frames[slice_label] = pd.read_csv(spec["output"])
    return frames


def _assert_matches_golden(regenerated: pd.DataFrame, golden_path: Path) -> None:
    golden = pd.read_csv(golden_path)

    # Align column order (defensive — both should already match since neither
    # frame's schema changed, but this keeps the comparison robust to any
    # incidental column reordering that isn't itself a behavior change).
    assert set(regenerated.columns) == set(golden.columns), (
        f"Column set mismatch.\nRegenerated: {sorted(regenerated.columns)}\n"
        f"Golden:      {sorted(golden.columns)}"
    )
    golden = golden[regenerated.columns.tolist()]

    # Sort both frames by the five bucket keys to neutralize any incidental
    # row-ordering difference between runs (see module docstring).
    sort_keys = [k for k in BUCKET_KEYS if k in regenerated.columns]
    regenerated_sorted = regenerated.sort_values(sort_keys).reset_index(drop=True)
    golden_sorted = golden.sort_values(sort_keys).reset_index(drop=True)

    try:
        pd.testing.assert_frame_equal(regenerated_sorted, golden_sorted, check_exact=True)
    except AssertionError:
        # Documented fallback (see module docstring) — should not be needed
        # in practice since all floats are integer-derived and 6dp-rounded.
        float_cols = regenerated_sorted.select_dtypes(include=["float64", "float32"]).columns.tolist()
        other_cols = [c for c in regenerated_sorted.columns if c not in float_cols]
        pd.testing.assert_frame_equal(
            regenerated_sorted[other_cols], golden_sorted[other_cols], check_exact=True
        )
        pd.testing.assert_frame_equal(
            regenerated_sorted[float_cols], golden_sorted[float_cols],
            check_exact=False, atol=1e-9, rtol=0,
        )


def test_discovery_manifest_matches_golden(regenerated_manifests):
    _assert_matches_golden(regenerated_manifests["discovery"], _MANIFESTS["discovery"]["golden"])


def test_oos_manifest_matches_golden(regenerated_manifests):
    _assert_matches_golden(regenerated_manifests["oos"], _MANIFESTS["oos"]["golden"])


def test_walkforward_manifest_matches_golden(regenerated_manifests):
    _assert_matches_golden(regenerated_manifests["walkforward"], _MANIFESTS["walkforward"]["golden"])
