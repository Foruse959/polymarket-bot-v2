"""Test deposit wallet order using official Polymarket example pattern"""
import os, sys, json, time, requests

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType

pk = os.getenv('POLY_PRIVATE_KEY')
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'

print("=== Deposit Wallet Order Test (Official Pattern) ===")

# Step 1: Derive API key with EOA (standard flow)
print("\n--- Step 1: Derive API key ---")
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
)
creds = client.create_or_derive_api_key()
print(f"API key: {creds.api_key}")

# Step 2: Create deposit wallet client with the derived creds
print("\n--- Step 2: Create deposit wallet client ---")
client2 = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    creds=creds,
    signature_type=3,  # POLY_1271
    funder=deposit_wallet,
)

print(f"Signer: {client2.signer.address()}")
print(f"Builder funder: {client2.builder.funder}")
print(f"Builder sig type: {client2.builder.signature_type}")

# Step 3: Check balance
print("\n--- Step 3: Check balance ---")
try:
    bal = client2.get_balance_allowance(asset_type="COLLATERAL")
    print(f"Balance: {bal}")
except Exception as e:
    print(f"Balance error: {e}")

# Step 4: Find a market
print("\n--- Step 4: Find market ---")
now = int(time.time())
rounded = (now // 300) * 300 + 300
slug = f"btc-updown-5m-{rounded}"
print(f"Looking for: {slug}")

r = requests.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get("events", [])

if not events:
    rounded2 = rounded + 300
    slug2 = f"btc-updown-5m-{rounded2}"
    print(f"Trying next epoch: {slug2}")
    r = requests.get("https://gamma-api.polymarket.com/events", params={"slug": slug2}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get("events", [])

if not events:
    print("No BTC updown market found right now. Trying ETH...")
    now2 = int(time.time())
    rounded3 = (now2 // 300) * 300 + 300
    for offset in [0, 300, 600, 900]:
        slug3 = f"eth-updown-5m-{rounded3 + offset}"
        r = requests.get("https://gamma-api.polymarket.com/events", params={"slug": slug3}, timeout=10)
        data = r.json()
        events = data if isinstance(data, list) else data.get("events", [])
        if events:
            slug = slug3
            print(f"Found ETH market: {slug}")
            break

if not events:
    print("No updown markets found. Listing available markets...")
    r = requests.get("https://gamma-api.polymarket.com/events", 
                     params={"limit": 10, "active": True, "closed": False}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get("events", [])
    for ev in events[:5]:
        q = ev.get("question", "N/A")
        s = ev.get("slug", "")
        print(f"  - {q} (slug: {s})")
    sys.exit(1)

market = events[0].get("markets", [])[0]
clob_ids = json.loads(market.get("clobTokenIds", "[]"))
condition_id = market.get("conditionId", "")
print(f"Market: {market.get('question', 'N/A')}")
print(f"Token IDs: {clob_ids}")

# Step 5: Get best price
print("\n--- Step 5: Get price ---")
down_token = clob_ids[1] if len(clob_ids) >= 2 else clob_ids[0]
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
best_ask = 0.50
if r2.status_code == 200:
    book = r2.json()
    asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]
    asks.sort(key=lambda x: x[0])
    if asks:
        best_ask = asks[0][0]
        print(f"Best ask: {best_ask} (size: {asks[0][1]})")
    else:
        print(f"No asks, using default: {best_ask}")
else:
    print(f"Book error {r2.status_code}, using default: {best_ask}")

# Step 6: Create and post order
print("\n--- Step 6: Place order ---")
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=best_ask,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

try:
    signed = client2.create_order(order_args, options)
    print(f"Order signer: {signed.signer}")
    print(f"Order maker: {signed.maker}")
    print(f"Order sigType: {signed.signatureType}")
    print(f"Signature: {signed.signature[:60]}...")
    
    result = client2.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"\n*** ORDER PLACED SUCCESSFULLY! ***")
    print(f"Result: {result}")
except Exception as e:
    err = str(e)
    print(f"\nOrder failed: {err[:800]}")
    
    if "insufficient" in err.lower():
        print("=> Balance issue")
    elif "allowance" in err.lower():
        print("=> Need to approve token allowances")
    elif "signer address" in err.lower():
        print("=> Signer/API key mismatch - this is the deposit wallet issue")
    elif "invalid signature" in err.lower():
        print("=> Signature validation failed")
