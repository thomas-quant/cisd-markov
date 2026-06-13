"""Discovery-slice review report — per-finding rate, n, CI, and OOS-eligible Y/N.

Reads ``output/validation_manifest_discovery.csv`` (written by ``build_validation.py``
on a default discovery run) and renders a per-analysis review report so the researcher
can make a go/no-go decision before spending the one sacred OOS evaluation.

Outputs:
  * output/discovery_summary.md  -- full per-analysis table (human review artifact)
  * stdout                       -- condensed one-line-per-OOS-eligible-bucket summary
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cisd_analysis import ANALYSES

MANIFEST_PATH = REPO_ROOT / "output" / "validation_manifest_discovery.csv"
SUMMARY_PATH  = REPO_ROOT / "output" / "discovery_summary.md"

# Ordered list of analysis keys (matches ANALYSES registry order)
_ANALYSIS_ORDER = list(ANALYSES.keys())


# ── Formatting helpers ────────────────────────────────────────────────────────

def _pct(value: float) -> str:
    """Format a proportion in [0, 1] as a 1-decimal percent string."""
    return f"{value * 100:.1f}%"


def _ci_str(ci_low: float, ci_high: float) -> str:
    """Format a Wilson CI pair as a bracket string, e.g. '[45.2–67.8%]'."""
    return f"[{ci_low * 100:.1f}–{ci_high * 100:.1f}%]"


# ── Report builder ────────────────────────────────────────────────────────────

def render_markdown(df: pd.DataFrame) -> str:
    """Render the per-analysis discovery report as Markdown.

    Each analysis gets a section header and a table with columns:
    Timeframe | Instrument | Direction | Bucket | Rate | N | 95% CI | OOS-eligible

    When an analysis has no buckets with min_n_pass == True, a note is printed
    instead of an empty table so the section is never silently dropped (D-08).
    """
    lines: list[str] = []
    lines.append("# Discovery-Slice Review Report")
    lines.append("")
    lines.append(
        "Produced by `scripts/build_discovery_summary.py` from"
        " `output/validation_manifest_discovery.csv`."
    )
    lines.append(
        "OOS-eligible = Y when n >= 50 on the discovery slice (D-01)."
        " Rates are discovery-slice only (no OOS data has been spent)."
    )
    lines.append("")

    # Use ANALYSES order; fall back to sorted for any analysis not in registry
    known   = [k for k in _ANALYSIS_ORDER if k in df["analysis"].unique()]
    unknown = sorted(set(df["analysis"].unique()) - set(_ANALYSIS_ORDER))
    all_keys = known + unknown

    eligible_total = 0

    for key in all_keys:
        label = ANALYSES[key][0] if key in ANALYSES else key
        lines.append(f"## {key}: {label}")
        lines.append("")

        subset = df[df["analysis"] == key].copy()
        # Sort for stable output: TF order, instrument, direction, bucket
        tf_order = {"Daily": 0, "4H": 1, "1H": 2, "15min": 3}
        subset["_tf_ord"] = subset["timeframe"].map(tf_order).fillna(99)
        subset = subset.sort_values(["_tf_ord", "instrument", "direction", "bucket"])
        subset = subset.drop(columns=["_tf_ord"])

        n_eligible = int(subset["min_n_pass"].sum())
        eligible_total += n_eligible

        if len(subset) == 0:
            lines.append("no reportable findings (all buckets below n=50)")
            lines.append("")
            continue

        lines.append(
            "| Timeframe | Instrument | Direction | Bucket |"
            " Rate | N | 95% CI | OOS-eligible |"
        )
        lines.append("|---|---|---|---|---:|---:|---|:---:|")

        for _, row in subset.iterrows():
            oos_flag = "Y" if row["min_n_pass"] else "N"
            lines.append(
                f"| {row['timeframe']} | {row['instrument']} | {row['direction']}"
                f" | {row['bucket']}"
                f" | {_pct(row['rate'])}"
                f" | {int(row['n']):,}"
                f" | {_ci_str(row['ci_low'], row['ci_high'])}"
                f" | {oos_flag} |"
            )

        if n_eligible == 0:
            lines.append("")
            lines.append("no reportable findings (all buckets below n=50)")

        lines.append("")

    lines.append(f"---")
    lines.append(f"*Total OOS-eligible buckets: {eligible_total}*")
    lines.append("")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not MANIFEST_PATH.exists():
        print(
            f"[error] manifest not found: {MANIFEST_PATH}\n"
            "Run `python3 scripts/build_validation.py` (discovery run) first."
        )
        sys.exit(1)

    df = pd.read_csv(MANIFEST_PATH)

    # Keep only discovery rows (guard against mixed manifests)
    df = df[df["slice"] == "discovery"].copy()

    if len(df) == 0:
        print("[warn] manifest contains no discovery rows — nothing to report")
        sys.exit(0)

    # Write full Markdown report
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    md_text = render_markdown(df)
    SUMMARY_PATH.write_text(md_text)
    print(f"[ok] wrote {SUMMARY_PATH}")

    # Condensed stdout: one line per OOS-eligible bucket
    eligible = df[df["min_n_pass"] == True].copy()  # noqa: E712
    if len(eligible) == 0:
        print("[warn] no OOS-eligible buckets found (all n < 50)")
        return

    print(f"\n[ok] OOS-eligible buckets ({len(eligible)} total):")
    for _, row in eligible.iterrows():
        print(
            f"  {row['analysis']:25s}  {row['timeframe']:6s}  {row['instrument']:2s}"
            f"  {row['direction']:8s}  {row['bucket']:30s}"
            f"  {_pct(row['rate']):6s}  n={int(row['n']):,}"
            f"  CI={_ci_str(row['ci_low'], row['ci_high'])}"
        )


if __name__ == "__main__":
    main()
