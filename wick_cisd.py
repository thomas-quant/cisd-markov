import pandas as pd
import numpy as np

DATA_PATH = 'cisd_data.csv'
LOOKAHEAD_BARS = 2

# Load and prepare data
df = pd.read_csv(DATA_PATH, parse_dates=['Local time'])
df.rename(columns={'Local time':'timestamp','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
df.set_index('timestamp', inplace=True)

df['direction'] = np.where(df['close']<df['open'],'bearish',np.where(df['close']>df['open'],'bullish','neutral'))
df['prev_close'] = df['close'].shift(1)
df['prev_direction'] = df['direction'].shift(1)
df['prev_high'] = df['high'].shift(1)
df['prev_low'] = df['low'].shift(1)

# Prepare CISDs
df_bull = df[(df['prev_direction']=='bearish') & (df['close']>df['prev_close'])]
df_bear = df[(df['prev_direction']=='bullish') & (df['close']<df['prev_close'])]

# Initialize stats
stats = {
    'bullish': {'above_wick': {'total':0,'runs':0}, 'within_wick': {'total':0,'runs':0}},
    'bearish': {'below_wick': {'total':0,'runs':0}, 'within_wick': {'total':0,'runs':0}}
}

dx = df.index
# Bullish CISD: compare close to prev_high
for ts, row in df_bull.iterrows():
    idx = dx.get_loc(ts)
    grp = 'above_wick' if row['close']>row['prev_high'] else 'within_wick'
    stats['bullish'][grp]['total'] += 1
    future = df.iloc[idx+1:idx+1+LOOKAHEAD_BARS]
    if future.empty: continue
    if (future['high']>=row['high']).any(): stats['bullish'][grp]['runs'] += 1

# Bearish CISD: compare close to prev_low
for ts, row in df_bear.iterrows():
    idx = dx.get_loc(ts)
    grp = 'below_wick' if row['close']<row['prev_low'] else 'within_wick'
    stats['bearish'][grp]['total'] += 1
    future = df.iloc[idx+1:idx+1+LOOKAHEAD_BARS]
    if future.empty: continue
    if (future['low']<=row['low']).any(): stats['bearish'][grp]['runs'] += 1

# Print results
print("BULLISH CISDs:")
for grp_label, grp in stats['bullish'].items():
    t = grp['total']; r = grp['runs']
    pct = r/t*100 if t>0 else np.nan
    label = 'Closes above wick' if grp_label=='above_wick' else 'Closes within wick'
    print(f"  {label}: {r}/{t} = {pct:.2f}%")

print("\nBEARISH CISDs:")
for grp_label, grp in stats['bearish'].items():
    t = grp['total']; r = grp['runs']
    pct = r/t*100 if t>0 else np.nan
    label = 'Closes below wick' if grp_label=='below_wick' else 'Closes within wick'
    print(f"  {label}: {r}/{t} = {pct:.2f}%")
