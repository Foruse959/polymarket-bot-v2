"""
Telegram UI — Coin selector and bot controls.

Commands:
  /start    — Welcome + status
  /status   — Balance, PnL, stats
  /coins    — Toggle BTC/ETH/SOL/XRP with inline buttons
  /positions — List open positions
  /recent   — Last 10 trades
  /pause    — Pause bot
  /resume   — Resume bot
  /help     — Commands list

Uses python-telegram-bot v21+ (async).
"""

import os
import asyncio
import threading
from typing import Callable, Optional

from config import Config

_TG_AVAILABLE = True
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
    )
except Exception as e:
    _TG_AVAILABLE = False
    _TG_IMPORT_ERROR = str(e)


class TelegramUI:
    """Telegram interface — coin selector + status + controls."""

    def __init__(self, state_provider: Callable = None, executor=None):
        self.state_provider = state_provider or (lambda: {})
        self.executor = executor
        # risk_mgr is pulled from executor when available so /tier can work.
        # Callers may also pass risk_mgr directly for read-only contexts.
        self.risk_mgr = getattr(executor, 'risk_mgr', None)
        self.app = None
        self._paused = False

    def available(self) -> bool:
        return _TG_AVAILABLE and bool(Config.TELEGRAM_BOT_TOKEN)

    def is_paused(self) -> bool:
        return self._paused

    # ─────────────────────────────────────────────────────────────
    # Command Handlers
    # ─────────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_html(
            f"<b>⚡ 5MIN_TRADE v{Config.VERSION} — {Config.VERSION_NAME}</b>\n"
            f"Polymarket V2 | pUSD Collateral\n\n"
            f"<b>Mode:</b> {'📋 PAPER' if Config.is_paper() else '🔴 LIVE'}\n"
            f"<b>Coins:</b> {', '.join(Config.ENABLED_COINS)}\n"
            f"<b>Timeframes:</b> {Config.ENABLED_TIMEFRAMES} min\n\n"
            "Commands:\n"
            "  /status — balance &amp; PnL\n"
            "  /coins — select BTC/ETH/SOL/XRP\n"
            "  /tier — change trading tier (SURVIVAL/SEED/etc)\n"
            "  /positions — open trades\n"
            "  /recent — last 10 trades\n"
            "  /pause /resume — control bot\n"
        )

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        state = self.state_provider()
        risk = state.get('risk', {})
        balance = state.get('balance', 0.0)
        start_bal = state.get('starting_balance', 100.0)
        ret_pct = ((balance - start_bal) / start_bal * 100) if start_bal > 0 else 0

        tier_emoji = risk.get('tier_emoji', '')
        tier_name = risk.get('tier', '—')
        manual = risk.get('manual_tier')
        tier_line = f"{tier_emoji} {tier_name}"
        if manual:
            tier_line += " 🔒 (manual lock)"
        else:
            tier_line += " (auto)"

        text = (
            f"💰 <b>Balance:</b> {balance:.2f} pUSD\n"
            f"🎚️ <b>Tier:</b> {tier_line}\n"
            f"📊 <b>Return:</b> {ret_pct:+.1f}%\n"
            f"📈 <b>Total PnL:</b> {state.get('total_pnl', 0):+.2f} pUSD\n"
            f"📅 <b>Daily PnL:</b> {state.get('daily_pnl', 0):+.2f} pUSD\n\n"
            f"🎯 <b>Win Rate:</b> {risk.get('win_rate', 0):.0f}%\n"
            f"✅ <b>Wins / Losses:</b> {risk.get('wins', 0)} / {risk.get('losses', 0)}\n"
            f"🔥 <b>Streak:</b> "
            f"{'W' + str(risk.get('consecutive_wins', 0)) if risk.get('consecutive_wins', 0) > 0 else 'L' + str(risk.get('consecutive_losses', 0))}\n"
            f"📉 <b>Drawdown:</b> {risk.get('drawdown_pct', 0):.1f}%\n\n"
            f"🌐 <b>Markets:</b> {state.get('markets_found', 0)} active\n"
            f"🎯 <b>Signals:</b> {state.get('total_signals', 0)} generated\n"
            f"💼 <b>Open positions:</b> {len(state.get('open_positions', []))}\n\n"
            f"<b>Coins:</b> {', '.join(Config.ENABLED_COINS)}\n"
            f"<b>Mode:</b> {'📋 PAPER' if Config.is_paper() else '🔴 LIVE'}\n"
            f"<b>Paused:</b> {'⏸ Yes' if self._paused else '▶️ No'}\n"
        )
        await update.message.reply_html(text)

    async def cmd_coins(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Show coin toggle buttons."""
        buttons = self._build_coin_buttons()
        await update.message.reply_html(
            "<b>🪙 Select coins to trade:</b>\n"
            "Tap a coin to toggle ON/OFF\n"
            f"<i>Currently enabled: {', '.join(Config.ENABLED_COINS)}</i>",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def cmd_positions(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.executor:
            await update.message.reply_text("Executor not initialized.")
            return
        positions = self.executor.get_positions_snapshot()
        if not positions:
            await update.message.reply_text("📭 No open positions.")
            return
        lines = [f"💼 <b>Open Positions ({len(positions)})</b>\n"]
        for p in positions[:10]:
            emoji = '📈' if p['pnl_pct'] >= 0 else '📉'
            lines.append(
                f"{emoji} <b>{p['coin']} {p['direction']}</b> — "
                f"{p['pnl_pct']:+.1f}% ({p['pnl_pusd']:+.2f} pUSD)\n"
                f"   size={p['size_pusd']:.2f} entry={p['entry_price']:.3f} "
                f"now={p['current_price']:.3f}\n"
                f"   TP=+{p['tp_pct']:.0f}% SL={p['sl_pct']:.0f}% "
                f"age={p['elapsed_sec']}s conf={p['confidence']:.0%}"
            )
        await update.message.reply_html('\n'.join(lines))

    async def cmd_recent(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self.executor:
            await update.message.reply_text("Executor not initialized.")
            return
        trades = self.executor.get_closed_snapshot(10)
        if not trades:
            await update.message.reply_text("📭 No trades yet.")
            return
        lines = [f"📜 <b>Last {len(trades)} Trades</b>\n"]
        for t in trades:
            emoji = '✅' if t['pnl_pusd'] > 0 else '❌'
            lines.append(
                f"{emoji} {t['coin']} {t['direction']} — "
                f"{t['pnl_pct']:+.1f}% ({t['pnl_pusd']:+.2f} pUSD) [{t['strategy']}]"
            )
        await update.message.reply_html('\n'.join(lines))

    async def cmd_pause(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self._paused = True
        await update.message.reply_text("⏸ Bot PAUSED. No new trades will be made. /resume to continue.")

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self._paused = False
        await update.message.reply_text("▶️ Bot RESUMED. Now scanning for trades.")

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self.cmd_start(update, ctx)

    async def cmd_tier(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Show tier picker. Lets user override balance-based tier selection."""
        if not self.risk_mgr:
            await update.message.reply_text("Risk manager not available.")
            return
        rm = self.risk_mgr
        current = rm.current_tier
        manual = rm.get_manual_tier()
        lock_line = (
            f"🔒 <b>Locked to {manual}</b> (overriding balance)"
            if manual else f"🤖 Auto (picked by balance)"
        )
        buttons = self._build_tier_buttons()
        await update.message.reply_html(
            f"<b>🎚️ Select trading tier:</b>\n"
            f"Balance: {rm.balance:.2f} pUSD\n"
            f"Current: {current.emoji} {current.name}\n"
            f"Mode: {lock_line}\n\n"
            f"<i>Pick a tier to lock it regardless of balance, or AUTO to let the bot decide.</i>",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def tier_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Handle tier button press."""
        query = update.callback_query
        await query.answer()
        if not self.risk_mgr:
            await query.edit_message_text("Risk manager not available.")
            return
        data = query.data
        if not data.startswith('tier:'):
            return
        name = data.split(':', 1)[1]
        ok, msg = self.risk_mgr.set_manual_tier(name)
        tier = self.risk_mgr.current_tier
        manual = self.risk_mgr.get_manual_tier()
        lock_line = (
            f"🔒 <b>Locked to {manual}</b> (overriding balance)"
            if manual else f"🤖 Auto (picked by balance)"
        )
        buttons = self._build_tier_buttons()
        try:
            await query.edit_message_text(
                text=(
                    f"<b>🎚️ Select trading tier:</b>\n"
                    f"Balance: {self.risk_mgr.balance:.2f} pUSD\n"
                    f"Current: {tier.emoji} {tier.name}\n"
                    f"Mode: {lock_line}\n\n"
                    f"{'✅' if ok else '❌'} {msg}\n\n"
                    f"<i>Tap another tier to change, or AUTO for balance-based.</i>"
                ),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception:
            # Ignore "message is not modified" if user taps same button
            pass

    def _build_tier_buttons(self):
        """Tier picker keyboard. 2 columns, tier + AUTO."""
        current_name = self.risk_mgr.current_tier.name if self.risk_mgr else ''
        manual = self.risk_mgr.get_manual_tier() if self.risk_mgr else None

        tier_defs = [
            ('SURVIVAL', '🛡️'),
            ('SEED', '🌱'),
            ('COMFORT', '⚖️'),
            ('AGGRESSIVE', '🔥'),
            ('FULL SEND', '🚀'),
        ]
        rows = []
        row = []
        for name, emoji in tier_defs:
            # Lock icon shows which tier is manually locked
            is_locked = manual == name
            is_active = current_name == name
            if is_locked:
                mark = '🔒'
            elif is_active:
                mark = '●'
            else:
                mark = '○'
            row.append(InlineKeyboardButton(
                f"{mark} {emoji} {name}",
                callback_data=f"tier:{name}",
            ))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        # AUTO button on its own row
        auto_mark = '●' if manual is None else '○'
        rows.append([InlineKeyboardButton(
            f"{auto_mark} 🤖 AUTO (by balance)",
            callback_data="tier:AUTO",
        )])
        return rows

    async def coin_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Handle coin toggle button press."""
        query = update.callback_query
        await query.answer()
        data = query.data
        if not data.startswith('coin:'):
            return
        coin = data.split(':', 1)[1].upper()
        Config.toggle_coin(coin)
        buttons = self._build_coin_buttons()
        await query.edit_message_text(
            text=(
                "<b>🪙 Select coins to trade:</b>\n"
                "Tap a coin to toggle ON/OFF\n"
                f"<i>Currently enabled: {', '.join(Config.ENABLED_COINS)}</i>"
            ),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    def _build_coin_buttons(self):
        rows = []
        row = []
        for coin in Config.ALL_SUPPORTED_COINS:
            enabled = coin in Config.ENABLED_COINS
            mark = '✅' if enabled else '❌'
            name = Config.COIN_DISPLAY_NAMES.get(coin, coin)
            row.append(InlineKeyboardButton(
                f"{mark} {coin} ({name})",
                callback_data=f"coin:{coin}"
            ))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return rows

    # ─────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────

    def run_in_thread(self):
        """Start Telegram bot in a background thread (non-blocking)."""
        if not self.available():
            print(f"[TG] ❌ Telegram unavailable — TOKEN not set or library missing", flush=True)
            return None
        thread = threading.Thread(target=self._run_blocking, daemon=True)
        thread.start()
        print(f"[TG] ✅ Telegram bot thread started", flush=True)
        return thread

    def _run_blocking(self):
        """Run telegram bot in its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("coins", self.cmd_coins))
        self.app.add_handler(CommandHandler("tier", self.cmd_tier))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("recent", self.cmd_recent))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CallbackQueryHandler(self.coin_callback, pattern=r'^coin:'))
        self.app.add_handler(CallbackQueryHandler(self.tier_callback, pattern=r'^tier:'))

        try:
            loop.run_until_complete(self.app.run_polling(close_loop=False, stop_signals=None))
        except Exception as e:
            print(f"[TG] ❌ Telegram polling error: {e}", flush=True)
