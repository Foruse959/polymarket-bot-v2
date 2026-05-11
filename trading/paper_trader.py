"""
Paper Trader — Simulation with USDC and Maker Orders

Simulates trading with:
- USDC amounts
- Maker/taker fee structure
- Slippage modeling
- Limit order fill simulation
"""

import uuid
import random
from typing import Dict, List, Optional
from datetime import datetime

from config import Config
from trading.live_balance_manager import LiveBalanceManager
from data.database import Database
from strategies.base_strategy import TradeSignal


class PaperTrader:
    """Paper trading with USDC and maker order simulation."""

    def __init__(self, db: Database, balance_mgr: LiveBalanceManager):
        self.db = db
        self.balance_mgr = balance_mgr
        self.positions: Dict[str, Dict] = {}
        self.pending_orders: Dict[str, Dict] = {}  # Simulated limit orders
        self.trade_history: List[Dict] = []
        self.total_trades = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl_usdc = 0.0

    async def execute_signal(self, signal: TradeSignal) -> Optional[Dict]:
        """Execute a trade signal (paper)."""
        allowed, reason = self.balance_mgr.can_trade(signal.confidence, signal.order_type)
        if not allowed:
            return None

        size_usdc = self.balance_mgr.calculate_position_size_usdc(
            signal.timeframe, signal.confidence, signal.order_type
        )
        
        if size_usdc < Config.POLYMARKET_MIN_ORDER_SIZE_USDC:
            return None

        # Simulate slippage (taker only, maker gets price improvement)
        if signal.order_type == 'taker':
            slippage = random.uniform(-0.005, 0.015)
            fill_price = signal.entry_price * (1 + slippage)
        else:
            # Maker: assume limit price or slight improvement
            if signal.limit_price:
                fill_price = signal.limit_price
            else:
                fill_price = signal.entry_price * random.uniform(0.998, 1.0)

        # Calculate shares
        shares = size_usdc / fill_price if fill_price > 0 else 0

        trade_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        trade = {
            'id': trade_id,
            'market_id': signal.market_id,
            'coin': signal.coin,
            'timeframe': signal.timeframe,
            'strategy': signal.strategy,
            'direction': signal.direction,
            'token_id': signal.token_id,
            'entry_price': fill_price,
            'exit_price': None,
            'size_usdc': size_usdc,
            'shares': shares,
            'pnl_usdc': None,
            'pnl_pct': None,
            'confidence': signal.confidence,
            'entry_time': now,
            'exit_time': None,
            'exit_reason': None,
            'status': 'open',
            'order_type': signal.order_type,
            'limit_price': signal.limit_price,
            'rationale': signal.rationale,
            'metadata': signal.metadata,
        }

        self.positions[trade_id] = trade
        self.balance_mgr.open_positions += 1
        self.total_trades += 1

        await self.db.save_trade(trade)

        order_type_emoji = '📝' if signal.order_type == 'maker' else '⚡'
        print(f"{order_type_emoji} PAPER BUY: {signal.coin} {signal.direction} "
              f"at {fill_price:.3f} ({signal.order_type}) "
              f"size: {Config.format_usdc(size_usdc)}", flush=True)

        return trade

    async def check_positions(self, current_prices: Dict[str, float],
                              seconds_remaining_map: Dict[str, int] = None) -> List[Dict]:
        """Check positions and close if conditions met."""
        closed = []
        seconds_remaining_map = seconds_remaining_map or {}

        for trade_id, pos in list(self.positions.items()):
            token_id = pos['token_id']
            current_price = current_prices.get(token_id)
            
            if current_price is None:
                continue

            # Get time remaining
            secs = seconds_remaining_map.get(pos.get('market_id', ''), 999)
            
            # Calculate unrealized P&L
            entry = pos['entry_price']
            shares = pos.get('shares', 0)
            
            if pos['direction'] in ['SELL_UP', 'SHORT']:
                # Short position
                unrealized = (entry - current_price) * shares
                pnl_pct = (entry - current_price) / entry * 100
            else:
                # Long position
                unrealized = (current_price - entry) * shares
                pnl_pct = (current_price - entry) / entry * 100

            # Check exit conditions
            exit_reason = None
            
            # Take profit
            if pnl_pct >= 10:
                exit_reason = 'profit_take'
            # Stop loss
            elif pnl_pct <= -15:
                exit_reason = 'stop_loss'
            # Time-based exit near expiry
            elif secs < 30 and pnl_pct > 0:
                exit_reason = 'time_exit'
            
            if exit_reason:
                await self._close_position(trade_id, current_price, unrealized, exit_reason)
                closed.append(pos)
            else:
                # Update position in DB
                await self.db.update_position_price(trade_id, current_price, unrealized)

        return closed

    async def close_at_settlement(self, token_id: str, final_price: float):
        """Close all positions for a settled market."""
        closed = []
        for trade_id, pos in list(self.positions.items()):
            if pos['token_id'] == token_id:
                entry = pos['entry_price']
                shares = pos.get('shares', 0)
                
                if pos['direction'] in ['SELL_UP', 'SHORT']:
                    pnl = (entry - final_price) * shares
                else:
                    pnl = (final_price - entry) * shares
                
                await self._close_position(trade_id, final_price, pnl, 'settlement')
                closed.append(pos)
        return closed

    async def _close_position(self, trade_id: str, exit_price: float, 
                              pnl_usdc: float, reason: str):
        """Close a position."""
        pos = self.positions.pop(trade_id, None)
        if not pos:
            return

        # Calculate fees
        entry_p = max(0.001, min(0.999, pos['entry_price']))
        exit_p = max(0.001, min(0.999, exit_price))
        
        if pos.get('order_type') == 'maker':
            # Maker: 0% fee, earn spread (simplified as small bonus)
            fee_usdc = 0
            pnl_usdc += pos['size_usdc'] * 0.001  # Simulated spread capture
        else:
            # Taker: dynamic fee
            entry_fee = pos['size_usdc'] * 0.25 * entry_p * (1 - entry_p) ** 2
            exit_size = pos['size_usdc'] + pnl_usdc
            exit_fee = abs(exit_size) * 0.25 * exit_p * (1 - exit_p) ** 2
            fee_usdc = entry_fee + exit_fee
        
        pnl_usdc -= fee_usdc
        pnl_pct = (pnl_usdc / pos['size_usdc'] * 100) if pos['size_usdc'] > 0 else 0

        # Update stats
        self.balance_mgr.open_positions -= 1
        self.total_pnl_usdc += pnl_usdc
        
        won = pnl_usdc > 0
        if won:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        self.balance_mgr.record_trade_result(pnl_usdc, won)
        
        # Update balance
        new_balance = self.balance_mgr.balance_usdc + pnl_usdc
        self.balance_mgr.update_balance(new_balance)

        # Update trade in DB
        await self.db.close_trade(trade_id, exit_price, pnl_usdc, reason)
        await self.db.update_strategy_stats(pos['strategy'], pnl_usdc, won, pos.get('order_type', 'maker'))
        await self.db.update_daily_pnl(pnl_usdc, won)

        # Store in history
        pos['exit_price'] = exit_price
        pos['pnl_usdc'] = pnl_usdc
        pos['pnl_pct'] = pnl_pct
        pos['exit_time'] = datetime.now().isoformat()
        pos['exit_reason'] = reason
        pos['status'] = 'closed'
        self.trade_history.append(pos)

        emoji = '✅' if won else '❌'
        print(f"{emoji} PAPER CLOSE: {pos['coin']} {pos['direction']} "
              f"PnL: {pnl_usdc:+.2f} USDC ({pnl_pct:+.1f}%) | {reason}", flush=True)

    def get_stats(self) -> Dict:
        """Get paper trading stats."""
        win_rate = self.win_count / (self.win_count + self.loss_count) * 100 if (self.win_count + self.loss_count) > 0 else 0
        return {
            'total_trades': self.total_trades,
            'open_positions': len(self.positions),
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': win_rate,
            'total_pnl_usdc': self.total_pnl_usdc,
            'balance_usdc': self.balance_mgr.balance_usdc,
        }
