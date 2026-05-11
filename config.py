"""
5min_trade v2 — Configuration

Updated for:
- pUSD currency (NOT USDC.e) - Polymarket switched to pUSD in 2025
- pUSD Contract: 0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB (Polygon)
- py-clob-client v0.34.6 API
- Maker-focused strategies (limit orders, not market orders)
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration for the 5min_trade v2 bot."""

    # ═══════════════════════════════════════════════════════════════════
    # VERSION
    # ═══════════════════════════════════════════════════════════════════
    VERSION = "2.0.0"
    VERSION_NAME = "Maker Edge"

    # ═══════════════════════════════════════════════════════════════════
    # TELEGRAM
    # ═══════════════════════════════════════════════════════════════════
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    # ═══════════════════════════════════════════════════════════════════
    # POLYMARKET WALLET
    # ═══════════════════════════════════════════════════════════════════
    POLY_PRIVATE_KEY = os.getenv('POLY_PRIVATE_KEY', '')
    POLY_SAFE_ADDRESS = os.getenv('POLY_SAFE_ADDRESS', '')
    POLY_FUNDER_ADDRESS = os.getenv('POLY_FUNDER_ADDRESS', '')  # Auto-derived if blank
    POLY_PROXY_WALLET = os.getenv('POLY_PROXY_WALLET', '')  # Proxy/maker wallet (sig_type=2)
    POLY_API_KEY = os.getenv('POLY_API_KEY', '')      # Auto-derived from private key
    POLY_API_SECRET = os.getenv('POLY_API_SECRET', '')  # Auto-derived from private key
    POLY_PASSPHRASE = os.getenv('POLY_PASSPHRASE', '')  # Auto-derived from private key
    POLY_SIGNATURE_TYPE = int(os.getenv('POLY_SIGNATURE_TYPE', '0'))  # 0=EOA, 1=Magic, 2=Proxy
    POLY_CHAIN_ID = int(os.getenv('POLY_CHAIN_ID', '137'))  # Polygon mainnet

    # ═══════════════════════════════════════════════════════════════════
    # BUILDER RELAYER (gasless auto-redeem of resolved positions)
    # ═══════════════════════════════════════════════════════════════════
    POLY_BUILDER_API_KEY = os.getenv('POLY_BUILDER_API_KEY', '')
    POLY_BUILDER_SECRET = os.getenv('POLY_BUILDER_SECRET', '')
    POLY_BUILDER_PASSPHRASE = os.getenv('POLY_BUILDER_PASSPHRASE', '')
    POLY_BUILDER_CODE = os.getenv('POLY_BUILDER_CODE', '')  # Builder code for V2 order attribution
    AUTO_REDEEM_INTERVAL = int(os.getenv('AUTO_REDEEM_INTERVAL', '120'))  # Check every N seconds
    POLYGON_RPC_URL = os.getenv('POLYGON_RPC_URL', '')  # Custom RPC (optional, has fallbacks)

    # ═══════════════════════════════════════════════════════════════════
    # API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    GAMMA_API_URL = 'https://gamma-api.polymarket.com'
    CLOB_API_URL = 'https://clob.polymarket.com'
    BINANCE_WS_URL = 'wss://stream.binance.com:9443/ws'
    POLYMARKET_WS_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
    POLYMARKET_LIVE_WS_URL = 'wss://ws-live-data.polymarket.com'

    # ═══════════════════════════════════════════════════════════════════
    # PROXY / RELAY (bypass Polymarket geoblock)
    # ═══════════════════════════════════════════════════════════════════
    PROXY_URL = os.getenv('PROXY_URL', '')
    CLOB_RELAY_URL = os.getenv('CLOB_RELAY_URL', '')
    CLOB_RELAY_AUTH_TOKEN = os.getenv('CLOB_RELAY_AUTH_TOKEN', '')  # Optional auth for relay

    # ═══════════════════════════════════════════════════════════════════
    # TRADING MODE
    # ═══════════════════════════════════════════════════════════════════
    TRADING_MODE = os.getenv('TRADING_MODE', 'paper')  # 'paper' or 'live'
    LIVE_RISK_MODE = os.getenv('LIVE_RISK_MODE', 'concentration')  # concentration/medium/aggressive
    STARTING_BALANCE_USDC = float(os.getenv('STARTING_BALANCE_USDC', '100.0'))  # USDC, not USD
    POLYMARKET_MIN_ORDER_SIZE_USDC = 1.0  # $1 minimum (Polymarket FOK minimum)
    
    # Maker vs Taker settings
    DEFAULT_ORDER_TYPE = os.getenv('DEFAULT_ORDER_TYPE', 'maker')  # 'maker' (limit) or 'taker' (market)
    MAKER_PREFERRED = os.getenv('MAKER_PREFERRED', 'true').lower() == 'true'  # Always prefer maker
    
    # Category-specific spread multipliers (based on Becker research)
    # Finance is most efficient (tighter spreads), Sports/Entertainment least efficient
    CATEGORY_SPREAD_MULTIPLIERS = {
        'finance': 1.0,      # Most efficient - tight spreads
        'politics': 1.25,    # Medium efficiency
        'sports': 1.75,      # Less efficient - wider spreads
        'entertainment': 2.0, # Least efficient - widest spreads
        'crypto': 1.5,       # Medium-high volatility
        'other': 1.5,        # Default
    }
    
    MARKET_FOCUS_IDLE_SCANS = int(os.getenv('MARKET_FOCUS_IDLE_SCANS', '3'))
    MIN_EDGE_AFTER_FEES_USDC = float(os.getenv('MIN_EDGE_AFTER_FEES_USDC', '0.03'))  # 0.03 USDC

    # ═══════════════════════════════════════════════════════════════════
    # COINS
    # ═══════════════════════════════════════════════════════════════════
    ENABLED_COINS = [c.strip().upper() for c in os.getenv('ENABLED_COINS', 'BTC,ETH').split(',')]

    # Binance symbol mapping
    BINANCE_SYMBOLS = {
        'BTC': 'btcusdt',
        'ETH': 'ethusdt',
        'SOL': 'solusdt',
        'XRP': 'xrpusdt',
    }

    # Polymarket slug prefixes per coin
    COIN_PM = {
        'BTC': 'btc', 'ETH': 'eth', 'SOL': 'sol', 'XRP': 'xrp',
    }

    # Polymarket series slugs per timeframe
    SERIES_SLUGS = {
        5: '{coin}-up-or-down-5m',
        15: '{coin}-up-or-down-15m',
        30: '{coin}-up-or-down-30m',
    }

    # ═══════════════════════════════════════════════════════════════════
    # TIMEFRAME SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    ENABLED_TIMEFRAMES = [int(t) for t in os.getenv('ENABLED_TIMEFRAMES', '5,15').split(',')]

    TIMEFRAME_PARAMS = {
        5: {
            'name': '5 min',
            'scan_interval': 1,
            'position_size_pct': 3.0,
            'max_positions': 20,
            'take_profit_pct': 200.0,
            'stop_loss_pct': 16.0,
            'min_confidence': 0.40,
            'preferred_strategies': ['maker_edge', 'longshot_bias', 'time_decay'],
        },
        15: {
            'name': '15 min',
            'scan_interval': 3,
            'position_size_pct': 3.0,
            'max_positions': 20,
            'take_profit_pct': 200.0,
            'stop_loss_pct': 16.0,
            'min_confidence': 0.40,
            'preferred_strategies': ['maker_edge', 'longshot_bias', 'cross_tf_arb'],
        },
        30: {
            'name': '30 min',
            'scan_interval': 5,
            'position_size_pct': 3.0,
            'max_positions': 20,
            'take_profit_pct': 200.0,
            'stop_loss_pct': 16.0,
            'min_confidence': 0.40,
            'preferred_strategies': ['maker_edge', 'longshot_bias', 'oracle_arb'],
        },
    }

    # ═══════════════════════════════════════════════════════════════════
    # MAKER STRATEGY SETTINGS (Based on Jon Becker's research)
    # ═══════════════════════════════════════════════════════════════════
    # Makers earn +1.12% avg excess return vs Takers losing -1.12%
    # Key insight: Place limit orders on NO side at high prices
    # Sell into biased YES taker flow
    
    MAKER_MIN_SPREAD_BPS = float(os.getenv('MAKER_MIN_SPREAD_BPS', '50'))  # 0.5% minimum spread
    MAKER_TARGET_SPREAD_BPS = float(os.getenv('MAKER_TARGET_SPREAD_BPS', '100'))  # 1% target
    MAKER_MAX_SPREAD_BPS = float(os.getenv('MAKER_MAX_SPREAD_BPS', '300'))  # 3% max spread
    
    # Longshot bias parameters
    LONGSHOT_THRESHOLD_LOW = float(os.getenv('LONGSHOT_THRESHOLD_LOW', '0.20'))  # <20¢ = overpriced
    LONGSHOT_THRESHOLD_HIGH = float(os.getenv('LONGSHOT_THRESHOLD_HIGH', '0.80'))  # >80¢ = underpriced
    LONGSHOT_MAX_POSITION_USDC = float(os.getenv('LONGSHOT_MAX_POSITION_USDC', '50.0'))

    # ═══════════════════════════════════════════════════════════════════
    # FEE STRUCTURE (in USDC)
    # ═══════════════════════════════════════════════════════════════════
    # Taker fee formula: fee = C × 0.25 × [p×(1−p)]²
    # Effective rate = 0.25 × p × (1−p)²
    # Peak ~3.7% at p≈0.33, 3.125% at p=0.50, 0.94% at p=0.78
    # Maker fee: 0% (earn spread instead)
    TAKER_FEE_RATE = float(os.getenv('TAKER_FEE_RATE', '0.03125'))  # 3.125% at p=0.50
    MAKER_FEE_RATE = 0.0  # Makers pay no fees, earn spread

    # ═══════════════════════════════════════════════════════════════════
    # RISK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════
    MAX_DAILY_LOSS_PCT = float(os.getenv('MAX_DAILY_LOSS_PCT', '50.0'))
    MAX_TOTAL_POSITIONS = int(os.getenv('MAX_TOTAL_POSITIONS', '20'))

    # ═══════════════════════════════════════════════════════════════════
    # DATABASE
    # ═══════════════════════════════════════════════════════════════════
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/trades.db')

    # ═══════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════
    @classmethod
    def is_paper(cls) -> bool:
        return cls.TRADING_MODE.lower() == 'paper'

    @classmethod
    def get_clob_url(cls) -> str:
        """Get effective CLOB API URL — relay if configured, else direct."""
        if cls.CLOB_RELAY_URL:
            return cls.CLOB_RELAY_URL.rstrip('/')
        return cls.CLOB_API_URL

    @classmethod
    def is_relay_enabled(cls) -> bool:
        """Check if CLOB relay is configured (bypasses geo-blocking)."""
        return bool(cls.CLOB_RELAY_URL)

    @classmethod
    def is_live_ready(cls) -> bool:
        """Check if minimum live trading config is set (just private key)."""
        pk = cls.POLY_PRIVATE_KEY.strip() if cls.POLY_PRIVATE_KEY else ''
        return bool(pk)

    @classmethod
    def derive_wallet_address(cls) -> str:
        """Derive wallet address from private key. Returns '' on failure."""
        pk = cls.POLY_PRIVATE_KEY.strip() if cls.POLY_PRIVATE_KEY else ''
        if not pk:
            return ''
        try:
            from eth_account import Account
            if not pk.startswith('0x'):
                pk = '0x' + pk
            wallet = Account.from_key(pk)
            return wallet.address
        except Exception:
            return ''

    @classmethod
    def get_funder_address(cls) -> str:
        """Get funder address — uses explicit config or auto-derives from key.
        
        For proxy wallets (sig_type=2): returns POLY_PROXY_WALLET (the maker address).
        For EOA wallets (sig_type=0): auto-derives from private key.
        """
        if cls.POLY_FUNDER_ADDRESS and cls.POLY_FUNDER_ADDRESS.strip():
            return cls.POLY_FUNDER_ADDRESS.strip()
        # Proxy wallet (sig_type=2): use POLY_PROXY_WALLET as funder
        if cls.POLY_SIGNATURE_TYPE == 2:
            if cls.POLY_PROXY_WALLET and cls.POLY_PROXY_WALLET.strip():
                return cls.POLY_PROXY_WALLET.strip()
            return ''  # Must be set explicitly for proxy wallets
        # Auto-derive for EOA wallets (signature_type=0)
        if cls.POLY_SIGNATURE_TYPE == 0:
            return cls.derive_wallet_address()
        return ''

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.TELEGRAM_BOT_TOKEN)

    @classmethod
    def get_timeframe_params(cls, minutes: int) -> dict:
        return cls.TIMEFRAME_PARAMS.get(minutes, cls.TIMEFRAME_PARAMS[15])

    @classmethod
    def format_usdc(cls, amount: float) -> str:
        """Format amount as USDC string (e.g., '5.00 USDC')."""
        return f"{amount:.2f} USDC"

    @classmethod
    def get_category_spread_multiplier(cls, category: str) -> float:
        """Get spread multiplier for a market category."""
        return cls.CATEGORY_SPREAD_MULTIPLIERS.get(category.lower(), 1.5)

    @classmethod
    def print_status(cls):
        mode = '📋 PAPER' if cls.is_paper() else '🔴 LIVE'
        pk_ok = bool(cls.POLY_PRIVATE_KEY and cls.POLY_PRIVATE_KEY.strip())
        wallet = cls.derive_wallet_address() if pk_ok else ''
        funder = cls.get_funder_address()
        api_auto = not bool(cls.POLY_API_KEY and cls.POLY_API_KEY.strip())
        order_type = 'MAKER (limit orders)' if cls.MAKER_PREFERRED else 'TAKER (market orders)'

        print(f"\n{'='*60}", flush=True)
        print(f"⚡ 5MIN_TRADE v{cls.VERSION} — {cls.VERSION_NAME}", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Mode: {mode}", flush=True)
        print(f"Order Type: {order_type}", flush=True)
        print(f"Coins: {', '.join(cls.ENABLED_COINS)}", flush=True)
        print(f"Timeframes: {cls.ENABLED_TIMEFRAMES}", flush=True)
        print(f"Telegram: {'✅' if cls.TELEGRAM_BOT_TOKEN else '❌'}", flush=True)
        print(f"{'─'*60}", flush=True)
        print(f"🔐 LIVE TRADING CONFIG:", flush=True)
        print(f"  Private Key: {'✅ set' if pk_ok else '❌ NOT SET — set POLY_PRIVATE_KEY'}", flush=True)
        if pk_ok:
            print(f"  Wallet: {wallet[:8]}...{wallet[-4:]}" if wallet else "  Wallet: ❌ could not derive", flush=True)
            print(f"  Funder: {funder[:8]}...{funder[-4:]}" if funder else "  Funder: ⚠️ not set (required for proxy wallets)", flush=True)
            if cls.POLY_SIGNATURE_TYPE == 2:
                proxy = cls.POLY_PROXY_WALLET.strip() if cls.POLY_PROXY_WALLET else ''
                print(f"  Proxy Wallet: {proxy[:8]}...{proxy[-4:]}" if proxy else "  Proxy Wallet: ❌ NOT SET — set POLY_PROXY_WALLET!", flush=True)
            print(f"  API Creds: {'🔑 auto-derive from key' if api_auto else '✅ manually set'}", flush=True)
            print(f"  Sig Type: {cls.POLY_SIGNATURE_TYPE} ({'EOA/MetaMask' if cls.POLY_SIGNATURE_TYPE == 0 else 'Email/Magic' if cls.POLY_SIGNATURE_TYPE == 1 else 'Proxy'})", flush=True)
        print(f"🔀 CLOB Relay: {'✅ ' + cls.CLOB_RELAY_URL if cls.is_relay_enabled() else '❌ Direct (may be geo-blocked)'}", flush=True)
        redeem_ok = bool(cls.POLY_BUILDER_API_KEY and cls.POLY_BUILDER_SECRET and cls.POLY_BUILDER_PASSPHRASE)
        print(f"💰 Auto-Redeem: {'✅ enabled' if redeem_ok else '❌ disabled (set POLY_BUILDER_* env vars)'}", flush=True)
        print(f"Balance: {cls.format_usdc(cls.STARTING_BALANCE_USDC)}", flush=True)
        print(f"{'='*60}\n", flush=True)
