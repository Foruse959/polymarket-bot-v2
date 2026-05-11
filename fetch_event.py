#!/usr/bin/env python3
import requests
import json

# Fetch the specific event
slug = "btc-updown-5m-1778308500"

print(f"Fetching event: {slug}")
print("="*60)

r = requests.get(f'https://gamma-api.polymarket.com/events',
                 params={'slug': slug},
                 timeout=15)

if r.status_code == 200:
    data = r.json()
    events = data if isinstance(data, list) else data.get('events', [])
    
    if events:
        event = events[0]
        print(f"Event found!")
        print(f"  Title: {event.get('title')}")
        print(f"  Slug: {event.get('slug')}")
        print(f"  Active: {event.get('active')}")
        print(f"  Closed: {event.get('closed')}")
        print(f"  Archived: {event.get('archived')}")
        print(f"  Markets count: {len(event.get('markets', []))}")
        print()
        
        for i, market in enumerate(event.get('markets', [])):
            print(f"  Market {i+1}:")
            print(f"    Question: {market.get('question')}")
            print(f"    Slug: {market.get('slug')}")
            print(f"    Active: {market.get('active')}")
            print(f"    Closed: {market.get('closed')}")
            print(f"    Token IDs: {market.get('clobTokenIds', [])}")
            print()
else:
    print(f"Error: {r.status_code}")
