"""
Strategies for 5min_trade v2.1 — Microstructure Edge

Research-backed strategies exploiting:
- Maker-taker wealth transfer (+1.12% edge per Becker 2026)
- BTC momentum streaks (62-67% accuracy)
- Volume-based taker bias (78.9% UP in low volume)
- Mean reversion to 50% fair value
"""

from .base_strategy import BaseStrategy, TradeSignal
from .microstructure_maker import MicrostructureMakerStrategy
from .momentum_breakout import MomentumBreakoutStrategy
from .volume_imbalance import VolumeImbalanceStrategy
from .mean_reversion import MeanReversionStrategy
from .maker_edge import MakerEdgeStrategy
from .longshot_bias import LongshotBiasStrategy
from .dynamic_picker import DynamicPicker

ALL_STRATEGIES = [
    MicrostructureMakerStrategy,
    MomentumBreakoutStrategy,
    VolumeImbalanceStrategy,
    MeanReversionStrategy,
    MakerEdgeStrategy,
    LongshotBiasStrategy,
]

__all__ = [
    'BaseStrategy', 'TradeSignal', 'ALL_STRATEGIES',
    'MicrostructureMakerStrategy', 'MomentumBreakoutStrategy',
    'VolumeImbalanceStrategy', 'MeanReversionStrategy',
    'MakerEdgeStrategy', 'LongshotBiasStrategy', 'DynamicPicker',
]
