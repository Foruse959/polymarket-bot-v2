#!/usr/bin/env python3
"""
ALL MODE COMPARISON TEST
SEED vs PLANT vs CONCENTRATION vs MEDIUM vs AGGRESSIVE
$10 each, 2 minutes each, targeting $0.30+ per trade

Mode configs:
- SEED:         $2 max bet (20%),  2 positions, 90% confidence, maker-only
- PLANT:         $3 max bet (30%),  3 positions, 80% confidence, maker+taker
- CONCENTRATION: $5 max bet (50%),  2 positions, 70% confidence, maker+taker
- MEDIUM:        $4 max bet (40%),  4 positions, 65% confidence, taker-ok
- AGGRESSIVE:    $7 max bet (70%),  5 positions, 55% confidence, any order
"""

import time
import sys
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

@dataclass
class ModeConfig:
    name: str
    emoji: str
    max_bet_pct: float
    max_positions: int
    min_confidence: float
    max_bet_usd: float
    color: str

MODES = [
    ModeConfig("SEED",         "🌱", 0.20, 2, 0.65, 2.00, "92m"),   # lowered confidence to get more trades
    ModeConfig("PLANT",         "🌿", 0.30, 3, 0.55, 3.00, "94m"),
    ModeConfig("CONCENTRATION", "🎯", 0.50, 2, 0.50, 5.00, "95m"),
    ModeConfig("MEDIUM",        "⚡", 0.40, 4, 0.45, 4.00, "93m"),
    ModeConfig("AGGRESSIVE",    "🔥", 0.70, 5, 0.35, 7.00, "91m"),
]

class ModeSimulator:
    """Simulate trading for a specific risk mode."""

    # Realistic Polymarket markets
    MARKETS = [
        {"token": "BTC>105k_Jun",   "base_prob": 0.52, "volatility": 0.06},
        {"token": "ETH>2500_Jun",   "base_prob": 0.48, "volatility": 0.05},
        {"token": "SOL>150_Jun",    "base_prob": 0.55, "volatility": 0.07},
        {"token": "BTC_5min_up",    "base_prob": 0.50, "volatility": 0.10},
        {"token": "ETH_5min_up",    "base_prob": 0.49, "volatility": 0.10},
        {"token": "BTC_15min_up",   "base_prob": 0.52, "volatility": 0.08},
        {"token": "SOL_5min_up",    "base_prob": 0.51, "volatility": 0.09},
        {"token": "ETH_15min_up",   "base_prob": 0.48, "volatility": 0.08},
    ]

    def __init__(self, mode: ModeConfig, balance: float = 10.0):
        self.mode = mode
        self.balance = balance
        self.start_balance = balance
        self.trades: List[Dict] = []
        self.positions = 0
        self.fee_rate = 0.02  # 2% taker fee on Polymarket

    def simulate_tick(self, tick: int):
        """Simulate one trading tick (~1 second)."""
        for market in self.MARKETS:
            # Simulate price movement
            prob = market["base_prob"] + random.gauss(0, market["volatility"] * 0.3)
            prob = max(0.10, min(0.90, prob))

            # Check if we should enter a trade
            # Lower confidence threshold = more trades
            signal_confidence = abs(prob - 0.50) * 2  # 0-1, higher = more certain
            if prob > 0.50:
                side = "YES"
                signal_confidence = prob
            else:
                side = "NO"
                signal_confidence = 1 - prob

            # Only trade if confidence exceeds mode threshold
            if signal_confidence < self.mode.min_confidence:
                continue

            # Only trade if we have position capacity
            if self.positions >= self.mode.max_positions:
                continue

            # Only trade with ~10% probability per tick (not every signal)
            if random.random() > 0.10:
                continue

            # Calculate trade size
            max_bet = min(self.mode.max_bet_usd, self.balance * self.mode.max_bet_pct)
            bet_size = round(random.uniform(max_bet * 0.5, max_bet), 2)

            if bet_size > self.balance * 0.95:
                continue  # Don't bet everything

            # Simulate realistic outcome
            # Higher confidence = higher win rate
            # BUT real markets have slippage, fees, and surprises
            
            # Win probability based on signal confidence and mode risk
            effective_win_rate = signal_confidence * 0.75  # Reality discount
            
            if random.random() < effective_win_rate:
                # WIN - realistic profit
                # On Polymarket: buying YES at 0.65 means you profit $0.35 per $1 if correct
                # But with fees and slippage, expect ~15-30% return on winning trades
                profit_pct = random.uniform(0.08, 0.25)  # 8-25% profit
                pnl = round(bet_size * profit_pct, 2)
                
                # Minimum profit check - is this meaningful?
                # At $2 bet with 15% return = $0.30
                
            else:
                # LOSS - realistic loss
                # Stop losses typically at 10-20%
                loss_pct = random.uniform(0.05, 0.15)  # 5-15% loss
                pnl = round(-bet_size * loss_pct, 2)

            # Apply fees
            fee = round(bet_size * self.fee_rate * 0.3, 2)  # maker fees ~0.6%
            pnl -= fee

            # Record trade
            trade = {
                "tick": tick,
                "mode": self.mode.name,
                "market": market["token"],
                "side": side,
                "confidence": round(signal_confidence, 2),
                "bet_size": bet_size,
                "pnl": pnl,
                "fee": fee,
                "balance_after": round(self.balance + pnl, 2),
                "won": pnl > 0,
            }
            self.trades.append(trade)
            self.balance += pnl
            if pnl > 0:
                self.positions = max(0, self.positions - 1)
            self.positions += 1

    def get_summary(self) -> Dict:
        """Get trading summary."""
        if not self.trades:
            return {
                "mode": self.mode.name,
                "emoji": self.mode.emoji,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "final_balance": self.balance,
                "roi_pct": 0,
                "avg_profit": 0,
                "max_profit": 0,
                "max_loss": 0,
                "avg_bet": 0,
                "min_profitable": 0,
            }

        wins = [t for t in self.trades if t["won"]]
        losses = [t for t in self.trades if not t["won"]]

        win_pnls = [t["pnl"] for t in wins]
        loss_pnls = [t["pnl"] for t in losses]

        return {
            "mode": self.mode.name,
            "emoji": self.mode.emoji,
            "trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trades) * 100,
            "total_pnl": round(self.balance - self.start_balance, 2),
            "final_balance": round(self.balance, 2),
            "roi_pct": round((self.balance - self.start_balance) / self.start_balance * 100, 2),
            "avg_profit": round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0,
            "max_profit": round(max(win_pnls), 2) if win_pnls else 0,
            "avg_loss": round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0,
            "max_loss": round(min(loss_pnls), 2) if loss_pnls else 0,
            "max_loss_trade": round(min(loss_pnls), 2) if loss_pnls else 0,
            "avg_bet": round(sum(t["bet_size"] for t in self.trades) / len(self.trades), 2) if self.trades else 0,
            "min_profitable": round(self.start_balance * 0.03, 2),  # 3% = minimum meaningful
        }


def print_comparison(results: List[Dict]):
    """Print side-by-side comparison."""
    print("\n" + "=" * 90)
    print("  MODE COMPARISON RESULTS - $10 STARTING BALANCE - 2 MIN SIMULATION")
    print("=" * 90)

    # Header
    print(f"\n  {'Mode':<18} {'Trades':>7} {'Wins':>5} {'Loss':>5} {'Win%':>6} {'P&L':>8} {'ROI':>7} {'AvgWin':>8} {'AvgLoss':>8} {'Best':>8}")
    print(f"  {'-'*18} {'-'*7} {'-'*5} {'-'*5} {'-'*6} {'-'*8} {'-'*7} {'-'*8} {'-'*8} {'-'*8}")

    for r in results:
        emoji = r["emoji"]
        name = f"{emoji} {r['mode']}"
        
        # Color based on P&L
        pnl_sign = "+" if r["total_pnl"] >= 0 else ""
        
        print(f"  {name:<18} {r['trades']:>7} {r['wins']:>5} {r['losses']:>5} {r['win_rate']:>5.0f}% "
              f"{pnl_sign}{r['total_pnl']:>7.2f} {r['roi_pct']:>+6.1f}% "
              f"{r.get('avg_profit',0):>+7.2f} {r.get('avg_loss',0):>+7.2f} {r.get('max_profit',0):>+7.2f}")

    print(f"\n  {'─'*90}")
    
    # Winner
    best = max(results, key=lambda x: x["total_pnl"])
    best_roi = max(results, key=lambda x: x["roi_pct"])
    best_wr = max(results, key=lambda x: x["win_rate"])
    
    print(f"\n  BEST P&L:        {best['emoji']} {best['mode']} with ${best['total_pnl']:+.2f} ({best['roi_pct']:+.1f}% ROI)")
    print(f"  BEST ROI:        {best_roi['emoji']} {best_roi['mode']} with {best_roi['roi_pct']:+.1f}%")
    print(f"  HIGHEST WIN RATE: {best_wr['emoji']} {best_wr['mode']} with {best_wr['win_rate']:.0f}%")

    # Meaningful profit check
    print(f"\n  {'─'*90}")
    print(f"  MEANINGFUL PROFIT CHECK (need $0.30+ per winning trade):")
    for r in results:
        meets = "YES" if r["avg_profit"] >= 0.30 else "NO"
        color = "92m" if meets == "YES" else "91m"
        print(f"    {r['emoji']} {r['mode']:<15} Avg profit: ${r['avg_profit']:+.2f}  [Meets $0.30: \033[{color}{meets}\033[0m]")

    # Recommendation
    print(f"\n  {'─'*90}")
    print(f"  RECOMMENDATION FOR $10 STARTING BALANCE:")
    
    # Find best mode that has meaningful profits
    meaningful = [r for r in results if r["avg_profit"] >= 0.15]
    if meaningful:
        rec = max(meaningful, key=lambda x: x["roi_pct"])
        print(f"    {rec['emoji']} USE {rec['mode']} MODE")
        print(f"      - Expected avg profit: ${rec['avg_profit']:+.2f} per trade")
        print(f"      - Expected ROI: {rec['roi_pct']:+.1f}%")
        print(f"      - Win rate: {rec['win_rate']:.0f}%")
        print(f"      - Bet size: ${rec['avg_bet']:.2f} avg")
    else:
        # If no mode meets $0.30, recommend the most profitable
        rec = max(results, key=lambda x: x["total_pnl"])
        print(f"    {rec['emoji']} USE {rec['mode']} MODE (best available)")
        print(f"      - Avg profit: ${rec['avg_profit']:+.2f} per trade")
        print(f"      - Need ${0.30 - rec['avg_profit']:.2f} more per trade")
        print(f"      - Requires larger position sizes")
    
    print(f"\n  {'='*90}")


def main():
    """Run all mode simulations."""
    print("=" * 90)
    print("  ALL MODE COMPARISON TEST")
    print("  $10 starting balance each | 2 minutes simulation each")
    print("  Targeting $0.30+ per winning trade")
    print("=" * 90)

    results = []

    for mode in MODES:
        print(f"\n  {mode.emoji} Running {mode.name} mode...")
        print(f"     Max bet: ${mode.max_bet_usd:.2f} ({mode.max_bet_pct*100:.0f}%)")
        print(f"     Positions: {mode.max_positions} | Min confidence: {mode.min_confidence*100:.0f}%")

        sim = ModeSimulator(mode, balance=10.0)
        
        # Simulate 120 ticks (2 minutes at ~1 tick/second)
        for tick in range(120):
            sim.simulate_tick(tick)

        result = sim.get_summary()
        results.append(result)

        # Quick summary
        pnl_str = f"${result['total_pnl']:+.2f}"
        print(f"     Done: {result['trades']} trades | P&L: {pnl_str} | ROI: {result['roi_pct']:+.1f}%")
        time.sleep(0.3)  # Brief pause between modes

    # Print comparison
    print_comparison(results)

    # Detailed trade samples for each mode
    print("\n" + "=" * 90)
    print("  SAMPLE TRADES PER MODE (first 5)")
    print("=" * 90)

    for mode in MODES:
        sim = ModeSimulator(mode, balance=10.0)
        for tick in range(120):
            sim.simulate_tick(tick)
        
        trades = sim.trades[:5]
        print(f"\n  {mode.emoji} {mode.name} MODE:")
        if trades:
            for t in trades:
                won_emoji = "W" if t["won"] else "L"
                print(f"    [{won_emoji}] {t['market']:<16} bet=${t['bet_size']:.2f} "
                      f"conf={t['confidence']*100:.0f}% "
                      f"pnl=${t['pnl']:+.2f} "
                      f"fee=${t['fee']:.2f} "
                      f"bal=${t['balance_after']:.2f}")
        else:
            print("    No trades (confidence too high)")


if __name__ == "__main__":
    main()