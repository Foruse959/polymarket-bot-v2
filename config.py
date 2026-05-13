"""
5min_trade v2.2 — Beast Mode Configuration

Polymarket V2 with:
- pUSD collateral
- SOL/XRP + BTC/ETH support with runtime coin toggling
- Persistent coin settings via coin_settings.json
- Comprehensive logging at every decision point
- Technical indicator-based strategies for 80%+ win rate
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# Persistent coin preferences file
COIN_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'coin_settings.json')


def _load_coin_settings() -> dict:
    """Load persistent coin settings from JSON (created by Telegram /coins command)."""
    try:
        if os.path.exists(COIN_SETTINGS_FILE):
            with open(COIN_SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[Config] Warning: could not load coin_settings.json: {e}", flush=True)
    return {}


def _save_coin_settings(settings: dict) -> bool:
    """Save coin settings to JSON."""
    try:
        with open(COIN_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"[Config] Error saving coin settings: {e}", flush=True)
        return False


class Config:
    """Central configuration for 5min_trade v2.2 Beast Mode."""

    # ═══════════════════════════════════════════════════════════════════
    VERSION = "2.2.0"
    VERSION_NAME = "Beast Mode"

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
    # BUILDER RELAYER
    # ═══════════════════════════════════════════════════════════════════
    POLY_BUILDER_API_KEY = os.getenv('POLY_BUILDER_API_KEY', '')
    POLY_BUILDER_SECRET = os.getenv('POLY_BUILDER_SECRET', '')
    POLY_BUILDER_PASSPHRASE = os.getenv('POLY_BUILDER_PASSPHRASE', '')
    POLY_BUILDER_CODE = os.getenv('POLY_BUILDER_CODE', '')
    AUTO_REDEEM_INTERVAL = int(os.getenv('AUTO_REDEEM_INTERVAL', '120'))
    POLYGON_RPC_URL = os.getenv('POLYGON_RPC_URL', '')

    # ═══════════════════════════════════════════════════════════════════
    # V2 CONTRACT ADDRESSES
    # ═══════════════════════════════════════════════════════════════════
    PUSD_CONTRACT = '0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB'
    CTF_EXCHANGE_V2 = '0xE111180000d2663C0091e4f400237545B87B996B'
    NEG_RISK_CTF_EXCHANGE = '0xe2222d279d744050d28e00520010520000310F59'

    # ═══════════════════════════════════════════════════════════════════
    # API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════
    GAMMA_API_URL = 'https://gamma-api.polymarket.com'
    CLOB_API_URL = 'https://clob.polymarket.com'
    BINANCE_API_URL = 'https://api.binance.com'
    BINANCE_WS_URL = 'wss://stream.binance.com:9443/ws'
    POLYMARKET_WS_URL = 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
    POLYMARKET_LIVE_WS_URL = 'wss://ws-live-data.polymarket.com'

    # ═══════════════════════════════════════════════════════════════════
    # PROXY / RELAY
    # ═══════════════════════════════════════════════════════════════════
    PROXY_URL = os.getenv('PROXY_URL', '')
    CLOB_RELAY_URL = os.getenv('CLOB_RELAY_URL', '')
    CLOB_RELAY_AUTH_TOKEN = os.getenv('CLOB_RELAY_AUTH_TOKEN', '')

    # ═══════════════════════════════════════════════════════════════════
    # TRADING MODE
    # ═══════════════════════════════════════════════════════════════════
    TRADING_MODE = os.getenv('TRADING_MODE', 'paper')
    STARTING_BALANCE = float(os.getenv('STARTING_BALANCE', '100.0'))
    POLYMARKET_MIN_ORDER_SIZE = 1.0
    DEFAULT_ORDER_TYPE = os.getenv('DEFAULT_ORDER_TYPE', 'maker')
    MAKER_PREFERRED = os.getenv('MAKER_PREFERRED', 'true').lower() == 'true'

    # ═══════════════════════════════════════════════════════════════════
    # V2 FEE STRUCTURE
    # ═══════════════════════════════════════════════════════════════════
    V2_FEE_RATES = {
        'crypto': 0.07, 'sports': 0.03, 'finance': 0.04, 'politics': 0.04,
        'economics': 0.05, 'culture': 0.05, 'weather': 0.05, 'tech': 0.04,
        'mentions': 0.04, 'geopolitics': 0.0, 'other': 0.05,
    }

    CATEGORY_SPREAD_MULTIPLIERS = {
        'finance': 1.0, 'politics': 1.25, 'crypto': 1.5, 'sports': 1.75,
        'entertainment': 2.0, 'culture': 2.0, 'other': 1.5,
    }

    # ═══════════════════════════════════════════════════════════════════
    # COINS — NOW SUPPORTS BTC, ETH, SOL, XRP (editable via Telegram)
    # ═══════════════════════════════════════════════════════════════════
    ALL_SUPPORTED_COINS = ['BTC', 'ETH', 'SOL', 'XRP']

    # Runtime coin settings (loaded from coin_settings.json or env)
    _coin_settings = _load_coin_settings()

    @classmethod
    def _get_enabled_coins(cls) -> list:
        """Get enabled coins from (1) coin_settings.json, (2) .env, (3) default."""
        saved = cls._coin_settings.get('enabled_coins')
        if saved and isinstance(saved, list):
            return [c.upper() for c in saved if c.upper() in cls.ALL_SUPPORTED_COINS]
        env_coins = os.getenv('ENABLED_COINS', 'BTC,ETH,SOL,XRP')
        return [c.strip().upper() for c in env_coins.split(',') if c.strip().upper() in cls.ALL_SUPPORTED_COINS]

    ENABLED_COINS = []  # Will be set below

    BINANCE_SYMBOLS = {'BTC': 'btcusdt', 'ETH': 'ethusdt', 'SOL': 'solusdt', 'XRP': 'xrpusdt'}
    BINANCE_CANDLE_SYMBOLS = {'BTC': 'BTCUSDT', 'ETH': 'ETHUSDT', 'SOL': 'SOLUSDT', 'XRP': 'XRPUSDT'}
    COIN_PM = {'BTC': 'btc', 'ETH': 'eth', 'SOL': 'sol', 'XRP': 'xrp'}
    COIN_DISPLAY_NAMES = {'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'SOL': 'Solana', 'XRP': 'XRP'}
    SERIES_SLUGS = {
        5: '{coin}-up-or-down-5m',
        15: '{coin}-up-or-down-15m',
        30: '{coin}-up-or-down-30m',
    }

    # ═══════════════════════════════════════════════════════════════════
    # TIMEFRAMES
    # ═══════════════════════════════════════════════════════════════════
    ENABLED_TIMEFRAMES = [int(t) for t in os.getenv('ENABLED_TIMEFRAMES', '5,15').split(',')]

    TIMEFRAME_PARAMS = {
        5: {'name': '5 min', 'scan_interval': 1, 'position_size_pct': 3.0,
            'max_positions': 20, 'take_profit_pct': 30.0, 'stop_loss_pct': 16.0,
            'min_confidence': 0.55,
            'preferred_strategies': ['indicator_fusion', 'microstructure_maker', 'momentum_breakout']},
        15: {'name': '15 min', 'scan_interval': 3, 'position_size_pct': 3.0,
             'max_positions': 20, 'take_profit_pct': 40.0, 'stop_loss_pct': 16.0,
             'min_confidence': 0.55,
             'preferred_strategies': ['indicator_fusion', 'microstructure_maker', 'mean_reversion']},
        30: {'name': '30 min', 'scan_interval': 5, 'position_size_pct': 3.0,
             'max_positions': 20, 'take_profit_pct': 50.0, 'stop_loss_pct': 16.0,
             'min_confidence': 0.55,
             'preferred_strategies': ['indicator_fusion', 'microstructure_maker', 'momentum_breakout']},
    }

    # ═══════════════════════════════════════════════════════════════════
    # STRATEGY SETTINGS
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
    # BEAST MODE: HIGH-CONVICTION MODE
    # When 3+ strategies agree → trade bigger, higher conviction
    # ═══════════════════════════════════════════════════════════════════
    HIGH_CONVICTION_MIN_STRATEGIES = 3
    HIGH_CONVICTION_SIZE_MULTIPLIER = 1.5
    STRICT_MIN_CONFIDENCE = float(os.getenv('STRICT_MIN_CONFIDENCE', '0.55'))
    INDICATOR_WEIGHT = 1.2  # Indicator-based strategy gets extra weight

    # ═══════════════════════════════════════════════════════════════════
    # RISK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════
    MAX_DAILY_LOSS_PCT = float(os.getenv('MAX_DAILY_LOSS_PCT', '50.0'))
    MAX_TOTAL_POSITIONS = int(os.getenv('MAX_TOTAL_POSITIONS', '20'))
    MAX_SINGLE_MARKET_EXPOSURE_PCT = float(os.getenv('MAX_SINGLE_MARKET_EXPOSURE_PCT', '15.0'))
    DRAWDOWN_HALT_PCT = float(os.getenv('DRAWDOWN_HALT_PCT', '25.0'))
    CONSECUTIVE_LOSS_HALT = int(os.getenv('CONSECUTIVE_LOSS_HALT', '8'))
    KELLY_FRACTION = float(os.getenv('KELLY_FRACTION', '0.25'))
    KELLY_MAX_BET_PCT = float(os.getenv('KELLY_MAX_BET_PCT', '0.08'))

    # ═══════════════════════════════════════════════════════════════════
    # BACKWARD COMPAT
    # ═══════════════════════════════════════════════════════════════════
    STARTING_BALANCE_USDC = STARTING_BALANCE
    POLYMARKET_MIN_ORDER_SIZE_USDC = 1.0
    LONGSHOT_MAX_POSITION_USDC = LONGSHOT_MAX_POSITION
    TAKER_FEE_RATE = float(os.getenv('TAKER_FEE_RATE', '0.03125'))
    MAKER_FEE_RATE = 0.0

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
        return f"{amount:.2f} pUSD"

    @classmethod
    def format_usdc(cls, amount: float) -> str:
        return f"{amount:.2f} pUSD"

    @classmethod
    def get_taker_fee(cls, category: str, shares: float, price: float) -> float:
        fee_rate = cls.V2_FEE_RATES.get(category.lower(), 0.05)
        return shares * fee_rate * price * (1 - price)

    @classmethod
    def get_category_spread_multiplier(cls, category: str) -> float:
        return cls.CATEGORY_SPREAD_MULTIPLIERS.get(category.lower(), 1.5)

    # ─── COIN PREFERENCE MANAGEMENT ──────────────────────────────
    @classmethod
    def update_enabled_coins(cls, coins: list) -> bool:
        """Toggle enabled coins at runtime (called by Telegram /coins command)."""
        valid = [c.upper() for c in coins if c.upper() in cls.ALL_SUPPORTED_COINS]
        if not valid:
            return False
        cls.ENABLED_COINS = valid
        cls._coin_settings['enabled_coins'] = valid
        return _save_coin_settings(cls._coin_settings)

    @classmethod
    def toggle_coin(cls, coin: str) -> bool:
        """Toggle a single coin on/off. Returns True if now enabled."""
        coin = coin.upper()
        if coin not in cls.ALL_SUPPORTED_COINS:
            return False
        current = list(cls.ENABLED_COINS)
        if coin in current:
            current.remove(coin)
            if not current:  # Don't allow zero coins
                current = [coin]
                cls.update_enabled_coins(current)
                return True
        else:
            current.append(coin)
        cls.update_enabled_coins(current)
        return coin in cls.ENABLED_COINS

    @classmethod
    def reload_coin_settings(cls):
        """Reload coin settings from disk."""
        cls._coin_settings = _load_coin_settings()
        cls.ENABLED_COINS = cls._get_enabled_coins()

    # ─── TIMEFRAME PREFERENCE MANAGEMENT ──────────────────────────
    ALL_SUPPORTED_TIMEFRAMES = [5, 15, 30]

    @classmethod
    def update_enabled_timeframes(cls, timeframes: list) -> bool:
        """
        Toggle enabled timeframes at runtime (called by Telegram /timeframe
        command). Persists to coin_settings.json.
        """
        valid = []
        for t in timeframes:
            try:
                tf = int(t)
                if tf in cls.ALL_SUPPORTED_TIMEFRAMES:
                    valid.append(tf)
            except (ValueError, TypeError):
                continue
        if not valid:
            return False
        # De-dup + sort for stable ordering
        valid = sorted(set(valid))
        cls.ENABLED_TIMEFRAMES = valid
        cls._coin_settings['enabled_timeframes'] = valid
        return _save_coin_settings(cls._coin_settings)

    @classmethod
    def toggle_timeframe(cls, tf: int) -> bool:
        """Toggle a single timeframe on/off. Returns True if now enabled."""
        try:
            tf = int(tf)
        except (ValueError, TypeError):
            return False
        if tf not in cls.ALL_SUPPORTED_TIMEFRAMES:
            return False
        current = list(cls.ENABLED_TIMEFRAMES)
        if tf in current:
            current.remove(tf)
            if not current:
                # Don't allow empty — keep the toggled one
                current = [tf]
                cls.update_enabled_timeframes(current)
                return True
        else:
            current.append(tf)
        cls.update_enabled_timeframes(current)
        return tf in cls.ENABLED_TIMEFRAMES

    @classmethod
    def _load_saved_timeframes(cls):
        """Restore saved timeframes from settings on startup (if any)."""
        saved = cls._coin_settings.get('enabled_timeframes')
        if saved and isinstance(saved, list):
            valid = [int(t) for t in saved if int(t) in cls.ALL_SUPPORTED_TIMEFRAMES]
            if valid:
                cls.ENABLED_TIMEFRAMES = sorted(set(valid))

    @classmethod
    def print_status(cls):
        mode = '📋 PAPER' if cls.is_paper() else '🔴 LIVE'
        order_type = 'MAKER (0% fee)' if cls.MAKER_PREFERRED else 'TAKER'
        print(f"\n{'='*60}", flush=True)
        print(f"⚡ 5MIN_TRADE v{cls.VERSION} — {cls.VERSION_NAME}", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Mode:    {mode}", flush=True)
        print(f"Orders:  {order_type}", flush=True)
        print(f"Coll:    pUSD (V2)", flush=True)
        print(f"Coins:   {', '.join(cls.ENABLED_COINS)}", flush=True)
        print(f"TFs:     {cls.ENABLED_TIMEFRAMES}min", flush=True)
        print(f"Balance: {cls.format_balance(cls.STARTING_BALANCE)}", flush=True)
        print(f"Risk:    Kelly={cls.KELLY_FRACTION} | Max DD={cls.DRAWDOWN_HALT_PCT}%", flush=True)
        print(f"Conv:    Min conf={cls.STRICT_MIN_CONFIDENCE} | HC need {cls.HIGH_CONVICTION_MIN_STRATEGIES}+ agree", flush=True)
        print(f"{'='*60}\n", flush=True)


# Initialize enabled coins AFTER class definition
Config.ENABLED_COINS = Config._get_enabled_coins()
Config._load_saved_timeframes()
