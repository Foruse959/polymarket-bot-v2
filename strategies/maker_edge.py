"""
Maker Edge Strategy — Based on Jon Becker's Research

Key insights from Becker's analysis:
1. Makers earn +1.12% avg excess return vs Takers losing -1.12%
2. The "maker advantage" is 2.24 percentage points
3. Strategy: Place limit orders on NO side at high prices
4. Sell into biased YES taker flow
5. Finance markets most efficient (0.17pp gap), Sports/Entertainment least (2-4.79pp)

Implementation:
- Always act as maker (place limit orders)
- Place orders on NO side at prices > 80¢ (underpriced)
- Target Sports and Entertainment markets (less efficient)
- Use dynamic spreads based on category
"""

import time
from typing import Dict, Optional, List
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class MakerEdgeStrategy(BaseStrategy):
    """
    Exploit the maker advantage by placing limit orders on the NO side.
    Based on research showing makers consistently outperform takers.
    """

    name = "maker_edge"
    description = "Place limit orders on NO side to earn maker advantage"
    preferred_order_type = "maker"

    def __init__(self):
        self.min_no_price = 0.75  # Minimum NO price to consider (75¢)
        self.max_no_price = 0.95  # Maximum NO price (95¢)
        self.min_edge_bps = 50    # Minimum 50 bps edge required
        self.target_no_holdings = 0.60  # Target 60% NO holdings

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """
        Analyze market for maker edge opportunity.
        
        Strategy: Find markets where NO is trading at attractive prices
        and place limit orders to provide liquidity.
        """
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        category = market.get('category', 'other')
        
        if not clob:
            return None

        # Get orderbook for both sides
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        
        if not up_token or not down_token:
            return None

        up_book = clob.get_orderbook(up_token)
        down_book = clob.get_orderbook(down_token)
        
        if not up_book or not down_book:
            return None

        # Get best NO (DOWN) price
        no_best_bid = down_book['best_bid']  # What we can sell NO for
        no_best_ask = down_book['best_ask']  # What we can buy NO for
        no_mid = down_book['mid_price']
        
        # Get market category spread multiplier
        spread_mult = Config.get_category_spread_multiplier(category)
        
        # Skip if market is too efficient (Finance) and spread is too tight
        base_spread_bps = 100  # 1% base spread target
        target_spread_bps = base_spread_bps * spread_mult
        
        current_spread_bps = down_book['spread_bps']
        
        # Check if there's enough spread to work with
        if current_spread_bps < target_spread_bps * 0.5:
            return None  # Spread too tight for maker edge

        # Strategy 1: Buy NO at attractive prices (> 75¢, < 95¢)
        # This is the "longshot bias" exploitation from Becker
        if self.min_no_price <= no_mid <= self.max_no_price:
            # Place limit order slightly below best ask
            # Target: buy NO at a discount to mid
            limit_price = min(no_best_ask - 0.005, no_mid - 0.01)
            limit_price = max(limit_price, no_best_bid + 0.001)  # Don't cross spread
            
            # Calculate edge vs mid
            edge_bps = (no_mid - limit_price) / no_mid * 10000
            
            if edge_bps >= self.min_edge_bps:
                confidence = self._calculate_confidence(no_mid, category, seconds_remaining)
                
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='DOWN',  # Buying NO
                    token_id=down_token,
                    market_id=market['market_id'],
                    entry_price=no_mid,
                    confidence=confidence,
                    rationale=(f"Maker edge: Buy NO at {limit_price:.3f} "
                              f"(mid: {no_mid:.3f}, edge: {edge_bps:.0f} bps). "
                              f"Category: {category} (mult: {spread_mult:.1f}x). "
                              f"Targeting {target_spread_bps:.0f} bps spread."),
                    metadata={
                        'no_mid': no_mid,
                        'limit_price': limit_price,
                        'edge_bps': edge_bps,
                        'category': category,
                        'spread_mult': spread_mult,
                        'current_spread_bps': current_spread_bps,
                    },
                    order_type='maker',
                    limit_price=limit_price,
                )

        # Strategy 2: Sell YES into biased flow when YES is overpriced
        # Low-priced YES contracts (< 20¢) are overpriced
        yes_mid = up_book['mid_price']
        
        if yes_mid < 0.20:  # Longshot YES is overpriced
            # Place limit order to sell YES above mid
            limit_price = min(up_book['best_ask'] - 0.001, yes_mid + 0.015)
            edge_bps = (limit_price - yes_mid) / yes_mid * 10000
            
            if edge_bps >= self.min_edge_bps:
                confidence = self._calculate_confidence(yes_mid, category, seconds_remaining)
                
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='SELL_UP',  # Selling YES
                    token_id=up_token,
                    market_id=market['market_id'],
                    entry_price=yes_mid,
                    confidence=confidence,
                    rationale=(f"Maker edge: Sell YES at {limit_price:.3f} "
                              f"(mid: {yes_mid:.3f}, edge: {edge_bps:.0f} bps). "
                              f"Longshot overpricing exploitation."),
                    metadata={
                        'yes_mid': yes_mid,
                        'limit_price': limit_price,
                        'edge_bps': edge_bps,
                        'category': category,
                    },
                    order_type='maker',
                    limit_price=limit_price,
                )

        return None

    def _calculate_confidence(self, price: float, category: str, seconds_remaining: int) -> float:
        """Calculate confidence score based on price, category, and time."""
        base_confidence = 0.55
        
        # Higher confidence for extreme prices (longshot bias)
        if price < 0.20 or price > 0.80:
            base_confidence += 0.10
        
        # Category adjustment (less efficient = higher confidence)
        category_mult = {
            'finance': 0.0,
            'politics': 0.02,
            'sports': 0.08,
            'entertainment': 0.10,
            'crypto': 0.05,
            'other': 0.03,
        }
        base_confidence += category_mult.get(category, 0.03)
        
        # Time decay (less confidence near expiry)
        if seconds_remaining < 60:
            base_confidence -= 0.05
        elif seconds_remaining < 300:
            base_confidence -= 0.02
        
        return min(0.95, max(0.30, base_confidence))
