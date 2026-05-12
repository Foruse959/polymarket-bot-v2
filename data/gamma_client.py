"""
Gamma API Client — Fast parallel market discovery for BTC/ETH/SOL/XRP updown.

SPEED OPTIMIZATIONS:
- Parallel slug lookups (all coins × timeframes at once)
- Session pooling (persistent HTTP connection)
- No artificial sleep
- TTL cache (10s) for recently-found markets
"""

import json
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Config


class GammaClient:
    """Parallel market discovery on Polymarket Gamma API."""

    def __init__(self):
        self.base_url = Config.GAMMA_API_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'5min-trade/{Config.VERSION}',
            'Accept': 'application/json',
        })
        self._executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix='gamma')
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 10.0

    def _check_market_by_slug(self, slug: str) -> Optional[Dict]:
        """Fetch a single market by slug (with cache)."""
        now = time.time()
        cached = self._cache.get(slug)
        if cached and (now - cached['ts']) < self._cache_ttl:
            return cached['event']
        try:
            r = self.session.get(
                f"{self.base_url}/events",
                params={'slug': slug},
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                events = data if isinstance(data, list) else data.get('events', [])
                event = events[0] if events else None
                self._cache[slug] = {'ts': now, 'event': event}
                return event
        except Exception:
            pass
        return None

    def discover_markets(self, coins=None, timeframes=None) -> List[Dict]:
        """
        Discover ACTIVE, NON-CLOSED updown markets in parallel.
        """
        coins = coins or Config.ENABLED_COINS
        timeframes = timeframes or Config.ENABLED_TIMEFRAMES

        now = datetime.now(timezone.utc)
        current_ts = int(now.timestamp())
        five_min = 5 * 60
        rounded_ts = (current_ts // five_min) * five_min

        # Build all slugs to check (parallel)
        slugs_to_check = []
        for offset in range(-1, 4):
            ts = rounded_ts + (offset * five_min)
            if ts < current_ts - 300:
                continue
            for coin in [c.lower() for c in coins]:
                for tf in timeframes:
                    slugs_to_check.append({
                        'slug': f"{coin}-updown-{tf}m-{ts}",
                        'coin': coin.upper(),
                        'tf': tf,
                        'ts': ts,
                        'offset': offset,
                    })

        # Parallel fetch
        all_markets = []
        futures = {
            self._executor.submit(self._check_market_by_slug, s['slug']): s
            for s in slugs_to_check
        }

        for future in as_completed(futures, timeout=15):
            meta = futures[future]
            try:
                event = future.result()
            except Exception:
                continue

            if not event:
                continue

            if not event.get('active') or event.get('closed') or event.get('archived'):
                continue

            markets = event.get('markets', [])
            if not markets:
                continue

            m = markets[0]
            raw_ids = m.get('clobTokenIds', '[]')
            if isinstance(raw_ids, str):
                try:
                    clob_ids = json.loads(raw_ids)
                except Exception:
                    clob_ids = []
            else:
                clob_ids = raw_ids if isinstance(raw_ids, list) else []
            if len(clob_ids) < 2:
                continue

            # End date
            end_str = event.get('endDate')
            seconds_remaining = meta['tf'] * 60
            if end_str:
                try:
                    end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    if end_dt < now:
                        continue
                    seconds_remaining = int((end_dt - now).total_seconds())
                except Exception:
                    pass

            all_markets.append({
                'market_id': meta['slug'],
                'event_slug': meta['slug'],
                'coin': meta['coin'],
                'timeframe': meta['tf'],
                'question': event.get('title', ''),
                'end_date': end_str,
                'seconds_remaining': seconds_remaining,
                'up_token_id': clob_ids[0],
                'down_token_id': clob_ids[1],
                'category': 'crypto',
                'spread_multiplier': 1.5,
                'epoch_timestamp': meta['ts'],
                'raw': m,
            })

        all_markets.sort(key=lambda x: abs(x['seconds_remaining'] - 150))
        return all_markets
