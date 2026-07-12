"""Build the before/after SMT invalidation-fix report (D-09/D-09a).

Reads the preserved pre-fix discovery manifest
(``output/validation_manifest_discovery_before_smt_fix.csv``) alongside the
regenerated discovery manifest (``output/validation_manifest_discovery.csv``)
and writes ``output/smt_invalidation_report.csv``:

- For every (timeframe, instrument, direction) of ``analysis == "smt_cisd"``,
  ``bucket == "w/ SMT"``, emits the before vs after rate/n and the delta
  (``rate_delta_pp`` in percentage points, ``n_delta`` in raw count) — the
  invalidation fix's visible impact on the previously-published rate (D-09).
- Appends after-only rows for the new buckets the fix introduces
  (``expired SMT``, ``w/ SMT & survived``, ``w/ SMT & broke``) with their
  after rate/n (before columns blank — these buckets did not exist pre-fix).

Also enforces the D-09a behavior-preservation invariant: every non-``smt*``
analysis row must be byte-value identical before vs after the regen. Any
drift there is a bug to investigate, never silently republished — the script
prints the offending rows and exits non-zero if the non-smt drift check
finds anything.

Usage::

    python3 scripts/build_smt_invalidation_report.py
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

BEFORE_DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery_before_smt_fix.csv"
AFTER_DISCOVERY_MANIFEST_PATH  = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
REPORT_PATH                    = REPO_ROOT / "output" / "smt_invalidation_report.csv"

# ── Merge keys / new-bucket vocabulary ────────────────────────────────────────

_MERGE_KEYS   = ["timeframe", "instrument", "direction"]
_NEW_BUCKETS  = ["expired SMT", "w/ SMT & survived", "w/ SMT & broke"]
_REPORT_COLS  = [
    "analysis", "timeframe", "instrument", "direction", "bucket",
    "before_rate", "before_n", "after_rate", "after_n",
    "rate_delta_pp", "n_delta",
]


# ── Before/after w/ SMT deltas + new-bucket after-rates (D-09) ───────────────

def build_smt_invalidation_rows(before_df: pd.DataFrame, after_df: pd.DataFrame) -> list[dict]:
    """Return before/after w/ SMT delta rows plus after-only new-bucket rows."""
    before_w = before_df[
        (before_df["analysis"] == "smt_cisd") & (before_df["bucket"] == "w/ SMT")
    ][_MERGE_KEYS + ["rate", "n"]].rename(columns={"rate": "before_rate", "n": "before_n"})
    after_w = after_df[
        (after_df["analysis"] == "smt_cisd") & (after_df["bucket"] == "w/ SMT")
    ][_MERGE_KEYS + ["rate", "n"]].rename(columns={"rate": "after_rate", "n": "after_n"})

    merged = before_w.merge(after_w, on=_MERGE_KEYS, how="outer")
    merged["analysis"] = "smt_cisd"
    merged["bucket"]   = "w/ SMT"
    merged["rate_delta_pp"] = merged.apply(
        lambda r: round((r["after_rate"] - r["before_rate"]) * 100, 1)
        if pd.notna(r["after_rate"]) and pd.notna(r["before_rate"]) else pd.NA,
        axis=1,
    )
    merged["n_delta"] = merged.apply(
        lambda r: int(r["after_n"] - r["before_n"])
        if pd.notna(r["after_n"]) and pd.notna(r["before_n"]) else pd.NA,
        axis=1,
    )
    rows = merged[_REPORT_COLS].to_dict(orient="records")

    for bucket in _NEW_BUCKETS:
        after_bucket = after_df[
            (after_df["analysis"] == "smt_cisd") & (after_df["bucket"] == bucket)
        ]
        for _, r in after_bucket.iterrows():
            rows.append({
                "analysis":      "smt_cisd",
                "timeframe":     r["timeframe"],
                "instrument":    r["instrument"],
                "direction":     r["direction"],
                "bucket":        bucket,
                "before_rate":   pd.NA,
                "before_n":      pd.NA,
                "after_rate":    r["rate"],
                "after_n":       r["n"],
                "rate_delta_pp": pd.NA,
                "n_delta":       pd.NA,
            })

    return rows


# ── Non-smt behavior-preservation drift check (D-09a) ─────────────────────────

def build_non_smt_drift(before_df: pd.DataFrame, after_df: pd.DataFrame) -> list[dict]:
    """Return the non-smt_* rows whose rate or n changed between before and after."""
    keys = ["analysis", "timeframe", "instrument", "direction", "bucket"]

    before_non_smt = before_df[~before_df["analysis"].str.startswith("smt")]
    after_non_smt  = after_df[~after_df["analysis"].str.startswith("smt")]

    merged = before_non_smt[keys + ["rate", "n"]].rename(
        columns={"rate": "before_rate", "n": "before_n"},
    ).merge(
        after_non_smt[keys + ["rate", "n"]].rename(
            columns={"rate": "after_rate", "n": "after_n"},
        ),
        on=keys,
        how="outer",
    )

    drifted = merged[
        (merged["before_rate"] != merged["after_rate"])
        | (merged["before_n"] != merged["after_n"])
    ]
    return drifted.to_dict(orient="records")


# ── Entry point: read manifests, write report, enforce drift gate ───────────

def build_report() -> int:
    """Read the before/after manifests, write the report, and enforce D-09a. Return exit code."""
    for label, path in (
        ("before", BEFORE_DISCOVERY_MANIFEST_PATH),
        ("after",  AFTER_DISCOVERY_MANIFEST_PATH),
    ):
        if not path.exists():
            print(f"[error] {label} discovery manifest not found: {path}")
            return 1

    before_df = pd.read_csv(BEFORE_DISCOVERY_MANIFEST_PATH)
    after_df  = pd.read_csv(AFTER_DISCOVERY_MANIFEST_PATH)

    rows = build_smt_invalidation_rows(before_df, after_df)
    report_df = pd.DataFrame(rows, columns=_REPORT_COLS)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(REPORT_PATH, index=False)
    print(f"[ok] wrote {REPORT_PATH} ({len(report_df)} rows)")

    drift = build_non_smt_drift(before_df, after_df)
    if drift:
        print(
            f"[error] non-smt drift detected in {len(drift)} row(s) — this is a bug to "
            "investigate (D-09a), never silently republish:"
        )
        for row in drift:
            print(f"        {row}")
        return 1

    print("[ok] non-smt drift check clean — all non-smt_* rows unchanged (D-09a)")
    return 0


if __name__ == "__main__":
    sys.exit(build_report())
