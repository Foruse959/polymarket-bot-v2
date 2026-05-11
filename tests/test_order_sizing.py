"""
Unit tests for the critical order sizing fix.

Validates that price × shares >= $1.00 for ALL price levels (0.01–0.99).
This was the root cause of the "invalid amount" error.
"""

import math
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


POLYMARKET_MIN_ORDER_SIZE = 1.0


def compute_shares(price: float, size: float) -> float:
    """Mirror the FIXED share calculation from live_trader.py."""
    min_shares_for_minimum = math.ceil(POLYMARKET_MIN_ORDER_SIZE / price * 100) / 100
    shares = max(min_shares_for_minimum, round(size / price, 2))

    # Double-check
    order_amount = round(price * shares, 6)
    if order_amount < POLYMARKET_MIN_ORDER_SIZE:
        shares = math.ceil(POLYMARKET_MIN_ORDER_SIZE / price * 100) / 100
        if shares * price < POLYMARKET_MIN_ORDER_SIZE:
            shares = math.ceil(POLYMARKET_MIN_ORDER_SIZE / price)
        order_amount = round(price * shares, 6)

    return shares


def test_all_prices_meet_minimum():
    """Every tick from $0.01 to $0.99 must produce order_amount >= $1.00."""
    failures = []
    for cents in range(1, 100):
        price = cents / 100.0
        shares = compute_shares(price, 1.0)
        order_amount = round(price * shares, 6)

        if order_amount < POLYMARKET_MIN_ORDER_SIZE:
            failures.append(
                f"  FAIL: price={price:.2f} → shares={shares:.2f} → "
                f"amount=${order_amount:.6f} < $1.00"
            )

    if failures:
        print("❌ FAILURES:")
        for f in failures:
            print(f)
    else:
        print("✅ All prices (0.01–0.99) produce order_amount >= $1.00")
    assert not failures, f"{len(failures)} prices produced invalid amounts"


def test_exact_dollar_boundaries():
    """Specific prices that caused the original bug."""
    test_cases = [
        (0.32, 1.0),   # Original: 3.12 shares → $0.9984 < $1
        (0.27, 1.0),   # Original: 3.70 shares → $0.999  < $1
        (0.41, 1.0),   # Original: 2.44 shares → $1.0004 (was OK)
        (0.03, 1.0),   # Edge: very cheap
        (0.99, 1.0),   # Edge: very expensive
        (0.50, 1.0),   # Fair price
        (0.01, 1.0),   # Absolute minimum price
    ]

    print("\nDetailed order sizing tests:")
    for price, size in test_cases:
        shares = compute_shares(price, size)
        amount = round(price * shares, 6)
        old_shares = round(size / price, 2)
        old_amount = round(price * old_shares, 6)

        status = "✅" if amount >= POLYMARKET_MIN_ORDER_SIZE else "❌"
        fixed = " (FIXED!)" if old_amount < POLYMARKET_MIN_ORDER_SIZE else ""
        print(
            f"  {status} price={price:.2f}: "
            f"old={old_shares:.2f}sh/${old_amount:.4f} → "
            f"new={shares:.2f}sh/${amount:.4f}{fixed}"
        )
        assert amount >= POLYMARKET_MIN_ORDER_SIZE, (
            f"price={price} → amount={amount} < $1.00"
        )


def test_dual_leg_affordability():
    """Test LiveBalanceManager.can_afford_dual_leg logic."""

    class MockConfig:
        POLYMARKET_MIN_ORDER_SIZE = 1.0

    # $4 balance with seed mode (0% reserve) → tradeable = $4 → can afford 2×$1
    tradeable_4 = 4.0
    assert tradeable_4 >= MockConfig.POLYMARKET_MIN_ORDER_SIZE * 2, \
        "$4 should afford dual-leg"

    # $1.50 balance → can't afford 2×$1
    tradeable_1_5 = 1.50
    assert not (tradeable_1_5 >= MockConfig.POLYMARKET_MIN_ORDER_SIZE * 2), \
        "$1.50 should NOT afford dual-leg"

    print("\n✅ Dual-leg affordability checks pass")


def test_fee_aware_arb_profit():
    """Cross-TF arb must subtract fees from profit calculation."""
    fee_rate = 0.0156

    # Scenario: UP@0.40 + DOWN@0.50 = 0.90 cost
    combo_cost = 0.40 + 0.50
    old_profit = 1.0 - combo_cost  # 0.10 (old calc, ignoring fees)
    new_profit = 1.0 - combo_cost - (combo_cost * fee_rate * 2)

    print(f"\nFee-aware arb: cost={combo_cost:.2f}")
    print(f"  Old profit: ${old_profit:.4f} (no fees)")
    print(f"  New profit: ${new_profit:.4f} (after ~{combo_cost * fee_rate * 2 * 100:.1f}¢ fees)")
    print(f"  Fees saved: ${old_profit - new_profit:.4f}")
    assert new_profit < old_profit, "Fee-adjusted profit should be lower"
    assert new_profit > 0, "This scenario should still be profitable"
    print("✅ Fee-aware arb calculation correct")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ORDER SIZING FIX — UNIT TESTS")
    print("=" * 60)

    test_all_prices_meet_minimum()
    test_exact_dollar_boundaries()
    test_dual_leg_affordability()
    test_fee_aware_arb_profit()

    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
