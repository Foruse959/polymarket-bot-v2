import requests
import json

# Get a specific market event to see the correct structure
slug = 'btc-updown-5m-1778310900'
r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
print(f'Status: {r.status_code}')
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if events:
    event = events[0]
    print(f"Event: {event.get('title')}")
    print(f"Active: {event.get('active')}")
    print(f"Closed: {event.get('closed')}")
    markets = event.get('markets', [])
    print(f"\nMarkets count: {len(markets)}")
    for m in markets:
        print(f"\n  Question: {m.get('question')}")
        print(f"  ID: {m.get('id')}")
        print(f"  Condition ID: {m.get('conditionId')}")
        print(f"  CLOB Token IDs: {m.get('clobTokenIds')}")
        print(f"  Active: {m.get('active')}")
        
        # Try to fetch price for each token
        for tid in (m.get('clobTokenIds') or []):
            if tid:
                pr = requests.get(f'https://clob.polymarket.com/price', params={'token_id': tid, 'side': 'buy'}, timeout=5)
                print(f"    Price ({tid[:20]}...): {pr.status_code} {pr.text[:100]}")
else:
    print('No events found')