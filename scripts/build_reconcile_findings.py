"""Reconciler — merge discovery + OOS manifests into a labeled findings table.

Reads ``output/validation_manifest_discovery.csv`` and
``output/validation_manifest_oos.csv`` (produced by ``build_validation.py``),
performs an outer merge on the five bucket keys so no bucket is ever silently
dropped (D-06), applies ``determine_verdict`` per row (D-01/D-02/D-03), and
writes ``output/validation_findings.csv`` with the 12-column D-09 schema:

    analysis, timeframe, instrument, direction, bucket,
    discovery_rate, discovery_n, discovery_ci_low, discovery_ci_high,
    oos_rate, oos_n, verdict

Verdict tokens (D-03):
    ``confirmed``     — discovery_n >= MIN_N and OOS rate on same side of 0.50
    ``not-confirmed`` — discovery_n >= MIN_N but OOS rate absent or wrong side
    ``below-n``       — discovery_n < MIN_N (eligibility gate on discovery only)

Usage::

    python3 scripts/build_reconcile_findings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import MIN_N

# ── Path constants (patched in unit tests via patch.object) ───────────────────

DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
OOS_MANIFEST_PATH       = REPO_ROOT / "output" / "validation_manifest_oos.csv"
FINDINGS_PATH           = REPO_ROOT / "output" / "validation_findings.csv"

# ── Merge keys ────────────────────────────────────────────────────────────────

_MERGE_KEYS = ["analysis", "timeframe", "instrument", "direction", "bucket"]

# ── Output column order (D-09) ────────────────────────────────────────────────

_OUTPUT_COLS = [
    "analysis", "timeframe", "instrument", "direction", "bucket",
    "discovery_rate", "discovery_n", "discovery_ci_low", "discovery_ci_high",
    "oos_rate", "oos_n", "verdict",
]


# ── Verdict logic (D-01 / D-02 / D-03) ───────────────────────────────────────

def _side(r: float) -> int:
    """Return 1 if r > 0.50, -1 if r < 0.50, 0 if r == 0.50 exactly.

    Exact 0.50 is treated as neither side — no directional evidence.
    """
    if r > 0.50:
        return 1
    if r < 0.50:
        return -1
    return 0  # exact tie — neither side


def determine_verdict(
    discovery_rate: float,
    discovery_n: float | None,
    oos_rate: float,
    oos_n: float | None,
) -> str:
    """Return a lowercase verdict token for one bucket row.

    Parameters
    ----------
    discovery_rate:
        Barrier-hit rate on the discovery slice (proportion in [0, 1]).
    discovery_n:
        Sample size on the discovery slice. May be NaN or None.
    oos_rate:
        Barrier-hit rate on the OOS slice. May be NaN when absent.
    oos_n:
        Sample size on the OOS slice. May be NaN, None, or 0 when absent.

    Returns
    -------
    str
        One of ``"confirmed"``, ``"not-confirmed"``, or ``"below-n"``.

    Notes
    -----
    D-01: Eligibility is gated on discovery_n >= MIN_N only.
    D-02: Confirmed iff eligible and OOS rate is on the same side of 0.50.
    D-03: Eligible buckets with no OOS evidence are ``"not-confirmed"``, not
          ``"below-n"``. ``"below-n"`` is reserved for discovery_n < MIN_N.
    """
    # D-01: eligibility gate — discovery sample size
    if pd.isna(discovery_n) or float(discovery_n) < MIN_N:
        return "below-n"

    # D-03 / D-02: eligible bucket — check OOS evidence
    if pd.isna(oos_n) or float(oos_n) == 0 or pd.isna(oos_rate):
        # Eligible bucket with no OOS data => not-confirmed, never below-n
        return "not-confirmed"

    # D-02: confirmed iff both rates are on the same non-boundary side of 0.50.
    # Exact 0.50 (_side == 0) counts as no directional evidence — not-confirmed.
    if _side(discovery_rate) != 0 and _side(oos_rate) != 0 and _side(discovery_rate) == _side(oos_rate):
        return "confirmed"
    return "not-confirmed"


def determine_geo_verdict(
    discovery_geo_verdict: object,
    discovery_geo_lift: float,
    oos_geo_lift: float,
    oos_geo_n: float | None,
) -> str:
    """OOS verdict on the corridor-position null (quick task 260929-mkg).

    Only buckets that passed the discovery geo gate (BH-corrected, geo_n >=
    MIN_N, verdict above-/below-baseline) are eligible. Confirmed iff the OOS
    slice carries >= MIN_N baselined events and its lift has the same
    non-zero sign. Non-eligible buckets pass their discovery geo_verdict
    through unchanged ("not-significant", "below-n", "diagnostic", ...).
    """
    if pd.isna(discovery_geo_verdict):
        return "no-baseline"
    verdict = str(discovery_geo_verdict)
    if verdict not in ("above-baseline", "below-baseline"):
        return verdict
    if pd.isna(oos_geo_n) or float(oos_geo_n) < MIN_N or pd.isna(oos_geo_lift) or oos_geo_lift == 0:
        return "not-confirmed"
    if (float(discovery_geo_lift) > 0) == (float(oos_geo_lift) > 0):
        return "confirmed"
    return "not-confirmed"


# ── Reconciliation ────────────────────────────────────────────────────────────

def reconcile() -> None:
    """Read both manifests, merge, apply verdicts, and write validation_findings.csv.

    Columns selected from the discovery manifest:
        rate -> discovery_rate, n -> discovery_n,
        ci_low -> discovery_ci_low, ci_high -> discovery_ci_high

    Columns selected from the OOS manifest:
        rate -> oos_rate, n -> oos_n

    The merge is ``how="outer"`` so buckets that appear in only one slice are
    still emitted (D-06 — never drop). Missing counterparts produce NaN values
    in the numeric columns, which ``determine_verdict`` handles correctly.
    """
    if not DISCOVERY_MANIFEST_PATH.exists():
        print(f"[error] discovery manifest not found: {DISCOVERY_MANIFEST_PATH}")
        print("Run `python3 scripts/build_validation.py` (discovery) first.")
        sys.exit(1)
    if not OOS_MANIFEST_PATH.exists():
        print(f"[error] OOS manifest not found: {OOS_MANIFEST_PATH}")
        print("Run `python3 scripts/build_validation.py --oos` before reconciling.")
        sys.exit(1)
    disc = pd.read_csv(DISCOVERY_MANIFEST_PATH)
    oos  = pd.read_csv(OOS_MANIFEST_PATH)

    # Select and rename discovery columns
    disc_cols = _MERGE_KEYS + ["rate", "n", "ci_low", "ci_high"]
    disc_sel  = disc[disc_cols].rename(columns={
        "rate":   "discovery_rate",
        "n":      "discovery_n",
        "ci_low": "discovery_ci_low",
        "ci_high": "discovery_ci_high",
    })

    # Select and rename OOS columns
    oos_cols = _MERGE_KEYS + ["rate", "n"]
    oos_sel  = oos[oos_cols].rename(columns={
        "rate": "oos_rate",
        "n":    "oos_n",
    })

    # Outer merge — preserves every bucket from either slice (D-06)
    merged = disc_sel.merge(oos_sel, on=_MERGE_KEYS, how="outer")

    # Apply verdict per row
    merged["verdict"] = merged.apply(
        lambda row: determine_verdict(
            row["discovery_rate"],
            row["discovery_n"],
            row["oos_rate"],
            row["oos_n"],
        ),
        axis=1,
    )

    # Corridor-position null (quick task 260929-mkg): additive columns, only
    # when both manifests carry them (older manifests reconcile unchanged).
    output_cols = list(_OUTPUT_COLS)
    if {"geo_lift", "geo_verdict"} <= set(disc.columns) and {"geo_lift", "geo_n"} <= set(oos.columns):
        geo = disc[_MERGE_KEYS + ["geo_lift", "geo_verdict"]].rename(columns={
            "geo_lift": "discovery_geo_lift", "geo_verdict": "discovery_geo_verdict"})
        geo = geo.merge(
            oos[_MERGE_KEYS + ["geo_lift", "geo_n"]].rename(columns={
                "geo_lift": "oos_geo_lift", "geo_n": "oos_geo_n"}),
            on=_MERGE_KEYS, how="outer")
        merged = merged.merge(geo, on=_MERGE_KEYS, how="left")
        merged["geo_verdict"] = merged.apply(
            lambda row: determine_geo_verdict(
                row["discovery_geo_verdict"], row["discovery_geo_lift"],
                row["oos_geo_lift"], row["oos_geo_n"],
            ),
            axis=1,
        )
        output_cols += ["discovery_geo_lift", "discovery_geo_verdict",
                        "oos_geo_lift", "oos_geo_n", "geo_verdict"]

    # Enforce D-09 column order
    result = merged[output_cols]

    # Write output
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(FINDINGS_PATH, index=False)

    # Summary print
    verdict_counts = result["verdict"].value_counts()
    total          = len(result)
    print(f"[ok] wrote {FINDINGS_PATH} ({total} rows)")
    for verdict, count in verdict_counts.items():
        print(f"     {verdict:20s}: {count}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reconcile()
