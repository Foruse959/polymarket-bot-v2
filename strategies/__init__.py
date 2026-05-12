"""
Strategies for 5min_trade v2.2 — Beast Mode

Research-backed strategies with live technical indicators:
- IndicatorFusion: RSI+MACD+BB+EMA live from Binance (STRONGEST)
- MicrostructureMaker: Exploit maker-taker wealth transfer
- MomentumBreakout: BTC streak detection (62-67%)
- VolumeImbalance: Order flow bias detection
- MeanReversion: Fair-value reversion
- MakerEdge: Limit orders on NO side
- LongshotBias: Overpriced longshot contracts
"""

from .base_strategy import BaseStrategy, TradeSignal
from .indicator_fusion import IndicatorFusionStrategy
from .microstructure_maker import MicrostructureMakerStrategy
from .momentum_breakout import MomentumBreakoutStrategy
from .volume_imbalance import VolumeImbalanceStrategy
from .mean_reversion import MeanReversionStrategy
from .maker_edge import MakerEdgeStrategy
from .longshot_bias import LongshotBiasStrategy

ALL_STRATEGIES = [
    IndicatorFusionStrategy,
    MicrostructureMakerStrategy,
    MomentumBreakoutStrategy,
    VolumeImbalanceStrategy,
    MeanReversionStrategy,
    MakerEdgeStrategy,
    LongshotBiasStrategy,
]

__all__ = [
    'BaseStrategy', 'TradeSignal', 'ALL_STRATEGIES',
    'IndicatorFusionStrategy', 'MicrostructureMakerStrategy',
    'MomentumBreakoutStrategy', 'VolumeImbalanceStrategy',
    'MeanReversionStrategy', 'MakerEdgeStrategy', 'LongshotBiasStrategy',
]
