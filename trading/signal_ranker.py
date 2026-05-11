#!/usr/bin/env python3
"""
Signal Ranker — ML-Inspired Fast Scoring

Ranks signals by expected value (EV) instantly.
Pre-computes scores for speed.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import deque

@dataclass(slots=True)
class RankedSignal:
    """Signal with computed rank score."""
    token_id: str
    side: str
    price: float
    size: float
    confidence: float
    strategy: str
    ev: float  # Expected value
    rank_score: float
    urgency: str  # NOW, SOON, LATER

class SignalRanker:
    """
    Ultra-fast signal ranking.
    
    Computes expected value and urgency instantly.
    """
    
    def __init__(self):
        # Historical performance per strategy
        self._strategy_perf: Dict[str, Dict] = {}
        # Recent signals (last 100)
        self._recent_signals: deque = deque(maxlen=100)
        # Pre-computed weights
        self._weights = {
            'confidence': 0.35,
            'ev': 0.30,
            'speed': 0.20,
            'recency': 0.15,
        }
    
    def rank_signal(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        confidence: float,
        strategy: str,
        market_context: Dict
    ) -> RankedSignal:
        """
        Rank signal instantly.
        
        Returns RankedSignal with EV and urgency.
        """
        # Calculate expected value
        ev = self._calculate_ev(confidence, price, size, strategy)
        
        # Calculate urgency
        urgency = self._calculate_urgency(market_context)
        
        # Calculate composite rank score
        rank_score = self._calculate_rank_score(
            confidence, ev, urgency, strategy
        )
        
        return RankedSignal(
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            confidence=confidence,
            strategy=strategy,
            ev=ev,
            rank_score=rank_score,
            urgency=urgency
        )
    
    def _calculate_ev(
        self,
        confidence: float,
        price: float,
        size: float,
        strategy: str
    ) -> float:
        """
        Calculate expected value.
        
        EV = (Win Probability × Win Amount) - (Loss Probability × Loss Amount)
        """
        # Get strategy win rate
        perf = self._strategy_perf.get(strategy, {'win_rate': 0.55, 'avg_win': 0.08})
        win_rate = perf.get('win_rate', 0.55)
        avg_win = perf.get('avg_win', 0.08)
        avg_loss = 0.05  # Assumed
        
        # Adjust by confidence
        adjusted_win_rate = win_rate * confidence
        
        # Calculate EV per dollar
        ev_per_dollar = (
            adjusted_win_rate * avg_win -
            (1 - adjusted_win_rate) * avg_loss
        )
        
        return ev_per_dollar * size
    
    def _calculate_urgency(self, market_context: Dict) -> str:
        """
        Calculate urgency based on market conditions.
        
        NOW: Execute immediately
        SOON: Execute within 5 seconds
        LATER: Can wait
        """
        seconds_left = market_context.get('seconds_remaining', 300)
        spread = market_context.get('spread', 0.10)
        depth = market_context.get('depth', 100)
        
        # Urgent if:
        # - Less than 60 seconds to expiry
        # - Spread widening
        # - Depth drying up
        
        if seconds_left < 60:
            return "NOW"
        elif spread > 0.08 or depth < 50:
            return "NOW"
        elif seconds_left < 120 or spread > 0.05:
            return "SOON"
        else:
            return "LATER"
    
    def _calculate_rank_score(
        self,
        confidence: float,
        ev: float,
        urgency: str,
        strategy: str
    ) -> float:
        """
        Calculate composite rank score (0-100).
        """
        w = self._weights
        
        # Confidence component
        conf_score = confidence * 100
        
        # EV component (normalize to 0-100)
        ev_score = min(100, max(0, ev * 100))
        
        # Speed component (based on urgency)
        speed_map = {"NOW": 100, "SOON": 70, "LATER": 40}
        speed_score = speed_map.get(urgency, 50)
        
        # Recency bonus (if strategy performed well recently)
        recent_perf = self._get_recent_performance(strategy)
        recency_score = recent_perf * 100
        
        # Weighted sum
        rank_score = (
            w['confidence'] * conf_score +
            w['ev'] * ev_score +
            w['speed'] * speed_score +
            w['recency'] * recency_score
        )
        
        return rank_score
    
    def _get_recent_performance(self, strategy: str) -> float:
        """Get recent win rate for strategy (last 20 trades)."""
        recent = [
            s for s in self._recent_signals
            if s.get('strategy') == strategy
        ][-20:]
        
        if not recent:
            return 0.5
        
        wins = sum(1 for s in recent if s.get('won', False))
        return wins / len(recent)
    
    def rank_multiple(
        self,
        signals: List[Dict],
        market_context: Dict
    ) -> List[RankedSignal]:
        """
        Rank multiple signals at once.
        
        Returns sorted by rank_score (descending).
        """
        ranked = []
        for sig in signals:
            ranked.append(self.rank_signal(
                token_id=sig['token_id'],
                side=sig['side'],
                price=sig['price'],
                size=sig['size'],
                confidence=sig['confidence'],
                strategy=sig['strategy'],
                market_context=market_context
            ))
        
        # Sort by rank score
        ranked.sort(key=lambda x: x.rank_score, reverse=True)
        return ranked
    
    def get_top_signals(
        self,
        signals: List[Dict],
        market_context: Dict,
        n: int = 3
    ) -> List[RankedSignal]:
        """Get top N signals."""
        ranked = self.rank_multiple(signals, market_context)
        return ranked[:n]
    
    def update_performance(
        self,
        strategy: str,
        won: bool,
        pnl: float
    ):
        """Update strategy performance."""
        if strategy not in self._strategy_perf:
            self._strategy_perf[strategy] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0.5,
                'avg_win': 0.05
            }
        
        perf = self._strategy_perf[strategy]
        perf['trades'] += 1
        if won:
            perf['wins'] += 1
        perf['total_pnl'] += pnl
        perf['win_rate'] = perf['wins'] / perf['trades']
        
        if won and pnl > 0:
            # Update avg win
            perf['avg_win'] = (
                (perf['avg_win'] * (perf['wins'] - 1) + pnl)
                / perf['wins'] if perf['wins'] > 0 else 0.05
            )
        
        # Add to recent signals
        self._recent_signals.append({
            'strategy': strategy,
            'won': won,
            'pnl': pnl,
            'timestamp': time.time()
        })

def main():
    """Test signal ranker."""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("="*70)
    print("SIGNAL RANKER TEST")
    print("="*70)
    
    ranker = SignalRanker()
    
    # Test signals
    signals = [
        {
            'token_id': '0x123',
            'side': 'UP',
            'price': 0.65,
            'size': 10.0,
            'confidence': 0.85,
            'strategy': 'arb_fast'
        },
        {
            'token_id': '0x123',
            'side': 'DOWN',
            'price': 0.35,
            'size': 5.0,
            'confidence': 0.72,
            'strategy': 'time_decay'
        },
        {
            'token_id': '0x456',
            'side': 'BUY',
            'price': 0.50,
            'size': 3.0,
            'confidence': 0.68,
            'strategy': 'spread_scalper'
        }
    ]
    
    market_context = {
        'seconds_remaining': 45,
        'spread': 0.06,
        'depth': 80
    }
    
    print("\nRanking signals...")
    start = time.perf_counter()
    
    ranked = ranker.rank_multiple(signals, market_context)
    
    elapsed = (time.perf_counter() - start) * 1000
    
    print(f"Ranked {len(signals)} signals in {elapsed:.2f}ms")
    print()
    
    for i, sig in enumerate(ranked, 1):
        print(f"{i}. {sig.strategy:<20} "
              f"conf={sig.confidence:.0%} "
              f"ev=${sig.ev:.2f} "
              f"rank={sig.rank_score:.1f} "
              f"[{sig.urgency}]")
    
    print("\n" + "="*70)
    print("SIGNAL RANKER READY")
    print("="*70)

if __name__ == "__main__":
    main()