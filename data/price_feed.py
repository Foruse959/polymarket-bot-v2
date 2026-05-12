"""
Price Feed — Binance REST candle data for technical indicators.

Falls back through multiple Binance endpoints if one is geo-blocked.
Fetches OHLCV for BTC/ETH/SOL/XRP at 1m/5m/15m.
"""

import time
import requests
from typing import List, Dict, Optional
from config import Config


# Try these endpoints in order (some are geo-blocked in certain regions)
BINANCE_ENDPOINTS = [
    'https://api.binance.com',
    'https://api1.binance.com',
    'https://api2.binance.com',
    'https://api3.binance.com',
    'https://data-api.binance.vision',  # Public data endpoint (less geo-blocked)
]


class PriceFeed:
    def __init__(self):
        self.endpoint = BINANCE_ENDPOINTS[0]
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
        self._candle_cache: Dict[str, Dict] = {}
        self._price_cache: Dict[str, Dict] = {}
        self.cache_ttl_seconds = 30
        self._endpoint_tested = False

    def _test_and_select_endpoint(self):
        """Find a working Binance endpoint (some are geo-blocked)."""
        for url in BINANCE_ENDPOINTS:
            try:
                resp = self.session.get(f"{url}/api/v3/ping", timeout=3)
                if resp.status_code == 200:
                    self.endpoint = url
                    print(f"[PRICE_FEED] ✅ Using Binance endpoint: {url}", flush=True)
                    return
            except Exception:
                continue
        print(f"[PRICE_FEED] ⚠️  All Binance endpoints blocked/unreachable. Indicators disabled.", flush=True)
        self.endpoint = None

    def get_candles(self, coin: str, interval: str = '1m', limit: int = 100) -> List[Dict]:
        """Get OHLCV candles with caching and endpoint fallback."""
        if not self._endpoint_tested:
            self._test_and_select_endpoint()
            self._endpoint_tested = True

        if self.endpoint is None:
            return []

        coin = coin.upper()
        symbol = Config.BINANCE_CANDLE_SYMBOLS.get(coin)
        if not symbol:
            return []

        cache_key = f"{coin}_{interval}_{limit}"
        now = time.time()
        cached = self._candle_cache.get(cache_key)
        if cached and (now - cached['ts']) < self.cache_ttl_seconds:
            return cached['candles']

        try:
            resp = self.session.get(
                f"{self.endpoint}/api/v3/klines",
                params={'symbol': symbol, 'interval': interval, 'limit': limit},
                timeout=5
            )
            if resp.status_code == 200:
                raw = resp.json()
                candles = [{
                    'open_time': int(k[0]), 'open': float(k[1]),
                    'high': float(k[2]), 'low': float(k[3]),
                    'close': float(k[4]), 'volume': float(k[5]),
                    'close_time': int(k[6]),
                } for k in raw]
                self._candle_cache[cache_key] = {'ts': now, 'candles': candles}
                return candles
            elif resp.status_code == 451:
                # Geo-blocked — try next endpoint
                print(f"[PRICE_FEED] ⚠️  {self.endpoint} geo-blocked (451). Trying fallback...", flush=True)
                idx = BINANCE_ENDPOINTS.index(self.endpoint) if self.endpoint in BINANCE_ENDPOINTS else 0
                if idx + 1 < len(BINANCE_ENDPOINTS):
                    self.endpoint = BINANCE_ENDPOINTS[idx + 1]
                    print(f"[PRICE_FEED] 🔄 Switched to: {self.endpoint}", flush=True)
                else:
                    print(f"[PRICE_FEED] ⚠️  All endpoints blocked. Disabling indicators.", flush=True)
                    self.endpoint = None
                return cached['candles'] if cached else []
            else:
                return cached['candles'] if cached else []
        except Exception as e:
            return cached['candles'] if cached else []

    def get_current_price(self, coin: str) -> Optional[float]:
        if self.endpoint is None:
            return None
        coin = coin.upper()
        symbol = Config.BINANCE_CANDLE_SYMBOLS.get(coin)
        if not symbol:
            return None
        cached = self._price_cache.get(coin)
        now = time.time()
        if cached and (now - cached['ts']) < 5:
            return cached['price']
        try:
            resp = self.session.get(
                f"{self.endpoint}/api/v3/ticker/price",
                params={'symbol': symbol}, timeout=3
            )
            if resp.status_code == 200:
                price = float(resp.json().get('price', 0))
                self._price_cache[coin] = {'ts': now, 'price': price}
                return price
        except Exception:
            pass
        return cached['price'] if cached else None

    def get_closes(self, coin: str, interval: str = '1m', limit: int = 50) -> List[float]:
        return [c['close'] for c in self.get_candles(coin, interval, limit)]


_instance = None

def get_price_feed() -> PriceFeed:
    global _instance
    if _instance is None:
        _instance = PriceFeed()
    return _instance
