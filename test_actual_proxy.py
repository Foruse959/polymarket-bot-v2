"""Try placing an order with the correct registered proxy (0x1a17) as funder"""
import os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType

pk = Config.POLY_PRIVATE_KEY
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'
# Use the ACTUAL registered proxy
actual_proxy = '0x1a175aF61505c1D6a359801Fed91952b9B4FA0E2'

print("=== Testing with actual registered proxy (0x1a17) ===")
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=2,  # Browser Proxy
    funder=actual_proxy,
)

creds = client.derive_api_key()
client.set_api_creds(creds)
print(f'API key: {creds.api_key}')

# Check server time
try:
    ok = client.get_ok()
    print(f'CLOB: {ok}')
except Exception as e:
    print(f'Connection error: {e}')

# Find a market
now = int(time.time())
rounded = (now // 300) * 300 + 300
slug = f'btc-updown-5m-{rounded}'
r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])
if not events:
    print("No market found!")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1]
print(f"Market: {market.get('question', 'N/A')}")
print(f"DOWN token: {down_token[:20]}...")

# Get orderbook
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
if r2.status_code == 200:
    book = r2.json()
    asks = [(float(a['price']), float(a['size'])) for a in book.get('asks', [])]
    bids = [(float(b['price']), float(b['size'])) for b in book.get('bids', [])]
    asks.sort(key=lambda x: x[0])
    best_ask = asks[0][0] if asks else 0.55
    print(f"Best ask: {best_ask} | Best bid: {bids[0][0] if bids else 'N/A'}")
else:
    best_ask = 0.55

# Try to place order
print(f"\nPlacing BUY 1 share @ {best_ask}...")
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=best_ask,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

try:
    result = client.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"ORDER RESULT: {result}")
except Exception as e:
    print(f"Order failed: {e}")
    error_str = str(e)
    if 'invalid signature' in error_str:
        print("\n>>> Invalid signature with actual proxy too!")
        print(">>> Need to check if the EOA-key-to-proxy mapping is correct on V2 exchange")
    elif 'insufficient' in error_str.lower():
        print("\n>>> Insufficient balance (expected - proxy has $0)")
    elif 'maker address' in error_str:
        print("\n>>> Maker address issue")

# Also try sig_type=0 (EOA) with actual proxy as funder
print("\n\n=== Testing sig_type=0 (EOA) with funder=actual_proxy ===")
client0 = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=0,
    funder=actual_proxy,
)
creds0 = client0.derive_api_key()
client0.set_api_creds(creds0)

try:
    result0 = client0.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"RESULT: {result0}")
except Exception as e:
    print(f"sig_type=0 failed: {e}")