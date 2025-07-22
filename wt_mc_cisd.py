import pandas as pd
import numpy as np

# Configuration
DATA_PATH = 'cisd_data.csv'
LOOKAHEAD_BARS = 2
MAX_CONSEC = 3

# Load data
cols = ['Local time','Open','High','Low','Close','Volume']
df = pd.read_csv(DATA_PATH, parse_dates=['Local time'])[cols]
df.rename(columns={'Local time':'timestamp','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
df.set_index('timestamp', inplace=True)

# Direction and previous values
df['direction'] = np.where(df['close']<df['open'],'bearish',np.where(df['close']>df['open'],'bullish','neutral'))
df['prev_close'] = df['close'].shift(1)
df['prev_direction'] = df['direction'].shift(1)
df['prev_high'] = df['high'].shift(1)
df['prev_low'] = df['low'].shift(1)

# Identify CISDs
df['cisd_type'] = np.select([
    (df['prev_direction']=='bearish')&(df['close']>df['prev_close']),
    (df['prev_direction']=='bullish')&(df['close']<df['prev_close'])],
    ['bullish','bearish'],None)
df_cisd = df[df['cisd_type'].notna()].copy()

def count_consec(idx, directions, target, max_n):
    cnt=0
    for i in range(1,max_n+1):
        pos=idx-i
        if pos<0 or directions.iloc[pos]!=target: break
        cnt+=1
    return cnt

# Initialize stats structure
stats={}
for ctype in ['bullish','bearish']:
    stats[ctype]={}
    for n in range(1,MAX_CONSEC+1):
        stats[ctype][n]={'above_wick':{'total':0,'runs':0},'within_wick':{'total':0,'runs':0}}

dirs=df['direction']
id_index=df.index

# Populate stats
def check_run(future, row, ctype):
    if ctype=='bullish': return (future['high']>=row['high']).any()
    return (future['low']<=row['low']).any()

for ts,row in df_cisd.iterrows():
    idx=id_index.get_loc(ts)
    ctype=row['cisd_type']
    target_dir='bearish' if ctype=='bullish' else 'bullish'
    consec=count_consec(idx,dirs,target_dir,MAX_CONSEC)
    if consec<1 or consec>MAX_CONSEC: continue
    # Wick test
    if ctype=='bullish': above=row['close']>row['prev_high']
    else: above=row['close']<row['prev_low']
    grp='above_wick' if above else 'within_wick'
    stats[ctype][consec][grp]['total']+=1
    future=df.iloc[idx+1:idx+1+LOOKAHEAD_BARS]
    if future.empty: continue
    if check_run(future,row,ctype): stats[ctype][consec][grp]['runs']+=1

# Print summary
for ctype in ['bullish','bearish']:
    print(f"\n{ctype.upper()} CISDs combined test:")
    for n in range(1,MAX_CONSEC+1):
        for grp,label in [('above_wick','Closes above wick'),('within_wick','Closes within wick')]:
            tot=stats[ctype][n][grp]['total']
            run=stats[ctype][n][grp]['runs']
            pct=run/tot*100 if tot>0 else np.nan
            print(f"  {n} consec opp, {label}: {run}/{tot} = {pct:.2f}%")