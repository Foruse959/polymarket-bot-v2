#!/usr/bin/env python3
import requests

# Check with and without active filter
print("With active=true filter:")
r1 = requests.get('https://gamma-api.polymarket.com/events',
                  params={'active': 'true', 'closed': 'false', 'limit': 200},
                  timeout=15)
data1 = r1.json()
events1 = data1 if isinstance(data1, list) else data1.get('events', [])
print(f"  Found {len(events1)} events")

# Check if our target is in there
found = any(e.get('slug') == 'btc-updown-5m-1778308500' for e in events1)
print(f"  btc-updown-5m-1778308500 in list: {found}")

print("\nWithout active filter:")
r2 = requests.get('https://gamma-api.polymarket.com/events',
                  params={'limit': 200},
                  timeout=15)
data2 = r2.json()
events2 = data2 if isinstance(data2, list) else data2.get('events', [])
print(f"  Found {len(events2)} events")

# Check if our target is in there
found2 = any(e.get('slug') == 'btc-updown-5m-1778308500' for e in events2)
print(f"  btc-updown-5m-1778308500 in list: {found2}")
