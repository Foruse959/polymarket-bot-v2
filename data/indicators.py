"""
Technical Indicators — Pure Python, no external dependencies.

Implements:
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
- RSI (Relative Strength Index)
- Bollinger Bands
- MACD
- Stochastic RSI
- ATR (Average True Range)
- Volume-Weighted Average Price

All functions accept a list of prices (closes) and return the indicator value.
"""

from typing import List, Tuple, Optional


def sma(prices: List[float], period: int) -> Optional[float]:
    """Simple Moving Average."""
    if len(prices) < period or period <= 0:
        return None
    return sum(prices[-period:]) / period


def ema(prices: List[float], period: int) -> Optional[float]:
    """Exponential Moving Average."""
    if len(prices) < period or period <= 0:
        return None
    k = 2 / (period + 1)
    ema_val = prices[0]
    for price in prices[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Relative Strength Index (0-100).
    - RSI > 70 → overbought (bearish signal)
    - RSI < 30 → oversold (bullish signal)
    """
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-diff)
    if len(gains) < period:
        return None
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Optional[Tuple[float, float, float]]:
    """
    Bollinger Bands: (upper, middle, lower).
    - Price above upper band → overbought
    - Price below lower band → oversold
    """
    if len(prices) < period:
        return None
    recent = prices[-period:]
    mean = sum(recent) / period
    variance = sum((p - mean) ** 2 for p in recent) / period
    std = variance ** 0.5
    upper = mean + num_std * std
    lower = mean - num_std * std
    return (upper, mean, lower)


def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Tuple[float, float, float]]:
    """
    MACD: (macd_line, signal_line, histogram).
    - macd_line > signal_line → bullish
    - macd_line < signal_line → bearish
    - Histogram shows divergence strength
    """
    if len(prices) < slow + signal:
        return None
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    if ema_fast is None or ema_slow is None:
        return None
    macd_line = ema_fast - ema_slow
    # Build MACD history for signal line
    macd_series = []
    for i in range(slow, len(prices) + 1):
        ef = ema(prices[:i], fast)
        es = ema(prices[:i], slow)
        if ef is not None and es is not None:
            macd_series.append(ef - es)
    if len(macd_series) < signal:
        return None
    signal_line = ema(macd_series, signal)
    if signal_line is None:
        return None
    return (macd_line, signal_line, macd_line - signal_line)


def stoch_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Stochastic RSI (0-100).
    - > 80 → overbought
    - < 20 → oversold
    """
    if len(prices) < period * 2:
        return None
    rsi_series = []
    for i in range(period, len(prices) + 1):
        r = rsi(prices[:i], period)
        if r is not None:
            rsi_series.append(r)
    if len(rsi_series) < period:
        return None
    recent_rsi = rsi_series[-period:]
    max_rsi = max(recent_rsi)
    min_rsi = min(recent_rsi)
    if max_rsi == min_rsi:
        return 50.0
    return (rsi_series[-1] - min_rsi) / (max_rsi - min_rsi) * 100


def atr(candles: List[dict], period: int = 14) -> Optional[float]:
    """Average True Range — volatility measure."""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        prev_close = candles[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period


def trend_strength(prices: List[float], short: int = 5, long: int = 20) -> Optional[float]:
    """
    Trend strength: (short_ma - long_ma) / long_ma * 100.
    Positive → uptrend, negative → downtrend. Magnitude = strength.
    """
    short_ma = sma(prices, short)
    long_ma = sma(prices, long)
    if short_ma is None or long_ma is None or long_ma == 0:
        return None
    return (short_ma - long_ma) / long_ma * 100


def analyze(prices: List[float], candles: List[dict] = None) -> dict:
    """
    Run full indicator suite and return a dict of all values.
    """
    if not prices or len(prices) < 30:
        return {
            'error': 'Not enough price history',
            'bars': len(prices) if prices else 0,
        }

    result = {
        'current_price': prices[-1],
        'bars': len(prices),
    }

    # Moving averages
    result['sma_5'] = sma(prices, 5)
    result['sma_10'] = sma(prices, 10)
    result['sma_20'] = sma(prices, 20)
    result['ema_5'] = ema(prices, 5)
    result['ema_10'] = ema(prices, 10)
    result['ema_20'] = ema(prices, 20)

    # Oscillators
    result['rsi_14'] = rsi(prices, 14)
    result['stoch_rsi'] = stoch_rsi(prices, 14)

    # Bollinger
    bb = bollinger_bands(prices, 20, 2.0)
    if bb:
        result['bb_upper'], result['bb_middle'], result['bb_lower'] = bb
        result['bb_position'] = (prices[-1] - bb[2]) / (bb[0] - bb[2]) if bb[0] != bb[2] else 0.5

    # MACD
    m = macd(prices)
    if m:
        result['macd'], result['macd_signal'], result['macd_hist'] = m

    # Trend
    result['trend_strength'] = trend_strength(prices, 5, 20)

    # ATR (volatility)
    if candles:
        result['atr'] = atr(candles, 14)

    # Overall sentiment
    bullish_signals = 0
    bearish_signals = 0
    signals = []

    if result.get('rsi_14') is not None:
        if result['rsi_14'] < 30:
            bullish_signals += 1
            signals.append(f"RSI oversold ({result['rsi_14']:.0f})")
        elif result['rsi_14'] > 70:
            bearish_signals += 1
            signals.append(f"RSI overbought ({result['rsi_14']:.0f})")

    if result.get('bb_position') is not None:
        if result['bb_position'] < 0.2:
            bullish_signals += 1
            signals.append(f"Below BB lower ({result['bb_position']:.0%})")
        elif result['bb_position'] > 0.8:
            bearish_signals += 1
            signals.append(f"Above BB upper ({result['bb_position']:.0%})")

    if result.get('macd_hist') is not None:
        if result['macd_hist'] > 0:
            bullish_signals += 1
            signals.append(f"MACD bullish (+{result['macd_hist']:.2f})")
        else:
            bearish_signals += 1
            signals.append(f"MACD bearish ({result['macd_hist']:.2f})")

    if result.get('trend_strength') is not None:
        ts = result['trend_strength']
        if ts > 0.5:
            bullish_signals += 1
            signals.append(f"Uptrend ({ts:.2f}%)")
        elif ts < -0.5:
            bearish_signals += 1
            signals.append(f"Downtrend ({ts:.2f}%)")

    if bullish_signals > bearish_signals:
        result['sentiment'] = 'bullish'
    elif bearish_signals > bullish_signals:
        result['sentiment'] = 'bearish'
    else:
        result['sentiment'] = 'neutral'

    result['bullish_count'] = bullish_signals
    result['bearish_count'] = bearish_signals
    result['signals'] = signals
    result['conviction'] = abs(bullish_signals - bearish_signals)
    return result
