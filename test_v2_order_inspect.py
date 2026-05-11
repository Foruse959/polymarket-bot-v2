import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from config import Config
from py_clob_client_v2 import ClobClient as V2Client
from py_clob_client_v2.clob_types import OrderArgs as OrderArgsV2, PartialCreateOrderOptions, BuilderConfig as V2BuilderConfig

pk = Config.POLY_PRIVATE_KEY
funder = Config.get_funder_address()
builder_code = Config.POLY_BUILDER_CODE.strip() if Config.POLY_BUILDER_CODE else '0x' + '0'*64

builder_config = V2BuilderConfig(
    builder_address=Config.POLY_PROXY_WALLET.strip(),
    builder_code=builder_code,
)

client = V2Client(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=2,
    funder=funder,
    builder_config=builder_config,
)

# Derive API key
creds = client.derive_api_key()
client.set_api_creds(creds)
print(f"API key: {creds.api_key}")

# Create an order and inspect it
# Use a dummy token for testing
order_args = OrderArgsV2(
    token_id="56749569062644465148087081627924131659531552181678025781533422352335421853549",
    side="BUY",
    price=0.45,
    size=1.0,
    builder_code=builder_code,
)

options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

signed = client.create_order(order_args, options)

print(f"\nSigned order type: {type(signed)}")
print(f"Signed order attrs: {[a for a in dir(signed) if not a.startswith('_')]}")

# Get the order dict
try:
    od = signed.dict() if hasattr(signed, 'dict') else signed.__dict__
    print(f"\nOrder dict:")
    for k, v in od.items():
        if k == 'signature':
            print(f"  {k}: {str(v)[:40]}...")
        elif k == 'order':
            print(f"  {k}:")
            if isinstance(v, dict):
                for kk, vv in v.items():
                    print(f"    {kk}: {vv}")
            else:
                print(f"    {type(v)}: {v}")
        else:
            print(f"  {k}: {v}")
except Exception as e:
    print(f"Failed to get order dict: {e}")

# Check what the V2 order looks like after serialization
from py_clob_client_v2.order_utils.serialization import order_to_json_v2
try:
    payload = order_to_json_v2(signed, creds.api_key, "FOK", False, False)
    print(f"\nV2 order payload:")
    print(json.dumps(payload, indent=2, default=str)[:2000])
except Exception as e:
    print(f"Serialization failed: {e}")