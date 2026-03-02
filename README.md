# CISD Barrier Analysis Suite

A high-performance analysis engine for testing **CISD (Close Implies Subsequent Direction)** patterns across NQ and ES. 

This tool evaluates the "run rate" of the CISD pattern using a strict **Barrier Problem** approach: *Does the price hit the target (CISD High/Low) before hitting the stop (opposite side) within the lookahead window?*

## 📈 Key Findings & Insights

Based on the multi-timeframe analysis (Daily, 4H, 1H, 15m) of the NQ and ES datasets:

### 1. The "Wick Advantage" (Primary Edge)
Closing **past the previous wick** is the single strongest predictor of success.
- **Past Wick Close:** ~70% – 75% success rate across all timeframes.
- **Within Wick Close:** ~45% – 55% success rate.
*Conclusion: A CISD that fails to clear the previous wick is essentially a coin flip; a clear breakout past the wick is a high-probability signal.*

### 2. Timeframe Reliability
- **1H & 15min:** Show the highest statistical consistency and sample size.
- **4H:** Shows a slight dip in reliable "barrier hit" probability compared to lower timeframes.
- **Daily:** Strongest "Bullish Bias" observed (nearly 10% higher success for bullish vs bearish).

### 3. Bullish vs Bearish Bias
The markets analyzed show a persistent bias towards bullish CISD success. Bullish setups consistently outperform bearish ones by 5-15% in terms of reaching the target before the stop.

---

## �️ Visual Reports

- 📈 **[Daily Comparison Chart](output/Daily.png)**
- 📈 **[4-Hour Comparison Chart](output/4H.png)**
- 📈 **[1-Hour Comparison Chart](output/1H.png)**
- 📈 **[15-Minute Comparison Chart](output/15min.png)**

---

## �🚀 Usage

Ensure you have your 1-minute data in `.parquet` format within the `data/` directory (`nq_1m.parquet`, `es_1m.parquet`).

### Run all analyses (Generates 4 PNGs + 4 CSVs):
```powershell
python cisd_analysis.py
```

### Run specific models:
```powershell
python cisd_analysis.py basic wick combined
```

## 📊 Evaluation Models (All Barrier-Based)

| Key | Model Name | Description |
| :--- | :--- | :--- |
| `basic` | **Basic Run Rate** | The baseline success rate for all CISD events. |
| `mc` | **Markov Segmentation** | Buckets results by how many consecutive opposite-direction candles preceded the CISD. |
| `significance` | **Stricter CISD** | Tests a variant where the CISD must close past the previous candle's High (Bullish) or Low (Bearish). |
| `wick` | **Wick Position** | Split by whether the CISD close was "Past the Wick" or "Within the Wick" of the previous bar. |
| `combined` | **Wick × Markov** | Cross-tabulated view of Wick Position and Consecutive Candle count for deep-dive stats. |

## ⚙️ Configuration

Modify constants at the top of `cisd_analysis.py`:
- `LOOKAHEAD`: Bars to check (Default: `2`).
- `MAX_CONSEC`: Max consecutive candles for Markov (Default: `3`).
- `TIMEFRAMES`: Resampling rules (Default: `Daily`, `4H`, `1H`, `15min`).

## 🛠️ Requirements

- Python 3.10+
- `pandas`, `numpy`, `matplotlib`, `pyarrow`
