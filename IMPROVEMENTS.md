# V1 Improvements - Analysis & Fixes

## Issues Identified from Logs

### 1. Balance Too Low ($2-3)
- Problem: Can't pay for gas ($5+ per tx)
- Fix: Need $50+ minimum to trade live, or use gasless relay

### 2. Stop Loss Too Tight
- Problem: -16% stop kills positions in 15 seconds
- Fix: Tiered stop-loss (entry price based)

### 3. Sell Fill Rate Only 20%
- Problem: FOK sell at exact price rarely fills
- Fix: Cross-spread pricing (sell 1-2¢ below bid)

### 4. Oracle Arb Broken
- Problem: 100% wrong signals
- Fix: Verify with Binance volume, not just price

### 5. Too Many Strategies (23)
- Problem: No clear edge
- Fix: Focus on top 5 proven strategies

## Top 5 Strategies to Keep

| Strategy | Edge | Why |
|----------|------|-----|
| Time Decay | High | Near expiry = discount |
| Cross-Timeframe Arb | Highest | Guaranteed profit |
| YES+NO Arb | Highest | Risk-free arb |
| Binance Momentum | High | Real data edge |
| Flash Crash | Medium | Buy panic dips |

## Fixes to Implement

1. **Position Sizing**: More conservative for small balance
2. **Stop Loss**: Dynamic based on entry price tier
3. **Sell Logic**: Aggressive pricing
4. **Strategy Filter**: Only top 5 enabled by default
5. **Paper Trading**: Better slippage model
