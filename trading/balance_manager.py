"""
Dynamic Balance Manager — Tiered Aggression System

THE IDEA: Risk less when balance is low, risk more when balance is high.

TIERS:
  $0-$15   → SURVIVAL: Ultra-conservative. Tiny bets, focus on doubling.
  $15-$50  → GROWTH: Moderate aggression. Build the bankroll.
  $50-$100 → AGGRESSIVE: Trade hard with $40+, keep $10 reserve.
  $100+    → FULL SEND: Maximum aggression, compound profits.

In live mode this ensures you never fully bust out.
The reserve floor ($10) means you always have a restart amount.
"""

from typing import Dict


class BalanceTier:
    """Represents a balance tier with its trading parameters."""
    def __init__(self, name: str, emoji: str, min_bal: float, max_bet_pct: float,
                 reserve: float, max_positions: int, aggression: float):
        self.name = name
        self.emoji = emoji
        self.min_bal = min_bal
        self.max_bet_pct = max_bet_pct      # Max % of TRADEABLE balance per trade
        self.reserve = reserve               # Amount to keep untouched
        self.max_positions = max_positions
        self.aggression = aggression         # 0.0 to 1.0


# Tier definitions
TIERS = [
    BalanceTier(
        name="SURVIVAL", emoji="🛡️",
        min_bal=0, max_bet_pct=2.0, reserve=0,
        max_positions=5, aggression=0.3
    ),
    BalanceTier(
        name="GROWTH", emoji="🌱",
        min_bal=15, max_bet_pct=3.0, reserve=5.0,
        max_positions=10, aggression=0.5
    ),
    BalanceTier(
        name="AGGRESSIVE", emoji="🔥",
        min_bal=50, max_bet_pct=5.0, reserve=10.0,
        max_positions=15, aggression=0.75
    ),
    BalanceTier(
        name="FULL SEND", emoji="🚀",
        min_bal=100, max_bet_pct=7.0, reserve=15.0,
        max_positions=20, aggression=1.0
    ),
]


class DynamicBalanceManager:
    """
    Adjusts trading parameters based on current balance.
    
    Low balance → conservative, small bets, focus on safe doubles
    High balance → aggressive, bigger bets, more positions
    Always keeps a reserve amount safe
    """

    def __init__(self, balance: float):
        self.balance = balance
        self._update_tier()

    def _update_tier(self):
        """Determine current tier based on balance."""
        self.tier = TIERS[0]  # Default to SURVIVAL
        for t in reversed(TIERS):
            if self.balance >= t.min_bal:
                self.tier = t
                break

    def update_balance(self, new_balance: float):
        """Update balance and recalculate tier."""
        old_tier = self.tier.name
        self.balance = new_balance
        self._update_tier()
        if self.tier.name != old_tier:
            print(f"📊 TIER CHANGE: {old_tier} → {self.tier.emoji} {self.tier.name} "
                  f"(${self.balance:.2f})")

    @property
    def tradeable_balance(self) -> float:
        """Balance available for trading (total - reserve)."""
        return max(0.50, self.balance - self.tier.reserve)

    def get_position_size(self, confidence: float) -> float:
        """
        Calculate position size based on tier and confidence.
        
        SURVIVAL: tiny bets (2% of tradeable)
        GROWTH: moderate (3%)
        AGGRESSIVE: bigger (5%)
        FULL SEND: maximum (7%)
        """
        pct = self.tier.max_bet_pct * (0.5 + confidence * 0.5)
        size = self.tradeable_balance * pct / 100

        # Absolute limits
        min_size = 0.25 if self.tier.name == 'SURVIVAL' else 0.50
        max_size = self.tradeable_balance * 0.10  # Never more than 10%

        size = max(min_size, min(size, max_size))
        return round(size, 2)

    @property
    def max_positions(self) -> int:
        return self.tier.max_positions

    def should_trade(self) -> tuple:
        """Check if we should trade at this balance level."""
        if self.balance < 0.50:
            return False, "💀 Balance too low"
        if self.tradeable_balance < 0.25:
            return False, "🛡️ Only reserve left"
        return True, f"{self.tier.emoji} {self.tier.name}"

    def get_strategy_preference(self) -> Dict:
        """
        Which strategies to prioritize at each tier.
        
        SURVIVAL: Safe arbs, cheap outcomes only
        GROWTH: Add trend following, straddles
        AGGRESSIVE: All strategies enabled
        FULL SEND: All strategies, higher frequency
        """
        if self.tier.name == 'SURVIVAL':
            return {
                'enabled': ['cheap_hunter', 'yes_no_arb', 'spread_scalper'],
                'disabled': ['straddle'],  # Too risky at low balance
                'min_confidence': 0.60,     # Higher bar when poor
            }
        elif self.tier.name == 'GROWTH':
            return {
                'enabled': ['cheap_hunter', 'yes_no_arb', 'mid_sniper',
                           'trend_follower', 'spread_scalper', 'oracle_arb'],
                'disabled': [],
                'min_confidence': 0.45,
            }
        elif self.tier.name == 'AGGRESSIVE':
            return {
                'enabled': 'all',
                'disabled': [],
                'min_confidence': 0.35,     # Low bar = more trades
            }
        else:  # FULL SEND
            return {
                'enabled': 'all',
                'disabled': [],
                'min_confidence': 0.30,     # Trade everything
            }

    def get_status(self) -> Dict:
        return {
            'balance': self.balance,
            'tier': self.tier.name,
            'tier_emoji': self.tier.emoji,
            'tradeable': self.tradeable_balance,
            'reserve': self.tier.reserve,
            'max_bet_pct': self.tier.max_bet_pct,
            'max_positions': self.tier.max_positions,
            'aggression': self.tier.aggression,
        }
