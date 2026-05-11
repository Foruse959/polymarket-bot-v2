"""Try posting order manually with deposit wallet as owner"""
import os, sys, json, time, requests

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions
from py_clob_client_v2.order_utils.model.order_data_v2 import order_to_json_v2
from py_clob_client_v2.headers.headers import create_level_2_headers
from py_clob_client_v2.http_helpers.helpers import RequestArgs
from py_clob_client_v2.clob_types import ApiCreds

pk = os.getenv('POLY_PRIVATE_KEY')
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'

# Derive API key
client = ClobClient(host='https://clob.polymarket.com', chain_id=137, key=pk)
creds = client.create_or_derive_api_key()
print(f"API key: {creds.api_key}")
print(f"EOA: {eoa}")
print(f"Deposit wallet: {deposit_wallet}")

# Create deposit wallet client
dw_client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    creds=creds,
    signature_type=3,
    funder=deposit_wallet,
)

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
clob_ids = json.loads(market.get("clobTokenIds", "[]"))
down_token = clob_ids[1]

r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
book = r2.json()
asks = [(float(a["price"]), float(a["size"])) for a in book.get("asks", [])]
asks.sort(key=lambda x: x[0])
best_ask = asks[0][0] if asks else 0.50

print(f"\nMarket: {market.get('question', 'N/A')}")
print(f"Best ask: {best_ask}")

# Create the order
order_args = OrderArgs(token_id=down_token, side="BUY", price=best_ask, size=1.0)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)
signed = dw_client.create_order(order_args, options)

print(f"\nOrder signer: {signed.signer}")
print(f"Order maker: {signed.maker}")
print(f"Order sigType: {signed.signatureType}")

# Method A: Post with deposit wallet as owner
print("\n=== Method A: Deposit wallet as owner ===")
body_a = order_to_json_v2(signed, deposit_wallet, "GTC", False, False)
serialized_a = json.dumps(body_a, separators=(",", ":"), ensure_ascii=False)
req_args_a = RequestArgs(method="POST", request_path="/order",
                          body=body_a, serialized_body=serialized_a)
headers_a = create_level_2_headers(dw_client.signer, creds, req_args_a)

r3 = requests.post("https://clob.polymarket.com/order",
                    headers=headers_a, data=serialized_a, timeout=10)
print(f"Status: {r3.status_code}")
print(f"Response: {r3.text[:500]}")

# Method B: Try with a fresh API key deletion + recreation
print("\n=== Method B: Delete and recreate API key ===")
try:
    client_del = ClobClient(host='https://clob.polymarket.com', chain_id=137, key=pk)
    # Delete existing key
    old_creds = client_del.derive_api_key()
    client_del.set_api_creds(old_creds)
    client_del.delete_api_key()
    print("Old API key deleted")
    
    # Create new key
    new_creds = client_del.create_api_key()
    print(f"New API key: {new_creds.api_key}")
    
    # Try with new creds
    dw_client2 = ClobClient(
        host='https://clob.polymarket.com',
        chain_id=137,
        key=pk,
        creds=new_creds,
        signature_type=3,
        funder=deposit_wallet,
    )
    
    signed2 = dw_client2.create_order(order_args, options)
    body_b = order_to_json_v2(signed2, new_creds.api_key, "GTC", False, False)
    serialized_b = json.dumps(body_b, separators=(",", ":"), ensure_ascii=False)
    req_args_b = RequestArgs(method="POST", request_path="/order",
                              body=body_b, serialized_body=serialized_b)
    headers_b = create_level_2_headers(dw_client2.signer, new_creds, req_args_b)
    
    r4 = requests.post("https://clob.polymarket.com/order",
                        headers=headers_b, data=serialized_b, timeout=10)
    print(f"Status: {r4.status_code}")
    print(f"Response: {r4.text[:500]}")
except Exception as e:
    print(f"Method B error: {e}")

# Method C: Try with V1 (sig_type=0) using EOA directly
print("\n=== Method C: EOA direct (sig_type=0) ===")
try:
    eoa_client = ClobClient(
        host='https://clob.polymarket.com',
        chain_id=137,
        key=pk,
        creds=creds,
        signature_type=0,  # EOA
    )
    
    signed3 = eoa_client.create_order(order_args, options)
    print(f"Order signer: {signed3.signer}")
    print(f"Order maker: {signed3.maker}")
    print(f"Order sigType: {signed3.signatureType}")
    
    body_c = order_to_json_v2(signed3, creds.api_key, "GTC", False, False)
    serialized_c = json.dumps(body_c, separators=(",", ":"), ensure_ascii=False)
    req_args_c = RequestArgs(method="POST", request_path="/order",
                              body=body_c, serialized_body=serialized_c)
    headers_c = create_level_2_headers(eoa_client.signer, creds, req_args_c)
    
    r5 = requests.post("https://clob.polymarket.com/order",
                        headers=headers_c, data=serialized_c, timeout=10)
    print(f"Status: {r5.status_code}")
    print(f"Response: {r5.text[:500]}")
except Exception as e:
    print(f"Method C error: {e}")
