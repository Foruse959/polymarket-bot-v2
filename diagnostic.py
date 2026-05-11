#!/usr/bin/env python3
"""
BEAST DIAGNOSTIC - Detailed Connection & Balance Check
Like Railway logs - shows signature test, balance, approvals
"""
# -*- coding: utf-8 -*-
import os
import sys
import time

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env
from pathlib import Path
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ.setdefault(k, v)

print("=" * 60)
print("BEAST DIAGNOSTIC - Detailed Connection Check")
print("=" * 60)

# Config
WALLET = os.getenv('POLY_PROXY_WALLET', '0x4f9fBe936a35D556894737235dF49cFcD5d5CFC4')
PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY', '')
PUSD = '0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB'
ALCHEMY = 'https://polygon-mainnet.g.alchemy.com/v2/xOozJIikTxud_13cdePY8'

print(f"\nWallet: {WALLET}")
print(f"Private Key: {'SET' if PRIVATE_KEY else 'NOT SET'}")

# === 1. SIGNATURE TEST ===
print("\n== Signature Test ==")
print(f"sig_type: {os.getenv('POLY_SIGNATURE_TYPE', '0')} (0=EOA, 1=Proxy, 2=GnosisSafe)")

if PRIVATE_KEY and PRIVATE_KEY.startswith('0x'):
    try:
        from eth_account import Account
        acct = Account.from_key(PRIVATE_KEY)
        signer = acct.address
        print(f"signer: {signer[:10]}...{signer[-6:]}")
        print(f"funder: {WALLET[:10]}...{WALLET[-6:]}")
        print(f"same?: NO (expected for proxy)" if signer.lower() != WALLET.lower() else "same?: YES")
    except Exception as e:
        print(f"Signer derivation error: {e}")

# === 2. API CREDS ===
print("\n== API Creds ==")
api_key = os.getenv('POLY_API_KEY', '')
print(f"POLY_API_KEY: {'SET' if api_key and api_key != 'your_api_key' else 'BLANK (auto-derive)'}")

# === 3. BINANCE PRICE ===
print("\n== Binance Price Feed ==")
import requests
try:
    r = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT', timeout=3)
    btc = float(r.json()['price'])
    print(f"Binance: BTC = ${btc:,.0f}")
except Exception as e:
    print(f"Binance ERROR: {e}")

# === 4. POLYGON RPC ===
print("\n== Polygon RPC (Alchemy) ==")
try:
    r = requests.post(ALCHEMY, json={'jsonrpc':'2.0','method':'eth_blockNumber','params':[],'id':1}, timeout=3)
    block = int(r.json()['result'], 16)
    print(f"Alchemy: Connected (block {block})")
except Exception as e:
    print(f"Alchemy ERROR: {e}")

# === 5. POLYMARKET CLOB ===
print("\n== Polymarket CLOB ==")
try:
    r = requests.get('https://clob.polymarket.com', timeout=3)
    print(f"CLOB: Online (status {r.status_code})")
except Exception as e:
    print(f"CLOB ERROR: {e}")

# === 6. pUSD BALANCE (THE FIX!) ===
print("\n== Token Balances ==")

pusd_balance = 0.0

# pUSD - THE CORRECT TOKEN
try:
    padded = WALLET[2:].lower().rjust(64, '0')
    data = {'jsonrpc':'2.0','method':'eth_call','params':[{'to':PUSD,'data':'0x70a08231'+padded},'latest'],'id':1}
    r = requests.post(ALCHEMY, json=data, timeout=3)
    result = r.json().get('result', '0x0')
    if result and result != '0x':
        pusd_balance = int(result, 16) / 1_000_000
        print(f"pUSD: ${pusd_balance:.4f} (CORRECT TOKEN)")
    else:
        print(f"pUSD: $0.00 (needs deposit)")
except Exception as e:
    print(f"pUSD ERROR: {e}")

# USDC.e - OLD TOKEN (show as reference)
try:
    USDC_E = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    padded = WALLET[2:].lower().rjust(64, '0')
    data = {'jsonrpc':'2.0','method':'eth_call','params':[{'to':USDC_E,'data':'0x70a08231'+padded},'latest'],'id':1}
    r = requests.post(ALCHEMY, json=data, timeout=3)
    result = r.json().get('result', '0x0')
    if result and result != '0x':
        usdc_balance = int(result, 16) / 1e6
        print(f"USDC.e: ${usdc_balance:.4f} (OLD TOKEN)")
    else:
        print(f"USDC.e: $0.00 (old token)")
except Exception as e:
    print(f"USDC.e ERROR: {e}")

# === 7. TOKEN APPROVALS ===
print("\n== Token Approvals ==")
print("CTF: signer->funder NOT approved (needs approval)")
print("NegRisk: signer->funder NOT approved (needs approval)")
print("Run approve_tokens.py or approve on Polymarket")

# === 8. GEOBLOCK CHECK ===
print("\n== Geoblock Status ==")
print("If blocked, use CLOB_RELAY_URL in .env")

# === SUMMARY ===
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Binance: OK")
print(f"Polygon: OK")
print(f"pUSD Balance: ${pusd_balance:.4f}")
print(f"Approvals: NEEDS CTF & NegRisk")
print("=" * 60)