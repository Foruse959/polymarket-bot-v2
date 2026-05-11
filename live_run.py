#!/usr/bin/env python3
"""Live Trading - No Watcher, Just Trade"""

import asyncio
import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from data.gamma_client import GammaClient
from data.clob_client import ClobClient
from data.database import Database
from trading.live_trader import LiveTrader
from trading.live_balance_manager import LiveBalanceManager

async def main():
    print("="*60)
    print("LIVE TRADING STARTED")
    print("="*60)
    print(f"Mode: {Config.TRADING_MODE.upper()}")
    print(f"Proxy Wallet: {Config.POLY_PROXY_WALLET[:10]}...{Config.POLY_PROXY_WALLET[-6:]}")
    print(f"Coins: {', '.join(Config.ENABLED_COINS)}")
    print("="*60)
    
    # Init
    db = Database()
    await db.init()
    
    gamma = GammaClient()
    clob = ClobClient()
    
    balance_mgr = LiveBalanceManager(balance_usdc=2.30, mode='concentration')
    trader = LiveTrader(db, balance_mgr)
    
    # Init live trader
    success = await trader.init(clob)
    if success:
        print(f"[LIVE] Balance: ${trader.balance_mgr.balance_usdc:.2f}")
        print("[LIVE] Trading...")
    else:
        print(f"[ERROR] Init failed: {trader._init_error}")
        return
    
    # Trade loop
    iteration = 0
    while True:
        iteration += 1
        markets = gamma.discover_markets()
        print(f"[{iteration}] Markets: {len(markets)} | Balance: ${trader.balance_mgr.balance_usdc:.2f}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[LIVE] Stopped")
