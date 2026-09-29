"""Build corrected-bar verdicts for the two post-CISD studies.

    python3 scripts/build_post_cisd_verdict.py             # old OOS slice
    python3 scripts/build_post_cisd_verdict.py --holdout   # fresh holdout ->
                                          # post_cisd_verdict_holdout*.csv

Legacy (0.5-null) verdicts and rollups use per-instrument rows only; geo
verdicts and the geo rollup use pooled NQ+ES rows only.
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
from scripts.build_reconcile_findings import _side
from scripts.build_validation import POOLED


# ── Path constants (patched in unit tests via patch.object) ──────────────────

DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
OOS_MANIFEST_PATH       = REPO_ROOT / "output" / "validation_manifest_oos.csv"
WALKFORWARD_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_walkforward.csv"
VERDICT_BUCKETS_PATH    = REPO_ROOT / "output" / "post_cisd_verdict.csv"
VERDICT_ROLLUP_PATH     = REPO_ROOT / "output" / "post_cisd_verdict_rollup.csv"
HOLDOUT_MANIFEST_PATH   = REPO_ROOT / "output" / "validation_manifest_holdout.csv"
HOLDOUT_BUCKETS_PATH    = REPO_ROOT / "output" / "post_cisd_verdict_holdout.csv"
HOLDOUT_ROLLUP_PATH     = REPO_ROOT / "output" / "post_cisd_verdict_holdout_rollup.csv"

POST_CISD_ANALYSES = ("post_cisd_context", "candle1_followthrough")

_MERGE_KEYS = ["analysis", "timeframe", "instrument", "direction", "bucket"]
_BUCKET_OUTPUT_COLS = [
    "analysis", "timeframe", "instrument", "direction", "bucket",
    "discovery_rate", "corrected_pass", "wf_verdict", "oos_rate", "oos_n",
    "same_side", "clears_bar",
]
_ROLLUP_OUTPUT_COLS = ["analysis", "tag", "n_buckets", "n_cleared", "verdict"]


# ── Verdict logic (D-02 / D-03) ─────────────────────────────────────────────

def _bucket_clears(
    discovery_rate: float,
    corrected_pass: object,
    wf_verdict: str | None,
    oos_rate: float,
    oos_n: float | None,
) -> bool:
    """Return whether one bucket clears all three corrected evidence gates."""
    if pd.isna(corrected_pass) or not bool(corrected_pass):
        return False
    if wf_verdict != "wf-robust":
        return False
    if pd.isna(oos_n) or float(oos_n) == 0 or pd.isna(oos_rate):
        return False

    discovery_side = _side(discovery_rate)
    return bool(discovery_side != 0 and discovery_side == _side(oos_rate))


def _bucket_clears_geo(
    geo_verdict: object,
    discovery_geo_lift: float,
    geo_wf_verdict: object,
    oos_geo_lift: float,
    oos_geo_n: float | None,
) -> bool:
    """Corridor-position null version of _bucket_clears (quick task 260929-mkg):
    discovery geo_verdict above-/below-baseline (BH-corrected, geo_n >= MIN_N),
    geo walk-forward wf-robust, and an OOS lift of the same non-zero sign on
    effective n (geo_n_eff; geo_n on older manifests) >= MIN_N. Diagnostic buckets never clear."""
    if pd.isna(geo_verdict) or str(geo_verdict) not in ("above-baseline", "below-baseline"):
        return False
    if geo_wf_verdict != "wf-robust":
        return False
    if pd.isna(oos_geo_n) or float(oos_geo_n) < MIN_N or pd.isna(oos_geo_lift) or oos_geo_lift == 0:
        return False
    return (float(discovery_geo_lift) > 0) == (float(oos_geo_lift) > 0)


def rollup_by_tag(bucket_rows: list[dict], flag: str = "clears_bar") -> list[dict]:
    """Roll bucket verdicts up by analysis and tag using a strict majority."""
    grouped: dict[tuple[object, object], list[object]] = {}
    for row in bucket_rows:
        key = (row["analysis"], row["bucket"])
        grouped.setdefault(key, []).append(row[flag])

    rollups: list[dict] = []
    for (analysis, tag), clears_flags in sorted(grouped.items()):
        n_buckets = len(clears_flags)
        n_cleared = sum(
            1 for flag in clears_flags
            if not pd.isna(flag) and bool(flag)
        )
        rollups.append({
            "analysis": analysis,
            "tag": tag,
            "n_buckets": n_buckets,
            "n_cleared": n_cleared,
            "verdict": "cleared" if n_cleared > n_buckets / 2 else "not-cleared",
        })
    return rollups


# ── Three-manifest verdict build (D-01 / D-09) ──────────────────────────────

def build_verdict() -> None:
    """Read the three manifests and write bucket and tag corrected verdicts."""
    manifest_paths = (
        ("discovery", DISCOVERY_MANIFEST_PATH),
        ("OOS", OOS_MANIFEST_PATH),
        ("walk-forward", WALKFORWARD_MANIFEST_PATH),
    )
    for label, path in manifest_paths:
        if not path.exists():
            print(f"[error] {label} manifest not found: {path}")
            sys.exit(1)

    disc = pd.read_csv(DISCOVERY_MANIFEST_PATH)
    oos  = pd.read_csv(OOS_MANIFEST_PATH)
    wf   = pd.read_csv(WALKFORWARD_MANIFEST_PATH)

    # D-01 blast-radius containment: filter every input before verdict logic.
    disc = disc[disc["analysis"].isin(POST_CISD_ANALYSES)].copy()
    oos  = oos[oos["analysis"].isin(POST_CISD_ANALYSES)].copy()
    wf   = wf[wf["analysis"].isin(POST_CISD_ANALYSES)].copy()

    disc_sel = disc[_MERGE_KEYS + ["rate", "corrected_pass"]].rename(
        columns={"rate": "discovery_rate"},
    )
    oos_sel = oos[_MERGE_KEYS + ["rate", "n"]].rename(
        columns={"rate": "oos_rate", "n": "oos_n"},
    )
    wf_sel = wf[_MERGE_KEYS + ["wf_verdict"]].drop_duplicates(
        subset=_MERGE_KEYS,
        keep="first",
    )

    merged = disc_sel.merge(oos_sel, on=_MERGE_KEYS, how="outer")
    merged = merged.merge(wf_sel, on=_MERGE_KEYS, how="outer")

    merged["same_side"] = merged.apply(
        lambda row: bool(
            not pd.isna(row["oos_n"])
            and float(row["oos_n"]) != 0
            and not pd.isna(row["oos_rate"])
            and _side(row["discovery_rate"]) != 0
            and _side(row["discovery_rate"]) == _side(row["oos_rate"])
        ),
        axis=1,
    )
    merged["clears_bar"] = merged.apply(
        lambda row: _bucket_clears(
            row["discovery_rate"],
            row["corrected_pass"],
            row["wf_verdict"],
            row["oos_rate"],
            row["oos_n"],
        ),
        axis=1,
    )
    bucket_cols = list(_BUCKET_OUTPUT_COLS)
    rollup_cols = list(_ROLLUP_OUTPUT_COLS)
    has_geo = ({"geo_verdict", "geo_lift"} <= set(disc.columns)
               and {"geo_lift", "geo_n"} <= set(oos.columns) and "geo_wf_verdict" in wf.columns)
    if has_geo:
        # Gate the OOS side on effective n when the manifest carries it.
        n_col = "geo_n_eff" if "geo_n_eff" in oos.columns else "geo_n"
        geo = disc[_MERGE_KEYS + ["geo_verdict", "geo_lift"]].rename(columns={"geo_lift": "discovery_geo_lift"})
        geo = geo.merge(oos[_MERGE_KEYS + ["geo_lift", n_col]].rename(
            columns={"geo_lift": "oos_geo_lift", n_col: f"oos_{n_col}"}), on=_MERGE_KEYS, how="outer")
        geo = geo.merge(wf[_MERGE_KEYS + ["geo_wf_verdict"]].drop_duplicates(subset=_MERGE_KEYS),
                        on=_MERGE_KEYS, how="outer")
        merged = merged.merge(geo, on=_MERGE_KEYS, how="left")
        merged["geo_clears_bar"] = merged.apply(
            lambda row: _bucket_clears_geo(
                row["geo_verdict"], row["discovery_geo_lift"], row["geo_wf_verdict"],
                row["oos_geo_lift"], row[f"oos_{n_col}"],
            ),
            axis=1,
        )
        bucket_cols += ["geo_verdict", "discovery_geo_lift", "geo_wf_verdict",
                        "oos_geo_lift", f"oos_{n_col}", "geo_clears_bar"]
    bucket_result = merged[bucket_cols]

    pooled = bucket_result["instrument"] == POOLED
    rollup_rows = rollup_by_tag(bucket_result[~pooled].to_dict(orient="records"))
    rollup_result = pd.DataFrame(rollup_rows, columns=_ROLLUP_OUTPUT_COLS)
    if has_geo:
        geo_rollup = pd.DataFrame(
            rollup_by_tag(bucket_result[pooled].to_dict(orient="records"), flag="geo_clears_bar"),
            columns=_ROLLUP_OUTPUT_COLS,
        ).rename(columns={"n_buckets": "geo_n_buckets", "n_cleared": "geo_n_cleared",
                          "verdict": "geo_verdict"})
        rollup_result = rollup_result.merge(geo_rollup, on=["analysis", "tag"], how="outer")
        rollup_cols += ["geo_n_buckets", "geo_n_cleared", "geo_verdict"]
    rollup_result = rollup_result[rollup_cols]

    VERDICT_BUCKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_ROLLUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    bucket_result.to_csv(VERDICT_BUCKETS_PATH, index=False)
    rollup_result.to_csv(VERDICT_ROLLUP_PATH, index=False)

    print(f"[ok] wrote {VERDICT_BUCKETS_PATH} ({len(bucket_result)} rows)")
    print(f"[ok] wrote {VERDICT_ROLLUP_PATH} ({len(rollup_result)} rows)")
    for verdict, count in rollup_result["verdict"].value_counts().items():
        print(f"     {verdict:20s}: {count}")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--holdout" in sys.argv[1:]:
        OOS_MANIFEST_PATH    = HOLDOUT_MANIFEST_PATH
        VERDICT_BUCKETS_PATH = HOLDOUT_BUCKETS_PATH
        VERDICT_ROLLUP_PATH  = HOLDOUT_ROLLUP_PATH
    build_verdict()
