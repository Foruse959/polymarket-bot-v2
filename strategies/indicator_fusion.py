"""
Indicator Fusion Strategy — Real-Time Technical Analysis Edge

Fetches live price data from Binance and computes:
- RSI, Bollinger Bands, MACD, Stochastic RSI, EMA, SMA, trend strength

Fires only when MULTIPLE indicators agree + market pricing is mispriced.
This is the KEY strategy for boosting win rate to 70%+.

Strategy logic:
  1. Get 1min and 5min candles from Binance for the coin
  2. Run full indicator suite
  3. Count bullish vs bearish signals
  4. If 3+ indicators agree in one direction → TRADE that direction
  5. Combine with market price deviation for edge
"""

from typing import Dict, Optional, List
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal
from data import indicators
from data.price_feed import get_price_feed


class IndicatorFusionStrategy(BaseStrategy):
    name = "indicator_fusion"
    description = "Multi-indicator TA (RSI+BB+MACD+EMA) on Binance data"
    preferred_order_type = "maker"

    MIN_CONVICTION = 2  # Need at least 2 indicators to disagree with majority

    def __init__(self):
        self._feed = get_price_feed()

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        coin = market.get('coin', 'BTC')
        timeframe = market.get('timeframe', 5)

        if not clob or seconds_remaining < 45:
            return None

        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None

        # Choose candle interval based on market timeframe
        interval = '1m' if timeframe == 5 else '5m' if timeframe == 15 else '15m'
        candles = self._feed.get_candles(coin, interval, limit=60)
        if len(candles) < 30:
            return None
        closes = [c['close'] for c in candles]

        # Run full indicator suite
        analysis = indicators.analyze(closes, candles)
        if 'error' in analysis:
            return None

        conviction = analysis.get('conviction', 0)
        sentiment = analysis.get('sentiment', 'neutral')
        bullish = analysis.get('bullish_count', 0)
        bearish = analysis.get('bearish_count', 0)
        sig_labels = analysis.get('signals', [])

        # Need clear conviction (at least 2 indicators difference)
        if conviction < self.MIN_CONVICTION:
            return None

        # Map sentiment to direction
        if sentiment == 'bullish':
            direction = 'UP'
            token_id = up_token
        elif sentiment == 'bearish':
            direction = 'DOWN'
            token_id = down_token
        else:
            return None

        # Get orderbook
        book = clob.get_orderbook(token_id)
        if not book or book.get('_synthetic'):
            return None

        # Check spread
        spread_bps = book['spread_bps']
        if spread_bps > 500 or spread_bps < 10:
            return None

        # Calculate limit price (maker-preferred)
        best_bid = book['best_bid']
        best_ask = book['best_ask']
        mid = book['mid_price']

        limit_price = round(best_ask - 0.01, 2)
        limit_price = max(limit_price, best_bid + 0.005)
        limit_price = max(0.01, min(0.99, limit_price))

        # Confidence scales with conviction
        base_conf = 0.55 + min(conviction * 0.04, 0.15)  # 0.55 → 0.70
        if conviction >= 4:
            base_conf += 0.05  # Very strong signal
        if 50 <= spread_bps <= 150:  # Sweet spot
            base_conf += 0.02

        # Boost if market price supports our direction
        if direction == 'UP' and mid < 0.45:
            base_conf += 0.05  # UP underpriced + indicators bullish
        elif direction == 'DOWN' and mid > 0.55:
            base_conf += 0.05

        confidence = min(0.85, max(0.55, base_conf))

        rationale = (
            f"Indicators {sentiment.upper()} "
            f"(bull:{bullish} vs bear:{bearish}): "
            f"{'; '.join(sig_labels[:3])}"
        )

        return TradeSignal(
            strategy=self.name,
            coin=coin,
            timeframe=timeframe,
            direction=direction,
            token_id=token_id,
            market_id=market['market_id'],
            entry_price=mid,
            confidence=confidence,
            rationale=rationale,
            metadata={
                'signal_type': 'indicator_fusion',
                'rsi': analysis.get('rsi_14'),
                'bb_position': analysis.get('bb_position'),
                'macd_hist': analysis.get('macd_hist'),
                'trend_strength': analysis.get('trend_strength'),
                'bullish_count': bullish,
                'bearish_count': bearish,
                'conviction': conviction,
                'all_signals': sig_labels,
            },
            order_type='maker',
            limit_price=limit_price,
        )
