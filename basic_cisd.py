import pandas as pd
import numpy as np

# Configuration
DATA_PATH = 'cisd_data.csv'  # Path to your CISD CSV file
LOOKAHEAD_BARS = 2           # Number of bars after the CISD to check for a run

# Load the data
# Expected columns: ['Local time', 'Open', 'High', 'Low', 'Close', 'Volume']
df = pd.read_csv(DATA_PATH, parse_dates=['Local time'])
df.rename(columns={
    'Local time': 'timestamp',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Close': 'close',
    'Volume': 'volume'
}, inplace=True)
df.set_index('timestamp', inplace=True)

# Identify candle direction
# bearish: close < open, bullish: close > open

df['direction'] = np.where(df['close'] > df['open'], 'bullish',
                           np.where(df['close'] < df['open'], 'bearish', 'neutral'))

# Identify CISD candles: current candle reverses previous
# Bullish CISD: previous bearish & current close > previous close
# Bearish CISD: previous bullish & current close < previous close
df['prev_close'] = df['close'].shift(1)
df['prev_direction'] = df['direction'].shift(1)
conditions = [
    (df['prev_direction'] == 'bearish') & (df['close'] > df['prev_close']),
    (df['prev_direction'] == 'bullish') & (df['close'] < df['prev_close'])
]
choices = ['bullish', 'bearish']
df['cisd_type'] = np.select(conditions, choices, default=None)

df_cisd = df[df['cisd_type'].notna()].copy()

# Counters for total CISDs and successes
totals = {'bullish': 0, 'bearish': 0}
runs = {'bullish': 0, 'bearish': 0}

# Check if any of the next LOOKAHEAD_BARS run past the CISD candle
for ts, row in df_cisd.iterrows():
    ctype = row['cisd_type']
    totals[ctype] += 1
    # Get next LOOKAHEAD_BARS candles
    future = df.loc[ts:].iloc[1:LOOKAHEAD_BARS+1]
    if future.empty:
        continue
    if ctype == 'bullish':
        # Check if any future high >= CISD high
        if (future['high'] >= row['high']).any():
            runs[ctype] += 1
    else:
        # bearish: any future low <= CISD low
        if (future['low'] <= row['low']).any():
            runs[ctype] += 1

# Print results
for ctype in ['bullish', 'bearish']:
    total = totals[ctype]
    run_count = runs[ctype]
    pct = (run_count / total * 100) if total > 0 else np.nan
    print(f"{ctype.upper()} CISDs: {total} events")
    print(f"  Runs within next {LOOKAHEAD_BARS} bars: {run_count} / {total} = {pct:.2f}%\n")