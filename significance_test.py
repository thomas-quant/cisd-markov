import pandas as pd
import numpy as np

DATA_PATH = 'cisd_data.csv'
LOOKAHEAD = 2

df = pd.read_csv(DATA_PATH, parse_dates=['Local time'])
df.rename(columns={'Local time':'timestamp','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
df.set_index('timestamp', inplace=True)

totals = {'bullish': 0, 'bearish': 0}
runs = {'bullish': 0, 'bearish': 0}

for i in range(1, len(df) - LOOKAHEAD):
    prev_high = df['high'].iloc[i-1]
    prev_low = df['low'].iloc[i-1]
    curr_close = df['close'].iloc[i]

    # Bullish scenario: close above previous high
    if curr_close > prev_high:
        totals['bullish'] += 1
        h = df['high'].iloc[i]
        future = df['high'].iloc[i+1:i+1+LOOKAHEAD]
        if (future >= h).any():
            runs['bullish'] += 1

    # Bearish scenario: close below previous low
    if curr_close < prev_low:
        totals['bearish'] += 1
        l = df['low'].iloc[i]
        future_low = df['low'].iloc[i+1:i+1+LOOKAHEAD]
        if (future_low <= l).any():
            runs['bearish'] += 1

for ctype in ['bullish', 'bearish']:
    total = totals[ctype]
    run = runs[ctype]
    pct = run / total * 100 if total > 0 else np.nan
    label = 'Bullish' if ctype == 'bullish' else 'Bearish'
    print(f"{label} events: {total}")
    print(f"Runs within next {LOOKAHEAD} bars: {run}/{total} = {pct:.2f}%\n")