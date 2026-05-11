"""Test: Use builder API key + POLY_1271 to place an order

The issue: derived API key is tied to EOA 0x871f, but POLY_1271 order signer is 0x4f9f.
The builder API key might handle the deposit wallet mapping differently.

Also trying: setting POLY_ADDRESS to deposit wallet address for API auth.
"""
import os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType, ApiCreds, BuilderConfig
from py_clob_client_v2.order_utils import SignatureTypeV2
from web3 import Web3

pk = Config.POLY_PRIVATE_KEY
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'

# Builder credentials from .env
builder_api_key = Config.BUILDER_API_KEY  # 019e0b44-d07d-7614-80fb-a232206d7632
builder_secret = Config.BUILDER_SECRET
builder_passphrase = Config.BUILDER_PASSPHRASE
builder_code = Config.BUILDER_CODE

print("=== Builder + POLY_1271 Order Test ===")
print(f"EOA: {eoa}")
print(f"Deposit Wallet: {deposit_wallet}")
print(f"Builder API Key: {builder_api_key}")

# Method 1: Use builder API key directly as creds
print("\n--- Method 1: Builder API Key as creds + POLY_1271 ---")
try:
    builder_creds = ApiCreds(
        api_key=builder_api_key,
        api_secret=builder_secret,
        api_passphrase=builder_passphrase,
    )
    client = ClobClient(
        host='https://clob.polymarket.com',
        chain_id=137,
        key=pk,
        creds=builder_creds,
        signature_type=3,  # POLY_1271
        funder=deposit_wallet,
    )
    
    # Check what address the builder creds are associated with
    try:
        keys = client.get_api_keys()
        print(f"Builder API keys: {keys}")
    except Exception as e:
        print(f"Get API keys error: {e}")
    
    # Check balance
    try:
        bal = client.get_balance_allowance(
            asset_type="COLLATERAL",
            signature_type=3,
        )
        print(f"Balance: {bal}")
    except Exception as e:
        print(f"Balance check error: {e}")
    
    # Find market
    now = int(time.time())
    rounded = (now // 300) * 300 + 300
    slug = f'btc-updown-5m-{rounded}'
    
    r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    if not events:
        rounded2 = rounded + 300
        slug2 = f'btc-updown-5m-{rounded2}'
        print(f"Trying: {slug2}")
        r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug2}, timeout=10)
        data = r.json()
        events = data if isinstance(data, list) else data.get('events', [])
    
    if events:
        market = events[0].get('markets', [])[0]
        clob_ids = json.loads(market.get('clobTokenIds', '[]'))
        down_token = clob_ids[1]
        print(f"Market: {market.get('question', 'N/A')}")
        print(f"Token: {down_token}")
        
        # Get price
        r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
        if r2.status_code == 200:
            book = r2.json()
            asks = [(float(a['price']), float(a['size'])) for a in book.get('asks', [])]
            asks.sort(key=lambda x: x[0])
            best_ask = asks[0][0] if asks else 0.50
        else:
            best_ask = 0.50
        
        print(f"Best ask: {best_ask}")
        
        # Try placing order with builder creds
        try:
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
            
            result = client.create_and_post_order(order_args, options, OrderType.GTC)
            print(f"ORDER RESULT: {result}")
            print("SUCCESS!")
        except Exception as e:
            err = str(e)
            print(f"Order error: {err[:500]}")
            if 'signer address' in err:
                print("=> Still signer address mismatch")
            elif 'insufficient' in err.lower():
                print("=> Balance issue (progress!)")
            elif 'allowance' in err.lower():
                print("=> Need to approve token spending")
    else:
        print("No market found!")
        
except Exception as e:
    print(f"Method 1 error: {e}")

# Method 2: Derive API key first, then manually set POLY_ADDRESS to deposit wallet in headers
print("\n--- Method 2: Derived creds + manually patch POLY_ADDRESS ---")
try:
    client2 = ClobClient(
        host='https://clob.polymarket.com',
        chain_id=137,
        key=pk,
        signature_type=3,
        funder=deposit_wallet,
    )
    
    # Derive API key normally (uses EOA address)
    derived_creds = client2.derive_api_key()
    print(f"Derived API key: {derived_creds.api_key}")
    client2.set_api_creds(derived_creds)
    
    # Now check what L2 headers would look like
    from py_clob_client_v2.headers.headers import POLY_ADDRESS
    print(f"Signer address: {client2.signer.address()}")
    print(f"Expected POLY_ADDRESS in headers: {client2.signer.address()}")
    print(f"Should be: {deposit_wallet} (for deposit wallet flow)")
    
except Exception as e:
    print(f"Method 2 error: {e}")

# Method 3: Create a NEW API key with the deposit wallet as POLY_ADDRESS
print("\n--- Method 3: Try creating API key with deposit wallet POLY_ADDRESS ---")
try:
    from py_clob_client_v2.signer import Signer
    from py_clob_client_v2.signing.eip712 import sign_clob_auth_message
    
    # Sign with EOA but send deposit wallet address in POLY_ADDRESS
    signer = Signer(pk, 137)
    ts = int(time.time())
    signature = sign_clob_auth_message(signer, ts, 0)
    
    # Try to derive/create API key with deposit wallet address
    headers_deposit = {
        'POLY_ADDRESS': deposit_wallet,
        'POLY_SIGNATURE': signature,
        'POLY_TIMESTAMP': str(ts),
        'POLY_NONCE': '0',
        'Content-Type': 'application/json',
    }
    
    # Try deriving an API key associated with the deposit wallet
    print("Trying derive with deposit wallet address...")
    r = requests.get(f'https://clob.polymarket.com/auth/derive-api-key', headers=headers_deposit, timeout=10)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
    
    if r.status_code != 200:
        print("\nTrying create with deposit wallet address...")
        r2 = requests.post(f'https://clob.polymarket.com/auth/api-key', headers=headers_deposit, timeout=10)
        print(f"Status: {r2.status_code}")
        print(f"Response: {r2.text[:500]}")
    
except Exception as e:
    print(f"Method 3 error: {e}")