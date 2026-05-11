#!/usr/bin/env python3
import requests
import time

now = int(time.time())
five_min = 5 * 60
rounded = (now // five_min) * five_min

coins = ['btc', 'eth']
tfs = [5, 15]

print(f"Current timestamp: {now}")
print(f"Rounded to 5min: {rounded}")
print("="*60)

# Check just a few recent ones
for offset in [0, 1, 2, 3]:
    ts = rounded + (offset * five_min)
    
    for coin in coins:
        for tf in tfs:
            slug = f"{coin}-updown-{tf}m-{ts}"
            
            r = requests.get('https://gamma-api.polymarket.com/events',
                             params={'slug': slug},
                             timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                events = data if isinstance(data, list) else data.get('events', [])
                if events:
                    e = events[0]
                    print(f"\n[FOUND] {slug}")
                    print(f"  Title: {e.get('title')}")
                    print(f"  Active: {e.get('active')}, Closed: {e.get('closed')}")
                    markets = e.get('markets', [])
                    if markets:
                        print(f"  Tokens: {markets[0].get('clobTokenIds', [])}")
            
            time.sleep(0.1)  # Rate limit

print("\n" + "="*60)
print("Check complete")
