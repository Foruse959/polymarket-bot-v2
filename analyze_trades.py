"""
Strategy Performance Analysis
Analyzes all trade logs to find what's working and what's not.
"""

import csv
import os
from collections import defaultdict
from typing import Dict, List


def analyze_trade_logs():
    """Analyze all trade CSV files and return strategy performance."""
    
    strategy_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0, 'trades': []})
    
    # Find all trade log files
    files = [
        'trades_log.csv',
        'trades_log (2).csv', 
        'trades_log (3).csv',
        'trades_log (4).csv',
        'trades_log (5).csv'
    ]
    
    for filename in files:
        if not os.path.exists(filename):
            continue
            
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = row.get('event', '')
                if event not in ['SELL', 'SETTLE']:
                    continue
                    
                strategy = row.get('strategy', 'unknown')
                pnl_net = float(row.get('pnl_net') or 0)
                pnl_pct = float(row.get('pnl_pct') or 0)
                reason = row.get('reason', '')
                confidence = float(row.get('confidence') or 0)
                
                stats = strategy_stats[strategy]
                stats['trades'].append({
                    'pnl': pnl_net,
                    'pnl_pct': pnl_pct,
                    'reason': reason,
                    'confidence': confidence
                })
                
                if pnl_net > 0:
                    stats['wins'] += 1
                else:
                    stats['losses'] += 1
                stats['total_pnl'] += pnl_net
    
    # Calculate stats
    print("=" * 70)
    print("STRATEGY PERFORMANCE ANALYSIS")
    print("=" * 70)
    
    results = []
    for strategy, stats in sorted(strategy_stats.items()):
        total = stats['wins'] + stats['losses']
        win_rate = stats['wins'] / total * 100 if total > 0 else 0
        avg_pnl = stats['total_pnl'] / total if total > 0 else 0
        
        results.append({
            'strategy': strategy,
            'wins': stats['wins'],
            'losses': stats['losses'],
            'total': total,
            'win_rate': win_rate,
            'total_pnl': stats['total_pnl'],
            'avg_pnl': avg_pnl
        })
    
    # Sort by win rate
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    
    print(f"\n{'Strategy':<25} {'Wins':>6} {'Losses':>7} {'Win%':>7} {'Total P&L':>12} {'Avg P&L':>10}")
    print("-" * 70)
    
    for r in results:
        emoji = "✅" if r['win_rate'] >= 50 else "❌"
        print(f"{emoji} {r['strategy']:<23} {r['wins']:>6} {r['losses']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10.2f} ${r['avg_pnl']:>8.2f}")
    
    # Summary
    total_wins = sum(r['wins'] for r in results)
    total_losses = sum(r['losses'] for r in results)
    total_pnl = sum(r['total_pnl'] for r in results)
    
    print("-" * 70)
    print(f"{'TOTAL':<25} {total_wins:>6} {total_losses:>7} {total_wins/(total_wins+total_losses)*100:>6.1f}% ${total_pnl:>10.2f}")
    
    # What's working vs not
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    working = [r for r in results if r['win_rate'] >= 50 and r['total'] >= 2]
    not_working = [r for r in results if r['win_rate'] < 40 and r['total'] >= 2]
    
    print("\n✅ WORKING (keep, maybe boost):")
    for w in working:
        print(f"   - {w['strategy']}: {w['win_rate']:.0f}% win rate, ${w['total_pnl']:.2f}")
    
    print("\n❌ NOT WORKING (disable or fix):")
    for nw in not_working:
        print(f"   - {nw['strategy']}: {nw['win_rate']:.0f}% win rate, ${nw['total_pnl']:.2f}")
    
    return results


if __name__ == "__main__":
    os.chdir(r"C:\Users\acer\.openclaw\workspace\5min_trade_v1")
    analyze_trade_logs()