#!/usr/bin/env python3
"""Test V1 order placement with builder config."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from config import Config
from py_clob_client.client import ClobClient as V1Client
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds
from py_clob_client.order_builder.constants import BUY
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
import time, json, requests

print("=" * 60)
print("V1 + BUILDER ORDER TEST")
print("=" * 60)

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()

# V1 client WITH builder config
builder_config = BuilderConfig(
    local_builder_creds=BuilderApiKeyCreds(
        key=Config.POLY_BUILDER_API_KEY.strip(),
        secret=Config.POLY_BUILDER_SECRET.strip(),
        passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
    )
)

client = V1Client(
    host="https://clob.polymarket.com",
    key=pk,
    chain_id=137,
    signature_type=2,
    funder=funder,
    builder_config=builder_config,
)

# Try to set builder API creds as L2 auth instead of derived
print("Setting builder API creds as L2 auth...")
api_creds = ApiCreds(
    api_key=Config.POLY_BUILDER_API_KEY.strip(),
    api_secret=Config.POLY_BUILDER_SECRET.strip(),
    api_passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
)
client.set_api_creds(api_creds)

# Test connection
try:
    ok = client.get_ok()
    print(f"Connection: {ok}")
except Exception as e:
    print(f"Connection test: {e}")

# Find market
now = int(time.time())
rounded = (now // 300) * 300 + 300  # next epoch
slug = f"btc-updown-5m-{rounded}"

print(f"\nFinding market: {slug}")
r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if events:
    market = events[0].get('markets', [])[0]
    clob_ids = json.loads(market.get('clobTokenIds', '[]'))
    down_token = clob_ids[1] if len(clob_ids) > 1 else None
    print(f"DOWN token: {down_token[:20]}...")
    
    # Get orderbook for price
    r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
    if r2.status_code == 200:
        book = r2.json()
        bids = [(float(b['price']), float(b['size'])) for b in book.get('bids', [])]
        asks = [(float(a['price']), float(a['size'])) for a in book.get('asks', [])]
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])
        best_bid = bids[0][0] if bids else 0.45
        best_ask = asks[0][0] if asks else 0.55
        print(f"Best bid: {best_bid}, Best ask: {best_ask}")
    else:
        best_bid = 0.45
    
    print(f"\nPlacing FOK BUY 1 share @ ${best_bid:.2f} (DOWN token)")
    
    order_args = OrderArgs(
        token_id=down_token,
        side=BUY,
        price=best_bid,
        size=1.0,
    )
    
    try:
        signed = client.create_order(order_args)
        print(f"Signed order created: {type(signed)}")
        resp = client.post_order(signed, OrderType.FOK)
        print(f"ORDER RESPONSE: {resp}")
    except Exception as e:
        print(f"Order failed: {e}")
else:
    print("NO MARKET FOUND")