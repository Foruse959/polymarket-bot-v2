#!/usr/bin/env python3
import requests

# Search for all updown events by using the tag or keyword
print("Searching for 'updown' or '5m' events...")

for offset in [0, 200, 400, 600, 800, 1000]:
    r = requests.get('https://gamma-api.polymarket.com/events',
                     params={'limit': 200, 'offset': offset},
                     timeout=15)
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    updown_events = [e for e in events if 'updown' in e.get('slug', '')]
    if updown_events:
        print(f"\nOffset {offset}: Found {len(updown_events)} updown events")
        for e in updown_events[:5]:
            print(f"  - {e.get('slug')}")
            print(f"    {e.get('title')}")
            print(f"    Active: {e.get('active')}, Closed: {e.get('closed')}")
