"""
Longshot Bias Strategy — Exploit Behavioral Market Inefficiencies

Based on research from SII-WANGZJ data and Becker's analysis:
1. Low-priced contracts (< 20¢) are systematically overpriced
2. High-priced contracts (> 80¢) are systematically underpriced
3. This is the "Optimism Tax" takers pay — makers capture it
4. Sell YES at longshot prices, buy NO at high prices

The "Optimism Tax":
- Takers overpay for longshots (hope/optimism bias)
- Takers sell winners too cheap (fear/loss aversion)
- Makers collect this premium through limit orders
"""

from typing import Dict, Optional, List
from config import Config
from strategies.base_strategy import BaseStrategy, TradeSignal


class LongshotBiasStrategy(BaseStrategy):
    """
    Exploit longshot bias by taking the opposite side of retail sentiment.
    Sell hope (overpriced longshots), buy fear (underpriced favorites).
    """

    name = "longshot_bias"
    description = "Exploit longshot bias: sell overpriced longshots, buy underpriced favorites"
    preferred_order_type = "maker"

    def __init__(self):
        # Price thresholds for longshot bias
        self.longshot_threshold = 0.20  # < 20¢ = overpriced
        self.favorite_threshold = 0.80  # > 80¢ = underpriced
        
        # Minimum edge required (in bps)
        self.min_edge_bps = 75
        
        # Position sizing limits
        self.max_position_usdc = Config.LONGSHOT_MAX_POSITION_USDC
        
        # Market conditions
        self.min_spread_bps = 30  # Minimum spread to work with

    def get_suitable_timeframes(self) -> List[int]:
        return [5, 15, 30]

    async def analyze(self, market: Dict, context: Dict) -> Optional[TradeSignal]:
        """
        Analyze market for longshot bias exploitation.
        
        Two main opportunities:
        1. Sell YES when price < 20¢ (overpriced due to optimism)
        2. Buy NO when price > 80¢ (underpriced due to pessimism)
        """
        clob = context.get('clob')
        seconds_remaining = context.get('seconds_remaining', 9999)
        
        if not clob:
            return None

        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        
        if not up_token or not down_token:
            return None

        up_book = clob.get_orderbook(up_token)
        down_book = clob.get_orderbook(down_token)
        
        if not up_book or not down_book:
            return None

        yes_mid = up_book['mid_price']
        no_mid = down_book['mid_price']
        
        # Check spread
        yes_spread_bps = up_book['spread_bps']
        no_spread_bps = down_book['spread_bps']
        
        # Opportunity 1: Sell YES at longshot prices (< 20¢)
        # Retail overpays for moonshots — we sell into that demand
        if yes_mid < self.longshot_threshold:
            if yes_spread_bps < self.min_spread_bps:
                return None
            
            # Place limit order to sell YES above mid
            # Target: 1-2¢ above mid price
            premium = max(0.01, yes_mid * 0.10)  # 10% premium or 1¢ min
            limit_price = min(yes_mid + premium, up_book['best_ask'] - 0.001)
            
            # Calculate edge
            edge_bps = (limit_price - yes_mid) / yes_mid * 10000 if yes_mid > 0 else 0
            
            if edge_bps >= self.min_edge_bps:
                confidence = self._calculate_sell_confidence(yes_mid, seconds_remaining)
                
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='SELL_UP',  # Selling YES
                    token_id=up_token,
                    market_id=market['market_id'],
                    entry_price=yes_mid,
                    confidence=confidence,
                    rationale=(f"Longshot bias: Sell YES at {limit_price:.3f} "
                              f"(overpriced at {yes_mid:.3f}, edge: {edge_bps:.0f} bps). "
                              f"Retail optimism tax capture."),
                    metadata={
                        'bias_type': 'longshot_overpriced',
                        'yes_mid': yes_mid,
                        'limit_price': limit_price,
                        'edge_bps': edge_bps,
                        'premium': premium,
                    },
                    order_type='maker',
                    limit_price=limit_price,
                )

        # Opportunity 2: Buy NO at high prices (> 80¢)
        # Retail undervalues high-probability events — we buy the discount
        if no_mid > self.favorite_threshold:
            if no_spread_bps < self.min_spread_bps:
                return None
            
            # Place limit order to buy NO below mid
            # Target: 1-2¢ below mid price
            discount = max(0.01, no_mid * 0.025)  # 2.5% discount or 1¢ min
            limit_price = max(no_mid - discount, down_book['best_bid'] + 0.001)
            
            # Calculate edge
            edge_bps = (no_mid - limit_price) / no_mid * 10000
            
            if edge_bps >= self.min_edge_bps:
                confidence = self._calculate_buy_confidence(no_mid, seconds_remaining)
                
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='DOWN',  # Buying NO
                    token_id=down_token,
                    market_id=market['market_id'],
                    entry_price=no_mid,
                    confidence=confidence,
                    rationale=(f"Longshot bias: Buy NO at {limit_price:.3f} "
                              f"(underpriced at {no_mid:.3f}, edge: {edge_bps:.0f} bps). "
                              f"Retail pessimism discount capture."),
                    metadata={
                        'bias_type': 'favorite_underpriced',
                        'no_mid': no_mid,
                        'limit_price': limit_price,
                        'edge_bps': edge_bps,
                        'discount': discount,
                    },
                    order_type='maker',
                    limit_price=limit_price,
                )

        # Opportunity 3: Extreme mispricing detection
        # When YES is very cheap (< 10¢) or very expensive (> 90¢)
        if yes_mid < 0.10:
            # Extreme longshot — sell at any price above 8¢
            if yes_mid > 0.08:
                limit_price = yes_mid + 0.005
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='SELL_UP',
                    token_id=up_token,
                    market_id=market['market_id'],
                    entry_price=yes_mid,
                    confidence=0.65,
                    rationale=f"Extreme longshot: Sell YES at {limit_price:.3f} (retail lottery ticket overpricing)",
                    metadata={'bias_type': 'extreme_longshot'},
                    order_type='maker',
                    limit_price=limit_price,
                )
        
        if yes_mid > 0.90:
            # Extreme favorite — buy NO at any price below 12¢
            no_implied = 1.0 - yes_mid
            if no_implied < 0.12:
                limit_price = no_implied - 0.002
                return TradeSignal(
                    strategy=self.name,
                    coin=market['coin'],
                    timeframe=market['timeframe'],
                    direction='DOWN',
                    token_id=down_token,
                    market_id=market['market_id'],
                    entry_price=no_implied,
                    confidence=0.70,
                    rationale=f"Extreme favorite: Buy NO at {limit_price:.3f} (retail ignores high prob)",
                    metadata={'bias_type': 'extreme_favorite'},
                    order_type='maker',
                    limit_price=max(0.01, limit_price),
                )

        return None

    def _calculate_sell_confidence(self, yes_price: float, seconds_remaining: int) -> float:
        """Calculate confidence for selling YES (shorting longshot)."""
        # Lower price = more overpriced = higher confidence
        base = 0.60
        
        if yes_price < 0.10:
            base += 0.15
        elif yes_price < 0.15:
            base += 0.10
        else:
            base += 0.05
        
        # Time decay reduces confidence
        if seconds_remaining < 120:
            base -= 0.05
        
        return min(0.90, max(0.35, base))

    def _calculate_buy_confidence(self, no_price: float, seconds_remaining: int) -> float:
        """Calculate confidence for buying NO (buying favorite)."""
        # Higher NO price = more underpriced = higher confidence
        base = 0.65
        
        if no_price > 0.90:
            base += 0.10
        elif no_price > 0.85:
            base += 0.05
        
        # More time = more confidence
        if seconds_remaining > 600:
            base += 0.05
        
        return min(0.92, max(0.40, base))
