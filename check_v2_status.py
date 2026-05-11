#!/usr/bin/env python3
"""
V2 Bot Status Check - Tests all credentials and connections
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Disable colors on Windows
if sys.platform == 'win32':
    G = R = Y = B = RST = BD = ""
else:
    G = "\033[92m"
    R = "\033[91m"
    Y = "\033[93m"
    B = "\033[94m"
    RST = "\033[0m"
    BD = "\033[1m"

def log_check(name):
    print(f"\n{BD}{'='*60}{RST}")
    print(f"{BD}{name}{RST}")
    print(f"{BD}{'='*60}{RST}")

def main():
    print(f"\n{BD}{'='*60}{RST}")
    print(f"{BD}POLYMARKET V2 BOT - STATUS CHECK{RST}")
    print(f"{BD}{'='*60}{RST}")
    
    issues = []
    warnings = []
    
    # CHECK 1: PRIVATE KEY
    log_check("1. PRIVATE KEY (CRITICAL)")
    pk = os.getenv('POLY_PRIVATE_KEY', '').strip()
    if not pk:
        print(f"{R}[FAIL] NOT SET{RST}")
        print(f"   You MUST provide POLY_PRIVATE_KEY to trade")
        issues.append("POLY_PRIVATE_KEY missing - cannot sign orders")
    else:
        print(f"{G}[OK] SET{RST}")
        print(f"   Length: {len(pk)} chars")
        try:
            from eth_account import Account
            if not pk.startswith('0x'):
                pk = '0x' + pk
            acct = Account.from_key(pk)
            print(f"   Derived: {acct.address}")
            if acct.address.lower() != os.getenv('POLY_PROXY_WALLET', '').lower():
                warnings.append(f"Private key derives {acct.address} but PROXY_WALLET is {os.getenv('POLY_PROXY_WALLET', 'not set')}")
        except Exception as e:
            print(f"{R}   [FAIL] Invalid key: {e}{RST}")
            issues.append(f"Invalid POLY_PRIVATE_KEY: {e}")
    
    # CHECK 2: PROXY WALLET
    log_check("2. PROXY WALLET / SIGNER")
    proxy = os.getenv('POLY_PROXY_WALLET', '').strip()
    funder = os.getenv('POLY_FUNDER_ADDRESS', '').strip()
    
    if proxy:
        print(f"{G}[OK] POLY_PROXY_WALLET: {proxy}{RST}")
    else:
        print(f"{R}[FAIL] POLY_PROXY_WALLET not set{RST}")
        issues.append("POLY_PROXY_WALLET required for sig_type=2")
    
    if funder:
        print(f"{G}[OK] POLY_FUNDER_ADDRESS: {funder}{RST}")
    else:
        print(f"{Y}[WARN] POLY_FUNDER_ADDRESS not set{RST}")
        warnings.append("Funder address not set (uses proxy)")
    
    # CHECK 3: SIGNATURE TYPE
    log_check("3. SIGNATURE TYPE")
    sig_type = os.getenv('POLY_SIGNATURE_TYPE', '0').strip()
    types = {'0': 'EOA/MetaMask', '1': 'Magic', '2': 'Proxy', '3': 'Deposit'}
    print(f"   Type: {sig_type} ({types.get(sig_type, 'Unknown')})")
    
    if sig_type == '2' and not proxy:
        print(f"{R}   [FAIL] Type 2 requires POLY_PROXY_WALLET{RST}")
        issues.append("sig_type=2 requires POLY_PROXY_WALLET")
    elif sig_type == '2' and proxy:
        print(f"{G}   [OK] Proxy wallet configured{RST}")
    
    # CHECK 4: BUILDER CREDENTIALS
    log_check("4. BUILDER RELAYER (Gasless)")
    bk = os.getenv('POLY_BUILDER_API_KEY', '').strip()
    bs = os.getenv('POLY_BUILDER_SECRET', '').strip()
    bp = os.getenv('POLY_BUILDER_PASSPHRASE', '').strip()
    bc = os.getenv('POLY_BUILDER_CODE', '').strip()
    
    if bk and bs and bp:
        print(f"{G}[OK] All builder credentials set{RST}")
        print(f"   API Key: {bk[:20]}...")
        print(f"   Secret: {'*' * 10}")
        print(f"   Passphrase: {'*' * 10}")
        if bc:
            print(f"   Builder Code: {bc[:20]}...")
        else:
            print(f"{Y}   [WARN] Builder code not set (optional){RST}")
        
        # Test builder connection
        print(f"\n   Testing builder relayer...")
        try:
            import requests
            resp = requests.get(
                "https://relayer-v2.polymarket.com/status",
                headers={"X-API-KEY": bk},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"   {G}[OK] Builder relayer reachable{RST}")
            else:
                print(f"   {Y}[WARN] Builder returned HTTP {resp.status_code}{RST}")
        except Exception as e:
            print(f"   {Y}[WARN] Could not connect: {e}{RST}")
    else:
        print(f"{Y}[WARN] INCOMPLETE{RST}")
        if not bk: print(f"   [MISSING] POLY_BUILDER_API_KEY")
        if not bs: print(f"   [MISSING] POLY_BUILDER_SECRET")
        if not bp: print(f"   [MISSING] POLY_BUILDER_PASSPHRASE")
        warnings.append("Builder credentials incomplete")
    
    # CHECK 5: CLOB RELAY AUTH
    log_check("5. CLOB RELAY AUTH")
    relay = os.getenv('CLOB_RELAY_AUTH_TOKEN', '').strip()
    if relay:
        print(f"{G}[OK] SET{RST}")
        print(f"   Token: {relay[:25]}...")
    else:
        print(f"{Y}[WARN] NOT SET (optional){RST}")
    
    # CHECK 6: ON-CHAIN BALANCE
    log_check("6. ON-CHAIN BALANCE (pUSD)")
    check_addr = proxy or funder
    if check_addr:
        print(f"   Checking: {check_addr}")
        print(f"   Querying Polygon for pUSD balance...")
        
        try:
            import requests
            # pUSD contract
            pusd = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
            padded = check_addr[2:].lower().zfill(64)
            data = f"0x70a08231{padded}"
            
            rpcs = [
                "https://polygon-bor-rpc.publicnode.com",
                "https://1rpc.io/matic",
                "https://polygon.drpc.org",
            ]
            
            found = False
            for rpc in rpcs:
                try:
                    r = requests.post(
                        rpc,
                        headers={"Content-Type": "application/json"},
                        json={
                            "jsonrpc": "2.0",
                            "method": "eth_call",
                            "params": [{"to": pusd, "data": data}, "latest"],
                            "id": 1,
                        },
                        timeout=10,
                    )
                    if r.status_code == 200:
                        result = r.json().get("result", "0x0")
                        bal = int(result, 16) / 1e6
                        print(f"   {G}[OK] pUSD Balance: ${bal:.2f}{RST}")
                        found = True
                        if bal < 1.0:
                            warnings.append(f"Low balance: ${bal:.2f}")
                        break
                except:
                    continue
            
            if not found:
                print(f"   {Y}[WARN] Could not fetch balance{RST}")
        except Exception as e:
            print(f"   {Y}[WARN] Error: {e}{RST}")
    else:
        print(f"   {Y}[WARN] No address to check{RST}")
    
    # CHECK 7: TRADING MODE
    log_check("7. TRADING MODE")
    mode = os.getenv('TRADING_MODE', 'paper')
    risk = os.getenv('LIVE_RISK_MODE', 'concentration')
    print(f"   Mode: {mode.upper()}")
    print(f"   Risk: {risk}")
    if mode == 'live' and not pk:
        print(f"{R}   [FAIL] LIVE mode requires PRIVATE_KEY{RST}")
        issues.append("LIVE mode set but no PRIVATE_KEY")
    elif mode == 'live':
        print(f"{G}   [OK] Ready for live trading{RST}")
    else:
        print(f"{G}   [OK] Paper trading mode (safe for testing){RST}")
    
    # SUMMARY
    print(f"\n{BD}{'='*60}{RST}")
    print(f"{BD}SUMMARY{RST}")
    print(f"{BD}{'='*60}{RST}")
    
    if issues:
        print(f"\n{R}{BD}[BLOCKED] CRITICAL ISSUES ({len(issues)}):{RST}")
        for i, issue in enumerate(issues, 1):
            print(f"   {R}[{i}] {issue}{RST}")
        print(f"\n{R}Trading will NOT work!{RST}")
    
    if warnings:
        print(f"\n{Y}{BD}[WARN] WARNINGS ({len(warnings)}):{RST}")
        for i, w in enumerate(warnings, 1):
            print(f"   {Y}[{i}] {w}{RST}")
    
    if not issues and not warnings:
        print(f"\n{G}{BD}[SUCCESS] ALL CHECKS PASSED!{RST}")
        print(f"   Bot is ready to trade!")
    elif not issues:
        print(f"\n{Y}{BD}[OK] PARTIALLY READY{RST}")
    
    print(f"\n{BD}{'='*60}{RST}")
    return len(issues) == 0

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
