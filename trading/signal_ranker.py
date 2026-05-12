"""
Signal Ranker V2 — Multi-strategy ensemble voting.
2+ strategies agreeing = +10% boost. 3+ = +20% boost.
Conflicting signals cancel out.
"""
from typing import Dict, List, Optional
from collections import defaultdict
from strategies.base_strategy import TradeSignal, BaseStrategy
from strategies import ALL_STRATEGIES
from config import Config

class SignalRanker:
    def __init__(self):
        self.strategies: List[BaseStrategy] = [S() for S in ALL_STRATEGIES]

    async def get_ranked_signals(self, markets: List[Dict], context: Dict) -> List[TradeSignal]:
        market_signals: Dict[str, List[TradeSignal]] = defaultdict(list)
        for market in markets:
            timeframe = market.get('timeframe', 5)
            for strategy in self.strategies:
                if timeframe not in strategy.get_suitable_timeframes(): continue
                try:
                    signal = await strategy.analyze(market, context)
                    if signal and signal.confidence >= 0.40:
                        key = f"{market.get('market_id','')}_{signal.direction}"
                        market_signals[key].append(signal)
                except Exception: continue
        all_signals = []
        for key, signals in market_signals.items():
            if not signals: continue
            best = max(signals, key=lambda s: s.confidence)
            count = len(signals)
            boost = 0.20 if count >= 3 else 0.10 if count >= 2 else 0.0
            final_conf = min(0.90, best.confidence + boost)
            enhanced = TradeSignal(
                strategy=best.strategy, coin=best.coin, timeframe=best.timeframe,
                direction=best.direction, token_id=best.token_id, market_id=best.market_id,
                entry_price=best.entry_price, confidence=final_conf,
                rationale=f"[{count} agree] {best.rationale}",
                metadata={**best.metadata, 'agreement_count': count, 'boost': boost},
                order_type=best.order_type, limit_price=best.limit_price,
            )
            all_signals.append(enhanced)
        # Remove conflicts
        filtered = self._remove_conflicts(all_signals)
        filtered = [s for s in filtered if s.confidence >= 0.50]
        filtered.sort(key=lambda s: s.confidence, reverse=True)
        return filtered[:Config.MAX_TOTAL_POSITIONS]

    def _remove_conflicts(self, signals):
        by_market = defaultdict(list)
        for s in signals: by_market[s.market_id].append(s)
        result = []
        for mkt, sigs in by_market.items():
            dirs = set(s.direction for s in sigs)
            if len(dirs) == 1: result.extend(sigs)
            else:
                up_max = max((s.confidence for s in sigs if s.direction == 'UP'), default=0)
                down_max = max((s.confidence for s in sigs if s.direction == 'DOWN'), default=0)
                if up_max > down_max + 0.05: result.extend(s for s in sigs if s.direction == 'UP')
                elif down_max > up_max + 0.05: result.extend(s for s in sigs if s.direction == 'DOWN')
        return result

    def get_strategy_names(self) -> List[str]:
        return [s.name for s in self.strategies]
