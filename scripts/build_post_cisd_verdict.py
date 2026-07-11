"""Build corrected-bar verdicts for the two post-CISD studies."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_reconcile_findings import _side


# ── Path constants (patched in unit tests via patch.object) ──────────────────

DISCOVERY_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
OOS_MANIFEST_PATH       = REPO_ROOT / "output" / "validation_manifest_oos.csv"
WALKFORWARD_MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_walkforward.csv"
VERDICT_BUCKETS_PATH    = REPO_ROOT / "output" / "post_cisd_verdict.csv"
VERDICT_ROLLUP_PATH     = REPO_ROOT / "output" / "post_cisd_verdict_rollup.csv"

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


def rollup_by_tag(bucket_rows: list[dict]) -> list[dict]:
    """Roll bucket verdicts up by analysis and tag using a strict majority."""
    grouped: dict[tuple[object, object], list[object]] = {}
    for row in bucket_rows:
        key = (row["analysis"], row["bucket"])
        grouped.setdefault(key, []).append(row["clears_bar"])

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
    bucket_result = merged[_BUCKET_OUTPUT_COLS]

    rollup_rows = rollup_by_tag(bucket_result.to_dict(orient="records"))
    rollup_result = pd.DataFrame(rollup_rows, columns=_ROLLUP_OUTPUT_COLS)

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
    build_verdict()
