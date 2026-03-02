# CISD Markov Analysis Suite

A consolidated high-performance analysis engine for testing **CISD (Close Implies Subsequent Direction)** patterns across multiple instruments and timeframes. 

This tool loads 1-minute intraday data, resamples it to various timeframes, and runs six distinct statistical models to evaluate the reliability and "run rate" of the CISD pattern.

## 🚀 Quick Start

Ensure you have your 1-minute data in `.parquet` format within the `data/` directory (e.g., `nq_1m.parquet`, `es_1m.parquet`).

### Run all analyses across all instruments and timeframes:
```powershell
python cisd_analysis.py
```

### Run specific models only:
```powershell
python cisd_analysis.py basic lr wick
```

## 📊 Evaluation Models

| Key | Model Name | Description |
| :--- | :--- | :--- |
| `basic` | **Basic Run Rate** | Simple hit/miss: Does price touch the target H/L within the lookahead window? |
| `lr` | **Barrier (H/L First)** | **The "Stop vs Target" test:** Does price hit the target high before hitting the low (bullish) or vice versa? |
| `mc` | **Markov Segmentation** | Buckets results by how many consecutive opposite-direction candles preceded the CISD. |
| `significance` | **Stricter CISD** | Tests a variant where the CISD must close past the previous candle's High (Bullish) or Low (Bearish). |
| `wick` | **Wick Position** | Segments by whether the CISD close was "Past the Wick" or "Within the Wick" of the previous bar. |
| `combined` | **Wick × Markov** | Cross-tabulated view of Wick Position and Consecutive Candle count for deep-dive stats. |

## ⚙️ Configuration

You can modify the following constants at the top of `cisd_analysis.py`:

- `LOOKAHEAD`: How many bars into the future to check (Default: `2`).
- `MAX_CONSEC`: Max consecutive candles to track for the Markov model (Default: `3`).
- `TIMEFRAMES`: Resampling rules (Default: `Daily`, `4H`, `1H`, `15min`).

## 🛠️ Requirements

- Python 3.10+
- `pandas`
- `numpy`
- `pyarrow` or `fastparquet` (for parquet file support)

---
*Note: This repository consolidates the original 6 independent research scripts into a single, unified monolith for easier comparative analysis.*
