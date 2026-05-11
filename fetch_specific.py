#!/usr/bin/env python3
import requests

# Try to fetch the specific market the user has a position in
slug = "btc-updown-5m-1778308500"

print(f"Fetching market: {slug}")
print("="*60)

# Try by slug
r = requests.get(f'https://gamma-api.polymarket.com/markets/{slug}', timeout=15)
print(f"By slug status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Found! Keys: {list(data.keys())}")
    print(f"Question: {data.get('question')}")
    print(f"Active: {data.get('active')}")
    print(f"Closed: {data.get('closed')}")
else:
    print(f"Not found by slug: {r.text[:200]}")

# Try events endpoint
print("\n" + "="*60)
print("Searching in events...")
r = requests.get('https://gamma-api.polymarket.com/events',
                 params={'slug': 'btc-updown-5m-1778308500'},
                 timeout=15)
print(f"Events status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    print(f"Found {len(events)} events")
    for e in events:
        print(f"  Event: {e.get('slug')}")
