"""
Signal Ranker V2.2 — Beast Mode Ensemble Voting

Key features:
- Multi-strategy voting with weighted strategies
- IndicatorFusion gets 1.2x weight (strongest signal)
- 2 strategies agree → +10% confidence
- 3 strategies agree → +20% confidence (HIGH CONVICTION)
- 4+ strategies agree → +25% confidence (MAXIMUM CONVICTION)
- Conflicting signals cancel out cleanly
- Detailed logging of every decision
"""

from typing import Dict, List, Optional
from collections import defaultdict
from strategies.base_strategy import TradeSignal, BaseStrategy
from strategies import ALL_STRATEGIES
from config import Config


class SignalRanker:
    def __init__(self, log_callback=None):
        self.strategies: List[BaseStrategy] = [S() for S in ALL_STRATEGIES]
        self.log = log_callback or (lambda lvl, msg: None)
        # Strategy weights — IndicatorFusion most trusted
        self.strategy_weights = {
            'indicator_fusion': Config.INDICATOR_WEIGHT,  # 1.2x
            'microstructure_maker': 1.0,
            'momentum_breakout': 1.0,
            'volume_imbalance': 0.9,
            'mean_reversion': 0.9,
            'maker_edge': 0.8,
            'longshot_bias': 0.7,
        }

    async def get_ranked_signals(self, markets: List[Dict], context: Dict) -> List[TradeSignal]:
        market_signals: Dict[str, List[TradeSignal]] = defaultdict(list)
        strategies_tried = 0
        strategies_fired = 0
        errors_per_strategy = defaultdict(int)

        for market in markets:
            timeframe = market.get('timeframe', 5)
            # Inject seconds_remaining into context for this market
            ctx = dict(context)
            ctx['seconds_remaining'] = market.get('seconds_remaining', 300)

            for strategy in self.strategies:
                if timeframe not in strategy.get_suitable_timeframes():
                    continue
                strategies_tried += 1
                try:
                    signal = await strategy.analyze(market, ctx)
                    if signal and signal.confidence >= 0.40:
                        key = f"{market.get('market_id','')}_{signal.direction}"
                        market_signals[key].append(signal)
                        strategies_fired += 1
                except Exception as e:
                    errors_per_strategy[strategy.name] += 1

        self.log('DEBUG', f"Strategies: tried={strategies_tried} fired={strategies_fired} "
                         f"errors={dict(errors_per_strategy)}")

        # Build enhanced signals with ensemble boosts
        all_signals = []
        for key, signals in market_signals.items():
            if not signals:
                continue

            # Weighted voting
            best = max(signals, key=lambda s: s.confidence * self.strategy_weights.get(s.strategy, 1.0))
            count = len(signals)

            # BEAST MODE boost tiers
            if count >= 4:
                boost = 0.25
                tier = 'MAXIMUM'
            elif count >= Config.HIGH_CONVICTION_MIN_STRATEGIES:  # 3
                boost = 0.20
                tier = 'HIGH'
            elif count >= 2:
                boost = 0.10
                tier = 'MEDIUM'
            else:
                boost = 0.0
                tier = 'SINGLE'

            final_conf = min(0.92, best.confidence + boost)
            strategies_list = [s.strategy for s in signals]

            enhanced = TradeSignal(
                strategy=best.strategy,
                coin=best.coin,
                timeframe=best.timeframe,
                direction=best.direction,
                token_id=best.token_id,
                market_id=best.market_id,
                entry_price=best.entry_price,
                confidence=final_conf,
                rationale=f"[{tier}:{count}/{len(self.strategies)} agree] {best.rationale}",
                metadata={
                    **best.metadata,
                    'agreement_count': count,
                    'conviction_tier': tier,
                    'strategies_agreeing': strategies_list,
                    'original_confidence': best.confidence,
                    'boost_applied': boost,
                },
                order_type=best.order_type,
                limit_price=best.limit_price,
            )
            all_signals.append(enhanced)

            self.log('SIGNAL', f"  {best.coin} {best.direction} @ {final_conf:.0%} "
                              f"[{tier}] from {strategies_list}")

        # Remove conflicts
        filtered = self._remove_conflicts(all_signals)

        # Apply strict minimum confidence
        min_conf = Config.STRICT_MIN_CONFIDENCE
        pre_count = len(filtered)
        filtered = [s for s in filtered if s.confidence >= min_conf]
        rejected = pre_count - len(filtered)
        if rejected > 0:
            self.log('DEBUG', f"Rejected {rejected} signals below {min_conf:.0%} confidence")

        filtered.sort(key=lambda s: s.confidence, reverse=True)
        return filtered[:Config.MAX_TOTAL_POSITIONS]

    def _remove_conflicts(self, signals):
        by_market = defaultdict(list)
        for s in signals:
            by_market[s.market_id].append(s)
        result = []
        for mkt, sigs in by_market.items():
            dirs = set(s.direction for s in sigs)
            if len(dirs) == 1:
                result.extend(sigs)
            else:
                up_sigs = [s for s in sigs if s.direction == 'UP']
                down_sigs = [s for s in sigs if s.direction == 'DOWN']
                up_max = max((s.confidence for s in up_sigs), default=0)
                down_max = max((s.confidence for s in down_sigs), default=0)
                if up_max > down_max + 0.05:
                    result.extend(up_sigs)
                    self.log('DEBUG', f"Conflict in {mkt[:30]}: UP wins ({up_max:.0%} vs {down_max:.0%})")
                elif down_max > up_max + 0.05:
                    result.extend(down_sigs)
                    self.log('DEBUG', f"Conflict in {mkt[:30]}: DOWN wins ({down_max:.0%} vs {up_max:.0%})")
                else:
                    self.log('DEBUG', f"Conflict in {mkt[:30]}: tied, skipping")
        return result

    def get_strategy_names(self) -> List[str]:
        return [s.name for s in self.strategies]
