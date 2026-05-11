"""Test sig_type=2 with proper order size - this passed the signer check!"""
import os, sys, json, time, requests

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType

pk = os.getenv('POLY_PRIVATE_KEY')
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'

# Derive API key
client = ClobClient(host='https://clob.polymarket.com', chain_id=137, key=pk)
creds = client.create_or_derive_api_key()
print(f"API key: {creds.api_key}")

# Find market
now = int(time.time())
rounded = (now // 300) * 300 + 300
r = requests.get("https://gamma-api.polymarket.com/events",
                  params={"slug": f"btc-updown-5m-{rounded}"}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get("events", [])
if not events:
    r = requests.get("https://gamma-api.polymarket.com/events",
                      params={"slug": f"btc-updown-5m-{rounded+300}"}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get("events", [])

if not events:
    print("No market found! Trying ETH...")
    for offset in [0, 300, 600, 900]:
        r = requests.get("https://gamma-api.polymarket.com/events",
                          params={"slug": f"eth-updown-5m-{rounded+offset}"}, timeout=10)
        data = r.json()
        events = data if isinstance(data, list) else data.get("events", [])
        if events:
            break

if not events:
    print("No updown markets found!")
    sys.exit(1)

market = events[0].get("markets", [])[0]
clob_ids = json.loads(market.get("clobTokenIds", "[]"))
neg_risk = market.get("negRisk", False)
print(f"Market: {market.get('question', 'N/A')}")
print(f"Neg risk: {neg_risk}")

# Get price for DOWN token
down_token = clob_ids[1]
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
book = r2.json()
asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]
asks.sort(key=lambda x: x[0])

if asks:
    best_ask = asks[0][0]
    print(f"Best ask: {best_ask} (size: {asks[0][1]})")
else:
    best_ask = 0.50
    print(f"No asks, using default: {best_ask}")

# For marketable orders, need size * price >= $1
# If price is 0.50, need size >= 2.0
# If price is 0.48, need size >= 2.09
min_size = 1.0 / best_ask + 0.01  # Add a bit for safety
order_size = round(min_size, 2)
print(f"Order size: {order_size} (cost: ${order_size * best_ask:.2f})")

# Create client with sig_type=2 (POLY_GNOSIS_SAFE)
print("\n=== sig_type=2 with proper size ===")
client2 = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    creds=creds,
    signature_type=2,  # POLY_GNOSIS_SAFE
    funder=deposit_wallet,
)

order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=best_ask,
    size=order_size,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=neg_risk)

try:
    signed = client2.create_order(order_args, options)
    print(f"Order signer: {signed.signer}")
    print(f"Order maker: {signed.maker}")
    print(f"Order sigType: {signed.signatureType}")
    
    result = client2.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"\n*** ORDER PLACED! ***")
    print(f"Result: {result}")
except Exception as e:
    err = str(e)
    print(f"Error: {err[:500]}")
    
    # If it's still failing, try with a non-marketable order (below market price)
    if "marketable" in err.lower() or "insufficient" in err.lower():
        print("\nTrying non-marketable order (below market)...")
        low_price = best_ask * 0.9  # 10% below market
        order_args2 = OrderArgs(
            token_id=down_token,
            side="BUY",
            price=low_price,
            size=1.0,
        )
        try:
            result2 = client2.create_and_post_order(order_args2, options, OrderType.GTC)
            print(f"*** LIMIT ORDER PLACED! ***")
            print(f"Result: {result2}")
        except Exception as e2:
            print(f"Limit order error: {str(e2)[:300]}")

# Also try: non-marketable limit order (maker order, not taker)
print("\n=== Non-marketable limit order (maker) ===")
try:
    # Place a limit order BELOW market (won't fill immediately = maker)
    low_price = round(best_ask * 0.95, 2)  # 5% below market
    if low_price < 0.01:
        low_price = 0.01
    
    order_args3 = OrderArgs(
        token_id=down_token,
        side="BUY",
        price=low_price,
        size=1.0,  # $1 * 0.95 = $0.95, but it's a maker order
    )
    # For non-marketable orders, size doesn't need to be >= $1
    result3 = client2.create_and_post_order(order_args3, options, OrderType.GTC)
    print(f"*** MAKER ORDER PLACED! ***")
    print(f"Result: {result3}")
except Exception as e:
    err = str(e)
    print(f"Error: {err[:500]}")
