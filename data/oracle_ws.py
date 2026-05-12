"""
Binance Oracle Lead — Real-time 1s Kline WebSocket

Based on research: Binance leads Polymarket by 4-12 seconds via the
Chainlink Data Streams oracle delay. If BTC spikes up on Binance, the
Polymarket UP token will follow — but you see the move first.

This is the REAL edge for 5-min markets.

Usage:
    oracle = BinanceOracleWS()
    await oracle.start()  # runs as asyncio task
    ...
    signal = oracle.get_signal('BTC')  # latest actionable signal
    analysis = oracle.get_lead_analysis('BTC')  # full breakdown

The 1-second stream catches impulses 2-3s faster than 1m REST polling.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Callable
from collections import deque

from config import Config


COIN_STREAMS = {
    'BTC': 'btcusdt@kline_1s',
    'ETH': 'ethusdt@kline_1s',
    'SOL': 'solusdt@kline_1s',
    'XRP': 'xrpusdt@kline_1s',
}


class OracleLeadSignal:
    """A real-time Binance impulse that Polymarket has not yet priced in."""

    __slots__ = ('coin', 'direction', 'magnitude', 'confidence',
                 'seconds_since_move', 'binance_price', 'reason', 'timestamp')

    def __init__(self, coin, direction, magnitude, confidence,
                 seconds_since_move, binance_price, reason):
        self.coin = coin
        self.direction = direction          # "UP" or "DOWN"
        self.magnitude = magnitude          # % size of the move
        self.confidence = confidence        # 0-1
        self.seconds_since_move = seconds_since_move
        self.binance_price = binance_price
        self.reason = reason
        self.timestamp = time.time()

    @property
    def is_actionable(self) -> bool:
        """Within 10s of the move — Polymarket likely still stale."""
        return time.time() - self.timestamp < 10

    def __repr__(self):
        return (f"OracleLeadSignal({self.coin} {self.direction} "
                f"{self.magnitude:.2f}% conf={self.confidence:.0%})")


class BinanceOracleWS:
    """
    1-second Binance kline WebSocket for oracle lead detection.

    - Connects to combined stream for all enabled coins
    - Buffers last 60s of 1s candles per coin
    - Detects 3 impulse types: single-candle, 3s rolling, 5s acceleration
    - Exports signals via get_signal() / get_lead_analysis()
    """

    def __init__(self, enabled_coins: Optional[List[str]] = None,
                 log_callback: Optional[Callable] = None):
        self.coins = [c for c in (enabled_coins or list(COIN_STREAMS.keys()))
                      if c in COIN_STREAMS]
        self._buffers: Dict[str, deque] = {c: deque(maxlen=60) for c in self.coins}
        self._latest_signals: Dict[str, OracleLeadSignal] = {}
        self._callbacks: List[Callable] = []
        self._running = False
        self._ws = None
        self._connected = False
        self._last_msg_ts = 0.0
        self.log = log_callback or (lambda lvl, msg: None)

        # Impulse detection parameters (tunable)
        self.impulse_threshold_pct = 0.05   # 0.05% in 1s = significant
        self.strong_impulse_pct = 0.15      # 0.15% in 1-3s = strong

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_msg_age_sec(self) -> float:
        return time.time() - self._last_msg_ts if self._last_msg_ts else 999

    def on_signal(self, callback: Callable):
        """Register a callback fired on every new signal."""
        self._callbacks.append(callback)

    def get_signal(self, coin: str) -> Optional[OracleLeadSignal]:
        """Get latest actionable signal for a coin (None if stale or missing)."""
        sig = self._latest_signals.get(coin)
        return sig if (sig and sig.is_actionable) else None

    def get_lead_analysis(self, coin: str) -> Dict:
        """Full oracle lead analysis. Consumable by strategies."""
        buf = self._buffers.get(coin, deque())
        if len(buf) < 5:
            return {'has_lead': False, 'direction': 'NEUTRAL', 'strength': 0.0,
                    'move_pct': 0.0, 'vol_ratio': 0.0, 'current_price': 0.0,
                    'active_signal': False, 'signal': None}

        prices = [c['close'] for c in buf]
        volumes = [c['volume'] for c in buf]

        recent_move = (prices[-1] - prices[-5]) / prices[-5] * 100
        vol_recent = sum(volumes[-3:])
        vol_avg = (sum(volumes) / len(volumes) * 3) if volumes else 0.0
        vol_ratio = vol_recent / max(vol_avg, 1e-6)

        if recent_move > 0.02:
            direction = 'UP'
        elif recent_move < -0.02:
            direction = 'DOWN'
        else:
            direction = 'NEUTRAL'

        strength = min(1.0, abs(recent_move) / 0.20 * vol_ratio)
        sig = self.get_signal(coin)

        return {
            'has_lead': direction != 'NEUTRAL' and strength > 0.3,
            'direction': direction,
            'strength': strength,
            'move_pct': recent_move,
            'vol_ratio': vol_ratio,
            'current_price': prices[-1],
            'active_signal': sig is not None,
            'signal': sig,
        }

    async def start(self):
        """Connect to Binance WS and stream candles until stop() is called."""
        try:
            import websockets
        except ImportError:
            self.log('WARN', "websockets not installed — oracle WS disabled")
            return

        streams = '/'.join(COIN_STREAMS[c] for c in self.coins)
        url = f"wss://stream.binance.com:9443/ws/{streams}"
        self._running = True
        self.log('INIT', f"Binance oracle WS connecting ({len(self.coins)} coins, 1s candles)")

        backoff = 3
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20,
                                              ping_timeout=60) as ws:
                    self._ws = ws
                    self._connected = True
                    self.log('INIT', "Binance oracle WS connected")
                    backoff = 3
                    async for raw in ws:
                        if not self._running:
                            break
                        self._last_msg_ts = time.time()
                        try:
                            msg = json.loads(raw)
                            self._process_message(msg)
                        except (json.JSONDecodeError, KeyError):
                            continue
                    self._connected = False
            except Exception as e:
                self._connected = False
                if self._running:
                    self.log('WARN', f"Binance oracle WS: {e} — reconnect in {backoff}s")
                    await asyncio.sleep(backoff)
                    backoff = min(30, backoff + 2)

    def stop(self):
        self._running = False

    # ─────────────────────────────────────────────────
    # Internal message processing
    # ─────────────────────────────────────────────────

    def _process_message(self, msg: Dict):
        data = msg.get('data') or msg
        kline = data.get('k')
        if not kline:
            return

        symbol = kline.get('s', '').upper()
        coin = None
        for c in self.coins:
            if symbol.startswith(c):
                coin = c
                break
        if not coin:
            return

        candle = {
            'open': float(kline['o']),
            'high': float(kline['h']),
            'low': float(kline['l']),
            'close': float(kline['c']),
            'volume': float(kline['v']),
            'ts': time.time(),
            'is_closed': kline.get('x', False),
        }
        self._buffers[coin].append(candle)
        self._check_impulse(coin, candle)

    def _check_impulse(self, coin: str, candle: Dict):
        buf = self._buffers[coin]
        if len(buf) < 3:
            return
        close = candle['close']

        # 1-second single-candle impulse
        single = (candle['close'] - candle['open']) / candle['open'] * 100
        if abs(single) >= self.impulse_threshold_pct:
            direction = 'UP' if single > 0 else 'DOWN'
            conf = min(0.8, abs(single) / self.strong_impulse_pct)
            self._emit(OracleLeadSignal(coin, direction, abs(single), conf,
                                        0, close, f"1s impulse: {single:+.3f}%"))
            return

        # 3-second rolling impulse
        if len(buf) >= 3:
            price_3s = list(buf)[-3]['open']
            move_3s = (close - price_3s) / price_3s * 100
            if abs(move_3s) >= self.strong_impulse_pct:
                direction = 'UP' if move_3s > 0 else 'DOWN'
                conf = min(0.9, abs(move_3s) / (self.strong_impulse_pct * 2))
                self._emit(OracleLeadSignal(coin, direction, abs(move_3s), conf,
                                            3, close, f"3s rolling: {move_3s:+.3f}%"))
                return

        # 5-second acceleration
        if len(buf) >= 5:
            prices = [c['close'] for c in list(buf)[-5:]]
            first = (prices[2] - prices[0]) / prices[0] * 100
            second = (prices[4] - prices[2]) / prices[2] * 100
            accel = second - first
            if abs(accel) > self.impulse_threshold_pct:
                direction = 'UP' if accel > 0 else 'DOWN'
                conf = min(0.7, abs(accel) / 0.3)
                self._emit(OracleLeadSignal(coin, direction, abs(accel), conf,
                                            2, close, f"5s accel: {accel:+.3f}%"))

    def _emit(self, signal: OracleLeadSignal):
        self._latest_signals[signal.coin] = signal
        for cb in self._callbacks:
            try:
                cb(signal)
            except Exception:
                pass


# Singleton access
_instance: Optional[BinanceOracleWS] = None


def get_oracle_ws() -> BinanceOracleWS:
    global _instance
    if _instance is None:
        _instance = BinanceOracleWS(enabled_coins=list(Config.ENABLED_COINS))
    return _instance
