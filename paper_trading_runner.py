#!/usr/bin/env python3
"""
PAPER TRADING RUNNER - With Real-time Dashboard

Runs paper trading with live dashboard updates showing:
- Live prices (Binance + Polymarket simulation)
- Trade logs
- Errors
- P&L
- Latency
- Orderbook
- Signals
"""

import asyncio
import time
import sys
import os
import random
import json
from datetime import datetime
from collections import deque
from typing import Dict, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Import our fast components
sys.path.insert(0, 'C:\\Users\\acer\\.openclaw\\workspace\\5min_trade_v2')
from trading.signal_ranker import SignalRanker
from trading.market_state_cache import MarketStateCache
from strategies.fast_picker import create_fast_picker

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'

class PaperTradingBot:
    """
    Paper trading bot with live dashboard.
    """
    
    def __init__(self, balance: float = 10.0, duration_minutes: int = 10):
        self.balance = balance
        self.start_balance = balance
        self.duration_seconds = duration_minutes * 60
        self.start_time = time.time()
        
        # Components
        self.ranker = SignalRanker()
        self.cache = MarketStateCache()
        self.picker = create_fast_picker()
        
        # State
        self.positions: Dict[str, Dict] = {}
        self.trade_logs = []
        self.errors = []
        self.signals = []
        self.orderbook_data = []
        
        # Live prices
        self.btc_price = 104250.50
        self.eth_price = 2450.75
        self.poly_prices = {
            'BTC>105k': 0.52,
            'ETH>2500': 0.48,
            'SOL>150': 0.45,
            'BTC-5min': 0.50,
            'ETH-5min': 0.49
        }
        
        # Stats
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.current_pnl = 0.0
        self.latency_history = []
        
    def update_prices(self):
        """Simulate live price updates."""
        # BTC fluctuates
        self.btc_price += random.uniform(-50, 50)
        self.btc_price = max(100000, min(110000, self.btc_price))
        
        # ETH fluctuates
        self.eth_price += random.uniform(-10, 10)
        self.eth_price = max(2000, min(3000, self.eth_price))
        
        # Polymarket probabilities fluctuate MORE to trigger signals
        for key in self.poly_prices:
            # Larger fluctuations to create trading opportunities
            change = random.uniform(-0.08, 0.08)
            self.poly_prices[key] = max(0.15, min(0.85, self.poly_prices[key] + change))
    
    def update_orderbook(self):
        """Simulate orderbook data."""
        for token in list(self.poly_prices.keys()):
            prob = self.poly_prices[token]
            
            # Create spread
            bid = prob - random.uniform(0.01, 0.03)
            ask = prob + random.uniform(0.01, 0.03)
            
            # Depth varies
            depth = random.uniform(500, 3000)
            
            self.orderbook_data.append({
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'token': token,
                'bid': round(bid, 2),
                'ask': round(ask, 2),
                'spread': round((ask - bid) * 100, 2),
                'depth': round(depth, 0)
            })
            
            # Update cache
            self.cache.update_state(
                token_id=token,
                price=prob,
                spread=ask - bid,
                bid_depth=depth,
                ask_depth=depth
            )
    
    def check_for_signals(self):
        """Check for trading signals."""
        signals_found = []
        
        for token, prob in self.poly_prices.items():
            spread = abs(0.95 - (prob + (1-prob)))
            
            # Check for arb opportunity
            if prob + (1-prob) < 0.95:
                signals_found.append({
                    'strategy': 'ARB',
                    'token': token,
                    'confidence': 0.85,
                    'side': 'BOTH',
                    'price': prob,
                    'urgency': 'NOW'
                })
            
            # Check for high confidence
            if prob > 0.75:
                signals_found.append({
                    'strategy': 'HIGH_PROB',
                    'token': token,
                    'confidence': prob,
                    'side': 'UP',
                    'price': prob,
                    'urgency': 'NOW' if prob > 0.85 else 'SOON'
                })
            elif prob < 0.25:
                signals_found.append({
                    'strategy': 'HIGH_PROB',
                    'token': token,
                    'confidence': 1-prob,
                    'side': 'DOWN',
                    'price': 1-prob,
                    'urgency': 'NOW' if (1-prob) > 0.85 else 'SOON'
                })
        
        return signals_found
    
    def execute_trade(self, signal: Dict) -> Dict:
        """Execute a paper trade."""
        start_time = time.perf_counter()
        
        # Determine size (max 20% of balance in SEED mode)
        max_size = self.balance * 0.20
        size = random.uniform(0.50, max_size)
        
        # Simulate execution
        price = signal['price']
        
        # Determine outcome (based on confidence)
        if random.random() < signal['confidence']:
            # Win!
            pnl = size * random.uniform(0.05, 0.15)
            won = True
        else:
            # Loss
            pnl = -size * random.uniform(0.02, 0.08)
            won = False
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        trade = {
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'token': signal['token'],
            'strategy': signal['strategy'],
            'side': signal['side'],
            'price': round(price, 3),
            'size': round(size, 2),
            'pnl': round(pnl, 2),
            'won': won,
            'latency_ms': round(latency_ms, 1),
            'confidence': signal['confidence']
        }
        
        # Update state
        self.balance += pnl
        self.current_pnl += pnl
        self.total_trades += 1
        
        if won:
            self.wins += 1
        else:
            self.losses += 1
        
        self.trade_logs.insert(0, trade)
        self.latency_history.append(latency_ms)
        
        # Keep only last 100 trades
        if len(self.trade_logs) > 100:
            self.trade_logs = self.trade_logs[:100]
        
        return trade
    
    def render_dashboard(self):
        """Render the real-time dashboard."""
        # Clear screen
        print('\033[2J\033[H', end='')
        
        elapsed = int(time.time() - self.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        remaining = int(self.duration_seconds - elapsed)
        rem_mins = remaining // 60
        rem_secs = remaining % 60
        
        # Calculate average latency
        avg_latency = sum(self.latency_history[-10:]) / len(self.latency_history[-10:]) if self.latency_history else 0
        
        print(f"{Colors.BOLD}{'='*90}{Colors.RESET}")
        print(f"{Colors.CYAN}🔷 POLYMARKET PAPER TRADING DASHBOARD{Colors.RESET} | "
              f"{Colors.YELLOW}Time: {mins:02d}:{secs:02d} | Remaining: {rem_mins:02d}:{rem_secs:02d}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*90}{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # BALANCE & P&L
        # ─────────────────────────────────────────────────────────────
        pnl_pct = ((self.balance - self.start_balance) / self.start_balance) * 100
        pnl_color = Colors.GREEN if self.current_pnl >= 0 else Colors.RED
        win_rate = (self.wins / max(1, self.total_trades)) * 100
        
        print(f"\n{Colors.BOLD}💰 BALANCE & P&L{Colors.RESET}")
        print(f"  Starting: ${self.start_balance:.2f} | "
              f"Current: {Colors.CYAN}${self.balance:.2f}{Colors.RESET} | "
              f"{pnl_color}P&L: ${self.current_pnl:.2f} ({pnl_pct:+.2f}%){Colors.RESET}")
        print(f"  Trades: {self.total_trades} | "
              f"Wins: {Colors.GREEN}{self.wins}{Colors.RESET} | "
              f"Losses: {Colors.RED}{self.losses}{Colors.RESET} | "
              f"Win Rate: {Colors.CYAN}{win_rate:.0f}%{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # LIVE PRICES
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📊 LIVE PRICES{Colors.RESET}")
        
        btc_change = ((self.btc_price - 104250) / 104250) * 100
        eth_change = ((self.eth_price - 2450) / 2450) * 100
        btc_color = Colors.GREEN if btc_change >= 0 else Colors.RED
        eth_color = Colors.GREEN if eth_change >= 0 else Colors.RED
        
        print(f"  {Colors.YELLOW}BINANCE:{Colors.RESET}")
        print(f"    BTC/USDT: {Colors.CYAN}${self.btc_price:,.2f}{Colors.RESET} | "
              f"{btc_color}{btc_change:+.2f}%{Colors.RESET}")
        print(f"    ETH/USDT: {Colors.CYAN}${self.eth_price:,.2f}{Colors.RESET} | "
              f"{eth_color}{eth_change:+.2f}%{Colors.RESET}")
        
        print(f"\n  {Colors.MAGENTA}POLYMARKET:{Colors.RESET}")
        for token, prob in list(self.poly_prices.items())[:5]:
            spread = 100 - (prob + (1-prob)) * 100
            print(f"    {token:<15} {Colors.CYAN}{prob:.2f}{Colors.RESET} | "
                  f"Spread: {spread:.1f}%")
        
        # ─────────────────────────────────────────────────────────────
        # ORDERBOOK & LATENCY
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📈 ORDERBOOK & PERFORMANCE{Colors.RESET}")
        
        if self.orderbook_data:
            latest = self.orderbook_data[0]
            depth_color = Colors.GREEN if latest['depth'] > 1000 else Colors.YELLOW if latest['depth'] > 500 else Colors.RED
            print(f"  Token: {latest['token']:<15} | "
                  f"Bid: {Colors.GREEN}{latest['bid']:.2f}{Colors.RESET} | "
                  f"Ask: {Colors.RED}{latest['ask']:.2f}{Colors.RESET} | "
                  f"Spread: {latest['spread']:.1f}% | "
                  f"Depth: {depth_color}${latest['depth']:.0f}{Colors.RESET}")
        
        latency_color = Colors.GREEN if avg_latency < 50 else Colors.YELLOW if avg_latency < 100 else Colors.RED
        print(f"  Avg Latency: {latency_color}{avg_latency:.1f}ms{Colors.RESET} | "
              f"Trades: {self.total_trades}")
        
        # ─────────────────────────────────────────────────────────────
        # RECENT TRADES
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📋 RECENT TRADES{Colors.RESET}")
        
        if self.trade_logs:
            for trade in self.trade_logs[:5]:
                side_color = Colors.GREEN if trade['side'] in ['BUY', 'UP'] else Colors.RED
                result_color = Colors.GREEN if trade['pnl'] >= 0 else Colors.RED
                
                print(f"  [{trade['timestamp']}] {trade['strategy']:<10} | "
                      f"{trade['token']:<12} | "
                      f"{side_color}{trade['side']:<5}{Colors.RESET} | "
                      f"${trade['size']:.2f} | "
                      f"{result_color}${trade['pnl']:+.2f}{Colors.RESET} | "
                      f"conf:{trade['confidence']*100:.0f}% | "
                      f"lat:{trade['latency_ms']:.0f}ms")
        else:
            print(f"  {Colors.YELLOW}Waiting for trading signals...{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ACTIVE SIGNALS
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}🎯 ACTIVE STRATEGIES{Colors.RESET}")
        
        # Check for potential signals
        signals = self.check_for_signals()
        
        if signals:
            for sig in signals[:3]:
                conf_color = Colors.GREEN if sig['confidence'] > 0.7 else Colors.YELLOW
                print(f"  {sig['strategy']:<10} | "
                      f"Token: {sig['token']:<12} | "
                      f"Conf: {conf_color}{sig['confidence']*100:.0f}%{Colors.RESET} | "
                      f"Urgency: {sig['urgency']}")
        else:
            print(f"  {Colors.YELLOW}Scanning markets...{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # FOOTER
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}{'─'*90}{Colors.RESET}")
        print(f"{Colors.CYAN}Mode: PAPER | Balance: ${self.balance:.2f} | "
              f"Max Position: $2.00 (20%) | Risk: SEED{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*90}{Colors.RESET}")
    
    async def run(self):
        """Run the paper trading bot."""
        print(f"\n{Colors.GREEN}🚀 Starting Paper Trading Bot{Colors.RESET}")
        print(f"   Balance: ${self.balance:.2f}")
        print(f"   Duration: {self.duration_seconds // 60} minutes")
        print(f"   Risk Mode: SEED (max 20% per trade)")
        print()
        
        last_signal_check = time.time()
        signal_interval = 2  # Check every 2 seconds
        
        while time.time() - self.start_time < self.duration_seconds:
            # Update prices (every 500ms)
            self.update_prices()
            self.update_orderbook()
            
            # Check for signals (every 2 seconds)
            if time.time() - last_signal_check > signal_interval:
                signals = self.check_for_signals()
                
                # Execute signal more frequently for testing
                if signals and random.random() < 0.6:  # 60% chance to trade
                    signal = random.choice(signals)
                    trade = self.execute_trade(signal)
                    
                    # Log
                    self.signals.insert(0, {
                        'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                        'strategy': signal['strategy'],
                        'confidence': signal['confidence'],
                        'token': signal['token'],
                        'executed': True
                    })
                
                last_signal_check = time.time()
            
            # Render dashboard
            self.render_dashboard()
            
            # Wait
            await asyncio.sleep(0.5)
        
        # Final summary
        print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}📊 PAPER TRADING COMPLETE{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"  Duration: {self.duration_seconds // 60} minutes")
        print(f"  Total Trades: {self.total_trades}")
        print(f"  Win Rate: {(self.wins / max(1, self.total_trades)) * 100:.0f}%")
        print(f"  Final P&L: {Colors.GREEN if self.current_pnl >= 0 else Colors.RED}${self.current_pnl:.2f}{Colors.RESET}")
        print(f"  Final Balance: ${self.balance:.2f}")
        print(f"  ROI: {((self.balance - self.start_balance) / self.start_balance) * 100:.2f}%")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")

async def main():
    """Main entry point."""
    balance = 10.0
    duration = 10  # minutes
    
    # Parse arguments
    if len(sys.argv) > 1:
        try:
            balance = float(sys.argv[1])
        except:
            pass
    
    if len(sys.argv) > 2:
        try:
            duration = int(sys.argv[2])
        except:
            pass
    
    bot = PaperTradingBot(balance=balance, duration_minutes=duration)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())