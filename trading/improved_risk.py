"""
Improved Risk Manager - Conservative for Small Balance

Key fixes:
1. Position sizing based on actual balance
2. Dynamic stop-loss based on entry price tier
3. Conservative for balance < $20
4. Proper exit pricing
"""

import time
from typing import Dict, Tuple


class ImprovedRiskManager:
    """Conservative risk management for small balances"""
    
    def __init__(self, balance: float = 10.0):
        self.balance = balance
        self.initial_balance = balance
        self.open_positions = 0
        self.max_positions = 3  # Conservative
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.wins = 0
        self.losses = 0
        self.min_balance = 5.0  # Stop trading if below
        
    def can_trade(self) -> Tuple[bool, str]:
        if self.balance < self.min_balance:
            return False, f"MIN BALANCE: ${self.balance:.2f} < ${self.min_balance}"
        if self.open_positions >= self.max_positions:
            return False, f"MAX POS: {self.open_positions}/{self.max_positions}"
        return True, f"BALANCE: ${self.balance:.2f}"
    
    def calculate_position_size(self, confidence: float) -> float:
        """Position size - conservative for small balance"""
        if self.balance < 10:
            # Very small: $0.50 - $1 per trade
            base = 0.50
            max_size = 1.0
        elif self.balance < 25:
            # Small: $1 - $2
            base = 1.0
            max_size = 2.0
        elif self.balance < 50:
            # Medium: $2 - $4
            base = 2.0
            max_size = 4.0
        else:
            # Growing: 5-10% of balance
            base = self.balance * 0.05
            max_size = self.balance * 0.10
        
        # Scale by confidence (0.4-0.95)
        conf_factor = (confidence - 0.35) / 0.60  # Normalize
        conf_factor = max(0.5, min(1.5, conf_factor))
        
        size = base * conf_factor
        return min(size, max_size)
    
    def should_exit(self, entry_price: float, current_price: float,
                   seconds_remaining: int) -> Tuple[str, float]:
        """
        Dynamic exit decision.
        Returns: (action, exit_price)
        
        Actions: 'hold', 'sell_profit', 'cut_loss'
        """
        if entry_price <= 0:
            return 'hold', current_price
        
        gain = current_price / entry_price
        pnl_pct = (current_price - entry_price) / entry_price * 100
        
        # Tiered exit based on entry price
        if entry_price <= 0.10:
            # Penny stock: allow -30% (lottery math)
            stop_pct = -30
            target_mult = 3.0
        elif entry_price <= 0.30:
            # Cheap: allow -20%
            stop_pct = -20
            target_mult = 2.5
        elif entry_price <= 0.50:
            # Medium: allow -15%
            stop_pct = -15
            target_mult = 2.0
        else:
            # Expensive: tight -10%
            stop_pct = -10
            target_mult = 1.5
        
        # Adjust for time remaining
        if seconds_remaining < 30:
            # Near expiry: let it settle (no stop)
            if gain >= target_mult:
                return 'sell_profit', current_price
            return 'hold', current_price
        elif seconds_remaining < 60:
            # Last minute: wider stop
            stop_pct *= 1.5
        
        # Check exits
        if gain >= target_mult:
            return 'sell_profit', current_price
        if pnl_pct <= stop_pct:
            return 'cut_loss', current_price
        
        return 'hold', current_price
    
    def get_aggressive_sell_price(self, current_bid: float) -> float:
        """Sell at cross-spread - 1-2 cents below bid for fills"""
        if current_bid <= 0.05:
            return max(0.01, current_bid - 0.01)
        return current_bid * 0.98  # 2% below bid
    
    def record_trade(self, pnl: float, won: bool):
        """Record trade result"""
        self.total_pnl += pnl
        self.daily_pnl += pnl
        self.balance += pnl
        self.open_positions = max(0, self.open_positions - 1)
        
        if won:
            self.wins += 1
        else:
            self.losses += 1
    
    def get_stats(self) -> Dict:
        total = self.wins + self.losses
        wr = self.wins / total if total > 0 else 0
        return {
            'balance': self.balance,
            'open_positions': self.open_positions,
            'total_pnl': self.total_pnl,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': wr,
            'can_trade': self.can_trade()[0]
        }