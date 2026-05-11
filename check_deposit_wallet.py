"""Check if 0x4f9f is a deposit wallet and try to deploy one if needed"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from config import Config
from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://polygon-bor-rpc.publicnode.com'))
eoa = Web3.to_checksum_address('0x871faC3EEE45e620606c1d8e228984d2d322244F')
old_proxy = Web3.to_checksum_address('0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4')

# Deposit Wallet Factory on Polygon (from docs)
# Need to find the actual factory address - check common Polymarket contracts
print("=== Checking 0x4f9f wallet structure ===")
code = w3.eth.get_code(old_proxy)
print(f"0x4f9f code length: {len(code)} bytes")

# Check storage slot 0 (implementation for custom proxy)
slot0 = w3.eth.get_storage_at(old_proxy, 0)
print(f"0x4f9f slot 0: {slot0.hex()}")

# Check the owner slot (ERC-1967 slot for implementation)
# Common slots: 0 (owner), 1 (pending owner), bytes32(keccak256("eip1967.proxy.implementation"))-1
import hashlib
impl_slot = Web3.solidityKeccak(['string'], ['eip1967.proxy.implementation'])
impl_slot_int = int.from_bytes(impl_slot, 'big') - 0
impl_value = w3.eth.get_storage_at(old_proxy, impl_slot)
print(f"0x4f9f ERC-1967 impl slot: 0x{impl_value.hex()}")
if int(impl_value.hex(), 16) != 0:
    print(f"  Implementation: 0x{int(impl_value.hex(), 16):040x}")

# Try getting the signer/owner using common patterns
# Polymarket FundWallet has: storage[0] = implementation, storage[1] = signer
signer_val = w3.eth.get_storage_at(old_proxy, 1)
print(f"0x4f9f slot 1 (possible signer): 0x{signer_val.hex()}")
if int(signer_val.hex(), 16) != 0:
    addr = '0x' + signer_val.hex()[-40:]
    print(f"  Possible signer: {addr}")
    print(f"  Matches our EOA: {addr.lower() == eoa.lower()}")

# Check who created this wallet (check the transaction that created it)
# We can use the RPC to find the transaction
print("\n=== Checking DepositWalletFactory ===")
# The DepositWalletFactory creates deterministic wallets
# From the Polymarket docs, wallet address = factory.getAddress(owner, salt)

# Try common Polymarket factory addresses
factory_candidates = [
    # Known Polymarket contract addresses
    '0x93CbFGWs8GNt3E2X4k6U3JNSCD5YvSPPMNk28xf6CrE3',  # DepositWalletFactory on mainnet?
]

# Actually let's check the bytecode of 0x4f9f to understand what it proxies to
# The minimal proxy pattern embeds the implementation address
code_hex = code.hex()
# EIP-1167 pattern: find the address in the bytecode
# Pattern: 0x363d3d373d3d3d363d73<address>5af43d82803e903d91602b57fd5bf3
if '363d3d373d3d3d363d73' in code_hex:
    idx = code_hex.index('363d3d373d3d3d363d73') + len('363d3d373d3d3d363d73')
    impl_hex = code_hex[idx:idx+40]
    impl_addr = Web3.to_checksum_address('0x' + impl_hex)
    print(f"0x4f9f proxies to implementation: {impl_addr}")

# Also try calling what function calls go through the proxy
# If it's a Polymarket FundWallet, slot 0 stores the implementation address
# Let's try reading storage more carefully
for i in range(5):
    val = w3.eth.get_storage_at(old_proxy, i)
    if int(val.hex(), 16) != 0:
        # Convert to address if it looks like one
        raw = val.hex()[-40:]
        addr_fmt = Web3.to_checksum_address('0x' + raw) if len(raw) == 40 else None
        print(f"0x4f9f slot {i}: 0x{val.hex()}" + (f" (as addr: {addr_fmt})" if addr_fmt else ""))

# Try the relayer to get the expected deposit wallet
print("\n=== Checking Relayer for deposit wallet ===")
RELELER_URL = "https://relayer-api.polymarket.com"
try:
    r = requests.get(f'{RELELER_URL}/status', timeout=10)
    print(f"Relayer status: {r.status_code} {r.text[:200]}")
except Exception as e:
    print(f"Relayer status error: {e}")

# Try to derive the deposit wallet address using the relayer
try:
    r = requests.get(f'{RELELER_URL}/deposit-wallet?signer={eoa}', timeout=10)
    print(f"Deposit wallet lookup: {r.status_code} {r.text[:200]}")
except Exception as e:
    print(f"Deposit wallet lookup error: {e}")

# Also check the DepositWalletFactory prediction
# address = keccak256(abi.encodePacked(byte(0xff), factory, salt, keccak256(init_code)))
# Use the builder auth to query
from builder_signing_sdk import BuilderConfig, BuilderApiKeyCreds
try:
    from py_builder_relayer_client.client import RelayClient

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
    
    try:
        expected = relayer.get_expected_safe(eoa)
        print(f"Relayer expected safe/wallet for {eoa[:10]}...: {expected}")
    except Exception as e:
        print(f"get_expected_safe error: {e}")
except Exception as e:
    print(f"Relayer init error: {e}")

# Final check: try the Polymarket CLOB API to check balances/positions for different addresses
print("\n=== CLOB Balance Check ===")
from py_clob_client_v2 import ClobClient as V2Client

pk = Config.POLY_PRIVATE_KEY
client = V2Client(host='https://clob.polymarket.com', chain_id=137, key=pk)
creds = client.derive_api_key()
client.set_api_creds(creds)

# Try checking balances for different addresses 
pUSD = '0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB'

for name, addr in [('EOA', eoa), ('OldProxy(4f9f)', old_proxy)]:
    try:
        bal = client.get_balance_allowance(addr, pUSD)
        print(f'{name}: {bal}')
    except Exception as ex:
        print(f'{name}: {ex}')