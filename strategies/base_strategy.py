"""
Base Strategy — Abstract interface for all trading strategies.

Updated for v2 with maker order support.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class TradeSignal:
    """Represents a trading signal from a strategy."""

    def __init__(
        self,
        strategy: str,
        coin: str,
        timeframe: int,
        direction: str,     # 'UP' or 'DOWN'
        token_id: str,
        market_id: str,
        entry_price: float,
        confidence: float,
        rationale: str,
        metadata: Dict = None,
        order_type: str = 'maker',  # 'maker' or 'taker'
        limit_price: float = None,  # For maker orders
        take_profit: float = None,
        stop_loss: float = None,
    ):
        self.strategy = strategy
        self.coin = coin
        self.timeframe = timeframe
        self.direction = direction
        self.token_id = token_id
        self.market_id = market_id
        self.entry_price = entry_price
        self.confidence = confidence
        self.rationale = rationale
        self.metadata = metadata or {}
        self.order_type = order_type
        self.limit_price = limit_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss

    def to_dict(self) -> Dict:
        return {
            'strategy': self.strategy,
            'coin': self.coin,
            'timeframe': self.timeframe,
            'direction': self.direction,
            'token_id': self.token_id,
            'market_id': self.market_id,
            'entry_price': self.entry_price,
            'confidence': self.confidence,
            'rationale': self.rationale,
            'metadata': self.metadata,
            'order_type': self.order_type,
            'limit_price': self.limit_price,
            'take_profit': self.take_profit,
            'stop_loss': self.stop_loss,
        }

    def __repr__(self):
        order_info = f" {self.order_type}" if self.order_type else ""
        limit_info = f" @ limit {self.limit_price:.4f}" if self.limit_price else ""
        return (f"Signal({self.strategy}{order_info} {self.coin} {self.direction} "
                f"@{self.entry_price:.4f}{limit_info} conf={self.confidence:.0%})")


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    name: str = "base"
    description: str = ""
    preferred_order_type: str = "maker"  # v2 prefers maker orders

    @abstractmethod
    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """
        Analyze a market and optionally return a trade signal.

        Args:
            market: Market data from GammaClient.discover_markets()
            context: {
                'clob': ClobClient,
                'seconds_remaining': int,
                'binance_price': float (optional),
                'category': str,
            }

        Returns:
            TradeSignal if a trade should be made, None otherwise.
        """
        pass

    @abstractmethod
    def get_suitable_timeframes(self) -> List[int]:
        """Return list of timeframes this strategy works best with."""
        pass

    def get_preferred_order_type(self) -> str:
        """Return preferred order type for this strategy."""
        return self.preferred_order_type
