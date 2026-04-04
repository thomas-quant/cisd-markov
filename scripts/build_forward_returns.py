from __future__ import annotations

import json
from copy import deepcopy
from html import escape as html_escape
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from cisd_analysis import INSTRUMENTS, TIMEFRAMES, load_1m, prepare_pair, MAX_CONSEC, _count_consecutive

FORWARD_RETURNS_LOOKAHEAD = 7
PERCENTILE_LEVELS = [5, 25, 50, 75, 95]
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "output" / "forward_returns.html"

DEFAULT_STATE = {
    "tf": next(iter(TIMEFRAMES)),
    "family": "core",
    "core": {"smt": "all", "size_cross": "all", "wick": "all", "consec": "all"},
    "fvg": {"fvg_bucket": "all", "fvg_mode": "all", "fvg_state": "all"},
    "structure": {"sweep": "all", "prev_swing": "all", "cisd_swing": "all"},
}


def core_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["smt"], state["size_cross"], state["wick"], state["consec"]])


def fvg_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["fvg_bucket"], state["fvg_mode"], state["fvg_state"]])


def structure_combo_key(state: dict[str, str]) -> str:
    return "|".join([state["sweep"], state["prev_swing"], state["cisd_swing"]])


COMBO_KEY_BUILDERS = {
    "core": core_combo_key,
    "fvg": fvg_combo_key,
    "structure": structure_combo_key,
}


def percentile_payload(series: pd.Series) -> dict[str, float] | None:
    if series.empty:
        return None
    values = series.to_numpy(dtype=float)
    return {str(level): float(np.percentile(values, level)) for level in PERCENTILE_LEVELS}


def _ensure_column(frame: pd.DataFrame, column: str, default) -> None:
    if column not in frame.columns:
        frame[column] = default


def _classify_wick(prepared: pd.DataFrame, idx: int, cisd_type: str) -> str:
    row = prepared.iloc[idx]
    if cisd_type == "bullish":
        return "past_wick" if row["close"] > row["prev_high"] else "within_wick"
    if cisd_type == "bearish":
        return "past_wick" if row["close"] < row["prev_low"] else "within_wick"
    return "all"


def _classify_size_cross(prepared: pd.DataFrame, idx: int, atr_series: pd.Series) -> str:
    atr = atr_series.iloc[idx]
    if pd.isna(atr) or atr <= 0:
        return "all"

    row = prepared.iloc[idx]
    prev_row = prepared.iloc[idx - 1] if idx > 0 else None
    cisd_big = abs(row["close"] - row["open"]) >= atr
    prev_big = bool(prev_row is not None and abs(prev_row["close"] - prev_row["open"]) >= atr)

    if cisd_big and not prev_big:
        return "Big CISD / Small prev"
    if cisd_big and prev_big:
        return "Big CISD / Big prev"
    if not cisd_big and not prev_big:
        return "Small CISD / Small prev"
    return "Small CISD / Big prev"


def build_forward_return_rows(prepared: pd.DataFrame, instrument: str) -> pd.DataFrame:
    rows = prepared[prepared["cisd_type"].notna()].copy()

    for column, default in (
        ("swing_smt_tag", "no SMT"),
        ("has_dir_fvg_mid0", False),
        ("has_dir_fvg_mid1", False),
        ("fvg_mid0_hold_close_near", "none"),
        ("fvg_mid1_hold_close_near", "none"),
        ("fvg_mid0_hold_wick_far", "none"),
        ("fvg_mid1_hold_wick_far", "none"),
        ("has_dir_sweep", False),
        ("prev_bar_is_dir_swing", False),
        ("cisd_bar_is_dir_swing", False),
    ):
        _ensure_column(rows, column, default)

    rows["instrument"] = instrument
    rows["smt"] = rows["swing_smt_tag"]
    rows["size_cross"] = "all"
    rows["wick"] = "all"
    rows["consec"] = "all"

    rows["fvg_bucket"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        ["mid0", "mid1"],
        default="no_fvg",
    )
    rows["fvg_state_close_through_near_edge"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_close_near"], rows["fvg_mid1_hold_close_near"]],
        default="none",
    )
    rows["fvg_state_wick_break_far_extreme"] = np.select(
        [rows["has_dir_fvg_mid0"], rows["has_dir_fvg_mid1"]],
        [rows["fvg_mid0_hold_wick_far"], rows["fvg_mid1_hold_wick_far"]],
        default="none",
    )
    rows["sweep"] = np.where(rows["has_dir_sweep"], "w/ sweep", "no sweep")
    rows["prev_swing"] = np.where(rows["prev_bar_is_dir_swing"], "yes", "no")
    rows["cisd_swing"] = np.where(rows["cisd_bar_is_dir_swing"], "yes", "no")

    atr_series = (prepared["high"] - prepared["low"]).rolling(14).mean()
    directions = prepared["direction"] if "direction" in prepared.columns else pd.Series(index=prepared.index, dtype=object)
    for ts, row in rows.iterrows():
        idx = prepared.index.get_loc(ts)
        rows.at[ts, "size_cross"] = _classify_size_cross(prepared, idx, atr_series)
        rows.at[ts, "wick"] = _classify_wick(prepared, idx, row["cisd_type"])
        opposite = "bearish" if row["cisd_type"] == "bullish" else "bullish"
        rows.at[ts, "consec"] = str(_count_consecutive(idx, directions, opposite, MAX_CONSEC))

    future_close = prepared["close"].shift(-FORWARD_RETURNS_LOOKAHEAD).reindex(rows.index)
    raw_return = (future_close / rows["close"] - 1.0) * 100.0
    rows["forward_return_pct"] = np.where(rows["cisd_type"] == "bearish", -raw_return, raw_return)
    return rows[rows["forward_return_pct"].notna()].copy()


def apply_family_filters(rows: pd.DataFrame, family: str, state: dict[str, str]) -> pd.DataFrame:
    filtered = rows

    if family == "core":
        for column, key in (("smt", "smt"), ("size_cross", "size_cross"), ("wick", "wick"), ("consec", "consec")):
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered.copy()

    if family == "fvg":
        if state["fvg_bucket"] != "all":
            filtered = filtered[filtered["fvg_bucket"] == state["fvg_bucket"]]
        if state["fvg_mode"] != "all" and state["fvg_state"] != "all":
            filtered = filtered[filtered[f"fvg_state_{state['fvg_mode']}"] == state["fvg_state"]]
        return filtered.copy()

    if family == "structure":
        for column, key in (("sweep", "sweep"), ("prev_swing", "prev_swing"), ("cisd_swing", "cisd_swing")):
            if state[key] != "all":
                filtered = filtered[filtered[column] == state[key]]
        return filtered.copy()

    raise ValueError(f"unknown family: {family}")


def aggregate_family_payload(rows: pd.DataFrame, family: str, state: dict[str, str]) -> dict[str, object]:
    filtered = apply_family_filters(rows, family, state)
    return {"n": int(len(filtered)), "data": percentile_payload(filtered["forward_return_pct"])}


def build_config() -> dict[str, object]:
    return {
        "forward_horizon": FORWARD_RETURNS_LOOKAHEAD,
        "default_state": DEFAULT_STATE,
        "timeframes": [{"value": tf, "label": tf} for tf in TIMEFRAMES],
        "families": {
            "core": {
                "label": "Core",
                "dimensions": {
                    "smt": {
                        "label": "SMT",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "w/ SMT", "label": "w/ SMT"},
                            {"value": "no SMT", "label": "no SMT"},
                        ],
                    },
                    "size_cross": {
                        "label": "Size x Prev",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "Big CISD / Small prev", "label": "Big / Small"},
                            {"value": "Big CISD / Big prev", "label": "Big / Big"},
                            {"value": "Small CISD / Small prev", "label": "Small / Small"},
                            {"value": "Small CISD / Big prev", "label": "Small / Big"},
                        ],
                    },
                    "wick": {
                        "label": "Wick",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "past_wick", "label": "Past wick"},
                            {"value": "within_wick", "label": "Within wick"},
                        ],
                    },
                    "consec": {
                        "label": "Consec",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "1", "label": "1"},
                            {"value": "2", "label": "2"},
                            {"value": "3", "label": "3"},
                        ],
                    },
                },
            },
            "fvg": {
                "label": "FVG",
                "dimensions": {
                    "fvg_bucket": {
                        "label": "Bucket",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "mid0", "label": "mid0"},
                            {"value": "mid1", "label": "mid1"},
                            {"value": "no_fvg", "label": "no_fvg"},
                        ],
                    },
                    "fvg_mode": {
                        "label": "Mode",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "close_through_near_edge", "label": "close_through_near_edge"},
                            {"value": "wick_break_far_extreme", "label": "wick_break_far_extreme"},
                        ],
                    },
                    "fvg_state": {
                        "label": "State",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "held", "label": "held"},
                            {"value": "failed", "label": "failed"},
                            {"value": "none", "label": "none"},
                        ],
                    },
                },
            },
            "structure": {
                "label": "Structure",
                "dimensions": {
                    "sweep": {
                        "label": "Sweep",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "w/ sweep", "label": "w/ sweep"},
                            {"value": "no sweep", "label": "no sweep"},
                        ],
                    },
                    "prev_swing": {
                        "label": "Prev swing",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "yes", "label": "yes"},
                            {"value": "no", "label": "no"},
                        ],
                    },
                    "cisd_swing": {
                        "label": "CISD swing",
                        "values": [
                            {"value": "all", "label": "All"},
                            {"value": "yes", "label": "yes"},
                            {"value": "no", "label": "no"},
                        ],
                    },
                },
            },
        },
    }


def _iter_family_states(family: str, config: dict[str, object]) -> list[dict[str, str]]:
    dimensions = config["families"][family]["dimensions"]
    names = list(dimensions.keys())
    states: list[dict[str, str]] = []
    for combo in product(*(dimensions[name]["values"] for name in names)):
        states.append({name: option["value"] for name, option in zip(names, combo)})
    return states


def _merge_config(base: dict[str, object], override: dict[str, object] | None) -> dict[str, object]:
    if not override:
        return deepcopy(base)

    merged = deepcopy(base)

    def _merge(target: dict[str, object], source: dict[str, object]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                _merge(target[key], value)
            else:
                target[key] = value

    _merge(merged, override)
    return merged


def build_dataset() -> dict[str, object]:
    config = build_config()
    dfs_1m = {instrument: load_1m(path) for instrument, path in INSTRUMENTS.items()}
    dataset: dict[str, object] = {"timeframes": {}}

    for tf_label, tf_rule in TIMEFRAMES.items():
        df_nq, df_es = prepare_pair(dfs_1m["NQ"], dfs_1m["ES"], tf_rule, with_swing_smt=True)
        rows_by_instrument = {
            "NQ": build_forward_return_rows(df_nq, "NQ"),
            "ES": build_forward_return_rows(df_es, "ES"),
        }

        timeframe_payload = {
            "x_days": list(range(1, FORWARD_RETURNS_LOOKAHEAD + 1)),
            "families": {},
        }

        for family, family_cfg in config["families"].items():
            family_payload = {"label": family_cfg["label"], "charts": {"NQ": {}, "ES": {}}}
            for instrument, rows in rows_by_instrument.items():
                instrument_rows = rows.copy()
                family_payload["charts"][instrument] = {}
                for direction in ("bullish", "bearish"):
                    direction_rows = instrument_rows[instrument_rows["cisd_type"] == direction]
                    combos: dict[str, dict[str, object]] = {}
                    for state in _iter_family_states(family, config):
                        combos[COMBO_KEY_BUILDERS[family](state)] = aggregate_family_payload(direction_rows, family, state)
                    family_payload["charts"][instrument][direction] = combos
            timeframe_payload["families"][family] = family_payload

        dataset["timeframes"][tf_label] = timeframe_payload

    return dataset


def _render_buttons(dim_name: str, dim_cfg: dict[str, object], active_value: str, family_name: str) -> str:
    buttons = []
    for option in dim_cfg["values"]:
        active = " active" if option["value"] == active_value else ""
        buttons.append(
            f'<button class="btn{active}" data-dim="{html_escape(dim_name)}" data-family-panel="{html_escape(family_name)}" '
            f'data-val="{html_escape(option["value"])}">{html_escape(option["label"])}</button>'
        )
    return "".join(buttons)


def _render_family_panel(family: str, family_cfg: dict[str, object], default_state: dict[str, object]) -> str:
    rows = []
    for dim_name, dim_cfg in family_cfg["dimensions"].items():
        rows.append(
            f'<div class="filter-row" data-dim-row="{html_escape(dim_name)}" data-family-panel="{html_escape(family)}">'
            f'<span class="filter-label">{html_escape(dim_cfg["label"])}</span>'
            f'{_render_buttons(dim_name, dim_cfg, default_state[family][dim_name], family)}'
            f"</div>"
        )
    return f'<div class="family-panel" data-family="{html_escape(family)}">{"".join(rows)}</div>'


def render_html(data: dict[str, object], config: dict[str, object]) -> str:
    config = _merge_config(build_config(), config)
    tf_buttons = "".join(
        f'<button class="btn{" active" if idx == 0 else ""}" data-dim="tf" data-val="{html_escape(tf["value"])}">{html_escape(tf["label"])}</button>'
        for idx, tf in enumerate(config["timeframes"])
    )
    family_buttons = "".join(
        f'<button class="btn{" active" if family == config["default_state"]["family"] else ""}" data-dim="family" data-val="{html_escape(family)}">{html_escape(family_cfg["label"])}</button>'
        for family, family_cfg in config["families"].items()
    )
    family_panels = "".join(
        _render_family_panel(family, family_cfg, config["default_state"])
        for family, family_cfg in config["families"].items()
    )

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CISD Forward Returns</title>
  <script src="https://cdn.jsdelivr.net/npm/plotly.js-dist@2.26.0/plotly.min.js" crossorigin="anonymous"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      min-height: 100%;
      background: #0f1117;
      color: #c0c4d0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    }}
    body {{ display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; overflow: hidden; }}
    header {{ display: flex; justify-content: space-between; align-items: baseline; flex-shrink: 0; gap: 12px; }}
    h1 {{ font-size: 14px; font-weight: 600; color: #e0e4f0; }}
    .subtitle {{ font-size: 11px; color: #7a7d90; }}
    .filters {{ display: flex; flex-direction: column; gap: 5px; flex-shrink: 0; }}
    .filter-row {{ display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }}
    .filter-label {{
      font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase;
      color: #555870; width: 72px; flex-shrink: 0; text-align: right; padding-right: 8px;
    }}
    .btn {{
      background: #1a1d27; border: 1px solid #2a2d3d; color: #6a6d80;
      padding: 3px 9px; border-radius: 4px; font-size: 11px;
      font-family: inherit; cursor: pointer;
      transition: border-color 0.1s, color 0.1s, background 0.1s; white-space: nowrap;
    }}
    .btn:hover:not(.active):not(:disabled) {{ border-color: #4a4d60; color: #a0a4b0; }}
    .btn.active {{ background: #1e2235; border-color: #4fc3f7; color: #e0e4f0; }}
    .btn:disabled {{ opacity: 0.45; cursor: not-allowed; }}
    .family-panel {{ display: flex; flex-direction: column; gap: 5px; }}
    .grid {{
      display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
      gap: 8px; flex: 1; min-height: 0;
    }}
    .cell {{ background: #1a1d27; border: 1px solid #2a2d3d; border-radius: 6px; overflow: hidden; }}
  </style>
</head>
<body>
  <header>
    <h1>CISD Forward Returns</h1>
    <span class="subtitle">Positive = CISD was correct | __FORWARD_HORIZON__ bars ahead</span>
  </header>

  <div class="filters">
    <div class="filter-row">
      <span class="filter-label">Timeframe</span>
      __TF_BUTTONS__
    </div>
    <div class="filter-row">
      <span class="filter-label">Family</span>
      __FAMILY_BUTTONS__
    </div>
    __FAMILY_PANELS__
  </div>

  <div class="grid">
    <div class="cell" id="chart-NQ-bullish"></div>
    <div class="cell" id="chart-NQ-bearish"></div>
    <div class="cell" id="chart-ES-bullish"></div>
    <div class="cell" id="chart-ES-bearish"></div>
  </div>

  <script>
  const CONFIG = __CONFIG_JSON__;
  const DATA = __DATA_JSON__;
  const COLORS = {{
    NQ: {{ bullish: "#26a69a", bearish: "#80cbc4" }},
    ES: {{ bullish: "#ffa726", bearish: "#ffcc80" }},
  }};
  const CELLS = [
    {{ divId: "chart-NQ-bullish", instr: "NQ", ct: "bullish" }},
    {{ divId: "chart-NQ-bearish", instr: "NQ", ct: "bearish" }},
    {{ divId: "chart-ES-bullish", instr: "ES", ct: "bullish" }},
    {{ divId: "chart-ES-bearish", instr: "ES", ct: "bearish" }},
  ];

  let state = JSON.parse(JSON.stringify(CONFIG.default_state));

  function familyState() {{
    return state[state.family];
  }}

  function comboKeyForFamily(family, familyStateValue) {{
    if (family === "core") {{
      return `${{familyStateValue.smt}}|${{familyStateValue.size_cross}}|${{familyStateValue.wick}}|${{familyStateValue.consec}}`;
    }}
    if (family === "fvg") {{
      return `${{familyStateValue.fvg_bucket}}|${{familyStateValue.fvg_mode}}|${{familyStateValue.fvg_state}}`;
    }}
    return `${{familyStateValue.sweep}}|${{familyStateValue.prev_swing}}|${{familyStateValue.cisd_swing}}`;
  }}

  function tfData() {{
    return DATA.timeframes[state.tf];
  }}

  function selectedFamilyData() {{
    return tfData().families[state.family];
  }}

  function selectedCombo() {{
    return comboKeyForFamily(state.family, familyState());
  }}

  function hexAlpha(hex, a) {{
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${{r}},${{g}},${{b}},${{a}})`;
  }}

  function band(x, lo, hi, color, alpha) {{
    return {{
      x: [...x, ...x.slice().reverse()],
      y: [...lo, ...hi.slice().reverse()],
      fill: "toself",
      fillcolor: hexAlpha(color, alpha),
      line: {{ width: 0 }},
      showlegend: false,
      hoverinfo: "skip",
      type: "scatter",
    }};
  }}

  function buildTraces(payload, x, color) {{
    if (!payload || !payload.data) {{
      return [];
    }}
    const p = payload.data;
    return [
      band(x, p["5"], p["95"], color, 0.07),
      band(x, p["25"], p["75"], color, 0.18),
      {{ x, y: p["5"], mode: "lines", line: {{ color, width: 0.7, dash: "dot" }}, showlegend: false, hoverinfo: "skip", type: "scatter" }},
      {{ x, y: p["95"], mode: "lines", line: {{ color, width: 0.7, dash: "dot" }}, showlegend: false, hoverinfo: "skip", type: "scatter" }},
      {{ x, y: p["50"], mode: "lines", line: {{ color, width: 2.2 }}, name: "Median", hovertemplate: "%{{y:.3f}}%<extra></extra>", type: "scatter" }},
    ];
  }}

  function makeLayout(title, xDays) {{
    const maxDay = xDays[xDays.length - 1];
    let tickvals;
    let ticktext;
    if (state.tf === "Daily") {{
      tickvals = xDays;
      ticktext = xDays.map((t) => `Day ${{Math.round(t)}}`);
    }} else {{
      tickvals = [0.5, 1, 2, 3, 4, 5].filter((t) => t <= maxDay);
      if (!tickvals.length || tickvals[tickvals.length - 1] < maxDay * 0.9) {{
        tickvals.push(+maxDay.toFixed(2));
      }}
      ticktext = tickvals.map((t) => `${{t}}d`);
    }}
    return {{
      title: {{ text: title, font: {{ size: 12, color: "#e0e4f0" }}, x: 0.03, xanchor: "left", pad: {{ t: 4 }} }},
      paper_bgcolor: "#1a1d27",
      plot_bgcolor: "#1a1d27",
      font: {{ family: "-apple-system, sans-serif", color: "#c0c4d0", size: 10 }},
      xaxis: {{ gridcolor: "#2a2d3d", gridwidth: 0.5, zeroline: false, tickvals, ticktext, tickfont: {{ size: 9 }}, fixedrange: true }},
      yaxis: {{ gridcolor: "#2a2d3d", gridwidth: 0.5, zeroline: true, zerolinecolor: "#555870", zerolinewidth: 1, tickfont: {{ size: 9 }}, title: {{ text: "Return (%)", font: {{ size: 9 }}, standoff: 4 }}, fixedrange: true }},
      showlegend: false,
      margin: {{ l: 50, r: 8, t: 36, b: 32 }},
    }};
  }}

  function syncControls() {{
    document.querySelectorAll('.btn[data-dim="family"]').forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.val === state.family);
    }});
    document.querySelectorAll(`.family-panel`).forEach((panel) => {{
      panel.hidden = panel.dataset.family !== state.family;
    }});

    document.querySelectorAll('.btn[data-dim="tf"]').forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.val === state.tf);
    }});

    document.querySelectorAll('.family-panel .btn[data-dim]').forEach((btn) => {{
      const dim = btn.dataset.dim;
      const family = btn.dataset.familyPanel;
      const active = state[family][dim] === btn.dataset.val;
      btn.classList.toggle("active", active);
      btn.disabled = false;
    }});

    const fvgStateButtons = document.querySelectorAll('.family-panel[data-family="fvg"] [data-dim="fvg_state"]');
    const fvgModeAll = state.family === "fvg" && state.fvg.fvg_mode === "all";
    fvgStateButtons.forEach((btn) => {{
      btn.disabled = fvgModeAll && btn.dataset.val !== "all";
    }});
  }}

  function renderAll() {{
    const familyData = selectedFamilyData();
    const xDays = tfData().x_days;
    const key = selectedCombo();
    CELLS.forEach(({ divId, instr, ct }) => {{
      const payload = familyData.charts[instr][ct][key];
      const color = COLORS[instr][ct];
      const traces = buildTraces(payload, xDays, color);
      const n = payload ? payload.n : 0;
      const title = `${{instr}} — ${{ct.charAt(0).toUpperCase() + ct.slice(1)}}  (n=${{n.toLocaleString()}})`;
      const layout = makeLayout(title, xDays);
      if (!traces.length) {{
        layout.annotations = [{{
          text: "No events",
          xref: "paper",
          yref: "paper",
          x: 0.5,
          y: 0.5,
          showarrow: false,
          font: {{ size: 14, color: "#555870" }},
        }}];
      }}
      Plotly.react(divId, traces, layout, {{ responsive: true, displayModeBar: false }});
    }});
  }}

  document.querySelectorAll(".btn[data-dim]").forEach((btn) => {{
    btn.addEventListener("click", () => {{
      const dim = btn.dataset.dim;
      const val = btn.dataset.val;
      if (dim === "family") {{
        state.family = val;
      }} else if (dim === "tf") {{
        state.tf = val;
      }} else {{
        state[state.family][dim] = val;
        if (state.family === "fvg" && dim === "fvg_mode" && val === "all") {{
          state.fvg.fvg_state = "all";
        }}
      }}
      syncControls();
      renderAll();
    }});
  }});

  syncControls();
  renderAll();
  </script>
</body>
</html>"""
    return (
        html.replace("__FORWARD_HORIZON__", str(config["forward_horizon"]))
        .replace("__TF_BUTTONS__", tf_buttons)
        .replace("__FAMILY_BUTTONS__", family_buttons)
        .replace("__FAMILY_PANELS__", family_panels)
        .replace("__CONFIG_JSON__", json.dumps(config, separators=(",", ":")))
        .replace("__DATA_JSON__", json.dumps(data, separators=(",", ":")))
    )


def write_html(path: Path, data: dict[str, object], config: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(data, config), encoding="utf-8")


def main() -> None:
    config = build_config()
    data = build_dataset()
    write_html(OUTPUT_PATH, data, config)


if __name__ == "__main__":
    main()
