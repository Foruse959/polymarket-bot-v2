#!/usr/bin/env python3
import requests

r = requests.get('https://gamma-api.polymarket.com/markets', 
                 params={'active': 'true', 'closed': 'false', 'limit': 200}, 
                 timeout=15)
data = r.json()
markets = data if isinstance(data, list) else data.get('markets', [])

print(f"Total markets: {len(markets)}")
print("\nAll slugs containing 'btc', 'eth', 'up', 'down', or '5m':")
print("="*70)

for m in markets:
    slug = m.get('slug', '').lower()
    question = m.get('question', '').lower()
    
    if any(kw in slug or kw in question for kw in ['btc', 'eth', 'bitcoin', 'ethereum', 'up', 'down', '5m', '15m']):
        print(f"Slug: {m.get('slug')}")
        print(f"Q: {m.get('question')[:70]}")
        print(f"Active: {m.get('active')} | Closed: {m.get('closed')}")
        print()
