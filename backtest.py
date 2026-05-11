"""
Backtester — Validate strategies against historical Binance kline data.

Simulates the 5min_trade bot against real historical price data from Binance.
Generates synthetic Polymarket-style UP/DOWN markets from BTC/ETH/SOL price
movements and runs all strategies against them.

Usage:
    python backtest.py                  # Last 24 hours, all strategies
    python backtest.py --hours 48       # Last 48 hours
    python backtest.py --coin BTC       # BTC only
    python backtest.py --strategy oracle_arb  # Single strategy
"""

import argparse
import asyncio
import time
import math
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

# Add parent to path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from strategies.dynamic_picker import DynamicPicker
from strategies.base_strategy import BaseStrategy, TradeSignal
from data.clob_client import ClobClient


# ═══════════════════════════════════════════════════════════════════
# DATA: Fetch historical klines from Binance
# ═══════════════════════════════════════════════════════════════════

BINANCE_PAIRS = {
    'BTC': 'BTCUSDT', 'ETH': 'ETHUSDT', 'SOL': 'SOLUSDT', 'XRP': 'XRPUSDT',
}


def fetch_klines(symbol: str, interval: str = '1m', hours: int = 24) -> List[Dict]:
    """Fetch historical klines from Binance."""
    pair = BINANCE_PAIRS.get(symbol.upper(), f'{symbol.upper()}USDT')
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (hours * 3600 * 1000)
    
    all_klines = []
    current_start = start_ms
    
    while current_start < end_ms:
        try:
            resp = requests.get(
                'https://api.binance.com/api/v3/klines',
                params={
                    'symbol': pair,
                    'interval': interval,
                    'startTime': current_start,
                    'endTime': end_ms,
                    'limit': 1000,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                break
            
            data = resp.json()
            if not data:
                break
            
            for k in data:
                all_klines.append({
                    'open_time': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': k[6],
                })
            
            current_start = data[-1][6] + 1  # Next candle after last close_time
            time.sleep(0.1)  # Rate limit
            
        except Exception as e:
            print(f"Error fetching klines: {e}")
            break
    
    return all_klines


# ═══════════════════════════════════════════════════════════════════
# SIMULATION: Create synthetic Polymarket markets from klines
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SimulatedMarket:
    """A simulated 5-minute Polymarket market."""
    coin: str
    timeframe: int
    start_time: int  # ms
    end_time: int    # ms
    start_price: float
    end_price: float
    klines: List[Dict] = field(default_factory=list)
    
    @property
    def outcome(self) -> str:
        """Actual outcome: UP if price went up, DOWN if down."""
        return 'UP' if self.end_price >= self.start_price else 'DOWN'
    
    def get_up_probability_at(self, elapsed_pct: float) -> float:
        """Estimate UP probability at a point in time.
        
        Uses the intermediate klines to compute a running probability.
        """
        if not self.klines:
            return 0.50
        
        # Find the kline closest to this elapsed percentage
        idx = min(int(elapsed_pct * len(self.klines)), len(self.klines) - 1)
        current = self.klines[idx]['close']
        
        # Simple probability based on current vs start price
        pct_change = (current - self.start_price) / self.start_price * 100
        
        # Map: +1% move = ~70% UP probability, -1% = ~30%
        # Time decay: probability is more extreme closer to expiry
        time_factor = 1.0 + elapsed_pct * 2.0  # Grows from 1x to 3x
        prob = 0.5 + (pct_change * 0.1 * time_factor)
        return max(0.02, min(0.98, prob))


def generate_markets(klines: List[Dict], coin: str, timeframe: int = 5) -> List[SimulatedMarket]:
    """Generate simulated Polymarket markets from klines."""
    if not klines:
        return []
    
    markets = []
    candles_per_market = timeframe  # 1m candles per N-min market
    
    for i in range(0, len(klines) - candles_per_market, candles_per_market):
        market_klines = klines[i:i + candles_per_market]
        if len(market_klines) < candles_per_market:
            break
        
        market = SimulatedMarket(
            coin=coin,
            timeframe=timeframe,
            start_time=market_klines[0]['open_time'],
            end_time=market_klines[-1]['close_time'],
            start_price=market_klines[0]['open'],
            end_price=market_klines[-1]['close'],
            klines=market_klines,
        )
        markets.append(market)
    
    return markets


# ═══════════════════════════════════════════════════════════════════
# MOCK: Fake CLOB and feeds for strategies
# ═══════════════════════════════════════════════════════════════════

class MockClobClient:
    """Simulated CLOB with prices from kline data."""
    
    def __init__(self):
        self._prices: Dict[str, float] = {}
        self._fallback_prices: Dict[str, float] = {}
    
    def set_market_prices(self, up_token: str, down_token: str, up_prob: float):
        """Set simulated orderbook prices."""
        down_prob = 1.0 - up_prob
        spread = 0.02  # 2 cent spread
        
        self._prices[up_token] = {
            'best_bid': max(0.01, up_prob - spread/2),
            'best_ask': min(0.99, up_prob + spread/2),
            'bid_depth': 10.0,
            'ask_depth': 10.0,
            'spread': spread,
        }
        self._prices[down_token] = {
            'best_bid': max(0.01, down_prob - spread/2),
            'best_ask': min(0.99, down_prob + spread/2),
            'bid_depth': 10.0,
            'ask_depth': 10.0,
            'spread': spread,
        }
    
    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        return self._prices.get(token_id)
    
    def get_dual_orderbook(self, up_token: str, down_token: str) -> Optional[Dict]:
        up = self._prices.get(up_token)
        down = self._prices.get(down_token)
        if not up or not down:
            return None
        combined = up['best_ask'] + down['best_ask']
        return {
            'up': up, 'down': down,
            'combined_ask': combined,
            'arb_profit': 1.0 - combined,
        }
    
    def set_fallback_price(self, token_id: str, price: float):
        self._fallback_prices[token_id] = price


class MockBinanceFeed:
    """Simulated Binance feed from kline data."""
    
    def __init__(self):
        self.latest_prices: Dict[str, float] = {}
        self.price_history: Dict[str, deque] = {}
    
    def set_price(self, coin: str, price: float):
        self.latest_prices[coin] = price
        if coin not in self.price_history:
            self.price_history[coin] = deque(maxlen=120)
        # Create snapshot with .price and .timestamp attributes
        snap = type('Snap', (), {'price': price, 'timestamp': time.time()})()
        self.price_history[coin].append(snap)
    
    def get_price(self, coin: str) -> Optional[float]:
        return self.latest_prices.get(coin.upper())
    
    def get_price_history(self, coin: str) -> List:
        return list(self.price_history.get(coin.upper(), []))


class MockPolyFeed:
    """Simulated Polymarket feed."""
    
    def __init__(self):
        self.latest_prices: Dict[str, object] = {}
        self.price_history: Dict[str, deque] = {}
    
    def set_price(self, token_id: str, price: float):
        snap = type('Snap', (), {
            'token_id': token_id, 'price': price,
            'best_bid': max(0.01, price - 0.01),
            'best_ask': min(0.99, price + 0.01),
            'timestamp': time.time(),
        })()
        self.latest_prices[token_id] = snap
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=120)
        self.price_history[token_id].append(snap)


# ═══════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BacktestResult:
    """Result of a single backtest trade."""
    strategy: str
    coin: str
    direction: str
    entry_price: float
    exit_price: float
    confidence: float
    outcome: str  # 'win' or 'loss'
    pnl_pct: float
    fee_pct: float
    net_pnl_pct: float
    seconds_remaining: int


class Backtester:
    """Run strategies against historical data."""
    
    FEE_RATE = 0.0156  # Max taker fee
    
    def __init__(self, coins: List[str] = None, timeframe: int = 5):
        self.coins = coins or ['BTC']
        self.timeframe = timeframe
        self.picker = DynamicPicker()
        self.results: List[BacktestResult] = []
    
    async def run(self, hours: int = 24, strategy_filter: str = None):
        """Run backtest over historical data."""
        print(f"\n{'='*60}")
        print(f"  BACKTEST: {', '.join(self.coins)} | {self.timeframe}m | {hours}h")
        print(f"{'='*60}\n")
        
        for coin in self.coins:
            print(f"Fetching {coin} klines ({hours}h)...", flush=True)
            klines = fetch_klines(coin, '1m', hours)
            print(f"  Got {len(klines)} candles")
            
            markets = generate_markets(klines, coin, self.timeframe)
            print(f"  Generated {len(markets)} simulated markets\n")
            
            for i, market in enumerate(markets):
                # Test at multiple time points within each market
                for elapsed_pct in [0.2, 0.5, 0.7, 0.9]:
                    await self._test_market(market, elapsed_pct, strategy_filter)
        
        self._print_report()
    
    async def _test_market(self, market: SimulatedMarket, elapsed_pct: float,
                           strategy_filter: str = None):
        """Run strategies against a market at a specific time point."""
        up_prob = market.get_up_probability_at(elapsed_pct)
        seconds_total = market.timeframe * 60
        seconds_remaining = int(seconds_total * (1 - elapsed_pct))
        
        # Create tokens
        up_token = f"sim_up_{market.start_time}"
        down_token = f"sim_down_{market.start_time}"
        
        # Set up mock data
        mock_clob = MockClobClient()
        mock_clob.set_market_prices(up_token, down_token, up_prob)
        
        # Find the kline at the current elapsed percentage
        kline_idx = min(int(elapsed_pct * len(market.klines)), len(market.klines) - 1)
        current_price = market.klines[kline_idx]['close']
        
        mock_binance = MockBinanceFeed()
        mock_binance.set_price(market.coin, current_price)
        
        mock_poly = MockPolyFeed()
        mock_poly.set_price(up_token, up_prob)
        mock_poly.set_price(down_token, 1.0 - up_prob)
        
        # Create market dict
        market_dict = {
            'coin': market.coin,
            'timeframe': market.timeframe,
            'market_id': f"sim_{market.start_time}",
            'up_token_id': up_token,
            'down_token_id': down_token,
            'up_price': up_prob,
            'down_price': 1.0 - up_prob,
        }
        
        context = {
            'clob': mock_clob,
            'poly_feed': mock_poly,
            'binance_feed': mock_binance,
            'seconds_remaining': seconds_remaining,
        }
        
        # Run strategies
        if strategy_filter:
            # Run specific strategy
            for strat in self.picker.strategies:
                if strat.name == strategy_filter:
                    try:
                        signal = await strat.analyze(market_dict, context)
                        if signal and signal.confidence >= 0.25:
                            self._evaluate_signal(signal, market, seconds_remaining)
                    except Exception:
                        pass
                    break
        else:
            # Run dynamic picker
            try:
                signal = await self.picker.analyze(market_dict, context)
                if signal:
                    self._evaluate_signal(signal, market, seconds_remaining)
            except Exception:
                pass
    
    def _evaluate_signal(self, signal: TradeSignal, market: SimulatedMarket,
                         seconds_remaining: int):
        """Evaluate if a trade signal would have been profitable."""
        # Skip BOTH-side trades for simplicity
        if signal.direction == 'BOTH':
            return
        
        entry_price = signal.entry_price
        
        # Determine outcome
        actual_outcome = market.outcome
        won = signal.direction == actual_outcome
        
        # Exit price: $1.00 if correct, $0.00 if wrong
        # In practice, we'd exit before settlement, but for backtest assume settlement
        if won:
            exit_price = 1.0
        else:
            exit_price = 0.0
        
        # PnL
        gross_pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        fee_pct = self._dynamic_fee(entry_price) * 100  # Entry fee
        net_pnl_pct = gross_pnl_pct - fee_pct
        
        result = BacktestResult(
            strategy=signal.strategy,
            coin=market.coin,
            direction=signal.direction,
            entry_price=entry_price,
            exit_price=exit_price,
            confidence=signal.confidence,
            outcome='win' if won else 'loss',
            pnl_pct=gross_pnl_pct,
            fee_pct=fee_pct,
            net_pnl_pct=net_pnl_pct,
            seconds_remaining=seconds_remaining,
        )
        self.results.append(result)
    
    def _dynamic_fee(self, price: float) -> float:
        """Dynamic fee: peaks at 50%, low at extremes."""
        return self.FEE_RATE * 4 * price * (1 - price)
    
    def _print_report(self):
        """Print backtest results."""
        if not self.results:
            print("\nNo trades generated. Strategies didn't find opportunities.")
            return
        
        print(f"\n{'='*70}")
        print(f"  BACKTEST RESULTS")
        print(f"{'='*70}")
        
        total = len(self.results)
        wins = sum(1 for r in self.results if r.outcome == 'win')
        losses = total - wins
        win_rate = wins / total * 100 if total > 0 else 0
        
        avg_win = sum(r.net_pnl_pct for r in self.results if r.outcome == 'win') / max(wins, 1)
        avg_loss = sum(r.net_pnl_pct for r in self.results if r.outcome == 'loss') / max(losses, 1)
        total_pnl = sum(r.net_pnl_pct for r in self.results)
        avg_confidence = sum(r.confidence for r in self.results) / total
        
        print(f"\n  Total Trades: {total}")
        print(f"  Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%")
        print(f"  Avg Win: {avg_win:+.1f}% | Avg Loss: {avg_loss:+.1f}%")
        print(f"  Total PnL: {total_pnl:+.1f}%")
        print(f"  Avg Confidence: {avg_confidence:.0%}")
        
        # Per strategy breakdown
        strategies = set(r.strategy for r in self.results)
        print(f"\n  {'Strategy':<25} {'Trades':>7} {'Win%':>7} {'Avg PnL':>8} {'Total':>8}")
        print(f"  {'-'*55}")
        
        for strat in sorted(strategies):
            strat_trades = [r for r in self.results if r.strategy == strat]
            s_total = len(strat_trades)
            s_wins = sum(1 for r in strat_trades if r.outcome == 'win')
            s_wr = s_wins / s_total * 100 if s_total > 0 else 0
            s_avg = sum(r.net_pnl_pct for r in strat_trades) / s_total
            s_sum = sum(r.net_pnl_pct for r in strat_trades)
            emoji = '\u2705' if s_sum > 0 else '\u274c'
            print(f"  {emoji} {strat:<22} {s_total:>7} {s_wr:>6.1f}% {s_avg:>+7.1f}% {s_sum:>+7.1f}%")
        
        # Confidence calibration
        print(f"\n  Confidence Calibration:")
        for bucket_min in [0.25, 0.50, 0.75]:
            bucket_max = bucket_min + 0.25
            bucket = [r for r in self.results if bucket_min <= r.confidence < bucket_max]
            if bucket:
                actual_wr = sum(1 for r in bucket if r.outcome == 'win') / len(bucket) * 100
                print(f"    {bucket_min:.0%}-{bucket_max:.0%} confidence: "
                      f"{actual_wr:.0f}% actual win rate ({len(bucket)} trades)")
        
        print(f"\n{'='*70}\n")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description='Backtest 5min_trade strategies')
    parser.add_argument('--hours', type=int, default=24, help='Hours of history (default: 24)')
    parser.add_argument('--coin', type=str, default=None, help='Single coin (default: BTC,ETH,SOL)')
    parser.add_argument('--coins', type=str, default=None, help='Comma-separated coins')
    parser.add_argument('--timeframe', type=int, default=5, help='Market timeframe in minutes')
    parser.add_argument('--strategy', type=str, default=None, help='Test single strategy')
    args = parser.parse_args()
    
    coins = [args.coin] if args.coin else (args.coins.split(',') if args.coins else ['BTC', 'ETH', 'SOL'])
    
    bt = Backtester(coins=coins, timeframe=args.timeframe)
    await bt.run(hours=args.hours, strategy_filter=args.strategy)


if __name__ == '__main__':
    asyncio.run(main())
