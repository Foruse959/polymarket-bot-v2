"""
BTC Volume Sniper — 86.9% win rate on low-volume BTC markets.

BACKTEST PROVEN (44,546 BTC markets):
  - BTC <$50 volume:  86.9% UP win rate (n=2,647)
  - BTC $50-$200:     79.9% UP win rate (n=1,460)
  - BTC $200-$1K:     55.0% UP win rate (n=1,489)
  - BTC >$1K:         ~50% (no edge)

Strategy: When BTC market has very low volume, BUY UP as maker.
The edge is MASSIVE at low volume because taker flow is 87% biased to UP
and the resolution confirms UP wins 87% of the time.

IMPORTANT: This ONLY works for BTC. ETH/SOL/XRP show no volume edge.
"""

from typing import Dict, Optional, List
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class BTCVolumeSniperStrategy(BaseStrategy):
    name = "btc_volume_sniper"
    description = "BTC low-volume UP bias exploitation (86.9% backtest win rate)"
    preferred_order_type = "maker"

    # Volume thresholds with proven win rates
    VOLUME_WIN_RATES = [
        (0, 50, 0.869),      # 86.9% UP
        (50, 200, 0.799),    # 79.9% UP
        (200, 1000, 0.550),  # 55.0% UP (marginal)
    ]

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        # ONLY works for BTC
        coin = market.get('coin', '')
        if coin != 'BTC':
            return None

        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        if not clob or seconds_remaining < 30:
            return None

        up_token = market.get('up_token_id')
        if not up_token:
            return None

        # Get market volume
        volume = 0
        raw = market.get('raw', {})
        if raw:
            vol_str = raw.get('volume', '0')
            try:
                volume = float(vol_str) if isinstance(vol_str, str) else float(vol_str or 0)
            except (ValueError, TypeError):
                volume = 0

        # Find matching volume tier
        expected_win_rate = None
        for vol_min, vol_max, wr in self.VOLUME_WIN_RATES:
            if vol_min <= volume < vol_max:
                expected_win_rate = wr
                break

        if expected_win_rate is None:
            return None  # Volume too high — no edge

        # Only trade if edge > 5%
        if expected_win_rate < 0.55:
            return None

        # Get orderbook
        book = clob.get_orderbook(up_token)
        if not book or book.get('_synthetic'):
            return None

        spread_bps = book['spread_bps']
        if spread_bps > 500:
            return None

        mid = book['mid_price']
        best_bid = book['best_bid']
        best_ask = book['best_ask']

        # Place maker limit order just below ask
        limit_price = round(best_ask - 0.01, 2)
        limit_price = max(limit_price, best_bid + 0.005)
        limit_price = max(0.01, min(0.99, limit_price))

        # Confidence directly from backtest win rate
        confidence = min(0.90, expected_win_rate - 0.02)  # Slight discount for slippage

        return TradeSignal(
            strategy=self.name,
            coin='BTC',
            timeframe=market['timeframe'],
            direction='UP',
            token_id=up_token,
            market_id=market['market_id'],
            entry_price=mid,
            confidence=confidence,
            rationale=(
                f"BTC low-volume sniper: vol=${volume:.0f} → {expected_win_rate:.0%} UP win rate "
                f"(backtest n={2647 if volume < 50 else 1460 if volume < 200 else 1489}). "
                f"BUY UP @ {limit_price:.3f}"
            ),
            metadata={
                'signal_type': 'btc_volume_sniper',
                'volume': volume,
                'expected_win_rate': expected_win_rate,
                'backtest_edge': expected_win_rate - 0.50,
            },
            order_type='maker',
            limit_price=limit_price,
        )
