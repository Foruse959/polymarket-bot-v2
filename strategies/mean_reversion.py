"""
Mean Reversion — Buy undervalued side when prices deviate from fair value.
Resolution is 50/50 (proven by 323K market analysis), so any price far from 0.50
represents a mispricing caused by biased taker flow.
"""
from typing import Dict, Optional, List
from collections import deque
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal

class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
    description = "Buy undervalued side when prices deviate from fair value"
    preferred_order_type = "maker"

    def __init__(self):
        self.price_history: Dict[str, deque] = {}
        self.fair_value = 0.50

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        if not clob or seconds_remaining < 60:
            return None
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None
        up_price = clob.get_mid_price(up_token)
        down_price = clob.get_mid_price(down_token)
        if up_price is None or down_price is None:
            return None
        up_dev = up_price - self.fair_value
        down_dev = down_price - self.fair_value
        if up_dev >= 0.10:
            return self._signal(market, clob, 'DOWN', down_token, up_dev, seconds_remaining)
        elif down_dev >= 0.10:
            return self._signal(market, clob, 'UP', up_token, down_dev, seconds_remaining)
        return None

    def _signal(self, market, clob, direction, token_id, deviation, seconds_remaining):
        book = clob.get_orderbook(token_id)
        if not book or book.get('_synthetic') or book['spread_bps'] > 500:
            return None
        if deviation >= 0.30: confidence = 0.70
        elif deviation >= 0.20: confidence = 0.62
        else: confidence = 0.52
        if seconds_remaining < 120: confidence -= 0.10
        elif seconds_remaining > 300: confidence += 0.05
        confidence = min(0.85, max(0.35, confidence))
        limit_price = round(book['best_ask'] - 0.01, 2)
        limit_price = max(limit_price, book['best_bid'] + 0.005)
        limit_price = max(0.01, min(0.99, limit_price))
        strength = 'EXTREME' if deviation >= 0.30 else 'STRONG' if deviation >= 0.20 else 'MILD'
        return TradeSignal(
            strategy=self.name, coin=market['coin'], timeframe=market['timeframe'],
            direction=direction, token_id=token_id, market_id=market['market_id'],
            entry_price=book['mid_price'], confidence=confidence,
            rationale=f"Mean reversion ({strength}): deviation={deviation:.1%} | BUY {direction} @ {limit_price:.3f}",
            metadata={'deviation': deviation, 'signal_strength': strength, 'signal_type': 'mean_reversion'},
            order_type='maker', limit_price=limit_price,
        )
