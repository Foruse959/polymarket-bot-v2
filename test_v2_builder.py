#!/usr/bin/env python3
"""Test V2 order with builder API creds."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from config import Config
from py_clob_client_v2 import ClobClient as V2Client
from py_clob_client_v2.clob_types import OrderArgs as OrderArgsV2, OrderType as V2OrderType, PartialCreateOrderOptions, ApiCreds as V2ApiCreds, BuilderConfig as V2BuilderConfig
import time, json, requests

print("=" * 60)
print("V2 + BUILDER API CREDS TEST")
print("=" * 60)

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()

# V2 client WITH builder config
builder_code = Config.POLY_BUILDER_CODE.strip() if Config.POLY_BUILDER_CODE else '0x0000000000000000000000000000000000000000000000000000000000000000'
builder_config = V2BuilderConfig(
    builder_address=Config.POLY_PROXY_WALLET.strip(),
    builder_code=builder_code,
)

client = V2Client(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=pk,
    signature_type=2,
    funder=funder,
    builder_config=builder_config,
)

# Method 1: Try builder creds as API key
print("\nSetting builder creds as API key...")
api_creds = V2ApiCreds(
    api_key=Config.POLY_BUILDER_API_KEY.strip(),
    api_secret=Config.POLY_BUILDER_SECRET.strip(),
    api_passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
)
client.set_api_creds(api_creds)
print("Builder creds set as API key")

# Test connection
try:
    ok = client.get_ok()
    print(f"Connection: {ok}")
except Exception as e:
    print(f"Connection test: {e}")

# Find market
now = int(time.time())
rounded = (now // 300) * 300 + 300
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
    
    # Get orderbook
    r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
    best_bid = 0.45
    if r2.status_code == 200:
        book = r2.json()
        bids = [(float(b['price']), float(b['size'])) for b in book.get('bids', [])]
        bids.sort(key=lambda x: x[0], reverse=True)
        best_bid = bids[0][0] if bids else 0.45
        print(f"Best bid: {best_bid}")
    
    print(f"\nPlacing V2 FOK BUY 1.0 shares @ ${best_bid:.2f}")
    
    order_args = OrderArgsV2(
        token_id=down_token,
        side="BUY",
        price=best_bid,
        size=1.0,
        builder_code=builder_code,
    )
    
    options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)
    
    try:
        signed = client.create_order(order_args, options)
        print(f"Signed order: {type(signed)}")
        resp = client.post_order(signed, V2OrderType.FOK)
        print(f"RESPONSE: {resp}")
    except Exception as e:
        print(f"V2 Order failed: {e}")
        import traceback
        traceback.print_exc()

    # Method 2: Try create_api_key first
    print("\n\n--- METHOD 2: create_api_key ---")
    try:
        client2 = V2Client(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=pk,
            signature_type=2,
            funder=funder,
            builder_config=builder_config,
        )
        # Create API key on the server
        print("Creating API key on server...")
        try:
            new_creds = client2.create_api_key()
            print(f"Created: {new_creds.api_key[:20]}...")
            client2.set_api_creds(new_creds)
        except Exception as e:
            print(f"Create failed: {e}, trying derive...")
            new_creds = client2.derive_api_key()
            print(f"Derived: {new_creds.api_key[:20]}...")
            client2.set_api_creds(new_creds)
        
        signed2 = client2.create_order(order_args, options)
        resp2 = client2.post_order(signed2, V2OrderType.FOK)
        print(f"METHOD 2 RESPONSE: {resp2}")
    except Exception as e:
        print(f"Method 2 failed: {e}")
else:
    print("NO MARKET FOUND")