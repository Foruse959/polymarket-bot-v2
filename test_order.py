#!/usr/bin/env python3
"""Test CLOB order placement with proper API credentials."""
import os
import sys
import math

# Load env
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from config import Config
from py_clob_client.client import ClobClient as PyClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

pk = Config.POLY_PRIVATE_KEY.strip()
funder = Config.get_funder_address()
sig_type = Config.POLY_SIGNATURE_TYPE
chain_id = Config.POLY_CHAIN_ID

print(f"Private key: {pk[:8]}...{pk[-4:]}")
print(f"Funder: {funder[:10]}...{funder[-4:] if funder else 'None'}")
print(f"Sig type: {sig_type}")
print(f"Chain ID: {chain_id}")
print()

# Initialize client
client = PyClobClient(
    host="https://clob.polymarket.com",
    key=pk,
    chain_id=chain_id,
    signature_type=sig_type,
    funder=funder,
)

# Test connection
try:
    ok = client.get_ok()
    print(f"CLOB connection: {ok}")
except Exception as e:
    print(f"CLOB connection failed: {e}")

# Derive API credentials
print("\nDeriving API credentials...")
try:
    creds = client.create_or_derive_api_creds()
    print(f"API key: {creds.api_key[:12]}...")
    print(f"API secret: {creds.api_secret[:12]}...")
    client.set_api_creds(creds)
    print("API credentials set successfully")
except Exception as e:
    print(f"Failed to derive API creds: {e}")

# Check balance
print("\nChecking balance...")
try:
    # Get USDC balance on-chain
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider("https://polygon-bor-rpc.publicnode.com"))
    pUSD_addr = Web3.to_checksum_address("0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB")
    wallet_addr = Web3.to_checksum_address(funder)
    
    # ERC20 ABI for balanceOf
    erc20_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    contract = w3.eth.contract(address=pUSD_addr, abi=erc20_abi)
    balance_raw = contract.functions.balanceOf(wallet_addr).call()
    balance = balance_raw / 1e6  # pUSD has 6 decimals
    print(f"pUSD balance: ${balance:.2f}")
except Exception as e:
    print(f"Balance check failed: {e}")

# Try to place a minimal order
print("\nTrying to place a minimal test order...")
try:
    # Find a current BTC 5m market token
    import requests
    import time
    now = int(time.time())
    rounded = (now // 300) * 300
    slug = f"btc-updown-5m-{rounded}"
    
    r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    if events:
        import json
        market = events[0].get('markets', [])[0]
        clob_ids = json.loads(market.get('clobTokenIds', '[]'))
        down_token = clob_ids[1] if len(clob_ids) > 1 else None
        
        if down_token:
            print(f"DOWN token: {down_token}")
            print(f"Placing FOK BUY 1 share @ $0.01 (minimal test)...")
            
            # Try FOK order - 1 share at $0.01 (minimal possible)
            order_args = OrderArgs(
                token_id=down_token,
                side=BUY,
                price=0.01,
                size=1.0,
            )
            
            signed_order = client.create_order(order_args)
            print(f"Signed order created: {type(signed_order)}")
            
            resp = client.post_order(signed_order, OrderType.FOK)
            print(f"Order response: {resp}")
            
            if isinstance(resp, dict) and 'error' in resp:
                print(f"ERROR: {resp['error']}")
    else:
        print("No current market found, trying next epoch...")
        rounded += 300
        slug = f"btc-updown-5m-{rounded}"
        r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
        data = r.json()
        events = data if isinstance(data, list) else data.get('events', [])
        if events:
            market = events[0].get('markets', [])[0]
            clob_ids = json.loads(market.get('clobTokenIds', '[]'))
            down_token = clob_ids[1]
            print(f"DOWN token: {down_token}")
            
            order_args = OrderArgs(
                token_id=down_token,
                side=BUY,
                price=0.01,
                size=1.0,
            )
            signed_order = client.create_order(order_args)
            resp = client.post_order(signed_order, OrderType.FOK)
            print(f"Order response: {resp}")
        
except Exception as e:
    print(f"Order failed: {e}")
    import traceback
    traceback.print_exc()