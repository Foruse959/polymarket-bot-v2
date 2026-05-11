import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from config import Config
from py_clob_client_v2 import ClobClient as V2Client
from py_clob_client_v2.clob_types import OrderArgs as OrderArgsV2, PartialCreateOrderOptions, OrderType as V2OrderType
import requests

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()

# Try sig_type=0 (EOA) first - no proxy wallet complications
print("=== TEST 1: sig_type=0 (EOA) ===")
client0 = V2Client(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=0,  # EOA
)

creds0 = client0.create_or_derive_api_key()
client0.set_api_creds(creds0)
print(f"API key: {creds0.api_key}")

# Try creating and posting
now = int(time.time())
rounded = (now // 300) * 300 + 300
r = requests.get(f'https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{rounded}', timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])
if not events:
    print("No market found")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1]

# Get price
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
bids = [(float(b['price']), float(b['size'])) for b in r2.json().get('bids', [])] if r2.status_code == 200 else []
bids.sort(key=lambda x: x[0], reverse=True)
best_bid = bids[0][0] if bids else 0.45
print(f"Best bid: {best_bid}")

order_args = OrderArgsV2(
    token_id=down_token,
    side="BUY",
    price=best_bid,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

try:
    result = client0.create_and_post_order(order_args, options, V2OrderType.FOK)
    print(f"RESULT: {result}")
except Exception as e:
    print(f"sig_type=0 FAILED: {e}")

# Test sig_type=1 (POLY_PROXY) 
print("\n=== TEST 2: sig_type=1 (POLY_PROXY) ===")
client1 = V2Client(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=1,  # POLY_PROXY (magic)
    funder=funder,
)
creds1 = client1.create_or_derive_api_key()
client1.set_api_creds(creds1)
print(f"API key: {creds1.api_key}")

order_args2 = OrderArgsV2(
    token_id=down_token,
    side="BUY",
    price=best_bid,
    size=1.0,
)

try:
    result2 = client1.create_and_post_order(order_args2, options, V2OrderType.FOK)
    print(f"RESULT: {result2}")
except Exception as e:
    print(f"sig_type=1 FAILED: {e}")

# Test sig_type=2 (Browser Proxy)
print("\n=== TEST 3: sig_type=2 (Browser Proxy) ===")
client2 = V2Client(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=2,  # Browser Proxy
    funder=funder,
)
creds2 = client2.create_or_derive_api_key()
client2.set_api_creds(creds2)
print(f"API key: {creds2.api_key}")

order_args3 = OrderArgsV2(
    token_id=down_token,
    side="BUY",
    price=best_bid,
    size=1.0,
)

try:
    result3 = client2.create_and_post_order(order_args3, options, V2OrderType.FOK)
    print(f"RESULT: {result3}")
except Exception as e:
    print(f"sig_type=2 FAILED: {e}")