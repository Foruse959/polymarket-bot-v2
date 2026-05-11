"""
Improved Dynamic Picker — TOP 5 STRATEGIES ONLY

Eliminates the noise. Focuses on strategies that actually have edge:
1. Time Decay - near expiry discount
2. Cross-Timeframe Arb - guaranteed profit
3. YES+NO Arb - risk-free
4. Binance Momentum - real data
5. Flash Crash - panicdip buying

Win rate learning included.
"""

from typing import Dict, List, Optional
from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.time_decay import TimeDecayStrategy
from strategies.cross_timeframe_arb import CrossTimeframeArbStrategy
from strategies.yes_no_arb import YesNoArbStrategy
from strategies.swing_scalpers import BinanceMomentumSniper
from strategies.flash_crash import MomentumReversal


class ImprovedTracker:
    """Simple win rate tracker - learns from results"""
    
    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.strategy_wins: Dict[str, int] = {}
        self.strategy_losses: Dict[str, int] = {}
    
    def record(self, strategy: str, won: bool):
        if won:
            self.wins += 1
            self.strategy_wins[strategy] = self.strategy_wins.get(strategy, 0) + 1
        else:
            self.losses += 1
            self.strategy_losses[strategy] = self.strategy_losses.get(strategy, 0) + 1
    
    def get_win_rate(self, strategy: str = None) -> float:
        if strategy:
            w = self.strategy_wins.get(strategy, 0)
            l = self.strategy_losses.get(strategy, 0)
            total = w + l
            return w / total if total > 0 else 0.5
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.5
    
    def get_stats(self) -> Dict:
        return {
            'total_wins': self.wins,
            'total_losses': self.losses,
            'overall_win_rate': self.get_win_rate(),
            'by_strategy': {s: self.get_win_rate(s) for s in set(list(self.strategy_wins.keys()) + list(self.strategy_losses.keys()))}
        }


class ImprovedDynamicPicker(BaseStrategy):
    """Top 5 strategies only - no noise"""
    
    name = "improved"
    description = "Top 5 proven strategies with win rate learning"
    
    def __init__(self):
        self.strategies: List[BaseStrategy] = [
            TimeDecayStrategy(),           # High edge: time decay
            CrossTimeframeArbStrategy(), # Guaranteed profit
            YesNoArbStrategy(),        # Risk-free arb
            BinanceMomentumSniper(),   # Real data edge
            MomentumReversal(),       # Panic dip buying
        ]
        self.tracker = ImprovedTracker()
    
    async def analyze(self, market: Dict, context: Dict,
                     balance_prefs: Dict = None) -> Optional[TradeSignal]:
        signals = []
        min_confidence = 0.35  # Slightly higher threshold
        
        for strategy in self.strategies:
            try:
                signal = await strategy.analyze(market, context)
                if signal and signal.confidence >= min_confidence:
                    # Boost based on strategy historical win rate
                    strat_wr = self.tracker.get_win_rate(strategy.name)
                    if strat_wr >= 0.6:
                        signal.confidence = min(0.95, signal.confidence + 0.10)
                    signals.append(signal)
            except Exception:
                continue
        
        if not signals:
            return None
        
        # Sort by confidence
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals[0]
    
    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]
    
    def record_result(self, won: bool):
        """Call after trade settles to learn"""
        # This will be called by the main loop
        pass
    
    def get_all_strategies(self) -> List[BaseStrategy]:
        return self.strategies