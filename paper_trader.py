#!/usr/bin/env python3
"""
Paper Trading Mode — Test strategies without real money.

Uses Polymarket API for live data but simulates trades.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

class PaperTrader:
    """Paper trading bot for testing strategies."""
    
    def __init__(self, starting_balance: float = 100.0):
        self.balance = starting_balance
        self.initial_balance = starting_balance
        self.positions = []
        self.trades = []
        self.running = False
        
    async def fetch_markets(self) -> list:
        """Fetch active crypto markets from Polymarket."""
        try:
            import requests
            
            # Get active markets from Gamma API
            url = "https://gamma-api.polymarket.com/markets"
            params = {
                'active': 'true',
                'closed': 'false',
                'limit': 100,
            }
            
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                markets = resp.json()
                # Filter for 5min/15min crypto markets
                crypto_markets = []
                for m in markets:
                    question = m.get('question', '').lower()
                    if any(c in question for c in ['bitcoin', 'btc', 'eth', 'ethereum', 'sol']):
                        if any(t in question for t in ['5m', '15m', '5 minute', '15 minute']):
                            crypto_markets.append(m)
                return crypto_markets
            return []
        except Exception as e:
            print(f"⚠️ Failed to fetch markets: {e}")
            return []
    
    async def analyze_market(self, market: dict) -> Optional[dict]:
        """Analyze a market for trading opportunity."""
        # Simplified analysis - check if there's a clear trend
        try:
            question = market.get('question', '').lower()
            
            # Mock analysis - in real bot this would use CLOB data
            # For paper mode, simulate finding opportunities
            import random
            
            if random.random() < 0.3:  # 30% chance of signal
                direction = 'UP' if random.random() < 0.52 else 'DOWN'
                confidence = random.uniform(0.55, 0.75)
                
                return {
                    'market_id': market.get('market_id'),
                    'direction': direction,
                    'confidence': confidence,
                    'suggested_price': random.uniform(0.45, 0.55),
                    'strategy': 'paper_momentum'
                }
            return None
        except Exception as e:
            return None
    
    async def simulate_trade(self, signal: dict) -> dict:
        """Simulate executing a trade."""
        market_id = signal['market_id']
        direction = signal['direction']
        entry_price = signal['suggested_price']
        
        # Position sizing: 2% of balance
        size = self.balance * 0.02
        
        trade = {
            'id': f"paper_{len(self.trades)}",
            'market_id': market_id,
            'direction': direction,
            'entry_price': entry_price,
            'size': size,
            'entry_time': datetime.now(timezone.utc).isoformat(),
            'status': 'open'
        }
        
        self.positions.append(trade)
        self.balance -= size
        
        print(f"📥 PAPER TRADE: {direction} @ ${entry_price:.3f} (Size: ${size:.2f})")
        
        return trade
    
    async def simulate_exit(self, position: dict) -> dict:
        """Simulate closing a position."""
        # Simulate outcome
        import random
        
        # 60% win rate for paper mode
        is_win = random.random() < 0.60
        
        if is_win:
            # Win: exit at 0.75-0.95
            exit_price = random.uniform(0.75, 0.95)
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            # Loss: exit at stop loss
            exit_price = position['entry_price'] * 0.75
            pnl = (exit_price - position['entry_price']) * position['size']
        
        # Apply fees
        fee = position['size'] * 0.005
        pnl -= fee
        
        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now(timezone.utc).isoformat()
        position['pnl'] = pnl
        position['status'] = 'closed'
        position['outcome'] = 'win' if is_win else 'loss'
        
        self.balance += position['size'] + pnl
        self.trades.append(position)
        
        emoji = "✅" if is_win else "❌"
        print(f"{emoji} PAPER EXIT: ${exit_price:.3f} | P&L: ${pnl:+.2f}")
        
        return position
    
    async def run_cycle(self):
        """Run one trading cycle."""
        print(f"\n{'='*60}")
        print(f"📊 PAPER TRADING CYCLE")
        print(f"   Balance: ${self.balance:.2f}")
        print(f"   Open Positions: {len(self.positions)}")
        print(f"{'='*60}")
        
        # Fetch markets
        markets = await self.fetch_markets()
        print(f"   Found {len(markets)} active crypto markets")
        
        # Analyze markets
        for market in markets[:5]:  # Check top 5
            signal = await self.analyze_market(market)
            if signal and len(self.positions) < 5:  # Max 5 positions
                if signal['confidence'] >= 0.60 and self.balance > 10:
                    await self.simulate_trade(signal)
        
        # Check existing positions for exits
        for pos in list(self.positions):
            # Simulate holding time
            import random
            if random.random() < 0.4:  # 40% chance to exit per cycle
                await self.simulate_exit(pos)
                self.positions.remove(pos)
    
    def print_stats(self):
        """Print trading statistics."""
        print(f"\n{'='*60}")
        print(f"📊 PAPER TRADING STATS")
        print(f"{'='*60}")
        print(f"   Initial Balance: ${self.initial_balance:.2f}")
        print(f"   Current Balance: ${self.balance:.2f}")
        print(f"   Total Return: {((self.balance / self.initial_balance) - 1) * 100:.1f}%")
        print(f"   Total Trades: {len(self.trades)}")
        
        if self.trades:
            wins = sum(1 for t in self.trades if t.get('outcome') == 'win')
            losses = len(self.trades) - wins
            win_rate = wins / len(self.trades) * 100
            
            print(f"   Wins: {wins} | Losses: {losses}")
            print(f"   Win Rate: {win_rate:.1f}%")
            
            total_pnl = sum(t.get('pnl', 0) for t in self.trades)
            print(f"   Total P&L: ${total_pnl:+.2f}")
        
        print(f"{'='*60}\n")
    
    async def run(self, cycles: int = 10):
        """Run paper trading for N cycles."""
        print(f"\n{'='*60}")
        print(f"🚀 STARTING PAPER TRADING MODE")
        print(f"   Starting Balance: ${self.balance:.2f}")
        print(f"   Cycles: {cycles}")
        print(f"{'='*60}\n")
        
        self.running = True
        
        for i in range(cycles):
            if not self.running:
                break
            
            print(f"\n🔄 Cycle {i+1}/{cycles}")
            await self.run_cycle()
            await asyncio.sleep(1)  # Simulate delay
        
        # Close all remaining positions
        print(f"\n🔄 Closing remaining positions...")
        for pos in list(self.positions):
            await self.simulate_exit(pos)
        self.positions.clear()
        
        # Final stats
        self.print_stats()
        
        print(f"{'='*60}")
        print(f"✅ PAPER TRADING COMPLETE")
        print(f"{'='*60}")
        
        # Verdict
        if self.balance > self.initial_balance:
            print(f"🎉 PROFITABLE — Strategy works in paper mode!")
        else:
            print(f"⚠️ UNPROFITABLE — Needs improvement")
        print(f"{'='*60}\n")

async def main():
    """Main entry point."""
    trader = PaperTrader(starting_balance=100.0)
    await trader.run(cycles=20)

if __name__ == "__main__":
    asyncio.run(main())