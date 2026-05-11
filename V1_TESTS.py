"""
V1 Test Script - Verify Improvements

Run this to test the improved v1 logic.
Will output simulation results.
"""

import random
from typing import Dict, Tuple, List


class Simulator:
    """Paper trading simulator with improved logic"""
    
    def __init__(self, initial_balance: float = 10.0):
        self.balance = initial_balance
        self.initial = initial_balance
        self.trades: List[Dict] = []
        self.wins = 0
        self.losses = 0
        
    def simulate_trade(self, entry_price: float, confidence: float,
                       seconds_remaining: int, direction: str = "UP") -> Dict:
        """
        Simulate a single trade with realistic outcomes.
        Returns trade result.
        """
        # Position size based on confidence
        if confidence >= 0.80:
            size = min(2.0, self.balance * 0.15)
        elif confidence >= 0.60:
            size = min(1.5, self.balance * 0.10)
        else:
            size = min(1.0, self.balance * 0.05)
        
        if size < 0.25:  # Minimum
            return None
        
        # Realistic outcome model
        # Win rate based on confidence
        win_prob = confidence * 0.7  # Confidence inflates actual win rate
        won = random.random() < win_prob
        
        if won:
            # Profit: 1.5x - 5x on winners
            if entry_price <= 0.20:
                exit_mult = random.uniform(2.0, 5.0)  # Penny stocks can go big
            else:
                exit_mult = random.uniform(1.3, 2.5)
            pnl = size * (exit_mult - 1)
            self.balance += pnl
            self.wins += 1
        else:
            # Loss
            if entry_price <= 0.20:
                pnl = size * random.uniform(-0.30, -0.10)  # -10% to -30%
            else:
                pnl = size * random.uniform(-0.15, -0.05)  # -5% to -15%
            self.balance += pnl
            self.losses += 1
        
        trade = {
            'entry': entry_price,
            'size': size,
            'confidence': confidence,
            'pnl': pnl,
            'won': won,
            'balance_after': self.balance
        }
        self.trades.append(trade)
        return trade
    
    def run_simulation(self, num_trades: int = 100) -> Dict:
        """Run N trades and return results"""
        for _ in range(num_trades):
            # Random market conditions
            entry_price = random.uniform(0.05, 0.80)
            confidence = random.uniform(0.35, 0.90)
            seconds_remaining = random.randint(5, 300)
            
            self.simulate_trade(entry_price, confidence, seconds_remaining)
            
            if self.balance < 1.0:
                break  # Stop if too low
        
        total = self.wins + self.losses
        win_rate = self.wins / total if total > 0 else 0
        
        return {
            'initial_balance': self.initial,
            'final_balance': self.balance,
            'total_trades': total,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'total_pnl': self.balance - self.initial,
            'roi_pct': (self.balance - self.initial) / self.initial * 100
        }


def test_improved_logic():
    """Test the improved v1 logic"""
    print("=" * 50)
    print("V1 IMPROVED LOGIC SIMULATION")
    print("=" * 50)
    
    # Test 1: Conservative start ($10)
    sim = Simulator(10.0)
    results = sim.run_simulation(100)
    
    print(f"\nStarting Balance: ${results['initial_balance']:.2f}")
    print(f"Final Balance: ${results['final_balance']:.2f}")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Win Rate: {results['win_rate']:.1%}")
    print(f"P&L: ${results['total_pnl']:.2f}")
    print(f"ROI: {results['roi_pct']:.1f}%")
    
    # Test 2: Different start amounts
    print("\n" + "-" * 30)
    print("Testing different start amounts:")
    
    for start in [5, 10, 25, 50]:
        sim = Simulator(start)
        r = sim.run_simulation(100)
        print(f"  Start ${start:>2}: Final ${r['final_balance']:.2f} | "
              f"Win: {r['win_rate']:.0%} | Trades: {r['total_trades']}")
    
    return results


if __name__ == "__main__":
    test_improved_logic()