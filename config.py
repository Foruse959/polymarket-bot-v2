"""
5min_trade v2.1 — Configuration

Fully upgraded for Polymarket V2 (April 28, 2026):
- pUSD collateral (NOT USDC.e) — backed 1:1 by USDC
- pUSD Contract: 0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB (Polygon)
- CTF Exchange V2: 0xE111180000d2663C0091e4f400237545B87B996B
- py-clob-client-v2 SDK with builder codes
- Maker-focused strategies (zero maker fees, earn rebates)
- Research-backed strategies from Becker's microstructure analysis
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration for the 5min_trade v2.1 bot."""

    # ═══════════════════════════════════════════════════════════════════
    # VERSION
    # ═══════════════════════════════════════════════════════════════════
    VERSION = "2.1.0"
    VERSION_NAME = "Microstructure Edge"

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
    POLY_FUNDER_ADDRESS = os.getenv('POLY_FUNDER_ADDRESS', '')
    POLY_PROXY_WALLET = os.getenv('POLY_PROXY_WALLET', '')
    POLY_API_KEY = os.getenv('POLY_API_KEY', '')
    POLY_API_SECRET = os.getenv('POLY_API_SECRET', '')
    POLY_PASSPHRASE = os.getenv('POLY_PASSPHRASE', '')
    POLY_SIGNATURE_TYPE = int(os.getenv('POLY_SIGNATURE_TYPE', '0'))
    POLY_CHAIN_ID = int(os.getenv('POLY_CHAIN_ID', '137'))

    # ═══════════════════════════════════════════════════════════════════
    # BUILDER RELAYER (V2: builder codes for attribution + gasless)
    # ═══════════════════════════════════════════════════════════════════
    POLY_BUILDER_API_KEY = os.getenv('POLY_BUILDER_API_KEY', '')
    POLY_BUILDER_SECRET = os.getenv('POLY_BUILDER_SECRET', '')
    POLY_BUILDER_PASSPHRASE = os.getenv('POLY_BUILDER_PASSPHRASE', '')
    POLY_BUILDER_CODE = os.getenv('POLY_BUILDER_CODE', '')
    AUTO_REDEEM_INTERVAL = int(os.getenv('AUTO_REDEEM_INTERVAL', '120'))
    POLYGON_RPC_URL = os.getenv('POLYGON_RPC_URL', '')

    # ═══════════════════════════════════════════════════════════════════
    # V2 CONTRACT ADDRESSES (April 28, 2026 upgrade)
    # ═══════════════════════════════════════════════════════════════════
    PUSD_CONTRACT = '0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB'
    CTF_EXCHANGE_V2 = '0xE111180000d2663C0091e4f400237545B87B996B'
    NEG_RISK_CTF_EXCHANGE = '0xe2222d279d744050d28e00520010520000310F59'
    NEG_RISK_ADAPTER = '0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296'
    CONDITIONAL_TOKENS = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'
    COLLATERAL_ONRAMP = '0x93070a847efEf7F70739046A929D47a521F5B8ee'
    COLLATERAL_OFFRAMP = '0x2957922Eb93258b93368531d39fAcCA3B4dC5854'
    CTF_COLLATERAL_ADAPTER = '0xAdA100Db00Ca00073811820692005400218FcE1f'
    NEGRISK_COLLATERAL_ADAPTER = '0xadA2005600Dec949baf300f4C6120000bDB6eAab'
    DEPOSIT_WALLET_FACTORY = '0x00000000000Fb5C9ADea0298D729A0CB3823Cc07'

    # ═══════════════════════════════════════════════════════════════════
    # API ENDPOINTS (V2)
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
    CLOB_RELAY_AUTH_TOKEN = os.getenv('CLOB_RELAY_AUTH_TOKEN', '')

    # ═══════════════════════════════════════════════════════════════════
    # TRADING MODE
    # ═══════════════════════════════════════════════════════════════════
    TRADING_MODE = os.getenv('TRADING_MODE', 'paper')
    LIVE_RISK_MODE = os.getenv('LIVE_RISK_MODE', 'concentration')
    STARTING_BALANCE = float(os.getenv('STARTING_BALANCE', '100.0'))
    POLYMARKET_MIN_ORDER_SIZE = 1.0  # $1 minimum (FOK minimum)
    DEFAULT_ORDER_TYPE = os.getenv('DEFAULT_ORDER_TYPE', 'maker')
    MAKER_PREFERRED = os.getenv('MAKER_PREFERRED', 'true').lower() == 'true'

    # ═══════════════════════════════════════════════════════════════════
    # V2 FEE STRUCTURE (fee = C * feeRate * p * (1-p))
    # Makers NEVER pay fees. Only takers pay.
    # ═══════════════════════════════════════════════════════════════════
    V2_FEE_RATES = {
        'crypto': 0.07, 'sports': 0.03, 'finance': 0.04,
        'politics': 0.04, 'economics': 0.05, 'culture': 0.05,
        'weather': 0.05, 'tech': 0.04, 'mentions': 0.04,
        'geopolitics': 0.0, 'other': 0.05,
    }
    V2_MAKER_REBATES = {
        'crypto': 0.20, 'sports': 0.25, 'finance': 0.25,
        'politics': 0.25, 'economics': 0.25, 'culture': 0.25,
        'weather': 0.25, 'tech': 0.25, 'mentions': 0.25,
        'geopolitics': 0.0, 'other': 0.25,
    }
    CATEGORY_SPREAD_MULTIPLIERS = {
        'finance': 1.0, 'politics': 1.25, 'crypto': 1.5,
        'sports': 1.75, 'entertainment': 2.0, 'culture': 2.0, 'other': 1.5,
    }

    MARKET_FOCUS_IDLE_SCANS = int(os.getenv('MARKET_FOCUS_IDLE_SCANS', '3'))
    MIN_EDGE_AFTER_FEES = float(os.getenv('MIN_EDGE_AFTER_FEES', '0.03'))

    # ═══════════════════════════════════════════════════════════════════
    # COINS
    # ═══════════════════════════════════════════════════════════════════
    ENABLED_COINS = [c.strip().upper() for c in os.getenv('ENABLED_COINS', 'BTC,ETH').split(',')]
    BINANCE_SYMBOLS = {'BTC': 'btcusdt', 'ETH': 'ethusdt', 'SOL': 'solusdt', 'XRP': 'xrpusdt'}
    COIN_PM = {'BTC': 'btc', 'ETH': 'eth', 'SOL': 'sol', 'XRP': 'xrp'}
    SERIES_SLUGS = {5: '{coin}-up-or-down-5m', 15: '{coin}-up-or-down-15m', 30: '{coin}-up-or-down-30m'}

    # ═══════════════════════════════════════════════════════════════════
    # TIMEFRAME SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    ENABLED_TIMEFRAMES = [int(t) for t in os.getenv('ENABLED_TIMEFRAMES', '5,15').split(',')]
    TIMEFRAME_PARAMS = {
        5: {'name': '5 min', 'scan_interval': 1, 'position_size_pct': 3.0, 'max_positions': 20,
            'take_profit_pct': 200.0, 'stop_loss_pct': 16.0, 'min_confidence': 0.40,
            'preferred_strategies': ['microstructure_maker', 'volume_imbalance', 'momentum_breakout']},
        15: {'name': '15 min', 'scan_interval': 3, 'position_size_pct': 3.0, 'max_positions': 20,
             'take_profit_pct': 200.0, 'stop_loss_pct': 16.0, 'min_confidence': 0.40,
             'preferred_strategies': ['microstructure_maker', 'mean_reversion', 'maker_edge']},
        30: {'name': '30 min', 'scan_interval': 5, 'position_size_pct': 3.0, 'max_positions': 20,
             'take_profit_pct': 200.0, 'stop_loss_pct': 16.0, 'min_confidence': 0.40,
             'preferred_strategies': ['microstructure_maker', 'momentum_breakout', 'oracle_arb']},
    }

    # ═══════════════════════════════════════════════════════════════════
    # MAKER STRATEGY SETTINGS (Becker research + 186K market backtest)
    # ═══════════════════════════════════════════════════════════════════
    MAKER_MIN_SPREAD_BPS = float(os.getenv('MAKER_MIN_SPREAD_BPS', '50'))
    MAKER_TARGET_SPREAD_BPS = float(os.getenv('MAKER_TARGET_SPREAD_BPS', '100'))
    MAKER_MAX_SPREAD_BPS = float(os.getenv('MAKER_MAX_SPREAD_BPS', '300'))
    VOLUME_LOW_THRESHOLD = float(os.getenv('VOLUME_LOW_THRESHOLD', '100'))
    VOLUME_MED_THRESHOLD = float(os.getenv('VOLUME_MED_THRESHOLD', '1000'))
    VOLUME_HIGH_THRESHOLD = float(os.getenv('VOLUME_HIGH_THRESHOLD', '10000'))
    LONGSHOT_THRESHOLD_LOW = float(os.getenv('LONGSHOT_THRESHOLD_LOW', '0.20'))
    LONGSHOT_THRESHOLD_HIGH = float(os.getenv('LONGSHOT_THRESHOLD_HIGH', '0.80'))
    LONGSHOT_MAX_POSITION = float(os.getenv('LONGSHOT_MAX_POSITION', '50.0'))

    # ═══════════════════════════════════════════════════════════════════
    # RISK MANAGEMENT (Enhanced)
    # ═══════════════════════════════════════════════════════════════════
    MAX_DAILY_LOSS_PCT = float(os.getenv('MAX_DAILY_LOSS_PCT', '50.0'))
    MAX_TOTAL_POSITIONS = int(os.getenv('MAX_TOTAL_POSITIONS', '20'))
    MAX_SINGLE_MARKET_EXPOSURE_PCT = float(os.getenv('MAX_SINGLE_MARKET_EXPOSURE_PCT', '15.0'))
    DRAWDOWN_HALT_PCT = float(os.getenv('DRAWDOWN_HALT_PCT', '25.0'))
    CONSECUTIVE_LOSS_HALT = int(os.getenv('CONSECUTIVE_LOSS_HALT', '8'))
    KELLY_FRACTION = float(os.getenv('KELLY_FRACTION', '0.25'))
    KELLY_MAX_BET_PCT = float(os.getenv('KELLY_MAX_BET_PCT', '0.08'))

    # ═══════════════════════════════════════════════════════════════════
    # BACKWARD COMPATIBILITY
    # ═══════════════════════════════════════════════════════════════════
    STARTING_BALANCE_USDC = float(os.getenv('STARTING_BALANCE', '100.0'))
    POLYMARKET_MIN_ORDER_SIZE_USDC = 1.0
    LONGSHOT_MAX_POSITION_USDC = float(os.getenv('LONGSHOT_MAX_POSITION', '50.0'))
    TAKER_FEE_RATE = float(os.getenv('TAKER_FEE_RATE', '0.03125'))
    MAKER_FEE_RATE = 0.0

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
        if cls.CLOB_RELAY_URL:
            return cls.CLOB_RELAY_URL.rstrip('/')
        return cls.CLOB_API_URL

    @classmethod
    def is_relay_enabled(cls) -> bool:
        return bool(cls.CLOB_RELAY_URL)

    @classmethod
    def is_live_ready(cls) -> bool:
        pk = cls.POLY_PRIVATE_KEY.strip() if cls.POLY_PRIVATE_KEY else ''
        return bool(pk)

    @classmethod
    def derive_wallet_address(cls) -> str:
        pk = cls.POLY_PRIVATE_KEY.strip() if cls.POLY_PRIVATE_KEY else ''
        if not pk:
            return ''
        try:
            from eth_account import Account
            if not pk.startswith('0x'):
                pk = '0x' + pk
            return Account.from_key(pk).address
        except Exception:
            return ''

    @classmethod
    def get_funder_address(cls) -> str:
        if cls.POLY_FUNDER_ADDRESS and cls.POLY_FUNDER_ADDRESS.strip():
            return cls.POLY_FUNDER_ADDRESS.strip()
        if cls.POLY_SIGNATURE_TYPE == 2:
            if cls.POLY_PROXY_WALLET and cls.POLY_PROXY_WALLET.strip():
                return cls.POLY_PROXY_WALLET.strip()
            return ''
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
    def format_balance(cls, amount: float) -> str:
        """Format amount as pUSD string (V2 collateral token)."""
        return f"{amount:.2f} pUSD"

    @classmethod
    def format_usdc(cls, amount: float) -> str:
        """Backward compat alias — shows pUSD."""
        return f"{amount:.2f} pUSD"

    @classmethod
    def get_taker_fee(cls, category: str, shares: float, price: float) -> float:
        """Calculate V2 taker fee: fee = C * feeRate * p * (1-p)"""
        fee_rate = cls.V2_FEE_RATES.get(category.lower(), 0.05)
        return shares * fee_rate * price * (1 - price)

    @classmethod
    def get_category_spread_multiplier(cls, category: str) -> float:
        return cls.CATEGORY_SPREAD_MULTIPLIERS.get(category.lower(), 1.5)

    @classmethod
    def print_status(cls):
        mode = '📋 PAPER' if cls.is_paper() else '🔴 LIVE'
        pk_ok = bool(cls.POLY_PRIVATE_KEY and cls.POLY_PRIVATE_KEY.strip())
        order_type = 'MAKER (0% fee)' if cls.MAKER_PREFERRED else 'TAKER'
        print(f"\n{'='*60}", flush=True)
        print(f"⚡ 5MIN_TRADE v{cls.VERSION} — {cls.VERSION_NAME}", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Mode: {mode} | Orders: {order_type} | Collateral: pUSD (V2)", flush=True)
        print(f"Coins: {', '.join(cls.ENABLED_COINS)} | TF: {cls.ENABLED_TIMEFRAMES}", flush=True)
        print(f"Balance: {cls.format_balance(cls.STARTING_BALANCE)}", flush=True)
        print(f"Risk: Kelly={cls.KELLY_FRACTION} | Max DD={cls.DRAWDOWN_HALT_PCT}%", flush=True)
        print(f"{'='*60}\n", flush=True)
