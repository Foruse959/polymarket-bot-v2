#!/usr/bin/env python3
"""Debug API - Check what Polymarket is actually returning"""

import requests
import json

print("="*70)
print("DEBUG: Polymarket Gamma API")
print("="*70)

# Test events endpoint
print("\n1. Testing /events endpoint...")
try:
    r = requests.get(
        'https://gamma-api.polymarket.com/events',
        params={'active': 'true', 'closed': 'false', 'limit': 100},
        timeout=15
    )
    print(f"   Status: {r.status_code}")
    data = r.json()
    
    if isinstance(data, list):
        print(f"   Type: List with {len(data)} items")
        if data:
            print(f"   First event keys: {list(data[0].keys())}")
            print(f"   Sample slug: {data[0].get('slug', 'N/A')}")
            print(f"   Sample title: {data[0].get('title', 'N/A')[:60]}")
    else:
        print(f"   Type: Dict with keys: {list(data.keys())}")
        events = data.get('events', [])
        print(f"   Events count: {len(events)}")
        
except Exception as e:
    print(f"   Error: {e}")

# Test markets endpoint
print("\n2. Testing /markets endpoint...")
try:
    r = requests.get(
        'https://gamma-api.polymarket.com/markets',
        params={'active': 'true', 'closed': 'false', 'limit': 100},
        timeout=15
    )
    print(f"   Status: {r.status_code}")
    data = r.json()
    
    if isinstance(data, list):
        print(f"   Type: List with {len(data)} items")
        if data:
            print(f"   First market keys: {list(data[0].keys())}")
            print(f"   Sample slug: {data[0].get('slug', 'N/A')}")
            print(f"   Sample question: {data[0].get('question', 'N/A')[:60]}")
    else:
        print(f"   Type: Dict with keys: {list(data.keys())}")
        markets = data.get('markets', [])
        print(f"   Markets count: {len(markets)}")
        
except Exception as e:
    print(f"   Error: {e}")

# Check for crypto markets specifically
print("\n3. Searching for crypto markets in events...")
try:
    r = requests.get(
        'https://gamma-api.polymarket.com/events',
        params={'active': 'true', 'closed': 'false', 'limit': 200},
        timeout=15
    )
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    crypto_keywords = ['btc', 'eth', 'sol', 'bitcoin', 'ethereum', 'up', 'down', 'updown']
    crypto_events = []
    
    for e in events:
        slug = e.get('slug', '').lower()
        title = e.get('title', '').lower()
        text = f"{slug} {title}"
        
        if any(kw in text for kw in crypto_keywords):
            crypto_events.append({
                'slug': e.get('slug'),
                'title': e.get('title')[:70],
                'markets': len(e.get('markets', []))
            })
    
    print(f"   Found {len(crypto_events)} crypto-related events")
    for ce in crypto_events[:10]:
        print(f"   - {ce['slug']}")
        print(f"     {ce['title']}")
        print(f"     Markets: {ce['markets']}")
        print()
        
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "="*70)
