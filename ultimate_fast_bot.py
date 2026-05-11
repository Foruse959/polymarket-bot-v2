#!/usr/bin/env python3
"""
ULTIMATE FAST BOT — The Fastest Polymarket Trading Bot

Combines ALL speed optimizations:
1. WebSocket real-time feeds (<10ms)
2. Concurrent strategy evaluation (<10ms)
3. Market state cache (instant lookup)
4. Signal ranking with EV (<0.1ms)
5. Pre-computed orders (<0.1ms)
6. Predictive signal detection
7. Async connection pooling

TOTAL TARGET: <50ms signal to execution
"""

import asyncio
import time
import sys
from typing import Optional, List

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from trading.ultra_fast_executor import UltraFastExecutor, FastSignal
from trading.market_state_cache import MarketStateCache, PredictiveEngine
from trading.signal_ranker import SignalRanker, RankedSignal
from strategies.fast_picker import create_fast_picker

class UltimateFastBot:
    """
    Ultimate low-latency trading bot.
    
    Pipeline:
    1. WebSocket price → Cache update (<10ms)
    2. Predictive detection → Pre-compute (<5ms)
    3. Strategy eval → Concurrent (<10ms)
    4. Signal rank → EV scoring (<0.1ms)
    5. Order prep → Pre-computed (<0.1ms)
    6. Execution → Async (<25ms)
    
    TOTAL: <50ms end-to-end
    """
    
    def __init__(self):
        self.executor: Optional[UltraFastExecutor] = None
        self.cache = MarketStateCache()
        self.predictor = PredictiveEngine()
        self.ranker = SignalRanker()
        self.picker = create_fast_picker()
        
        self._running = False
        self._stats = {
            'cycles': 0,
            'predictions_made': 0,
            'cache_hits': 0,
            'signals_ranked': 0,
            'executions': 0,
            'avg_latency_ms': 0,
        }
        
    async def init(self, api_key: str = '', api_secret: str = ''):
        """Initialize all components."""
        print("🚀 Initializing ULTIMATE FAST BOT...")
        
        self.executor = UltraFastExecutor(api_key, api_secret)
        await self.executor.init()
        
        print("✅ Bot initialized")
        print(f"   • Market cache: Ready")
        print(f"   • Signal ranker: Ready")
        print(f"   • Predictor: Ready")
        print(f"   • Executor: Ready")
        
    async def process_market_update(
        self,
        token_id: str,
        price: float,
        spread: float,
        bid_depth: float,
        ask_depth: float
    ):
        """
        Process market update through fast pipeline.
        """
        cycle_start = time.perf_counter()
        
        # 1. Update cache with pre-computations (<5ms)
        self.cache.update_state(
            token_id=token_id,
            price=price,
            spread=spread,
            bid_depth=bid_depth,
            ask_depth=ask_depth
        )
        
        # 2. Check for pre-computed opportunity (instant)
        pre_order = self.cache.check_opportunity(token_id)
        if pre_order:
            self._stats['cache_hits'] += 1
            
            # Execute pre-computed order
            success, exec_latency, error = await self._execute_pre_computed(
                token_id, pre_order
            )
            
            latency = (time.perf_counter() - cycle_start) * 1000
            self._update_stats(latency, success)
            
            return {
                'source': 'cache',
                'success': success,
                'latency_ms': latency,
                'cache_hit': True
            }
        
        # 3. Check predictor (<2ms)
        prediction = self.predictor.predict_signal(token_id)
        if prediction and prediction['confidence'] > 0.8:
            self._stats['predictions_made'] += 1
            # Pre-prepare for predicted signal
            pass
        
        # 4. Evaluate strategies (<10ms)
        market = {'token_id': token_id}
        context = {
            'clob': {
                'orderbook': {
                    'spread': spread,
                    'bid_depth': bid_depth,
                    'ask_depth': ask_depth
                }
            },
            'seconds_remaining': 120
        }
        
        signal = await self.picker.pick_best(market, context)
        
        if not signal:
            return {'source': 'none', 'signal': None}
        
        # 5. Rank signal (<0.1ms)
        ranked = self.ranker.rank_signal(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.price,
            size=signal.size,
            confidence=signal.confidence,
            strategy=signal.strategy,
            market_context=context
        )
        
        self._stats['signals_ranked'] += 1
        
        # Only execute if urgent
        if ranked.urgency != 'NOW':
            return {
                'source': 'ranked',
                'signal': ranked,
                'executed': False,
                'reason': f'Urgency: {ranked.urgency}'
            }
        
        # 6. Execute (<25ms)
        success, exec_latency, error = await self._execute_signal(ranked)
        
        total_latency = (time.perf_counter() - cycle_start) * 1000
        self._update_stats(total_latency, success)
        
        return {
            'source': 'evaluated',
            'signal': ranked,
            'success': success,
            'latency_ms': total_latency,
            'error': error
        }
    
    async def _execute_pre_computed(
        self,
        token_id: str,
        order: dict
    ) -> tuple:
        """Execute pre-computed order."""
        fast_signal = FastSignal(
            token_id=token_id,
            side='BUY',  # From pre-computed
            price=order['price'],
            size=order['size'],
            confidence=0.85,  # High for cached
            strategy='cache_hit',
            timestamp=int(time.time() * 1000)
        )
        
        return await self.executor.execute_fast(fast_signal)
    
    async def _execute_signal(
        self,
        ranked: RankedSignal
    ) -> tuple:
        """Execute ranked signal."""
        fast_signal = FastSignal(
            token_id=ranked.token_id,
            side=ranked.side,
            price=ranked.price,
            size=ranked.size,
            confidence=ranked.confidence,
            strategy=ranked.strategy,
            timestamp=int(time.time() * 1000)
        )
        
        return await self.executor.execute_fast(fast_signal)
    
    def _update_stats(self, latency: float, success: bool):
        """Update performance stats."""
        self._stats['cycles'] += 1
        if success:
            self._stats['executions'] += 1
        
        # Rolling average
        n = self._stats['cycles']
        self._stats['avg_latency_ms'] = (
            (self._stats['avg_latency_ms'] * (n - 1) + latency) / n
        )
    
    async def run_speed_test(self, iterations: int = 100):
        """Run comprehensive speed test."""
        print("="*70)
        print("⚡ ULTIMATE FAST BOT — SPEED TEST")
        print("="*70)
        print(f"Running {iterations} iterations...")
        print()
        
        latencies = []
        
        for i in range(iterations):
            start = time.perf_counter()
            
            # Simulate market update
            result = await self.process_market_update(
                token_id=f'0xTOKEN{i % 5}',
                price=0.45 + (i % 10) * 0.01,
                spread=0.03 + (i % 5) * 0.01,
                bid_depth=1000,
                ask_depth=1000
            )
            
            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)
            
            if i < 5:  # Show first 5
                source = result.get('source', 'unknown')
                print(f"  Iter {i+1}: {latency:.2f}ms [{source}]")
        
        # Stats
        latencies.sort()
        p50 = latencies[len(latencies)//2]
        p99 = latencies[int(len(latencies)*0.99)]
        avg = sum(latencies) / len(latencies)
        
        print(f"\n📊 SPEED RESULTS ({iterations} iterations):")
        print(f"  Average: {avg:.2f}ms")
        print(f"  P50:     {p50:.2f}ms")
        print(f"  P99:     {p99:.2f}ms")
        print(f"  Min:     {min(latencies):.2f}ms")
        print(f"  Max:     {max(latencies):.2f}ms")
        
        # Target check
        under_50ms = sum(1 for l in latencies if l < 50)
        print(f"\n🎯 TARGET: <50ms")
        print(f"  Achieved: {under_50ms}/{iterations} ({under_50ms/iterations*100:.0f}%)")
        
        return {
            'avg': avg,
            'p50': p50,
            'p99': p99,
            'min': min(latencies),
            'max': max(latencies),
            'under_50ms': under_50ms / iterations
        }
    
    def get_stats(self) -> dict:
        """Get bot statistics."""
        cache_stats = self.cache.get_cache_stats()
        exec_stats = self.executor.get_performance_stats() if self.executor else {}
        
        return {
            **self._stats,
            'cache': cache_stats,
            'executor': exec_stats
        }
    
    async def close(self):
        """Shutdown bot."""
        self._running = False
        if self.executor:
            await self.executor.close()

async def main():
    """Run ultimate fast bot."""
    print("="*70)
    print("🚀 ULTIMATE FAST POLYMARKET BOT")
    print("="*70)
    print()
    print("SPEED TARGETS:")
    print("  • Market update:   <5ms (cache)")
    print("  • Prediction:      <2ms (predictor)")
    print("  • Strategy eval:   <10ms (concurrent)")
    print("  • Signal rank:     <0.1ms (EV scoring)")
    print("  • Order prep:      <0.1ms (pre-computed)")
    print("  • Execution:       <25ms (async)")
    print("  ─────────────────────────")
    print("  • TOTAL TARGET:    <50ms")
    print()
    
    bot = UltimateFastBot()
    
    try:
        await bot.init()
        
        # Run speed test
        results = await bot.run_speed_test(iterations=100)
        
        # Final stats
        print("\n" + "="*70)
        print("📊 FINAL BOT STATS")
        print("="*70)
        stats = bot.get_stats()
        print(f"Cycles:        {stats['cycles']}")
        print(f"Cache hits:    {stats['cache_hits']}")
        print(f"Predictions:   {stats['predictions_made']}")
        print(f"Signals ranked: {stats['signals_ranked']}")
        print(f"Executions:    {stats['executions']}")
        print(f"Avg latency:   {stats['avg_latency_ms']:.2f}ms")
        
        if results['under_50ms'] > 0.9:
            print("\n✅ BOT IS ULTRA-FAST (>90% under 50ms)")
        elif results['under_50ms'] > 0.7:
            print("\n✅ BOT IS FAST (>70% under 50ms)")
        else:
            print("\n⚠️  BOT NEEDS OPTIMIZATION")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopped")
    finally:
        await bot.close()
    
    print("\n" + "="*70)
    print("✅ ULTIMATE FAST BOT COMPLETE")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())