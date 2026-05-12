"""
Microstructure Maker Strategy — Exploit maker-taker wealth transfer.
Based on Becker (2026): Makers earn +1.12% vs Takers -1.12%.
Backtest: Low volume markets show 78.9% UP taker bias.
Strategy: BUY NO/DOWN as maker in low-medium volume markets.
"""
from typing import Dict, Optional, List
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal

class MicrostructureMakerStrategy(BaseStrategy):
    name = "microstructure_maker"
    description = "Exploit maker-taker wealth transfer via NO-side limit orders"
    preferred_order_type = "maker"
    VOLUME_BIAS = {
        'very_low': {'max_vol': 100, 'up_bias': 0.789, 'confidence_boost': 0.15},
        'low': {'max_vol': 1000, 'up_bias': 0.593, 'confidence_boost': 0.10},
        'medium': {'max_vol': 10000, 'up_bias': 0.483, 'confidence_boost': 0.03},
        'high': {'max_vol': float('inf'), 'up_bias': 0.494, 'confidence_boost': 0.0},
    }

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        if not clob or seconds_remaining < 30:
            return None
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None
        dual_book = clob.get_dual_orderbook(up_token, down_token)
        if not dual_book:
            return None
        down_book = dual_book['down']
        if down_book.get('_synthetic'):
            return None
        volume = market.get('raw', {}).get('volume', 0)
        if isinstance(volume, str):
            try: volume = float(volume)
            except: volume = 0
        bias_tier = self._get_volume_tier(volume)
        if bias_tier['up_bias'] < 0.55:
            return None
        no_mid = down_book['mid_price']
        spread_bps = down_book['spread_bps']
        if spread_bps < 20 or spread_bps > 500:
            return None
        if not (0.35 <= no_mid <= 0.70):
            return None
        no_best_ask = down_book['best_ask']
        no_best_bid = down_book['best_bid']
        offset = min(0.02, spread_bps / 10000 * 0.3)
        limit_price = round(no_best_ask - offset, 2)
        limit_price = max(limit_price, no_best_bid + 0.01)
        limit_price = max(0.01, min(0.99, limit_price))
        edge = bias_tier['up_bias'] - 0.50
        confidence = 0.45 + bias_tier['confidence_boost']
        if 50 <= spread_bps <= 200: confidence += 0.05
        if seconds_remaining > 180: confidence += 0.03
        elif seconds_remaining < 60: confidence -= 0.10
        confidence = min(0.90, max(0.30, confidence))
        return TradeSignal(
            strategy=self.name, coin=market['coin'], timeframe=market['timeframe'],
            direction='DOWN', token_id=down_token, market_id=market['market_id'],
            entry_price=no_mid, confidence=confidence,
            rationale=f"Microstructure: BUY NO @ {limit_price:.3f} | bias={bias_tier['up_bias']:.0%} | edge={edge*10000:.0f}bps",
            metadata={'volume': volume, 'up_bias': bias_tier['up_bias'], 'edge_bps': edge*10000, 'signal_type': 'volume_bias'},
            order_type='maker', limit_price=limit_price,
        )

    def _get_volume_tier(self, volume: float) -> Dict:
        if volume < Config.VOLUME_LOW_THRESHOLD: return {**self.VOLUME_BIAS['very_low'], 'label': 'very_low'}
        elif volume < Config.VOLUME_MED_THRESHOLD: return {**self.VOLUME_BIAS['low'], 'label': 'low'}
        elif volume < Config.VOLUME_HIGH_THRESHOLD: return {**self.VOLUME_BIAS['medium'], 'label': 'medium'}
        else: return {**self.VOLUME_BIAS['high'], 'label': 'high'}
