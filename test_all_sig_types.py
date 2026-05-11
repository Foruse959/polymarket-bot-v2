"""Try direct API call bypassing SDK, and test all signature types"""
import os, sys, json, time, requests, hmac, hashlib

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, ApiCreds, RequestArgs
from py_clob_client_v2.order_utils.model.order_data_v2 import order_to_json_v2
from py_clob_client_v2.headers.headers import create_level_2_headers
from py_clob_client_v2.signer import Signer
from py_clob_client_v2.signing.eip712 import sign_clob_auth_message

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

market = events[0].get("markets", [])[0]
clob_ids = json.loads(market.get("clobTokenIds", []))
down_token = clob_ids[1]

r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
book = r2.json()
asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]
asks.sort(key=lambda x: x[0])
best_ask = asks[0][0] if asks else 0.50
neg_risk = market.get("negRisk", False)

print(f"Market: {market.get('question', 'N/A')}")
print(f"Best ask: {best_ask}")
print(f"Neg risk: {neg_risk}")

# Test each signature type
for sig_type in [0, 1, 2, 3]:
    print(f"\n=== Testing signature_type={sig_type} ===")
    
    if sig_type == 0:
        # EOA - signer=EOA, maker=EOA
        test_client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=0,
        )
    elif sig_type == 1:
        # POLY_PROXY
        test_client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=1,
            funder=deposit_wallet,
        )
    elif sig_type == 2:
        # POLY_GNOSIS_SAFE
        test_client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=2,
            funder=deposit_wallet,
        )
    elif sig_type == 3:
        # POLY_1271
        test_client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=3,
            funder=deposit_wallet,
        )
    
    order_args = OrderArgs(token_id=down_token, side="BUY", price=best_ask, size=1.0)
    options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=neg_risk)
    
    try:
        signed = test_client.create_order(order_args, options)
        print(f"  signer: {signed.signer}")
        print(f"  maker: {signed.maker}")
        print(f"  sigType: {signed.signatureType}")
        
        result = test_client.post_order(signed)
        print(f"  POST RESULT: {result}")
    except Exception as e:
        err = str(e)[:200]
        print(f"  Error: {err}")

# Also try: override the order's signer to EOA after building (sig_type=3)
print("\n=== Testing: sig_type=3 but override signer to EOA ===")
try:
    dw_client = ClobClient(
        host='https://clob.polymarket.com',
        chain_id=137,
        key=pk,
        creds=creds,
        signature_type=3,
        funder=deposit_wallet,
    )
    
    order_args = OrderArgs(token_id=down_token, side="BUY", price=best_ask, size=1.0)
    options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=neg_risk)
    signed = dw_client.create_order(order_args, options)
    
    # Build payload with EOA as signer
    body = order_to_json_v2(signed, creds.api_key, "GTC", False, False)
    body["order"]["signer"] = "0x871faC3EEE45e620606c1d8e228984d2d322244F"  # Override to EOA
    
    serialized = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    req_args = RequestArgs(method="POST", request_path="/order",
                            body=body, serialized_body=serialized)
    headers = create_level_2_headers(dw_client.signer, creds, req_args)
    
    r3 = requests.post("https://clob.polymarket.com/order",
                        headers=headers, data=serialized, timeout=10)
    print(f"Status: {r3.status_code}")
    print(f"Response: {r3.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
