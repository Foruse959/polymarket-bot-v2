#!/usr/bin/env python3
"""Test Gamma client market discovery"""
import sys
sys.path.insert(0, '.')

from data.gamma_client import GammaClient
from config import Config

print("Testing Gamma Client...")
print(f"Enabled coins: {Config.ENABLED_COINS}")
print(f"Enabled timeframes: {Config.ENABLED_TIMEFRAMES}")
print()

client = GammaClient()
markets = client.discover_markets()

print(f"\n{'='*60}")
print(f"Found {len(markets)} matching markets")
print(f"{'='*60}")

for m in markets:
    print(f"\n🎯 {m['coin']} {m['timeframe']}m")
    print(f"   ID: {m['market_id']}")
    print(f"   Q: {m['question'][:60]}")
    print(f"   UP token: {m['up_token_id'][:20] if m['up_token_id'] else 'None'}...")
    print(f"   DOWN token: {m['down_token_id'][:20] if m['down_token_id'] else 'None'}...")
    print(f"   Ends in: {m['seconds_remaining']}s")
