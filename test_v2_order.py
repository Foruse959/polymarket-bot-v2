#!/usr/bin/env python3
"""Test V2 order placement."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from config import Config
from data.clob_client import ClobClient
import time, json, requests

print("=" * 60)
print("V2 ORDER PLACEMENT TEST")
print("=" * 60)

# 1. Init CLOB client
clob = ClobClient()
pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()
sig_type = Config.POLY_SIGNATURE_TYPE

print(f"\nPK: {pk[:8]}...{pk[-4:]}")
print(f"Funder: {funder[:10]}...{funder[-4:]}")
print(f"Sig type: {sig_type}")
print(f"Builder code: {Config.POLY_BUILDER_CODE[:10]}..." if Config.POLY_BUILDER_CODE else "No builder code")

client = clob.init_py_clob_client(pk, funder=funder, signature_type=sig_type)

if not client:
    print("FAILED to init CLOB client")
    sys.exit(1)

print(f"\nV2 client type: {type(client).__module__}.{type(client).__name__}")
print(f"Is V2: {clob._is_v2}")

# 2. Find current market
now = int(time.time())
rounded = (now // 300) * 300
slug = f"btc-updown-5m-{rounded}"

print(f"\nFinding market: {slug}")
r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if not events:
    # Try next epoch
    rounded += 300
    slug = f"btc-updown-5m-{rounded}"
    print(f"Trying next epoch: {slug}")
    r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])

if not events:
    print("NO MARKET FOUND")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1] if len(clob_ids) > 1 else None
slug_found = events[0].get('slug', 'unknown')
print(f"Found: {slug_found}")
print(f"DOWN token: {down_token[:20]}...")

# 3. Get orderbook first
print(f"\nFetching orderbook...")
book = clob.get_orderbook(down_token)
if book:
    print(f"Best bid: {book['best_bid']}, Best ask: {book['best_ask']}, Mid: {book['mid_price']}")
    bid_price = book['best_bid']
else:
    print("No orderbook, using default price")
    bid_price = 0.45

# 4. Place a minimal FOK order ($1)
print(f"\n{'='*60}")
print(f"PLACING ORDER: BUY DOWN @ ${bid_price:.2f} for $1.00")
print(f"{'='*60}")

result = clob.place_market_order(
    token_id=down_token,
    side="BUY",
    size_usdc=1.00,  # $1 minimum
    price=bid_price,
)

print(f"\n{'='*60}")
print(f"ORDER RESULT:")
print(f"{'='*60}")
if result:
    for k, v in result.items():
        print(f"  {k}: {v}")
else:
    print("ORDER FAILED - No result returned")