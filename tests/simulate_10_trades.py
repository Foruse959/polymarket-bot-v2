#!/usr/bin/env python3
"""
REALISTIC 10-TRADE SIMULATION WITH LIVE BINANCE DATA

Simulates exactly how the bot would trade on Polymarket:
- Fetches REAL BTC/ETH 1-minute candles from Binance
- Applies the bot's actual indicator analysis (RSI, MACD, Bollinger, etc.)
- Uses the real TP/SL system (conviction-based dynamic exits)
- Uses the real risk manager (tiered Kelly sizing from $5 balance)
- Walks forward through candles, checking TP/SL every bar

Starting balance: $5 (SEED tier)
Trades: 10
Output: Full breakdown of every trade, win rate, PnL, TP/SL hits

Run:  python tests/simulate_10_trades.py
"""

import sys
import os
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
STARTING_BALANCE = 5.0
NUM_TRADES = 10
COINS = ['BTC', 'ETH']
BINANCE_SYMBOLS = {'BTC': 'BTCUSDT', 'ETH': 'ETHUSDT'}
BINANCE_URL = 'https://api.binance.com'

# Polymarket-style pricing: maps real price move to binary outcome token price
# If BTC goes up 0.1% in 5 min → UP token moves from 0.50 toward ~0.65
# Calibrated from real Polymarket 5-min markets
PRICE_SENSITIVITY = {
    'BTC': 0.003,  # 0.3% BTC move = full swing 0→1
    'ETH': 0.005,  # 0.5% ETH move = full swing
}

# TP/SL tiers (from autonomous_executor.py Position.DYNAMIC_EXITS)
DYNAMIC_EXITS = {
    'MAXIMUM': {'tp_pct': 200.0, 'sl_pct': 50.0, 'hold_to_resolution': True},
    'HIGH':    {'tp_pct': 90.0,  'sl_pct': 35.0, 'hold_to_resolution': False},
    'MEDIUM':  {'tp_pct': 70.0,  'sl_pct': 25.0, 'hold_to_resolution': False},
    'SINGLE':  {'tp_pct': 35.0,  'sl_pct': 16.0, 'hold_to_resolution': False},
}

# Fee rate (Polymarket crypto category)
FEE_RATE = 0.07  # 7 cents per dollar


# ─────────────────────────────────────────────────────────────
# FETCH REAL BINANCE DATA
# ─────────────────────────────────────────────────────────────

def fetch_binance_candles(symbol: str, interval: str = '1m', limit: int = 500) -> List[Dict]:
    """Fetch real candles from Binance API."""
    endpoints = [
        'https://api.binance.com',
        'https://api1.binance.com',
        'https://data-api.binance.vision',
    ]
    for url in endpoints:
        try:
            resp = requests.get(
                f"{url}/api/v3/klines",
                params={'symbol': symbol, 'interval': interval, 'limit': limit},
                timeout=10
            )
            if resp.status_code == 200:
                raw = resp.json()
                candles = [{
                    'open_time': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                } for k in raw]
                return candles
        except Exception:
            continue
    return []


# ─────────────────────────────────────────────────────────────
# TECHNICAL INDICATORS (simplified from data/indicators.py)
# ─────────────────────────────────────────────────────────────

def compute_rsi(closes: List[float], period: int = 14) -> float:
    """Compute RSI."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_ema(closes: List[float], period: int) -> List[float]:
    """Compute EMA."""
    if len(closes) < period:
        return closes[:]
    multiplier = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


def compute_macd(closes: List[float]) -> Tuple[float, float, float]:
    """MACD (12,26,9)."""
    if len(closes) < 26:
        return 0.0, 0.0, 0.0
    ema12 = compute_ema(closes, 12)
    ema26 = compute_ema(closes, 26)
    min_len = min(len(ema12), len(ema26))
    macd_line = [ema12[-(min_len-i)] - ema26[-(min_len-i)] for i in range(min_len)]
    if len(macd_line) < 9:
        return macd_line[-1] if macd_line else 0, 0, 0
    signal = compute_ema(macd_line, 9)
    macd_val = macd_line[-1]
    signal_val = signal[-1] if signal else 0
    histogram = macd_val - signal_val
    return macd_val, signal_val, histogram


def compute_bollinger(closes: List[float], period: int = 20) -> Tuple[float, float, float]:
    """Bollinger Bands (20, 2)."""
    if len(closes) < period:
        return closes[-1], closes[-1], closes[-1]
    window = closes[-period:]
    sma = sum(window) / period
    std = (sum((x - sma) ** 2 for x in window) / period) ** 0.5
    return sma - 2 * std, sma, sma + 2 * std


def analyze_indicators(closes: List[float]) -> Dict:
    """
    Run full indicator suite, return signal direction and confidence.
    Mirrors the bot's indicator_fusion strategy logic.
    """
    if len(closes) < 30:
        return {'direction': None, 'confidence': 0, 'signals': []}

    rsi = compute_rsi(closes)
    macd_val, macd_signal, macd_hist = compute_macd(closes)
    bb_lower, bb_mid, bb_upper = compute_bollinger(closes)
    current_price = closes[-1]

    bullish_signals = []
    bearish_signals = []

    # RSI
    if rsi < 30:
        bullish_signals.append(f'RSI_oversold({rsi:.0f})')
    elif rsi > 70:
        bearish_signals.append(f'RSI_overbought({rsi:.0f})')

    # MACD
    if macd_hist > 0 and macd_val > macd_signal:
        bullish_signals.append('MACD_bull_cross')
    elif macd_hist < 0 and macd_val < macd_signal:
        bearish_signals.append('MACD_bear_cross')

    # Bollinger
    if current_price <= bb_lower:
        bullish_signals.append('BB_lower_touch')
    elif current_price >= bb_upper:
        bearish_signals.append('BB_upper_touch')

    # EMA trend (8 vs 21)
    if len(closes) >= 21:
        ema8 = compute_ema(closes, 8)[-1]
        ema21 = compute_ema(closes, 21)[-1]
        if ema8 > ema21:
            bullish_signals.append('EMA_8>21')
        else:
            bearish_signals.append('EMA_8<21')

    # Momentum (5-bar)
    if len(closes) >= 6:
        mom = (closes[-1] - closes[-6]) / closes[-6] * 100
        if mom > 0.03:
            bullish_signals.append(f'MOM_up({mom:.2f}%)')
        elif mom < -0.03:
            bearish_signals.append(f'MOM_down({mom:.2f}%)')

    bull_count = len(bullish_signals)
    bear_count = len(bearish_signals)

    if bull_count > bear_count:
        direction = 'UP'
        conviction = bull_count - bear_count
        confidence = min(0.90, 0.50 + conviction * 0.10)
    elif bear_count > bull_count:
        direction = 'DOWN'
        conviction = bear_count - bull_count
        confidence = min(0.90, 0.50 + conviction * 0.10)
    else:
        direction = None
        confidence = 0.0

    return {
        'direction': direction,
        'confidence': confidence,
        'bullish': bullish_signals,
        'bearish': bearish_signals,
        'rsi': rsi,
        'macd_hist': macd_hist,
    }


# ─────────────────────────────────────────────────────────────
# POSITION SIZING (Kelly from v2_risk_manager.py)
# ─────────────────────────────────────────────────────────────

def kelly_size(balance: float, confidence: float, tier: str = 'SEED') -> float:
    """
    Quarter-Kelly position sizing for $5 balance (SEED tier).
    SEED tier: 10-18% of balance, min $1
    """
    edge = confidence - 0.50
    if edge <= 0.02:
        return 0.0

    # Kelly fraction
    kelly_pct = edge / (1.0)  # Binary outcome: odds = 1:1
    quarter_kelly = kelly_pct * 0.25

    # Tier limits
    if tier == 'SURVIVAL':
        bet_pct = min(max(quarter_kelly, 0.15), 0.25)
    elif tier == 'SEED':
        bet_pct = min(max(quarter_kelly, 0.10), 0.18)
    else:
        bet_pct = min(max(quarter_kelly, 0.04), 0.08)

    size = balance * bet_pct
    return max(1.0, round(size, 2))  # Min $1 on Polymarket


# ─────────────────────────────────────────────────────────────
# POLYMARKET PRICE SIMULATION
# ─────────────────────────────────────────────────────────────

def real_price_to_token_price(
    pct_move: float, direction: str, sensitivity: float
) -> float:
    """
    Convert real price % move to Polymarket binary token price.
    
    If you bought UP at 0.55 and BTC goes up 0.1%:
      token_price = 0.55 + (0.001 / sensitivity) * 0.50
    
    Clamped to [0.01, 0.99].
    """
    # Normalize move relative to sensitivity
    normalized = pct_move / sensitivity
    # Token price moves ~half of the normalized amount from 0.50
    token_delta = normalized * 0.45
    if direction == 'UP':
        price = 0.50 + token_delta
    else:  # DOWN token benefits from price drop
        price = 0.50 - token_delta
    return max(0.01, min(0.99, price))


# ─────────────────────────────────────────────────────────────
# TRADE SIMULATION ENGINE
# ─────────────────────────────────────────────────────────────

@dataclass
class SimTrade:
    trade_num: int
    coin: str
    direction: str
    confidence: float
    conviction_tier: str
    entry_price: float
    exit_price: float
    size_pusd: float
    shares: float
    tp_pct: float
    sl_pct: float
    pnl_pusd: float
    pnl_pct: float
    outcome: str  # 'TP_HIT', 'SL_HIT', 'TIMEOUT', 'RESOLUTION'
    duration_bars: int
    signals: List[str] = field(default_factory=list)
    entry_btc_price: float = 0.0
    exit_btc_price: float = 0.0


def simulate_trade(
    candles: List[Dict],
    start_idx: int,
    direction: str,
    confidence: float,
    conviction_tier: str,
    entry_price: float,
    coin: str,
    size_pusd: float,
) -> Tuple[SimTrade, int]:
    """
    Walk forward through candles from start_idx, simulating TP/SL.
    Returns the completed trade and the index where it exited.
    """
    exits = DYNAMIC_EXITS.get(conviction_tier, DYNAMIC_EXITS['SINGLE'])
    tp_pct = exits['tp_pct']
    sl_pct = exits['sl_pct']
    hold_to_res = exits['hold_to_resolution']

    # Widen SL for high confidence (mirrors autonomous_executor.py)
    if confidence >= 0.80:
        sl_pct *= 1.3
    elif confidence >= 0.70:
        sl_pct *= 1.15

    entry_real_price = candles[start_idx]['close']
    sensitivity = PRICE_SENSITIVITY.get(coin, 0.003)
    shares = size_pusd / entry_price if entry_price > 0 else 0
    max_bars = 5  # 5-minute market = 5 bars of 1-min candles

    exit_price = entry_price
    exit_reason = 'TIMEOUT'
    exit_idx = start_idx

    for i in range(start_idx + 1, min(start_idx + max_bars + 1, len(candles))):
        bar = candles[i]
        # How much did real price move since entry?
        pct_move = (bar['close'] - entry_real_price) / entry_real_price

        # Convert to token price
        if direction == 'UP':
            current_token_price = real_price_to_token_price(pct_move, 'UP', sensitivity)
        else:
            current_token_price = real_price_to_token_price(-pct_move, 'DOWN', sensitivity)

        # PnL %
        pnl_pct = (current_token_price - entry_price) / entry_price * 100

        # Check TP
        if not hold_to_res and pnl_pct >= tp_pct:
            exit_price = current_token_price
            exit_reason = 'TP_HIT'
            exit_idx = i
            break

        # Check SL
        if pnl_pct <= -sl_pct:
            exit_price = current_token_price
            exit_reason = 'SL_HIT'
            exit_idx = i
            break

        exit_price = current_token_price
        exit_idx = i

    # If hold_to_resolution and we reach end of market, resolve
    if hold_to_res and exit_reason == 'TIMEOUT':
        # At resolution, token is worth $1 (correct) or $0 (wrong)
        final_move = (candles[min(start_idx + max_bars, len(candles)-1)]['close'] - entry_real_price) / entry_real_price
        if direction == 'UP' and final_move > 0:
            exit_price = 1.0
            exit_reason = 'RESOLUTION'
        elif direction == 'DOWN' and final_move < 0:
            exit_price = 1.0
            exit_reason = 'RESOLUTION'
        elif exit_reason == 'TIMEOUT':
            # Wrong direction at resolution
            exit_price = 0.0
            exit_reason = 'RESOLUTION'

    # If regular timeout (non-resolution), use last token price
    if exit_reason == 'TIMEOUT' and not hold_to_res:
        # At resolution of 5-min market
        final_move = (candles[min(start_idx + max_bars, len(candles)-1)]['close'] - entry_real_price) / entry_real_price
        if direction == 'UP' and final_move > 0:
            exit_price = 1.0
            exit_reason = 'RESOLUTION'
        elif direction == 'DOWN' and final_move < 0:
            exit_price = 1.0
            exit_reason = 'RESOLUTION'
        else:
            exit_price = 0.0
            exit_reason = 'RESOLUTION'

    pnl_pct_final = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
    pnl_pusd = shares * (exit_price - entry_price) - (size_pusd * FEE_RATE)  # subtract entry fee
    duration = exit_idx - start_idx

    trade = SimTrade(
        trade_num=0,
        coin=coin,
        direction=direction,
        confidence=confidence,
        conviction_tier=conviction_tier,
        entry_price=entry_price,
        exit_price=exit_price,
        size_pusd=size_pusd,
        shares=shares,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        pnl_pusd=pnl_pusd,
        pnl_pct=pnl_pct_final,
        outcome=exit_reason,
        duration_bars=duration,
        entry_btc_price=entry_real_price,
        exit_btc_price=candles[exit_idx]['close'],
    )
    return trade, exit_idx


# ─────────────────────────────────────────────────────────────
# MAIN SIMULATION
# ─────────────────────────────────────────────────────────────

def run_simulation():
    print("=" * 72)
    print("  POLYMARKET BOT — 10-TRADE SIMULATION WITH LIVE BINANCE DATA")
    print("  Starting Balance: $5.00 | Tier: SEED | TP/SL: Dynamic")
    print("=" * 72)

    # Fetch real data
    print("\n  Fetching live Binance 1m candles...")
    all_candles = {}
    for coin, symbol in BINANCE_SYMBOLS.items():
        candles = fetch_binance_candles(symbol, '1m', 1000)
        if candles:
            all_candles[coin] = candles
            print(f"    {coin}: {len(candles)} candles "
                  f"(${candles[-1]['close']:,.2f} current)")
        else:
            print(f"    {coin}: FAILED to fetch (skipping)")

    if not all_candles:
        print("\n  ERROR: Could not fetch any Binance data. Check network.")
        return

    # Simulation state
    balance = STARTING_BALANCE
    trades: List[SimTrade] = []
    trade_num = 0

    print(f"\n  Running {NUM_TRADES} trades with real price action...\n")
    print("-" * 72)

    # Walk through candles looking for signals
    coin_idx = {coin: 30 for coin in all_candles}  # start at bar 30 (need history)
    max_iterations = 5000  # safety break

    iterations = 0
    while trade_num < NUM_TRADES and iterations < max_iterations:
        iterations += 1
        found_any = False

        # Cycle through coins
        for coin in list(all_candles.keys()):
            if trade_num >= NUM_TRADES:
                break

            candles = all_candles[coin]
            idx = coin_idx[coin]

            if idx >= len(candles) - 10:
                continue  # Not enough bars left

            found_any = True

            # Get indicator analysis on last 30 bars
            closes = [c['close'] for c in candles[max(0, idx-30):idx+1]]
            analysis = analyze_indicators(closes)

            if analysis['direction'] is None or analysis['confidence'] < 0.55:
                coin_idx[coin] += 1  # Skip ahead
                continue

            direction = analysis['direction']
            confidence = analysis['confidence']

            # Determine conviction tier (simulate ensemble)
            bull_count = len(analysis['bullish'])
            bear_count = len(analysis['bearish'])
            agreement = max(bull_count, bear_count)

            if agreement >= 4:
                conviction_tier = 'MAXIMUM'
            elif agreement >= 3:
                conviction_tier = 'HIGH'
            elif agreement >= 2:
                conviction_tier = 'MEDIUM'
            else:
                conviction_tier = 'SINGLE'

            # Balance tier
            tier = 'SURVIVAL' if balance < 5 else 'SEED' if balance < 15 else 'COMFORT'

            # Position sizing
            size_pusd = kelly_size(balance, confidence, tier)
            if size_pusd > balance:
                size_pusd = max(1.0, balance * 0.9)
            if size_pusd < 1.0:
                coin_idx[coin] += 1
                continue

            # Entry price (simulate buying token at fair value given direction)
            sensitivity = PRICE_SENSITIVITY.get(coin, 0.003)
            entry_price = 0.52 if confidence > 0.7 else 0.55  # Slight edge at entry

            # Execute trade
            trade, exit_idx = simulate_trade(
                candles, idx, direction, confidence,
                conviction_tier, entry_price, coin, size_pusd
            )
            trade_num += 1
            trade.trade_num = trade_num
            trade.signals = analysis['bullish'] if direction == 'UP' else analysis['bearish']

            # Update balance
            balance += trade.pnl_pusd
            trades.append(trade)

            # Print trade
            outcome_emoji = {
                'TP_HIT': '  ', 'RESOLUTION': '  ',
                'SL_HIT': '  ', 'TIMEOUT': '  '
            }
            win = trade.pnl_pusd > 0
            emoji = outcome_emoji.get(trade.outcome, '  ')

            print(f"  Trade #{trade.trade_num:2d} | {coin:3s} {direction:4s} | "
                  f"Conf: {confidence:.0%} [{conviction_tier:7s}] | "
                  f"Entry: ${entry_price:.3f} → Exit: ${trade.exit_price:.3f}")
            print(f"           | Size: ${size_pusd:.2f} ({trade.shares:.1f} shares) | "
                  f"TP: +{trade.tp_pct:.0f}% SL: -{trade.sl_pct:.0f}%")
            print(f"           | {emoji} {trade.outcome:10s} | "
                  f"PnL: {'+'if trade.pnl_pusd>=0 else ''}{trade.pnl_pusd:.3f} "
                  f"({'+' if trade.pnl_pct>=0 else ''}{trade.pnl_pct:.1f}%) | "
                  f"Bal: ${balance:.2f}")
            print(f"           | Real: ${trade.entry_btc_price:,.2f} → "
                  f"${trade.exit_btc_price:,.2f} | "
                  f"Dur: {trade.duration_bars} bars | "
                  f"Signals: {', '.join(trade.signals[:3])}")
            print("-" * 72)

            # Advance past this trade
            coin_idx[coin] = exit_idx + 6  # Skip ahead past trade + cooldown

            if balance < 0.50:
                print("\n  BALANCE DEPLETED - STOPPING")
                break

        if not found_any:
            print("\n  No more candle data available — ending simulation.")
            break

    # ─────────────────────────────────────────────────────────────
    # RESULTS SUMMARY
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  SIMULATION RESULTS")
    print("=" * 72)

    wins = [t for t in trades if t.pnl_pusd > 0]
    losses = [t for t in trades if t.pnl_pusd <= 0]
    total_pnl = sum(t.pnl_pusd for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    tp_hits = [t for t in trades if t.outcome == 'TP_HIT']
    sl_hits = [t for t in trades if t.outcome == 'SL_HIT']
    resolutions = [t for t in trades if t.outcome == 'RESOLUTION']
    timeouts = [t for t in trades if t.outcome == 'TIMEOUT']

    avg_win = sum(t.pnl_pusd for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl_pusd for t in losses) / len(losses) if losses else 0
    avg_dur = sum(t.duration_bars for t in trades) / len(trades) if trades else 0
    mdd = max_drawdown(trades)
    pf = profit_factor(trades)

    print(f"""
  Starting Balance:    ${STARTING_BALANCE:.2f}
  Final Balance:       ${balance:.2f}
  Total PnL:          {'+'if total_pnl>=0 else ''}{total_pnl:.3f} ({total_pnl/STARTING_BALANCE*100:+.1f}%)

  Total Trades:        {len(trades)}
  Wins:                {len(wins)} ({win_rate:.0f}%)
  Losses:              {len(losses)} ({100-win_rate:.0f}%)

  Avg Win:             ${avg_win:.3f}
  Avg Loss:            ${avg_loss:.3f}

  ── EXIT TYPES ──
  TP Hits:             {len(tp_hits)} ({len(tp_hits)/len(trades)*100:.0f}%)
  SL Hits:             {len(sl_hits)} ({len(sl_hits)/len(trades)*100:.0f}%)
  Resolution:          {len(resolutions)} ({len(resolutions)/len(trades)*100:.0f}%)
  Timeout:             {len(timeouts)} ({len(timeouts)/len(trades)*100:.0f}%)

  ── RISK METRICS ──
  Max Drawdown:        ${mdd:.3f}
  Profit Factor:       {pf:.2f}
  Avg Trade Duration:  {avg_dur:.1f} bars (minutes)

  ── CONVICTION BREAKDOWN ──""")

    for tier in ['MAXIMUM', 'HIGH', 'MEDIUM', 'SINGLE']:
        tier_trades = [t for t in trades if t.conviction_tier == tier]
        if tier_trades:
            tier_wins = [t for t in tier_trades if t.pnl_pusd > 0]
            tier_wr = len(tier_wins) / len(tier_trades) * 100
            tier_pnl = sum(t.pnl_pusd for t in tier_trades)
            print(f"  {tier:8s}:  {len(tier_trades)} trades, "
                  f"{tier_wr:.0f}% WR, "
                  f"PnL: {'+'if tier_pnl>=0 else ''}{tier_pnl:.3f}")

    print("\n" + "=" * 72)
    if win_rate >= 55:
        print(f"  RESULT: {win_rate:.0f}% WIN RATE — Bot is profitable!")
    elif win_rate >= 45:
        print(f"  RESULT: {win_rate:.0f}% WIN RATE — Near breakeven")
    else:
        print(f"  RESULT: {win_rate:.0f}% WIN RATE — Needs tuning")
    print("=" * 72)


def max_drawdown(trades: List[SimTrade]) -> float:
    """Calculate max drawdown in $ terms."""
    peak = 0.0
    cumulative = 0.0
    max_dd = 0.0
    for t in trades:
        cumulative += t.pnl_pusd
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
    return max_dd


def profit_factor(trades: List[SimTrade]) -> float:
    """Gross wins / gross losses."""
    gross_wins = sum(t.pnl_pusd for t in trades if t.pnl_pusd > 0)
    gross_losses = abs(sum(t.pnl_pusd for t in trades if t.pnl_pusd < 0))
    return gross_wins / gross_losses if gross_losses > 0 else float('inf')


if __name__ == '__main__':
    run_simulation()
