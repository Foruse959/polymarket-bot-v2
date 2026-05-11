"""Test POLY_1271 (deposit wallet) order placement with upgraded SDK v1.0.1"""
import os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType, AssetType, BalanceAllowanceParams
from py_clob_client_v2.order_utils import SignatureTypeV2

pk = Config.POLY_PRIVATE_KEY
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'

print(f"=== POLY_1271 Test with upgraded SDK v1.0.1 ===")
print(f"EOA: {eoa}")
print(f"Deposit Wallet: {deposit_wallet}")

client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=3,  # POLY_1271
    funder=deposit_wallet,
)

# Derive API key
creds = client.derive_api_key()
client.set_api_creds(creds)
print(f"API key: {creds.api_key}")

# Verify the client setup
print(f"Signer: {client.signer.address()}")
print(f"Funder: {client.builder.funder}")
print(f"Builder sig type: {client.builder.signature_type}")

# Step 1: Update balance allowance (crucial for deposit wallet)
print("\n=== Updating balance allowance ===")
try:
    result = client.update_balance_allowance(
        BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=SignatureTypeV2.POLY_1271,
        )
    )
    print(f"Balance allowance update result: {result}")
except Exception as e:
    print(f"Balance allowance update failed: {e}")

try:
    result2 = client.update_balance_allowance(
        BalanceAllowanceParams(
            asset_type=AssetType.CONDITIONAL,
            signature_type=SignatureTypeV2.POLY_1271,
        )
    )
    print(f"Conditional allowance update result: {result2}")
except Exception as e:
    print(f"Conditional allowance update failed: {e}")

# Step 2: Create and inspect order
now = int(time.time())
rounded = (now // 300) * 300 + 300
slug = f'btc-updown-5m-{rounded}'

print(f"\n=== Finding market: {slug} ===")
r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if not events:
    # Try next epoch
    rounded2 = rounded + 300
    slug2 = f'btc-updown-5m-{rounded2}'
    print(f"Trying next epoch: {slug2}")
    r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug2}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])

if not events:
    print("No market found!")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
condition_id = market.get('conditionId', '')
print(f"Market: {market.get('question', 'N/A')}")

# Get best price
down_token = clob_ids[1]
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
if r2.status_code == 200:
    book = r2.json()
    asks = [(float(a['price']), float(a['size'])) for a in book.get('asks', [])]
    asks.sort(key=lambda x: x[0])
    best_ask = asks[0][0] if asks else 0.50
else:
    best_ask = 0.50

# Step 3: Create and sign the order first (don't post yet)
print(f"\n=== Creating order: BUY 1 @ {best_ask} ===")
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=best_ask,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

signed_order = client.create_order(order_args, options)
print(f"Order signer: {signed_order.signer}")
print(f"Order maker: {signed_order.maker}")
print(f"Order sigType: {signed_order.signatureType}")
print(f"Order timestamp: {signed_order.timestamp}")
print(f"Signature length: {len(signed_order.signature)} chars")
print(f"Signature starts with: {signed_order.signature[:40]}...")

# Check that signer is the deposit wallet (not EOA)
if signed_order.signer.lower() == deposit_wallet.lower():
    print("[OK] Order signer = deposit wallet (POLY_1271 correct)")
else:
    print(f"[WARN] Order signer = {signed_order.signer} (expected {deposit_wallet})")

# Step 4: Try to post the order
print(f"\n=== Posting order ===")
try:
    result = client.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"ORDER RESULT: {result}")
    print("SUCCESS! ORDER PLACED!")
except Exception as e:
    error_str = str(e)
    print(f"Order failed: {error_str}")
    
    if 'insufficient' in error_str.lower():
        print("=> Balance issue - need to update allowances or add USDC")
    elif 'allowance' in error_str.lower():
        print("=> Need to approve token spending")
    elif 'invalid signature' in error_str.lower():
        print("=> Signature validation failed")
    elif 'maker address not allowed' in error_str.lower():
        print("=> Wallet not registered for trading")