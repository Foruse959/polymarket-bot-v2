#!/usr/bin/env python3
"""
Fast Strategy Picker — Concurrent Evaluation + Early Exit

Optimizations:
1. Evaluates ALL strategies in parallel
2. Early exit if high-confidence signal found
3. Pre-filter markets (skip obvious losers)
4. Minimal allocations (avoid GC)
5. JIT compilation ready
"""

import asyncio
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import functools

@dataclass(slots=True)  # slots=True for less memory, faster access
class FastSignal:
    """Minimal signal structure — fast creation."""
    token_id: str
    side: str
    price: float
    size: float
    confidence: float
    strategy: str
    latency_ms: float

class FastStrategyPicker:
    """
    Ultra-fast strategy evaluation.
    
    Target: <10ms from market data to signal
    """
    
    # Confidence thresholds
    CONF_HIGH = 0.85  # Take immediately
    CONF_MED = 0.70   # Consider
    CONF_LOW = 0.60   # Minimum
    
    # Early exit — if we find CONF_HIGH, stop evaluating others
    EARLY_EXIT = True
    
    def __init__(self):
        self.strategies: Dict[str, callable] = {}
        self._executor = ThreadPoolExecutor(max_workers=8)
        self._perf_stats = {
            'evaluations': 0,
            'signals_found': 0,
            'avg_latency_ms': 0,
        }
    
    def add_strategy(self, name: str, strategy_fn: callable):
        """Add a strategy function."""
        self.strategies[name] = strategy_fn
    
    async def pick_best(
        self,
        market: Dict,
        context: Dict,
        timeout_ms: float = 10.0
    ) -> Optional[FastSignal]:
        """
        Pick best strategy signal.
        
        Evaluates all strategies concurrently.
        Returns best signal or None.
        """
        start = time.perf_counter()
        
        # Pre-filter: Skip if no opportunity
        if not self._prefilter(market, context):
            return None
        
        # Evaluate all strategies concurrently
        signals = await self._evaluate_all_concurrent(market, context)
        
        # Sort by confidence (descending)
        signals.sort(key=lambda s: s.confidence, reverse=True)
        
        # Return best if meets threshold
        if signals and signals[0].confidence >= self.CONF_LOW:
            best = signals[0]
            
            # Update stats
            self._perf_stats['evaluations'] += 1
            self._perf_stats['signals_found'] += 1
            latency = (time.perf_counter() - start) * 1000
            self._perf_stats['avg_latency_ms'] = (
                (self._perf_stats['avg_latency_ms'] * (self._perf_stats['evaluations'] - 1) + latency)
                / self._perf_stats['evaluations']
            )
            
            return FastSignal(
                token_id=best.token_id,
                side=best.side,
                price=best.price,
                size=best.size,
                confidence=best.confidence,
                strategy=best.strategy,
                latency_ms=latency
            )
        
        return None
    
    def _prefilter(self, market: Dict, context: Dict) -> bool:
        """
        Fast pre-filter to skip obvious losers.
        
        Returns False if market should be skipped.
        """
        # Skip if too close to expiry
        seconds_left = context.get('seconds_remaining', 300)
        if seconds_left < 30:
            return False
        
        # Skip if no liquidity info
        book = context.get('clob', {}).get('orderbook', {})
        if not book:
            return False
        
        # Skip if spread too wide
        spread = book.get('spread', 1.0)
        if spread > 0.10:  # >10 cent spread
            return False
        
        return True
    
    async def _evaluate_all_concurrent(
        self,
        market: Dict,
        context: Dict
    ) -> List[FastSignal]:
        """
        Evaluate all strategies concurrently.
        """
        # Create tasks
        tasks = [
            self._evaluate_one(name, fn, market, context)
            for name, fn in self.strategies.items()
        ]
        
        # Run all with early exit option
        if self.EARLY_EXIT:
            # Use as_completed to check results as they arrive
            signals = []
            for coro in asyncio.as_completed(tasks):
                try:
                    signal = await coro
                    if signal:
                        signals.append(signal)
                        # Early exit if high confidence
                        if signal.confidence >= self.CONF_HIGH:
                            break
                except Exception:
                    pass
            return signals
        else:
            # Wait for all
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r for r in results if isinstance(r, FastSignal)]
    
    async def _evaluate_one(
        self,
        name: str,
        strategy_fn: callable,
        market: Dict,
        context: Dict
    ) -> Optional[FastSignal]:
        """Evaluate single strategy."""
        try:
            # Run in thread pool if sync
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    functools.partial(strategy_fn, market, context)
                ),
                timeout=0.005  # 5ms timeout per strategy
            )
            
            if result and result.confidence >= self.CONF_LOW:
                return result
                
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        
        return None
    
    def get_stats(self) -> Dict:
        """Get performance statistics."""
        return self._perf_stats.copy()

# Strategy implementations (ultra-fast versions)
def arb_strategy_fast(market: Dict, context: Dict) -> Optional[FastSignal]:
    """
    Ultra-fast arb detection.
    
    Checks if YES + NO < 0.98
    """
    clob = context.get('clob', {})
    
    up_book = clob.get('up_book', {})
    down_book = clob.get('down_book', {})
    
    if not up_book or not down_book:
        return None
    
    up_ask = up_book.get('best_ask', 1.0)
    down_ask = down_book.get('best_ask', 1.0)
    combined = up_ask + down_ask
    
    if combined < 0.95:  # Guaranteed profit
        return FastSignal(
            token_id=market.get('token_id', ''),
            side='BOTH',
            price=combined / 2,
            size=10.0,
            confidence=0.95,
            strategy='arb_fast',
            latency_ms=0
        )
    
    return None

def time_decay_fast(market: Dict, context: Dict) -> Optional[FastSignal]:
    """
    Ultra-fast time decay check.
    """
    seconds = context.get('seconds_remaining', 300)
    
    # Only trade in last 2 minutes
    if seconds > 120:
        return None
    
    # Get price direction
    prob = market.get('up_probability', 0.5)
    
    if prob > 0.65:
        return FastSignal(
            token_id=market.get('token_id', ''),
            side='UP',
            price=prob,
            size=5.0,
            confidence=0.80,
            strategy='time_decay_fast',
            latency_ms=0
        )
    elif prob < 0.35:
        return FastSignal(
            token_id=market.get('token_id', ''),
            side='DOWN',
            price=1-prob,
            size=5.0,
            confidence=0.80,
            strategy='time_decay_fast',
            latency_ms=0
        )
    
    return None

def spread_scalper_fast(market: Dict, context: Dict) -> Optional[FastSignal]:
    """
    Ultra-fast spread scalping.
    """
    book = context.get('clob', {}).get('orderbook', {})
    
    spread = book.get('spread', 0)
    if spread > 0.05:  # Wide spread
        best_bid = book.get('best_bid', 0)
        best_ask = book.get('best_ask', 1)
        mid = (best_bid + best_ask) / 2
        
        return FastSignal(
            token_id=market.get('token_id', ''),
            side='BUY' if mid < 0.5 else 'SELL',
            price=mid,
            size=3.0,
            confidence=0.70,
            strategy='spread_scalper_fast',
            latency_ms=0
        )
    
    return None

def create_fast_picker() -> FastStrategyPicker:
    """Create picker with fast strategies."""
    picker = FastStrategyPicker()
    
    picker.add_strategy('arb', arb_strategy_fast)
    picker.add_strategy('time_decay', time_decay_fast)
    picker.add_strategy('spread', spread_scalper_fast)
    
    return picker

async def main():
    """Test fast picker."""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("="*70)
    print("FAST PICKER TEST")
    print("="*70)
    
    picker = create_fast_picker()
    
    # Test market
    market = {
        'token_id': '0x123',
        'up_probability': 0.75,
    }
    
    context = {
        'seconds_remaining': 60,
        'clob': {
            'orderbook': {
                'best_bid': 0.48,
                'best_ask': 0.52,
                'spread': 0.04
            },
            'up_book': {'best_ask': 0.47},
            'down_book': {'best_ask': 0.48}
        }
    }
    
    print("\n📊 Testing fast evaluation...")
    
    # Run 100 evaluations
    start = time.perf_counter()
    for _ in range(100):
        signal = await picker.pick_best(market, context)
    elapsed = (time.perf_counter() - start) * 1000
    
    print(f"100 evaluations in {elapsed:.1f}ms")
    print(f"Avg: {elapsed/100:.2f}ms per evaluation")
    
    if signal:
        print(f"\n✅ Signal: {signal.strategy} @ {signal.confidence:.0%} confidence")
    
    stats = picker.get_stats()
    print(f"\n📈 Stats: {stats}")
    
    print("\n" + "="*70)
    print("✅ FAST PICKER READY")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())