#!/usr/bin/env python3
"""Test fixed gamma client"""
import sys
sys.path.insert(0, '.')

from data.gamma_client import GammaClient

print("Testing Fixed Gamma Client...")
print("="*60)

client = GammaClient()
markets = client.discover_markets()

print(f"\n{'='*60}")
print(f"DISCOVERED {len(markets)} MARKETS:")
print('='*60)

for m in markets:
    print(f"\n{m['coin']} {m['timeframe']}m")
    print(f"  ID: {m['market_id']}")
    print(f"  UP: {m['up_token_id'][:30]}...")
    print(f"  DOWN: {m['down_token_id'][:30]}...")
