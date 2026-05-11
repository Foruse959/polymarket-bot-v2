"""Check 0x4f9f proxy implementation and derive deposit wallet"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))
eoa = Web3.to_checksum_address('0x871faC3EEE45e620606c1d8e228984d2d322244F')
old_proxy = Web3.to_checksum_address('0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4')

# Implementation found in slot 0
impl = Web3.to_checksum_address('0xE51aBdF814f8854941b9fE8E3a4F65cAB4E7a4a8')

print(f"Implementation contract: {impl}")
impl_code = w3.eth.get_code(impl)
print(f"Implementation code: {len(impl_code)} bytes")

# Check storage slots of the proxy for owner/signer
print("\n=== Proxy Storage ===")
for i in range(10):
    val = w3.eth.get_storage_at(old_proxy, i)
    if int(val.hex(), 16) != 0:
        raw = val.hex()[-40:]
        if len(raw) == 40:
            addr = Web3.to_checksum_address('0x' + raw)
            print(f"Slot {i}: {val.hex()} (as addr: {addr})")
        else:
            print(f"Slot {i}: {val.hex()}")

# Call signer() on the implementation through the proxy
print("\n=== Calling signer() through proxy ===")
signer_abi = [{'constant':True,'inputs':[],'name':'signer','outputs':[{'name':'','type':'address'}],'type':'function'}]
try:
    proxy_contract = w3.eth.contract(address=old_proxy, abi=signer_abi)
    proxy_signer = proxy_contract.functions.signer().call()
    print(f"signer(): {proxy_signer}")
    print(f"Matches EOA: {proxy_signer.lower() == eoa.lower()}")
except Exception as ex:
    print(f"signer() failed: {ex}")

# Try owner()
owner_abi = [{'constant':True,'inputs':[],'name':'owner','outputs':[{'name':'','type':'address'}],'type':'function'}]
try:
    proxy_contract2 = w3.eth.contract(address=old_proxy, abi=owner_abi)
    proxy_owner = proxy_contract2.functions.owner().call()
    print(f"owner(): {proxy_owner}")
except Exception as ex:
    print(f"owner() failed: {ex}")

# Try getPolyProxyWalletAddress from V1 CTF Exchange for our EOA
print("\n=== V1 Proxy Wallet Lookup ===")
ctf_v1 = Web3.to_checksum_address('0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')
proxy_abi = [{'constant':True,'inputs':[{'name':'signer','type':'address'}],'name':'getPolyProxyWalletAddress','outputs':[{'name':'','type':'address'}],'type':'function'}]
try:
    contract = w3.eth.contract(address=ctf_v1, abi=proxy_abi)
    registered_proxy = contract.functions.getPolyProxyWalletAddress(eoa).call()
    print(f"V1 registered proxy for EOA: {registered_proxy}")
except Exception as ex:
    print(f"V1 lookup failed: {ex}")

# Try to derive deposit wallet using the relayer
print("\n=== Deriving Deposit Wallet ===")
from py_builder_relayer_client.client import RelayClient
from py_builder_signing_sdk.config import BuilderConfig, BuilderApiKeyCreds

builder_config = BuilderConfig(
    local_builder_creds=BuilderApiKeyCreds(
        key=Config.POLY_BUILDER_API_KEY.strip(),
        secret=Config.POLY_BUILDER_SECRET.strip(),
        passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
    )
)

relayer = RelayClient(
    'https://relayer-api.polymarket.com',
    137,
    Config.POLY_PRIVATE_KEY,
    builder_config,
)

# Check what address the relayer gives us
print(f"Relayer signer address: {relayer.signer.address()}")

# Try get_expected_safe which is the only method available
try:
    expected = relayer.get_expected_safe(eoa)
    print(f"Expected safe/wallet: {expected}")
except Exception as ex:
    print(f"get_expected_safe error: {ex}")

# Try to get expected deposit wallet
try:
    # The relayer might have a method for this
    result = relayer.get_nonce(eoa, 'WALLET')
    print(f"WALLET nonce: {result}")
except Exception as ex:
    print(f"get_nonce error: {ex}")

# Also check if old_proxy (0x4f9f) might already be a deposit wallet
# deposit wallets have an ERC-1271 isValidSignature function
erc1271_abi = [
    {'constant':False,'inputs':[{'name':'_hash','type':'bytes32'},{'name':'_signature','type':'bytes'}],'name':'isValidSignature','outputs':[{'name':'','type':'bytes4'}],'type':'function'},
    {'constant':True,'inputs':[],'name':'isOwner','outputs':[{'name':'','type':'address'}],'type':'function'},
]
try:
    dw_contract = w3.eth.contract(address=old_proxy, abi=erc1271_abi)
    # Try static call to isValidSignature with dummy data
    # This is a view function for ERC-1271, but may not work via staticcall
    # Instead just check if isOwner returns our EOA
    owner = dw_contract.functions.isOwner().call()
    print(f"isOwner(): {owner}")
except Exception as ex:
    print(f"ERC-1271 check failed: {ex}")

# Compute expected deposit wallet address deterministically
# DepositWalletFactory: CREATE2 with owner address
# But we don't know the factory address or init code hash
# Let's try the Polymarket approach

print("\n=== Checking 0x1a17 (registered V1 proxy) ===")
actual_proxy = Web3.to_checksum_address('0x1a175aF61505c1D6a359801Fed91952b9B4FA0E2')
code2 = w3.eth.get_code(actual_proxy)
print(f"0x1a17 code length: {len(code2)} bytes (deployed: {len(code2) > 0})")

# Balances
pUSD = Web3.to_checksum_address('0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB')
erc20_abi = [{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'balance','type':'uint256'}],'type':'function'}]
pUSD_c = w3.eth.contract(address=pUSD, abi=erc20_abi)
print(f"0x4f9f pUSD: ${pUSD_c.functions.balanceOf(old_proxy).call() / 1e6:.4f}")
print(f"0x1a17 pUSD: ${pUSD_c.functions.balanceOf(actual_proxy).call() / 1e6:.4f}")
print(f"EOA pUSD: ${pUSD_c.functions.balanceOf(eoa).call() / 1e6:.4f}")
print(f"EOA POL: {w3.eth.get_balance(eoa) / 1e18:.6f}")