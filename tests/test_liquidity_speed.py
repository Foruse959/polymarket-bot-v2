"""
Liquidity Check Speed Simulation Test

Simulates the BEFORE vs AFTER of the scan cycle to prove the speedup.

BEFORE: Each strategy calls clob.get_orderbook() independently
  → 4 coins x 2 tokens x 7 strategies = 56+ network calls per scan

AFTER: prefetch_scan() batches all tokens, CachedClobProxy serves from memory
  → 8 network calls total (4 coins x 2 tokens), rest are instant cache hits

Run: python -m pytest tests/test_liquidity_speed.py -v
  or: python tests/test_liquidity_speed.py
"""

import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.market_cache import MarketCache, CachedClobProxy


# ─────────────────────────────────────────────────────────────
# MOCK: Simulates ClobClient with artificial network latency
# ─────────────────────────────────────────────────────────────

class MockClobClient:
    """Simulates ClobClient with configurable latency per call."""

    def __init__(self, latency_ms: float = 80):
        self.latency = latency_ms / 1000.0  # convert to seconds
        self.call_count = 0
        self.fallback_prices = {}

    def get_orderbook(self, token_id: str):
        """Simulate an API call with network latency."""
        self.call_count += 1
        time.sleep(self.latency)  # simulate network round-trip
        # Return realistic-looking orderbook
        price = hash(token_id) % 80 / 100 + 0.10  # 0.10 - 0.90
        spread = 0.02
        best_bid = max(0.01, price - spread / 2)
        best_ask = min(0.99, price + spread / 2)
        return {
            'token_id': token_id,
            'bids': [(best_bid, 150.0)],
            'asks': [(best_ask, 150.0)],
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': spread,
            'spread_pct': (spread / best_ask * 100) if best_ask > 0 else 0,
            'spread_bps': (spread / best_ask * 10000) if best_ask > 0 else 0,
            'mid_price': (best_bid + best_ask) / 2,
            'bid_depth': best_bid * 150,
            'ask_depth': best_ask * 150,
            'imbalance': 0.05,
        }

    def get_dual_orderbook(self, up_token: str, down_token: str):
        up_book = self.get_orderbook(up_token)
        down_book = self.get_orderbook(down_token)
        return {'up': up_book, 'down': down_book,
                'combined_bid': up_book['best_bid'] + down_book['best_bid'],
                'combined_ask': up_book['best_ask'] + down_book['best_ask'],
                'arb_opportunity': False, 'arb_profit_bps': 0, 'net_flow_signal': 0}

    def _synthetic_book(self, token_id):
        return {
            'token_id': token_id, 'bids': [], 'asks': [(0.99, 100.0)],
            'best_bid': 0.01, 'best_ask': 0.99, 'spread': 0.98,
            'spread_pct': 98.0, 'spread_bps': 9800, 'mid_price': 0.50,
            'bid_depth': 0, 'ask_depth': 99.0, 'imbalance': -1.0, '_synthetic': True,
        }


# ─────────────────────────────────────────────────────────────
# TEST MARKETS (simulating 4 coins x 2 timeframes = 8 markets)
# ─────────────────────────────────────────────────────────────

def generate_test_markets(num_coins=4):
    """Generate realistic market data like gamma_client would return."""
    coins = ['BTC', 'ETH', 'SOL', 'XRP'][:num_coins]
    markets = []
    for i, coin in enumerate(coins):
        for tf in [5, 15]:
            markets.append({
                'coin': coin,
                'timeframe': tf,
                'market_id': f'market_{coin}_{tf}min',
                'up_token_id': f'token_{coin}_UP_{tf}',
                'down_token_id': f'token_{coin}_DOWN_{tf}',
                'seconds_remaining': 180,
                'question': f'Will {coin} go up in next {tf} min?',
                'raw': {'volume': 50000},
            })
    return markets


# ─────────────────────────────────────────────────────────────
# SIMULATION: OLD approach (direct clob calls, no pre-fetch)
# ─────────────────────────────────────────────────────────────

def simulate_old_approach(markets, clob, num_strategies=7):
    """
    Simulates the OLD behavior where each strategy calls
    clob.get_orderbook() directly (sequential, no caching).
    
    Each strategy needs ~2 orderbook calls per market.
    """
    clob.call_count = 0
    start = time.time()

    for market in markets:
        up_token = market['up_token_id']
        down_token = market['down_token_id']

        for strat_idx in range(num_strategies):
            # Most strategies call get_orderbook on both tokens
            if strat_idx < 3:
                # maker_edge, longshot_bias, microstructure: dual book
                clob.get_orderbook(up_token)
                clob.get_orderbook(down_token)
            elif strat_idx < 5:
                # indicator_fusion, momentum_breakout: single book
                clob.get_orderbook(up_token)
            else:
                # volume_imbalance, mean_reversion: single book
                clob.get_orderbook(down_token)

    elapsed = time.time() - start
    return elapsed, clob.call_count


# ─────────────────────────────────────────────────────────────
# SIMULATION: NEW approach (prefetch + CachedClobProxy)
# ─────────────────────────────────────────────────────────────

async def simulate_new_approach(markets, clob, num_strategies=7):
    """
    Simulates the NEW behavior:
    1. prefetch_scan() fetches ALL tokens in parallel ONCE
    2. CachedClobProxy serves all strategy requests from memory
    """
    clob.call_count = 0
    market_cache = MarketCache(clob, ttl_seconds=5.0, max_workers=12)
    proxy = CachedClobProxy(market_cache, clob)

    start = time.time()

    # Step 1: Pre-fetch all tokens for this scan (ONE parallel batch)
    all_tokens = []
    for m in markets:
        if m.get('up_token_id'):
            all_tokens.append(m['up_token_id'])
        if m.get('down_token_id'):
            all_tokens.append(m['down_token_id'])

    await market_cache.prefetch_scan(all_tokens)
    prefetch_time = time.time() - start

    # Step 2: Strategies read from cache (instant)
    strategy_start = time.time()
    for market in markets:
        up_token = market['up_token_id']
        down_token = market['down_token_id']

        for strat_idx in range(num_strategies):
            if strat_idx < 3:
                proxy.get_orderbook(up_token)
                proxy.get_orderbook(down_token)
            elif strat_idx < 5:
                proxy.get_orderbook(up_token)
            else:
                proxy.get_orderbook(down_token)

    strategy_time = time.time() - strategy_start
    total_elapsed = time.time() - start

    return total_elapsed, clob.call_count, prefetch_time, strategy_time, market_cache.get_cache_stats()


# ─────────────────────────────────────────────────────────────
# MAIN: Run simulation and report
# ─────────────────────────────────────────────────────────────

async def run_simulation():
    print("=" * 70)
    print("  LIQUIDITY CHECK SPEED SIMULATION")
    print("  Comparing OLD (direct API) vs NEW (prefetch + cache proxy)")
    print("=" * 70)

    # Config
    NUM_COINS = 4
    NUM_STRATEGIES = 7
    LATENCY_MS = 80  # realistic API latency

    markets = generate_test_markets(NUM_COINS)
    num_markets = len(markets)
    print(f"\n  Config: {NUM_COINS} coins, {num_markets} markets, "
          f"{NUM_STRATEGIES} strategies, {LATENCY_MS}ms API latency\n")

    # ── OLD APPROACH ──
    print("-" * 70)
    print("  OLD APPROACH: Each strategy calls clob.get_orderbook() directly")
    print("-" * 70)

    clob_old = MockClobClient(latency_ms=LATENCY_MS)
    old_time, old_calls = simulate_old_approach(markets, clob_old, NUM_STRATEGIES)

    print(f"  API calls made:  {old_calls}")
    print(f"  Total time:      {old_time:.2f}s")
    print(f"  Avg per call:    {(old_time/old_calls*1000):.1f}ms")

    # ── NEW APPROACH ──
    print("\n" + "-" * 70)
    print("  NEW APPROACH: prefetch_scan() + CachedClobProxy")
    print("-" * 70)

    clob_new = MockClobClient(latency_ms=LATENCY_MS)
    new_time, new_calls, prefetch_t, strat_t, stats = await simulate_new_approach(
        markets, clob_new, NUM_STRATEGIES
    )

    print(f"  API calls made:  {new_calls} (all during prefetch)")
    print(f"  Prefetch time:   {prefetch_t:.3f}s (parallel)")
    print(f"  Strategy time:   {strat_t*1000:.2f}ms (all from cache)")
    print(f"  Total time:      {new_time:.3f}s")
    print(f"  Cache stats:     {stats}")

    # ── COMPARISON ──
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)
    speedup = old_time / new_time if new_time > 0 else float('inf')
    calls_saved = old_calls - new_calls
    pct_saved = (calls_saved / old_calls * 100) if old_calls > 0 else 0

    print(f"  Speed improvement:   {speedup:.1f}x faster")
    print(f"  Time saved:          {old_time - new_time:.2f}s per scan")
    print(f"  API calls saved:     {calls_saved} ({pct_saved:.0f}% reduction)")
    print(f"  Old: {old_calls} calls in {old_time:.2f}s")
    print(f"  New: {new_calls} calls in {new_time:.3f}s")
    print("=" * 70)

    # ── ASSERTIONS ──
    assert new_time < old_time, f"New approach should be faster! old={old_time:.2f}s new={new_time:.2f}s"
    assert new_calls < old_calls, f"New approach should make fewer API calls! old={old_calls} new={new_calls}"
    assert speedup > 3, f"Should be at least 3x faster, got {speedup:.1f}x"
    assert strat_t < 0.01, f"Strategy phase should be <10ms (cache only), got {strat_t*1000:.1f}ms"

    print(f"\n  ALL ASSERTIONS PASSED")
    print(f"  Liquidity check is {speedup:.0f}x faster with scan-scoped prefetch!")
    return speedup


def test_liquidity_speed():
    """Pytest entry point."""
    speedup = asyncio.run(run_simulation())
    assert speedup > 3


if __name__ == '__main__':
    asyncio.run(run_simulation())
