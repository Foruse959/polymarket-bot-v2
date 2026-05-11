#!/usr/bin/env python3
"""
Kelly Criterion Position Sizing

Mathematically optimal position sizing based on edge and odds.
Formula: f* = (bp - q) / b
Where:
  f* = fraction of bankroll to bet
  b = odds received (decimal)
  p = probability of win
  q = probability of loss (1 - p)
"""

import math
from typing import Tuple, Optional

class KellyCriterion:
    """Kelly Criterion position sizing calculator."""
    
    # Safety factor - use half-Kelly to reduce volatility
    KELLY_FRACTION = 0.5
    
    # Maximum bet size (don't risk more than this % of bankroll)
    MAX_BET_PCT = 0.10  # 10%
    
    # Minimum edge required to bet
    MIN_EDGE = 0.02  # 2%
    
    @staticmethod
    def calculate_kelly(
        win_prob: float,
        odds: float,
        current_bankroll: float
    ) -> Tuple[float, float, str]:
        """
        Calculate Kelly-optimal bet size.
        
        Args:
            win_prob: Probability of winning (0-1)
            odds: Decimal odds (e.g., 2.0 for even money)
            current_bankroll: Current balance
        
        Returns:
            (bet_size, kelly_fraction, reasoning)
        """
        loss_prob = 1 - win_prob
        
        # Calculate edge
        edge = (win_prob * odds) - 1
        
        # Check if edge is positive
        if edge <= 0:
            return (0.0, 0.0, f"No edge (EV: {edge:.2%}) - Skip trade")
        
        # Check minimum edge
        if edge < KellyCriterion.MIN_EDGE:
            return (0.0, 0.0, f"Edge too small ({edge:.2%} < {KellyCriterion.MIN_EDGE:.2%})")
        
        # Kelly formula: f* = (bp - q) / b
        # Where b = odds - 1 (net odds), p = win_prob, q = loss_prob
        b = odds - 1
        kelly = ((b * win_prob) - loss_prob) / b
        
        # Apply safety factor (half-Kelly)
        kelly_safe = kelly * KellyCriterion.KELLY_FRACTION
        
        # Cap at maximum
        kelly_capped = min(kelly_safe, KellyCriterion.MAX_BET_PCT)
        
        # Calculate bet size
        bet_size = current_bankroll * kelly_capped
        
        # Ensure minimum bet
        if bet_size < 1.0:
            return (0.0, 0.0, "Bet size too small (< $1)")
        
        reasoning = (
            f"Win prob: {win_prob:.1%} | "
            f"Odds: {odds:.2f} | "
            f"Edge: {edge:.2%} | "
            f"Kelly: {kelly:.2%} | "
            f"Safe: {kelly_capped:.2%} | "
            f"Bet: ${bet_size:.2f}"
        )
        
        return (bet_size, kelly_capped, reasoning)
    
    @staticmethod
    def calculate_ev(
        win_prob: float,
        win_amount: float,
        loss_prob: float,
        loss_amount: float
    ) -> float:
        """
        Calculate expected value of a trade.
        
        Args:
            win_prob: Probability of win
            win_amount: Profit if win (positive)
            loss_prob: Probability of loss
            loss_amount: Loss if lose (negative)
        
        Returns:
            Expected value
        """
        return (win_prob * win_amount) + (loss_prob * loss_amount)
    
    @staticmethod
    def should_trade(
        entry_price: float,
        estimated_prob: float,
        market_prob: float,
        bankroll: float
    ) -> Tuple[bool, float, str]:
        """
        Determine if we should trade based on Kelly and EV.
        
        Args:
            entry_price: Current price (our entry)
            estimated_prob: Our estimated true probability
            market_prob: Market implied probability (current price)
            bankroll: Current bankroll
        
        Returns:
            (should_trade, bet_size, reasoning)
        """
        # Check for edge
        if estimated_prob <= market_prob:
            return (False, 0.0, "No edge (our prob <= market)")
        
        edge = estimated_prob - market_prob
        
        # Calculate odds based on entry price
        # If entry is 0.45, odds are 1/0.45 = 2.22
        odds = 1 / entry_price if entry_price > 0 else 1
        
        # Calculate Kelly bet
        bet_size, kelly_pct, kelly_reasoning = KellyCriterion.calculate_kelly(
            win_prob=estimated_prob,
            odds=odds,
            current_bankroll=bankroll
        )
        
        if bet_size <= 0:
            return (False, 0.0, kelly_reasoning)
        
        # Calculate EV
        win_amount = (1 - entry_price) * bet_size  # Profit if win
        loss_amount = -entry_price * bet_size  # Loss if lose
        ev = KellyCriterion.calculate_ev(
            win_prob=estimated_prob,
            win_amount=win_amount,
            loss_prob=(1 - estimated_prob),
            loss_amount=loss_amount
        )
        
        if ev <= 0:
            return (False, 0.0, f"Negative EV: ${ev:.2f}")
        
        reasoning = (
            f"✅ TRADE APPROVED | "
            f"Entry: ${entry_price:.3f} | "
            f"Edge: {edge:.1%} | "
            f"EV: ${ev:.2f} | "
            f"{kelly_reasoning}"
        )
        
        return (True, bet_size, reasoning)

def main():
    """Test Kelly calculations."""
    print("="*60)
    print("🧮 KELLY CRITERION TESTS")
    print("="*60 + "\n")
    
    kelly = KellyCriterion()
    bankroll = 100.0
    
    # Test cases
    tests = [
        (0.60, 0.50, "Strong edge"),  # 60% true, 50% market
        (0.55, 0.50, "Small edge"),
        (0.52, 0.50, "Tiny edge"),
        (0.48, 0.50, "No edge (skip)"),
    ]
    
    for true_prob, market_price, desc in tests:
        print(f"\n📊 Test: {desc}")
        print(f"   True prob: {true_prob:.0%} | Market price: ${market_price:.2f}")
        
        should_trade, bet, reason = kelly.should_trade(
            entry_price=market_price,
            estimated_prob=true_prob,
            market_prob=market_price,
            bankroll=bankroll
        )
        
        print(f"   Result: {'✅ TRADE' if should_trade else '❌ SKIP'}")
        if should_trade:
            print(f"   Bet size: ${bet:.2f}")
        print(f"   Reason: {reason}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()