"""
Autonomous Trade Executor — Beast Mode

Full-auto entry/exit with tier-aware validation and REAL on-chain execution:

- Entry: Kelly-sized + tier-aware agreement filter
- Pending-order tracking: an order sitting on the book (status=LIVE) is
  NOT yet a position. We track pending orders separately, poll their
  status, and only promote to a Position once status=MATCHED (filled).
  Unfilled orders are canceled after PENDING_ORDER_TIMEOUT seconds.
- FOK for high-conviction taker entries: when signal.order_type == 'taker'
  AND conviction_tier in {HIGH, MAXIMUM}, place a fill-or-kill limit
  instead of a GTC limit — speed matters for oracle front-running.
- Real exit orders: when TP/SL fires in LIVE mode, we place an opposite
  SELL order on the CLOB (FOK) to actually close the position on-chain,
  not just update paper PnL.
- Balance refresh hook: after any fill or exit, we call balance_refresh_cb
  so the dashboard shows fresh on-chain pUSD, not stale internal PnL.
- Paper mode: still simulates fills instantly (no CLOB round-trip).

Logs EVERY decision with reason.
"""

import time
import uuid
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone

from config import Config
from strategies.base_strategy import TradeSignal


# How long a GTC limit order is allowed to sit unfilled before we cancel it
# and give up. Oracle-lead signals are time-sensitive; a fill that lands 30s
# late is usually a loss.
PENDING_ORDER_TIMEOUT = 30.0  # seconds


class Position:
    """
    Position with LINEAR SCORE-BASED TP/SL.

    New formula (v2 beast mode upgrade):
      TP% = 30 + (score - 1) * 15
      SL% = 16 + (score - 1) * 5
      score >= 5 → hold to resolution (let market close naturally)

    Score is the agreement_count (number of strategies that agree).

    Examples:
      score=1 → TP=30%, SL=16%     (conservative, single signal)
      score=2 → TP=45%, SL=21%     (MEDIUM)
      score=3 → TP=60%, SL=26%     (HIGH)
      score=4 → TP=75%, SL=31%     (stronger HIGH)
      score=5+ → hold to resolution (MAXIMUM, let it resolve)
    """

    # Legacy tier table (kept for backward compat / fallback only)
    DYNAMIC_EXITS = {
        'MAXIMUM': {'tp_pct': 200.0, 'sl_pct': 50.0, 'hold_to_resolution': True},
        'HIGH':    {'tp_pct': 90.0,  'sl_pct': 35.0, 'hold_to_resolution': False},
        'MEDIUM':  {'tp_pct': 70.0,  'sl_pct': 25.0, 'hold_to_resolution': False},
        'SINGLE':  {'tp_pct': 35.0,  'sl_pct': 16.0, 'hold_to_resolution': False},
    }

    @staticmethod
    def compute_exits_from_score(score: int, timeframe: int = 5) -> dict:
        """
        Linear score-based TP/SL, scaled by timeframe.

        Score determines base TP/SL (more strategies agreeing = wider targets).
        Timeframe multiplier widens targets for longer markets — a 30min market
        has ~2.4x the price variance of a 5min market (sqrt(30/5) ≈ 2.45), so
        a SL tight enough for 5min trades fires prematurely on 30min trades
        before the thesis has time to play out.

        TIMEFRAME MULTIPLIER (volatility adjustment, approx sqrt of ratio):
          5min  → 1.00x  (baseline)
          15min → 1.60x  (sqrt(3) ≈ 1.73, trimmed for safety)
          30min → 2.25x  (sqrt(6) ≈ 2.45, trimmed for safety)

        score >= 5 → hold to resolution (let market close naturally)

        Examples (5min baseline):
          score=1 → TP=30%, SL=16%
          score=2 → TP=45%, SL=21%
          score=3 → TP=60%, SL=26%
          score=4 → TP=75%, SL=31%
          score=5+ → hold to resolution

        Examples (15min, 1.6x mult):
          score=1 → TP=48%, SL=26%
          score=3 → TP=96%, SL=42%

        Examples (30min, 2.25x mult):
          score=1 → TP=68%, SL=36%
          score=3 → TP=135%, SL=59%
        """
        score = max(1, int(score))
        tf = int(timeframe) if timeframe else 5
        if tf <= 5:
            mult = 1.0
        elif tf <= 15:
            mult = 1.6
        elif tf <= 30:
            mult = 2.25
        else:
            # Very long tf — cap multiplier so SL stays sane
            mult = min(3.0, (tf / 5.0) ** 0.5)

        if score >= 5:
            # Hold to resolution: wide SL, but still scale so 30m doesn't
            # get nuked on a quick -50% dip.
            return {
                'tp_pct': 200.0,
                'sl_pct': min(75.0, 50.0 * mult),
                'hold_to_resolution': True,
            }
        base_tp = 30.0 + (score - 1) * 15.0   # 30, 45, 60, 75
        base_sl = 16.0 + (score - 1) * 5.0    # 16, 21, 26, 31
        return {
            'tp_pct': round(base_tp * mult, 1),
            'sl_pct': round(base_sl * mult, 1),
            'hold_to_resolution': False,
        }

    def __init__(self, signal: TradeSignal, size_pusd: float, entry_price: float,
                 order_id: str = None, shares_filled: float = None):
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
        # Prefer the actual filled share count from the CLOB (more accurate
        # than size_pusd / entry_price when partial fills happen).
        if shares_filled is not None and shares_filled > 0:
            self.shares = shares_filled
        else:
            self.shares = size_pusd / entry_price if entry_price > 0 else 0

        conviction_tier = signal.metadata.get('conviction_tier', 'SINGLE')
        agreement_count = signal.metadata.get('agreement_count', 1)
        exits = self.compute_exits_from_score(agreement_count, self.timeframe)

        self.take_profit_pct = exits['tp_pct']
        self.stop_loss_pct = exits['sl_pct']
        self.hold_to_resolution = exits['hold_to_resolution']
        self.conviction_tier = conviction_tier
        self.agreement_count = agreement_count

        if self.confidence >= 0.80:
            self.stop_loss_pct *= 1.3
        elif self.confidence >= 0.70:
            self.stop_loss_pct *= 1.15

        if self.hold_to_resolution:
            self.max_hold_seconds = signal.timeframe * 60 + 120
        else:
            self.max_hold_seconds = signal.timeframe * 60 + 60

        self.current_price = entry_price
        self.pnl_pusd = 0.0
        self.pnl_pct = 0.0
        self.status = 'open'
        # Exit-order tracking (live mode): order_id of the SELL we placed
        # to close. None until exit is triggered.
        self.exit_order_id: Optional[str] = None
        self.exit_price: Optional[float] = None

    def update_price(self, current_price: float):
        self.current_price = current_price
        if self.direction == 'UP':
            self.pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        elif self.direction in ('SELL_UP', 'SHORT'):
            self.pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
        else:  # DOWN
            self.pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        self.pnl_pusd = self.size_pusd * self.pnl_pct / 100

    def should_exit(self) -> Optional[str]:
        elapsed = time.time() - self.opened_at

        if self.hold_to_resolution:
            if self.pnl_pct <= -self.stop_loss_pct:
                return f'stop_loss_max ({self.pnl_pct:.1f}%, conviction={self.conviction_tier})'
            if elapsed > self.max_hold_seconds:
                return f'resolution_hold_complete ({elapsed:.0f}s)'
            return None

        if self.pnl_pct >= self.take_profit_pct:
            return f'profit_take ({self.pnl_pct:.1f}%, tp={self.take_profit_pct:.0f}%)'
        if self.pnl_pct <= -self.stop_loss_pct:
            return f'stop_loss ({self.pnl_pct:.1f}%, sl=-{self.stop_loss_pct:.0f}%)'
        if elapsed > self.max_hold_seconds:
            return f'timeout ({elapsed:.0f}s)'

        if self.conviction_tier == 'HIGH' and self.pnl_pct > 40:
            if self.pnl_pct < 10:
                return f'trailing_exit ({self.pnl_pct:.1f}%, was +40%+)'

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
            'conviction_tier': self.conviction_tier,
            'agreement_count': self.agreement_count,
            'hold_to_resolution': self.hold_to_resolution,
            'elapsed_sec': int(time.time() - self.opened_at),
            'status': self.status,
            'order_id': self.order_id,
            'exit_order_id': self.exit_order_id,
        }


class PendingOrder:
    """A live limit order sitting on the book, not yet filled."""

    def __init__(self, signal: TradeSignal, size_pusd: float, entry_price: float,
                 order_id: str, side: str, shares: float, neg_risk: bool = False):
        self.signal = signal
        self.size_pusd = size_pusd
        self.entry_price = entry_price
        self.order_id = order_id
        self.side = side
        self.shares = shares
        self.neg_risk = neg_risk
        self.placed_at = time.time()
        self.poll_count = 0

    def age(self) -> float:
        return time.time() - self.placed_at


class AutonomousExecutor:
    """Full-auto trade executor with pending-order tracking + real exit orders."""

    def __init__(self, risk_mgr, clob_client, log_callback: Callable = None,
                 balance_refresh_cb: Callable = None):
        self.risk_mgr = risk_mgr
        self.clob = clob_client
        self.log = log_callback or (lambda lvl, msg: None)
        # Optional callback invoked after fills / exits to re-read on-chain
        # balance. Dashboard wires this to clob.get_pusd_balance_onchain.
        self.balance_refresh_cb = balance_refresh_cb
        self.open_positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, PendingOrder] = {}   # order_id -> pending
        self.closed_trades: List[Position] = []
        self._dedup: Dict[str, float] = {}
        self.DEDUP_SECS = 15

    # ───── Balance refresh (wired from dashboard) ─────

    def _refresh_balance_sync(self, reason: str):
        """Invoke balance_refresh_cb if present. Swallow errors so trading
        is never blocked by a balance-read failure."""
        if not self.balance_refresh_cb:
            return
        try:
            new_balance = self.balance_refresh_cb()
            if new_balance is not None and new_balance >= 0:
                old = self.risk_mgr.balance
                # Keep peak_balance monotonic for drawdown calc
                self.risk_mgr.balance = new_balance
                self.risk_mgr.peak_balance = max(
                    self.risk_mgr.peak_balance, new_balance
                )
                self.log('INFO',
                         f"💰 Balance refresh ({reason}): "
                         f"{old:.2f} → {new_balance:.2f} pUSD")
        except Exception as e:
            self.log('DEBUG', f"Balance refresh skipped ({reason}): {e}")

    def is_dedup(self, signal: TradeSignal) -> bool:
        key = f"{signal.coin}_{signal.direction}_{signal.timeframe}_{signal.market_id}"
        now = time.time()
        if key in self._dedup and (now - self._dedup[key]) < self.DEDUP_SECS:
            return True
        self._dedup[key] = now
        return False

    # ───── Entry flow ─────

    def _should_use_fok(self, signal: TradeSignal) -> bool:
        """
        FOK is used when we have high conviction AND the strategy asks for
        taker-style immediate execution.

        - oracle_lead fires with order_type='taker' → speed matters, needs
          immediate fill at crossing price.
        - Any signal with conviction_tier HIGH or MAXIMUM where order_type
          is 'taker' also gets FOK.
        """
        if signal.order_type != 'taker':
            return False
        conv = signal.metadata.get('conviction_tier', 'SINGLE')
        if conv in ('HIGH', 'MAXIMUM'):
            return True
        # Oracle-lead is always time-sensitive regardless of agreement count
        if signal.strategy == 'oracle_lead':
            return True
        return False

    async def execute_signal(self, signal: TradeSignal) -> Optional[Position]:
        """
        Execute a trade signal. In LIVE mode, the returned value may be:
          - Position  — FOK path filled instantly, position open now
          - None      — GTC limit sitting on book (tracked in pending_orders),
                         or order was rejected, or risk blocked the trade.
        In PAPER mode always returns a Position (simulated instant fill).
        """
        if self.is_dedup(signal):
            return None

        agreement_count = signal.metadata.get('agreement_count', 1)
        conviction_tier = signal.metadata.get('conviction_tier', 'SINGLE')

        ok, reason = self.risk_mgr.validate_signal(
            signal.confidence, signal.direction,
            signal.coin, signal.market_id,
            agreement_count=agreement_count,
        )
        if not ok:
            self.log('RISK', f"⛔ BLOCKED: {signal.coin} {signal.direction} — {reason}")
            return None

        size_pusd = self.risk_mgr.calculate_position_size(
            signal.confidence, signal.strategy, signal.market_id,
            signal.order_type,
            agreement_count=agreement_count,
            conviction_tier=conviction_tier,
        )

        if size_pusd < Config.POLYMARKET_MIN_ORDER_SIZE:
            self.log('WARN', f"⚠️ Size {size_pusd:.2f} < min {Config.POLYMARKET_MIN_ORDER_SIZE} — skip")
            return None

        # Liquidity depth check — need enough to BOTH enter and exit
        # without excessive slippage. Required = 3x entry size on the buy
        # side, 2x on the sell side (we'll exit smaller amounts as price
        # moves). Skip the trade if either side is too thin.
        if signal.token_id and hasattr(self.clob, 'get_orderbook'):
            try:
                book = self.clob.get_orderbook(signal.token_id)
                if book and not book.get('_synthetic'):
                    side = 'BUY'
                    if signal.direction in ('SELL_UP', 'SHORT'):
                        side = 'SELL'
                    ask_depth = float(book.get('ask_depth', 0) or 0)
                    bid_depth = float(book.get('bid_depth', 0) or 0)
                    # Buy side (entry)
                    entry_depth = ask_depth if side == 'BUY' else bid_depth
                    # Exit side (opposite of entry)
                    exit_depth = bid_depth if side == 'BUY' else ask_depth

                    required_entry = size_pusd * 3
                    required_exit = size_pusd * 2

                    if entry_depth < required_entry:
                        self.log('LIQUIDITY',
                                 f"⚠️ Thin entry book: {signal.coin} {signal.direction} "
                                 f"depth=${entry_depth:.2f} < 3x size=${required_entry:.2f} — skip")
                        return None
                    if exit_depth < required_exit:
                        self.log('LIQUIDITY',
                                 f"⚠️ Thin EXIT book: {signal.coin} {signal.direction} "
                                 f"exit depth=${exit_depth:.2f} < 2x size=${required_exit:.2f} — skip "
                                 f"(can't exit cleanly)")
                        return None
            except Exception as e:
                self.log('DEBUG', f"Liquidity check skipped: {e}")

        entry_price = signal.limit_price or signal.entry_price

        tier = self.risk_mgr.get_tier()
        use_fok = self._should_use_fok(signal)
        order_label = "FOK" if use_fok else ("LIMIT" if signal.order_type == 'maker' else "MKT")

        self.log('TRADE', f"🎯 ENTRY [{tier.emoji}{tier.name}] {signal.coin} {signal.direction} "
                         f"[{conviction_tier}] "
                         f"size={size_pusd:.2f}pUSD @ {entry_price:.3f} "
                         f"({order_label}) conf={signal.confidence:.0%} "
                         f"agree={agreement_count} | {signal.strategy}")
        self.log('TRADE', f"   Reason: {signal.rationale[:140]}")

        # PAPER MODE: simulate instant fill, create position immediately
        if Config.is_paper():
            self.log('PAPER', f"   📋 PAPER execution (simulated fill)")
            order_id = f"paper-{uuid.uuid4().hex[:8]}"
            position = Position(signal, size_pusd, entry_price, order_id)
            self.open_positions[position.id] = position
            self.risk_mgr.register_position(signal.market_id, size_pusd)
            self.log('TRADE', f"   ✅ [PAPER] Position opened: {position.id} "
                             f"TP=+{position.take_profit_pct:.0f}% "
                             f"SL=-{position.stop_loss_pct:.0f}% "
                             f"[{position.conviction_tier}] "
                             f"{'🔒HOLD TO RESOLUTION' if position.hold_to_resolution else ''}")
            return position

        # LIVE MODE
        if not self.clob.is_initialized():
            self.log('ERROR', f"   ❌ Live mode but CLOB not initialized")
            return None

        side = 'BUY'
        if signal.direction in ('SELL_UP', 'SHORT'):
            side = 'SELL'

        # ── Place the actual order ──
        if use_fok:
            # For FOK, push the limit one tick in our favor to maximize fill
            # probability while still capping slippage at the specified price.
            fok_price = round(min(0.99, max(0.01, entry_price + 0.01)), 2)
            self.log('TRADE', f"   📤 FOK {side} @ {fok_price:.3f}")
            result = self.clob.place_fok_order(
                token_id=signal.token_id, side=side,
                price=fok_price, size_pusd=size_pusd,
            )
        elif signal.order_type == 'maker' and signal.limit_price:
            self.log('TRADE', f"   📤 LIMIT {side} @ {signal.limit_price:.3f} GTC")
            result = self.clob.place_limit_order(
                token_id=signal.token_id, side=side,
                price=signal.limit_price, size_pusd=size_pusd,
                expiration='GTC',
            )
        else:
            self.log('TRADE', f"   📤 MARKET {side} (FOK fallback)")
            result = self.clob.place_market_order(
                token_id=signal.token_id, side=side,
                size_pusd=size_pusd, price=signal.entry_price,
            )

        if not result:
            self.log('ERROR', f"   ❌ Order placement FAILED")
            return None

        order_id = result.get('order_id', 'unknown')
        status = (result.get('status') or 'UNKNOWN').upper()
        shares = float(result.get('size', 0) or 0)
        self.log('TRADE', f"   📨 Order placed: id={order_id} status={status}")

        # Classify placement outcome
        if status == 'MATCHED':
            # Fully filled synchronously — promote to Position immediately.
            fill_price = self.clob.get_fill_price(order_id, fallback=entry_price)
            position = Position(signal, size_pusd, fill_price, order_id,
                                shares_filled=shares)
            self.open_positions[position.id] = position
            self.risk_mgr.register_position(signal.market_id, size_pusd)
            self.log('TRADE', f"   ✅ FILLED immediately: {position.id} @ {fill_price:.3f} "
                             f"TP=+{position.take_profit_pct:.0f}% "
                             f"SL=-{position.stop_loss_pct:.0f}%")
            self._refresh_balance_sync("entry_fill")
            return position

        if status in ('LIVE', 'DELAYED'):
            # On the book, not yet filled. Track as pending.
            pending = PendingOrder(
                signal=signal, size_pusd=size_pusd, entry_price=entry_price,
                order_id=order_id, side=side, shares=shares,
            )
            self.pending_orders[order_id] = pending
            self.log('TRADE', f"   ⏳ Order on book (not filled): {order_id} — "
                             f"tracking for up to {PENDING_ORDER_TIMEOUT:.0f}s")
            return None

        # UNMATCHED / CANCELED / REJECTED — terminal non-fill
        self.log('WARN', f"   ⚠️ Order did not fill: status={status}. Skipping.")
        return None

    # ───── Pending-order polling ─────

    async def monitor_pending_orders(self) -> int:
        """
        Poll each pending order. Promote filled ones to Positions. Cancel
        stale ones past the timeout. Called from the main scan loop.
        Returns number of orders resolved (filled + canceled).
        """
        if not self.pending_orders:
            return 0

        resolved = 0
        for order_id, pending in list(self.pending_orders.items()):
            try:
                pending.poll_count += 1
                filled, raw = self.clob.is_order_filled(order_id)

                if filled is True:
                    # Promote to Position
                    fill_price = self.clob.get_fill_price(
                        order_id, fallback=pending.entry_price
                    )
                    # Get actual filled size
                    try:
                        size_matched = float((raw or {}).get('size_matched', 0) or 0)
                    except (ValueError, TypeError):
                        size_matched = pending.shares

                    position = Position(
                        pending.signal, pending.size_pusd, fill_price,
                        order_id, shares_filled=size_matched or pending.shares,
                    )
                    self.open_positions[position.id] = position
                    self.risk_mgr.register_position(
                        pending.signal.market_id, pending.size_pusd
                    )
                    self.log('TRADE',
                             f"✅ FILL: {pending.signal.coin} {pending.signal.direction} "
                             f"@ {fill_price:.3f} (waited {pending.age():.1f}s, "
                             f"id={order_id[:10]})")
                    del self.pending_orders[order_id]
                    resolved += 1
                    self._refresh_balance_sync("pending_fill")
                    continue

                if filled is None:
                    # Terminal non-fill (CANCELED / UNMATCHED / REJECTED / NOT_FOUND)
                    # NOT_FOUND is ambiguous: sometimes it means the order was
                    # instantly matched and pruned before we polled. Check
                    # trades to disambiguate.
                    status = (raw or {}).get('status', 'UNKNOWN')
                    if status == 'NOT_FOUND':
                        trades = self.clob.get_trades_for_order(order_id)
                        if trades:
                            # It WAS filled, CLOB just pruned it — recover.
                            fill_price = self.clob.get_fill_price(
                                order_id, fallback=pending.entry_price
                            )
                            position = Position(
                                pending.signal, pending.size_pusd, fill_price,
                                order_id, shares_filled=pending.shares,
                            )
                            self.open_positions[position.id] = position
                            self.risk_mgr.register_position(
                                pending.signal.market_id, pending.size_pusd
                            )
                            self.log('TRADE',
                                     f"✅ FILL (recovered from trades): "
                                     f"{pending.signal.coin} @ {fill_price:.3f} "
                                     f"id={order_id[:10]}")
                            del self.pending_orders[order_id]
                            resolved += 1
                            self._refresh_balance_sync("pending_fill_recovered")
                            continue

                    self.log('WARN',
                             f"⚠️ Pending order {order_id[:10]} terminal "
                             f"status={status} — dropping "
                             f"(was {pending.signal.coin} {pending.signal.direction})")
                    del self.pending_orders[order_id]
                    resolved += 1
                    continue

                # Still pending. Cancel if past timeout.
                if pending.age() > PENDING_ORDER_TIMEOUT:
                    self.log('WARN',
                             f"⏰ Pending order {order_id[:10]} timed out "
                             f"after {pending.age():.1f}s — canceling "
                             f"({pending.signal.coin} {pending.signal.direction})")
                    try:
                        self.clob.cancel_order(order_id)
                    except Exception as e:
                        self.log('DEBUG', f"Cancel error (non-fatal): {e}")
                    del self.pending_orders[order_id]
                    resolved += 1

            except Exception as e:
                self.log('DEBUG', f"Pending poll error for {order_id[:10]}: {e}")
                # Don't remove on transient errors — try again next scan.
                continue

        return resolved

    # ───── Exit flow ─────

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

    async def _place_exit_order(self, pos: Position) -> Optional[Dict]:
        """
        Place an actual SELL order on the CLOB to close the position.

        Uses a MULTI-TIER FALLBACK CASCADE:
          1. FOK at best bid (aggressive, likely to fill immediately)
          2. FOK at best bid - 1 tick (price dropped, cross further)
          3. FAK (fill-any-kill) at best bid - 2 ticks (accept partial)
          4. GTC at best bid - 3 ticks (sit on book, best we can do)

        Each attempt uses the exact share count we own (NEVER size_pusd,
        which rounds UP and triggers "not enough balance" errors when the
        computed size exceeds the position's actual share count).

        We also re-read the orderbook before each tier so exits adapt to
        price movement during cascade.
        """
        if not self.clob.is_initialized():
            return None
        if pos.shares <= 0:
            self.log('ERROR', f"   ❌ Position has zero shares, nothing to sell")
            return None

        # Truncate to 2 decimals — CLOB uses cent-shares. Never round up
        # on exit or we'll request more shares than we own.
        owned_shares = (int(pos.shares * 100)) / 100.0
        if owned_shares <= 0:
            self.log('ERROR', f"   ❌ Owned shares rounds to 0 ({pos.shares})")
            return None

        # Pull fresh orderbook for best bid
        try:
            book = self.clob.get_orderbook(pos.token_id)
        except Exception:
            book = None

        best_bid = (book or {}).get('best_bid') or max(0.01, pos.current_price - 0.02)

        # Cascade of (order_type, price_offset_ticks, label) tuples.
        # Each successive tier crosses deeper into the book.
        cascade = [
            ('FOK', 0,  'tier1_fok_best_bid'),
            ('FOK', -1, 'tier2_fok_1tick_below'),
            ('FAK', -2, 'tier3_fak_2tick_below'),
            ('GTC', -3, 'tier4_gtc_3tick_below'),
        ]

        last_error = None
        for order_type, offset, label in cascade:
            # Refresh book each retry (price can move during cascade)
            if offset != 0:
                try:
                    book = self.clob.get_orderbook(pos.token_id)
                    best_bid = (book or {}).get('best_bid') or best_bid
                except Exception:
                    pass

            price = round(max(0.01, min(0.99, best_bid + offset * 0.01)), 2)

            # Liquidity sanity: if there's literally no bid depth at this
            # price, skip this tier. (Dashboard logs the issue.)
            if book:
                try:
                    bid_depth = float(book.get('bid_depth') or 0)
                    if bid_depth < 1.0 and order_type == 'FOK':
                        self.log('LIQUIDITY',
                                 f"   ⚠️ {label}: bid depth ${bid_depth:.2f} too thin for FOK")
                        continue
                except Exception:
                    pass

            self.log('TRADE',
                     f"   📤 EXIT [{label}] {order_type} SELL {owned_shares:.2f}sh "
                     f"@ {price:.3f} (best_bid={best_bid:.3f})")
            try:
                result = self.clob.place_sell_shares(
                    token_id=pos.token_id,
                    shares=owned_shares,
                    price=price,
                    order_type=order_type,
                )
            except Exception as e:
                last_error = str(e)
                self.log('WARN', f"   ⚠️ {label} exception: {e}")
                continue

            if not result:
                self.log('WARN', f"   ⚠️ {label} returned no result, trying next tier")
                continue

            status = (result.get('status') or 'UNKNOWN').upper()
            if status == 'MATCHED':
                self.log('TRADE', f"   ✅ Exit filled via {label}")
                result['_cascade_label'] = label
                return result

            # FAK may partial-fill. Check via trades.
            if order_type == 'FAK' or status in ('DELAYED', 'LIVE'):
                await asyncio.sleep(0.3)
                trades = self.clob.get_trades_for_order(result.get('order_id', ''))
                if trades:
                    self.log('TRADE',
                             f"   ✅ Exit partial-filled via {label} (trades={len(trades)})")
                    result['_cascade_label'] = label
                    return result
                # GTC that's still LIVE — position is on the book; accept
                # this result even though unfilled. It will resolve later.
                if order_type == 'GTC' and status == 'LIVE':
                    self.log('WARN',
                             f"   ⚠️ {label} sitting unfilled — will resolve via market settlement")
                    result['_cascade_label'] = label
                    return result

            self.log('WARN', f"   ⚠️ {label} status={status}, trying next tier")

        self.log('ERROR',
                 f"   ❌ All exit tiers failed. Position will rely on market resolution. "
                 f"last_error={last_error}")
        return None

    async def _close_position(self, pid: str, reason: str):
        pos = self.open_positions.pop(pid, None)
        if not pos:
            return

        # In LIVE mode, actually place a SELL order before booking PnL.
        # If the exit fails, re-insert the position so monitor_positions()
        # can retry on the next scan (instead of silently losing it).
        exit_fill_price = pos.current_price
        exit_filled = False
        if not Config.is_paper():
            self.log('TRADE',
                     f"🔚 Closing LIVE {pos.coin} {pos.direction} — reason={reason}")
            exit_result = await self._place_exit_order(pos)
            if exit_result:
                pos.exit_order_id = exit_result.get('order_id')
                status = (exit_result.get('status') or 'UNKNOWN').upper()
                label = exit_result.get('_cascade_label', 'cascade')
                if status == 'MATCHED':
                    actual = self.clob.get_fill_price(
                        pos.exit_order_id, fallback=pos.current_price
                    )
                    exit_fill_price = actual
                    exit_filled = True
                    self.log('TRADE',
                             f"   ✅ Exit FILLED @ {actual:.3f} via {label} "
                             f"(id={pos.exit_order_id})")
                else:
                    # LIVE / DELAYED / partial — poll trades
                    await asyncio.sleep(0.5)
                    trades = self.clob.get_trades_for_order(pos.exit_order_id)
                    if trades:
                        exit_fill_price = self.clob.get_fill_price(
                            pos.exit_order_id, fallback=pos.current_price
                        )
                        exit_filled = True
                        self.log('TRADE',
                                 f"   ✅ Exit filled (from trades) @ {exit_fill_price:.3f} "
                                 f"via {label}")
                    else:
                        # Unfilled but sitting on book (GTC fallback). Keep
                        # the position open-ish — let next scan re-evaluate.
                        self.log('WARN',
                                 f"   ⚠️ Exit {label} still unfilled — re-queuing position")
                        pos.status = 'closing'
                        self.open_positions[pid] = pos
                        return
            else:
                # All cascade tiers failed. Re-queue the position so next
                # scan will retry. We keep it in open_positions so TP/SL
                # logic continues to monitor it.
                self.log('ERROR',
                         f"   ❌ All exit tiers failed — re-queuing position for retry next scan")
                pos.status = 'exit_failed'
                self.open_positions[pid] = pos
                return

        # Recompute PnL at the actual exit price
        pos.update_price(exit_fill_price)
        pos.exit_price = exit_fill_price

        won = pos.pnl_pusd > 0
        pos.status = 'closed_' + reason.split(' ')[0]

        self.risk_mgr.record_trade_result(pos.pnl_pusd, won, pos.market_id)
        self.risk_mgr.close_position(pos.market_id)

        self.closed_trades.append(pos)
        if len(self.closed_trades) > 200:
            self.closed_trades = self.closed_trades[-200:]

        emoji = '✅' if won else '❌'
        self.log('TRADE',
                 f"{emoji} EXIT: {pos.coin} {pos.direction} "
                 f"PnL={pos.pnl_pusd:+.2f}pUSD ({pos.pnl_pct:+.1f}%) "
                 f"exit={exit_fill_price:.3f} reason={reason} strat={pos.strategy}")

        self._refresh_balance_sync("exit_fill")

    # ───── Snapshots ─────

    def get_positions_snapshot(self) -> List[dict]:
        return [p.to_dict() for p in self.open_positions.values()]

    def get_closed_snapshot(self, limit: int = 20) -> List[dict]:
        return [p.to_dict() for p in self.closed_trades[-limit:][::-1]]

    def get_pending_snapshot(self) -> List[dict]:
        """Pending orders (on book, not yet filled) for dashboard visibility."""
        out = []
        for oid, po in self.pending_orders.items():
            out.append({
                'order_id': oid,
                'coin': po.signal.coin,
                'direction': po.signal.direction,
                'side': po.side,
                'size_pusd': po.size_pusd,
                'entry_price': po.entry_price,
                'shares': po.shares,
                'age_sec': int(po.age()),
                'strategy': po.signal.strategy,
            })
        return out
