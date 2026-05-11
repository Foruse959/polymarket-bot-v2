import os, sys, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import RequestArgs
from py_clob_client_v2.headers.headers import create_level_2_headers

pk = os.getenv('POLY_PRIVATE_KEY')
deposit_wallet = '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4'

# Init client
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=2,
    funder=deposit_wallet,
)
creds = client.create_or_derive_api_key()
client.set_api_creds(creds)

# Check balance via CLOB API
print("Checking balance via CLOB API...")
headers = create_level_2_headers(
    client.signer, creds,
    RequestArgs(method="GET", request_path="/balance-and-allowance")
)
r = requests.get(
    "https://clob.polymarket.com/balance-and-allowance",
    params={"signature_type": 2, "asset_type": "COLLATERAL"},
    headers=headers, timeout=10
)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Response: {data}")
    balance_raw = data.get('balance', '0')
    allowance_raw = data.get('allowance', '0')
    balance_usdc = int(balance_raw) / 1e6
    allowance_usdc = int(allowance_raw) / 1e6
    print(f"Balance: {balance_raw} = ${balance_usdc:.6f} USDC")
    print(f"Allowance: {allowance_raw} = ${allowance_usdc:.6f} USDC")
else:
    print(f"Error: {r.text}")

# Also check via Alchemy (Polygon RPC)
print("\nChecking via Polygon RPC...")
w3_url = os.getenv('POLYGON_RPC_URL', 'https://polygon-bor-rpc.publicnode.com')
pusd_contract = '0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB'

# ERC20 balanceOf(address)
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(w3_url))
if w3.is_connected():
    # balanceOf selector + address padded to 32 bytes
    data = '0x70a08231' + '000000000000000000000000' + deposit_wallet[2:].lower()
    result = w3.eth.call({'to': pusd_contract, 'data': data})
    balance_wei = int(result.hex(), 16)
    balance_pusd = balance_wei / 1e6
    print(f"pUSD balance (Alchemy): {balance_wei} = ${balance_pusd:.6f}")
else:
    print("Polygon RPC not connected")
