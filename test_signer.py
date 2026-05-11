import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from config import Config
from py_clob_client_v2 import ClobClient as V2Client
from py_clob_client_v2.clob_types import BuilderConfig as V2BuilderConfig

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

print(f"Signer type: {type(client.signer)}")
attrs = [a for a in dir(client.signer) if not a.startswith('_')]
print(f"Signer attrs: {attrs}")
for attr in attrs:
    try:
        val = getattr(client.signer, attr)
        if not callable(val):
            print(f"  signer.{attr} = {val}")
    except:
        pass

# Check get_address
try:
    addr = client.get_address()
    print(f"get_address: {addr}")
except Exception as e:
    print(f"get_address failed: {e}")

# Get version
try:
    ver = client.get_version()
    print(f"CLOB API version: {ver}")
except Exception as e:
    print(f"get_version failed: {e}")

# Try to navigate the version resolution
try:
    ver2 = client._ClobClient__resolve_version()
    print(f"Resolved version: {ver2}")
except Exception as e:
    print(f"resolve_version failed: {e}")