#!/usr/bin/env python3
"""
REAL Bot Runner - Discovers markets, shows status, NO FAKE TRADES
"""

import asyncio
import sys
import os
import json
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from data.gamma_client import GammaClient
from logger import logger


def log_to_file(entry):
    """Append log entry to file"""
    log_file = "logs/live_trading.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_print(level, category, message, data=None):
    """Print and log to file"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = {
        "timestamp": timestamp,
        "level": level,
        "category": category,
        "message": message,
        "data": data or {},
        "unix_time": datetime.now().timestamp()
    }
    log_to_file(entry)
    print(f"[{timestamp}] [{level}] {message}")


async def main():
    print("="*70)
    print("POLYMARKET BOT v2.0 - REAL MARKET DISCOVERY")
    print("="*70)
    print(f"Mode: {Config.TRADING_MODE.upper()}")
    print(f"Wallet: {Config.POLY_PROXY_WALLET}")
    print(f"Coins: {', '.join(Config.ENABLED_COINS)}")
    print(f"Timeframes: {Config.ENABLED_TIMEFRAMES}")
    print("="*70)
    print()
    
    # Initialize
    log_print("INFO", "INIT", "Starting bot...")
    
    gamma = GammaClient()
    
    scan_round = 0
    
    while True:
        scan_round += 1
        print(f"\n{'='*70}")
        print(f"SCAN ROUND #{scan_round} - {datetime.now().strftime('%H:%M:%S')}")
        print('='*70)
        
        # Discover markets
        markets = gamma.discover_markets()
        
        if not markets:
            log_print("WARN", "SCAN", "No active markets found. Waiting...")
        else:
            log_print("INFO", "SCAN", f"Found {len(markets)} active markets")
            
            # Group by timeframe
            by_tf = {}
            for m in markets:
                tf = m['timeframe']
                if tf not in by_tf:
                    by_tf[tf] = []
                by_tf[tf].append(m)
            
            for tf, tf_markets in sorted(by_tf.items()):
                print(f"\n  [{tf}m Timeframe - {len(tf_markets)} markets]")
                for m in tf_markets[:5]:  # Show first 5
                    status = "LIVE" if m['seconds_remaining'] < 300 else f"+{m['seconds_remaining']//60}m"
                    print(f"    {m['coin']:4} | Epoch: {m['epoch_timestamp']} | {status:8} | {m['question'][:50]}")
        
        # Wait before next scan
        print(f"\n[Waiting 10 seconds for next scan...]")
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_print("INFO", "SYSTEM", "Bot stopped by user")
    except Exception as e:
        log_print("ERROR", "SYSTEM", f"Fatal error: {e}")
