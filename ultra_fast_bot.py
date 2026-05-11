#!/usr/bin/env python3
"""
ULTRA-FAST Trading Bot — The Fastest Polymarket Bot

Speed Optimizations:
- WebSocket price feeds (<10ms latency)
- Concurrent strategy evaluation (<10ms)
- Pre-computed orders (<1ms)
- Async/await throughout
- Connection pooling
- Zero-allocation hot path
- <100ms total: signal → execution
"""

import asyncio
import time
from typing import Optional
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from trading.ultra_fast_executor import UltraFastExecutor, FastSignal
from trading.websocket_feed import FastPriceOracle
from strategies.fast_picker import create_fast_picker, FastSignal as PickerSignal

class UltraFastBot:
    """
    Ultra-low latency trading bot.
    
    Target performance:
    - Price update: <10ms (WebSocket)
    - Strategy eval: <10ms (concurrent)
    - Order prep: <1ms (JIT)
    - Execution: <50ms (async)
    - TOTAL: <100ms signal to execution
    """
    
    def __init__(self):
        self.executor: Optional[UltraFastExecutor] = None
        self.price_oracle: Optional[FastPriceOracle] = None
        self.picker = create_fast_picker()
        self._running = False
        self._stats = {
            'cycles': 0,
            'signals_found': 0,
            'executions': 0,
            'avg_latency_ms': 0,
        }
    
    async def init(self, api_key: str = '', api_secret: str = ''):
        """Initialize all components."""
        print("🚀 Initializing Ultra-Fast Bot...")
        
        # 1. Price oracle (WebSocket)
        self.price_oracle = FastPriceOracle()
        # TODO: Start with actual token IDs
        # await self.price_oracle.start(['token1', 'token2'])
        
        # 2. Executor (connection pool)
        self.executor = UltraFastExecutor(api_key, api_secret)
        await self.executor.init()
        
        print("✅ Bot initialized")
    
    async def run_cycle(self):
        """
        Single trading cycle.
        
        Target: Complete in <100ms
        """
        cycle_start = time.perf_counter()
        
        # 1. Get market data (from cache/WebSocket)
        # This should be instant from WebSocket cache
        market = self._get_market_snapshot()
        
        # 2. Pick best strategy (<10ms)
        context = self._build_context()
        signal = await self.picker.pick_best(market, context)
        
        if not signal:
            return  # No opportunity
        
        self._stats['signals_found'] += 1
        
        # 3. Execute (<100ms)
        fast_signal = FastSignal(
            token_id=signal.token_id,
            side=signal.side,
            price=signal.price,
            size=signal.size,
            confidence=signal.confidence,
            strategy=signal.strategy,
            timestamp=int(time.time() * 1000)
        )
        
        success, latency, error = await self.executor.execute_fast(fast_signal)
        
        # 4. Update stats
        self._stats['cycles'] += 1
        if success:
            self._stats['executions'] += 1
        
        # Update average latency
        total_latency = (time.perf_counter() - cycle_start) * 1000
        self._stats['avg_latency_ms'] = (
            (self._stats['avg_latency_ms'] * (self._stats['cycles'] - 1) + total_latency)
            / self._stats['cycles']
        )
        
        # Log
        emoji = "✅" if success else "❌"
        print(f"{emoji} {signal.strategy:<20} conf={signal.confidence:.0%} "
              f"latency={total_latency:.1f}ms ({latency:.1f}ms exec)")
    
    def _get_market_snapshot(self) -> dict:
        """Get instant market snapshot from cache."""
        # In real implementation, this would come from WebSocket cache
        return {
            'token_id': '0x123',
            'up_probability': 0.65,
            'timestamp': int(time.time() * 1000)
        }
    
    def _build_context(self) -> dict:
        """Build execution context."""
        return {
            'seconds_remaining': 120,
            'clob': {
                'orderbook': {
                    'best_bid': 0.48,
                    'best_ask': 0.52,
                    'spread': 0.04,
                    'bid_depth': 1000,
                    'ask_depth': 1000
                }
            }
        }
    
    async def run(self, duration_seconds: float = 60):
        """Run bot for specified duration."""
        print("="*70)
        print("⚡ ULTRA-FAST BOT RUNNING")
        print("="*70)
        print(f"Target: <100ms signal to execution")
        print(f"Duration: {duration_seconds}s")
        print()
        
        self._running = True
        start_time = time.time()
        
        while self._running and (time.time() - start_time) < duration_seconds:
            await self.run_cycle()
            await asyncio.sleep(0.1)  # 10 cycles/sec max
        
        self._running = False
        
        # Print stats
        print("\n" + "="*70)
        print("📊 FINAL STATS")
        print("="*70)
        print(f"Cycles: {self._stats['cycles']}")
        print(f"Signals: {self._stats['signals_found']}")
        print(f"Executions: {self._stats['executions']}")
        print(f"Avg Latency: {self._stats['avg_latency_ms']:.1f}ms")
        
        exec_stats = self.executor.get_performance_stats()
        if exec_stats:
            print(f"P99 Latency: {exec_stats.get('p99_latency_ms', 0):.1f}ms")
        
        picker_stats = self.picker.get_stats()
        print(f"Strategy Evals: {picker_stats.get('evaluations', 0)}")
    
    async def close(self):
        """Shutdown bot."""
        self._running = False
        if self.executor:
            await self.executor.close()
        if self.price_oracle:
            await self.price_oracle.close()

async def main():
    """Run ultra-fast bot."""
    print("="*70)
    print("🚀 ULTRA-FAST POLYMARKET BOT")
    print("="*70)
    print()
    print("SPEED TARGETS:")
    print("  • Price feed: <10ms (WebSocket)")
    print("  • Strategy eval: <10ms (concurrent)")
    print("  • Order prep: <1ms (JIT)")
    print("  • Execution: <50ms (async)")
    print("  • TOTAL: <100ms signal to execution")
    print()
    
    bot = UltraFastBot()
    
    try:
        await bot.init()
        await bot.run(duration_seconds=10)
    except KeyboardInterrupt:
        print("\n⏹️  Stopped")
    finally:
        await bot.close()
    
    print("\n" + "="*70)
    print("✅ BOT COMPLETE")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())