#!/usr/bin/env python3
"""
Run Bot + Dashboard + Watcher Together
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Fix encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from config import Config

async def run_dashboard():
    """Run the trading dashboard."""
    print("[LAUNCHER] Starting Dashboard...")
    try:
        from trading_dashboard import TradingDashboard
        dashboard = TradingDashboard(balance=Config.STARTING_BALANCE_USDC)
        dashboard.running = True
        
        while dashboard.running:
            dashboard.render()
            await asyncio.sleep(2)
    except Exception as e:
        print(f"[DASHBOARD ERROR] {e}")

async def run_watcher():
    """Run the bot watcher."""
    print("[LAUNCHER] Starting Watcher...")
    try:
        from bot_watcher import BotWatcher
        watcher = BotWatcher()
        await watcher.watch_loop()
    except Exception as e:
        print(f"[WATCHER ERROR] {e}")

async def run_simple_bot():
    """Run a simple bot without Telegram."""
    print("[LAUNCHER] Starting Simple Bot...")
    try:
        from data.gamma_client import GammaClient
        from data.clob_client import ClobClient
        from trading.paper_trader import PaperTrader
        from trading.live_balance_manager import LiveBalanceManager
        
        # Init components
        gamma = GammaClient()
        clob = ClobClient()
        
        balance_mgr = LiveBalanceManager(
            balance_usdc=Config.STARTING_BALANCE_USDC,
            mode='concentration'
        )
        
        print(f"[BOT] Mode: {Config.TRADING_MODE}")
        print(f"[BOT] Balance: ${balance_mgr.balance_usdc:.2f}")
        print(f"[BOT] Coins: {', '.join(Config.ENABLED_COINS)}")
        
        # Main loop
        iteration = 0
        while True:
            iteration += 1
            
            # Scan markets
            markets = gamma.discover_markets()
            print(f"[BOT] Iteration {iteration}: Found {len(markets)} markets")
            
            # Simulate finding opportunities
            if markets and iteration % 5 == 0:
                print(f"[BOT] Analyzing {len(markets[:3])} markets for signals...")
            
            await asyncio.sleep(10)
            
    except Exception as e:
        print(f"[BOT ERROR] {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all components."""
    print("="*60)
    print("POLYMARKET BOT LAUNCHER")
    print("="*60)
    print()
    
    # Run all concurrently
    await asyncio.gather(
        run_simple_bot(),
        run_watcher(),
        # run_dashboard(),  # Terminal UI - run separately
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Shutdown complete")
