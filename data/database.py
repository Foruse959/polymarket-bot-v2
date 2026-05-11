"""
Database — Trade Storage (SQLite)

Stores trades, positions, strategy stats, and P&L history.
Updated for v2 with USDC and maker order tracking.
"""

import os
import json
import aiosqlite
from typing import Dict, List, Optional
from datetime import datetime

from config import Config


class Database:
    """Async SQLite database for trade management."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)

    async def init(self):
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    market_id TEXT,
                    coin TEXT,
                    timeframe INTEGER,
                    strategy TEXT,
                    direction TEXT,
                    token_id TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    size_usdc REAL,
                    pnl_usdc REAL,
                    pnl_pct REAL,
                    confidence REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    exit_reason TEXT,
                    status TEXT DEFAULT 'open',
                    order_type TEXT DEFAULT 'maker',
                    order_id TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    trade_id TEXT,
                    market_id TEXT,
                    coin TEXT,
                    timeframe INTEGER,
                    strategy TEXT,
                    direction TEXT,
                    token_id TEXT,
                    entry_price REAL,
                    current_price REAL,
                    target_price REAL,
                    stop_loss_price REAL,
                    size_usdc REAL,
                    unrealized_pnl_usdc REAL,
                    entry_time TEXT,
                    status TEXT DEFAULT 'open',
                    order_type TEXT DEFAULT 'maker',
                    order_id TEXT
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    trade_id TEXT,
                    market_id TEXT,
                    token_id TEXT,
                    order_type TEXT,
                    side TEXT,
                    price REAL,
                    size_usdc REAL,
                    status TEXT,
                    created_at TEXT,
                    filled_at TEXT,
                    cancelled_at TEXT,
                    clob_order_id TEXT
                );

                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl_usdc REAL DEFAULT 0,
                    avg_win_usdc REAL DEFAULT 0,
                    avg_loss_usdc REAL DEFAULT 0,
                    maker_trades INTEGER DEFAULT 0,
                    taker_trades INTEGER DEFAULT 0,
                    last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date TEXT PRIMARY KEY,
                    starting_balance_usdc REAL,
                    ending_balance_usdc REAL,
                    total_trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    gross_profit_usdc REAL,
                    gross_loss_usdc REAL,
                    net_pnl_usdc REAL
                );

                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin);
                CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
                CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(trade_id);
            """)
            await db.commit()
        print("[OK] Database initialized")

    async def save_trade(self, trade: Dict):
        """Save or update a trade."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO trades
                (id, market_id, coin, timeframe, strategy, direction, token_id,
                 entry_price, exit_price, size_usdc, pnl_usdc, pnl_pct, confidence,
                 entry_time, exit_time, exit_reason, status, order_type, order_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['id'], trade.get('market_id', ''), trade.get('coin', ''),
                trade.get('timeframe', 0), trade.get('strategy', ''),
                trade.get('direction', ''), trade.get('token_id', ''),
                trade.get('entry_price', 0), trade.get('exit_price'),
                trade.get('size_usdc', 0), trade.get('pnl_usdc'),
                trade.get('pnl_pct'), trade.get('confidence', 0),
                trade.get('entry_time', ''), trade.get('exit_time'),
                trade.get('exit_reason'), trade.get('status', 'open'),
                trade.get('order_type', 'maker'),
                trade.get('order_id'),
                json.dumps(trade.get('metadata', {})),
            ))
            await db.commit()

    async def save_position(self, position: Dict):
        """Save or update a position."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO positions
                (id, trade_id, market_id, coin, timeframe, strategy, direction,
                 token_id, entry_price, current_price, target_price, stop_loss_price,
                 size_usdc, unrealized_pnl_usdc, entry_time, status, order_type, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position['id'], position.get('trade_id', position['id']),
                position.get('market_id', ''), position.get('coin', ''),
                position.get('timeframe', 0), position.get('strategy', ''),
                position.get('direction', ''), position.get('token_id', ''),
                position.get('entry_price', 0), position.get('current_price', 0),
                position.get('target_price', 0), position.get('stop_loss_price', 0),
                position.get('size_usdc', 0), position.get('unrealized_pnl_usdc', 0),
                position.get('entry_time', ''), position.get('status', 'open'),
                position.get('order_type', 'maker'),
                position.get('order_id'),
            ))
            await db.commit()

    async def save_order(self, order: Dict):
        """Save an order."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO orders
                (id, trade_id, market_id, token_id, order_type, side, price, 
                 size_usdc, status, created_at, filled_at, cancelled_at, clob_order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order['id'], order.get('trade_id'), order.get('market_id'),
                order.get('token_id'), order.get('order_type'),
                order.get('side'), order.get('price'), order.get('size_usdc'),
                order.get('status'), order.get('created_at'),
                order.get('filled_at'), order.get('cancelled_at'),
                order.get('clob_order_id'),
            ))
            await db.commit()

    async def close_trade(self, trade_id: str, exit_price: float, pnl_usdc: float, reason: str):
        """Mark a trade as closed."""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE trades SET exit_price=?, pnl_usdc=?, exit_time=?, exit_reason=?, status='closed'
                WHERE id=?
            """, (exit_price, pnl_usdc, now, reason, trade_id))
            await db.execute("DELETE FROM positions WHERE id=?", (trade_id,))
            await db.commit()

    async def update_position_price(self, trade_id: str, current_price: float, unrealized_pnl: float):
        """Update position mark price."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE positions SET current_price=?, unrealized_pnl_usdc=? WHERE id=?
            """, (current_price, unrealized_pnl, trade_id))
            await db.commit()

    async def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM positions WHERE status='open'") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_open_trades(self) -> List[Dict]:
        """Get all open trades."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM trades WHERE status='open'") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """Get closed trade history."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM trades WHERE status='closed' ORDER BY exit_time DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_strategy_stats(self) -> Dict[str, Dict]:
        """Get stats for all strategies."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM strategy_stats") as cursor:
                rows = await cursor.fetchall()
                return {row['strategy']: dict(row) for row in rows}

    async def update_strategy_stats(self, strategy: str, pnl_usdc: float, won: bool, 
                                    order_type: str = 'maker'):
        """Update strategy statistics."""
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get current stats
            async with db.execute(
                "SELECT * FROM strategy_stats WHERE strategy=?", (strategy,)
            ) as cursor:
                row = await cursor.fetchone()
            
            if row:
                row = dict(row)
                total = row['total_trades'] + 1
                wins = row['wins'] + (1 if won else 0)
                losses = row['losses'] + (0 if won else 1)
                total_pnl = row['total_pnl_usdc'] + pnl_usdc
                
                if won and pnl_usdc > 0:
                    avg_win = (row['avg_win_usdc'] * row['wins'] + pnl_usdc) / wins
                    avg_loss = row['avg_loss_usdc']
                elif not won and pnl_usdc < 0:
                    avg_win = row['avg_win_usdc']
                    avg_loss = (row['avg_loss_usdc'] * row['losses'] + pnl_usdc) / losses
                else:
                    avg_win = row['avg_win_usdc']
                    avg_loss = row['avg_loss_usdc']
                
                maker_trades = row['maker_trades'] + (1 if order_type == 'maker' else 0)
                taker_trades = row['taker_trades'] + (1 if order_type == 'taker' else 0)
                
                await db.execute("""
                    UPDATE strategy_stats 
                    SET total_trades=?, wins=?, losses=?, total_pnl_usdc=?, 
                        avg_win_usdc=?, avg_loss_usdc=?, maker_trades=?, taker_trades=?, last_updated=?
                    WHERE strategy=?
                """, (total, wins, losses, total_pnl, avg_win, avg_loss, 
                      maker_trades, taker_trades, now, strategy))
            else:
                await db.execute("""
                    INSERT INTO strategy_stats 
                    (strategy, total_trades, wins, losses, total_pnl_usdc, 
                     avg_win_usdc, avg_loss_usdc, maker_trades, taker_trades, last_updated)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (strategy, 1 if won else 0, 0 if won else 1, pnl_usdc,
                      pnl_usdc if won else 0, pnl_usdc if not won else 0,
                      1 if order_type == 'maker' else 0,
                      1 if order_type == 'taker' else 0, now))
            
            await db.commit()

    async def get_daily_pnl(self, date: str = None) -> Optional[Dict]:
        """Get P&L for a specific date."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM daily_pnl WHERE date=?", (date,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_daily_pnl(self, pnl_usdc: float, won: bool):
        """Update daily P&L."""
        date = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM daily_pnl WHERE date=?", (date,)) as cursor:
                row = await cursor.fetchone()
            
            if row:
                row = dict(row)
                total = row['total_trades'] + 1
                wins = row['wins'] + (1 if won else 0)
                losses = row['losses'] + (0 if won else 1)
                gross_profit = row['gross_profit_usdc'] + (pnl_usdc if pnl_usdc > 0 else 0)
                gross_loss = row['gross_loss_usdc'] + (pnl_usdc if pnl_usdc < 0 else 0)
                net_pnl = row['net_pnl_usdc'] + pnl_usdc
                
                await db.execute("""
                    UPDATE daily_pnl 
                    SET total_trades=?, wins=?, losses=?, gross_profit_usdc=?,
                        gross_loss_usdc=?, net_pnl_usdc=?
                    WHERE date=?
                """, (total, wins, losses, gross_profit, gross_loss, net_pnl, date))
            else:
                await db.execute("""
                    INSERT INTO daily_pnl 
                    (date, total_trades, wins, losses, gross_profit_usdc, 
                     gross_loss_usdc, net_pnl_usdc, starting_balance_usdc, ending_balance_usdc)
                    VALUES (?, 1, ?, ?, ?, ?, ?, 0, 0)
                """, (date, 1 if won else 0, 0 if won else 1,
                      pnl_usdc if pnl_usdc > 0 else 0,
                      pnl_usdc if pnl_usdc < 0 else 0, pnl_usdc))
            
            await db.commit()

    async def get_open_orders(self) -> List[Dict]:
        """Get all open orders."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE status='open'") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_order_status(self, order_id: str, status: str, filled_at: str = None):
        """Update order status."""
        async with aiosqlite.connect(self.db_path) as db:
            if filled_at:
                await db.execute(
                    "UPDATE orders SET status=?, filled_at=? WHERE id=?",
                    (status, filled_at, order_id)
                )
            else:
                await db.execute(
                    "UPDATE orders SET status=? WHERE id=?",
                    (status, order_id)
                )
            await db.commit()
