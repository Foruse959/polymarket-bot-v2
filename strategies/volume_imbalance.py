"""
Volume Imbalance Strategy — Trade against biased order flow.
When UP orderbook shows heavy buying pressure, provide NO liquidity.
"""
from typing import Dict, Optional, List
from collections import deque
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal

class VolumeImbalanceStrategy(BaseStrategy):
    name = "volume_imbalance"
    description = "Detect and trade against biased order flow imbalance"
    preferred_order_type = "maker"

    def __init__(self):
        self.recent_imbalances: Dict[str, deque] = {}

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        if not clob or seconds_remaining < 45:
            return None
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None
        dual_book = clob.get_dual_orderbook(up_token, down_token)
        if not dual_book:
            return None
        up_book, down_book = dual_book['up'], dual_book['down']
        if up_book.get('_synthetic') or down_book.get('_synthetic'):
            return None
        up_imbalance = up_book.get('imbalance', 0)
        market_key = market.get('market_id', '')
        if market_key not in self.recent_imbalances:
            self.recent_imbalances[market_key] = deque(maxlen=5)
        self.recent_imbalances[market_key].append(up_imbalance)
        history = self.recent_imbalances[market_key]
        if len(history) < 2:
            return None
        avg_imbalance = sum(history) / len(history)
        up_bid_depth = up_book.get('bid_depth', 0)
        down_bid_depth = down_book.get('bid_depth', 0)
        cross_ratio = (up_bid_depth + 0.001) / (down_bid_depth + 0.001)
        if avg_imbalance > 0.35 and cross_ratio > 1.5:
            no_mid = down_book['mid_price']
            spread_bps = down_book['spread_bps']
            if spread_bps > 500 or no_mid < 0.25 or no_mid > 0.75:
                return None
            limit_price = round(min(down_book['best_ask'] - 0.01, no_mid + 0.005), 2)
            limit_price = max(limit_price, down_book['best_bid'] + 0.005)
            limit_price = max(0.01, min(0.99, limit_price))
            confidence = 0.50 + min(avg_imbalance * 0.3, 0.25)
            if len(history) >= 3 and all(h > 0.2 for h in history):
                confidence += 0.05
            return TradeSignal(
                strategy=self.name, coin=market['coin'], timeframe=market['timeframe'],
                direction='DOWN', token_id=down_token, market_id=market['market_id'],
                entry_price=no_mid, confidence=min(0.85, confidence),
                rationale=f"Flow imbalance: avg={avg_imbalance:.2f} cross={cross_ratio:.1f}x | BUY NO @ {limit_price:.3f}",
                metadata={'avg_imbalance': avg_imbalance, 'cross_ratio': cross_ratio, 'signal_type': 'flow_imbalance'},
                order_type='maker', limit_price=limit_price,
            )
        return None
