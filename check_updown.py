#!/usr/bin/env python3
import requests

r = requests.get('https://gamma-api.polymarket.com/markets', 
                 params={'active': 'true', 'closed': 'false', 'limit': 500}, 
                 timeout=15)
data = r.json()
markets = data if isinstance(data, list) else data.get('markets', [])

print(f"Total markets: {len(markets)}")
print("\nMarkets with 'Up or Down' or '5m' in question:")
print("="*70)

count = 0
for m in markets:
    question = m.get('question', '').lower()
    slug = m.get('slug', '')
    
    if 'up or down' in question or '5m' in question or '5 min' in question:
        count += 1
        print(f"Slug: {slug}")
        print(f"Q: {m.get('question')}")
        print(f"Active: {m.get('active')} | Closed: {m.get('closed')}")
        print()
        
print(f"\nTotal found: {count}")
