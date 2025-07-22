import pandas as pd
import numpy as np

DATA_PATH = 'cisd_data.csv'
LOOKAHEAD_BARS = 2

# Load and prepare data
df = pd.read_csv(DATA_PATH, parse_dates=['Local time'])
df.rename(columns={'Local time':'timestamp','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
df.set_index('timestamp', inplace=True)

# Determine candle directions
df['direction'] = np.where(df['close']<df['open'],'bearish', np.where(df['close']>df['open'],'bullish','neutral'))
df['prev_direction'] = df['direction'].shift(1)

# Identify CISD candles
df['cisd_type'] = np.select([
    (df['prev_direction']=='bearish') & (df['close']>df['close'].shift(1)),
    (df['prev_direction']=='bullish') & (df['close']<df['close'].shift(1))
], ['bullish','bearish'], None)
df_cisd = df[df['cisd_type'].notna()].copy()

# Initialize counters
results = {'bullish': {'low_first':0,'high_first':0,'total':0},
           'bearish': {'high_first':0,'low_first':0,'total':0}}
idxs = df.index

for ts, row in df_cisd.iterrows():
    i = idxs.get_loc(ts)
    ctype = row['cisd_type']
    results[ctype]['total'] += 1
    low_target = row['low']
    high_target = row['high']
    # look ahead bars
    first = None
    for j in range(1, LOOKAHEAD_BARS+1):
        if i+j >= len(df): break
        bar = df.iloc[i+j]
        if ctype == 'bullish':
            if bar['low'] <= low_target and first is None:
                first = 'low'
            if bar['high'] >= high_target and first is None:
                first = 'high'
        else:
            if bar['high'] >= high_target and first is None:
                first = 'high'
            if bar['low'] <= low_target and first is None:
                first = 'low'
    if first:
        key = 'low_first' if (ctype=='bullish' and first=='low') or (ctype=='bearish' and first=='low') else 'high_first'
        results[ctype][key] += 1

# Print results
for ctype in ['bullish','bearish']:
    print(f"\n{ctype.upper()} CISDs: {results[ctype]['total']} events")
    lf = results[ctype]['low_first']
    hf = results[ctype]['high_first']
    tot = results[ctype]['total']
    print(f"  Low crossed first: {lf}/{tot} = {lf/tot*100:.2f}%")
    print(f"  High crossed first: {hf}/{tot} = {hf/tot*100:.2f}%")