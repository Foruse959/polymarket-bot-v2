#!/usr/bin/env python3
import requests

# Check multiple pages
for offset in [0, 200, 400, 600, 800]:
    r = requests.get('https://gamma-api.polymarket.com/events',
                     params={'limit': 200, 'offset': offset},
                     timeout=15)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    found = any(e.get('slug') == 'btc-updown-5m-1778308500' for e in events)
    print(f"Offset {offset}: {len(events)} events, target found: {found}")
    
    if found:
        for e in events:
            if e.get('slug') == 'btc-updown-5m-1778308500':
                print(f"  Title: {e.get('title')}")
                print(f"  Active: {e.get('active')}")
        break
