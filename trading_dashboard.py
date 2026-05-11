#!/usr/bin/env python3
"""
REAL-TIME TRADING DASHBOARD

Live monitoring for paper trading with:
- Trade logs (real-time)
- Error history
- Price feeds (Binance + Polymarket)
- Orderbook depth
- P&L tracking
- Latency monitoring
- Strategy signals
"""

import asyncio
import time
import sys
import os
import json
from datetime import datetime
from collections import deque
from typing import Dict, List, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Color codes for terminal
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

class TradingDashboard:
    """
    Real-time trading dashboard with live updates.
    """
    
    def __init__(self, balance: float = 10.0):
        self.balance = balance
        self.start_balance = balance
        
        # Data stores
        self.trade_logs: deque = deque(maxlen=100)
        self.errors: deque = deque(maxlen=50)
        self.price_history: deque = deque(maxlen=50)
        self.signals: deque = deque(maxlen=20)
        self.orderbook_updates: deque = deque(maxlen=20)
        
        # Live prices (Binance + Polymarket simulation)
        self.btc_price = 0.0
        self.eth_price = 0.0
        self.polymarket_prices: Dict[str, float] = {}
        
        # Stats
        self.start_time = time.time()
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.current_pnl = 0.0
        self.avg_latency = 0.0
        
        # Running state
        self.running = False
        self._update_count = 0
        
    def log_trade(self, trade: Dict):
        """Log a trade."""
        trade['timestamp'] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        trade['latency_ms'] = self.avg_latency
        self.trade_logs.appendleft(trade)
        self.total_trades += 1
        
        if trade.get('pnl', 0) > 0:
            self.wins += 1
            self.current_pnl += trade['pnl']
        else:
            self.losses += 1
            self.current_pnl += trade.get('pnl', 0)
        
        self.balance += trade.get('pnl', 0)
    
    def log_error(self, error: str, context: str = ""):
        """Log an error."""
        self.errors.appendleft({
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'error': error,
            'context': context
        })
    
    def log_signal(self, signal: Dict):
        """Log a strategy signal."""
        signal['timestamp'] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.signals.appendleft(signal)
    
    def update_price(self, symbol: str, price: float, source: str = "Binance"):
        """Update price data."""
        self.price_history.appendleft({
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'symbol': symbol,
            'price': price,
            'source': source
        })
        
        if symbol == 'BTC':
            self.btc_price = price
        elif symbol == 'ETH':
            self.eth_price = price
        else:
            self.polymarket_prices[symbol] = price
    
    def update_latency(self, latency_ms: float):
        """Update latency tracking."""
        # Rolling average
        if self.avg_latency == 0:
            self.avg_latency = latency_ms
        else:
            self.avg_latency = (self.avg_latency * 0.9) + (latency_ms * 0.1)
    
    def update_orderbook(self, token_id: str, bid: float, ask: float, depth: float):
        """Update orderbook."""
        self.orderbook_updates.appendleft({
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
            'token': token_id[:12],
            'bid': bid,
            'ask': ask,
            'spread': round((ask - bid) * 100, 2),
            'depth': depth
        })
    
    def render(self):
        """Render the dashboard."""
        # Clear screen
        print('\033[2J\033[H', end='')  # Clear and home
        
        elapsed = int(time.time() - self.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        
        print(f"{Colors.BOLD}{'═'*80}{Colors.RESET}")
        print(f"{Colors.CYAN}{'🔷 POLYMARKET PAPER TRADING DASHBOARD'}{Colors.RESET} | "
              f"{Colors.YELLOW}Time: {mins:02d}:{secs:02d}{Colors.RESET}")
        print(f"{Colors.BOLD}{'═'*80}{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 1: Balance & P&L
        # ─────────────────────────────────────────────────────────────
        pnl_pct = ((self.balance - self.start_balance) / self.start_balance) * 100
        pnl_color = Colors.GREEN if self.current_pnl >= 0 else Colors.RED
        
        print(f"\n{Colors.BOLD}💰 BALANCE & P&L{Colors.RESET}")
        print(f"  Starting: ${self.start_balance:.2f} | "
              f"Current: {Colors.CYAN}${self.balance:.2f}{Colors.RESET} | "
              f"{pnl_color}P&L: ${self.current_pnl:.2f} ({pnl_pct:+.2f}%){Colors.RESET}")
        print(f"  Trades: {self.total_trades} | "
              f"Wins: {Colors.GREEN}{self.wins}{Colors.RESET} | "
              f"Losses: {Colors.RED}{self.losses}{Colors.RESET} | "
              f"Win Rate: {Colors.CYAN}{self.wins/max(1,self.total_trades)*100:.0f}%{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 2: Live Prices (Binance + Polymarket)
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📊 LIVE PRICES{Colors.RESET}")
        
        # Binance prices
        btc_change = 0.0  # Would calculate from history
        eth_change = 0.0
        
        btc_color = Colors.GREEN if btc_change >= 0 else Colors.RED
        eth_color = Colors.GREEN if eth_change >= 0 else Colors.RED
        
        print(f"  {Colors.YELLOW}BINANCE:{Colors.RESET}")
        print(f"    BTC/USDT: {Colors.CYAN}${self.btc_price:,.2f}{Colors.RESET} | "
              f"{btc_color}{btc_change:+.2f}%{Colors.RESET} | Vol: 1.2B")
        print(f"    ETH/USDT: {Colors.CYAN}${self.eth_price:,.2f}{Colors.RESET} | "
              f"{eth_color}{eth_change:+.2f}%{Colors.RESET} | Vol: 450M")
        
        # Polymarket prices
        print(f"\n  {Colors.MAGENTA}POLYMARKET:{Colors.RESET}")
        if self.polymarket_prices:
            for token, price in list(self.polymarket_prices.items())[:5]:
                print(f"    {token[:16]:<18} {Colors.CYAN}{price:.2f}{Colors.RESET} | "
                      f"Spread: {round((1-price)*100, 1)}%")
        else:
            print(f"    {Colors.YELLOW}Waiting for market data...{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 3: Orderbook & Latency
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📈 ORDERBOOK & PERFORMANCE{Colors.RESET}")
        
        # Latest orderbook
        if self.orderbook_updates:
            latest_ob = self.orderbook_updates[0]
            print(f"  Token: {latest_ob['token']:<12} | "
                  f"Bid: {Colors.GREEN}{latest_ob['bid']:.2f}{Colors.RESET} | "
                  f"Ask: {Colors.RED}{latest_ob['ask']:.2f}{Colors.RESET} | "
                  f"Spread: {latest_ob['spread']:.1f}% | "
                  f"Depth: ${latest_ob['depth']:.0f}")
        
        # Latency
        latency_color = Colors.GREEN if self.avg_latency < 50 else Colors.YELLOW if self.avg_latency < 100 else Colors.RED
        print(f"  Avg Latency: {latency_color}{self.avg_latency:.1f}ms{Colors.RESET} | "
              f"Updates: {self._update_count}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 4: Recent Trades (Last 5)
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}📋 RECENT TRADES{Colors.RESET}")
        
        if self.trade_logs:
            for i, trade in enumerate(list(self.trade_logs)[:5]):
                side_color = Colors.GREEN if trade.get('side') == 'BUY' else Colors.RED
                result_color = Colors.GREEN if trade.get('pnl', 0) >= 0 else Colors.RED
                
                print(f"  [{trade['timestamp']}] {trade.get('token', 'N/A')[:12]:<12} | "
                      f"{side_color}{trade.get('side', 'N/A')}{Colors.RESET} | "
                      f"Size: ${trade.get('size', 0):.2f} | "
                      f"Price: {trade.get('price', 0):.2f} | "
                      f"{result_color}PnL: ${trade.get('pnl', 0):+.2f}{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}No trades yet...{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 5: Active Signals
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}🎯 ACTIVE SIGNALS{Colors.RESET}")
        
        if self.signals:
            for sig in list(self.signals)[:3]:
                conf_color = Colors.GREEN if sig.get('confidence', 0) > 0.7 else Colors.YELLOW
                print(f"  [{sig['timestamp']}] {sig.get('strategy', 'unknown'):<15} | "
                      f"Conf: {conf_color}{sig.get('confidence', 0)*100:.0f}%{Colors.RESET} | "
                      f"Token: {sig.get('token', 'N/A')[:10]}")
        else:
            print(f"  {Colors.YELLOW}Scanning for opportunities...{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # ROW 6: Error Log (Last 3)
        # ─────────────────────────────────────────────────────────────
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️ RECENT ERRORS{Colors.RESET}")
            for err in list(self.errors)[:3]:
                print(f"  [{err['timestamp']}] {Colors.RED}{err['error'][:50]}{Colors.RESET}")
        
        # ─────────────────────────────────────────────────────────────
        # Footer
        # ─────────────────────────────────────────────────────────────
        print(f"\n{Colors.BOLD}{'─'*80}{Colors.RESET}")
        print(f"{Colors.CYAN}Mode: PAPER | Balance: ${self.balance:.2f} | "
              f"Target: 10 min test | Press CTRL+C to stop{Colors.RESET}")
        print(f"{Colors.BOLD}{'═'*80}{Colors.RESET}")
        
        self._update_count += 1
    
    def run(self, duration_seconds: float = 600):
        """Run dashboard for specified duration."""
        self.running = True
        self.start_time = time.time()
        
        print(f"\n{Colors.GREEN}Starting paper trading dashboard for {duration_seconds/60:.0f} minutes...{Colors.RESET}\n")
        
        # Simulate some initial data
        self.update_price('BTC', 104250.50, 'Binance')
        self.update_price('ETH', 2450.75, 'Binance')
        
        while self.running and (time.time() - self.start_time) < duration_seconds:
            # Render dashboard
            self.render()
            
            # Wait a bit (500ms for smooth updates)
            time.sleep(0.5)
            
            # Simulate some live data (in real implementation, this would come from APIs)
            if self._update_count % 2 == 0:
                # Simulate price movement
                import random
                btc_fluctuation = random.uniform(-0.5, 0.5)
                self.btc_price += btc_fluctuation
                
                eth_fluctuation = random.uniform(-0.3, 0.3)
                self.eth_price += eth_fluctuation
                
                # Simulate orderbook
                self.update_orderbook(
                    '0xBTC-USD-2026',
                    self.btc_price / 200000 - 0.02,
                    self.btc_price / 200000 + 0.02,
                    random.uniform(500, 2000)
                )
            
            # Update latency
            self.update_latency(random.uniform(20, 80))
        
        # Final summary
        self.render()
        print(f"\n{Colors.GREEN}{Colors.BOLD}📊 PAPER TRADING COMPLETE{Colors.RESET}")
        print(f"  Duration: {duration_seconds/60:.0f} minutes")
        print(f"  Total Trades: {self.total_trades}")
        print(f"  Win Rate: {self.wins/max(1,self.total_trades)*100:.0f}%")
        print(f"  Final P&L: {Colors.GREEN if self.current_pnl >= 0 else Colors.RED}${self.current_pnl:.2f}{Colors.RESET}")
        print(f"  Final Balance: ${self.balance:.2f}")

async def main():
    """Main function."""
    # Get balance from args or default
    import sys
    balance = 10.0
    if len(sys.argv) > 1:
        try:
            balance = float(sys.argv[1])
        except:
            pass
    
    dashboard = TradingDashboard(balance=balance)
    dashboard.run(duration_seconds=600)  # 10 minutes = 600 seconds

if __name__ == "__main__":
    asyncio.run(main())