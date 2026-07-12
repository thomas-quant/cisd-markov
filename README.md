# CISD Barrier Analysis Suite

A high-performance analysis engine for testing **CISD (Change in State of Delivery)** patterns across NQ and ES.

This tool evaluates the "run rate" of the CISD pattern using a strict **Barrier Problem** approach: *Does the price hit the target (CISD High/Low) before hitting the stop (opposite side) within the lookahead window?*

Swing SMT confirmation is now backed by the local SMT library at `/mnt/e/backup/code/Finance/Misc/SMT`. The matching rule is left-only: a CISD at bar `t` counts when a same-direction Swing SMT was created on `t`, `t-1`, or `t-2`.

Planned future research ideas live in `docs/research_backlog.md`.
The current research surface also includes standalone analyses for CISD-linked FVG creation/hold, sweep confirmation, and direction-specific swing-position buckets.

## Key Findings

> All figures use barrier logic: target hit **before** stop, lookahead = 2 bars.

### How to read these tables

All rates are **discovery-slice rates** (oldest ~70% of data; OOS boundary = `2024-04-30`). Full-history rates are not reported — every number went through the validation harness.

- **N** = discovery sample size
- **95% CI** = Wilson score interval on the discovery slice (pure-Python, no dependencies)
- **✓ CONFIRMED** = eligible (n ≥ 50 on discovery) and the OOS rate held the same side of 50%
- **✗ NOT CONFIRMED** = eligible but the OOS rate did not hold — a retired hypothesis, not a finding
- **below-n / not a finding** = discovery n < 50; shown so the bucket can be watched as n grows

**`below-n` and `✗ NOT CONFIRMED` are different states.** `below-n` means the bucket never had enough data to evaluate — it may be real or may not. `✗ NOT CONFIRMED` means the bucket was fully evaluated and the edge did not replicate out-of-sample; it should not be published as a finding.

---

### 1. Baseline (Basic Run Rate)

| Timeframe | Instrument | Direction | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 61.0% | 292 | [55.3–66.4%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | 59.1% | 279 | [53.3–64.7%] | ✗ NOT CONFIRMED |
| Daily | ES | Bullish | 57.7% | 293 | [52.0–63.2%] | ✓ CONFIRMED |
| Daily | ES | Bearish | 55.3% | 293 | [49.6–60.9%] | ✗ NOT CONFIRMED |
| 4H | NQ | Bullish | 54.9% | 1471 | [52.4–57.5%] | ✓ CONFIRMED |
| 4H | NQ | Bearish | 50.2% | 1465 | [47.7–52.8%] | ✓ CONFIRMED |
| 4H | ES | Bullish | 57.1% | 1463 | [54.5–59.6%] | ✓ CONFIRMED |
| 4H | ES | Bearish | 51.9% | 1458 | [49.3–54.4%] | ✓ CONFIRMED |
| 1H | NQ | Bullish | 61.4% | 5462 | [60.1–62.7%] | ✓ CONFIRMED |
| 1H | NQ | Bearish | 57.3% | 5455 | [56.0–58.6%] | ✓ CONFIRMED |
| 1H | ES | Bullish | 62.7% | 5235 | [61.4–64.0%] | ✓ CONFIRMED |
| 1H | ES | Bearish | 58.5% | 5175 | [57.1–59.8%] | ✓ CONFIRMED |
| 15min | NQ | Bullish | 62.4% | 21518 | [61.7–63.0%] | ✓ CONFIRMED |
| 15min | NQ | Bearish | 59.1% | 21400 | [58.5–59.8%] | ✓ CONFIRMED |
| 15min | ES | Bullish | 62.4% | 20168 | [61.7–63.0%] | ✓ CONFIRMED |
| 15min | ES | Bearish | 59.9% | 20006 | [59.2–60.6%] | ✓ CONFIRMED |

**Key findings:** Bullish bias holds OOS at all timeframes. Bearish Daily failed OOS for both instruments — Daily bearish edges should not be treated as established findings. 4H is the weakest timeframe; 1H and 15min are the most consistent.

---

### 2. Wick Position (Strongest Edge)

A CISD that closes **past the previous wick** is the single most reliable filter.

| Timeframe | Instrument | Direction | Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | past_wick | 77.7% | 94 | [68.2–84.9%] | ✓ CONFIRMED |
| Daily | NQ | Bullish | within_wick | 53.0% | 198 | [46.1–59.9%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | past_wick | 75.0% | 100 | [65.7–82.5%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | within_wick | 50.3% | 179 | [43.0–57.5%] | ✗ NOT CONFIRMED |
| Daily | ES | Bullish | past_wick | 70.1% | 107 | [60.8–77.9%] | ✓ CONFIRMED |
| Daily | ES | Bullish | within_wick | 50.5% | 186 | [43.4–57.6%] | ✓ CONFIRMED |
| Daily | ES | Bearish | past_wick | 73.0% | 100 | [63.6–80.7%] | ✓ CONFIRMED |
| Daily | ES | Bearish | within_wick | 46.1% | 193 | [39.2–53.2%] | ✓ CONFIRMED |
| 4H | NQ | Bullish | past_wick | 62.7% | 491 | [58.4–66.9%] | ✓ CONFIRMED |
| 4H | NQ | Bullish | within_wick | 51.0% | 980 | [47.9–54.1%] | ✓ CONFIRMED |
| 4H | NQ | Bearish | past_wick | 61.7% | 488 | [57.3–65.9%] | ✓ CONFIRMED |
| 4H | NQ | Bearish | within_wick | 44.5% | 977 | [41.4–47.7%] | ✓ CONFIRMED |
| 4H | ES | Bullish | past_wick | 67.2% | 466 | [62.8–71.3%] | ✓ CONFIRMED |
| 4H | ES | Bullish | within_wick | 52.4% | 997 | [49.3–55.4%] | ✓ CONFIRMED |
| 4H | ES | Bearish | past_wick | 62.3% | 443 | [57.7–66.7%] | ✓ CONFIRMED |
| 4H | ES | Bearish | within_wick | 47.3% | 1015 | [44.2–50.4%] | ✓ CONFIRMED |
| 1H | NQ | Bullish | past_wick | 71.9% | 1669 | [69.7–74.0%] | ✓ CONFIRMED |
| 1H | NQ | Bullish | within_wick | 56.8% | 3793 | [55.2–58.3%] | ✓ CONFIRMED |
| 1H | NQ | Bearish | past_wick | 68.9% | 1567 | [66.6–71.2%] | ✓ CONFIRMED |
| 1H | NQ | Bearish | within_wick | 52.6% | 3888 | [51.1–54.2%] | ✓ CONFIRMED |
| 1H | ES | Bullish | past_wick | 73.3% | 1602 | [71.1–75.5%] | ✓ CONFIRMED |
| 1H | ES | Bullish | within_wick | 58.1% | 3633 | [56.4–59.6%] | ✓ CONFIRMED |
| 1H | ES | Bearish | past_wick | 69.3% | 1496 | [66.9–71.5%] | ✓ CONFIRMED |
| 1H | ES | Bearish | within_wick | 54.1% | 3679 | [52.5–55.7%] | ✓ CONFIRMED |
| 15min | NQ | Bullish | past_wick | 72.5% | 6281 | [71.4–73.6%] | ✓ CONFIRMED |
| 15min | NQ | Bullish | within_wick | 58.2% | 15237 | [57.4–58.9%] | ✓ CONFIRMED |
| 15min | NQ | Bearish | past_wick | 70.5% | 6114 | [69.4–71.7%] | ✓ CONFIRMED |
| 15min | NQ | Bearish | within_wick | 54.6% | 15286 | [53.8–55.4%] | ✓ CONFIRMED |
| 15min | ES | Bullish | past_wick | 73.9% | 5565 | [72.7–75.0%] | ✓ CONFIRMED |
| 15min | ES | Bullish | within_wick | 58.0% | 14603 | [57.2–58.8%] | ✓ CONFIRMED |
| 15min | ES | Bearish | past_wick | 73.3% | 5570 | [72.2–74.5%] | ✓ CONFIRMED |
| 15min | ES | Bearish | within_wick | 54.7% | 14436 | [53.9–55.5%] | ✓ CONFIRMED |

**Past-wick closure is confirmed across all timeframes and both instruments.** Spread between past-wick and within-wick is ~15–25pp at all timeframes. Daily NQ bearish within-wick (50.3%, n=179) did not survive OOS — within-wick bearish setups on the Daily are not an established finding.

---

### 3. Combined Wick × Consecutive Candles

Combining past-wick closure with 2–3 consecutive opposite candles consistently yields the highest discovery hit rates. Many Daily combined buckets are `below-n / not a finding` due to small sample sizes; the 1H and 15min buckets are the most fully evaluated.

**Daily — selected confirmed and not-confirmed buckets (many Daily cells are below-n):**

| Timeframe | Instrument | Direction | Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 1c_within_wick | 54.1% | 111 | [44.8–63.0%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | 1c_within_wick | 51.2% | 84 | [40.7–61.6%] | ✗ NOT CONFIRMED |
| Daily | NQ | Bearish | 3c_within_wick | 54.5% | 55 | [41.5–66.9%] | ✗ NOT CONFIRMED |
| Daily | ES | Bullish | 1c_past_wick | 72.7% | 55 | [59.8–82.7%] | ✓ CONFIRMED |
| Daily | ES | Bullish | 1c_within_wick | 48.9% | 90 | [38.8–59.0%] | ✗ NOT CONFIRMED |
| Daily | ES | Bullish | 2c_within_wick | 54.4% | 57 | [41.6–66.6%] | ✗ NOT CONFIRMED |
| Daily | ES | Bearish | 1c_past_wick | 71.4% | 56 | [58.5–81.6%] | ✓ CONFIRMED |
| Daily | ES | Bearish | 1c_within_wick | 43.3% | 90 | [33.6–53.6%] | ✓ CONFIRMED |
| Daily | ES | Bearish | 3c_within_wick | 50.0% | 54 | [37.1–62.9%] | ✓ CONFIRMED |

**4H — all buckets:**

| Instrument | Direction | Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| NQ | Bullish | 1c_past_wick | 60.9% | 261 | [54.9–66.6%] | ✓ CONFIRMED |
| NQ | Bullish | 1c_within_wick | 52.6% | 532 | [48.4–56.8%] | ✓ CONFIRMED |
| NQ | Bullish | 2c_past_wick | 59.7% | 129 | [51.1–67.8%] | ✓ CONFIRMED |
| NQ | Bullish | 2c_within_wick | 49.6% | 238 | [43.3–55.9%] | ✗ NOT CONFIRMED |
| NQ | Bullish | 3c_past_wick | 71.3% | 101 | [61.8–79.2%] | ✓ CONFIRMED |
| NQ | Bullish | 3c_within_wick | 48.6% | 210 | [41.9–55.3%] | ✓ CONFIRMED |
| NQ | Bearish | 1c_past_wick | 66.8% | 238 | [60.6–72.5%] | ✓ CONFIRMED |
| NQ | Bearish | 1c_within_wick | 41.8% | 474 | [37.4–46.3%] | ✓ CONFIRMED |
| NQ | Bearish | 2c_past_wick | 55.9% | 111 | [46.6–64.7%] | ✓ CONFIRMED |
| NQ | Bearish | 2c_within_wick | 46.4% | 252 | [40.4–52.6%] | ✓ CONFIRMED |
| NQ | Bearish | 3c_past_wick | 57.6% | 139 | [49.2–65.5%] | ✓ CONFIRMED |
| NQ | Bearish | 3c_within_wick | 47.8% | 251 | [41.7–53.9%] | ✓ CONFIRMED |
| ES | Bullish | 1c_past_wick | 64.0% | 272 | [58.1–69.4%] | ✓ CONFIRMED |
| ES | Bullish | 1c_within_wick | 54.7% | 525 | [50.4–58.9%] | ✓ CONFIRMED |
| ES | Bullish | 2c_past_wick | 67.9% | 109 | [58.6–75.9%] | ✓ CONFIRMED |
| ES | Bullish | 2c_within_wick | 50.4% | 248 | [44.2–56.6%] | ✓ CONFIRMED |
| ES | Bullish | 3c_past_wick | 76.5% | 85 | [66.4–84.2%] | ✓ CONFIRMED |
| ES | Bullish | 3c_within_wick | 49.1% | 224 | [42.6–55.6%] | ✗ NOT CONFIRMED |
| ES | Bearish | 1c_past_wick | 59.1% | 230 | [52.7–65.3%] | ✓ CONFIRMED |
| ES | Bearish | 1c_within_wick | 45.9% | 525 | [41.7–50.2%] | ✓ CONFIRMED |
| ES | Bearish | 2c_past_wick | 65.5% | 87 | [55.1–74.7%] | ✓ CONFIRMED |
| ES | Bearish | 2c_within_wick | 49.2% | 238 | [42.9–55.5%] | ✓ CONFIRMED |
| ES | Bearish | 3c_past_wick | 65.9% | 126 | [57.2–73.6%] | ✓ CONFIRMED |
| ES | Bearish | 3c_within_wick | 48.4% | 252 | [42.3–54.6%] | ✓ CONFIRMED |

**1H and 15min combined buckets:** All 48 buckets (24 each) are ✓ CONFIRMED. Past-wick + 2c or 3c at 1H/15min consistently reaches 70–75% discovery rates and holds OOS.

**Note on Daily combined buckets:** Most Daily combined cells fall `below-n / not a finding` (discovery n < 50). Of the 24 Daily combined buckets with n ≥ 50, 8 are `✗ NOT CONFIRMED` (concentrated in within-wick bearish and ES bullish within-wick). Daily past-wick + any consecutive count confirms for both instruments where n ≥ 50.

---

### 4. Stricter CISD (Significance Test)

Requiring the close to exceed the **previous candle's High/Low** (not just the close) gives a consistent +5–8pp lift over baseline. All 16 buckets are ✓ CONFIRMED.

| Timeframe | Instrument | Direction | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 68.4% | 329 | [63.2–73.2%] | ✓ CONFIRMED |
| Daily | NQ | Bearish | 65.3% | 259 | [59.3–70.8%] | ✓ CONFIRMED |
| Daily | ES | Bullish | 68.2% | 333 | [62.9–72.9%] | ✓ CONFIRMED |
| Daily | ES | Bearish | 65.5% | 261 | [59.6–71.0%] | ✓ CONFIRMED |
| 4H | NQ | Bullish | 60.3% | 1619 | [57.9–62.6%] | ✓ CONFIRMED |
| 4H | NQ | Bearish | 58.3% | 1332 | [55.7–60.9%] | ✓ CONFIRMED |
| 4H | ES | Bullish | 63.1% | 1567 | [60.7–65.5%] | ✓ CONFIRMED |
| 4H | ES | Bearish | 59.7% | 1269 | [56.9–62.3%] | ✓ CONFIRMED |
| 1H | NQ | Bullish | 65.8% | 5644 | [64.6–67.0%] | ✓ CONFIRMED |
| 1H | NQ | Bearish | 63.6% | 4686 | [62.2–64.9%] | ✓ CONFIRMED |
| 1H | ES | Bullish | 66.6% | 5546 | [65.4–67.9%] | ✓ CONFIRMED |
| 1H | ES | Bearish | 64.8% | 4594 | [63.4–66.1%] | ✓ CONFIRMED |
| 15min | NQ | Bullish | 67.5% | 21256 | [66.9–68.2%] | ✓ CONFIRMED |
| 15min | NQ | Bearish | 66.2% | 19161 | [65.5–66.9%] | ✓ CONFIRMED |
| 15min | ES | Bullish | 68.6% | 20307 | [67.9–69.2%] | ✓ CONFIRMED |
| 15min | ES | Bearish | 67.7% | 18387 | [66.9–68.3%] | ✓ CONFIRMED |

---

### 5. Consecutive Opposite Candles (Markov)

Consecutive candle count alone has **weak and inconsistent** predictive value at Daily and partially at 4H. At 1H and 15min, all consecutive buckets are confirmed.

**Daily — all buckets (many not-confirmed):**

| Instrument | Direction | Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|---|---|
| NQ | Bullish | 1_consecutive | 61.0% | 159 | [53.3–68.2%] | ✓ CONFIRMED |
| NQ | Bullish | 2_consecutive | 63.4% | 71 | [51.8–73.6%] | ✗ NOT CONFIRMED |
| NQ | Bullish | 3_consecutive | 58.1% | 62 | [45.7–69.5%] | ✓ CONFIRMED |
| NQ | Bearish | 1_consecutive | 58.3% | 127 | [49.6–66.5%] | ✗ NOT CONFIRMED |
| NQ | Bearish | 2_consecutive | 57.6% | 66 | [45.6–68.8%] | ✗ NOT CONFIRMED |
| NQ | Bearish | 3_consecutive | 61.6% | 86 | [51.1–71.2%] | ✗ NOT CONFIRMED |
| ES | Bullish | 1_consecutive | 57.9% | 145 | [49.8–65.7%] | ✓ CONFIRMED |
| ES | Bullish | 2_consecutive | 62.4% | 85 | [51.7–71.9%] | ✗ NOT CONFIRMED |
| ES | Bullish | 3_consecutive | 50.8% | 63 | [38.8–62.7%] | ✓ CONFIRMED |
| ES | Bearish | 1_consecutive | 54.1% | 146 | [46.0–61.9%] | ✗ NOT CONFIRMED |
| ES | Bearish | 2_consecutive | 59.2% | 71 | [47.5–69.8%] | ✗ NOT CONFIRMED |
| ES | Bearish | 3_consecutive | 53.9% | 76 | [42.8–64.6%] | ✗ NOT CONFIRMED |

**4H — mixed results; 6 of 12 not-confirmed (bearish ES and some bullish NQ).**

**1H and 15min — all 24 buckets confirmed.** Hit rates are flat across 1–3 consecutive candles (within ~3pp of baseline). The edge from Markov segmentation alone is small; it only emerges clearly when combined with wick position (see §3).

---

### 6. Candle Body Size vs ATR & Cross-Tab

*(See standalone charts: `CandleSize_All_Timeframes.png`, `SizeCross_All_Timeframes.png`)*

CISD candles with a body ≥ 0.5× ATR(14) show meaningfully higher hit rates than smaller candles. The cross-tab reveals a clear quadrant structure: **Big CISD + Small prev** = strongest; **Small CISD + Big prev** = weakest. The pattern is robust at 1H and 15min (all buckets confirmed); some Daily and 4H cells are `below-n / not a finding` or `✗ NOT CONFIRMED`.

**Representative confirmed candle_size buckets (1H, NQ Bullish):**

| Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|
| < 0.5× ATR | 55.6% | 3448 | [53.9–57.2%] | ✓ CONFIRMED |
| 0.5–1× ATR | 68.2% | 1225 | [65.6–70.8%] | ✓ CONFIRMED |
| 1–1.5× ATR | 72.6% | 503 | [68.5–76.3%] | ✓ CONFIRMED |
| > 1.5× ATR | 82.7% | 284 | [77.9–86.7%] | ✓ CONFIRMED |

**Size cross-tab confirmed quadrant (1H, NQ Bullish):**

| Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|
| Big CISD / Small prev | 76.7% | 593 | [73.2–80.0%] | ✓ CONFIRMED |
| Big CISD / Big prev | 74.7% | 194 | [68.2–80.3%] | ✓ CONFIRMED |
| Small CISD / Small prev | 58.7% | 4098 | [57.1–60.2%] | ✓ CONFIRMED |
| Small CISD / Big prev | 60.7% | 575 | [56.6–64.6%] | ✓ CONFIRMED |

**Daily and 4H notes:** Many "Big CISD" Daily buckets fall `below-n / not a finding` (n < 50). At 4H NQ bullish, the < 0.5× ATR bucket (n=950) is `✗ NOT CONFIRMED`. All 15min candle_size and size_cross buckets are ✓ CONFIRMED, confirming the ATR-segmentation pattern across large samples.

---

### 7. Volume Ratio

*(See `Volume_All_Timeframes.png`)*

Volume ratio (CISD candle vs previous candle) has **negligible impact** on outcomes at 1H and 15min — hit rates are stable across all volume buckets and all 32 1H/15min buckets are ✓ CONFIRMED. At Daily and 4H, some buckets are `✗ NOT CONFIRMED` (particularly 1x–1.5x bearish Daily and several 4H cells), and a handful are `below-n / not a finding` due to small n in the 1.5x–2.5x bin.

**Representative confirmed volume buckets (1H, NQ Bullish):**

| Bucket | Discovery Rate | N | 95% CI | Verdict |
|---|---|---|---|---|
| < 1× (lower vol) | 60.5% | 3058 | [58.8–62.2%] | ✓ CONFIRMED |
| 1×–1.5× | 62.7% | 1316 | [60.0–65.3%] | ✓ CONFIRMED |
| 1.5×–2.5× | 61.7% | 741 | [58.1–65.1%] | ✓ CONFIRMED |
| > 2.5× (spike) | 63.4% | 347 | [58.2–68.3%] | ✓ CONFIRMED |

The near-flat distribution across all four buckets at 1H/15min confirms that volume ratio does not add meaningful edge as a standalone filter on CISD barrier outcomes at those timeframes.

---

### 8. Swing SMT Confirmation

*(See `SMT_CISD_All_Timeframes.png`)*

A co-occurring same-direction **Swing SMT** (divergence between NQ and ES swing highs/lows, lookback=20) is used as a confirmation filter. As of v2.0 the `w/ SMT` population is corrected — see "SMT Invalidation Honesty (v2.0)" below for what changed and why. Results vary sharply by timeframe.

| Timeframe | Instrument | Direction | w/ SMT Rate | w/ SMT N | 95% CI | no SMT Rate | Δ | Verdict (w/ SMT) |
|---|---|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 69.2% | 39 | [53.6–81.4%] | 60.5% | +8.7pp | below-n / not a finding |
| Daily | NQ | Bearish | 64.3% | 28 | [45.8–79.3%] | 57.5% | +6.8pp | below-n / not a finding |
| Daily | ES | Bullish | 57.1% | 42 | [42.2–70.9%] | 59.1% | −1.9pp | below-n / not a finding |
| Daily | ES | Bearish | 51.4% | 35 | [35.6–67.0%] | 55.4% | −4.0pp | below-n / not a finding |
| 4H | NQ | Bullish | 59.0% | 156 | [51.1–66.4%] | 54.9% | +4.1pp | ✓ CONFIRMED |
| 4H | NQ | Bearish | 50.3% | 171 | [42.9–57.7%] | 50.1% | +0.2pp | ✓ CONFIRMED |
| 4H | ES | Bullish | 64.5% | 152 | [56.6–71.6%] | 56.7% | +7.8pp | ✓ CONFIRMED |
| 4H | ES | Bearish | 52.2% | 161 | [44.5–59.7%] | 51.1% | +1.0pp | ✓ CONFIRMED |
| 1H | NQ | Bullish | 59.0% | 503 | [54.7–63.3%] | 61.2% | −2.1pp | ✓ CONFIRMED |
| 1H | NQ | Bearish | 54.9% | 565 | [50.7–58.9%] | 57.5% | −2.7pp | ✓ CONFIRMED |
| 1H | ES | Bullish | 60.4% | 472 | [55.9–64.7%] | 62.6% | −2.3pp | ✓ CONFIRMED |
| 1H | ES | Bearish | 55.3% | 535 | [51.1–59.5%] | 58.8% | −3.4pp | ✓ CONFIRMED |
| 15min | NQ | Bullish | **64.9%** | 1887 | [62.7–67.0%] | 61.9% | +2.9pp | ✓ CONFIRMED |
| 15min | NQ | Bearish | **61.2%** | 1965 | [59.0–63.4%] | 58.6% | +2.6pp | ✓ CONFIRMED |
| 15min | ES | Bullish | **63.9%** | 1810 | [61.7–66.1%] | 62.1% | +1.9pp | ✓ CONFIRMED |
| 15min | ES | Bearish | **60.5%** | 1884 | [58.3–62.7%] | 59.7% | +0.8pp | ✓ CONFIRMED |

The invalidation fix also surfaces the **`expired SMT`** bucket — CISDs that matched a same-direction Swing SMT in the `[t-2, t]` window, but that SMT was already invalidated (`broken_ts <= t`) by the time the CISD formed. These were previously mis-credited as `w/ SMT`; they are now reported separately and are **not** part of the corrected `w/ SMT` rate above:

| Timeframe | Instrument | Direction | expired SMT Rate | expired SMT N |
|---|---|---|---|---|
| Daily | NQ | Bullish | 40.0% | 10 |
| Daily | NQ | Bearish | 72.2% | 18 |
| Daily | ES | Bullish | 22.2% | 9 |
| Daily | ES | Bearish | 61.1% | 18 |
| 4H | NQ | Bullish | 46.0% | 63 |
| 4H | NQ | Bearish | 53.3% | 60 |
| 4H | ES | Bullish | 47.6% | 63 |
| 4H | ES | Bearish | 65.6% | 61 |
| 1H | NQ | Bullish | 71.6% | 225 |
| 1H | NQ | Bearish | 58.5% | 260 |
| 1H | ES | Bullish | 69.9% | 219 |
| 1H | ES | Bearish | 59.9% | 252 |
| 15min | NQ | Bullish | 66.3% | 816 |
| 15min | NQ | Bearish | 65.0% | 857 |
| 15min | ES | Bullish | 65.2% | 747 |
| 15min | ES | Bearish | 62.2% | 788 |

**Key takeaways (corrected, v2.0):**

- **Daily** SMT: all four `w/ SMT` buckets are now `below-n / not a finding` (n < 50 in every combo) — the two ES buckets that were previously eligible (n=51, n=53) dropped below the n=50 gate once the `expired SMT` split removed already-dead matches from the `w/ SMT` population. Daily SMT carries no finding at either the before-fix or after-fix bar.
- **4H** SMT: all four `w/ SMT` buckets are confirmed post-fix. **ES Bearish flips from `✗ NOT CONFIRMED` to `✓ CONFIRMED`** — the pre-fix bucket's discovery rate (55.9%) held on OOS at 46.7% (opposite side), but the corrected discovery rate (52.2%) now holds the same side as the corrected OOS rate (51.5%). This flip is a direct, documented consequence of the invalidation fix, not a new discovery.
- **1H** SMT: all four `w/ SMT` buckets remain confirmed; rates shift down modestly (−2 to −4pp vs the pre-fix numbers) now that expired matches are excluded, but the same-side-of-50% OOS confirmation is unaffected.
- **15min** remains the strongest timeframe: all four buckets confirmed, **+0.8–2.9pp** over no-SMT with large discovery samples (n=1,810–1,965).
- **Scope note:** the `w/ SMT & survived` / `w/ SMT & broke` split (new in v2.0) is a **diagnostic only** — the aggregate `w/ SMT` population above is never filtered on survival, since that would be hindsight (an outcome only knowable after the barrier window closes). See `output/smt_invalidation_report.csv` and `SMT_Role_All_Timeframes.png` / `SMT_BlockSize_All_Timeframes.png` / `SMT_InBlock_All_Timeframes.png` for the new `smt_role` / `smt_block_size` / `smt_in_block` validated buckets (n + Wilson CI + BH-FDR + walk-forward), which are separate analyses, not sub-splits of `smt_cisd`.

---

## SMT Invalidation Honesty (v2.0)

Phase 9 fixes a bug in the Swing SMT confirmation tagging: a matched same-direction SMT was credited as `w/ SMT` even when it had **already been invalidated by the CISD bar `t`** (`broken_ts <= t`). Because sub-bar ordering between an intrabar invalidation and the CISD close is unknowable, an SMT whose `broken_ts` lands exactly on bar `t` is now treated conservatively as dead — the CISD is reclassified into a new **`expired SMT`** bucket instead of `w/ SMT`. The `swing_smt_tag` split is therefore three-way as of v2.0: `w/ SMT` (still valid at `t`) / `expired SMT` (matched but dead by `t`) / `no SMT` (no same-direction match at all).

This changes the previously-published `w/ SMT` rate and n for every timeframe/instrument/direction combo — always a reduction in n (dead matches leave the bucket) and a rate shift in either direction depending on how the removed expired matches performed. Per D-09a, the "before" numbers below are the currently-published (pre-fix) §8 values already on record — no separate recompute or snapshot ceremony was needed. "After" is the corrected, regenerated discovery manifest. The table is generated by `scripts/build_smt_invalidation_report.py` from `output/smt_invalidation_report.csv`:

| Timeframe | Instrument | Direction | Before Rate | Before N | After Rate | After N | Δ Rate | Δ N |
|---|---|---|---|---|---|---|---|---|
| Daily | NQ | Bullish | 63.3% | 49 | 69.2% | 39 | +6.0pp | −10 |
| Daily | NQ | Bearish | 67.4% | 46 | 64.3% | 28 | −3.1pp | −18 |
| Daily | ES | Bullish | 51.0% | 51 | 57.1% | 42 | +6.2pp | −9 |
| Daily | ES | Bearish | 54.7% | 53 | 51.4% | 35 | −3.3pp | −18 |
| 4H | NQ | Bullish | 55.3% | 219 | 59.0% | 156 | +3.7pp | −63 |
| 4H | NQ | Bearish | 51.1% | 231 | 50.3% | 171 | −0.8pp | −60 |
| 4H | ES | Bullish | 59.5% | 215 | 64.5% | 152 | +4.9pp | −63 |
| 4H | ES | Bearish | 55.9% | 222 | 52.2% | 161 | −3.7pp | −61 |
| 1H | NQ | Bullish | 62.9% | 728 | 59.0% | 503 | −3.9pp | −225 |
| 1H | NQ | Bearish | 56.0% | 825 | 54.9% | 565 | −1.1pp | −260 |
| 1H | ES | Bullish | 63.4% | 691 | 60.4% | 472 | −3.0pp | −219 |
| 1H | ES | Bearish | 56.8% | 787 | 55.3% | 535 | −1.5pp | −252 |
| 15min | NQ | Bullish | 65.3% | 2703 | 64.9% | 1887 | −0.4pp | −816 |
| 15min | NQ | Bearish | 62.4% | 2822 | 61.2% | 1965 | −1.1pp | −857 |
| 15min | ES | Bullish | 64.3% | 2557 | 63.9% | 1810 | −0.4pp | −747 |
| 15min | ES | Bearish | 61.0% | 2672 | 60.5% | 1884 | −0.5pp | −788 |

**What changed, in plain terms:**

- Every combo loses n (10–857 CISDs move out of `w/ SMT` into `expired SMT`) — the previously mis-credited already-dead-SMT population is now visible as its own bucket instead of silently inflating `w/ SMT`.
- Rate moves are mixed (−3.9pp to +6.2pp) depending on how the removed expired-SMT matches happened to run relative to the still-valid ones — there is no systematic direction to the correction, consistent with fixing a labeling bug rather than discovering a new effect.
- Two Daily ES buckets drop from eligible (n≥50) to `below-n` purely because of the n reduction — not because their behavior changed.
- **One verdict flip:** 4H ES Bearish moves from `✗ NOT CONFIRMED` (pre-fix) to `✓ CONFIRMED` (corrected) — see the §8 key takeaways above for the discovery/OOS numbers behind the flip.
- **Every non-`smt_*` analysis is confirmed byte-value unchanged** by the regeneration's own drift check (`build_non_smt_drift` in `scripts/build_smt_invalidation_report.py`, run against the regenerated `output/validation_manifest_discovery.csv`): it compares every non-SMT `(analysis, timeframe, instrument, direction, bucket)` row's `rate`/`n` before vs after and exits non-zero if anything moved. The regen that produced this table's "after" numbers reported zero drifted rows — the other 15 published analyses (Baseline, Wick Position, Combined, Stricter CISD, Consecutive Candles, Candle Size, Volume, CISD FVG, FVG Hold, CISD FVG Interaction, Sweep, SSSF Swing, and both post-CISD studies) moved by exactly nothing (D-09a).

---

## Visual Reports

**Per-Timeframe (5 core analyses):**

![Daily](output/Daily.png)

![4-Hour](output/4H.png)

![1-Hour](output/1H.png)

![15-Minute](output/15min.png)

**Standalone — All Timeframes side-by-side:**

![Candle Body Size vs ATR(14)](output/CandleSize_All_Timeframes.png)

![CISD Body x Prev Body vs ATR (Cross-Tab)](output/SizeCross_All_Timeframes.png)

![Volume Ratio](output/Volume_All_Timeframes.png)

![Swing SMT Confirmation](output/SMT_CISD_All_Timeframes.png)

![Swing SMT Role (Swept vs Failed-to-Sweep)](output/SMT_Role_All_Timeframes.png)

![SMT Block Size vs ATR(14)](output/SMT_BlockSize_All_Timeframes.png)

![CISD In SMT Block Containment](output/SMT_InBlock_All_Timeframes.png)

---

## Usage

Ensure data is in `.parquet` format in the `data/` directory (`nq_1m.parquet`, `es_1m.parquet`).

## Forward Returns Explorer

Rebuild the interactive forward-returns report with:

```bash
python3 scripts/build_forward_returns.py
```

The page groups research into three families:

- `core`: SMT, size-vs-prev-body, wick position, and consecutive-candle buckets.
- `fvg`: CISD-linked FVG creation and hold-state buckets.
- `structure`: sweep confirmation plus the previous-bar and CISD-bar swing-position buckets.

### Run all analyses (4 per-TF PNGs + CSVs + 9 standalone PNGs):
```powershell
python cisd_analysis.py
```

### Run specific models:
```powershell
python cisd_analysis.py cisd_fvg fvg_hold cisd_fvg_interaction sweep sssf_swing
```

The current CLI surface is limited to the analysis keys listed below.

## Evaluation Models (All Barrier-Based)

| Key | Model Name | Description |
| :--- | :--- | :--- |
| `basic` | **Basic Run Rate** | Baseline success rate for all CISD events. |
| `mc` | **Markov Segmentation** | Buckets by consecutive opposite-direction candles preceding the CISD. |
| `significance` | **Stricter CISD** | CISD must close past the previous candle's High (Bullish) or Low (Bearish). |
| `wick` | **Wick Position** | Split by whether the close was past the wick or within it. |
| `combined` | **Wick x Markov** | Cross-tab of wick position and consecutive candle count. |
| `volume` | **Volume Ratio** | Segments by CISD volume relative to previous candle. Standalone all-TF output. |
| `candle_size` | **Candle Body vs ATR** | Segments by CISD body size as a multiple of ATR(14). Standalone all-TF output. |
| `size_cross` | **CISD Body × Prev Body** | Cross-tab: both candles vs ATR(14). Standalone all-TF output. |
| `smt_cisd` | **Swing SMT Confirmation** | Barrier rate split by whether a same-direction, still-valid-at-`t` Swing SMT co-occurs (`w/ SMT` / `expired SMT` / `no SMT`), plus `w/ SMT & survived`/`w/ SMT & broke` diagnostic sub-buckets. Standalone. |
| `smt_role` | **Swing SMT Role** | Swept vs failed-to-sweep split over the valid `w/ SMT` population only. Standalone. |
| `smt_block_size` | **SMT Block Size vs ATR** | Segments the matched-SMT population by `smt_block_size_atr` (reference-bar range / ATR(14)) using the `candle_size` bucket convention. Standalone. |
| `smt_in_block` | **CISD In SMT Block** | Splits the matched-SMT population by whether the CISD body is fully contained within the SMT's reference-bar range (`cisd_in_block`/`cisd_out_block`). Standalone. |
| `cisd_fvg` | **CISD FVG Creation** | Barrier rate split by whether the CISD is the middle candle of a same-direction FVG (`mid0`), the next bar is the middle candle (`mid1`), or no linked FVG exists. Standalone. |
| `fvg_hold` | **FVG Hold** | Hold rate of same-direction CISD-linked FVGs over a 10-bar window from the FVG middle candle, reported for both hold-failure modes and both `mid0`/`mid1` buckets. Standalone. |
| `cisd_fvg_interaction` | **CISD FVG Interaction** | Barrier rate of the parent CISD split by whether its linked same-direction FVG later held or failed, for both failure modes and both `mid0`/`mid1` buckets. Standalone. |
| `sweep` | **Sweep Confirmation** | Barrier rate split by whether a same-direction sweep of a prior swing occurred in the `[t-4, t]` window around the CISD. Standalone. |
| `sssf_swing` | **SSSF Swing** | Barrier rate split by whether `candle[-1]` or `candle[0]` is the direction-matched 3-candle swing point, with a baseline `neither` bucket. Standalone. |

## Research Tag Rules

- FVG formation uses the standard 3-candle wick-to-wick rule.
  - Bullish: left high `<` right low.
  - Bearish: left low `>` right high.
  - `mid0` means the CISD bar is the middle candle; `mid1` means the next bar is the middle candle.
- FVG direction must match the parent CISD direction.
- FVG hold is measured over `FVG_HOLD_LOOKAHEAD = 10` bars from the FVG middle candle with two failure modes:
  - `close_through_near_edge`
  - `wick_break_far_extreme`
- Sweep confirmation is direction-specific and binary:
  - bullish CISD checks for a low sweep
  - bearish CISD checks for a high sweep
  - the sweep can occur on any bar in `[t-4, t]`
  - prior swing points are sourced from a `20`-bar swing lookback
- Swing-position buckets use a 3-candle swing rule (`N=1`):
  - bullish CISDs use swing lows
  - bearish CISDs use swing highs
  - `prev_bar_is_swing` corresponds to `candle[-1]`
  - `cisd_bar_is_swing` corresponds to `candle[0]`

## Validation Methodology — Harder Evidence Bar (v2.0)

Phase 6 adds two additive validation capabilities to `scripts/build_validation.py`. Neither changes an existing manifest column or a previously published rate — both are new columns / new sibling artifacts layered on top of the v1.0 harness (sacred chronological holdout, Wilson CI, `min_n_pass` gate).

- **D-04 scope disclaimer:** This harder corrected bar currently applies **only** to the two post-CISD studies, `post_cisd_context` and `candle1_followthrough`. The other 8 published Key Findings sections — Baseline, Wick Position, Combined Wick×Consecutive, Stricter CISD, Consecutive Opposite Candles, Candle Body Size, Volume Ratio, and Swing SMT — have **not** been re-evaluated under it.

**Multiple-comparisons (FDR) correction:**

- Every bucket in the discovery manifest now carries a `p_value` testing `H0: rate = 0.5` (the fixed coin-flip null, not a bucket's own baseline rate) — a two-sided normal-approximation z-test (`p_value_vs_half`).
- A single global Benjamini-Hochberg step-up correction (`bh_correct`) is applied across **every bucket, across every analysis × timeframe × instrument × direction, in one pass** — never grouped per-analysis-key — because the point is to account for the full extent of data-snooping across the whole engine, not one chart at a time.
- The correction fires at the **discovery-manifest stage only** (`validation_manifest_discovery.csv`), before the sacred OOS look; it is a pre-registration-style gate on which buckets earn that look. The OOS manifest is unaffected.
- Adds `bh_rank`, `bh_q_value`, `bh_significant`, and `corrected_pass` columns to `validation_manifest_discovery.csv`. `corrected_pass = min_n_pass AND bh_significant` — the harder evidence bar requires clearing both the sample-size gate and FDR significance.

**Walk-forward (rolling-window) validation:**

- Run with `python3 scripts/build_validation.py --walk-forward`. Output: a new sibling artifact, `output/validation_manifest_walkforward.csv` — the existing `validation_manifest_discovery.csv` / `validation_manifest_oos.csv` files and the sacred OOS banner are never touched by this path.
- Windows are **expanding / anchored**: each of the 4 folds trains on all discovery history from the start through its fold boundary, then tests on the following chunk — chosen because the discovery history is finite and every available bar should be used rather than discarded.
- Fold boundaries are **4 frozen calendar dates** (`WALK_FORWARD_FOLDS` in `cisd_data.py`), derived once as the 20th/40th/60th/80th-percentile dates of the discovery-region calendar (mirroring how `OOS_START` itself was derived and frozen) — not recomputed at runtime, and every boundary is strictly before `OOS_START`, so walk-forward never consumes the one sacred OOS evaluation.
- Each fold is scored by `evaluate_fold()`: both the anchored train window and the test chunk must independently clear `MIN_N` (a per-fold sample-size gate), and the test rate must confirm the train rate's same non-boundary side of 50% (an exact 50% train rate makes no directional prediction and cannot pass).
- The per-bucket aggregate `wf_verdict` (`walk_forward_verdict()`) requires a **majority — strictly more than 50% — of folds to pass** (`wf-robust`); exactly 50% is `wf-fragile`, not robust. `below-n` folds still count in the denominator.
- `validation_manifest_walkforward.csv` columns: `analysis, timeframe, instrument, direction, bucket, fold_index, train_end, test_end, train_rate, train_n, test_rate, test_n, fold_verdict, wf_verdict`.

## Post-CISD Context — Corrected Re-Validation (v2.0)

This section extends the badge vocabulary with a fourth, strictly harder tier: **✓ CORRECTED-BAR CLEARED**. Under the D-02 three-condition AND, a bucket must have discovery `corrected_pass`, walk-forward `wf_verdict == 'wf-robust'`, **and** a sacred-OOS rate on the same side of `0.50` as discovery. This is stricter than **✓ CONFIRMED**, which checks the OOS same-side condition without the FDR-correction and walk-forward legs. **not-cleared** means the tag did not clear this corrected bar; it does not replace the existing **✗ NOT CONFIRMED** or **below-n / not a finding** states.

| analysis | tag | n_buckets | n_cleared | verdict |
|---|---|---:|---:|---|
| candle1_followthrough | against_forward | 16 | 12 | cleared |
| candle1_followthrough | against_inwindow | 16 | 12 | cleared |
| candle1_followthrough | with_past_wick_forward | 16 | 12 | cleared |
| candle1_followthrough | with_past_wick_inwindow | 16 | 12 | cleared |
| candle1_followthrough | with_within_wick_forward | 16 | 8 | not-cleared |
| candle1_followthrough | with_within_wick_inwindow | 16 | 9 | cleared |
| post_cisd_context | candle2_past_candle1_wick | 16 | 12 | cleared |
| post_cisd_context | failed_gap_against | 16 | 10 | cleared |
| post_cisd_context | failed_gap_against_neither | 16 | 10 | cleared |
| post_cisd_context | failed_gap_against_reversal | 16 | 10 | cleared |
| post_cisd_context | failed_gap_flat | 16 | 10 | cleared |
| post_cisd_context | failed_gap_with | 16 | 11 | cleared |

For the `failed_gap_against` reversal-barrier reading, the mutually exclusive outcomes partition the same population. Discovery is **32.9% continuation** (`failed_gap_against`, n=23,247), **59.2% reversal** (n=23,247), and **7.9% neither** (n=23,247). Sacred OOS is **34.3% continuation** (n=10,706), **57.8% reversal** (n=10,706), and **7.9% neither** (n=10,706). The majority therefore reverse after a failed-gap-against CISD; that reversal rate is distinct from, and is not conflated with, the continuation rate in the CISD direction.

## Conditioning Features — Magnitude, Session & Volume Anomaly (v2.0)

Phase 10 (RES-07) adds three economically-motivated conditioning-feature families on top of the existing binary flags, each pushed through the **full corrected harness** (n ≥ 50 gate, Wilson CI, one global Benjamini-Hochberg FDR correction, and walk-forward robustness) with **zero harness change** — every new analysis is an additive standalone `compute_*` / `chart_*` / `ANALYSES` entry (the Phase-9 "new feature = additive standalone analysis" pattern). All **408 new discovery buckets are published**, including those that do not clear the bar — the point is to hand Phase 11's model economically-motivated, harness-validated inputs rather than let it mine noise.

**Families:**

1. **Magnitude** — continuous ATR-normalized versions of existing binary flags: `wick_distance` (signed distance past the prior wick, with a bin edge exactly at 0 so the old past/within split stays recoverable), `sweep_depth` (how far the CISD extreme pierced the swept level), `fvg_size` (gap width).
2. **Session / time-of-day** — the engine's first temporal dimension: a frozen 3-bucket `rth_open` (09:30–10:30 ET) / `rth` (10:30–16:00) / `overnight` (16:00–09:30) split from the tz-naive ET index, with no timezone or DST math. Registered on **15min and 1H only** — a session tag on a Daily/4H bar spans multiple sessions and is economically meaningless, and would only add below-n cells that dilute the global FDR family.
3. **Volume anomaly** — measures beyond the already-negligible 1-bar volume ratio (which stays untouched): `effort_result` (within-bar volume ÷ range, baseline-free), and slot-normalized `rvol` / `volume_zscore` (same-time-of-day trailing baseline, frozen `K=20`, so the intraday volume profile is *removed* rather than *measured*).

**Badges in this section.** `corrected` is the discovery **BH-FDR** verdict (`corrected_pass = min_n_pass AND bh_significant`); `below-n` = discovery n < 50; `✗ NOT CONFIRMED` = eligible but did not clear the corrected bar. `OOS` is the sacred-holdout rate; `walk-fwd` is the expanding-window `wf_verdict`. The strongest evidence is a bucket that is corrected-confirmed **and** walk-forward `wf-robust` **and** whose OOS rate holds the discovery side of 0.50. All frozen bins were shape-informed **once** from the discovery-slice histogram (index < `OOS_START`, ~225k obs) **outcome-blind** — chosen from the distribution, never tuned to hit rates — then frozen in-code.

### Summary — 408 new discovery buckets

| feature | ✓ confirmed | ✗ not-conf | below-n | wf-robust | wf-fragile |
|---|--:|--:|--:|--:|--:|
| wick_distance | 44 | 12 | 8 | 32 | 32 |
| sweep_depth | 30 | 7 | 27 | 16 | 48 |
| fvg_size | 44 | 0 | 20 | 16 | 48 |
| effort_result | 30 | 8 | 26 | 28 | 36 |
| rvol | 45 | 13 | 6 | 37 | 27 |
| volume_zscore | 47 | 13 | 4 | 36 | 28 |
| session | 24 | 0 | 0 | 20 | 4 |

(wf-robust / wf-fragile count each bucket once; the confirmed/not-confirmed/below-n split is the discovery BH-FDR verdict.)

### Representative results

**Magnitude · signed wick distance — monotonic, the standout**  _(15min NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <-1x ATR (deep within wick) | 55.5% | 1880 | [53.2%–57.7%] | ✓ CONFIRMED | 53.9% | wf-robust |
| -1x-0 ATR (within wick) | 58.5% | 13354 | [57.7%–59.4%] | ✓ CONFIRMED | 58.0% | wf-robust |
| 0-1x ATR (past wick) | 72.2% | 5790 | [71.1%–73.4%] | ✓ CONFIRMED | 71.5% | wf-robust |
| >1x ATR (far past wick) | 76.2% | 491 | [72.2%–79.7%] | ✓ CONFIRMED | 76.4% | wf-robust |

**Magnitude · FVG size**  _(15min NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <0.5x ATR | 92.5% | 3913 | [91.6%–93.3%] | ✓ CONFIRMED | 92.4% | wf-robust |
| 0.5x-1x ATR | 92.3% | 888 | [90.4%–93.9%] | ✓ CONFIRMED | 93.8% | wf-robust |
| 1x-1.5x ATR | 89.8% | 283 | [85.7%–92.8%] | ✓ CONFIRMED | 92.7% | wf-robust |
| >1.5x ATR | 87.4% | 182 | [81.8%–91.4%] | ✓ CONFIRMED | 76.0% | wf-fragile |

**Magnitude · sweep depth — confirmed but flat (little gradient)**  _(15min NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <0.5x ATR | 70.5% | 664 | [66.9%–73.8%] | ✓ CONFIRMED | 71.3% | wf-robust |
| 0.5x-1x ATR | 72.1% | 458 | [67.8%–76.0%] | ✓ CONFIRMED | 70.2% | wf-robust |
| 1x-1.5x ATR | 71.5% | 354 | [66.6%–75.9%] | ✓ CONFIRMED | 68.1% | wf-robust |
| >1.5x ATR | 66.8% | 596 | [62.9%–70.4%] | ✓ CONFIRMED | 69.1% | wf-robust |

**Volume · slot-relative RVOL — monotonic**  _(15min NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <0.7x slot | 58.3% | 6723 | [57.1%–59.5%] | ✓ CONFIRMED | 58.7% | wf-robust |
| 0.7x-1x slot | 63.2% | 6670 | [62.0%–64.3%] | ✓ CONFIRMED | 61.9% | wf-robust |
| 1x-1.5x slot (elevated) | 64.7% | 5324 | [63.4%–65.9%] | ✓ CONFIRMED | 63.9% | wf-robust |
| >1.5x slot (spike) | 65.4% | 2359 | [63.5%–67.3%] | ✓ CONFIRMED | 66.2% | wf-robust |

**Volume · slot z-score — monotonic**  _(15min NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <-0.5 sigma | 58.8% | 8093 | [57.7%–59.9%] | ✓ CONFIRMED | 59.3% | wf-robust |
| -0.5-0.5 sigma | 63.7% | 8510 | [62.7%–64.7%] | ✓ CONFIRMED | 62.7% | wf-robust |
| 0.5-1.5 sigma | 66.0% | 2794 | [64.2%–67.7%] | ✓ CONFIRMED | 64.7% | wf-robust |
| >1.5 sigma (spike) | 65.3% | 1679 | [63.0%–67.6%] | ✓ CONFIRMED | 64.8% | wf-robust |

**Volume · effort-vs-result — noisy / TF-scale-fragmented**  _(15min ES bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| <150 | 62.5% | 8 | [30.6%–86.3%] | below-n | 68.9% | wf-fragile |
| 150-550 | 65.8% | 4124 | [64.3%–67.2%] | ✓ CONFIRMED | 63.7% | wf-robust |
| 550-1500 | 61.2% | 8294 | [60.2%–62.3%] | ✓ CONFIRMED | 59.5% | wf-robust |
| >1500 | 61.7% | 7742 | [60.6%–62.8%] | ✓ CONFIRMED | 61.5% | wf-robust |

**Session · time-of-day — rth_open > rth > overnight**  _(1H NQ bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| rth_open | 67.4% | 227 | [61.1%–73.2%] | ✓ CONFIRMED | 63.4% | wf-fragile |
| rth | 66.1% | 1143 | [63.3%–68.7%] | ✓ CONFIRMED | 64.7% | wf-robust |
| overnight | 59.8% | 4092 | [58.2%–61.2%] | ✓ CONFIRMED | 62.7% | wf-robust |

**Session · time-of-day**  _(15min ES bullish)_

| bucket | disc rate | n | Wilson CI | corrected | OOS | walk-fwd |
|---|--:|--:|:--:|:--:|--:|:--:|
| rth_open | 66.3% | 879 | [63.1%–69.4%] | ✓ CONFIRMED | 69.2% | wf-robust |
| rth | 64.8% | 4838 | [63.4%–66.1%] | ✓ CONFIRMED | 63.2% | wf-robust |
| overnight | 61.3% | 14451 | [60.5%–62.1%] | ✓ CONFIRMED | 60.9% | wf-robust |

### Interpretation

- **`wick_distance` — the standout.** The signed magnitude is cleanly monotonic and genuinely subsumes the binary wick split: continuation climbs deep-within → within → just-past → far-past-wick (≈55% → 58% → 72% → 76%+), holding out-of-sample and walk-forward-robust across the high-n intraday timeframes. It enriches `compute_wick`, it does not merely restate it.
- **`fvg_size`.** Small FVGs (< 0.5× ATR) continue ≈90–95%; the rate softens and turns walk-forward-fragile for the largest gaps (> 1.5× ATR — e.g. 15min NQ bull OOS 76%, `wf-fragile`). Tight gaps are the higher-continuation regime.
- **`session`.** A clean, fully-confirmed temporal ordering — `rth_open` > `rth` > `overnight` — on both 1H and 15min: the opening-drive hour carries the highest CISD continuation. The engine's first temporal edge.
- **`rvol` / `volume_zscore`.** A modest but consistent, monotonic, walk-forward-robust anomaly signal — higher slot-relative volume → higher continuation — and the two independent measures agree.
- **`sweep_depth`.** Confirmed but **flat** across depth (≈67–72%, no gradient): the pierce-depth magnitude adds little beyond the binary sweep flag it enriches.
- **`effort_result`.** The weakest and noisiest — its raw baseline-free ratio has a scale that differs sharply across timeframes (D-07), fragmenting the fixed bins so Daily/4H buckets are mostly below-n while the intraday buckets confirm without a strong gradient.

### Honesty caveats (D-11)

- **OHLCV-only limitation.** These volume features are **unsigned effort / anomaly proxies** computed from OHLCV alone. No signed or delta **order flow** is available on this data, so none of them can distinguish buying from selling pressure — they measure *how much* volume/effort, never *which side*. Read them as activity-intensity conditioning, not order flow.
- **Slot-normalization is partial.** The slot baseline (same time-of-day, trailing `K=20`) neutralizes **most but not necessarily all** of the intraday volume profile. A residual seasonality can survive, especially in the thin/heterogeneous overnight window (Asia / London / pre-market differ), so `rvol` / `volume_zscore` should not be read as fully seasonality-free.

### No silent drift (D-12 / D-13)

- **Existing base rates are byte-stable (D-12).** All **19 pre-existing analyses'** published `rate / n / successes / ci_low / ci_high / min_n_pass` are unchanged — the seven new features are purely additive standalone analyses that touch no existing compute or annotation column. This is enforced by `scripts/build_conditioning_report.py`, a drift gate that exits non-zero on any change to an existing analysis's base columns, run against the golden manifest before it is refreshed.
- **Moved corrected verdicts are correct, not drift (D-13).** Adding ~408 buckets **does** shift the `bh_q_value` / `corrected_pass` of some *existing* buckets, because `apply_bh_correction` builds **one global BH family** across every analysis × timeframe × instrument × direction in the discovery slice — never grouped per-analysis-key. A moved corrected verdict is the correct consequence of honestly accounting for more tested hypotheses (exactly what MHT-01 is for), **not** a base-rate drift: the base rates themselves do not move (proven by the drift gate); only the multiple-comparisons-corrected verdicts — which are the additive `bh_*` columns — do.

## Configuration

Edit constants at the top of `cisd_analysis.py`:
- `LOOKAHEAD`: Bars to check ahead (Default: `2`).
- `MAX_CONSEC`: Max consecutive candles for Markov (Default: `3`).
- `TIMEFRAMES`: Resampling rules (Default: `Daily`, `4H`, `1H`, `15min`).
- `FVG_HOLD_LOOKAHEAD`: Bars used to judge whether a linked FVG held (Default: `10`).
- `SWEEP_TOLERANCE`: Bars in the CISD-relative sweep window `[t-4, t]` (Default: `5`).
- `SWEEP_SWING_LOOKBACK`: Lookback used to source prior swing points for sweeps (Default: `20`).
- Swing SMT support depends on the local SMT package at `/mnt/e/backup/code/Finance/Misc/SMT`.

## Requirements

- Python 3.12 (3.12.3 verified)
- Install pinned runtime: `pip install -r requirements.txt`
- Core libraries pinned in `requirements.txt`: `pandas==3.0.2`, `numpy==2.4.4`, `matplotlib==3.10.8`, `pyarrow==23.0.1`, `pytest==9.0.2`
- Plotly.js is loaded from CDN inside the generated `output/forward_returns.html` and is never pip-installed
