"""Build the Phase 10 conditioning-features report + existing-analysis drift gate.

Reads the pre-Phase-10 discovery golden manifest
(``tests/golden/manifest_discovery_golden.csv.gz``) as "before" alongside the
freshly regenerated discovery manifest
(``output/validation_manifest_discovery.csv``) as "after" and:

- Enforces D-12 (existing binary analyses' published rates are byte-stable):
  every row whose ``analysis`` is NOT one of the 7 new Phase 10 analysis keys
  must be unchanged on its BASE columns (``rate``, ``n``, ``successes``,
  ``ci_low``, ``ci_high``, ``min_n_pass``). The BH-FDR columns (``bh_rank``,
  ``bh_q_value``, ``bh_significant``, ``corrected_pass``) and ``p_value`` are
  explicitly EXCLUDED from this comparison -- they move by design because
  ``apply_bh_correction`` builds one global BH family across the whole grid
  (D-13); a moved corrected verdict is the correct consequence of testing more
  hypotheses, not drift. Any base-column drift is a bug to investigate, never
  silently republished -- the script prints the offending rows and exits
  non-zero.
- Emits ``output/conditioning_features_report.csv``: a tidy per-bucket table
  of the 7 new analyses' rows (one row per analysis/timeframe/instrument/
  direction/bucket), keeping below-n and not-corrected buckets rather than
  dropping them (SC4).

Usage::

    python3 scripts/build_conditioning_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ── Path constants (patched in unit tests via patch.object) ──────────────────

BEFORE_DISCOVERY_GOLDEN_PATH  = REPO_ROOT / "tests" / "golden" / "manifest_discovery_golden.csv.gz"
AFTER_DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
REPORT_PATH                   = REPO_ROOT / "output" / "conditioning_features_report.csv"

# ── The 7 new Phase 10 conditioning-feature analysis keys ───────────────────

_NEW_ANALYSIS_KEYS = (
    "wick_distance", "sweep_depth", "fvg_size",
    "effort_result", "rvol", "volume_zscore", "session",
)

# ── Drift gate: base columns compared vs. excluded BH/p-value columns ───────

_MERGE_KEYS  = ["analysis", "timeframe", "instrument", "direction", "bucket"]
_BASE_COLUMNS = ["rate", "n", "successes", "ci_low", "ci_high", "min_n_pass"]

# Explicitly excluded from the drift comparison (D-13): these move by design
# because apply_bh_correction is one global BH family across the whole grid,
# and adding the 7 new analyses' buckets legitimately shifts every existing
# bucket's rank / q-value / significance.
_EXCLUDED_FROM_DRIFT = ["bh_rank", "bh_q_value", "bh_significant", "corrected_pass", "p_value"]
assert not (set(_BASE_COLUMNS) & set(_EXCLUDED_FROM_DRIFT)), (
    "D-13 invariant violated: a BH/p-value column leaked into the compared base columns"
)

_NEW_FEATURES_REPORT_COLS = [
    "analysis", "timeframe", "instrument", "direction", "bucket",
    "rate", "n", "ci_low", "ci_high", "min_n_pass",
    "bh_significant", "corrected_pass",
    # Corridor-position null (quick task 260929-mkg) — the verdict columns.
    "geo_n", "geo_expected_rate", "geo_lift", "geo_verdict",
]


# ── Existing-analysis byte-stability drift gate (D-12/D-13) ─────────────────

def build_existing_analysis_drift(before_df: pd.DataFrame, after_df: pd.DataFrame) -> list[dict]:
    """Return rows whose BASE columns differ for analyses NOT in _NEW_ANALYSIS_KEYS.

    Mirrors ``build_non_smt_drift`` (scripts/build_smt_invalidation_report.py)
    exactly: subset both manifests to non-new-analysis rows, merge on the
    bucket-identity keys, and flag rows where any base column differs.
    bh_*/p_value are never compared here (D-13) -- they move by design.
    """
    before_existing = before_df[~before_df["analysis"].isin(_NEW_ANALYSIS_KEYS)]
    after_existing  = after_df[~after_df["analysis"].isin(_NEW_ANALYSIS_KEYS)]

    before_cols = {col: f"before_{col}" for col in _BASE_COLUMNS}
    after_cols  = {col: f"after_{col}" for col in _BASE_COLUMNS}

    merged = before_existing[_MERGE_KEYS + _BASE_COLUMNS].rename(columns=before_cols).merge(
        after_existing[_MERGE_KEYS + _BASE_COLUMNS].rename(columns=after_cols),
        on=_MERGE_KEYS,
        how="outer",
    )

    drift_mask = pd.Series(False, index=merged.index)
    for col in _BASE_COLUMNS:
        drift_mask = drift_mask | (merged[f"before_{col}"] != merged[f"after_{col}"])

    drifted = merged[drift_mask]
    return drifted.to_dict(orient="records")


# ── New-features report: every new bucket, below-n / not-corrected kept ────

def build_new_features_report(after_df: pd.DataFrame) -> list[dict]:
    """Return one row per new-analysis bucket, never dropping below-n / not-confirmed rows (SC4)."""
    new_rows = after_df[after_df["analysis"].isin(_NEW_ANALYSIS_KEYS)]
    cols = [col for col in _NEW_FEATURES_REPORT_COLS if col in new_rows.columns]
    return new_rows[cols].to_dict(orient="records")


# ── Entry point: read manifests, run the drift gate, write the report ──────

def build_report() -> int:
    """Read the before/after manifests, enforce the drift gate, write the report. Return exit code."""
    if not BEFORE_DISCOVERY_GOLDEN_PATH.exists():
        print(f"[error] before discovery golden manifest not found: {BEFORE_DISCOVERY_GOLDEN_PATH}")
        return 1
    if not AFTER_DISCOVERY_MANIFEST_PATH.exists():
        print(f"[error] after discovery manifest not found: {AFTER_DISCOVERY_MANIFEST_PATH}")
        return 1

    before_df = pd.read_csv(BEFORE_DISCOVERY_GOLDEN_PATH)
    after_df  = pd.read_csv(AFTER_DISCOVERY_MANIFEST_PATH)

    drift = build_existing_analysis_drift(before_df, after_df)
    if drift:
        print(
            f"[error] existing-analysis drift detected in {len(drift)} row(s) — this is a bug "
            "to investigate (D-12), never silently republish:"
        )
        for row in drift:
            print(f"        {row}")
        return 1

    print("[ok] existing-analysis drift check clean (D-12)")

    new_rows = build_new_features_report(after_df)
    report_df = pd.DataFrame(new_rows, columns=_NEW_FEATURES_REPORT_COLS)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(REPORT_PATH, index=False)
    print(f"[ok] wrote {REPORT_PATH} ({len(report_df)} rows)")

    return 0


if __name__ == "__main__":
    sys.exit(build_report())
