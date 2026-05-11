#!/usr/bin/env python3
"""
Market State Cache — Predictive Pre-computation

Pre-computes market states and potential signals.
Orders ready BEFORE opportunity arises.
"""

import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass(slots=True)
class MarketState:
    """Pre-computed market state."""
    token_id: str
    price: float
    spread: float
    bid_depth: float
    ask_depth: float
    timestamp: float
    opportunity_score: float
    recommended_strategy: str
    pre_computed_order: Optional[Dict] = None

class MarketStateCache:
    """
    Predictive market state caching.
    
    Pre-computes:
    - Market conditions
    - Opportunity scores
    - Recommended strategies
    - Pre-built orders
    
    Result: Sub-millisecond signal detection
    """
    
    def __init__(self, max_states: int = 1000):
        self._states: Dict[str, MarketState] = {}
        self._opportunity_queue: List[str] = []  # Sorted by score
        self._max_states = max_states
        self._last_update = 0
        self._update_interval = 0.1  # 100ms refresh
        self._hit_count = 0
        self._miss_count = 0
        
    def update_state(
        self,
        token_id: str,
        price: float,
        spread: float,
        bid_depth: float,
        ask_depth: float,
        strategy_scores: Optional[Dict] = None
    ):
        """
        Update market state with pre-computations.
        """
        # Calculate opportunity score (0-100)
        opp_score = self._calc_opportunity_score(
            spread, bid_depth, ask_depth, strategy_scores
        )
        
        # Determine best strategy
        best_strategy = self._pick_best_strategy(strategy_scores or {})
        
        # Pre-compute order if high opportunity
        pre_order = None
        if opp_score > 70:
            pre_order = self._pre_compute_order(token_id, price, opp_score)
        
        state = MarketState(
            token_id=token_id,
            price=price,
            spread=spread,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            timestamp=time.time(),
            opportunity_score=opp_score,
            recommended_strategy=best_strategy,
            pre_computed_order=pre_order
        )
        
        self._states[token_id] = state
        self._update_opportunity_queue()
        
    def _calc_opportunity_score(
        self,
        spread: float,
        bid_depth: float,
        ask_depth: float,
        strategy_scores: Optional[Dict]
    ) -> float:
        """
        Calculate opportunity score (0-100).
        
        Higher = better opportunity
        """
        score = 50.0  # Base score
        
        # Spread bonus (wider spread = more edge)
        if spread > 0.08:
            score += 20
        elif spread > 0.05:
            score += 10
        
        # Depth penalty (thin liquidity = risk)
        min_depth = min(bid_depth, ask_depth)
        if min_depth < 10:
            score -= 30
        elif min_depth < 50:
            score -= 10
        elif min_depth > 500:
            score += 10
        
        # Strategy score bonus
        if strategy_scores:
            max_score = max(strategy_scores.values())
            score += max_score * 20  # Up to +20
        
        return max(0, min(100, score))
    
    def _pick_best_strategy(self, strategy_scores: Dict) -> str:
        """Pick best strategy from scores."""
        if not strategy_scores:
            return "arb_fast"
        
        return max(strategy_scores.items(), key=lambda x: x[1])[0]
    
    def _pre_compute_order(
        self,
        token_id: str,
        price: float,
        opp_score: float
    ) -> Dict:
        """
        Pre-compute order structure.
        
        Ready to submit instantly.
        """
        # Calculate optimal size based on opportunity
        if opp_score > 85:
            size = 10.0
        elif opp_score > 70:
            size = 5.0
        else:
            size = 3.0
        
        return {
            'token_id': token_id,
            'price': price,
            'size': size,
            'prepared_at': time.time(),
            'valid_for': 5.0,  # Valid for 5 seconds
        }
    
    def _update_opportunity_queue(self):
        """Keep opportunity queue sorted."""
        # Sort by opportunity score
        sorted_tokens = sorted(
            self._states.keys(),
            key=lambda t: self._states[t].opportunity_score,
            reverse=True
        )
        self._opportunity_queue = sorted_tokens[:20]  # Top 20
        
    def get_state(self, token_id: str) -> Optional[MarketState]:
        """Get cached state (instant)."""
        if token_id in self._states:
            self._hit_count += 1
            return self._states[token_id]
        self._miss_count += 1
        return None
    
    def get_top_opportunities(self, n: int = 5) -> List[MarketState]:
        """Get top N opportunities (pre-sorted)."""
        return [
            self._states[t] for t in self._opportunity_queue[:n]
            if t in self._states
        ]
    
    def check_opportunity(self, token_id: str) -> Optional[Dict]:
        """
        Check if opportunity exists (instant lookup).
        
        Returns pre-computed order if high opportunity.
        """
        state = self.get_state(token_id)
        if not state:
            return None
        
        # Check freshness
        if time.time() - state.timestamp > 1.0:  # >1s old
            return None
        
        # Check if high opportunity
        if state.opportunity_score < 60:
            return None
        
        # Return pre-computed order if available
        if state.pre_computed_order:
            order = state.pre_computed_order.copy()
            order['timestamp'] = int(time.time() * 1000)  # Update timestamp
            return order
        
        return None
    
    def get_cache_stats(self) -> Dict:
        """Get cache performance stats."""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0
        
        return {
            'states_cached': len(self._states),
            'hit_count': self._hit_count,
            'miss_count': self._miss_count,
            'hit_rate': hit_rate,
            'top_opportunities': len(self._opportunity_queue)
        }
    
    def cleanup_old_states(self, max_age_seconds: float = 5.0):
        """Remove old states."""
        now = time.time()
        to_remove = [
            t for t, s in self._states.items()
            if now - s.timestamp > max_age_seconds
        ]
        for t in to_remove:
            del self._states[t]
        
        if to_remove:
            self._update_opportunity_queue()

class PredictiveEngine:
    """
    Predictive signal engine.
    
    Anticipates signals before they fully form.
    """
    
    def __init__(self):
        self.cache = MarketStateCache()
        self._price_history: Dict[str, List[float]] = defaultdict(list)
        self._prediction_threshold = 0.75
        
    def update_price(self, token_id: str, price: float):
        """Update price history."""
        self._price_history[token_id].append(price)
        
        # Keep last 50 prices
        if len(self._price_history[token_id]) > 50:
            self._price_history[token_id] = self._price_history[token_id][-50:]
        
        # Check for forming opportunity
        self._check_forming_opportunity(token_id)
    
    def _check_forming_opportunity(self, token_id: str):
        """Check if opportunity is forming."""
        prices = self._price_history[token_id]
        if len(prices) < 10:
            return
        
        # Simple trend detection
        recent = prices[-5:]
        older = prices[-10:-5]
        
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        # If trending strongly
        if abs(recent_avg - older_avg) > 0.02:
            # Pre-compute potential order
            direction = 'UP' if recent_avg > older_avg else 'DOWN'
            
            # Update cache with prediction
            self.cache.update_state(
                token_id=token_id,
                price=recent_avg,
                spread=0.04,
                bid_depth=1000,
                ask_depth=1000,
                strategy_scores={'predicted_trend': 0.8}
            )
    
    def predict_signal(self, token_id: str) -> Optional[Dict]:
        """
        Predict upcoming signal.
        
        Returns potential signal if confidence high.
        """
        prices = self._price_history.get(token_id, [])
        if len(prices) < 20:
            return None
        
        # Calculate momentum
        momentum = self._calc_momentum(prices)
        
        if abs(momentum) > self._prediction_threshold:
            return {
                'token_id': token_id,
                'predicted_direction': 'UP' if momentum > 0 else 'DOWN',
                'confidence': abs(momentum),
                'predicted_in': 2.0,  # Seconds until signal
            }
        
        return None
    
    def _calc_momentum(self, prices: List[float]) -> float:
        """Calculate price momentum (-1 to 1)."""
        if len(prices) < 20:
            return 0
        
        # Short vs long term average
        short = sum(prices[-5:]) / 5
        long = sum(prices[-20:]) / 20
        
        # Normalize to -1 to 1
        diff = (short - long) / long if long > 0 else 0
        return max(-1, min(1, diff * 10))

def main():
    """Test market state cache."""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("="*70)
    print("MARKET STATE CACHE TEST")
    print("="*70)
    
    cache = MarketStateCache()
    
    # Simulate updates
    print("\nSimulating market updates...")
    
    tokens = ['0xBTC', '0xETH', '0xSOL', '0xDOGE', '0xPEPE']
    
    for i, token in enumerate(tokens):
        cache.update_state(
            token_id=token,
            price=0.45 + i * 0.05,
            spread=0.03 + i * 0.01,
            bid_depth=1000 - i * 100,
            ask_depth=1000 - i * 100,
            strategy_scores={
                'arb': 0.8 - i * 0.1,
                'time_decay': 0.7 - i * 0.1
            }
        )
    
    print(f"Cached {len(cache._states)} states")
    
    # Get top opportunities
    print("\nTop 3 Opportunities:")
    for i, state in enumerate(cache.get_top_opportunities(3), 1):
        print(f"{i}. {state.token_id:<10} "
              f"score={state.opportunity_score:.0f} "
              f"strat={state.recommended_strategy:<15} "
              f"{'[PRE-COMPUTED]' if state.pre_computed_order else ''}")
    
    # Test instant lookup
    print("\nInstant lookup test:")
    start = time.perf_counter()
    order = cache.check_opportunity('0xBTC')
    elapsed = (time.perf_counter() - start) * 1000
    
    if order:
        print(f"Order ready in {elapsed:.3f}ms: {order}")
    
    # Cache stats
    stats = cache.get_cache_stats()
    print(f"\nCache stats: {stats}")
    
    print("\n" + "="*70)
    print("MARKET STATE CACHE READY")
    print("="*70)

if __name__ == "__main__":
    main()