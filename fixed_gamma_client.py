"""
Fixed Gamma Client - Discovers updown markets by pattern
"""

import time
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone
from config import Config

class FixedGammaClient:
    """Discovers updown markets using timestamp pattern"""
    
    def __init__(self):
        self.base_url = Config.GAMMA_API_URL
        
    def _check_market(self, slug: str) -> Optional[Dict]:
        """Check if a market exists by slug"""
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
    
    def discover_updown_markets(self, coins=None, timeframes=None, lookback=2, lookahead=4) -> List[Dict]:
        """
        Discover updown markets by checking timestamp patterns
        
        Args:
            coins: List of coins ['BTC', 'ETH']
            timeframes: List of timeframes [5, 15]
            lookback: Number of past rounds to check
            lookahead: Number of future rounds to check
        """
        coins = coins or Config.ENABLED_COINS
        timeframes = timeframes or Config.ENABLED_TIMEFRAMES
        
        now = datetime.now(timezone.utc)
        current_ts = int(now.timestamp())
        
        # Round to nearest 5 minutes
        five_min = 5 * 60
        rounded_ts = (current_ts // five_min) * five_min
        
        markets = []
        
        print(f"[DISCOVER] Current time: {now.strftime('%H:%M:%S')}")
        print(f"[DISCOVER] Searching for markets...")
        
        # Check past and future rounds (with delay to avoid rate limit)
        for offset in range(-lookback, lookahead + 1):
            ts = rounded_ts + (offset * five_min)
            
            for coin in [c.lower() for c in coins]:
                for tf in timeframes:
                    slug = f"{coin}-updown-{tf}m-{ts}"
                    event = self._check_market(slug)
                    
                    if event and event.get('active') and not event.get('closed'):
                        markets_in_event = event.get('markets', [])
                        if markets_in_event:
                            m = markets_in_event[0]
                            clob_ids = m.get('clobTokenIds', [])
                            
                            market_data = {
                                'market_id': slug,
                                'event_slug': slug,
                                'coin': coin.upper(),
                                'timeframe': tf,
                                'question': event.get('title', ''),
                                'end_date': event.get('endDate'),
                                'seconds_remaining': max(0, ts - current_ts),
                                'up_token_id': clob_ids[0] if len(clob_ids) > 0 else None,
                                'down_token_id': clob_ids[1] if len(clob_ids) > 1 else None,
                                'category': 'crypto',
                                'spread_multiplier': 1.5,
                                'raw': m,
                            }
                            markets.append(market_data)
                            print(f"  [FOUND] {coin.upper()} {tf}m - {event.get('title')}")
        
        print(f"[DISCOVER] Total markets found: {len(markets)}")
        return markets

# Test
if __name__ == "__main__":
    client = FixedGammaClient()
    markets = client.discover_updown_markets()
    
    print(f"\n{'='*60}")
    print(f"DISCOVERED {len(markets)} MARKETS:")
    print('='*60)
    
    for m in markets:
        print(f"\n{m['coin']} {m['timeframe']}m")
        print(f"  ID: {m['market_id']}")
        print(f"  UP: {m['up_token_id'][:30]}...")
        print(f"  DOWN: {m['down_token_id'][:30]}...")
