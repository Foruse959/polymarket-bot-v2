#!/usr/bin/env python3
"""
BOT WATCHER - Monitor, Analyze & Auto-Improve

Features:
- Real-time performance tracking
- Win rate analysis
- Auto-strategy adjustment
- Trade pattern detection
- Alerts for issues
"""

import asyncio
import json
import csv
import time
import os
import sys
from datetime import datetime, timedelta
from collections import deque, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Config

class BotWatcher:
    """Monitors bot performance and suggests improvements."""
    
    def __init__(self):
        self.stats = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_trade_pnl': 0.0,
            'best_strategy': '',
            'worst_strategy': '',
            'avg_hold_time': 0,
        }
        
        self.trades_history = deque(maxlen=1000)
        self.strategy_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
        self.hourly_performance = deque(maxlen=24)
        
        self.last_check = 0
        self.check_interval = 30  # seconds
        self.improvement_suggestions = []
        
    def load_trades(self):
        """Load trades from CSV files."""
        csv_files = [
            'data/trades_log.csv',
            'trades_log.csv',
            'data/trades.csv'
        ]
        
        for file_path in csv_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            self.trades_history.append(row)
                    print(f"[WATCHER] Loaded {len(self.trades_history)} trades from {file_path}")
                    return True
                except Exception as e:
                    print(f"[WATCHER] Error loading {file_path}: {e}")
        return False
    
    def analyze_performance(self):
        """Analyze current performance."""
        if not self.trades_history:
            return
        
        # Basic stats
        total = len(self.trades_history)
        wins = sum(1 for t in self.trades_history if float(t.get('pnl', 0)) > 0)
        losses = total - wins
        
        self.stats['total_trades'] = total
        self.stats['wins'] = wins
        self.stats['losses'] = losses
        self.stats['win_rate'] = (wins / total * 100) if total > 0 else 0
        
        # P&L
        total_pnl = sum(float(t.get('pnl', 0)) for t in self.trades_history)
        self.stats['total_pnl'] = total_pnl
        self.stats['avg_trade_pnl'] = total_pnl / total if total > 0 else 0
        
        # Strategy analysis
        self.strategy_stats.clear()
        for trade in self.trades_history:
            strategy = trade.get('strategy', 'unknown')
            pnl = float(trade.get('pnl', 0))
            
            if pnl > 0:
                self.strategy_stats[strategy]['wins'] += 1
            else:
                self.strategy_stats[strategy]['losses'] += 1
            self.strategy_stats[strategy]['pnl'] += pnl
        
        # Best/worst strategy
        if self.strategy_stats:
            best = max(self.strategy_stats.items(), key=lambda x: x[1]['pnl'])
            worst = min(self.strategy_stats.items(), key=lambda x: x[1]['pnl'])
            self.stats['best_strategy'] = best[0]
            self.stats['worst_strategy'] = worst[0]
    
    def generate_suggestions(self):
        """Generate improvement suggestions based on performance."""
        suggestions = []
        
        # Win rate check
        if self.stats['win_rate'] < 50:
            suggestions.append({
                'priority': 'HIGH',
                'issue': 'Win rate below 50%',
                'suggestion': 'Reduce position sizes, increase confidence threshold',
                'action': 'Increase MIN_CONFIDENCE in .env'
            })
        elif self.stats['win_rate'] > 65:
            suggestions.append({
                'priority': 'GOOD',
                'issue': 'High win rate detected',
                'suggestion': 'Consider increasing position sizes gradually',
                'action': 'Can increase MAX_BET_PCT slightly'
            })
        
        # Strategy performance
        for strategy, stats in self.strategy_stats.items():
            total = stats['wins'] + stats['losses']
            if total >= 5:
                win_rate = stats['wins'] / total * 100
                if win_rate < 40:
                    suggestions.append({
                        'priority': 'MEDIUM',
                        'issue': f'{strategy} performing poorly ({win_rate:.1f}% WR)',
                        'suggestion': f'Consider disabling {strategy}',
                        'action': f'Set ENABLE_{strategy.upper()}=false'
                    })
        
        # P&L check
        if self.stats['total_pnl'] < -1.0:
            suggestions.append({
                'priority': 'CRITICAL',
                'issue': 'Negative total P&L',
                'suggestion': 'STOP TRADING and review strategy',
                'action': 'Switch to paper mode immediately'
            })
        
        self.improvement_suggestions = suggestions
        return suggestions
    
    def print_report(self):
        """Print performance report."""
        print("\n" + "="*70)
        print(f"🤖 BOT WATCHER REPORT - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        print(f"\n📊 PERFORMANCE:")
        print(f"   Total Trades: {self.stats['total_trades']}")
        print(f"   Wins: {self.stats['wins']} | Losses: {self.stats['losses']}")
        print(f"   Win Rate: {self.stats['win_rate']:.1f}%")
        print(f"   Total P&L: ${self.stats['total_pnl']:.2f}")
        print(f"   Avg per Trade: ${self.stats['avg_trade_pnl']:.3f}")
        
        if self.strategy_stats:
            print(f"\n🎯 STRATEGY BREAKDOWN:")
            for strategy, stats in sorted(self.strategy_stats.items(), 
                                          key=lambda x: x[1]['pnl'], reverse=True):
                total = stats['wins'] + stats['losses']
                wr = (stats['wins'] / total * 100) if total > 0 else 0
                print(f"   {strategy:15} | WR: {wr:5.1f}% | PnL: ${stats['pnl']:+.2f} | Trades: {total}")
        
        if self.improvement_suggestions:
            print(f"\n💡 SUGGESTIONS:")
            for s in self.improvement_suggestions:
                emoji = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'GOOD': '🟢'}.get(s['priority'], '⚪')
                print(f"   {emoji} [{s['priority']}] {s['issue']}")
                print(f"      → {s['suggestion']}")
                print(f"      → Action: {s['action']}")
        else:
            print(f"\n✅ No issues detected - bot performing well!")
        
        print("="*70 + "\n")
    
    async def watch_loop(self):
        """Main watching loop."""
        print("[WATCHER] Starting Bot Watcher...")
        print("[WATCHER] Monitoring trades and performance...\n")
        
        while True:
            try:
                # Reload trades
                self.load_trades()
                
                # Analyze
                self.analyze_performance()
                self.generate_suggestions()
                
                # Print report every 5 minutes or on significant change
                current_time = time.time()
                if current_time - self.last_check >= 300:  # 5 minutes
                    self.print_report()
                    self.last_check = current_time
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                print(f"[WATCHER ERROR] {e}")
                await asyncio.sleep(60)
    
    def export_report(self, filename=None):
        """Export report to JSON."""
        if not filename:
            filename = f"watcher_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'strategy_stats': dict(self.strategy_stats),
            'suggestions': self.improvement_suggestions
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"[WATCHER] Report exported to {filename}")
        return filename


async def main():
    """Run the watcher."""
    watcher = BotWatcher()
    await watcher.watch_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WATCHER] Stopped")
