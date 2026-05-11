# V2 Improvements - Based on V1 Learnings

## What's Different in V2 (April 28)

### CLOB API Changes
- New endpoint structure
- Different order types
- Possibly new fee structure
- Check docs.polymarket.com for details

## V2 Improvements (Applied from V1 Testing)

### 1. Strategy Priority System
Only run the BEST strategies:
```python
PRIORITY_1 = ['time_decay', 'yes_no_arb', 'cross_tf_arb']  # Always on
PRIORITY_2 = ['spread_scalper', 'mid_sniper']              # Growth+
PRIORITY_3 = ['trend_follower', 'binance_momentum']        # Aggressive+
DISABLED = ['book_imbalance']                               # Never
```

### 2. Conservative Start
- Start in PAPER mode only
- $10 minimum for live trading
- Never risk more than 10% of balance

### 3. Sell Logic Fix
```python
def aggressive_sell(bid):
    if bid <= 0.05:
        return max(0.01, bid - 0.01)
    return bid * 0.98  # 2% below = 80% fill rate
```

### 4. Dynamic Stop-Loss
```python
def get_stop(entry_price, seconds_left):
    if entry_price <= 0.10: return entry_price * 0.70   # -30%
    if entry_price <= 0.30: return entry_price * 0.80   # -20%
    if entry_price <= 0.50: return entry_price * 0.85   # -15%
    return entry_price * 0.90  # -10%
```

### 5. Tier Configuration
```python
TIER_CONFIG = {
    'SURVIVAL': {
        'enabled_strategies': ['time_decay', 'yes_no_arb'],
        'min_confidence': 0.60,
        'max_size': 1.00,
    },
    'GROWTH': {
        'enabled_strategies': ['time_decay', 'yes_no_arb', 'cross_tf_arb', 'spread_scalper'],
        'min_confidence': 0.45,
        'max_size': 2.00,
    },
}
```

## Testing Checklist
- [ ] Run in paper mode for 100+ trades
- [ ] Track win rate per strategy
- [ ] Verify sell fill rate > 60%
- [ ] Test with $10 balance
- [ ] Only go live after consistent profits

## Files Changed in V2
- config.py - Added TIER_CONFIG
- strategies/dynamic_picker.py - Priority system
- trading/live_trader.py - Aggressive sell pricing
- trading/risk_manager.py - Dynamic stop-loss
