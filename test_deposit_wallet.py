"""Test sig_type=3 (POLY_1271 / Deposit Wallet) with funder=0x4f9f"""
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

print("=== Testing sig_type=3 (POLY_1271 / Deposit Wallet) ===")
print(f"Signer/EOA: {eoa}")
print(f"Funder/Deposit Wallet: {deposit_wallet}")

client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key=pk,
    signature_type=3,  # POLY_1271 (Deposit Wallet)
    funder=deposit_wallet,
)

creds = client.derive_api_key()
client.set_api_creds(creds)
print(f'API key: {creds.api_key}')

# Find a market
now = int(time.time())
rounded = (now // 300) * 300 + 300
slug = f'btc-updown-5m-{rounded}'
r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])
if not events:
    # Try next epoch
    rounded2 = rounded + 300
    slug2 = f'btc-updown-5m-{rounded2}'
    r = requests.get(f'https://gamma-api.polymarket.com/events', params={'slug': slug2}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
if not events:
    print("No market found!")
    sys.exit(1)

market = events[0].get('markets', [])[0]
clob_ids = json.loads(market.get('clobTokenIds', '[]'))
down_token = clob_ids[1]
print(f"Market: {market.get('question', 'N/A')}")

# Get best ask price
r2 = requests.get(f"https://clob.polymarket.com/book?token_id={down_token}", timeout=10)
if r2.status_code == 200:
    book = r2.json()
    asks = [(float(a['price']), float(a['size'])) for a in book.get('asks', [])]
    asks.sort(key=lambda x: x[0])
    best_ask = asks[0][0] if asks else 0.50
    total_liquidity = sum(s for _, s in asks)
    print(f"Best ask: {best_ask} | Total ask liquidity: {total_liquidity:.1f}")
else:
    best_ask = 0.50

# Try to place a BUY order for 1 share at best ask
print(f"\nPlacing BUY 1 share @ {best_ask} (sig_type=3, funder={deposit_wallet[:10]}...)")
order_args = OrderArgs(
    token_id=down_token,
    side="BUY",
    price=best_ask,
    size=1.0,
)
options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=True)

try:
    result = client.create_and_post_order(order_args, options, OrderType.GTC)
    print(f"ORDER RESULT: {result}")
    print("SUCCESS! sig_type=3 works!")
except Exception as e:
    print(f"Order failed: {e}")
    error_str = str(e)
    if 'invalid signature' in error_str:
        print("\n>>> Still invalid signature. Need to check ERC-1271 support.")
    elif 'insufficient' in error_str.lower():
        print("\n>>> Insufficient balance")
    elif 'deposit wallet' in error_str:
        print("\n>>> Deposit wallet issue")
    elif 'allowance' in error_str.lower():
        print("\n>>> Need to approve token allowance")

# Also check if we need to set allowance for the deposit wallet
print("\n=== Checking allowances ===")
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))
pUSD = Web3.to_checksum_address('0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB')
ctf_v2 = Web3.to_checksum_address('0xE111180000d2663C0091e4f400237545B87B996B')
neg_risk_v2 = Web3.to_checksum_address('0xe2222d279d744050d28e00520010520000310F59')

erc20_abi = [
    {'constant':True,'inputs':[{'name':'_owner','type':'address'},{'name':'_spender','type':'address'}],'name':'allowance','outputs':[{'name':'','type':'uint256'}],'type':'function'},
]
pUSD_c = w3.eth.contract(address=pUSD, abi=erc20_abi)

dw = Web3.to_checksum_address(deposit_wallet)
for name, spender in [('CTF_V2', ctf_v2), ('NegRisk_V2', neg_risk_v2)]:
    try:
        allow = pUSD_c.functions.allowance(dw, spender).call() / 1e6
        print(f'Deposit wallet -> {name}: ${allow:.2f} allowance')
    except Exception as ex:
        print(f'Allowance check failed for {name}: {ex}')

# Check pUSD balance on deposit wallet
erc20_balance_abi = [{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'}]
pUSD_balance = w3.eth.contract(address=pUSD, abi=erc20_balance_abi)
bal = pUSD_balance.functions.balanceOf(dw).call() / 1e6
print(f'pUSD balance on deposit wallet: ${bal:.4f}')