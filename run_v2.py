#!/usr/bin/env python3
"""
5MIN_TRADE v2.1 — Beast Mode Runner

Fully integrated with:
- V2 Risk Manager (Kelly sizing, circuit breakers)
- 6 research-backed strategies (ensemble voting)
- Signal Ranker (multi-strategy agreement boosting)
- pUSD collateral display
- Live dashboard server on port 8080
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from data.gamma_client import GammaClient
from data.clob_client import ClobClient
from trading.v2_risk_manager import V2RiskManager
from trading.signal_ranker import SignalRanker


# Global state for dashboard
BOT_STATE = {
    'started_at': None,
    'scan_round': 0,
    'markets_found': 0,
    'signals_generated': 0,
    'trades_executed': 0,
    'last_signals': [],
    'last_markets': [],
    'logs': [],
    'risk_stats': {},
    'strategy_stats': {},
}


def log(level: str, msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level:5}] {msg}"
    print(line, flush=True)
    BOT_STATE['logs'].append({'ts': ts, 'level': level, 'msg': msg})
    if len(BOT_STATE['logs']) > 500:
        BOT_STATE['logs'] = BOT_STATE['logs'][-500:]
    # Also write to log file
    os.makedirs("logs", exist_ok=True)
    with open("logs/v2_trading.log", "a") as f:
        f.write(json.dumps({'ts': ts, 'level': level, 'msg': msg}) + "\n")


async def run_bot():
    # Parse args
    if '--live' in sys.argv:
        Config.TRADING_MODE = 'live'
    elif '--paper' in sys.argv:
        Config.TRADING_MODE = 'paper'

    Config.print_status()
    BOT_STATE['started_at'] = datetime.now(timezone.utc).isoformat()

    # Initialize
    log("INIT", f"Starting 5min_trade v{Config.VERSION} ({Config.VERSION_NAME})")
    gamma = GammaClient()
    clob = ClobClient()
    risk_mgr = V2RiskManager(Config.STARTING_BALANCE)
    signal_ranker = SignalRanker()

    log("INIT", f"Strategies: {signal_ranker.get_strategy_names()}")
    log("INIT", f"Risk: Kelly={Config.KELLY_FRACTION} | Max DD={Config.DRAWDOWN_HALT_PCT}%")
    log("INIT", f"Collateral: pUSD | Exchange: CTF V2")

    # Try to initialize CLOB for live trading
    if Config.TRADING_MODE == 'live' and Config.is_live_ready():
        log("INIT", "Connecting to CLOB V2...")
        try:
            pk = Config.POLY_PRIVATE_KEY.strip()
            funder = Config.get_funder_address()
            client = clob.init_py_clob_client(pk, funder, Config.POLY_SIGNATURE_TYPE)
            if client:
                log("INIT", "✅ CLOB V2 connected!")
            else:
                log("WARN", "CLOB init returned None — paper mode")
        except Exception as e:
            log("ERROR", f"CLOB init failed: {e}")

    scan_round = 0

    while True:
        scan_round += 1
        BOT_STATE['scan_round'] = scan_round

        print(f"\n{'━'*70}", flush=True)
        log("SCAN", f"Round #{scan_round} | {risk_mgr.get_status_line()}")
        print('━' * 70, flush=True)

        # Risk check
        can_trade, reason = risk_mgr.can_trade()
        if not can_trade:
            log("RISK", f"⚠️ {reason}")
            BOT_STATE['risk_stats'] = {'halted': True, 'reason': reason}
            await asyncio.sleep(30)
            continue

        BOT_STATE['risk_stats'] = {
            'halted': False,
            'balance': risk_mgr.balance,
            'peak': risk_mgr.peak_balance,
            'drawdown_pct': risk_mgr._drawdown_pct(),
            'wins': risk_mgr.wins,
            'losses': risk_mgr.losses,
            'consecutive_wins': risk_mgr.consecutive_wins,
            'consecutive_losses': risk_mgr.consecutive_losses,
            'total_pnl': risk_mgr.total_pnl,
        }

        # Discover markets
        try:
            markets = gamma.discover_markets()
        except Exception as e:
            log("ERROR", f"Market discovery failed: {e}")
            markets = []

        BOT_STATE['markets_found'] = len(markets) if markets else 0

        if not markets:
            log("SCAN", "No active markets. Waiting...")
            await asyncio.sleep(10)
            continue

        log("SCAN", f"Found {len(markets)} active markets")
        BOT_STATE['last_markets'] = [
            {'coin': m['coin'], 'tf': m['timeframe'], 'secs': m['seconds_remaining'], 'q': m['question'][:60]}
            for m in markets[:10]
        ]

        # Build context
        context = {
            'clob': clob,
            'risk_mgr': risk_mgr,
            'seconds_remaining': markets[0].get('seconds_remaining', 300) if markets else 300,
        }

        # Run signal ranker
        try:
            signals = await signal_ranker.get_ranked_signals(markets, context)
        except Exception as e:
            log("ERROR", f"Signal generation failed: {e}")
            signals = []

        BOT_STATE['signals_generated'] += len(signals)
        BOT_STATE['last_signals'] = [
            {
                'coin': s.coin, 'dir': s.direction, 'conf': s.confidence,
                'strategy': s.strategy, 'limit': s.limit_price,
                'agreement': s.metadata.get('agreement_count', 1),
                'rationale': s.rationale[:100],
            }
            for s in signals[:10]
        ]

        if signals:
            log("SIGNAL", f"🎯 {len(signals)} signals generated:")
            for i, sig in enumerate(signals[:5]):
                agreement = sig.metadata.get('agreement_count', 1)
                stars = '⭐' * min(agreement, 3)
                log("SIGNAL", f"  #{i+1} {stars} {sig.coin} {sig.direction} | "
                    f"Conf: {sig.confidence:.0%} | {sig.strategy} | "
                    f"{'Limit: ' + str(sig.limit_price) if sig.limit_price else 'MKT'}")

                # Paper trade simulation
                if Config.is_paper():
                    size = risk_mgr.calculate_position_size(sig.confidence, sig.strategy)
                    if size >= Config.POLYMARKET_MIN_ORDER_SIZE:
                        log("PAPER", f"    📋 Would trade: {Config.format_balance(size)} | "
                            f"{sig.rationale[:80]}")
                        BOT_STATE['trades_executed'] += 1
        else:
            log("SCAN", "No signals above threshold")

        # Strategy performance tracking
        strat_counts = {}
        for s in signals:
            strat_counts[s.strategy] = strat_counts.get(s.strategy, 0) + 1
        BOT_STATE['strategy_stats'] = strat_counts

        # Heartbeat
        clob.send_heartbeat()

        await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log("SYSTEM", "Bot stopped by user")
        print("\n👋 Bye!", flush=True)
    except Exception as e:
        log("FATAL", f"Unhandled error: {e}")
        import traceback
        traceback.print_exc()
