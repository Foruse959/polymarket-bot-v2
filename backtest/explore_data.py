import pandas as pd
import sys

df = pd.read_parquet('C:/Users/acer/.openclaw/workspace/5min_trade_v2/data/markets.parquet')
resolved = df[df['closed'] == 1]
print(f'Resolved markets: {len(resolved)}')
print(f'Volume stats:')
print(resolved['volume'].describe())
# Date range
print(f'Date range: {resolved["created_at"].min()} to {resolved["created_at"].max()}')
# Check for 5min markets
min5 = resolved[resolved['question'].str.contains('Up or Down', na=False)]
print(f'5-min Up/Down markets: {len(min5)}')
# Categories
print(f'Sample questions:')
for q in resolved['question'].head(20):
    print(f'  {q}')