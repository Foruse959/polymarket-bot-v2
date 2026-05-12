"""
Momentum Breakout — BTC streak detection (62-67% accuracy).
After 2+ consecutive UPs → 62% next UP. After 5 → 67.4%.
BTC has 54.5% inherent UP bias on 5m. Best hours: 15-18, 22 UTC.
"""
from typing import Dict, Optional, List
from collections import deque
from datetime import datetime, timezone
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal

class MomentumBreakoutStrategy(BaseStrategy):
    name = "momentum_breakout"
    description = "Trade with BTC momentum using streak detection and time signals"
    preferred_order_type = "maker"
    UP_STREAK_PROBS = {2: 0.620, 3: 0.630, 4: 0.647, 5: 0.674}
    DOWN_STREAK_PROBS = {2: 0.553, 3: 0.556, 4: 0.543, 5: 0.538}
    BTC_BULLISH_HOURS = {15, 16, 18, 22, 11}
    COIN_BASE_RATES = {'BTC': 0.545, 'ETH': 0.504, 'SOL': 0.501, 'XRP': 0.491}

    def __init__(self):
        self.outcome_history: Dict[str, deque] = {}

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        if not clob or seconds_remaining < 45:
            return None
        coin = market.get('coin', 'BTC')
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        if not up_token or not down_token:
            return None
        coin_key = f"{coin}_{market.get('timeframe', 5)}"
        history = self.outcome_history.get(coin_key, deque(maxlen=10))
        signal = self._composite_signal(coin, history, market, clob, up_token, down_token)
        if not signal:
            return None
        direction = signal['direction']
        token_id = up_token if direction == 'UP' else down_token
        book = clob.get_orderbook(token_id)
        if not book or book.get('_synthetic') or book['spread_bps'] > 500:
            return None
        limit_price = round(book['best_ask'] - 0.01, 2)
        limit_price = max(limit_price, book['best_bid'] + 0.005)
        limit_price = max(0.01, min(0.99, limit_price))
        return TradeSignal(
            strategy=self.name, coin=coin, timeframe=market['timeframe'],
            direction=direction, token_id=token_id, market_id=market['market_id'],
            entry_price=book['mid_price'], confidence=signal['confidence'],
            rationale=signal['rationale'],
            metadata={'signal_type': 'momentum_composite', 'signals': signal.get('labels', [])},
            order_type='maker', limit_price=limit_price,
        )

    def _composite_signal(self, coin, history, market, clob, up_token, down_token):
        up_score, down_score = 0.0, 0.0
        labels = []
        # Streak signal
        if len(history) >= 2:
            up_streak = sum(1 for x in reversed(history) if x == 'UP')
            down_streak = sum(1 for x in reversed(history) if x == 'DOWN')
            if history[-1] != 'UP': up_streak = 0
            if history[-1] != 'DOWN': down_streak = 0
            if up_streak >= 2:
                prob = self.UP_STREAK_PROBS.get(min(up_streak, 5), 0.62)
                up_score += (prob - 0.5) * 0.40
                labels.append(f"{up_streak}x UP streak ({prob:.0%})")
            elif down_streak >= 2:
                prob = self.DOWN_STREAK_PROBS.get(min(down_streak, 5), 0.55)
                down_score += (prob - 0.5) * 0.40
                labels.append(f"{down_streak}x DOWN streak ({prob:.0%})")
        # Time-of-day
        hour = datetime.now(timezone.utc).hour
        if coin == 'BTC' and hour in self.BTC_BULLISH_HOURS:
            up_score += 0.05 * 0.20
            labels.append(f"Bullish hour {hour}:00")
        # Base rate
        base = self.COIN_BASE_RATES.get(coin, 0.50)
        if base > 0.51:
            up_score += (base - 0.50) * 0.25
            labels.append(f"{coin} base rate {base:.1%}")
        elif base < 0.49:
            down_score += (0.50 - base) * 0.25
        if up_score > down_score and up_score > 0.02:
            conf = 0.45 + min(up_score * 3, 0.40)
            return {'direction': 'UP', 'confidence': min(0.85, conf), 'rationale': f"Momentum UP: {'; '.join(labels)}", 'labels': labels}
        elif down_score > up_score and down_score > 0.02:
            conf = 0.45 + min(down_score * 3, 0.40)
            return {'direction': 'DOWN', 'confidence': min(0.85, conf), 'rationale': f"Momentum DOWN: {'; '.join(labels)}", 'labels': labels}
        return None

    def record_outcome(self, coin: str, timeframe: int, outcome: str):
        key = f"{coin}_{timeframe}"
        if key not in self.outcome_history:
            self.outcome_history[key] = deque(maxlen=10)
        self.outcome_history[key].append(outcome)
