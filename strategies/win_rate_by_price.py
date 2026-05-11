#!/usr/bin/env python3
"""
Win Rate by Price Analysis

Analyzes which entry prices have the best win rates.
Based on prediction-market-analysis research.
"""

import json
import os
from typing import Dict, List, Tuple
from dataclasses import dataclass

@dataclass
class PriceBucket:
    """Track performance for a price range."""
    min_price: float
    max_price: float
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    
    @property
    def total_trades(self) -> int:
        return self.wins + self.losses
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades
    
    @property
    def avg_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

class WinRateByPrice:
    """Analyze win rates across different price buckets."""
    
    # Price buckets based on research
    BUCKETS = [
        (0.01, 0.10),  # Penny stocks (high risk/high reward)
        (0.10, 0.20),  # Cheap
        (0.20, 0.30),  # Low
        (0.30, 0.40),  # Medium-low
        (0.40, 0.50),  # Near fair
        (0.50, 0.60),  # Near fair
        (0.60, 0.70),  # Medium-high
        (0.70, 0.80),  # High
        (0.80, 0.90),  # Expensive
        (0.90, 0.99),  # Very expensive
    ]
    
    def __init__(self, data_file: str = None):
        self.buckets = {i: PriceBucket(low, high) for i, (low, high) in enumerate(self.BUCKETS)}
        self.data_file = data_file or os.path.join(os.path.dirname(__file__), '..', 'data', 'price_analysis.json')
        self.load()
    
    def get_bucket(self, price: float) -> int:
        """Get bucket index for a price."""
        for i, (low, high) in enumerate(self.BUCKETS):
            if low <= price < high:
                return i
        return len(self.BUCKETS) - 1  # Last bucket
    
    def record_trade(self, entry_price: float, won: bool, pnl: float):
        """Record a trade result."""
        bucket_idx = self.get_bucket(entry_price)
        bucket = self.buckets[bucket_idx]
        
        if won:
            bucket.wins += 1
        else:
            bucket.losses += 1
        bucket.total_pnl += pnl
        
        self.save()
    
    def get_best_price_range(self, min_trades: int = 10) -> Tuple[float, float]:
        """Get the price range with highest win rate."""
        best_bucket = None
        best_rate = 0.0
        
        for bucket in self.buckets.values():
            if bucket.total_trades >= min_trades and bucket.win_rate > best_rate:
                best_rate = bucket.win_rate
                best_bucket = bucket
        
        if best_bucket:
            return (best_bucket.min_price, best_bucket.max_price)
        return (0.0, 1.0)  # Default: all prices
    
    def should_trade_at_price(self, price: float, min_win_rate: float = 0.55) -> bool:
        """Check if we should trade at this price based on historical data."""
        bucket_idx = self.get_bucket(price)
        bucket = self.buckets[bucket_idx]
        
        if bucket.total_trades < 5:  # Not enough data
            return True  # Default to yes
        
        return bucket.win_rate >= min_win_rate
    
    def get_price_confidence(self, price: float) -> float:
        """Get confidence score (0-1) for trading at this price."""
        bucket_idx = self.get_bucket(price)
        bucket = self.buckets[bucket_idx]
        
        if bucket.total_trades < 5:
            return 0.5  # Neutral
        
        return bucket.win_rate
    
    def print_analysis(self):
        """Print price analysis table."""
        print("\n" + "="*60)
        print("📊 WIN RATE BY PRICE ANALYSIS")
        print("="*60)
        print(f"{'Price Range':<15} {'Trades':<8} {'Win Rate':<10} {'Avg P&L':<12}")
        print("-"*60)
        
        for bucket in self.buckets.values():
            if bucket.total_trades > 0:
                range_str = f"${bucket.min_price:.2f}-${bucket.max_price:.2f}"
                win_rate_str = f"{bucket.win_rate*100:.1f}%"
                avg_pnl_str = f"${bucket.avg_pnl:+.2f}"
                print(f"{range_str:<15} {bucket.total_trades:<8} {win_rate_str:<10} {avg_pnl_str:<12}")
        
        best = self.get_best_price_range()
        print("-"*60)
        print(f"✅ BEST PRICE RANGE: ${best[0]:.2f} - ${best[1]:.2f}")
        print("="*60 + "\n")
    
    def save(self):
        """Save analysis to file."""
        data = {
            'buckets': [
                {
                    'min': b.min_price,
                    'max': b.max_price,
                    'wins': b.wins,
                    'losses': b.losses,
                    'total_pnl': b.total_pnl,
                }
                for b in self.buckets.values()
            ]
        }
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass
    
    def load(self):
        """Load analysis from file."""
        if not os.path.exists(self.data_file):
            return
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            for i, b_data in enumerate(data.get('buckets', [])):
                if i in self.buckets:
                    self.buckets[i].wins = b_data.get('wins', 0)
                    self.buckets[i].losses = b_data.get('losses', 0)
                    self.buckets[i].total_pnl = b_data.get('total_pnl', 0.0)
        except:
            pass

# Global instance
_price_analyzer = None

def get_analyzer() -> WinRateByPrice:
    """Get singleton analyzer instance."""
    global _price_analyzer
    if _price_analyzer is None:
        _price_analyzer = WinRateByPrice()
    return _price_analyzer

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # Test
    analyzer = WinRateByPrice()
    
    # Simulate some trades
    analyzer.record_trade(0.45, True, 0.5)
    analyzer.record_trade(0.48, True, 0.45)
    analyzer.record_trade(0.52, False, -0.25)
    analyzer.record_trade(0.15, True, 0.8)
    analyzer.record_trade(0.85, True, 0.15)
    
    analyzer.print_analysis()