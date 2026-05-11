"""
Live Trader — Real CLOB Order Execution (v0.34.6, USDC)

Uses py-clob-client v0.34.6 to place real orders on Polymarket.
- Maker-first (limit orders preferred)
- USDC for all amounts
- Dynamic spread management
"""

import uuid
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from config import Config
from trading.live_balance_manager import LiveBalanceManager
from data.database import Database
from strategies.base_strategy import TradeSignal


class LiveTrader:
    """Real order execution on Polymarket CLOB with maker preference."""

    ORDER_TIMEOUT = 60
    BASE_TAKER_FEE_RATE = 0.03125

    def __init__(self, db: Database, balance_mgr: LiveBalanceManager):
        self.db = db
        self.balance_mgr = balance_mgr
        self.positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        self.clob_client = None
        self._initialized = False
        self._consecutive_failures = 0
        self._trading_paused = False
        self._init_error = ''
        self._stop_loss_cooldowns: Dict[str, float] = {}
        self.STOP_LOSS_COOLDOWN_SECS = 60
        self._signal_dedup: Dict[str, float] = {}
        self.SIGNAL_DEDUP_SECS = 10

    async def init(self, clob_client) -> bool:
        """Initialize with CLOB client."""
        self.clob_client = clob_client
        
        if not Config.is_live_ready():
            self._init_error = 'POLY_PRIVATE_KEY not set'
            return False

        try:
            # Initialize py-clob-client
            private_key = Config.POLY_PRIVATE_KEY.strip()
            funder = Config.get_funder_address() or None
            sig_type = Config.POLY_SIGNATURE_TYPE
            
            py_client = self.clob_client.init_py_clob_client(private_key, funder, sig_type)
            
            if py_client:
                self._initialized = True
                print("✅ Live trader initialized", flush=True)
                return True
            else:
                self._init_error = 'Failed to initialize py-clob-client'
                return False
                
        except Exception as e:
            self._init_error = str(e)
            print(f"❌ Live trader init failed: {e}", flush=True)
            return False

    async def execute_signal(self, signal: TradeSignal) -> Optional[Dict]:
        """Execute a trade signal with maker preference."""
        if not self._initialized or not self.clob_client:
            return None

        if self._trading_paused:
            return None

        # Risk check
        allowed, reason = self.balance_mgr.can_trade(signal.confidence, signal.order_type)
        if not allowed:
            return None

        # Signal dedup
        dedup_key = f"{signal.coin}_{signal.direction}_{signal.strategy}"
        now = datetime.now().timestamp()
        if dedup_key in self._signal_dedup:
            if now - self._signal_dedup[dedup_key] < self.SIGNAL_DEDUP_SECS:
                return None
        self._signal_dedup[dedup_key] = now

        # Calculate size
        size_usdc = self.balance_mgr.calculate_position_size_usdc(
            signal.timeframe, signal.confidence, signal.order_type
        )
        
        if size_usdc < Config.POLYMARKET_MIN_ORDER_SIZE_USDC:
            return None

        # Determine order side
        side = 'BUY' if signal.direction in ['UP', 'DOWN'] and not signal.direction.startswith('SELL') else 'SELL'
        
        # Place order
        order_result = None
        
        if signal.order_type == 'maker' and signal.limit_price:
            # Place limit order
            order_result = self.clob_client.place_limit_order(
                token_id=signal.token_id,
                side=side,
                price=signal.limit_price,
                size_usdc=size_usdc,
            )
        else:
            # Fall back to market order
            order_result = self.clob_client.place_market_order(
                token_id=signal.token_id,
                side=side,
                size_usdc=size_usdc,
            )

        if not order_result:
            self._consecutive_failures += 1
            return None

        self._consecutive_failures = 0

        # Record trade
        trade_id = str(uuid.uuid4())[:8]
        now_iso = datetime.now().isoformat()

        trade = {
            'id': trade_id,
            'market_id': signal.market_id,
            'coin': signal.coin,
            'timeframe': signal.timeframe,
            'strategy': signal.strategy,
            'direction': signal.direction,
            'token_id': signal.token_id,
            'entry_price': signal.limit_price or signal.entry_price,
            'size_usdc': size_usdc,
            'order_id': order_result.get('order_id'),
            'order_type': signal.order_type,
            'entry_time': now_iso,
            'status': 'open',
            'rationale': signal.rationale,
            'metadata': signal.metadata,
        }

        self.positions[trade_id] = trade
        self.balance_mgr.open_positions += 1

        await self.db.save_trade(trade)
        await self.db.save_order({
            'id': str(uuid.uuid4())[:8],
            'trade_id': trade_id,
            'market_id': signal.market_id,
            'token_id': signal.token_id,
            'order_type': signal.order_type,
            'side': side,
            'price': signal.limit_price or signal.entry_price,
            'size_usdc': size_usdc,
            'status': 'open',
            'created_at': now_iso,
            'clob_order_id': order_result.get('order_id'),
        })

        order_emoji = '📝' if signal.order_type == 'maker' else '⚡'
        print(f"{order_emoji} LIVE {signal.order_type.upper()}: {signal.coin} {signal.direction} "
              f"size: {Config.format_usdc(size_usdc)} | order: {order_result.get('order_id', 'N/A')[:8]}", flush=True)

        return trade

    async def check_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        """Check positions and handle exits."""
        closed = []
        
        for trade_id, pos in list(self.positions.items()):
            current_price = current_prices.get(pos['token_id'])
            if current_price is None:
                continue

            entry = pos['entry_price']
            
            # Calculate P&L
            if pos['direction'] in ['SELL_UP', 'SHORT']:
                pnl_usdc = (entry - current_price) * pos['size_usdc'] / entry
                pnl_pct = (entry - current_price) / entry * 100
            else:
                pnl_usdc = (current_price - entry) * pos['size_usdc'] / entry
                pnl_pct = (current_price - entry) / entry * 100

            # Exit logic
            exit_reason = None
            
            if pnl_pct >= 15:
                exit_reason = 'profit_take'
            elif pnl_pct <= -12:
                exit_reason = 'stop_loss'

            if exit_reason:
                await self._close_position(trade_id, current_price, pnl_usdc, exit_reason)
                closed.append(pos)

        return closed

    async def _close_position(self, trade_id: str, exit_price: float, 
                              pnl_usdc: float, reason: str):
        """Close a position."""
        pos = self.positions.pop(trade_id, None)
        if not pos:
            return

        # Calculate final fees
        if pos.get('order_type') == 'maker':
            fee_usdc = 0  # Maker pays no fees
        else:
            # Taker fee
            exit_p = max(0.001, min(0.999, exit_price))
            fee_usdc = abs(pos['size_usdc'] + pnl_usdc) * 0.25 * exit_p * (1 - exit_p) ** 2

        pnl_usdc -= fee_usdc
        
        won = pnl_usdc > 0
        
        # Update balance manager
        self.balance_mgr.open_positions -= 1
        self.balance_mgr.record_trade_result(pnl_usdc, won)
        
        new_balance = self.balance_mgr.balance_usdc + pnl_usdc
        self.balance_mgr.update_balance(new_balance)

        # Update database
        await self.db.close_trade(trade_id, exit_price, pnl_usdc, reason)
        await self.db.update_strategy_stats(pos['strategy'], pnl_usdc, won, pos.get('order_type', 'maker'))
        await self.db.update_daily_pnl(pnl_usdc, won)

        pos['exit_price'] = exit_price
        pos['pnl_usdc'] = pnl_usdc
        pos['exit_time'] = datetime.now().isoformat()
        pos['exit_reason'] = reason
        pos['status'] = 'closed'
        self.trade_history.append(pos)

        emoji = '✅' if won else '❌'
        print(f"{emoji} LIVE CLOSE: {pos['coin']} {pos['direction']} "
              f"PnL: {pnl_usdc:+.2f} USDC | {reason}", flush=True)

    def is_initialized(self) -> bool:
        return self._initialized

    def get_init_error(self) -> str:
        return self._init_error
