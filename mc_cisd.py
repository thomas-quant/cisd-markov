import pandas as pd
import numpy as np

# Configuration
DATA_PATH = 'cisd_data.csv'  # Path to your CISD CSV file
LOOKAHEAD_BARS = 2           # Number of bars after the CISD to check for a run
MAX_CONSEC = 3               # Maximum number of consecutive candles to test

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
df['direction'] = np.where(df['close'] < df['open'], 'bearish',
                           np.where(df['close'] > df['open'], 'bullish', 'neutral'))

# Identify CISD candles
df['prev_close'] = df['close'].shift(1)
df['prev_direction'] = df['direction'].shift(1)
conditions = [
    (df['prev_direction'] == 'bearish') & (df['close'] > df['prev_close']),
    (df['prev_direction'] == 'bullish') & (df['close'] < df['prev_close'])
]
choices = ['bullish', 'bearish']
df['cisd_type'] = np.select(conditions, choices, default=None)

df_cisd = df[df['cisd_type'].notna()].copy()

# Function to count consecutive opposite-direction candles before idx
def count_consecutive(idx, directions, target_dir, max_n):
    count = 0
    for i in range(1, max_n + 1):
        pos = idx - i
        if pos < 0:
            break
        if directions.iloc[pos] == target_dir:
            count += 1
        else:
            break
    return count

# Initialize stats
stats = {
    ctype: {n: {'total': 0, 'runs': 0} for n in range(1, MAX_CONSEC + 1)}
    for ctype in ['bullish', 'bearish']
}

directions = df['direction']
de = df.index

# Populate stats
for ts, row in df_cisd.iterrows():
    idx = de.get_loc(ts)
    ctype = row['cisd_type']
    target_dir = 'bearish' if ctype == 'bullish' else 'bullish'
    consec = count_consecutive(idx, directions, target_dir, MAX_CONSEC)
    if consec < 1 or consec > MAX_CONSEC:
        continue
    stats[ctype][consec]['total'] += 1
    future = df.iloc[idx + 1: idx + 1 + LOOKAHEAD_BARS]
    if future.empty:
        continue
    if ctype == 'bullish':
        ran = (future['high'] >= row['high']).any()
    else:
        ran = (future['low'] <= row['low']).any()
    if ran:
        stats[ctype][consec]['runs'] += 1

# Print summary
for ctype in ['bullish', 'bearish']:
    print(f"\n{ctype.upper()} CISDs segmented by consecutive opposite candles:")
    for n in range(1, MAX_CONSEC + 1):
        total = stats[ctype][n]['total']
        runs = stats[ctype][n]['runs']
        pct = (runs / total * 100) if total > 0 else np.nan
        print(f"  {n} consecutive before: {total} events; Runs: {runs}/{total} = {pct:.2f}%")