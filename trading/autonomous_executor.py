"""
Autonomous Trade Executor — Beast Mode

Full-auto entry/exit with tier-aware validation:
- Entry: Kelly-sized + tier-aware agreement filter
- TP/SL monitoring: checks each open position every scan
- Auto-exit: profit target, stop loss, or time-based
- Paper simulation: realistic fill simulation with resolution
- Live execution: uses CLOB for real orders

Logs EVERY decision with reason.
"""

import time
import uuid
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone

from config import Config
from strategies.base_strategy import TradeSignal


class Position:
    def __init__(self, signal: TradeSignal, size_pusd: float, entry_price: float,
                 order_id: str = None):
        self.id = str(uuid.uuid4())[:8]
        self.signal = signal
        self.coin = signal.coin
        self.direction = signal.direction
        self.market_id = signal.market_id
        self.token_id = signal.token_id
        self.timeframe = signal.timeframe
        self.strategy = signal.strategy
        self.confidence = signal.confidence
        self.size_pusd = size_pusd
        self.entry_price = entry_price
        self.order_id = order_id
        self.opened_at = time.time()
        self.shares = size_pusd / entry_price if entry_price > 0 else 0

        tf_params = Config.get_timeframe_params(signal.timeframe)
        self.take_profit_pct = tf_params['take_profit_pct']
        self.stop_loss_pct = tf_params['stop_loss_pct']
        self.max_hold_seconds = signal.timeframe * 60 + 60

        self.current_price = entry_price
        self.pnl_pusd = 0.0
        self.pnl_pct = 0.0
        self.status = 'open'

    def update_price(self, current_price: float):
        self.current_price = current_price
        if self.direction == 'UP':
            self.pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        elif self.direction in ('SELL_UP', 'SHORT'):
            # Short position — profit when price drops
            self.pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
        else:  # DOWN
            self.pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        self.pnl_pusd = self.size_pusd * self.pnl_pct / 100

    def should_exit(self) -> Optional[str]:
        """Return exit reason or None."""
        elapsed = time.time() - self.opened_at
        if self.pnl_pct >= self.take_profit_pct:
            return f'profit_take ({self.pnl_pct:.1f}%)'
        if self.pnl_pct <= -self.stop_loss_pct:
            return f'stop_loss ({self.pnl_pct:.1f}%)'
        if elapsed > self.max_hold_seconds:
            return f'timeout ({elapsed:.0f}s)'
        return None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'coin': self.coin,
            'direction': self.direction,
            'strategy': self.strategy,
            'confidence': self.confidence,
            'size_pusd': self.size_pusd,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'pnl_pusd': self.pnl_pusd,
            'pnl_pct': self.pnl_pct,
            'tp_pct': self.take_profit_pct,
            'sl_pct': -self.stop_loss_pct,
            'elapsed_sec': int(time.time() - self.opened_at),
            'status': self.status,
        }


class AutonomousExecutor:
    """Full-auto trade executor with TP/SL monitoring."""

    def __init__(self, risk_mgr, clob_client, log_callback: Callable = None):
        self.risk_mgr = risk_mgr
        self.clob = clob_client
        self.log = log_callback or (lambda lvl, msg: None)
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[Position] = []
        self._dedup: Dict[str, float] = {}
        self.DEDUP_SECS = 15

    def is_dedup(self, signal: TradeSignal) -> bool:
        key = f"{signal.coin}_{signal.direction}_{signal.timeframe}_{signal.market_id}"
        now = time.time()
        if key in self._dedup and (now - self._dedup[key]) < self.DEDUP_SECS:
            return True
        self._dedup[key] = now
        return False

    async def execute_signal(self, signal: TradeSignal) -> Optional[Position]:
        """Execute a trade signal with comprehensive logging."""
        if self.is_dedup(signal):
            return None

        agreement_count = signal.metadata.get('agreement_count', 1)
        conviction_tier = signal.metadata.get('conviction_tier', 'SINGLE')

        # Tier-aware validation
        ok, reason = self.risk_mgr.validate_signal(
            signal.confidence, signal.direction,
            signal.coin, signal.market_id,
            agreement_count=agreement_count,
        )
        if not ok:
            self.log('RISK', f"⛔ BLOCKED: {signal.coin} {signal.direction} — {reason}")
            return None

        # Tier-aware sizing
        size_pusd = self.risk_mgr.calculate_position_size(
            signal.confidence, signal.strategy, signal.market_id,
            signal.order_type,
            agreement_count=agreement_count,
            conviction_tier=conviction_tier,
        )

        if size_pusd < Config.POLYMARKET_MIN_ORDER_SIZE:
            self.log('WARN', f"⚠️ Size {size_pusd:.2f} < min {Config.POLYMARKET_MIN_ORDER_SIZE} — skip")
            return None

        entry_price = signal.limit_price or signal.entry_price

        tier = self.risk_mgr.get_tier()
        self.log('TRADE', f"🎯 ENTRY [{tier.emoji}{tier.name}] {signal.coin} {signal.direction} "
                         f"[{conviction_tier}] "
                         f"size={size_pusd:.2f}pUSD @ {entry_price:.3f} "
                         f"conf={signal.confidence:.0%} agree={agreement_count} | {signal.strategy}")
        self.log('TRADE', f"   Reason: {signal.rationale[:140]}")

        # Execute (paper vs live)
        order_id = None
        if Config.is_paper():
            self.log('PAPER', f"   📋 PAPER execution (simulated)")
            order_id = f"paper-{uuid.uuid4().hex[:8]}"
        else:
            if not self.clob.is_initialized():
                self.log('ERROR', f"   ❌ Live mode but CLOB not initialized")
                return None

            side = 'BUY'
            if signal.direction in ('SELL_UP', 'SHORT'):
                side = 'SELL'

            if signal.order_type == 'maker' and signal.limit_price:
                self.log('TRADE', f"   📤 LIMIT {side} @ {signal.limit_price:.3f}")
                result = self.clob.place_limit_order(
                    token_id=signal.token_id, side=side,
                    price=signal.limit_price, size_pusd=size_pusd,
                    expiration='GTC',
                )
            else:
                self.log('TRADE', f"   📤 MARKET {side}")
                result = self.clob.place_market_order(
                    token_id=signal.token_id, side=side,
                    size_pusd=size_pusd, price=signal.entry_price,
                )

            if not result:
                self.log('ERROR', f"   ❌ Order placement FAILED")
                return None
            order_id = result.get('order_id', 'unknown')
            self.log('TRADE', f"   ✅ Order placed: {order_id} status={result.get('status')}")

        # Create position
        position = Position(signal, size_pusd, entry_price, order_id)
        self.open_positions[position.id] = position
        self.risk_mgr.register_position(signal.market_id, size_pusd)

        self.log('TRADE', f"   ✅ Position opened: {position.id} "
                         f"TP=+{position.take_profit_pct:.0f}% SL=-{position.stop_loss_pct:.0f}%")
        return position

    async def monitor_positions(self, current_prices: Dict[str, float]) -> List[Position]:
        """Check all open positions for exit conditions."""
        closed = []
        for pid, pos in list(self.open_positions.items()):
            current = current_prices.get(pos.token_id)
            if current is None or current <= 0:
                continue
            pos.update_price(current)

            reason = pos.should_exit()
            if reason:
                await self._close_position(pid, reason)
                closed.append(pos)
        return closed

    async def _close_position(self, pid: str, reason: str):
        pos = self.open_positions.pop(pid, None)
        if not pos:
            return

        won = pos.pnl_pusd > 0
        pos.status = 'closed_' + reason.split(' ')[0]

        # Update risk manager (this records PnL and decrements open_positions)
        self.risk_mgr.record_trade_result(pos.pnl_pusd, won, pos.market_id)
        self.risk_mgr.close_position(pos.market_id)

        self.closed_trades.append(pos)
        if len(self.closed_trades) > 200:
            self.closed_trades = self.closed_trades[-200:]

        emoji = '✅' if won else '❌'
        self.log('TRADE', f"{emoji} EXIT: {pos.coin} {pos.direction} "
                         f"PnL={pos.pnl_pusd:+.2f}pUSD ({pos.pnl_pct:+.1f}%) "
                         f"reason={reason} strat={pos.strategy}")

    def get_positions_snapshot(self) -> List[dict]:
        return [p.to_dict() for p in self.open_positions.values()]

    def get_closed_snapshot(self, limit: int = 20) -> List[dict]:
        return [p.to_dict() for p in self.closed_trades[-limit:][::-1]]
