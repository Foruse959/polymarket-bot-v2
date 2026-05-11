# V1 PROPER ANALYSIS & FIXES

## Tier System (Already Implemented)

| Tier | Balance | Max Bet | Positions | Min Conf |
|------|---------|---------|-----------|----------|
| 🛡️ SURVIVAL | $0-15 | 2% | 5 | 0.60 |
| 🌱 GROWTH | $15-50 | 3% | 10 | 0.45 |
| 🔥 AGGRESSIVE | $50-100 | 5% | 15 | 0.35 |
| 🚀 FULL SEND | $100+ | 7% | 20 | 0.30 |

## Strategy Performance (from actual trades)

| Strategy | Win Rate | P&L | Status |
|----------|----------|-----|--------|
| time_decay | 67% | +$1.77 | ✅ KEEP |
| cross_tf_arb | 50% | +$0.43 | ⚠️ FIX SELL |
| book_imbalance | 0% | -$2.20 | ❌ DISABLE |
| oracle_arb | N/A | N/A | ❌ BROKEN |

## Issues & Fixes

### 1. time_decay (WORKING)
**Keep as-is. Best performer.**

### 2. cross_tf_arb (MIXED)
**Issue**: Sell orders fail → position settles at loss
**Fix**: 
- Use GTC for sells instead of FOK
- Set aggressive sell price (cross spread)
- Add retry logic

### 3. book_imbalance (FAILING)
**Issue**: Losing 100% of trades
**Fix**: Disable in SEED mode, or fix signal calculation

### 4. oracle_arb (BROKEN)
**Issue**: 100% wrong signals
**Fix**: 
- Check Binance API connectivity
- Verify signal calculation
- Increase MIN_EDGE threshold

## What to Test

1. Run in PAPER mode with $10 balance
2. Track each strategy's performance
3. Disable book_imbalance
4. Fix cross_tf_arb sell logic
5. Debug oracle_arb signals

## V2 Migration (April 28)
- Research CLOB v2 changes
- Test with new API
- Apply fixes from V1 testing
