"""
Risk Manager — Dynamic Balance Tiers

Uses BalanceManager for tiered aggression:
  SURVIVAL ($0-15)  → tiny bets, safe strategies only
  GROWTH ($15-50)   → moderate bets, more strategies
  AGGRESSIVE ($50+) → bigger bets, keep $10 reserve
  FULL SEND ($100+) → maximum aggression, compound
"""

import time
from typing import Dict
from config import Config
from trading.balance_manager import DynamicBalanceManager


class RiskManager:
    """Balance-aware risk manager. Adapts aggression to balance tier."""

    def __init__(self, balance: float = None):
        self.balance = balance or Config.STARTING_BALANCE
        self.bm = DynamicBalanceManager(self.balance)
        self.daily_pnl = 0.0
        self.open_positions = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

    def can_trade(self) -> tuple:
        """Check tradeable status based on balance tier."""
        ok, reason = self.bm.should_trade()
        if not ok:
            return False, reason
        if self.open_positions >= self.bm.max_positions:
            return False, f"📊 {self.open_positions}/{self.bm.max_positions} positions open"
        return True, f"{self.bm.tier.emoji} {self.bm.tier.name}"

    def calculate_position_size(self, timeframe: int, confidence: float) -> float:
        """Position size from balance manager (tier-aware)."""
        return self.bm.get_position_size(confidence)

    def get_balance_preferences(self) -> Dict:
        """Get strategy preferences for current balance tier."""
        return self.bm.get_strategy_preference()

    def record_trade_result(self, pnl: float, won: bool):
        """Track results and update balance tier."""
        self.total_trades += 1
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.balance += pnl
        self.bm.update_balance(self.balance)

        if won:
            self.wins += 1
        else:
            self.losses += 1

    def should_hold_or_sell(self, entry_price: float, current_price: float,
                            seconds_remaining: int) -> str:
        """
        Dynamic exit decision based on balance tier.
        
        SURVIVAL: Take profits early (2x), cut losses tight (-10%)
        GROWTH: Moderate targets (3x), normal stop (-16%)
        AGGRESSIVE: Hold longer (5x), wider stop (-20%)
        FULL SEND: Diamond hands (7x), ride to settlement more
        """
        if entry_price <= 0:
            return 'hold'

        gain_multiple = current_price / entry_price
        pnl_pct = (current_price - entry_price) / entry_price * 100

        tier = self.bm.tier.name

        if tier == 'SURVIVAL':
            # Conservative: take profit early, tight stops
            if gain_multiple >= 2.0:
                return 'sell'
            if pnl_pct <= -10 and seconds_remaining > 20:
                return 'cut_loss'
        elif tier == 'GROWTH':
            # Moderate targets
            if gain_multiple >= 3.0:
                return 'sell'
            if gain_multiple >= 2.0 and seconds_remaining > 60:
                return 'sell'
            if pnl_pct <= -16 and seconds_remaining > 30:
                return 'cut_loss'
        elif tier == 'AGGRESSIVE':
            # Hold for bigger wins
            if gain_multiple >= 5.0:
                return 'sell'
            if gain_multiple >= 3.0 and seconds_remaining > 90:
                return 'sell'
            if pnl_pct <= -20 and seconds_remaining > 30:
                return 'cut_loss'
        else:  # FULL SEND
            # Diamond hands
            if gain_multiple >= 7.0:
                return 'sell'
            if gain_multiple >= 5.0 and seconds_remaining > 120:
                return 'sell'
            if pnl_pct <= -25 and seconds_remaining > 45:
                return 'cut_loss'

        # Near expiry with cheap entry → ride to settlement
        if seconds_remaining < 20 and entry_price < 0.10:
            return 'hold'

        return 'hold'

    def reset_daily(self):
        self.daily_pnl = 0.0

    def get_stats(self) -> Dict:
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        bm_status = self.bm.get_status()
        return {
            'balance': self.balance,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'open_positions': self.open_positions,
            **bm_status,
        }
