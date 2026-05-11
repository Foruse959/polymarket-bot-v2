"""Debug the order JSON for sig_type=3 to find signer mismatch"""
import os, sys, json, time, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PartialCreateOrderOptions, OrderType

pk = Config.POLY_PRIVATE_KEY
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'
eoa = '0x871faC3EEE45e620606c1d8e228984d2d322244F'

client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=3,  # POLY_1271
    funder=deposit_wallet,
)

creds = client.derive_api_key()
client.set_api_creds(creds)
print(f'API key: {creds.api_key}')
print(f'Signer address (EOA): {client.signer.address()}')
print(f'Funder/deposit wallet: {deposit_wallet}')

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

# Create the signed order but DON'T post it - just inspect it
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=0.50,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

# Create order (signs locally, doesn't post)
signed_order = client.create_order(order_args, options)
print(f'\n=== SIGNED ORDER ===')
if hasattr(signed_order, '__dict__'):
    for k, v in sorted(signed_order.__dict__.items()):
        val = str(v)[:80]
        print(f'  {k}: {val}')
elif hasattr(signed_order, '__iter__'):
    for item in signed_order:
        print(f'  {item}')
else:
    print(f'  Type: {type(signed_order)}')
    print(f'  Value: {str(signed_order)[:300]}')

# Check what the API key address is
print(f'\n=== API KEY INFO ===')
print(f'API key: {creds.api_key}')
print(f'API secret: {creds.api_secret[:10]}...')
print(f'API passphrase: {creds.api_passphrase}')

# Also check the address associated with the API key
try:
    keys = client.get_api_keys()
    print(f'API keys response: {keys}')
except Exception as e:
    print(f'Get API keys error: {e}')

# Check different client configs
print(f'\n=== CLIENT INFO ===')
print(f'Client signer type: {type(client.signer).__name__}')
print(f'Signer address: {client.signer.address()}')
print(f'Signer private key: {client.signer.private_key[:10]}...')
print(f'Funder: {client.funder if hasattr(client, "funder") else "N/A"}')
print(f'Funder from builder: {client.builder.funder}')