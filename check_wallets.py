"""Check if 0x4f9f is a deposit wallet registered to our EOA on CLOB V2"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))

eoa = Web3.to_checksum_address('0x871faC3EEE45e620606c1d8e228984d2d322244F')
old_proxy = Web3.to_checksum_address('0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4')
actual_proxy = Web3.to_checksum_address('0x1a175aF61505c1D6a359801Fed91952b9B4FA0E2')

pUSD = Web3.to_checksum_address('0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB')
USDCe = Web3.to_checksum_address('0x2791Bca1f2de4661D88DB800B22F825E4527e7E6')  # USDC.e

erc20_abi = [
    {'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'},
]

print("=== BALANCE CHECK ===")
for name, addr in [('EOA', eoa), ('OldProxy(0x4f9f)', old_proxy), ('ActualProxy(0x1a17)', actual_proxy)]:
    pUSD_contract = w3.eth.contract(address=pUSD, abi=erc20_abi)
    usdce_contract = w3.eth.contract(address=USDCe, abi=erc20_abi)
    
    pUSD_bal = pUSD_contract.functions.balanceOf(addr).call() / 1e6
    usdce_bal = usdce_contract.functions.balanceOf(addr).call() / 1e6
    matic = w3.eth.get_balance(addr) / 1e18
    
    print(f'{name} ({addr[:10]}...):')
    print(f'  pUSD: ${pUSD_bal:.4f}')
    print(f'  USDC.e: ${usdce_bal:.4f}')
    print(f'  POL: {matic:.4f}')

# Check allowance for CTF Exchange V2
print("\n=== ALLOWANCE CHECK ===")
ctf_v2 = Web3.to_checksum_address('0xE111180000d2663C0091e4f400237545B87B996B')
neg_risk_v2 = Web3.to_checksum_address('0xe2222d279d744050d28e00520010520000310F59')

allowance_abi = [
    {'constant':True,'inputs':[{'name':'_owner','type':'address'},{'name':'_spender','type':'address'}],'name':'allowance','outputs':[{'name':'','type':'uint256'}],'type':'function'},
]

pUSD_contract = w3.eth.contract(address=pUSD, abi=allowance_abi)

for name, addr in [('OldProxy(0x4f9f)', old_proxy), ('ActualProxy(0x1a17)', actual_proxy)]:
    for spender_name, spender in [('CTF_V2', ctf_v2), ('NegRisk_V2', neg_risk_v2)]:
        try:
            allow = pUSD_contract.functions.allowance(addr, spender).call() / 1e6
            print(f'{name} -> {spender_name}: ${allow:.2f}')
        except Exception as e:
            print(f'{name} -> {spender_name}: error {e}')

# Check the CLOB API for deposit wallet mapping
print("\n=== CLOB API CHECK ===")
# Try to get positions/balances via the API
r = requests.get(f'https://clob.polymarket.com/profile?profile=0x871faC3EEE45e620606c1d8e228984d2d322244F', timeout=10)
print(f'Profile response: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    for k, v in data.items():
        print(f'  {k}: {v}')

# Check deposit wallet mapping on V2 exchange
print("\n=== DEPOSIT WALLET CHECK ===")
# Try checking if Polymarket knows 0x4f9f as a deposit wallet for our EOA
deposit_abi = [
    {'constant':True,'inputs':[{'name':'signer','type':'address'}],'name':'getDepositWalletAddress','outputs':[{'name':'','type':'address'}],'type':'function'},
]

for exchange_name, exchange_addr in [('CTF_V2', ctf_v2), ('NegRisk_V2', neg_risk_v2)]:
    try:
        contract = w3.eth.contract(address=exchange_addr, abi=deposit_abi)
        result = contract.functions.getDepositWalletAddress(eoa).call()
        print(f'{exchange_name} getDepositWalletAddress({eoa[:10]}...): {result}')
    except Exception as e:
        print(f'{exchange_name} getDepositWalletAddress failed: {e}')

# Also check the V1 exchanges
ctf_v1 = Web3.to_checksum_address('0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')
neg_risk_v1 = Web3.to_checksum_address('0xC5d563A36AE78145C45a50134d48A1215220f80a')
for exchange_name, exchange_addr in [('CTF_V1', ctf_v1), ('NegRisk_V1', neg_risk_v1)]:
    try:
        contract = w3.eth.contract(address=exchange_addr, abi=deposit_abi)
        result = contract.functions.getDepositWalletAddress(eoa).call()
        print(f'{exchange_name} getDepositWalletAddress({eoa[:10]}...): {result}')
    except Exception as e:
        print(f'{exchange_name} getDepositWalletAddress failed: {e}')