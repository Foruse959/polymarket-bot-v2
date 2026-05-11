#!/usr/bin/env python3
import requests
import sys
sys.path.insert(0, '.')

print('Checking Polymarket for available markets...')
print('='*60)

# Fetch events
r = requests.get('https://gamma-api.polymarket.com/events?active=true&closed=false&archived=false', timeout=10)
data = r.json()

print(f'Total events: {len(data)}')

# Filter for crypto up/down
crypto_markets = []
for event in data:
    title = event.get('title', '').lower()
    slug = event.get('slug', '').lower()
    if any(x in title or x in slug for x in ['btc', 'eth', 'sol', 'bitcoin', 'ethereum']):
        if 'up' in title or 'down' in title or 'updown' in slug:
            crypto_markets.append({
                'title': event.get('title'),
                'slug': event.get('slug'),
                'markets': len(event.get('markets', []))
            })

print(f'\nCrypto Up/Down markets found: {len(crypto_markets)}')
for m in crypto_markets[:15]:
    print(f"  - {m['title'][:70]}")
    print(f"    Slug: {m['slug']}")
    print(f"    Markets: {m['markets']}")
    print()

if not crypto_markets:
    print("No active crypto up/down markets found!")
    print("This means Polymarket doesn't have any 5m/15m BTC/ETH markets open right now.")
