"""Check wallet identities and balances"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/demo'))
if not w3.is_connected():
    w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))

eoa = Web3.to_checksum_address('0x871faC3EEE45e620606c1d8e228984d2d322244F')
old_proxy = Web3.to_checksum_address('0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4')
actual_proxy = Web3.to_checksum_address('0x1a175aF61505c1D6a359801Fed91952b9B4FA0E2')

pUSD = Web3.to_checksum_address('0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB')

erc20_abi = [
    {'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'},
    {'constant':True,'inputs':[{'name':'_owner','type':'address'},{'name':'_spender','type':'address'}],'name':'allowance','outputs':[{'name':'','type':'uint256'}],'type':'function'},
]

pUSD_c = w3.eth.contract(address=pUSD, abi=erc20_abi)

print("=== BALANCES ===")
for name, addr in [('EOA', eoa), ('OldProxy(4f9f)', old_proxy), ('ActualProxy(1a17)', actual_proxy)]:
    try:
        pUSD_bal = pUSD_c.functions.balanceOf(addr).call() / 1e6
        matic = w3.eth.get_balance(addr) / 1e18
        deployed = len(w3.eth.get_code(addr)) > 0
        print(f'{name} ({addr[:10]}...): pUSD=${pUSD_bal:.4f}, POL={matic:.6f}, code={deployed}')
    except Exception as ex:
        print(f'{name}: error {ex}')

print("\n=== CTF EXCHANGE PROXY LOOKUP ===")
ctf_v1 = Web3.to_checksum_address('0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')
proxy_abi = [{'constant':True,'inputs':[{'name':'signer','type':'address'}],'name':'getPolyProxyWalletAddress','outputs':[{'name':'','type':'address'}],'type':'function'}]
fund_abi = [{'constant':True,'inputs':[{'name':'signer','type':'address'}],'name':'getFundAddress','outputs':[{'name':'','type':'address'}],'type':'function'}]

for name, addr in [('CTF_V1', ctf_v1)]:
    try:
        contract = w3.eth.contract(address=addr, abi=proxy_abi + fund_abi)
        proxy = contract.functions.getPolyProxyWalletAddress(eoa).call()
        fund = contract.functions.getFundAddress(eoa).call()
        print(f'{name}: proxy={proxy}, fund={fund}')
    except Exception as ex:
        print(f'{name}: {ex}')

# Check CLOB API positions endpoint
print("\n=== CLOB API ===")
try:
    r = requests.get(f'https://clob.polymarket.com/profile?profile={eoa}', timeout=10)
    print(f'Profile API: {r.status_code} {r.text[:200]}')
except Exception as ex:
    print(f'Profile API error: {ex}')

# Check Polymarket Data API for our address
try:
    r2 = requests.get(f'https://data-api.polymarket.com/profiles/{eoa}', timeout=10)
    print(f'Data API: {r2.status_code} {r2.text[:200]}')
except Exception as ex:
    print(f'Data API error: {ex}')

# Check if old_proxy (0x4f9f) is a Polymarket exchange proxy - find its signer
print("\n=== REVERSE LOOKUP: Who owns 0x4f9f? ===")
# Try calling getPolyProxyWalletAddress with different EOAs to find who maps to 0x4f9f
# Alternatively, check if 0x4f9f is a deposit wallet
impl_slot = '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc'
code_hash = w3.eth.get_storage_at(old_proxy, impl_slot).hex()
print(f'0x4f9f ERC1967 impl slot: {code_hash}')

# Check what the 0x4f9f proxy delegates to - read the bytecode
code = w3.eth.get_code(old_proxy)
print(f'0x4f9f code ({len(code)} bytes): 0x{code.hex()[:120]}...')

# Try owner()/signer() on the implementation that 0x4f9f proxies to
# From the minimal proxy pattern, the implementation address is embedded in the code
# Pattern: 0x363d3d373d3d3d363d73<implementation_address>5af43d82803e903d91602b57fd5bf3
print(f'Full 0x4f9f code hex: 0x{code.hex()}')