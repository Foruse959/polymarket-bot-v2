#!/usr/bin/env python3
"""
Oracle Lead Strategy Backtest

Tests whether Binance front-running actually makes money.

Methodology:
- Fetch 1-minute Binance klines (as proxy for 1s — resolution limited by API)
- Simulate 5-min markets: price at t=0 → price at t=5min
- Check if a detectable impulse at t=T gives actionable lead info
- Entry: when an impulse >= 0.15% occurs in last 1m before our check
- Verify: did the market resolve in that direction?

If win rate > 55%, add the strategy to the bot.
If < 55%, keep it out (doesn't meet break-even threshold after 7% fee).

Run:  python backtest/backtest_oracle_lead.py
"""

import sys
import os
import time
import requests
from typing import List, Dict, Tuple
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


BINANCE_ENDPOINTS = [
    'https://api.binance.com',
    'https://api1.binance.com',
    'https://data-api.binance.vision',
]

COINS = {
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT',
    'SOL': 'SOLUSDT',
}


def fetch_klines(symbol: str, interval: str = '1m', limit: int = 1000) -> List[Dict]:
    """Fetch historical klines from Binance."""
    for url in BINANCE_ENDPOINTS:
        try:
            r = requests.get(f"{url}/api/v3/klines",
                             params={'symbol': symbol, 'interval': interval,
                                     'limit': limit}, timeout=10)
            if r.status_code == 200:
                return [{
                    'open_time': int(k[0]),
                    'open': float(k[1]), 'high': float(k[2]),
                    'low': float(k[3]), 'close': float(k[4]),
                    'volume': float(k[5]),
                } for k in r.json()]
        except Exception:
            continue
    return []


@dataclass
class OracleTrade:
    coin: str
    direction: str
    entry_time_min: int
    entry_pct_move: float  # the impulse we saw
    outcome_move: float    # what actually happened in remaining time
    outcome: str           # 'win' or 'loss'
    seconds_remaining: int


def detect_oracle_impulse(candles: List[Dict], idx: int,
                          threshold_pct: float = 0.15) -> Tuple[str, float]:
    """
    Check if we have a fresh oracle-lead opportunity at index idx.

    Returns (direction, magnitude_pct) or (None, 0) if no signal.

    Simulates the oracle WebSocket's 3s rolling impulse detection, but
    on 1m candles we scale the threshold up to 0.15% (equivalent to
    0.05% per 20s × 3).
    """
    if idx < 2 or idx >= len(candles):
        return (None, 0.0)

    # Use a 2-candle window (2 minutes of price action)
    # If we saw the last 2 mins, we'd know the direction
    window_open = candles[idx - 1]['open']
    window_close = candles[idx]['close']
    pct_move = (window_close - window_open) / window_open * 100

    if abs(pct_move) < threshold_pct:
        return (None, 0.0)
    direction = 'UP' if pct_move > 0 else 'DOWN'
    return (direction, abs(pct_move))


def backtest_oracle(coin: str, candles: List[Dict],
                    market_len_min: int = 5,
                    threshold_pct: float = 0.15) -> List[OracleTrade]:
    """
    Walk forward through candles.
    Every minute, check for an impulse.
    If detected, assume we entered at candle[idx+1] and the market
    resolves at candle[idx + market_len_min].
    """
    trades: List[OracleTrade] = []
    n = len(candles)

    # Need at least 2 lookback + market_len_min forward
    for idx in range(2, n - market_len_min - 1):
        direction, magnitude = detect_oracle_impulse(candles, idx, threshold_pct)
        if not direction:
            continue

        # Market spans from entry to entry+market_len_min
        entry_price = candles[idx + 1]['open']
        exit_price = candles[idx + market_len_min]['close']
        outcome_move = (exit_price - entry_price) / entry_price * 100

        if direction == 'UP':
            won = outcome_move > 0
        else:
            won = outcome_move < 0

        trades.append(OracleTrade(
            coin=coin,
            direction=direction,
            entry_time_min=idx,
            entry_pct_move=magnitude * (1 if direction == 'UP' else -1),
            outcome_move=outcome_move,
            outcome='win' if won else 'loss',
            seconds_remaining=market_len_min * 60,
        ))

    return trades


def main():
    print("=" * 74)
    print("  ORACLE LEAD STRATEGY BACKTEST")
    print("  Testing: Binance impulse -> Polymarket market follow-through")
    print("=" * 74)

    all_trades: List[OracleTrade] = []

    for coin, sym in COINS.items():
        print(f"\n  Fetching 1000x 1m candles for {coin}...")
        candles = fetch_klines(sym, '1m', 1000)
        if not candles:
            print(f"  [{coin}] FAILED to fetch — skipping")
            continue
        print(f"  [{coin}] {len(candles)} candles "
              f"({candles[0]['open_time']} → {candles[-1]['open_time']})")

        # Test multiple thresholds
        for threshold in [0.10, 0.15, 0.20, 0.30]:
            trades = backtest_oracle(coin, candles, 5, threshold)
            if not trades:
                continue
            wins = sum(1 for t in trades if t.outcome == 'win')
            wr = wins / len(trades) * 100
            print(f"  [{coin}] threshold={threshold:.2f}% -> "
                  f"{len(trades):3d} trades, {wr:5.1f}% WR")

        # Use 0.15% for the full aggregate
        coin_trades = backtest_oracle(coin, candles, 5, 0.15)
        all_trades.extend(coin_trades)

    if not all_trades:
        print("\n  No trades generated. Backtest failed.")
        return 1

    # ─────────────────────────────────────────────
    # Aggregate
    # ─────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("  AGGREGATE RESULTS (threshold=0.15%, 5-min markets)")
    print("=" * 74)

    total = len(all_trades)
    wins = sum(1 for t in all_trades if t.outcome == 'win')
    losses = total - wins
    wr = wins / total * 100

    # Compute PnL assuming $1 per trade, buy at 0.55, win=$1/lose=$0
    # With 7% fee on entry
    entry_price = 0.55
    fee = 0.07
    pnl = 0.0
    for t in all_trades:
        if t.outcome == 'win':
            pnl += (1.0 - entry_price) / entry_price - fee
        else:
            pnl += -1.0 - fee
    avg_pnl_pct = pnl / total * 100

    # Break-even WR:
    # 0 = WR * (1 - 0.55) / 0.55 - (1 - WR) * 1 - fee
    # → WR ≈ (1 + fee) / (1 + fee + (1-0.55)/0.55)
    # ≈ (1.07) / (1.07 + 0.818) = 56.7%
    break_even_wr = (1 + fee) / (1 + fee + (1 - entry_price) / entry_price) * 100

    print(f"\n  Total trades:  {total}")
    print(f"  Wins:          {wins} ({wr:.1f}%)")
    print(f"  Losses:        {losses} ({100 - wr:.1f}%)")
    print(f"  Avg PnL/trade: {avg_pnl_pct:+.1f}% (entry=${entry_price:.2f}, fee={fee:.0%})")
    print(f"  Break-even WR: {break_even_wr:.1f}%")

    # Per-coin breakdown
    print(f"\n  Per-coin:")
    for coin in COINS:
        ct = [t for t in all_trades if t.coin == coin]
        if not ct:
            continue
        cw = sum(1 for t in ct if t.outcome == 'win')
        cwr = cw / len(ct) * 100
        print(f"    {coin}: {len(ct):3d} trades, {cwr:5.1f}% WR")

    # Per-direction breakdown
    up_t = [t for t in all_trades if t.direction == 'UP']
    dn_t = [t for t in all_trades if t.direction == 'DOWN']
    if up_t:
        uw = sum(1 for t in up_t if t.outcome == 'win') / len(up_t) * 100
        print(f"    UP   impulses: {len(up_t):3d} trades, {uw:5.1f}% WR")
    if dn_t:
        dw = sum(1 for t in dn_t if t.outcome == 'win') / len(dn_t) * 100
        print(f"    DOWN impulses: {len(dn_t):3d} trades, {dw:5.1f}% WR")

    # Bucket by magnitude
    print(f"\n  By impulse magnitude:")
    for lo, hi in [(0.15, 0.25), (0.25, 0.40), (0.40, 1.00)]:
        bucket = [t for t in all_trades if lo <= abs(t.entry_pct_move) < hi]
        if bucket:
            bw = sum(1 for t in bucket if t.outcome == 'win') / len(bucket) * 100
            print(f"    {lo:.2f}-{hi:.2f}%: {len(bucket):3d} trades, {bw:5.1f}% WR")

    print("\n" + "=" * 74)
    if wr >= break_even_wr:
        print(f"  PASS: {wr:.1f}% WR >= {break_even_wr:.1f}% break-even")
        print(f"  -> Oracle lead strategy is PROFITABLE. Safe to add to bot.")
    elif wr >= 50:
        print(f"  MIXED: {wr:.1f}% WR (break-even {break_even_wr:.1f}%)")
        print(f"  -> Coin-flip edge. Only add with tight magnitude filter.")
    else:
        print(f"  FAIL: {wr:.1f}% WR < 50% (break-even {break_even_wr:.1f}%)")
        print(f"  -> Strategy loses money. DO NOT add to bot.")
    print("=" * 74)

    return 0 if wr >= break_even_wr else 1


if __name__ == '__main__':
    sys.exit(main())
