"""
Strategies for 5min_trade v2.2 — Beast Mode

9 strategies total, ranked by backtest win rate:
1. BTCVolumeSniper: 86.9% win rate on BTC low-volume markets
2. MomentumCascade: 74.4% multi-signal cascade (momentum+vol+time+base)
3. IndicatorFusion: RSI+MACD+BB+EMA live from Binance
4. MicrostructureMaker: Exploit maker-taker wealth transfer
5. MomentumBreakout: BTC streak detection (62-67%)
6. VolumeImbalance: Order flow bias detection
7. MeanReversion: Fair-value reversion
8. MakerEdge: Limit orders on NO side
9. LongshotBias: Overpriced longshot contracts
"""

from .base_strategy import BaseStrategy, TradeSignal
from .btc_volume_sniper import BTCVolumeSniperStrategy
from .momentum_cascade import MomentumCascadeStrategy
from .indicator_fusion import IndicatorFusionStrategy
from .microstructure_maker import MicrostructureMakerStrategy
from .momentum_breakout import MomentumBreakoutStrategy
from .volume_imbalance import VolumeImbalanceStrategy
from .mean_reversion import MeanReversionStrategy
from .maker_edge import MakerEdgeStrategy
from .longshot_bias import LongshotBiasStrategy

# Ordered by backtest win rate (highest first)
ALL_STRATEGIES = [
    BTCVolumeSniperStrategy,      # 86.9% (BTC only, low volume)
    MomentumCascadeStrategy,      # 74.4% (multi-signal cascade)
    IndicatorFusionStrategy,      # ~70% (live TA indicators)
    MicrostructureMakerStrategy,  # ~65% (maker-taker edge)
    MomentumBreakoutStrategy,     # 62-67% (streak-based)
    VolumeImbalanceStrategy,      # ~60% (flow detection)
    MeanReversionStrategy,        # ~58% (fair-value reversion)
    MakerEdgeStrategy,            # ~55% (NO-side limit orders)
    LongshotBiasStrategy,         # ~55% (overpriced longshots)
]

__all__ = [
    'BaseStrategy', 'TradeSignal', 'ALL_STRATEGIES',
    'BTCVolumeSniperStrategy', 'MomentumCascadeStrategy',
    'IndicatorFusionStrategy', 'MicrostructureMakerStrategy',
    'MomentumBreakoutStrategy', 'VolumeImbalanceStrategy',
    'MeanReversionStrategy', 'MakerEdgeStrategy', 'LongshotBiasStrategy',
]
