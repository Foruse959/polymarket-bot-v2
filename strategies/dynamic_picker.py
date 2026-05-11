"""
Dynamic Strategy Picker — Select Best Strategy for Market Conditions

Updated for v2 with maker-first approach and category-aware selection.
"""

import time
from typing import Dict, List, Optional
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.maker_edge import MakerEdgeStrategy
from strategies.longshot_bias import LongshotBiasStrategy


class DynamicPicker(BaseStrategy):
    """
    Dynamically picks the best strategy based on market conditions.
    Prioritizes maker strategies for v2.
    """

    name = "dynamic_picker"
    description = "Automatically selects best strategy based on market conditions"
    preferred_order_type = "maker"

    def __init__(self):
        self.strategies = {
            'maker_edge': MakerEdgeStrategy(),
            'longshot_bias': LongshotBiasStrategy(),
        }
        
        self.performance_tracker = {}
        self.last_switch_time = 0
        self.min_switch_interval = 300  # 5 minutes

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """
        Run all strategies and pick the best signal.
        Prioritizes maker orders with highest edge.
        """
        signals = []
        
        # Run all strategies
        for name, strategy in self.strategies.items():
            try:
                signal = await strategy.analyze(market, context)
                if signal:
                    # Add performance weight
                    perf = self.performance_tracker.get(name, {'win_rate': 0.5, 'avg_pnl': 0})
                    weighted_confidence = signal.confidence * (0.8 + 0.4 * perf['win_rate'])
                    signal.confidence = min(0.95, weighted_confidence)
                    signals.append((name, signal))
            except Exception as e:
                print(f"⚠️ Strategy {name} failed: {e}", flush=True)
                continue
        
        if not signals:
            return None
        
        # Score each signal
        def score_signal(name_signal):
            name, signal = name_signal
            score = signal.confidence
            
            # Prefer maker orders
            if signal.order_type == 'maker':
                score += 0.05
            
            # Prefer higher edge if available
            edge = signal.metadata.get('edge_bps', 0)
            score += min(0.10, edge / 1000)  # Up to +0.10 for high edge
            
            # Penalize if strategy is underperforming
            perf = self.performance_tracker.get(name, {'avg_pnl': 0})
            if perf['avg_pnl'] < -0.5:
                score -= 0.10
            
            return score
        
        # Pick best signal
        signals.sort(key=score_signal, reverse=True)
        best_name, best_signal = signals[0]
        
        # Update signal with picker info
        best_signal.metadata['picked_by'] = self.name
        best_signal.metadata['runner_up'] = signals[1][0] if len(signals) > 1 else None
        best_signal.metadata['strategy_scores'] = {
            name: score_signal((name, sig)) for name, sig in signals
        }
        
        return best_signal

    def update_performance(self, strategy_name: str, pnl_usdc: float, won: bool):
        """Update performance tracking for a strategy."""
        if strategy_name not in self.performance_tracker:
            self.performance_tracker[strategy_name] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0.5,
                'avg_pnl': 0,
            }
        
        perf = self.performance_tracker[strategy_name]
        perf['trades'] += 1
        if won:
            perf['wins'] += 1
        perf['total_pnl'] += pnl_usdc
        perf['win_rate'] = perf['wins'] / perf['trades']
        perf['avg_pnl'] = perf['total_pnl'] / perf['trades']

    def get_performance_summary(self) -> Dict:
        """Get performance summary for all strategies."""
        return self.performance_tracker.copy()
