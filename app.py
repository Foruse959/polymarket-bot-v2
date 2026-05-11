"""
5min_trade v2 — Entry Point

Runs the Telegram bot + trading engine concurrently.
Maker-focused trading with USDC.
"""

import asyncio
import os
import sys
import signal

from config import Config

# Proxy setup
if Config.PROXY_URL:
    os.environ['HTTP_PROXY'] = Config.PROXY_URL
    os.environ['HTTPS_PROXY'] = Config.PROXY_URL
    os.environ['http_proxy'] = Config.PROXY_URL
    os.environ['https_proxy'] = Config.PROXY_URL
    print(f"🌐 Proxy configured: {Config.PROXY_URL[:30]}...", flush=True)

from data.gamma_client import GammaClient
from data.clob_client import ClobClient
from data.database import Database
from strategies.dynamic_picker import DynamicPicker
from strategies.maker_edge import MakerEdgeStrategy
from strategies.longshot_bias import LongshotBiasStrategy
from trading.paper_trader import PaperTrader
from trading.live_trader import LiveTrader
from trading.live_balance_manager import LiveBalanceManager, LIVE_MODES
from bot.main import TelegramBot


class TradingEngine:
    """Core engine — maker-focused, USDC trading."""

    def __init__(self):
        # Data layer
        self.gamma = GammaClient()
        self.clob = ClobClient()
        self.db = Database()

        # Trading components
        self.paper_balance_mgr = LiveBalanceManager(
            balance_usdc=Config.STARTING_BALANCE_USDC,
            mode='concentration'
        )
        self.paper_trader = PaperTrader(self.db, self.paper_balance_mgr)

        self.live_balance_mgr = LiveBalanceManager(
            balance_usdc=0.0,  # Will sync from chain
            mode=Config.LIVE_RISK_MODE
        )
        self.live_trader = LiveTrader(self.db, self.live_balance_mgr)

        # Mode
        self.trading_mode = Config.TRADING_MODE
        self.is_running = True  # Auto-start trading
        self._shutdown = False
        print("🚀 Trading auto-started", flush=True)

        # Strategies
        self.dynamic_picker = DynamicPicker()
        self.strategies = {
            'maker_edge': MakerEdgeStrategy(),
            'longshot_bias': LongshotBiasStrategy(),
            'dynamic': self.dynamic_picker,
        }
        self.active_strategy = 'dynamic'

        # Bot
        self.bot = TelegramBot(self)

        # Market tracking
        self.markets_cache = []
        self._last_market_scan = 0
        self._market_scan_interval = 15

    async def init(self):
        """Initialize components."""
        print(f"\n{'='*60}", flush=True)
        print(f"5MIN_TRADE v{Config.VERSION} - {Config.VERSION_NAME}", flush=True)
        print(f"{'='*60}\n", flush=True)

        # Init database
        await self.db.init()

        # Init live trader if in live mode
        if self.trading_mode == 'live':
            success = await self.live_trader.init(self.clob)
            if success:
                # Use configured balance (pUSD on deposit wallet)
                usdc_balance = Config.STARTING_BALANCE_USDC
                self.live_balance_mgr.update_balance(usdc_balance)
                print(f"Live balance: {Config.format_usdc(usdc_balance)}", flush=True)
            else:
                print(f"Live trader init failed: {self.live_trader.get_init_error()}", flush=True)
                print("Falling back to paper mode", flush=True)
                self.trading_mode = 'paper'

        # Setup bot
        await self.bot.setup()

        print(f"\nConfiguration:", flush=True)
        print(f"   Mode: {self.trading_mode.upper()}", flush=True)
        print(f"   Order Type: {'MAKER (limit)' if Config.MAKER_PREFERRED else 'TAKER (market)'}", flush=True)
        print(f"   Coins: {', '.join(Config.ENABLED_COINS)}", flush=True)
        print(f"   Timeframes: {Config.ENABLED_TIMEFRAMES}", flush=True)
        print(f"\n{'='*60}\n", flush=True)

    async def scan_markets(self):
        """Scan for active markets."""
        now = asyncio.get_event_loop().time()
        if now - self._last_market_scan < self._market_scan_interval:
            return self.markets_cache

        markets = self.gamma.discover_markets()
        self.markets_cache = markets
        self._last_market_scan = now

        if markets:
            print(f"📈 Found {len(markets)} active markets", flush=True)

        return markets

    async def run_strategy_cycle(self):
        """Run one trading cycle."""
        if not self.is_running:
            return

        # Get markets
        markets = await self.scan_markets()
        if not markets:
            return

        # Get active strategy
        strategy = self.strategies.get(self.active_strategy, self.dynamic_picker)

        # Analyze each market
        for market in markets[:10]:  # Limit to top 10 markets
            if self._shutdown:
                break

            context = {
                'clob': self.clob,
                'seconds_remaining': market.get('seconds_remaining', 9999),
                'category': market.get('category', 'other'),
            }

            try:
                signal = await strategy.analyze(market, context)
                if signal:
                    print(f"📊 Signal: {signal.coin} {signal.direction} conf={signal.confidence:.0%} type={signal.order_type}", flush=True)
                    if self.trading_mode == 'live':
                        result = await self.live_trader.execute_signal(signal)
                        if result:
                            print(f"✅ Trade executed: {result}", flush=True)
                    else:
                        await self.paper_trader.execute_signal(signal)
                else:
                    print(f"  No signal: {market.get('coin','?')} {market.get('timeframe','?')}m", flush=True)
            except Exception as e:
                print(f"⚠️ Strategy error for {market.get('coin','?')}: {e}", flush=True)

    async def check_positions(self):
        """Check and update positions."""
        if not self.is_running:
            return

        # Get current prices
        prices = {}
        open_positions = []
        
        if self.trading_mode == 'live':
            open_positions = list(self.live_trader.positions.values())
        else:
            open_positions = list(self.paper_trader.positions.values())

        for pos in open_positions:
            price = self.clob.get_price(pos['token_id'])
            if price:
                prices[pos['token_id']] = price

        # Check exits
        if self.trading_mode == 'live':
            await self.live_trader.check_positions(prices)
        else:
            await self.paper_trader.check_positions(prices)

    async def trading_loop(self):
        """Main trading loop."""
        while not self._shutdown:
            if self.is_running:
                try:
                    await self.run_strategy_cycle()
                    await self.check_positions()
                except Exception as e:
                    print(f"⚠️ Trading loop error: {e}", flush=True)

            await asyncio.sleep(5)  # 5 second cycle

    def start(self):
        """Start trading."""
        self.is_running = True
        print("🚀 Trading started", flush=True)

    def stop(self):
        """Stop trading."""
        self.is_running = False
        print("⏹️ Trading stopped", flush=True)

    async def run(self):
        """Run the engine."""
        await self.init()

        # Initialize Telegram bot first (before trading starts)
        await self.bot.app.initialize()
        await self.bot.app.start()
        if self.bot.app.updater:
            await self.bot.app.updater.start_polling(drop_pending_updates=True)
        print("✅ Telegram bot started", flush=True)

        # Now start both concurrently
        async def keep_telegram_alive():
            import asyncio
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        bot_task = asyncio.create_task(keep_telegram_alive())
        trading_task = asyncio.create_task(self.trading_loop())

        # Handle shutdown
        def signal_handler(sig, frame):
            print("\n🛑 Shutting down...", flush=True)
            self._shutdown = True
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            await asyncio.gather(bot_task, trading_task)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                if self.bot.app.updater:
                    await self.bot.app.updater.stop()
                await self.bot.app.stop()
                await self.bot.app.shutdown()
            except Exception:
                pass


async def main():
    """Main entry point."""
    engine = TradingEngine()
    await engine.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
