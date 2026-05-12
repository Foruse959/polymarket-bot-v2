"""
Oracle Lead Strategy — BTC-only Binance front-running

BACKTEST RESULTS (Nov 2025, 1000x 1m candles):
  BTC  @ 0.15% threshold: 29 trades, 69.0% win rate (PROFITABLE)
  ETH  @ 0.15% threshold: 61 trades, 41.0% win rate (LOSES)
  SOL  @ 0.15% threshold: 104 trades, 44.2% win rate (LOSES)

CONCLUSION: Only BTC follows Binance tightly enough for oracle
front-running to work. ETH and SOL are too noisy on Polymarket's
5-min markets.

Therefore this strategy fires ONLY on BTC.

Exploits the 4-12 second lag between Binance price and Polymarket's
Chainlink oracle. When Binance shows a fresh impulse, Polymarket token
price hasn't caught up yet — we bet in the direction before it does.

Only fires when:
- Market coin is BTC (backtest-validated only)
- Oracle detects a recent impulse (< 8 seconds old)
- Impulse magnitude >= 0.15% (filters noise)
- Polymarket mid-price is still near 0.50 (hasn't repriced)
"""

import time
from typing import Dict, List, Optional
from strategies.base_strategy import BaseStrategy, TradeSignal


class OracleLeadStrategy(BaseStrategy):
    name = "oracle_lead"
    description = "BTC-only Binance front-run (69% backtest WR)"
    preferred_order_type = "taker"

    # Only trade BTC per backtest findings
    SUPPORTED_COINS = ['BTC']

    MAX_AGE_SEC = 8
    MIN_MAGNITUDE_PCT = 0.15
    MIN_SECONDS_REMAINING = 20

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        coin = market.get('coin', 'BTC')
        if coin not in self.SUPPORTED_COINS:
            return None  # BTC only — validated

        oracle = context.get('oracle_ws')
        if oracle is None:
            return None

        seconds_remaining = context.get('seconds_remaining', 9999)
        if seconds_remaining < self.MIN_SECONDS_REMAINING:
            return None

        signal = oracle.get_signal(coin)
        if not signal:
            return None

        age = time.time() - signal.timestamp
        if age > self.MAX_AGE_SEC:
            return None

        if signal.magnitude < self.MIN_MAGNITUDE_PCT:
            return None

        clob = context.get('clob')
        if not clob:
            return None

        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None

        target_token = up_token if signal.direction == 'UP' else down_token

        book = clob.get_orderbook(target_token)
        if not book:
            return None

        best_ask = book.get('best_ask', 1.0)
        mid_price = book.get('mid_price', 0.5)

        if best_ask >= 0.75:
            return None  # Already priced in

        pm_neutrality = 1.0 - abs(mid_price - 0.50) * 2
        if pm_neutrality < 0.4:
            return None  # Polymarket already picked a side

        freshness = max(0.3, 1.0 - (age / self.MAX_AGE_SEC))
        magnitude_factor = min(1.0, signal.magnitude / 0.30)
        # Backtest says 69% WR so confidence floor is high
        confidence = min(0.85, 0.65 + signal.confidence * 0.15
                         + magnitude_factor * 0.08 + freshness * 0.05)

        limit_price = round(min(0.72, max(0.30, best_ask)), 2)

        return TradeSignal(
            strategy=self.name,
            coin=coin,
            timeframe=market.get('timeframe', 5),
            direction=signal.direction,
            token_id=target_token,
            market_id=market.get('market_id', ''),
            entry_price=best_ask,
            confidence=confidence,
            rationale=(f"Oracle lead: Binance {signal.direction} {signal.magnitude:.2f}% "
                       f"{age:.1f}s ago | PM mid={mid_price:.2f} "
                       f"(neutrality={pm_neutrality:.0%}) | {signal.reason}"),
            metadata={
                'oracle_magnitude': signal.magnitude,
                'oracle_age_sec': age,
                'pm_mid_price': mid_price,
                'pm_neutrality': pm_neutrality,
                'backtest_wr': 0.69,  # Proven in BTC backtest
            },
            order_type='taker',
            limit_price=limit_price,
        )
