#!/usr/bin/env python3
"""
Batch Data Downloader — Download small chunks, test, delete.

Uses Polymarket Gamma API to fetch recent market data in batches.
"""

import requests
import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'batches')
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_recent_markets(days: int = 7, limit: int = 100) -> List[Dict]:
    """Fetch markets from last N days."""
    print(f"📊 Fetching markets from last {days} days...")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        'closed': 'false',
        'active': 'true',
        'limit': limit,
        'sort': 'volume',  # Sort by volume
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            markets = resp.json()
            
            # Filter for crypto markets
            crypto_markets = []
            for m in markets:
                question = m.get('question', '').lower()
                if any(c in question for c in ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'crypto']):
                    if any(t in question for t in ['5m', '15m', '30m', 'minute']):
                        crypto_markets.append(m)
            
            print(f"   ✅ Found {len(crypto_markets)} crypto markets")
            return crypto_markets
        else:
            print(f"   ❌ API error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def fetch_market_trades(market_id: str) -> List[Dict]:
    """Fetch trade history for a specific market."""
    url = f"https://clob.polymarket.com/trades"
    params = {
        'market': market_id,
        'limit': 100,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('trades', [])
        return []
    except:
        return []

def save_batch(markets: List[Dict], batch_name: str):
    """Save batch to file."""
    filepath = os.path.join(DATA_DIR, f"{batch_name}.json")
    with open(filepath, 'w') as f:
        json.dump(markets, f, indent=2)
    size_kb = os.path.getsize(filepath) / 1024
    print(f"   💾 Saved to {batch_name}.json ({size_kb:.1f} KB)")

def load_batch(batch_name: str) -> List[Dict]:
    """Load batch from file."""
    filepath = os.path.join(DATA_DIR, f"{batch_name}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return []

def delete_batch(batch_name: str):
    """Delete batch file."""
    filepath = os.path.join(DATA_DIR, f"{batch_name}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"   🗑️  Deleted {batch_name}.json")

def analyze_batch(markets: List[Dict]):
    """Quick analysis of batch."""
    print(f"\n📊 BATCH ANALYSIS:")
    print(f"   Total markets: {len(markets)}")
    
    if not markets:
        return
    
    # Group by coin
    coins = {}
    for m in markets:
        q = m.get('question', '').lower()
        if 'btc' in q or 'bitcoin' in q:
            coin = 'BTC'
        elif 'eth' in q or 'ethereum' in q:
            coin = 'ETH'
        elif 'sol' in q or 'solana' in q:
            coin = 'SOL'
        else:
            coin = 'OTHER'
        coins[coin] = coins.get(coin, 0) + 1
    
    print(f"   By coin: {coins}")
    
    # Volume stats
    volumes = [m.get('volume', 0) for m in markets if m.get('volume')]
    if volumes:
        print(f"   Avg volume: ${sum(volumes)/len(volumes):,.0f}")
        print(f"   Total volume: ${sum(volumes):,.0f}")

def main():
    """Main batch download workflow."""
    print("="*60)
    print("📦 BATCH DATA DOWNLOADER")
    print("="*60)
    print("\nStrategy: Download small batch → Test → Delete → Repeat\n")
    
    batch_num = 1
    all_results = []
    
    while True:
        print(f"\n{'='*60}")
        print(f"🔄 BATCH #{batch_num}")
        print(f"{'='*60}")
        
        # Download small batch
        markets = fetch_recent_markets(days=7, limit=50)
        
        if not markets:
            print("   No markets found, skipping...")
            batch_num += 1
            if batch_num > 3:  # Max 3 batches for testing
                break
            continue
        
        # Save
        batch_name = f"batch_{batch_num:03d}"
        save_batch(markets, batch_name)
        
        # Analyze
        analyze_batch(markets)
        
        # Add to results
        all_results.extend(markets)
        
        # Ask if continue (auto-continue for now)
        print(f"\n✅ Batch {batch_num} complete")
        
        # Delete immediately to save space
        delete_batch(batch_name)
        
        batch_num += 1
        
        if batch_num > 3:  # Stop after 3 batches for testing
            print("\n⏹️  Stopping after 3 batches (testing mode)")
            break
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"   Total batches processed: {batch_num - 1}")
    print(f"   Total markets analyzed: {len(all_results)}")
    print(f"   Data saved: No (deleted after analysis)")
    print(f"   Space used: Minimal (~0 KB)")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()