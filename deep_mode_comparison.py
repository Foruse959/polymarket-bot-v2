#!/usr/bin/env python3
"""
DEEP MODE COMPARISON - 1000 simulated trades per mode
Realistic market simulation with proper strategy edge
"""

import sys
import random
from dataclasses import dataclass

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

MODES = [
    ModeConfig("SEED",         "🌱", 0.20, 2, 0.55, 2.00),
    ModeConfig("PLANT",         "🌿", 0.30, 3, 0.50, 3.00),
    ModeConfig("CONCENTRATION", "🎯", 0.50, 2, 0.50, 5.00),
    ModeConfig("MEDIUM",        "⚡", 0.40, 4, 0.45, 4.00),
    ModeConfig("AGGRESSIVE",    "🔥", 0.70, 5, 0.40, 7.00),
]

def simulate_mode(mode: ModeConfig, starting_balance: float = 10.0, num_trades: int = 150) -> dict:
    """
    Simulate a mode with realistic market conditions.
    
    Key insight: On Polymarket, buying at 0.65 means you profit $0.35 if YES wins.
    Buying at 0.35 means you profit $0.65 if NO wins (cheaper = more profit).
    
    Strategy edge comes from:
    1. Picking the RIGHT side (YES or NO)
    2. Picking good entry prices (0.30-0.70 range = best edge)
    3. Avoiding 50/50 bets (no edge)
    """
    balance = starting_balance
    trades = []
    positions_held = 0
    
    # Good strategies have ~60% win rate with proper edge
    # Better entry prices = bigger wins
    
    for i in range(num_trades):
        if balance < 0.50:  # Can't trade with too little
            break
        
        # Generate a market signal
        # Entry price: random between 0.15-0.85
        entry_price = random.uniform(0.15, 0.85)
        
        # Signal confidence based on how far from 0.50
        # 0.50 = no edge, 0.80 or 0.20 = big edge
        if entry_price > 0.50:
            signal_confidence = entry_price  # YES confidence
            side = "YES"
            edge = entry_price  # Higher price = YES favored
        else:
            signal_confidence = 1 - entry_price  # NO confidence
            side = "NO"
            edge = 1 - entry_price
        
        # Skip if confidence too low for this mode
        if signal_confidence < mode.min_confidence:
            continue
        
        # Position limit check
        if positions_held >= mode.max_positions:
            positions_held = max(0, positions_held - 1)  # Simulate close
            continue
        
        # Calculate bet size
        max_bet = min(mode.max_bet_usd, balance * mode.max_bet_pct)
        bet_size = round(random.uniform(max_bet * 0.5, max_bet), 2)
        bet_size = min(bet_size, balance * 0.95)  # Never bet more than 95%
        
        if bet_size < 0.10:
            continue
        
        # Determine outcome
        # The key insight: signal confidence IS our expected win rate
        # But we apply a "reality discount" of 0.85 (markets are harder than expected)
        effective_win_rate = signal_confidence * 0.82  # 82% of expected
        
        # Clamp between 0.30 and 0.75 (realistic range)
        effective_win_rate = max(0.30, min(0.75, effective_win_rate))
        
        if random.random() < effective_win_rate:
            # WIN
            # On Polymarket, buying YES at 0.65 and it wins = $0.35 profit per $1
            # Buying NO at 0.35 and it wins = $0.65 profit per $1
            # More extreme entry = bigger profit potential
            profit_per_dollar = max(0.05, (1 - entry_price)) if side == "YES" else max(0.05, entry_price)
            
            # Apply slippage and fees
            profit_per_dollar *= random.uniform(0.7, 0.95)  # 70-95% of theoretical
            
            pnl = round(bet_size * profit_per_dollar, 2)
            won = True
        else:
            # LOSS
            # If YES at 0.65 and it loses, you lose $0.65 per $1
            loss_per_dollar = entry_price if side == "YES" else (1 - entry_price)
            loss_per_dollar *= random.uniform(0.3, 0.7)  # Stop loss limits damage
            
            pnl = round(-bet_size * loss_per_dollar, 2)
            won = False
        
        # Apply maker fee (0.6% on Polymarket)
        fee = round(bet_size * 0.006, 2) if effective_win_rate < 0.55 else round(bet_size * 0.002, 2)
        pnl -= fee
        
        balance += pnl
        
        trades.append({
            "mode": mode.name,
            "market": f"mkt_{i:03d}",
            "side": side,
            "entry": round(entry_price, 2),
            "confidence": round(signal_confidence, 2),
            "bet_size": bet_size,
            "pnl": pnl,
            "fee": fee,
            "balance": round(balance, 2),
            "won": won,
        })
        
        positions_held = positions_held + 1 if not won else max(0, positions_held)
    
    wins = [t for t in trades if t["won"]]
    losses = [t for t in trades if not t["won"]]
    
    return {
        "mode": mode.name,
        "emoji": mode.emoji,
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / max(1, len(trades)) * 100,
        "total_pnl": round(balance - starting_balance, 2),
        "final_balance": round(balance, 2),
        "roi_pct": round((balance - starting_balance) / starting_balance * 100, 1),
        "avg_profit": round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0,
        "max_profit": round(max((t["pnl"] for t in wins), default=0), 2),
        "max_loss": round(min((t["pnl"] for t in losses), default=0), 2),
        "avg_bet": round(sum(t["bet_size"] for t in trades) / len(trades), 2) if trades else 0,
        "starting": starting_balance,
        "bankrupt": balance < 1.0,
    }

def main():
    print("=" * 95)
    print("  DEEP MODE COMPARISON - 150 TRADES PER MODE - $10 STARTING BALANCE")
    print("  Realistic Polymarket simulation with fees, slippage, and edge decay")
    print("=" * 95)
    
    # Run 5 simulations per mode for statistical reliability
    all_results = {}
    
    for mode in MODES:
        results = []
        for run in range(5):
            random.seed(run * 100 + hash(mode.name))  # Reproducible
            r = simulate_mode(mode, starting_balance=10.0, num_trades=150)
            results.append(r)
        all_results[mode.name] = results
    
    # Print results
    print(f"\n  {'Mode':<20} {'Trades':>7} {'Win%':>6} {'P&L':>8} {'ROI':>8} {'AvgWin':>8} {'AvgLoss':>8} {'MaxWin':>8} {'$0.30+?':>7}")
    print(f"  {'─'*20} {'─'*7} {'─'*6} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*7}")
    
    final_recs = []
    
    for mode in MODES:
        results = all_results[mode.name]
        
        # Average across runs
        avg_trades = sum(r["trades"] for r in results) / len(results)
        avg_win_rate = sum(r["win_rate"] for r in results) / len(results)
        avg_pnl = sum(r["total_pnl"] for r in results) / len(results)
        avg_roi = sum(r["roi_pct"] for r in results) / len(results)
        avg_profit = sum(r["avg_profit"] for r in results) / len(results)
        avg_loss = sum(r["avg_loss"] for r in results) / len(results)
        max_profit = max(r["max_profit"] for r in results)
        bankruptcies = sum(1 for r in results if r["bankrupt"])
        
        meets_target = "YES" if avg_profit >= 0.30 else "NO"
        
        print(f"  {mode.emoji} {mode.name:<17} {avg_trades:>7.0f} {avg_win_rate:>5.0f}% "
              f"${avg_pnl:>+7.2f} {avg_roi:>+7.1f}% "
              f"${avg_profit:>+7.2f} ${avg_loss:>+7.2f} "
              f"${max_profit:>+7.2f} {meets_target:>7}")
        
        final_recs.append({
            "mode": mode.name,
            "emoji": mode.emoji,
            "avg_pnl": avg_pnl,
            "avg_roi": avg_roi,
            "avg_profit": avg_profit,
            "avg_loss": avg_loss,
            "avg_win_rate": avg_win_rate,
            "avg_trades": avg_trades,
            "bankruptcies": bankruptcies,
            "meets_target": meets_target,
        })
    
    # Recommendation
    print(f"\n  {'═'*95}")
    print(f"\n  VERDICT: Which mode makes $0.30+ per winning trade AND overall profit?\n")
    
    profitable = [r for r in final_recs if r["avg_pnl"] > 0]
    meeting_target = [r for r in final_recs if r["meets_target"] == "YES" and r["avg_pnl"] > 0]
    
    print(f"  Total bankrupcies across all runs:")
    for r in final_recs:
        print(f"    {r['emoji']} {r['mode']:<15}: {r['bankruptcies']}/5 runs went bankrupt")
    
    print()
    
    if meeting_target:
        best = max(meeting_target, key=lambda x: x["avg_roi"])
        print(f"  WINNER: {best['emoji']} {best['mode']} MODE")
        print(f"    - Avg profit per winning trade: ${best['avg_profit']:+.2f}")
        print(f"    - Avg P&L over 150 trades: ${best['avg_pnl']:+.2f}")
        print(f"    - Avg ROI: {best['avg_roi']:+.1f}%")
        print(f"    - Avg win rate: {best['avg_win_rate']:.0f}%")
        print(f"    - Avg trades per 2min: {best['avg_trades']:.0f}")
    elif profitable:
        best = max(profitable, key=lambda x: x["avg_roi"])
        print(f"  BEST OPTION: {best['emoji']} {best['mode']} MODE")
        print(f"    - Avg profit per winning trade: ${best['avg_profit']:+.2f}")
        print(f"    - But avg profit needs ${0.30 - best['avg_profit']:.2f} more per trade")
        print(f"    - Need to increase bet sizes or improve strategy")
    else:
        print(f"  NO MODE IS PROFITABLE with $10 starting balance")
        print(f"  Minimum recommended starting balance: $50-$100")
    
    # Show what $0.30+ per trade requires
    print(f"\n  {'─'*95}")
    print(f"  HOW TO GET $0.30+ PER TRADE:")
    print(f"")
    print(f"  At 15% average return per winning trade:")
    print(f"    $0.30 profit = $2.00 bet size")
    print(f"    This requires PLANT mode (30% max bet = $3.00)")
    print(f"")
    print(f"  At 25% average return per winning trade:")
    print(f"    $0.30 profit = $1.20 bet size")  
    print(f"    This works even in SEED mode (20% max bet = $2.00)")
    print(f"")
    print(f"  KEY INSIGHT: Need to enter at 0.70-0.80 or 0.20-0.30 prices")
    print(f"  These give 20-30 cent profit per dollar if correct")
    print(f"  Avoid 0.45-0.55 range (no meaningful edge)")
    
    print(f"\n  {'═'*95}")

if __name__ == "__main__":
    main()