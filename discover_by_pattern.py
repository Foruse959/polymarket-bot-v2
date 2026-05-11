#!/usr/bin/env python3
"""
Discover updown markets by checking known patterns
"""

import requests
import time
from datetime import datetime, timezone

def check_market(slug: str):
    """Check if a market exists by slug"""
    try:
        r = requests.get('https://gamma-api.polymarket.com/events',
                         params={'slug': slug},
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            events = data if isinstance(data, list) else data.get('events', [])
            if events:
                return events[0]
    except:
        pass
    return None

def find_current_updown_markets():
    """Find current 5m/15m BTC/ETH markets"""
    
    now = datetime.now(timezone.utc)
    current_ts = int(now.timestamp())
    
    # Round to nearest 5 minutes
    five_min = 5 * 60
    rounded_ts = (current_ts // five_min) * five_min
    
    coins = ['btc', 'eth', 'sol']
    timeframes = [5, 15, 30]
    markets = []
    
    print(f"Current time: {now}")
    print(f"Searching around timestamp: {rounded_ts}")
    print("="*60)
    
    # Check current and next few rounds
    for offset in range(-2, 5):
        ts = rounded_ts + (offset * five_min)
        
        for coin in coins:
            for tf in timeframes:
                slug = f"{coin}-updown-{tf}m-{ts}"
                event = check_market(slug)
                
                if event:
                    print(f"\n[FOUND] {slug}")
                    print(f"  Title: {event.get('title')}")
                    print(f"  Active: {event.get('active')}")
                    print(f"  Closed: {event.get('closed')}")
                    
                    # Get market details
                    markets_in_event = event.get('markets', [])
                    if markets_in_event:
                        m = markets_in_event[0]
                        print(f"  Token IDs: {m.get('clobTokenIds', [])}")
                        
                        markets.append({
                            'slug': slug,
                            'coin': coin.upper(),
                            'timeframe': tf,
                            'event': event,
                            'market': m
                        })
    
    return markets

if __name__ == "__main__":
    markets = find_current_updown_markets()
    
    print(f"\n{'='*60}")
    print(f"Total found: {len(markets)}")
