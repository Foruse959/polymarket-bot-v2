#!/usr/bin/env python3
"""
Market Discovery from User Positions
Since Gamma API doesn't list updown markets in events endpoint,
we discover them from user's existing positions.
"""

import requests
import json
from typing import List, Dict, Optional

class PositionScanner:
    """Scan user's positions to find tradeable markets"""
    
    def __init__(self, wallet_address: str):
        self.wallet = wallet_address.lower()
        self.base_url = "https://polymarket.com/api"
        
    def fetch_positions(self) -> List[Dict]:
        """Fetch user's positions from Polymarket API"""
        try:
            # Use the data API endpoint for positions
            url = f"https://data-api.polymarket.com/positions"
            params = {
                'user': self.wallet,
                'active': 'true'
            }
            
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch positions: {e}")
        
        return []
    
    def get_tradeable_markets(self) -> List[Dict]:
        """Get markets from positions that are tradeable"""
        positions = self.fetch_positions()
        markets = []
        
        for pos in positions:
            # Check if it's a up/down market
            slug = pos.get('slug', '')
            title = pos.get('title', '')
            
            if 'updown' in slug.lower():
                # Extract coin and timeframe from slug
                # Pattern: btc-updown-5m-1778308500
                parts = slug.split('-')
                if len(parts) >= 3:
                    coin = parts[0].upper()
                    tf_match = parts[2]  # "5m" or "15m"
                    
                    if tf_match.endswith('m'):
                        try:
                            tf = int(tf_match[:-1])  # Remove 'm'
                        except:
                            tf = 0
                    else:
                        tf = 0
                    
                    # Get token IDs
                    up_token = pos.get('oppositeAsset') if pos.get('outcomeIndex') == 1 else pos.get('asset')
                    down_token = pos.get('asset') if pos.get('outcomeIndex') == 1 else pos.get('oppositeAsset')
                    
                    market = {
                        'market_id': slug,
                        'event_slug': slug,
                        'coin': coin,
                        'timeframe': tf,
                        'question': title,
                        'end_date': pos.get('endDate'),
                        'seconds_remaining': 300,  # 5 min markets
                        'up_token_id': up_token,
                        'down_token_id': down_token,
                        'category': 'crypto',
                        'spread_multiplier': 1.5,
                        'redeemable': pos.get('redeemable', False),
                        'current_price': pos.get('curPrice', 0),
                        'position_size': pos.get('size', 0),
                    }
                    markets.append(market)
        
        return markets

# Test
if __name__ == "__main__":
    wallet = "0x4f9fbe936a35d556894737235df49cfcd5d5cfc4"
    scanner = PositionScanner(wallet)
    markets = scanner.get_tradeable_markets()
    
    print(f"Found {len(markets)} tradeable up/down markets from positions:")
    print("="*60)
    
    for m in markets:
        print(f"\n🎯 {m['coin']} {m['timeframe']}m")
        print(f"   ID: {m['market_id']}")
        print(f"   Q: {m['question']}")
        print(f"   UP: {m['up_token_id'][:30]}...")
        print(f"   DOWN: {m['down_token_id'][:30]}...")
        print(f"   Current Price: {m['current_price']}")
        print(f"   Position Size: {m['position_size']}")
