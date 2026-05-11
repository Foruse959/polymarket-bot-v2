# 5min_trade v2 — Maker Edge

Polymarket trading bot focused on **maker strategies** to exploit the +1.12% excess return identified in academic research.

## What's New in v2

### 1. USDC Currency
- All amounts displayed in **USDC** (not USD)
- Polymarket trades in USDC on Polygon (chain_id=137)
- Updated balance displays: `5.00 USDC` instead of `$5.00`

### 2. Updated py-clob-client (v0.34.6)
- Uses latest API for order placement
- Supports signature_type 0 (EOA), 1 (Magic), 2 (Proxy)
- Auto-derives API credentials from private key
- Funder address support for proxy wallets

### 3. Maker-First Strategy
Based on Jon Becker's research:
- **Makers earn +1.12%** avg excess return vs takers losing -1.12%
- Bot **always places limit orders** (maker) instead of market orders (taker)
- Strategy: Place limit orders on NO side at high prices
- Sell into biased YES taker flow

### 4. Longshot Bias Exploitation
- Low-priced contracts (<20¢) are systematically overpriced
- High-priced contracts (>80¢) are systematically underpriced
- The "Optimism Tax" takers pay becomes the maker's profit

### 5. Category-Aware Spread Management
| Category | Spread Multiplier | Efficiency |
|----------|------------------|------------|
| Finance | 1.0x | Most efficient (0.17pp gap) |
| Politics | 1.25x | Medium |
| Sports | 1.75x | Less efficient (2-4.79pp gap) |
| Entertainment | 2.0x | Least efficient |

## Installation

```bash
# Clone and enter directory
cd 5min_trade_v2

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

## Configuration

### Minimum Required (.env)
```bash
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# For live trading
POLY_PRIVATE_KEY=0x...
POLY_SIGNATURE_TYPE=0
```

### Wallet Types

**EOA Wallet (MetaMask)** - `POLY_SIGNATURE_TYPE=0`
```bash
POLY_PRIVATE_KEY=0x...
POLY_SIGNATURE_TYPE=0
# Funder auto-derived from private key
```

**Proxy Wallet (Browser)** - `POLY_SIGNATURE_TYPE=2`
```bash
POLY_PRIVATE_KEY=0x...
POLY_SIGNATURE_TYPE=2
POLY_PROXY_WALLET=0xYourMakerAddress
```

## Usage

```bash
# Paper trading (default)
python app.py

# Live trading
TRADING_MODE=live python app.py
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome & status |
| `/trade` | Start trading |
| `/stop` | Stop trading |
| `/status` | Position & P&L status |
| `/balance` | Check USDC balance |
| `/positions` | View open positions |
| `/strategy` | View active strategies |
| `/mode` | Show current mode |

## Strategies

### 1. Maker Edge
- Places limit orders on NO side at prices >75¢
- Captures the maker advantage (+1.12% vs taker -1.12%)
- Category-aware: wider spreads for Sports/Entertainment

### 2. Longshot Bias
- Sells YES when price <20¢ (overpriced)
- Buys NO when price >80¢ (underpriced)
- Exploits retail "Optimism Tax"

### 3. Dynamic Picker
- Automatically selects best strategy per market
- Tracks performance and adjusts weights
- Prioritizes maker orders

## Risk Modes

| Mode | Balance | Max Positions | Maker Preference |
|------|---------|---------------|------------------|
| 🌱 Seed | 1-5 USDC | 2 | 100% |
| 🌿 Plant | 5-15 USDC | 3 | 95% |
| 🎯 Concentration | 5-20 USDC | 4 | 90% |
| ⚖️ Medium | 20-100 USDC | 8 | 85% |
| 🔥 Aggressive | 100+ USDC | 12 | 75% |

## File Structure

```
5min_trade_v2/
├── app.py                 # Main entry point
├── config.py              # Configuration (USDC, v0.34.6)
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── README.md             # This file
├── data/
│   ├── gamma_client.py   # Market discovery with categories
│   ├── clob_client.py    # CLOB API (v0.34.6)
│   └── database.py       # SQLite with USDC
├── strategies/
│   ├── base_strategy.py
│   ├── maker_edge.py     # NEW: Maker advantage
│   ├── longshot_bias.py  # NEW: Behavioral arb
│   └── dynamic_picker.py # Strategy selector
├── trading/
│   ├── paper_trader.py   # Simulation
│   ├── live_trader.py    # Real execution
│   └── live_balance_manager.py  # USDC risk mgmt
└── bot/
    └── main.py           # Telegram interface
```

## Key Research Insights

> "Makers consistently earn +1.12% avg excess return vs Takers losing -1.12%"
> — Jon Becker, Polymarket Analysis

> "Low-priced contracts (<20¢) are overpriced; high-priced contracts (>80¢) are underpriced"
> — SII-WANGZJ Data (170M+ records)

## License

MIT
