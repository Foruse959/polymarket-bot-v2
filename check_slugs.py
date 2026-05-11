#!/usr/bin/env python3
import requests

r = requests.get('https://gamma-api.polymarket.com/markets', 
                 params={'active': 'true', 'closed': 'false', 'limit': 500}, 
                 timeout=15)
data = r.json()
markets = data if isinstance(data, list) else data.get('markets', [])

print(f"Total markets: {len(markets)}")
print("\nAll slugs containing 'updown':")
print("="*70)

for m in markets:
    slug = m.get('slug', '').lower()
    question = m.get('question', '')
    
    if 'updown' in slug:
        print(f"Slug: {m.get('slug')}")
        print(f"Q: {question}")
        print(f"Active: {m.get('active')} | Closed: {m.get('closed')}")
        print()
