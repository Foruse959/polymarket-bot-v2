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
    
    print(f'First market: {m.get("coin")} {m.get("timeframe")}m')
    print(f'UP token: {up_tid}')
    print(f'DOWN token: {down_tid}')
    print(f'UP type: {type(up_tid)}, len: {len(str(up_tid) or "")}')
    print(f'DOWN type: {type(down_tid)}, len: {len(str(down_tid) or "")}')
    
    # Test CLOB API directly
    for label, tid in [('UP', up_tid), ('DOWN', down_tid)]:
        if tid:
            r = requests.get('https://clob.polymarket.com/book', params={'token_id': tid}, timeout=10)
            print(f'{label} CLOB book: {r.status_code} ({len(r.text)} bytes)')
else:
    print('No markets found')