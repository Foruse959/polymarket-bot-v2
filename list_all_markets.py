import requests
r = requests.get('https://gamma-api.polymarket.com/events?active=true&closed=false', timeout=10)
data = r.json()
print('ALL ACTIVE MARKETS:')
print('='*70)
for e in data[:30]:
    title = e.get('title', 'N/A')
    print(f"- {title[:70]}")
