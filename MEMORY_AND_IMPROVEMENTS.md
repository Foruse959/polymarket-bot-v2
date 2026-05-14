# Polymarket Bot v2.2 Beast Mode — Complete Memory & Improvement Plan

> **Purpose:** Give this file to any AI assistant to instantly understand the full project state, what's been built, what's been fixed, what still needs fixing, and how everything connects. No guessing, no re-reading code.

---

## Repository

- **Repo:** `github.com/Foruse959/polymarket-bot-v2`
- **Active branch:** `oracle-lead-plus-fixes` (PR #12)
- **Commits:** `465dea1` → `72c4568` → `129fde2` → `7e48fd7`
- **Deploy:** Railway (live trading)
- **Language:** Python 3.11

---

## Architecture

```
polymarket-bot-v2/
├── dashboard.py              # Main entry point: bot loop + web dashboard on :8080
├── config.py                 # All settings, 5-tier system, coin/tf/tier toggle, persists to coin_settings.json
├── coin_settings.json        # Runtime preferences (coins, timeframes) saved by Telegram commands
├── data/
│   ├── clob_client.py        # CLOB V2 API: auth, buy/sell orders, order status, exact-share sells, FOK
│   ├── gamma_client.py       # Market discovery from Gamma API (finds active 5/15/30min markets)
│   ├── market_cache.py       # Parallel orderbook caching (2s TTL, 8-worker ThreadPoolExecutor)
│   ├── oracle_ws.py          # Binance 1s kline WebSocket for oracle-lead front-running
│   ├── price_feed.py         # Binance REST price feeds
│   └── indicators.py         # RSI, MACD, Bollinger Bands, EMA calculations
├── strategies/
│   ├── base_strategy.py      # TradeSignal dataclass + BaseStrategy ABC
│   ├── btc_volume_sniper.py  # 86.9% WR on low-volume BTC (backtest proven)
│   ├── momentum_cascade.py   # 74.4% WR momentum continuation
│   ├── oracle_lead.py        # 69% WR Binance→Polymarket lag exploit (BTC ONLY)
│   ├── indicator_fusion.py   # RSI+MACD+BB+EMA ensemble
│   ├── microstructure_maker.py
│   ├── momentum_breakout.py
│   ├── volume_imbalance.py
│   ├── mean_reversion.py
│   ├── maker_edge.py
│   └── longshot_bias.py
├── trading/
│   ├── v2_risk_manager.py    # 5-tier balance system, manual tier override, drawdown alert
│   ├── autonomous_executor.py # Entry/exit: pending tracking, exit cascade, TF-aware TP/SL
│   ├── signal_ranker.py      # Ensemble voting with weighted strategies
│   └── auto_redeem.py        # On-chain CTF redemption via Gnosis Safe / EOA / relayer
├── bot/
│   └── telegram_ui.py        # /coins /timeframe /tier /status /positions /recent /pause /resume
├── backtest/
│   ├── real_backtest.py
│   └── backtest_oracle_lead.py
└── tests/
    ├── simulate_10_trades.py
    ├── test_liquidity_speed.py
    └── test_order_sizing.py
```

---

## How The Bot Works (Flow)

1. **Startup:** `dashboard.py` starts web server, connects CLOB V2, reads on-chain balance, starts Telegram bot, starts Binance oracle WS
2. **Every 2 seconds (scan loop):**
   - Auto-redeem check (2-min cooldown internally)
   - Poll pending orders (promote fills, cancel stale)
   - Monitor open positions (TP/SL check, place exit orders if triggered)
   - Discover markets via Gamma API
   - If `can_trade=True`: generate signals → rank → execute top signals
   - If `can_trade=False` (drawdown/halt): still monitors + sells, just no NEW entries
3. **Entry:** Kelly-sized, tier-validated, liquidity-checked, FOK or GTC depending on conviction
4. **Exit:** 4-tier cascade (FOK → FOK-1tick → FAK → GTC), uses exact owned shares (never rounds up)
5. **Redemption:** Auto-redeemer checks CTF contract every 2min for resolved positions, redeems to pUSD

---

## 5-Tier Balance System

| Tier | Balance Range | Min Conf | Min Strategies | Max Positions | Bet Size |
|------|--------------|----------|----------------|---------------|----------|
| SURVIVAL | $0-5 | 65% | 2+ agree | 2 | 15-25% (max $1.50) |
| SEED | $5-15 | 60% | 2+ agree | 4 | 10-18% |
| COMFORT | $15-50 | 55% | 1+ agree | 6 | 4-8% |
| AGGRESSIVE | $50-150 | 55% | 1+ agree | 10 | 5-10% |
| FULL SEND | $150+ | 50% | 1+ agree | 20 | 6-12% |

**Manual override:** User can lock any tier via `/tier` regardless of balance. Reserve is capped at balance/2 so low-balance users can still trade in high tiers.

---

## TP/SL System (Linear Score-Based × Timeframe)

**Base formula (5min):**
- Score 1 (SINGLE): TP=30%, SL=16%
- Score 2 (MEDIUM): TP=45%, SL=21%
- Score 3 (HIGH): TP=60%, SL=26%
- Score 4: TP=75%, SL=31%
- Score 5+ (MAXIMUM): Hold to resolution

**Timeframe multiplier:**
- 5min → 1.00x (baseline)
- 15min → 1.60x (e.g. SL=26% instead of 16%)
- 30min → 2.25x (e.g. SL=36% instead of 16%)

**Confidence boost:** 80%+ confidence → SL widens 30% more. 70%+ → 15% more.

---

## Telegram Commands

| Command | What it does |
|---------|-------------|
| `/status` | Balance, PnL, tier, win rate, drawdown |
| `/coins` | Toggle BTC/ETH/SOL/XRP with inline buttons |
| `/timeframe` | Toggle 5/15/30 min markets |
| `/tier` | Lock SURVIVAL/SEED/COMFORT/AGGRESSIVE/FULL SEND or AUTO |
| `/positions` | Show open positions with PnL |
| `/recent` | Last 10 closed trades |
| `/pause` / `/resume` | Pause/resume new entries (monitoring continues) |

All changes apply mid-trading on the next scan cycle. No restart needed.

---

## Fixes Completed (History)

### Commit `465dea1` — Initial oracle-lead branch
- Removed hard-stop on balance check failure
- Use proxy wallet for pUSD reads
- Never block scanning

### Commit `72c4568` — Real order lifecycle
1. **Limit order tracking:** PendingOrder class, poll status, promote only on MATCHED
2. **Real exit orders:** Actual FOK SELL on CLOB when TP/SL fires
3. **Auto-redeem wired:** AutoRedeemer in dashboard loop (2-min cooldown)
4. **Balance refresh:** Callback fires after every fill/exit/redemption
5. **FOK for high conviction:** oracle_lead + HIGH/MAX taker signals use FOK

### Commit `129fde2` — Sizing fix + tier override
6. **Sub-MIN sizing bug:** $6 balance was computing $0.93 size (below $1 minimum). Fixed by applying caps first, MIN floor last.
7. **Manual tier override:** `/tier` command, inline keyboard, persists through balance changes

### Commit `7e48fd7` — Exit fixes + timeframe SL + /timeframe
8. **Share-count mismatch on SELL:** Bot asked CLOB for 5.10sh when it owned 5.00sh. New `place_sell_shares()` uses exact owned shares truncated DOWN.
9. **Exit cascade (4 tiers):** FOK → FOK-1tick → FAK → GTC. Re-reads book each tier. Failed exits re-queue position.
10. **Drawdown alert not halt:** Drawdown no longer blocks `monitor_positions()`. Alert-only, positions always monitored.
11. **Timeframe-aware TP/SL:** 5min=1.0x, 15min=1.6x, 30min=2.25x multiplier
12. **`/timeframe` command:** Toggle 5/15/30 via Telegram
13. **cancel_order fix:** SDK uses `cancel_order()` not `cancel()`
14. **Two-sided liquidity check:** Entry (3x) + exit (2x) depth required

---

## CRITICAL: What NOT To Change

These are proven correct. Changing them will break things:

- **Exit shares ALWAYS truncated DOWN** (never computed from pUSD)
- **Position monitoring runs BEFORE `can_trade` gate** in scan loop
- **Drawdown is alert-only** (never halts monitoring/selling)
- **SDK method is `cancel_order()`** not `cancel()`
- **Maker orders (0% fee) for entry, FOK for exits**
- **Reserve capped at balance/2** for manual tier overrides
- **`compute_exits_from_score()` takes timeframe arg** — don't remove it
- **oracle_lead is BTC-only** — ETH/SOL backtest at 41-44% WR (loses money)
- **All Telegram config changes apply on next scan** (no restart)
- **`_place_sell_exact_shares_v2()`** is the ONLY path for exits (not `_place_order_v2`)

---

## Known Issues & Improvement Plan

### P0 — CRITICAL (Must Fix Next)

#### 1. MARKET RESOLUTION TIMING (HIGHEST PRIORITY)

**The bug:** Bot has NO awareness of market closing time. It doesn't track `seconds_remaining` for open positions. It doesn't know when a market has already resolved.

**Real-world incident (May 14, 2026):**
```
15min market, position was UP +90% profit
Bot did NOT sell during the market (no TP trigger or it missed the window)
In the LAST MINUTE: market reversed (volatile final seconds, oracle update flipped direction)
Bot THEN tried to sell — but too late, book was empty (no liquidity at market close)
SELL FOK failed — "not enough balance" / no bids
Market resolved in the OPPOSITE direction → position went from +90% to LOSS
Even AFTER market closed/resolved, bot STILL attempted to sell (doesn't know market ended)
```

**What went wrong (3 separate failures):**
1. Bot didn't sell when it was +90% profit before the volatile last minute
2. Bot tried to sell in the last seconds when liquidity was gone
3. Bot didn't know market had already resolved and kept trying to sell a dead position

**The correct behavior (smart resolution-aware exit):**

The bot must track `seconds_remaining` per position and make a decision:

**CASE A — Position is IN PROFIT and market is about to close (< 60s):**
- **If you EXPECT it will resolve in your favor** (i.e., price hasn't reversed, trend is stable): **DO NOT SELL. Wait for resolution.** Winning shares auto-resolve to $1.00 with ZERO fees (no taker fee, no spread crossing). This is ALWAYS better than selling at 0.85-0.90 and paying 3% fees. AutoRedeemer picks up the resolved tokens.
- **If you SENSE reversal risk** (price is moving against you, or the last few seconds show momentum change): **Sell at 60-30 seconds remaining**, while liquidity still exists and you can still cross the spread. Don't wait until < 10s when the book is empty.

**CASE B — Position is in LOSS and market is about to close (< 60s):**
- Try to sell at 60s mark while there's still some bid liquidity
- If can't sell by 30s remaining, STOP trying — accept the loss, let market resolve
- Don't sell into an empty book at the last second (you'll get worst price or fail entirely)

**CASE C — Market has already resolved:**
- STOP trying to sell immediately. Mark position as `awaiting_redemption`
- AutoRedeemer will handle it on next 2-min check cycle
- Never place a SELL order on a resolved/closed market

**Implementation approach:**
- `gamma.discover_markets()` already returns `seconds_remaining` per market
- Pass this to executor's `monitor_positions()` so each position knows how close market end is
- Add a `should_hold_to_resolution()` check that overrides TP/SL in the final 60s
- Track market close timestamp per position (from gamma market data at entry time)
- After close time passes: mark position as `resolved`, stop all sell attempts

**Why this is the #1 priority:** User had a +90% winning trade that turned into a loss because:
- The bot didn't book profits when it should have (before the volatile last minute)
- Then tried to sell when it was too late (empty book)
- Then kept trying after market was already dead

This single fix would have saved that entire trade AND future trades. The resolution-hold approach (Case A) also saves 10-15% in fees on every winning trade that resolves naturally.

#### 2. No Reconciliation on Restart
Bot forgets positions after crash. Fix: persist executor state to JSON, or rebuild from CLOB trades on startup.

#### 3. Partial Fills Not Handled
GTC fills 4/10 shares, times out, we treat 4 as full position sized for 10. Should track actual filled size.

#### 4. Zombie Positions
If exit GTC is placed but market closes before fill, position disappears from state but tokens remain on-chain. Need "zombie" tracking for auto-redeem to catch.

### P1 — Performance (Win Rate Impact)

#### 5. WebSocket for Order Status
REST polling = 2-8s latency. WS would give sub-100ms fills. Critical for oracle-lead (edge dies in 8s).

#### 6. Correlation-Aware Sizing
BTC 5m + BTC 15m + ETH 5m all UP = 3 correlated bets. Should cap at 50% balance across correlated markets.

#### 7. Strategy Performance Tracking
No per-strategy win rate. Should auto-deweight strategies below 50% WR after 100 trades.

#### 8. Entry Delay for Same-Market Signals
4 strategies on same market = 4 positions on same bet. Wait 2s, re-rank, take best only.

#### 9. "Market About to Resolve" Entry Guard
Skip entry if < 15% of market lifetime remaining. A trade entered 10s before close has 0% edge.

### P2 — Robustness

#### 10. Log Rotation (10MB × 5 files)
#### 11. Rate Limiting (asyncio.Semaphore(3) on execute_signal)
#### 12. Thread Safety (Lock around STATE dict)
#### 13. Auto-Redeemer Gas Check (alert if < 0.01 POL)

### P3 — Winning Improvements (+5-15% Win Rate)

#### 14. Hold-to-Resolution for Winners
When in profit + < 60s remaining: skip sell, let resolve at $1.00. Saves 10-15% per winning trade in fees alone.

#### 15. Dynamic BTC Bias Exploitation
54.5% UP bias = place small "default BTC UP" at 0.50 when no signal. EV: +$0.045 per $1.

#### 16. Rolling Strategy Audit
Every 50 trades: compute Sharpe per strategy. Below 0 → reduce weight to 0.3x until recovery.

#### 17. Oracle Lag Detection
Track Binance→Polymarket lag per hour. Short lag → conservative. Wide lag → aggressive.

#### 18. Post-Trade Signal Audit
Log which strategies fired, actual resolution, correctness. Build accuracy.json for tuning.

---

## Key Design Decisions & Backtest Data

| Decision | Rationale |
|----------|-----------|
| pUSD collateral (V2) | Polymarket switched from USDC to pUSD in April 2026 |
| py-clob-client-v2 SDK | V1 deprecated, V2 has FOK/FAK/GTC order types |
| Maker entry (0% fee) | GTC limit orders pay no fees, only taker pays |
| FOK exit (accepts fee) | Speed matters more than fee savings on exit |
| BTC oracle-lead only | ETH/SOL backtest: 41-44% WR (loses money) |
| Timeframe SL scaling | sqrt(time) volatility — no ML needed |
| 2s scan cadence | Oracle signals die in 8s, 5s was too slow |
| 30s pending timeout | Oracle signals stale after 30s |

**Backtest source:** HuggingFace SII-WANGZJ/Polymarket_data (markets.parquet, 158MB, 323K crypto up/down markets)

**Key stats:**
- BTC inherent UP bias: 54.5% on 5min markets (186K markets)
- BTC momentum: after 5 consecutive UPs → 67.5% next UP probability
- Low volume BTC (<$50 book): 86.9% UP win rate
- ETH/SOL/XRP: near 50/50, only momentum/cascade strategies work

---

## Contract Addresses

| Contract | Address |
|----------|---------|
| pUSD (collateral) | `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` |
| CTF Exchange V2 | `0xE111180000d2663C0091e4f400237545B87B996B` |
| NegRisk CTF Exchange | `0xe2222d279d744050d28e00520010520000310F59` |
| User Proxy Wallet | `0x4f9fbe936a35d556894737235df49cfcd5d5cfc4` |

---

## User Context

- **Balance:** ~$2-6 pUSD (fluctuates with trades)
- **Goal:** Grow from tiny balance using highest-confidence signals
- **Region:** May need CLOB relay for geo-block
- **Platform:** Windows (Python 3.11), deployed on Railway
- **Telegram bot:** Configured for monitoring/control
- **User preference:** Aggressive trading with manual tier control
- **All changes must apply mid-trading** — no restart required
- **User confirmed:** /tier command is safe, doesn't affect bot core

---

## How to Continue Development

1. Read this file first
2. Check the improvement plan (P0 items are most urgent)
3. The market resolution timing (#1 + #14) is the highest-impact single change
4. Don't touch the "What NOT To Change" section without understanding why each item exists
5. All fixes should be testable with mock CLOB (see existing test patterns in the commit messages)
6. Push to `oracle-lead-plus-fixes` branch, PR #12 is already open against `master`
