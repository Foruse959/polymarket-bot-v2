import os, sys, json, time
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from config import Config
from py_clob_client_v2 import ClobClient as V2Client
from py_clob_client_v2.clob_types import OrderArgs as OrderArgsV2, PartialCreateOrderOptions, BuilderConfig as V2BuilderConfig, OrderType as V2OrderType
import requests

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()
builder_code = Config.POLY_BUILDER_CODE.strip() if Config.POLY_BUILDER_CODE else '0x' + '0'*64

builder_config = V2BuilderConfig(
    builder_address=Config.POLY_PROXY_WALLET.strip(),
    builder_code=builder_code,
)

# Create client with sig_type=2
client = V2Client(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=2,
    funder=funder,
    builder_config=builder_config,
)

# Derive API key (from EOA)
creds = client.derive_api_key()
client.set_api_creds(creds)
print(f"Derived API key: {creds.api_key}")

# Get current market token
now = int(time.time())
rounded = (now // 300) * 300 + 300
r = requests.get(f'https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{rounded}', timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])
if not events:
    print("No market found")
    sys.exit(1)

market = events[0].get('markets', [])[0]
import json as _json
clob_ids = _json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1]

# Get orderbook for price
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
if r2.status_code == 200:
    book = r2.json()
    bids = [(float(b['price']), float(b['size'])) for b in book.get('bids', [])]
    bids.sort(key=lambda x: x[0], reverse=True)
    best_bid = bids[0][0] if bids else 0.45
else:
    best_bid = 0.45

print(f"Best bid: {best_bid}")
print(f"Using DOWN token: {down_token[:30]}...")

# Method: Use create_and_post_order (handles version mismatches internally)
print("\n--- Using create_and_post_order ---")
order_args = OrderArgsV2(
    token_id=down_token,
    side="BUY",
    price=best_bid,
    size=1.0,
    builder_code=builder_code,
)

options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

try:
    result = client.create_and_post_order(
        order_args=order_args,
        options=options,
        order_type=V2OrderType.FOK,
    )
    print(f"Result: {result}")
except Exception as e:
    print(f"create_and_post_order failed: {e}")
    
# Also try posting manually with detailed error
print("\n--- Manual create + post ---")
try:
    signed = client.create_order(order_args, options)
    print(f"Order created, posting...")
    # Post with retry on version
    result2 = client.post_order(signed, V2OrderType.FOK)
    print(f"Post result: {result2}")
except Exception as e:
    print(f"Manual post failed: {e}")
    import traceback
    traceback.print_exc()

# Also try: POST directly with requests to see raw error
print("\n--- Raw HTTP test ---")
try:
    signed = client.create_order(order_args, options)
    
    # Serialize order manually
    from py_clob_client_v2.order_utils.serialization import order_to_json_v2
    payload = order_to_json_v2(signed, creds.api_key, "FOK", False, False)
    
    # Get L2 headers
    from py_clob_client_v2.clob_types import RequestArgs
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    request_args = RequestArgs(
        method="POST",
        request_path="/order",
        body=payload,
        serialized_body=serialized,
    )
    headers = client._l2_headers("POST", "/order", body=payload, serialized_body=serialized)
    
    resp = requests.post(
        "https://clob.polymarket.com/order",
        headers=headers,
        data=serialized,
        timeout=10,
    )
    print(f"Raw HTTP status: {resp.status_code}")
    print(f"Raw HTTP response: {resp.text[:500]}")
except Exception as e:
    print(f"Raw HTTP test failed: {e}")