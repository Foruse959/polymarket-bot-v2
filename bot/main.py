"""
Telegram Bot — Main Handlers (v2)

Commands for controlling the v2 maker-focused bot.
"""

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from config import Config


class TelegramBot:
    """Telegram bot for controlling the 5min_trade v2 scalper."""

    def __init__(self, engine=None):
        self.engine = engine
        self.app = None

    async def setup(self):
        """Build the Telegram application."""
        self.app = (
            Application.builder()
            .token(Config.TELEGRAM_BOT_TOKEN)
            .build()
        )

        # Register commands
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("trade", self.cmd_trade))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("strategy", self.cmd_strategy))
        self.app.add_handler(CommandHandler("mode", self.cmd_mode))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("download", self.cmd_download))
        self.app.add_handler(CommandHandler("export", self.cmd_download))

        try:
            await self.app.bot.set_my_commands([
                BotCommand("start", "Welcome & menu"),
                BotCommand("trade", "Start trading"),
                BotCommand("stop", "Stop trading"),
                BotCommand("mode", "Switch paper/live mode"),
                BotCommand("status", "Position & P&L status"),
                BotCommand("balance", "Check balance"),
                BotCommand("positions", "View open positions"),
                BotCommand("strategy", "View/change strategy"),
                BotCommand("download", "Download trades CSV"),
                BotCommand("export", "Export trades (alias)"),
            ])
            print("✅ Telegram commands registered", flush=True)
        except Exception as e:
            print(f"⚠️ Telegram commands setup failed: {e}", flush=True)

        async def error_handler(update, context):
            print(f"❌ Bot error: {context.error}")

        self.app.add_error_handler(error_handler)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message."""
        is_live = self.engine and self.engine.trading_mode == 'live'
        mode = "🔴 LIVE" if is_live else "📋 PAPER"
        trading = "✅ Running" if (self.engine and self.engine.is_running) else "⏹️ Stopped"

        if is_live:
            balance = self.engine.live_balance_mgr.balance_usdc
            m = self.engine.live_balance_mgr.mode
            risk_line = f"Risk: {m.emoji} {m.name}\n"
        else:
            balance = self.engine.paper_trader.balance_mgr.balance_usdc if self.engine else Config.STARTING_BALANCE_USDC
            risk_line = ""

        text = (
            f"⚡ *5MIN_TRADE v{Config.VERSION} — {Config.VERSION_NAME}*\n\n"
            f"Mode: {mode}\n"
            f"{risk_line}"
            f"Status: {trading}\n"
            f"Balance: {Config.format_usdc(balance)}\n"
            f"Coins: {', '.join(Config.ENABLED_COINS)}\n"
            f"Timeframes: {Config.ENABLED_TIMEFRAMES}\n\n"
            f"🎯 *Strategies:*\n"
            f"  📝 Maker Edge — Limit orders on NO side\n"
            f"  🎯 Longshot Bias — Exploit retail bias\n\n"
            f"Commands:\n"
            f"/trade — Start trading\n"
            f"/stop — Stop trading\n"
            f"/status — Check status\n"
            f"/balance — View balance\n"
            f"/positions — Open positions\n"
        )

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start trading."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        if self.engine.is_running:
            await update.message.reply_text("✅ Already trading")
            return

        self.engine.start()
        await update.message.reply_text("🚀 Trading started!")

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop trading."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        self.engine.stop()
        await update.message.reply_text("⏹️ Trading stopped")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get status."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        is_live = self.engine.trading_mode == 'live'
        mode = "🔴 LIVE" if is_live else "📋 PAPER"
        
        if is_live:
            stats = self.engine.live_balance_mgr.get_stats()
        else:
            stats = self.engine.paper_trader.get_stats()

        text = (
            f"📊 *Status*\n\n"
            f"Mode: {mode}\n"
            f"Running: {'✅' if self.engine.is_running else '⏹️'}\n"
            f"Balance: {Config.format_usdc(stats['balance_usdc'])}\n"
            f"Open Positions: {stats.get('open_positions', 0)}\n"
        )

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show balance."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        is_live = self.engine.trading_mode == 'live'
        
        if is_live:
            balance = self.engine.live_balance_mgr.balance_usdc
            tradeable = self.engine.live_balance_mgr.get_tradeable_balance_usdc()
        else:
            balance = self.engine.paper_trader.balance_mgr.balance_usdc
            tradeable = self.engine.paper_trader.balance_mgr.get_tradeable_balance_usdc()

        text = (
            f"💰 *Balance*\n\n"
            f"Total: {Config.format_usdc(balance)}\n"
            f"Tradeable: {Config.format_usdc(tradeable)}\n"
        )

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show open positions."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        positions = list(self.engine.paper_trader.positions.values()) if not self.engine.trading_mode == 'live' else list(self.engine.live_trader.positions.values())

        if not positions:
            await update.message.reply_text("No open positions")
            return

        text = "📈 *Open Positions*\n\n"
        for pos in positions[:5]:
            text += f"• {pos['coin']} {pos['direction']} @ {pos['entry_price']:.3f} ({pos['order_type']})\n"

        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current strategy."""
        text = (
            f"🎯 *Active Strategies*\n\n"
            f"• Maker Edge (maker orders)\n"
            f"• Longshot Bias (behavioral arb)\n\n"
            f"Default: {Config.DEFAULT_ORDER_TYPE.upper()}"
        )
        await update.message.reply_text(text, parse_mode='Markdown')

    async def cmd_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show/switch mode."""
        if not self.engine:
            await update.message.reply_text("❌ Engine not initialized")
            return

        current = self.engine.trading_mode
        text = f"Current mode: {'🔴 LIVE' if current == 'live' else '📋 PAPER'}\n\nUse environment variable TRADING_MODE to switch."
        await update.message.reply_text(text)

    async def cmd_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download trades CSV."""
        import csv
        import io
        from datetime import datetime
        
        try:
            # Get trade history
            if self.engine and self.engine.trading_mode == 'live':
                trades = list(self.engine.live_trader.trade_history)
            elif self.engine:
                trades = list(self.engine.paper_trader.trade_history)
            else:
                trades = []
            
            # Also check for CSV file
            csv_files = ['data/trades_log.csv', 'trades_log.csv']
            file_path = None
            for f in csv_files:
                if os.path.exists(f):
                    file_path = f
                    break
            
            if file_path:
                # Send existing file
                await update.message.reply_document(
                    document=open(file_path, 'rb'),
                    caption=f"📊 Trades CSV - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
            elif trades:
                # Generate CSV from memory
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['ID', 'Time', 'Coin', 'Direction', 'Entry', 'Exit', 'PnL', 'Strategy'])
                
                for t in trades:
                    writer.writerow([
                        t.get('id', ''),
                        t.get('entry_time', ''),
                        t.get('coin', ''),
                        t.get('direction', ''),
                        t.get('entry_price', 0),
                        t.get('exit_price', 0),
                        t.get('pnl', 0),
                        t.get('strategy', '')
                    ])
                
                output.seek(0)
                await update.message.reply_document(
                    document=output.getvalue().encode(),
                    filename=f"trades_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    caption=f"📊 {len(trades)} trades exported"
                )
            else:
                await update.message.reply_text("📭 No trades to export yet")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    async def run(self):
        """Start the bot (v22 compatible)."""
        try:
            print("📱 Initializing Telegram...", flush=True)
            await self.app.initialize()
            print("📱 Starting Telegram app...", flush=True)
            await self.app.start()
            if self.app.updater:
                print("📱 Starting polling...", flush=True)
                await self.app.updater.start_polling(drop_pending_updates=True)
            print("✅ Telegram bot started", flush=True)
        except Exception as e:
            print(f"❌ Telegram bot error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return
        # Keep alive
        import asyncio
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Stop the bot."""
        if self.app:
            try:
                if self.app.updater:
                    await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                print(f"Telegram stop error: {e}", flush=True)
