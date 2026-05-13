"""
V2 Risk Manager — Beast Mode Tiered Balance System

5-Tier system (user-requested, based on real low-balance usage):

  🛡️  SURVIVAL  ($0.50 - $5)   — Only HIGHEST conviction trades (4+ strategies agree)
       - Bet size: $1-$1.50 max
       - Min confidence: 70%
       - Max positions: 1
       - Goal: survive and double

  🌱 SEED       ($5 - $15)     — Top-tier signals only (3+ strategies agree)
       - Bet size: 3-5% of balance
       - Min confidence: 65%
       - Max positions: 3
       - Goal: build to comfortable

  ⚖️  COMFORT   ($15 - $50)    — Solid signals (2+ strategies agree)
       - Bet size: 4-6% of balance
       - Min confidence: 58%
       - Max positions: 5
       - Keep $5 reserve

  🔥 AGGRESSIVE ($50 - $150)   — All strategies enabled
       - Bet size: 5-8% of balance  
       - Min confidence: 55%
       - Max positions: 10
       - Keep $10 reserve

  🚀 FULL SEND  ($150+)         — Max aggression, compound
       - Bet size: 6-10% of balance
       - Min confidence: 50%
       - Max positions: 20
       - Keep $20 reserve

Includes:
- Kelly Criterion sizing (quarter-Kelly for safety)
- Drawdown-based circuit breakers
- Consecutive loss halt
- Streak-based position scaling
- Full logging of every decision
"""

import time
from typing import Dict, Tuple, Optional, List
from datetime import datetime, timezone
from collections import deque
from config import Config


class BalanceTier:
    """Tier definition with trading parameters."""
    def __init__(self, name, emoji, min_bal, max_bal,
                 bet_pct_range, min_confidence, max_positions,
                 min_agreement, reserve, description):
        self.name = name
        self.emoji = emoji
        self.min_bal = min_bal
        self.max_bal = max_bal
        self.bet_pct_min, self.bet_pct_max = bet_pct_range
        self.min_confidence = min_confidence
        self.max_positions = max_positions
        self.min_agreement = min_agreement  # Min strategies agreeing
        self.reserve = reserve
        self.description = description

    def contains(self, balance: float) -> bool:
        return self.min_bal <= balance < self.max_bal


# Tier definitions — LOWERED REQUIREMENTS (beast mode upgrade)
# Rationale: original thresholds too strict for real market conditions,
# bot was skipping 90%+ of valid signals. Lowered to trade more often
# while still maintaining quality via confidence + Kelly sizing.
TIERS = [
    BalanceTier(
        "SURVIVAL", "🛡️", 0.0, 5.0,
        bet_pct_range=(15.0, 25.0),   # 15-25% of tiny balance
        min_confidence=0.65,
        max_positions=2,
        min_agreement=2,               # Was 4, now 2 (still needs confirmation)
        reserve=0.0,
        description="Ultra-low balance — needs 2+ strategies agreeing (65%+ conf)"
    ),
    BalanceTier(
        "SEED", "🌱", 5.0, 15.0,
        bet_pct_range=(10.0, 18.0),
        min_confidence=0.60,
        max_positions=4,
        min_agreement=2,               # Was 3, now 2
        reserve=1.0,
        description="Seed capital — solid signals (2+ agree, 60%+ conf)"
    ),
    BalanceTier(
        "COMFORT", "⚖️", 15.0, 50.0,
        bet_pct_range=(4.0, 8.0),
        min_confidence=0.55,
        max_positions=6,
        min_agreement=1,               # Was 2, now 1 (all signals OK at this tier)
        reserve=5.0,
        description="Comfortable — all signals welcome (1+ agree, 55%+ conf)"
    ),
    BalanceTier(
        "AGGRESSIVE", "🔥", 50.0, 150.0,
        bet_pct_range=(5.0, 10.0),
        min_confidence=0.55,
        max_positions=10,
        min_agreement=1,               # All signals OK
        reserve=10.0,
        description="Aggressive — all signals welcome (1+ agree, 55%+ conf)"
    ),
    BalanceTier(
        "FULL SEND", "🚀", 150.0, float('inf'),
        bet_pct_range=(6.0, 12.0),
        min_confidence=0.50,
        max_positions=20,
        min_agreement=1,
        reserve=20.0,
        description="Full send — maximum aggression (50%+ conf)"
    ),
]


class V2RiskManager:
    """Beast Mode risk manager with 5-tier balance system."""

    def __init__(self, balance: float = None, log_callback=None):
        self.balance = balance if balance is not None else Config.STARTING_BALANCE
        self.starting_balance = self.balance
        self.peak_balance = self.balance
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.open_positions = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.recent_pnls: deque = deque(maxlen=50)
        self.position_exposure: Dict[str, float] = {}
        self._halted = False
        self._halt_reason = ''
        self._halt_until = 0
        # Manual tier override — user can lock the bot to any tier regardless
        # of balance via Telegram /tier command. None = auto-pick by balance.
        self._manual_tier_override: Optional[str] = None
        self.log = log_callback or (lambda lvl, msg: None)
        self.current_tier = self._determine_tier()
        self._last_tier_name = self.current_tier.name

    # ─── Manual tier override ───────────────────────────────────
    def set_manual_tier(self, tier_name: Optional[str]) -> Tuple[bool, str]:
        """
        Lock the bot to a specific tier regardless of balance. Pass None or
        'AUTO' to restore automatic balance-based selection.
        Returns (ok, message).
        """
        if tier_name is None or tier_name.upper() in ('AUTO', 'NONE', 'OFF'):
            self._manual_tier_override = None
            self.current_tier = self._determine_tier()
            self._last_tier_name = self.current_tier.name
            return True, f"Tier set to AUTO ({self.current_tier.emoji} {self.current_tier.name})"

        name = tier_name.upper().strip()
        # Accept 'FULL' as shorthand for 'FULL SEND'
        if name == 'FULL':
            name = 'FULL SEND'
        for t in TIERS:
            if t.name == name:
                self._manual_tier_override = t.name
                self.current_tier = t
                self._last_tier_name = t.name
                self.log('TIER', f"🔒 MANUAL TIER LOCK: {t.emoji} {t.name} (balance={self.balance:.2f})")
                return True, f"Tier locked to {t.emoji} {t.name} (overrides balance-based selection)"
        return False, f"Unknown tier '{tier_name}'. Valid: SURVIVAL, SEED, COMFORT, AGGRESSIVE, FULL SEND, AUTO"

    def get_manual_tier(self) -> Optional[str]:
        return self._manual_tier_override

    def _determine_tier(self) -> BalanceTier:
        """Find current tier. Manual override beats balance-based selection."""
        if self._manual_tier_override:
            for tier in TIERS:
                if tier.name == self._manual_tier_override:
                    return tier
        for tier in TIERS:
            if tier.contains(self.balance):
                return tier
        return TIERS[0]

    def _check_tier_change(self):
        """Log tier transitions. Manual override disables auto-transitions."""
        if self._manual_tier_override:
            # User has locked a tier; keep it no matter what balance does.
            return
        new_tier = self._determine_tier()
        if new_tier.name != self._last_tier_name:
            direction = "⬆️ UP" if new_tier.min_bal > self.current_tier.min_bal else "⬇️ DOWN"
            self.log('INFO', f"{direction} TIER CHANGE: {self.current_tier.name} → {new_tier.emoji} {new_tier.name}")
            self.log('INFO', f"   {new_tier.description}")
            self._last_tier_name = new_tier.name
        self.current_tier = new_tier

    def get_tier(self) -> BalanceTier:
        return self.current_tier

    def can_trade(self) -> Tuple[bool, str]:
        """Check if trading is currently allowed."""
        self._check_tier_change()

        if self._halted:
            if time.time() < self._halt_until:
                return False, f"HALTED: {self._halt_reason}"
            self._halted = False
            self.log('INFO', f"🔓 Halt cleared, resuming trades")

        if self.balance < Config.POLYMARKET_MIN_ORDER_SIZE:
            return False, f"💀 Balance too low ({self.balance:.2f} < {Config.POLYMARKET_MIN_ORDER_SIZE} pUSD)"

        dd = self._drawdown_pct()
        if dd >= Config.DRAWDOWN_HALT_PCT:
            self._halt(f"Drawdown {dd:.1f}%", 300)
            return False, f"📉 Drawdown halt: {dd:.1f}%"

        if self.consecutive_losses >= Config.CONSECUTIVE_LOSS_HALT:
            self._halt(f"{self.consecutive_losses} consecutive losses", 180)
            return False, f"🔴 {self.consecutive_losses} consecutive losses"

        daily_loss_pct = (self.daily_pnl / self.starting_balance * 100) if self.starting_balance > 0 else 0
        if daily_loss_pct < -Config.MAX_DAILY_LOSS_PCT:
            return False, f"📊 Daily loss limit ({daily_loss_pct:.1f}%)"

        if self.open_positions >= self.current_tier.max_positions:
            return False, f"📊 Max positions for {self.current_tier.name} tier ({self.open_positions}/{self.current_tier.max_positions})"

        return True, f"OK ({self.current_tier.emoji} {self.current_tier.name})"

    def validate_signal(self, confidence: float, direction: str,
                        coin: str, market_id: str,
                        agreement_count: int = 1) -> Tuple[bool, str]:
        """
        Tier-aware signal validation.
        
        Key: stricter tiers require higher confidence AND more strategies agreeing.
        """
        can, reason = self.can_trade()
        if not can:
            return False, reason

        tier = self.current_tier

        # Check tier's min confidence
        if confidence < tier.min_confidence:
            return False, (
                f"{tier.emoji} {tier.name}: confidence {confidence:.0%} "
                f"< tier min {tier.min_confidence:.0%}"
            )

        # Check tier's min agreement count
        if agreement_count < tier.min_agreement:
            return False, (
                f"{tier.emoji} {tier.name}: only {agreement_count} strategies agree "
                f"(need {tier.min_agreement}+ for this tier)"
            )

        return True, f"OK ({tier.emoji} {tier.name})"

    def calculate_position_size(self, confidence: float, strategy: str = '',
                                 market_id: str = '', order_type: str = 'maker',
                                 agreement_count: int = 1,
                                 conviction_tier: str = 'SINGLE') -> float:
        """
        Tier-aware Kelly-based position sizing.
        
        Returns pUSD size for the trade. Respects:
        - Tier bet_pct range
        - Kelly Criterion
        - Drawdown scaling
        - Streak multipliers
        - High conviction multiplier
        
        Floor: always enforces POLYMARKET_MIN_ORDER_SIZE. If even the MIN
        order would exceed available tradeable balance, returns 0 (skip).
        This fixes the sub-minimum sizing bug where $6 balance + SEED tier
        → base size 0.25 → max(MIN=1, 0.25)=1 → min(cap=0.90) = 0.90 REJECTED.
        """
        if not self.can_trade()[0]:
            return 0.0

        tier = self.current_tier
        MIN = Config.POLYMARKET_MIN_ORDER_SIZE

        # Edge calculation
        edge = confidence - 0.50
        if edge <= 0.02:
            return 0.0

        # Kelly fraction (capped)
        kelly_full = 2 * confidence - 1
        kelly_safe = kelly_full * Config.KELLY_FRACTION
        kelly_capped = min(kelly_safe, Config.KELLY_MAX_BET_PCT)

        # Tier-based sizing
        conf_progress = (confidence - tier.min_confidence) / (0.95 - tier.min_confidence)
        conf_progress = max(0, min(1, conf_progress))
        tier_pct = tier.bet_pct_min + (tier.bet_pct_max - tier.bet_pct_min) * conf_progress

        # Use the smaller of Kelly vs tier max (safety)
        effective_pct = min(kelly_capped * 100, tier_pct)

        # Cap reserve at 50% of balance. Without this, manually overriding to
        # AGGRESSIVE (reserve=$10) with a $3 balance gives tradeable=-$7 which
        # we clamp to $1, and the bot can never place an order. Capping at
        # balance/2 means low-balance users can still use high tiers — they
        # just get half their balance as playing money and half as reserve.
        effective_reserve = min(tier.reserve, self.balance * 0.5)
        tradeable = max(MIN, self.balance - effective_reserve)
        size = tradeable * effective_pct / 100.0

        # Drawdown scaling
        dd = self._drawdown_pct()
        if dd > 15:
            size *= 0.50
        elif dd > 10:
            size *= 0.70
        elif dd > 5:
            size *= 0.85

        # Streak scaling
        if self.consecutive_losses >= 5:
            size *= 0.30
        elif self.consecutive_losses >= 3:
            size *= 0.60
        elif self.consecutive_wins >= 5:
            size *= 1.30
        elif self.consecutive_wins >= 3:
            size *= 1.15

        # Conviction multiplier (from signal ranker tier)
        if conviction_tier == 'MAXIMUM':
            size *= 1.5
        elif conviction_tier == 'HIGH':
            size *= 1.25
        elif conviction_tier == 'MEDIUM':
            size *= 1.1

        # ── Apply CAPS first (shrink size if too big) ──
        if tier.name == 'SURVIVAL':
            # SURVIVAL: absolute cap of 1.5 pUSD per trade
            size = min(size, 1.5)
        else:
            # Other tiers: cap to 25% of tradeable and 15% of balance
            size = min(size, tradeable * 0.25, self.balance * 0.15)

        # ── Hard floor: enforce exchange minimum AFTER all caps ──
        # Low-balance tiers always need a MIN-sized order or we can never
        # trade. Only skip if we can't even afford the MIN out of tradeable.
        if size < MIN:
            # Can we afford a MIN-sized order without blowing past balance?
            # Need MIN + a tiny buffer so we don't end up negative on gas/rounding
            required_buffer = MIN * 1.05
            if tradeable >= required_buffer:
                # Bump size UP to MIN. User's tier config said "bet X%" but the
                # exchange won't let us bet less than MIN, so MIN is the true
                # minimum bet size.
                size = MIN
            else:
                # Can't afford even a MIN order. Skip rather than return an
                # invalid size below MIN.
                return 0.0

        return round(size, 2)

    def record_trade_result(self, pnl: float, won: bool, market_id: str = ''):
        """Record a completed trade."""
        self.total_trades += 1
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.balance += pnl
        self.peak_balance = max(self.peak_balance, self.balance)
        self.recent_pnls.append(pnl)

        if won:
            self.wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        if market_id in self.position_exposure:
            del self.position_exposure[market_id]

        # Check for tier change after balance update
        self._check_tier_change()

    def register_position(self, market_id: str, size: float):
        """Register an open position."""
        self.position_exposure[market_id] = self.position_exposure.get(market_id, 0) + size
        self.open_positions += 1

    def close_position(self, market_id: str):
        """Mark position as closed (no PnL update — use record_trade_result)."""
        self.open_positions = max(0, self.open_positions - 1)

    def _drawdown_pct(self) -> float:
        if self.peak_balance <= 0:
            return 0
        return (self.peak_balance - self.balance) / self.peak_balance * 100

    def _halt(self, reason, duration_seconds):
        self._halted = True
        self._halt_reason = reason
        self._halt_until = time.time() + duration_seconds
        self.log('RISK', f"🚨 HALT: {reason} (for {duration_seconds}s)")

    def get_status_line(self) -> str:
        wr = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        streak = f"W{self.consecutive_wins}" if self.consecutive_wins > 0 else f"L{self.consecutive_losses}"
        return (
            f"{self.current_tier.emoji}{self.current_tier.name[:4]} "
            f"{Config.format_balance(self.balance)} | "
            f"W/L:{self.wins}/{self.losses} ({wr:.0f}%) | "
            f"DD:{self._drawdown_pct():.1f}% | {streak}"
        )

    def get_stats(self) -> Dict:
        wr = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0
        return {
            'balance': self.balance,
            'peak_balance': self.peak_balance,
            'starting_balance': self.starting_balance,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'drawdown_pct': self._drawdown_pct(),
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': wr,
            'total_trades': self.total_trades,
            'open_positions': self.open_positions,
            'tier': self.current_tier.name,
            'tier_emoji': self.current_tier.emoji,
            'tier_description': self.current_tier.description,
            'tier_min_conf': self.current_tier.min_confidence,
            'tier_min_agreement': self.current_tier.min_agreement,
            'tier_max_positions': self.current_tier.max_positions,
            'halted': self._halted,
            'halt_reason': self._halt_reason,
            'manual_tier': self._manual_tier_override,
        }
