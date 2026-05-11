#!/usr/bin/env python3
"""Test V1 client with builder config - check if builder headers fix the auth issue."""
import os, sys, time, json, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from config import Config
from py_clob_client.client import ClobClient as V1Client
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds
from py_clob_client.order_builder.constants import BUY
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds

print("=" * 60)
print("V1 + BUILDER CONFIG TEST")
print("=" * 60)

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()

# Set up builder config
builder_config = BuilderConfig(
    local_builder_creds=BuilderApiKeyCreds(
        key=Config.POLY_BUILDER_API_KEY.strip(),
        secret=Config.POLY_BUILDER_SECRET.strip(),
        passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
    )
)

# Initialize V1 client with builder_config
client = V1Client(
    host="https://clob.polymarket.com",
    key=pk,
    chain_id=137,
    signature_type=2,
    funder=funder,
    builder_config=builder_config,
)

# Check if builder auth is available
print(f"can_builder_auth: {client.can_builder_auth()}")

# First try: derive API key from private key
print("\n--- Test with derived API key ---")
api_creds = client.create_or_derive_api_creds()
client.set_api_creds(api_creds)
print(f"API key: {api_creds.api_key[:20]}...")

# Test connection
ok = client.get_ok()
print(f"CLOB connection: {ok}")

# Get API key info  
try:
    keys = client.get_api_keys()
    print(f"Active API keys: {len(keys) if keys else 0}")
    if keys:
        for k in keys[:3]:
            print(f"  Key: {k.get('key', k.get('apiKey', 'N/A'))[:20]}...")
except Exception as e:
    print(f"Get API keys failed: {e}")

# Find market
now = int(time.time())
rounded = (now // 300) * 300 + 300
slug = f"btc-updown-5m-{rounded}"

r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if not events:
    print("NO MARKET FOUND")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1]
print(f"DOWN token: {down_token[:20]}...")

# Get orderbook
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
if r2.status_code == 200:
    book = r2.json()
    bids = [(float(b['price']), float(b['size'])) for b in book.get('bids', [])]
    bids.sort(key=lambda x: x[0], reverse=True)
    best_bid = bids[0][0] if bids else 0.45
    print(f"Best bid: {best_bid}")
else:
    best_bid = 0.45

# Try to place FOK order $1
print(f"\nPlacing FOK BUY 1 share @ ${best_bid:.2f}")
order_args = OrderArgs(
    token_id=down_token,
    side=BUY,
    price=best_bid,
    size=1.0,
)

try:
    signed = client.create_order(order_args)
    print(f"Order created, posting via builder...")
    resp = client.post_order(signed, OrderType.FOK)
    print(f"RESPONSE: {resp}")
except Exception as e:
    print(f"Order failed: {e}")
    
    # Check if post_order tried builder headers
    import traceback
    
    # Now try with builder API creds directly as L2 auth
    print("\n--- Test with builder API key as L2 auth ---")
    builder_creds = ApiCreds(
        api_key=Config.POLY_BUILDER_API_KEY.strip(),
        api_secret=Config.POLY_BUILDER_SECRET.strip(),
        api_passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
    )
    client.set_api_creds(builder_creds)
    
    try:
        signed2 = client.create_order(order_args)
        resp2 = client.post_order(signed2, OrderType.FOK)
        print(f"RESPONSE (builder auth): {resp2}")
    except Exception as e2:
        print(f"Builder auth order also failed: {e2}")