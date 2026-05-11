"""
Backtest Runner — Simple backtester for maker strategies

Uses research insights from:
- Becker's maker advantage analysis (+1.12% vs -1.12%)
- SII-WANGZJ data on longshot bias

This is a simplified backtester. For full historical analysis,
integrate with quant.parquet data (170M+ records).
"""

import json
import random
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestTrade:
    entry_price: float
    exit_price: float
    size_usdc: float
    direction: str
    order_type: str
    pnl_usdc: float
    timestamp: str


class SimpleBacktester:
    """
    Simplified backtester for maker strategy validation.
    
    Simulates the core thesis:
    1. Maker orders get filled at better prices (spread capture)
    2. Longshot bias creates exploitable edges
    3. Category efficiency affects spread width
    """

    def __init__(self, initial_balance_usdc: float = 100.0):
        self.initial_balance_usdc = initial_balance_usdc
        self.balance_usdc = initial_balance_usdc
        self.trades: List[BacktestTrade] = []
        
        # Parameters from research
        self.maker_edge_bps = 112  # 1.12% maker advantage
        self.taker_penalty_bps = 112  # 1.12% taker disadvantage
        self.longshot_threshold = 0.20
        self.favorite_threshold = 0.80
        
        # Category multipliers
        self.category_mult = {
            'finance': 1.0,
            'politics': 1.25,
            'sports': 1.75,
            'entertainment': 2.0,
            'crypto': 1.5,
            'other': 1.5,
        }

    def simulate_trade(self, entry_price: float, exit_price: float,
                      size_usdc: float, direction: str, order_type: str,
                      category: str = 'other') -> BacktestTrade:
        """
        Simulate a single trade with maker/taker dynamics.
        
        Args:
            entry_price: Mid price at entry
            exit_price: Mid price at exit
            size_usdc: Position size
            direction: 'UP', 'DOWN', 'SELL_UP'
            order_type: 'maker' or 'taker'
            category: Market category for spread adjustment
        """
        cat_mult = self.category_mult.get(category, 1.5)
        
        # Calculate effective prices with spread
        if order_type == 'maker':
            # Maker: better fill (inside spread)
            spread_bps = 50 * cat_mult  # Base 50 bps * category multiplier
            price_improvement = spread_bps / 10000 * entry_price
            
            if direction in ['UP', 'DOWN']:
                # Buying: fill below mid
                effective_entry = entry_price - price_improvement
            else:
                # Selling: fill above mid
                effective_entry = entry_price + price_improvement
                
            fee_rate = 0.0  # Maker pays no fees
        else:
            # Taker: worse fill (cross spread)
            spread_bps = 100 * cat_mult
            price_penalty = spread_bps / 10000 * entry_price
            
            if direction in ['UP', 'DOWN']:
                effective_entry = entry_price + price_penalty
            else:
                effective_entry = entry_price - price_penalty
                
            # Taker fee (dynamic based on price)
            fee_rate = 0.25 * entry_price * (1 - entry_price) ** 2

        # Calculate P&L
        if direction == 'UP':
            pnl = (exit_price - effective_entry) * size_usdc / effective_entry
        elif direction == 'DOWN':
            pnl = (effective_entry - exit_price) * size_usdc / effective_entry
        elif direction == 'SELL_UP':
            pnl = (effective_entry - exit_price) * size_usdc / effective_entry
        else:
            pnl = 0

        # Apply fees
        fee_usdc = size_usdc * fee_rate
        pnl -= fee_usdc

        trade = BacktestTrade(
            entry_price=effective_entry,
            exit_price=exit_price,
            size_usdc=size_usdc,
            direction=direction,
            order_type=order_type,
            pnl_usdc=pnl,
            timestamp=datetime.now().isoformat(),
        )

        self.trades.append(trade)
        self.balance_usdc += pnl

        return trade

    def run_scenario(self, scenario_name: str, num_trades: int = 100):
        """Run a backtest scenario."""
        print(f"\n{'='*60}")
        print(f"Backtest: {scenario_name}")
        print(f"{'='*60}\n")

        scenarios = {
            'maker_vs_taker': self._run_maker_vs_taker,
            'longshot_bias': self._run_longshot_bias,
            'category_efficiency': self._run_category_efficiency,
        }

        if scenario_name in scenarios:
            scenarios[scenario_name](num_trades)
        else:
            print(f"Unknown scenario: {scenario_name}")
            print(f"Available: {list(scenarios.keys())}")

    def _run_maker_vs_taker(self, num_trades: int):
        """Compare maker vs taker performance."""
        # Reset
        self.trades = []
        self.balance_usdc = self.initial_balance_usdc

        print("Testing: Maker vs Taker (same market conditions)\n")

        # Simulate 50 maker trades, 50 taker trades
        for i in range(num_trades // 2):
            price = random.uniform(0.3, 0.7)
            exit = price + random.uniform(-0.1, 0.1)
            size = random.uniform(5, 20)
            direction = random.choice(['UP', 'DOWN'])

            self.simulate_trade(price, exit, size, direction, 'maker')

        maker_pnl = sum(t.pnl_usdc for t in self.trades)
        maker_win_rate = sum(1 for t in self.trades if t.pnl_usdc > 0) / len(self.trades)

        # Reset for taker
        self.trades = []
        self.balance_usdc = self.initial_balance_usdc

        for i in range(num_trades // 2):
            price = random.uniform(0.3, 0.7)
            exit = price + random.uniform(-0.1, 0.1)
            size = random.uniform(5, 20)
            direction = random.choice(['UP', 'DOWN'])

            self.simulate_trade(price, exit, size, direction, 'taker')

        taker_pnl = sum(t.pnl_usdc for t in self.trades)
        taker_win_rate = sum(1 for t in self.trades if t.pnl_usdc > 0) / len(self.trades)

        print(f"Results ({num_trades} trades each):")
        print(f"  Maker P&L: {maker_pnl:+.2f} USDC (win rate: {maker_win_rate:.1%})")
        print(f"  Taker P&L: {taker_pnl:+.2f} USDC (win rate: {taker_win_rate:.1%})")
        print(f"  Advantage: {maker_pnl - taker_pnl:+.2f} USDC")
        print(f"\nMaker advantage: {(maker_pnl - taker_pnl) / num_trades * 2:.2f} USDC/trade")

    def _run_longshot_bias(self, num_trades: int):
        """Test longshot bias exploitation."""
        self.trades = []
        self.balance_usdc = self.initial_balance_usdc

        print("Testing: Longshot Bias Exploitation\n")
        print("Strategy: Sell YES < 20¢, Buy NO > 80¢\n")

        for i in range(num_trades):
            # Longshot scenario: YES at 15¢, actually worth 10¢
            if i % 2 == 0:
                entry = 0.15  # Retail overpays
                exit = 0.10   # True value
                direction = 'SELL_UP'  # Sell the overpriced YES
                size = 10
                self.simulate_trade(entry, exit, size, direction, 'maker', 'sports')
            else:
                # Favorite scenario: NO at 85¢, actually worth 90¢
                entry = 0.85  # Retail undervalues
                exit = 0.90   # True value
                direction = 'DOWN'  # Buy the underpriced NO
                size = 10
                self.simulate_trade(entry, exit, size, direction, 'maker', 'sports')

        total_pnl = sum(t.pnl_usdc for t in self.trades)
        win_rate = sum(1 for t in self.trades if t.pnl_usdc > 0) / len(self.trades)

        print(f"Results ({num_trades} trades):")
        print(f"  Total P&L: {total_pnl:+.2f} USDC")
        print(f"  Win Rate: {win_rate:.1%}")
        print(f"  Avg per trade: {total_pnl / num_trades:.2f} USDC")

    def _run_category_efficiency(self, num_trades: int):
        """Test category-based spread management."""
        print("Testing: Category Efficiency Impact\n")

        categories = ['finance', 'politics', 'sports', 'entertainment']
        results = {}

        for category in categories:
            self.trades = []
            self.balance_usdc = self.initial_balance_usdc

            for i in range(num_trades // len(categories)):
                price = random.uniform(0.4, 0.6)
                exit = price + random.uniform(-0.05, 0.05)
                size = 10
                direction = random.choice(['UP', 'DOWN'])

                self.simulate_trade(price, exit, size, direction, 'maker', category)

            pnl = sum(t.pnl_usdc for t in self.trades)
            results[category] = pnl

        print(f"Results (per category, {num_trades // len(categories)} trades each):")
        for cat, pnl in sorted(results.items(), key=lambda x: x[1], reverse=True):
            mult = self.category_mult[cat]
            print(f"  {cat:15} (mult: {mult:.1f}x): {pnl:+.2f} USDC")

    def generate_report(self) -> Dict:
        """Generate backtest report."""
        if not self.trades:
            return {}

        wins = [t for t in self.trades if t.pnl_usdc > 0]
        losses = [t for t in self.trades if t.pnl_usdc <= 0]

        return {
            'initial_balance_usdc': self.initial_balance_usdc,
            'final_balance_usdc': self.balance_usdc,
            'total_pnl_usdc': self.balance_usdc - self.initial_balance_usdc,
            'total_trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) if self.trades else 0,
            'avg_win_usdc': sum(t.pnl_usdc for t in wins) / len(wins) if wins else 0,
            'avg_loss_usdc': sum(t.pnl_usdc for t in losses) / len(losses) if losses else 0,
            'maker_trades': sum(1 for t in self.trades if t.order_type == 'maker'),
            'taker_trades': sum(1 for t in self.trades if t.order_type == 'taker'),
        }


def main():
    """Run backtest scenarios."""
    bt = SimpleBacktester(initial_balance_usdc=100.0)

    # Run scenarios
    bt.run_scenario('maker_vs_taker', num_trades=100)
    bt.run_scenario('longshot_bias', num_trades=100)
    bt.run_scenario('category_efficiency', num_trades=100)

    print(f"\n{'='*60}")
    print("Backtest Complete")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
