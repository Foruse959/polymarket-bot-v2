import requests, json, time

now = int(time.time())
rounded = (now // 300) * 300
slug = f'btc-updown-5m-{rounded}'

print(f'Checking slug: {slug}')
r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if events:
    event = events[0]
    markets = event.get('markets', [])
    print(f'\nEvent: {event.get("title")}')
    print(f'Active: {event.get("active")}')
    print(f'Markets count: {len(markets)}')
    
    for m in markets:
        print(f'\nMarket: {m.get("question")}')
        tids = m.get('clobTokenIds')
        print(f'  clobTokenIds type: {type(tids)}')
        print(f'  clobTokenIds raw: {repr(tids)[:200]}')
        
        # Try to parse
        if isinstance(tids, str):
            print(f'  It is a STRING - need to JSON parse it!')
            try:
                parsed = json.loads(tids)
                print(f'  Parsed: {parsed[:2] if len(parsed) > 2 else parsed}')
            except:
                print(f'  Failed to JSON parse')
        elif isinstance(tids, list):
            for i, tid in enumerate(tids):
                print(f'  Token {i}: {tid[:40]}...' if len(str(tid)) > 40 else f'  Token {i}: {tid}')
else:
    print('No events found')