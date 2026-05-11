"""
Gamma API Client - Fixed for Up/Down Market Discovery

Discovers only ACTIVE, TRADEABLE updown markets (not resolved/finished)
"""

import json
import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import Config


class GammaClient:
    """Discovers active crypto minute-markets on Polymarket."""
    
    def __init__(self):
        self.base_url = Config.GAMMA_API_URL
        
    def _check_market_by_slug(self, slug: str) -> Optional[Dict]:
        """Check if a market exists and is tradeable"""
        try:
            r = requests.get(
                f"{self.base_url}/events",
                params={'slug': slug},
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                events = data if isinstance(data, list) else data.get('events', [])
                if events:
                    return events[0]
        except:
            pass
        return None
    
    def discover_markets(self, coins=None, timeframes=None) -> List[Dict]:
        """
        Discover only ACTIVE, NON-CLOSED updown markets
        
        Filters applied:
        - active=True (not archived)
        - closed=False (not resolved)
        - Future markets (end_time > now)
        - Has valid token IDs
        """
        coins = coins or Config.ENABLED_COINS
        timeframes = timeframes or Config.ENABLED_TIMEFRAMES
        
        now = datetime.now(timezone.utc)
        current_ts = int(now.timestamp())
        
        # Round to nearest 5 minutes
        five_min = 5 * 60
        rounded_ts = (current_ts // five_min) * five_min
        
        all_markets = []
        
        print(f"[DISCOVER] Scanning for active markets at {now.strftime('%H:%M:%S')} UTC")
        
        # Check: past 1 round (expiring soon), current, and next 3 rounds
        for offset in range(-1, 4):
            ts = rounded_ts + (offset * five_min)
            
            # Skip if this timestamp is in the past (market already resolved)
            if ts < current_ts - 300:  # Allow 5 min grace period
                continue
            
            for coin in [c.lower() for c in coins]:
                for tf in timeframes:
                    slug = f"{coin}-updown-{tf}m-{ts}"
                    event = self._check_market_by_slug(slug)
                    
                    if not event:
                        continue
                    
                    # STRICT FILTERS: Only tradeable markets
                    if not event.get('active'):
                        continue
                    if event.get('closed'):
                        continue
                    if event.get('archived'):
                        continue
                    
                    markets_in_event = event.get('markets', [])
                    if not markets_in_event:
                        continue
                    
                    m = markets_in_event[0]
                    clob_ids_raw = m.get('clobTokenIds', '[]')
                    
                    # clobTokenIds may be a JSON string, need to parse it
                    if isinstance(clob_ids_raw, str):
                        try:
                            clob_ids = json.loads(clob_ids_raw)
                        except (json.JSONDecodeError, TypeError):
                            clob_ids = []
                    else:
                        clob_ids = clob_ids_raw if isinstance(clob_ids_raw, list) else []
                    
                    # Must have valid token IDs
                    if len(clob_ids) < 2:
                        continue
                    
                    # Parse end date
                    end_date_str = event.get('endDate')
                    if end_date_str:
                        try:
                            if end_date_str.endswith('Z'):
                                end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                            else:
                                end_dt = datetime.fromisoformat(end_date_str)
                            
                            # Skip if already ended
                            if end_dt < now:
                                continue
                            
                            seconds_remaining = int((end_dt - now).total_seconds())
                        except:
                            seconds_remaining = tf * 60  # Default to timeframe
                    else:
                        seconds_remaining = tf * 60
                    
                    market_data = {
                        'market_id': slug,
                        'event_slug': slug,
                        'coin': coin.upper(),
                        'timeframe': tf,
                        'question': event.get('title', ''),
                        'end_date': end_date_str,
                        'seconds_remaining': seconds_remaining,
                        'up_token_id': clob_ids[0],
                        'down_token_id': clob_ids[1],
                        'category': 'crypto',
                        'spread_multiplier': 1.5,
                        'epoch_timestamp': ts,
                        'raw': m,
                    }
                    all_markets.append(market_data)
                    
                    status = "LIVE" if offset == 0 else f"+{offset} rounds" if offset > 0 else f"{offset} rounds"
                    print(f"  [ACTIVE] {coin.upper()} {tf}m | {status} | Ends in {seconds_remaining}s")
                    
                    time.sleep(0.02)  # Rate limit
        
        # Sort by: current live first, then future
        all_markets.sort(key=lambda x: abs(x['seconds_remaining'] - 150))  # Closest to middle of window
        
        print(f"[DISCOVER] Found {len(all_markets)} active tradeable markets")
        return all_markets


# Keep backward compatibility
GammaClient = GammaClient
