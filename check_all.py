#!/usr/bin/env python3
import requests

# Check all markets without active filter
r = requests.get('https://gamma-api.polymarket.com/markets', 
                 params={'limit': 500, 'offset': 0}, 
                 timeout=15)
data = r.json()
markets = data if isinstance(data, list) else data.get('markets', [])

print(f"Total markets (no filter): {len(markets)}")
print("\nMarkets with 'btc' and 'updown' in slug:")
print("="*70)

for m in markets:
    slug = m.get('slug', '').lower()
    question = m.get('question', '')
    
    if 'btc' in slug and 'updown' in slug:
        print(f"Slug: {m.get('slug')}")
        print(f"Q: {question}")
        print(f"Active: {m.get('active')} | Closed: {m.get('closed')} | Archived: {m.get('archived')}")
        print(f"End date: {m.get('endDate')}")
        print()
