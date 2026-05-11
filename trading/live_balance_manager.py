"""
Live Balance Manager — Risk Modes with USDC

Updated for v2:
- All amounts in USDC
- Maker-focused position sizing
- Category-aware spread management
"""

import time
from typing import Dict, Optional
from config import Config


class LiveRiskMode:
    """Defines parameters for a live trading risk mode."""
    def __init__(self, name: str, emoji: str, max_bet_pct: float,
                 reserve_pct: float, reserve_min_usdc: float,
                 max_pos_per_dollar: float, max_positions_cap: int,
                 min_confidence: float, description: str,
                 maker_preference: float = 0.8):
        self.name = name
        self.emoji = emoji
        self.max_bet_pct = max_bet_pct
        self.reserve_pct = reserve_pct
        self.reserve_min_usdc = reserve_min_usdc
        self.max_pos_per_dollar = max_pos_per_dollar
        self.max_positions_cap = max_positions_cap
        self.min_confidence = min_confidence
        self.description = description
        self.maker_preference = maker_preference  # % of trades as maker


# ═══════════════════════════════════════════════════════════════════
# RISK MODE DEFINITIONS (USDC)
# ═══════════════════════════════════════════════════════════════════

LIVE_MODES = {
    'seed': LiveRiskMode(
        name='SEED',
        emoji='🌱',
        max_bet_pct=20.0,
        reserve_pct=15.0,
        reserve_min_usdc=0.50,
        max_pos_per_dollar=1.0,
        max_positions_cap=2,
        min_confidence=0.90,
        description='1-5 USDC start — 2 positions, 0.90 confidence, safe growth',
        maker_preference=1.0,  # Always maker
    ),
    'plant': LiveRiskMode(
        name='PLANT',
        emoji='🌿',
        max_bet_pct=22.0,
        reserve_pct=22.0,
        reserve_min_usdc=2.0,
        max_pos_per_dollar=0.5,
        max_positions_cap=3,
        min_confidence=0.87,
        description='5-15 USDC — growth mode, maker-focused, quality signals',
        maker_preference=0.95,
    ),
    'concentration': LiveRiskMode(
        name='CONCENTRATION',
        emoji='🎯',
        max_bet_pct=20.0,
        reserve_pct=40.0,
        reserve_min_usdc=2.0,
        max_pos_per_dollar=0.25,
        max_positions_cap=4,
        min_confidence=0.65,
        description='5-20 USDC — focused growth with safety net',
        maker_preference=0.90,
    ),
    'medium': LiveRiskMode(
        name='MEDIUM',
        emoji='\u2696\ufe0f',
        max_bet_pct=50.0,
        reserve_pct=10.0,
        reserve_min_usdc=0.50,
        max_pos_per_dollar=0.5,
        max_positions_cap=8,
        min_confidence=0.40,
        description='20-100 USDC — balanced risk, more strategies',
        maker_preference=0.85,
    ),
    'aggressive': LiveRiskMode(
        name='AGGRESSIVE',
        emoji='🔥',
        max_bet_pct=45.0,
        reserve_pct=10.0,
        reserve_min_usdc=1.00,
        max_pos_per_dollar=0.5,
        max_positions_cap=12,
        min_confidence=0.30,
        description='100+ USDC — full compound, all strategies, maximum growth',
        maker_preference=0.75,  # Allow some taker for speed
    ),
}

# Auto-graduation thresholds (in USDC)
GRADUATION_THRESHOLDS = {
    'seed': ('plant', 5.0),
    'plant': ('medium', 20.0),
    'concentration': ('medium', 20.0),
    'medium': ('aggressive', 100.0),
}

SEED_GRADUATE_BALANCE_USDC = GRADUATION_THRESHOLDS['seed'][1]


class LiveBalanceManager:
    """
    Dynamic balance management for live trading with USDC.
    Features maker-first sizing and category-aware spreads.
    """

    def __init__(self, balance_usdc: float = 0.0, mode: str = 'concentration'):
        self.balance_usdc = balance_usdc
        self.initial_balance_usdc = balance_usdc
        self.mode = LIVE_MODES.get(mode, LIVE_MODES['concentration'])
        self.open_positions = 0
        self.daily_pnl_usdc = 0.0
        self.peak_balance_usdc = balance_usdc
        self.max_drawdown_pct = 0.0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self._mode_name = mode
        self._last_check = 0

    def set_mode(self, mode: str):
        """Set risk mode."""
        if mode in LIVE_MODES:
            self.mode = LIVE_MODES[mode]
            self._mode_name = mode

    def get_mode_name(self) -> str:
        """Get current mode name."""
        return self._mode_name

    def update_balance(self, new_balance_usdc: float):
        """Update balance and track metrics."""
        old_balance = self.balance_usdc
        self.balance_usdc = new_balance_usdc
        
        # Track peak and drawdown
        if new_balance_usdc > self.peak_balance_usdc:
            self.peak_balance_usdc = new_balance_usdc
        
        if self.peak_balance_usdc > 0:
            drawdown = (self.peak_balance_usdc - new_balance_usdc) / self.peak_balance_usdc * 100
        else:
            drawdown = 0.0
        self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown)
        
        # Track daily P&L
        self.daily_pnl_usdc += new_balance_usdc - old_balance
        
        # Check for graduation
        self._check_graduation()

    def _check_graduation(self):
        """Check if balance qualifies for mode graduation."""
        if self._mode_name not in GRADUATION_THRESHOLDS:
            return
        
        next_mode, threshold = GRADUATION_THRESHOLDS[self._mode_name]
        if self.balance_usdc >= threshold and next_mode in LIVE_MODES:
            print(f"🎓 Graduating {self._mode_name} → {next_mode} (balance: {Config.format_usdc(self.balance_usdc)})", flush=True)
            self.set_mode(next_mode)

    def record_trade_result(self, pnl_usdc: float, won: bool):
        """Record trade result and update streaks."""
        if won:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

    def get_tradeable_balance_usdc(self) -> float:
        """Get balance available for trading."""
        # For small balances, use minimal reserve
        if self.balance_usdc <= 5.0:
            reserve = 0.30  # Keep 30 cents as buffer for gas/fees
        elif self.balance_usdc <= 20.0:
            reserve = 1.00  # Keep $1 reserve
        else:
            reserve_pct = self.balance_usdc * (self.mode.reserve_pct / 100)
            reserve = max(reserve_pct, self.mode.reserve_min_usdc)
        return max(0, self.balance_usdc - reserve)

    def calculate_position_size_usdc(self, timeframe: int, confidence: float,
                                     order_type: str = 'maker') -> float:
        """
        Calculate position size in USDC.
        
        Smart sizing based on available balance:
        - Always respects $1 minimum (Polymarket FOK minimum)
        - Uses $1 per position for small balances, scaling up for larger ones
        - Keeps a small reserve for safety
        - Maker orders can be larger (no taker fees)
        """
        min_size = Config.POLYMARKET_MIN_ORDER_SIZE_USDC  # $1.00
        tradeable = self.get_tradeable_balance_usdc()
        
        if tradeable < min_size:
            return 0  # Can't even afford minimum order
        
        # Max positions check
        if self.open_positions >= self.mode.max_positions_cap:
            return 0
        
        # Remaining slots
        remaining_slots = self.mode.max_positions_cap - self.open_positions
        
        # Split tradeable balance across remaining slots
        # But each position must be at least $1
        per_slot = tradeable / max(1, remaining_slots)
        
        # Confidence and mode adjustments
        base_pct = self.mode.max_bet_pct / 100
        conf_mult = 0.5 + (confidence * 0.5)  # 0.5 to 1.0
        maker_mult = 1.2 if order_type == 'maker' else 1.0
        loss_mult = max(0.7, 1.0 - (self.consecutive_losses * 0.05))
        
        # Kelly-style: use min of per_slot and percentage-based
        pct_size = tradeable * base_pct * conf_mult * maker_mult * loss_mult
        size = min(per_slot, pct_size)
        
        # For small balances, just use $1 per position (minimum viable)
        if tradeable <= 5.0:
            size = min_size  # $1 per position for balances <= $5
        elif tradeable <= 20.0:
            size = max(min_size, min(size, 3.0))  # $1-3 per position for $5-20
        
        # Hard cap: never risk more than 45% of total balance on one trade
        max_size = self.balance_usdc * 0.45
        size = min(size, max_size)
        
        # Ensure minimum
        size = max(min_size, size)
        
        # Can't exceed tradeable
        size = min(size, tradeable)
        
        return round(size, 2)

    def can_trade(self, confidence: float = 0.0, order_type: str = 'maker') -> tuple:
        """Check if trading is allowed."""
        if self.balance_usdc < Config.POLYMARKET_MIN_ORDER_SIZE_USDC:
            return False, f"Balance {Config.format_usdc(self.balance_usdc)} below minimum"
        
        if confidence < self.mode.min_confidence:
            return False, f"Confidence {confidence:.0%} below threshold {self.mode.min_confidence:.0%}"
        
        if self.open_positions >= self.mode.max_positions_cap:
            return False, f"Max positions ({self.mode.max_positions_cap}) reached"
        
        # Check daily loss limit
        daily_loss_pct = abs(min(0, self.daily_pnl_usdc)) / self.initial_balance_usdc * 100 if self.initial_balance_usdc > 0 else 0
        if daily_loss_pct >= Config.MAX_DAILY_LOSS_PCT:
            return False, f"Daily loss limit ({Config.MAX_DAILY_LOSS_PCT}%) reached"
        
        return True, "OK"

    def get_stats(self) -> Dict:
        """Get current stats."""
        return {
            'balance_usdc': self.balance_usdc,
            'initial_balance_usdc': self.initial_balance_usdc,
            'tradeable_usdc': self.get_tradeable_balance_usdc(),
            'daily_pnl_usdc': self.daily_pnl_usdc,
            'max_drawdown_pct': self.max_drawdown_pct,
            'open_positions': self.open_positions,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'mode': self.mode.name,
            'maker_preference': self.mode.maker_preference,
        }
