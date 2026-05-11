"""Check what address the API key is associated with and test with correct signer."""
import os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType, ApiCreds

pk = Config.POLY_PRIVATE_KEY
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'

# With sig_type=3, the order signer should be the DEPOSIT WALLET (0x4f9f)
# But the API key was derived from the EOA (0x871f) private key
# The CLOB checks: signer in order == address of API key
# So we need the API key's address to be the deposit wallet!
# 
# But the API key is derived from the EOA private key...
# The CLOB "derive_api_key" derives from the L1 signed message
# So the API key is associated with the EOA address.
#
# For POLY_1271, the docs say:
# - API key address = deposit wallet address (need to create API key with deposit wallet as signer)
# - Order signer = deposit wallet address
# - But we can't sign with the deposit wallet's private key (it's a smart contract!)
#
# Actually wait - re-reading the docs:
# "the order signer field: Deposit wallet address"
# But API keys are derived from the OWNER's EOA private key
# The L1 auth POLY_ADDRESS header should be the EOA (owner)
# The L2 auth POLY_ADDRESS should also be the EOA? Or deposit wallet?

# Let me check what the CLOB API key derives to:
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=3,
    funder=deposit_wallet,
)

# Check create_api_key (vs derive)
try:
    creds_create = client.create_api_key()
    print(f"Created API key: {creds_create.api_key}")
except Exception as e:
    print(f"Create API key failed: {e}")

# Try derive
try:
    creds_derive = client.derive_api_key()
    print(f"Derived API key: {creds_derive.api_key}")
except Exception as e:
    print(f"Derive API key failed: {e}")

# Check create_or_derive
creds = client.create_or_derive_api_key()
print(f"API key (create_or_derive): {creds.api_key}")
client.set_api_creds(creds)

print(f"\nSigner address: {client.signer.address()}")
print(f"Funder: {client.builder.funder}")

# The key issue: for POLY_1271, the order's signer field should = deposit wallet
# But the API key is associated with the EOA.
# The POLY_ADDRESS header in L2 uses signer.address() which is the EOA.
#
# For the server to validate:
# 1. It receives the order with signer=deposit_wallet, maker=deposit_wallet
# 2. It receives L2 headers with POLY_ADDRESS=EOA
# 3. It checks if EOA is an authorized signer for the deposit wallet (via ERC-1271)
#
# The error "the order signer address has to be the address of the API KEY"
# means POLY_ADDRESS in the header must match the order signer.
# For POLY_1271, the order signer is the deposit wallet.
# So POLY_ADDRESS should be deposit wallet address.
# But we can't create an API key for the deposit wallet with our EOA key...
#
# UNLESS: the CLOB has special handling for POLY_1271 where it checks
# if the EOA is an approved signer for the deposit wallet.

print("\n=== Testing order with sig_type=3 ===")
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

# Now check what the client would send as the order
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=0.50,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

# Create signed order and inspect it
signed = client.create_order(order_args, options)
print(f"Order signer: {signed.signer}")
print(f"Order maker: {signed.maker}")
print(f"Order signatureType: {signed.signatureType}")
print(f"Order timestamp: {signed.timestamp}")

# The _v2_order_signer method should return deposit_wallet for sig_type=3
# Let's verify by checking the OrderBuilder
print(f"\nBuilder funder: {client.builder.funder}")
print(f"Builder signer type: {client.builder.signature_type}")
print(f"Builder _v2_order_signer: {client.builder._v2_order_signer()}")

# Now try to post the order and see the exact error
try:
    result = client.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"ORDER RESULT: {result}")
except Exception as e:
    print(f"Order failed: {e}")