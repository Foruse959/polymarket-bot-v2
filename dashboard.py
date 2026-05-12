#!/usr/bin/env python3
"""
5MIN_TRADE v2.2 Beast Mode — Dashboard + Autonomous Bot

Features:
- Live HTML dashboard on http://localhost:8080 with ALL logs
- Comprehensive logging: every scan, decision, error, balance check
- Real-time balance monitoring (on-chain pUSD reads)
- Telegram bot integration (/coins, /status, /positions, /recent)
- Autonomous executor (entry + TP/SL + auto-exit)
- Indicator-based strategies for 70%+ win rate
- Multi-strategy ensemble voting with conviction tiers
- Runtime coin toggle (BTC/ETH/SOL/XRP) via Telegram

Usage:
    python dashboard.py --paper       # Paper mode (simulated)
    python dashboard.py --live        # Live mode (real pUSD)
"""

import asyncio
import json
import os
import sys
import time
import threading
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from data.gamma_client import GammaClient
from data.clob_client import ClobClient, ClobAuthError
from data.price_feed import get_price_feed
from trading.v2_risk_manager import V2RiskManager
from trading.signal_ranker import SignalRanker
from trading.autonomous_executor import AutonomousExecutor
from bot.telegram_ui import TelegramUI


# ═══════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════
STATE = {
    'started_at': None,
    'version': Config.VERSION,
    'version_name': Config.VERSION_NAME,
    'mode': Config.TRADING_MODE,
    'collateral': 'pUSD',
    'scan_round': 0,
    'uptime_seconds': 0,
    'enabled_coins': list(Config.ENABLED_COINS),
    'wallet_address': '',
    'onchain_balance': None,
    # Markets
    'markets_found': 0,
    'active_markets': [],
    # Signals
    'total_signals': 0,
    'last_signals': [],
    # Trades
    'total_trades': 0,
    'open_positions': [],
    'closed_trades': [],
    # PnL
    'balance': Config.STARTING_BALANCE,
    'starting_balance': Config.STARTING_BALANCE,
    'total_pnl': 0.0,
    'daily_pnl': 0.0,
    'equity_curve': [Config.STARTING_BALANCE],
    # Risk
    'risk': {
        'halted': False, 'reason': '',
        'drawdown_pct': 0, 'peak_balance': Config.STARTING_BALANCE,
        'consecutive_wins': 0, 'consecutive_losses': 0,
        'wins': 0, 'losses': 0, 'win_rate': 0,
    },
    'strategy_stats': {},
    'logs': [],
    'errors': [],
    'last_scan_at': None,
}

# ═══════════════════════════════════════════════════════════════════
# LOGGING — The user wants EVERYTHING visible
# ═══════════════════════════════════════════════════════════════════
LOG_LEVELS = {
    'DEBUG': '\033[90m',   # Gray
    'INFO': '\033[36m',    # Cyan
    'INIT': '\033[35m',    # Magenta
    'SCAN': '\033[34m',    # Blue
    'SIGNAL': '\033[33m',  # Yellow
    'TRADE': '\033[32m',   # Green
    'PAPER': '\033[92m',   # Light green
    'RISK': '\033[91m',    # Light red
    'WARN': '\033[93m',    # Light yellow
    'ERROR': '\033[31m',   # Red
    'FATAL': '\033[41m',   # Red background
    'RESET': '\033[0m',
}


def add_log(level: str, msg: str):
    """Global logger — prints to stdout, writes to file, pushes to dashboard."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = {'ts': ts, 'level': level, 'msg': msg}
    STATE['logs'].append(entry)
    if len(STATE['logs']) > 2000:
        STATE['logs'] = STATE['logs'][-2000:]

    # Track errors separately
    if level in ('ERROR', 'FATAL'):
        STATE['errors'].append(entry)
        if len(STATE['errors']) > 100:
            STATE['errors'] = STATE['errors'][-100:]

    # Colored console output
    color = LOG_LEVELS.get(level, '')
    reset = LOG_LEVELS['RESET']
    print(f"{color}[{ts}] [{level:6}] {msg}{reset}", flush=True)

    # File log
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/beast_trading.log", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD HTML (Beast Mode)
# ═══════════════════════════════════════════════════════════════════
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>5MIN_TRADE v2.2 Beast Mode — Live Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace; background: #0a0e17; color: #e0e6ed; min-height: 100vh; font-size: 13px; }
.header { background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%); border-bottom: 2px solid #30363d; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; }
.header h1 { font-size: 16px; color: #58a6ff; font-weight: 700; }
.header .sub { color: #8b949e; font-size: 11px; margin-top: 2px; }
.header .status { display: flex; gap: 10px; align-items: center; }
.badge { padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.badge-live { background: #da363322; color: #f85149; border: 1px solid #f85149; }
.badge-paper { background: #d2992222; color: #d29922; border: 1px solid #d29922; }
.badge-pusd { background: #3fb95022; color: #3fb950; border: 1px solid #3fb950; }
.badge-ok { background: #2ea04333; color: #3fb950; }
.badge-err { background: #da363333; color: #f85149; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; padding: 14px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }
.card h3 { color: #8b949e; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; display:flex; justify-content: space-between; align-items: center; }
.stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #21262d; font-size: 12px; }
.stat-row:last-child { border: none; }
.stat-label { color: #8b949e; }
.stat-value { font-weight: 600; }
.stat-value.green { color: #3fb950; }
.stat-value.red { color: #f85149; }
.stat-value.blue { color: #58a6ff; }
.stat-value.gold { color: #d29922; }
.big-number { font-size: 24px; font-weight: 700; margin: 4px 0; }
.log-container { max-height: 380px; overflow-y: auto; font-size: 10.5px; line-height: 1.55; padding: 4px; background: #0d1117; border-radius: 4px; }
.log-container::-webkit-scrollbar { width: 6px; }
.log-container::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
.log-entry { padding: 1px 6px; border-left: 3px solid transparent; margin: 1px 0; }
.log-entry.INFO { border-color: #58a6ff; }
.log-entry.INIT { border-color: #b392f0; }
.log-entry.SCAN { border-color: #58a6ff; }
.log-entry.SIGNAL { border-color: #d29922; }
.log-entry.PAPER, .log-entry.TRADE { border-color: #3fb950; background: #3fb95011; }
.log-entry.RISK { border-color: #f85149; background: #f8514911; }
.log-entry.WARN { border-color: #f0883e; }
.log-entry.ERROR, .log-entry.FATAL { border-color: #f85149; background: #da363322; color: #f85149; font-weight: 600; }
.log-entry.DEBUG { border-color: #484f58; color: #6e7681; }
.log-ts { color: #484f58; }
.log-level { font-weight: 700; width: 55px; display: inline-block; }
.signal-card { background: #1c2128; border: 1px solid #30363d; border-radius: 4px; padding: 8px; margin: 4px 0; font-size: 11px; }
.signal-header { display: flex; justify-content: space-between; align-items: center; }
.signal-coin { font-weight: 700; color: #58a6ff; }
.signal-dir { padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 700; }
.signal-dir.UP { background: #3fb95022; color: #3fb950; }
.signal-dir.DOWN { background: #f8514922; color: #f85149; }
.signal-conf { font-size: 18px; font-weight: 700; }
.signal-meta { font-size: 10px; color: #8b949e; margin-top: 4px; }
.chart-container { width: 100%; height: 110px; }
.chart-svg { width: 100%; height: 100%; }
.strategy-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 11px; }
.strategy-name { flex: 1; }
.strategy-count { color: #58a6ff; font-weight: 700; }
.market-row { font-size: 10.5px; padding: 3px 0; display: flex; gap: 8px; border-bottom: 1px dashed #21262d; }
.market-coin { color: #58a6ff; font-weight: 700; width: 38px; }
.market-tf { color: #8b949e; width: 26px; }
.market-time { color: #d29922; width: 42px; }
.position-table { width: 100%; font-size: 11px; border-collapse: collapse; }
.position-table th { text-align: left; padding: 6px 4px; border-bottom: 1px solid #30363d; color: #8b949e; font-weight: 600; font-size: 10px; text-transform: uppercase; }
.position-table td { padding: 5px 4px; border-bottom: 1px dashed #21262d; font-size: 11px; }
.position-table tr:hover { background: #1c2128; }
.coin-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.coin-chip { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background: #21262d; color: #8b949e; border: 1px solid #30363d; }
.coin-chip.active { background: #58a6ff33; color: #58a6ff; border-color: #58a6ff; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; animation: pulse 1.8s infinite; display: inline-block; }
.live-dot.stopped { background: #f85149; animation: none; }
.footer { text-align: center; padding: 10px; color: #484f58; font-size: 10px; border-top: 1px solid #21262d; }
.error-banner { background: #da363322; border: 1px solid #f85149; padding: 8px 12px; margin: 0 14px 14px; border-radius: 4px; color: #f85149; font-size: 11px; display: none; }
.error-banner.show { display: block; }
.wallet { font-family: monospace; font-size: 10px; color: #8b949e; }
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>⚡ 5MIN_TRADE v2.2 — Beast Mode</h1>
        <div class="sub">Polymarket V2 | pUSD Collateral | Autonomous Trading Bot</div>
    </div>
    <div class="status">
        <span class="live-dot" id="live-dot"></span>
        <span class="badge badge-paper" id="mode-badge">PAPER</span>
        <span class="badge badge-pusd">pUSD</span>
        <span id="uptime" style="color:#8b949e;font-size:11px;">00:00:00</span>
    </div>
</div>

<div class="error-banner" id="error-banner"></div>

<div class="grid">
    <!-- Balance / PnL -->
    <div class="card">
        <h3>💰 Balance & PnL <span class="badge badge-pusd" id="onchain-indicator" style="display:none">On-chain</span></h3>
        <div class="big-number" id="balance">100.00 pUSD</div>
        <div class="stat-row"><span class="stat-label">Wallet</span><span class="stat-value wallet" id="wallet-addr">—</span></div>
        <div class="stat-row"><span class="stat-label">Total PnL</span><span class="stat-value" id="total-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Daily PnL</span><span class="stat-value" id="daily-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Return</span><span class="stat-value" id="return-pct">0.0%</span></div>
        <div class="chart-container"><svg class="chart-svg" id="equity-chart"></svg></div>
    </div>

    <!-- Risk -->
    <div class="card">
        <h3>🛡️ Risk Manager</h3>
        <div class="stat-row"><span class="stat-label">Win Rate</span><span class="stat-value green" id="win-rate">0%</span></div>
        <div class="stat-row"><span class="stat-label">W / L</span><span class="stat-value" id="win-loss">0 / 0</span></div>
        <div class="stat-row"><span class="stat-label">Streak</span><span class="stat-value" id="streak">—</span></div>
        <div class="stat-row"><span class="stat-label">Drawdown</span><span class="stat-value red" id="drawdown">0.0%</span></div>
        <div class="stat-row"><span class="stat-label">Kelly Fraction</span><span class="stat-value blue">25%</span></div>
        <div class="stat-row"><span class="stat-label">Status</span><span class="stat-value green" id="risk-status">Active</span></div>
        <div class="stat-row"><span class="stat-label">Open positions</span><span class="stat-value blue" id="open-count">0</span></div>
    </div>

    <!-- Coins -->
    <div class="card">
        <h3>🪙 Enabled Coins <span style="color:#484f58;font-size:10px;">(edit via Telegram /coins)</span></h3>
        <div class="coin-chips" id="coin-chips"></div>
        <div style="margin-top:12px;font-size:10.5px;color:#8b949e;">
            Active timeframes: <span id="tfs">5,15</span>min<br>
            Strategies: <span id="strat-count">7</span> active<br>
            Min confidence: <span id="min-conf">55</span>%
        </div>
    </div>

    <!-- Signals -->
    <div class="card">
        <h3>🎯 Latest Signals <span style="color:#484f58;">(<span id="signal-count">0</span>)</span></h3>
        <div id="signals-container"></div>
    </div>

    <!-- Strategy Agreement -->
    <div class="card">
        <h3>📊 Strategy Activity</h3>
        <div id="strategy-container"></div>
    </div>

    <!-- Active Markets -->
    <div class="card">
        <h3>🌐 Active Markets <span style="color:#484f58;">(<span id="market-count">0</span>)</span></h3>
        <div id="markets-container" style="max-height:300px;overflow-y:auto;"></div>
    </div>

    <!-- OPEN POSITIONS -->
    <div class="card" style="grid-column: 1 / -1;">
        <h3>💼 Open Positions <span style="color:#484f58;">(live TP/SL tracking)</span></h3>
        <div id="positions-wrap">
            <table class="position-table" id="positions-table">
                <thead><tr>
                    <th>Coin</th><th>Dir</th><th>Strategy</th><th>Conf</th><th>Size</th>
                    <th>Entry</th><th>Current</th><th>PnL %</th><th>PnL pUSD</th>
                    <th>TP</th><th>SL</th><th>Age</th>
                </tr></thead>
                <tbody id="positions-body"><tr><td colspan="12" style="color:#484f58;padding:14px;text-align:center;">No open positions</td></tr></tbody>
            </table>
        </div>
    </div>

    <!-- Recent Closed -->
    <div class="card" style="grid-column: 1 / -1;">
        <h3>📜 Recent Closed Trades <span style="color:#484f58;">(last 15)</span></h3>
        <table class="position-table" id="closed-table">
            <thead><tr>
                <th>Coin</th><th>Dir</th><th>Strategy</th><th>Entry</th><th>Exit</th>
                <th>PnL %</th><th>PnL pUSD</th><th>Status</th>
            </tr></thead>
            <tbody id="closed-body"><tr><td colspan="8" style="color:#484f58;padding:14px;text-align:center;">No closed trades yet</td></tr></tbody>
        </table>
    </div>

    <!-- Live Log - FULL -->
    <div class="card" style="grid-column: 1 / -1;">
        <h3>📋 Full Live Log <span style="color:#484f58;">(last 300 — everything shown)</span></h3>
        <div class="log-container" id="log-container" style="max-height:480px;"></div>
    </div>
</div>

<div class="footer">
    5min_trade v2.2.0 (Beast Mode) | Indicator Fusion + Microstructure + Momentum | Scan #<span id="scan-round">0</span> | Last scan: <span id="last-scan">—</span>
</div>

<script>
let startTime = Date.now();
function updateUptime() {
    const secs = Math.floor((Date.now() - startTime) / 1000);
    const h = String(Math.floor(secs / 3600)).padStart(2, '0');
    const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    document.getElementById('uptime').textContent = `${h}:${m}:${s}`;
}
setInterval(updateUptime, 1000);

function fetchState() {
    fetch('/api/state').then(r => r.json()).then(state => {
        // Balance
        document.getElementById('balance').textContent = state.balance.toFixed(2) + ' pUSD';
        if (state.onchain_balance !== null && state.onchain_balance !== undefined) {
            document.getElementById('onchain-indicator').style.display = 'inline-block';
        }
        document.getElementById('wallet-addr').textContent = state.wallet_address
            ? state.wallet_address.slice(0,8) + '...' + state.wallet_address.slice(-6)
            : 'not set';

        const pnl = state.total_pnl;
        const pnlEl = document.getElementById('total-pnl');
        pnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' pUSD';
        pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'green' : 'red');

        const daily = state.daily_pnl;
        const dailyEl = document.getElementById('daily-pnl');
        dailyEl.textContent = (daily >= 0 ? '+' : '') + daily.toFixed(2);
        dailyEl.className = 'stat-value ' + (daily >= 0 ? 'green' : 'red');

        const ret = ((state.balance - state.starting_balance) / state.starting_balance * 100);
        const retEl = document.getElementById('return-pct');
        retEl.textContent = (ret >= 0 ? '+' : '') + ret.toFixed(1) + '%';
        retEl.className = 'stat-value ' + (ret >= 0 ? 'green' : 'red');

        // Risk
        const r = state.risk || {};
        document.getElementById('win-rate').textContent = (r.win_rate || 0).toFixed(0) + '%';
        document.getElementById('win-loss').textContent = `${r.wins || 0} / ${r.losses || 0}`;
        const streak = r.consecutive_wins > 0 ? `W${r.consecutive_wins} 🔥`
                     : r.consecutive_losses > 0 ? `L${r.consecutive_losses} ❄️` : '—';
        document.getElementById('streak').textContent = streak;
        document.getElementById('drawdown').textContent = (r.drawdown_pct || 0).toFixed(1) + '%';
        document.getElementById('risk-status').textContent = r.halted ? '🚨 HALTED: ' + (r.reason || '') : '✅ Active';
        document.getElementById('risk-status').className = 'stat-value ' + (r.halted ? 'red' : 'green');
        document.getElementById('open-count').textContent = (state.open_positions || []).length;

        // Coins
        const chips = document.getElementById('coin-chips');
        const supported = ['BTC', 'ETH', 'SOL', 'XRP'];
        chips.innerHTML = supported.map(c => {
            const active = (state.enabled_coins || []).includes(c);
            return `<span class="coin-chip ${active ? 'active' : ''}">${active ? '✓' : '○'} ${c}</span>`;
        }).join('');

        // Signals
        document.getElementById('signal-count').textContent = state.total_signals || 0;
        const sigContainer = document.getElementById('signals-container');
        const sigs = state.last_signals || [];
        sigContainer.innerHTML = sigs.length ? sigs.slice(0, 6).map(s => {
            const stars = '⭐'.repeat(Math.min(s.agreement || 1, 4));
            const tier = s.tier || '';
            return `<div class="signal-card">
                <div class="signal-header">
                    <span><span class="signal-coin">${s.coin}</span>
                    <span class="signal-dir ${s.dir}">${s.dir}</span>
                    <span style="color:#d29922;font-size:10px;">${tier}</span></span>
                    <span class="signal-conf">${(s.conf*100).toFixed(0)}%</span>
                </div>
                <div class="signal-meta">${stars} ${s.strategy} | Limit: ${s.limit ? s.limit.toFixed(3) : 'MKT'}</div>
            </div>`;
        }).join('') : '<div style="color:#484f58;text-align:center;padding:20px;">Waiting for signals...</div>';

        // Markets
        document.getElementById('market-count').textContent = state.markets_found || 0;
        const mktContainer = document.getElementById('markets-container');
        const mkts = state.active_markets || [];
        mktContainer.innerHTML = mkts.length ? mkts.map(m => `
            <div class="market-row">
                <span class="market-coin">${m.coin}</span>
                <span class="market-tf">${m.tf}m</span>
                <span class="market-time">${m.secs}s</span>
                <span style="color:#8b949e;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${m.q}</span>
            </div>
        `).join('') : '<div style="color:#484f58;text-align:center;padding:20px;">Scanning...</div>';

        // Strategy stats
        const stratContainer = document.getElementById('strategy-container');
        const strats = state.strategy_stats || {};
        stratContainer.innerHTML = Object.keys(strats).length
            ? Object.entries(strats).sort((a,b)=>b[1]-a[1]).map(([n, c]) =>
                `<div class="strategy-row"><span class="strategy-name">${n}</span><span class="strategy-count">${c}</span></div>`
            ).join('')
            : '<div style="color:#484f58;text-align:center;padding:20px;">Waiting...</div>';

        // Open positions table
        const posBody = document.getElementById('positions-body');
        const positions = state.open_positions || [];
        if (positions.length === 0) {
            posBody.innerHTML = '<tr><td colspan="12" style="color:#484f58;padding:14px;text-align:center;">No open positions</td></tr>';
        } else {
            posBody.innerHTML = positions.map(p => {
                const pnlClass = p.pnl_pct >= 0 ? 'green' : 'red';
                const age = p.elapsed_sec < 60 ? `${p.elapsed_sec}s` : `${Math.floor(p.elapsed_sec/60)}m`;
                return `<tr>
                    <td><span style="color:#58a6ff;font-weight:700;">${p.coin}</span></td>
                    <td><span class="signal-dir ${p.direction}">${p.direction}</span></td>
                    <td style="color:#8b949e;">${p.strategy.substring(0,14)}</td>
                    <td>${(p.confidence*100).toFixed(0)}%</td>
                    <td>${p.size_pusd.toFixed(2)}</td>
                    <td>${p.entry_price.toFixed(3)}</td>
                    <td>${p.current_price.toFixed(3)}</td>
                    <td class="${pnlClass}" style="font-weight:700;">${p.pnl_pct >= 0 ? '+' : ''}${p.pnl_pct.toFixed(1)}%</td>
                    <td class="${pnlClass}" style="font-weight:700;">${p.pnl_pusd >= 0 ? '+' : ''}${p.pnl_pusd.toFixed(2)}</td>
                    <td style="color:#3fb950;">+${p.tp_pct.toFixed(0)}%</td>
                    <td style="color:#f85149;">${p.sl_pct.toFixed(0)}%</td>
                    <td style="color:#8b949e;">${age}</td>
                </tr>`;
            }).join('');
        }

        // Closed trades table
        const closedBody = document.getElementById('closed-body');
        const closed = state.closed_trades || [];
        if (closed.length === 0) {
            closedBody.innerHTML = '<tr><td colspan="8" style="color:#484f58;padding:14px;text-align:center;">No closed trades yet</td></tr>';
        } else {
            closedBody.innerHTML = closed.slice(0, 15).map(t => {
                const pnlClass = t.pnl_pusd >= 0 ? 'green' : 'red';
                const emoji = t.pnl_pusd >= 0 ? '✅' : '❌';
                return `<tr>
                    <td><span style="color:#58a6ff;font-weight:700;">${t.coin}</span></td>
                    <td><span class="signal-dir ${t.direction}">${t.direction}</span></td>
                    <td style="color:#8b949e;">${t.strategy.substring(0,16)}</td>
                    <td>${t.entry_price.toFixed(3)}</td>
                    <td>${t.current_price.toFixed(3)}</td>
                    <td class="${pnlClass}" style="font-weight:700;">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(1)}%</td>
                    <td class="${pnlClass}" style="font-weight:700;">${emoji} ${t.pnl_pusd >= 0 ? '+' : ''}${t.pnl_pusd.toFixed(2)}</td>
                    <td style="color:#8b949e;font-size:10px;">${t.status}</td>
                </tr>`;
            }).join('');
        }

        // Scan round & last scan
        document.getElementById('scan-round').textContent = state.scan_round || 0;
        document.getElementById('last-scan').textContent = state.last_scan_at || '—';

        // Mode badge
        const mb = document.getElementById('mode-badge');
        mb.textContent = (state.mode || 'PAPER').toUpperCase();
        mb.className = 'badge ' + (state.mode === 'live' ? 'badge-live' : 'badge-paper');

        // Equity chart
        drawEquityChart(state.equity_curve || []);

        // Logs
        const logContainer = document.getElementById('log-container');
        const logs = (state.logs || []).slice(-300);
        const wasAtBottom = (logContainer.scrollTop + logContainer.clientHeight) >= (logContainer.scrollHeight - 20);
        logContainer.innerHTML = logs.map(l =>
            `<div class="log-entry ${l.level}"><span class="log-ts">${l.ts}</span> <span class="log-level">${l.level}</span> ${escapeHtml(l.msg)}</div>`
        ).join('');
        if (wasAtBottom) logContainer.scrollTop = logContainer.scrollHeight;

        // Show recent error banner if any
        const errors = (state.errors || []).slice(-1);
        const banner = document.getElementById('error-banner');
        if (errors.length > 0) {
            banner.textContent = '⚠ ' + errors[0].msg;
            banner.classList.add('show');
        } else {
            banner.classList.remove('show');
        }
    }).catch(err => {
        document.getElementById('live-dot').classList.add('stopped');
    });
}

function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function drawEquityChart(curve) {
    if (!curve || curve.length < 2) return;
    const svg = document.getElementById('equity-chart');
    const w = svg.clientWidth || 300;
    const h = svg.clientHeight || 110;
    const min = Math.min(...curve) * 0.98;
    const max = Math.max(...curve) * 1.02;
    const range = max - min || 1;
    const points = curve.map((v, i) => {
        const x = (i / (curve.length - 1)) * w;
        const y = h - ((v - min) / range) * h;
        return `${x},${y}`;
    }).join(' ');
    const last = curve[curve.length - 1];
    const color = last >= curve[0] ? '#3fb950' : '#f85149';
    svg.innerHTML = `
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" opacity="0.9"/>
        <polyline points="0,${h} ${points} ${w},${h}" fill="${color}" opacity="0.12"/>
    `;
}

// Refresh every 1.5 seconds for live feel
setInterval(fetchState, 1500);
fetchState();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════════════════════════════════════
class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/dashboard'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif path == '/api/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(STATE, default=str).encode())
        elif path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(STATE['logs'][-300:]).encode())
        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard_server(port=8080):
    for attempt_port in [port, port + 1, port + 2, 8181, 8282]:
        try:
            server = HTTPServer(('0.0.0.0', attempt_port), DashboardHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            return server, attempt_port
        except OSError:
            continue
    return None, None


# ═══════════════════════════════════════════════════════════════════
# BOT LOOP
# ═══════════════════════════════════════════════════════════════════
async def bot_loop():
    # Parse args
    if '--live' in sys.argv:
        Config.TRADING_MODE = 'live'
    elif '--paper' in sys.argv:
        Config.TRADING_MODE = 'paper'

    STATE['mode'] = Config.TRADING_MODE
    STATE['started_at'] = datetime.now(timezone.utc).isoformat()
    STATE['enabled_coins'] = list(Config.ENABLED_COINS)

    Config.print_status()

    # Start dashboard
    port = int(os.getenv('DASHBOARD_PORT', '8080'))
    server, actual_port = start_dashboard_server(port)
    if server:
        add_log("INIT", f"🌐 Dashboard running on http://localhost:{actual_port}")
    else:
        add_log("WARN", f"⚠️  Could not start dashboard (ports all busy). Bot will still run.")

    add_log("INIT", f"=" * 60)
    add_log("INIT", f"⚡ 5MIN_TRADE v{Config.VERSION} ({Config.VERSION_NAME}) starting")
    add_log("INIT", f"Mode: {Config.TRADING_MODE.upper()} | Collateral: pUSD")
    add_log("INIT", f"Coins: {', '.join(Config.ENABLED_COINS)} | TF: {Config.ENABLED_TIMEFRAMES}")
    add_log("INIT", f"Balance: {Config.format_balance(Config.STARTING_BALANCE)}")
    add_log("INIT", f"=" * 60)

    # Init components
    gamma = GammaClient()
    clob = ClobClient()
    risk_mgr = V2RiskManager(Config.STARTING_BALANCE)
    signal_ranker = SignalRanker(log_callback=add_log)
    executor = AutonomousExecutor(risk_mgr, clob, log_callback=add_log)
    price_feed = get_price_feed()

    add_log("INIT", f"✅ Strategies loaded: {signal_ranker.get_strategy_names()}")
    add_log("INIT", f"✅ Risk manager: Kelly={Config.KELLY_FRACTION} | MaxDD={Config.DRAWDOWN_HALT_PCT}%")
    add_log("INIT", f"✅ Autonomous executor ready (entry + TP/SL + auto-exit)")

    # Wallet info
    wallet = Config.derive_wallet_address()
    funder = Config.get_funder_address()
    STATE['wallet_address'] = wallet or ''
    if wallet:
        add_log("INIT", f"💼 Wallet: {wallet[:8]}...{wallet[-6:]}")
    if funder and funder != wallet:
        add_log("INIT", f"💰 Funder: {funder[:8]}...{funder[-6:]}")

    # CLOB init for live
    if Config.TRADING_MODE == 'live':
        if not Config.is_live_ready():
            add_log("ERROR", "❌ LIVE mode requested but POLY_PRIVATE_KEY not set in .env")
            add_log("ERROR", "💡 Set POLY_PRIVATE_KEY in .env or run with --paper")
            return

        add_log("INIT", "🔌 Connecting to CLOB V2...")
        try:
            pk = Config.POLY_PRIVATE_KEY.strip()
            client = clob.init_py_clob_client(pk, funder, Config.POLY_SIGNATURE_TYPE)
            if client:
                add_log("INIT", "✅ CLOB V2 connected and ready")
            else:
                add_log("WARN", "⚠️  CLOB init returned None — check auth")
        except ClobAuthError as e:
            add_log("FATAL", f"CLOB AUTH FAILED — see instructions below")
            for line in str(e).split('\n'):
                add_log("ERROR", line)
            add_log("WARN", "Bot will run in READ-ONLY mode (no trades). Fix auth to enable trading.")
        except Exception as e:
            add_log("ERROR", f"❌ CLOB init failed: {e}")
            add_log("ERROR", traceback.format_exc().replace('\n', ' | '))

    # Initial balance check
    if wallet:
        add_log("INIT", "🔍 Checking on-chain pUSD balance...")
        onchain = clob.get_pusd_balance_onchain(wallet)
        if onchain is not None:
            STATE['onchain_balance'] = onchain
            add_log("INIT", f"💰 On-chain pUSD balance: {onchain:.2f} pUSD")
            if onchain < Config.POLYMARKET_MIN_ORDER_SIZE and Config.TRADING_MODE == 'live':
                add_log("WARN", f"⚠️  Low balance: {onchain:.2f} pUSD < min {Config.POLYMARKET_MIN_ORDER_SIZE:.2f}")
                add_log("WARN", f"💡 Deposit USDC on polymarket.com (auto-wraps to pUSD)")
        else:
            add_log("WARN", "⚠️  Could not read on-chain balance (RPC issue). Using starting balance.")

    # Telegram UI
    tg = TelegramUI(state_provider=lambda: STATE, executor=executor)
    if tg.available():
        tg.run_in_thread()
        add_log("INIT", f"📱 Telegram bot started (commands: /status /coins /positions /recent)")
    else:
        add_log("WARN", "📱 Telegram disabled (TELEGRAM_BOT_TOKEN not set or library missing)")

    add_log("INIT", "")
    add_log("INIT", "🚀 BEAST MODE READY — entering scan loop")
    add_log("INIT", "")

    start_time = time.time()
    scan_round = 0
    last_balance_check = 0

    while True:
        try:
            scan_round += 1
            STATE['scan_round'] = scan_round
            STATE['uptime_seconds'] = int(time.time() - start_time)
            STATE['last_scan_at'] = datetime.now(timezone.utc).strftime("%H:%M:%S")
            STATE['enabled_coins'] = list(Config.ENABLED_COINS)

            add_log("SCAN", f"━━━ Round #{scan_round} | {risk_mgr.get_status_line()} ━━━")

            # Periodic on-chain balance check (every 60s in live mode)
            if Config.TRADING_MODE == 'live' and wallet and (time.time() - last_balance_check > 60):
                onchain = clob.get_pusd_balance_onchain(wallet)
                if onchain is not None:
                    STATE['onchain_balance'] = onchain
                    add_log("INFO", f"💰 On-chain pUSD: {onchain:.2f}")
                last_balance_check = time.time()

            # Pause check (Telegram /pause)
            if tg.is_paused():
                add_log("INFO", "⏸  Bot paused via Telegram. Use /resume to continue.")
                await asyncio.sleep(15)
                continue

            # Risk check
            can_trade, reason = risk_mgr.can_trade()
            STATE['risk'] = {
                'halted': not can_trade,
                'reason': reason if not can_trade else '',
                'drawdown_pct': risk_mgr._drawdown_pct(),
                'peak_balance': risk_mgr.peak_balance,
                'consecutive_wins': risk_mgr.consecutive_wins,
                'consecutive_losses': risk_mgr.consecutive_losses,
                'wins': risk_mgr.wins,
                'losses': risk_mgr.losses,
                'win_rate': (risk_mgr.wins / risk_mgr.total_trades * 100) if risk_mgr.total_trades > 0 else 0,
            }
            STATE['balance'] = risk_mgr.balance
            STATE['total_pnl'] = risk_mgr.total_pnl
            STATE['daily_pnl'] = risk_mgr.daily_pnl

            if not can_trade:
                add_log("RISK", f"⛔ Trading blocked: {reason}")
                await asyncio.sleep(30)
                continue

            # Discover markets
            try:
                markets = gamma.discover_markets()
            except Exception as e:
                add_log("ERROR", f"Market discovery failed: {e}")
                markets = []

            STATE['markets_found'] = len(markets) if markets else 0
            STATE['active_markets'] = [
                {'coin': m['coin'], 'tf': m['timeframe'], 'secs': m['seconds_remaining'],
                 'q': m['question'][:60]}
                for m in (markets or [])[:12]
            ]

            if not markets:
                add_log("SCAN", "📭 No active markets right now. Waiting 10s...")
                await asyncio.sleep(10)
                continue

            add_log("SCAN", f"🌐 Found {len(markets)} active markets "
                           f"({len(set(m['coin'] for m in markets))} coins × {len(set(m['timeframe'] for m in markets))} TFs)")

            # Monitor open positions FIRST (update prices, check TP/SL)
            if executor.open_positions:
                # Get current prices for all open position tokens
                current_prices = {}
                for pos in executor.open_positions.values():
                    price = clob.get_mid_price(pos.token_id)
                    if price is not None:
                        current_prices[pos.token_id] = price
                closed_this_scan = await executor.monitor_positions(current_prices)
                if closed_this_scan:
                    add_log("INFO", f"📊 Closed {len(closed_this_scan)} positions this scan")

            # Update state snapshots
            STATE['open_positions'] = executor.get_positions_snapshot()
            STATE['closed_trades'] = executor.get_closed_snapshot(15)

            # Build context for strategies
            context = {
                'clob': clob,
                'risk_mgr': risk_mgr,
                'price_feed': price_feed,
            }

            # Generate signals (ensemble voting)
            try:
                signals = await signal_ranker.get_ranked_signals(markets, context)
            except Exception as e:
                add_log("ERROR", f"Signal generation error: {e}")
                add_log("ERROR", traceback.format_exc().replace('\n', ' | ')[:300])
                signals = []

            STATE['total_signals'] += len(signals)
            STATE['last_signals'] = [
                {'coin': s.coin, 'dir': s.direction, 'conf': s.confidence,
                 'strategy': s.strategy, 'limit': s.limit_price,
                 'agreement': s.metadata.get('agreement_count', 1),
                 'tier': s.metadata.get('conviction_tier', 'SINGLE')}
                for s in (signals or [])[:8]
            ]

            # Track strategy stats
            strat_counts = STATE.get('strategy_stats', {})
            for s in signals:
                for ss in s.metadata.get('strategies_agreeing', [s.strategy]):
                    strat_counts[ss] = strat_counts.get(ss, 0) + 1
            STATE['strategy_stats'] = strat_counts

            if not signals:
                add_log("SCAN", "🔍 No signals above threshold this scan")
            else:
                add_log("SIGNAL", f"🎯 {len(signals)} trade signals generated (showing top 5):")
                for i, sig in enumerate(signals[:5]):
                    agr = sig.metadata.get('agreement_count', 1)
                    tier = sig.metadata.get('conviction_tier', 'SINGLE')
                    stars = '⭐' * min(agr, 4)
                    limit_str = f"@ {sig.limit_price:.3f}" if sig.limit_price else "@ MKT"
                    add_log("SIGNAL", f"  #{i+1} {stars} [{tier}] {sig.coin} {sig.direction} "
                                     f"{sig.confidence:.0%} {limit_str} | {sig.strategy}")

                # EXECUTE TOP SIGNALS (autonomous)
                executed = 0
                for sig in signals[:5]:  # Top 5 per scan
                    position = await executor.execute_signal(sig)
                    if position:
                        executed += 1
                        STATE['total_trades'] += 1

                add_log("SCAN", f"🤖 Executed {executed}/{min(len(signals), 5)} signals")

            # Equity curve
            STATE['equity_curve'].append(risk_mgr.balance)
            if len(STATE['equity_curve']) > 500:
                STATE['equity_curve'] = STATE['equity_curve'][-500:]

            # Heartbeat
            clob.send_heartbeat()

            await asyncio.sleep(5)

        except Exception as e:
            add_log("ERROR", f"Main loop error: {e}")
            add_log("ERROR", traceback.format_exc().replace('\n', ' | ')[:300])
            await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("⚡ 5MIN_TRADE v2.2 Beast Mode — Dashboard + Autonomous Bot")
    print("=" * 60)
    try:
        asyncio.run(bot_loop())
    except KeyboardInterrupt:
        add_log("SYSTEM", "Bot stopped by user")
        print("\n👋 Goodbye!", flush=True)
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        traceback.print_exc()
