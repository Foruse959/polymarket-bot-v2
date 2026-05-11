import sys
sys.path.insert(0, '.')
from data.gamma_client import GammaClient
import requests

g = GammaClient()
markets = g.discover_markets()

if markets:
    m = markets[0]
    up_tid = m.get('up_token_id', '')
    down_tid = m.get('down_token_id', '')
    
    print('First market: %s %dm' % (m.get('coin'), m.get('timeframe')))
    print('UP token: %s... (len: %d)' % (up_tid[:30], len(up_tid)))
    print('DOWN token: %s... (len: %d)' % (down_tid[:30], len(down_tid)))
    
    # Test CLOB API directly
    for label, tid in [('UP', up_tid), ('DOWN', down_tid)]:
        if tid and len(tid) > 10:
            r = requests.get('https://clob.polymarket.com/book', params={'token_id': tid}, timeout=10)
            print('%s CLOB book: %d (%d bytes)' % (label, r.status_code, len(r.text)))
            if r.status_code == 200:
                data = r.json()
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                print('  Bids: %d, Asks: %d' % (len(bids), len(asks)))
else:
    print('No markets found')
