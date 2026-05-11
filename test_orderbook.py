import sys
sys.path.insert(0, '.')
from data.clob_client import ClobClient
import time, requests

clob = ClobClient()

# Get current epoch token IDs
now = int(time.time())
rounded = (now // 300) * 300
slug = f'btc-updown-5m-{rounded}'
print(f'Checking slug: {slug}')

r = requests.get('https://gamma-api.polymarket.com/events', params={'slug': slug}, timeout=10)
data = r.json()
events = data if isinstance(data, list) else data.get('events', [])

if events:
    markets = events[0].get('markets', [])
    print(f'Found {len(markets)} markets')
    if markets:
        tids = markets[0].get('clobTokenIds', [])
        print(f'Token IDs: {len(tids)}')
        for i, tid in enumerate(tids):
            if tid:
                print(f'\n  Token {i}: {tid[:40]}...')
                try:
                    book = clob.get_orderbook(tid)
                    if book:
                        print(f'  ORDERBOOK OK!')
                        print(f'  Best bid: {book["best_bid"]}')
                        print(f'  Best ask: {book["best_ask"]}')
                        print(f'  Spread: {book["spread_bps"]:.0f}bps')
                        print(f'  Mid: {book["mid_price"]}')
                    else:
                        print(f'  ORDERBOOK: None returned')
                except Exception as e:
                    print(f'  ERROR: {e}')
else:
    print('No events found')

# Also test dual orderbook
print('\n\nTesting dual orderbook...')
if events and markets and len(tids) >= 2:
    try:
        dual = clob.get_dual_orderbook(tids[0], tids[1])
        if dual:
            print(f'  DUAL OK!')
            print(f'  UP mid: {dual["up"]["mid_price"]}')
            print(f'  DOWN mid: {dual["down"]["mid_price"]}')
            print(f'  Combined bid: {dual["combined_bid"]}')
            print(f'  Combined ask: {dual["combined_ask"]}')
            print(f'  ARB: {dual.get("arb_opportunity", False)}')
        else:
            print(f'  DUAL: None returned')
    except Exception as e:
        print(f'  ERROR: {e}')