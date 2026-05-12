#!/usr/bin/env python3
"""
5MIN_TRADE v2.1 — Live Trading Dashboard

Modern real-time web dashboard with:
- Live trade log stream (WebSocket)
- Open positions & PnL tracking
- Equity curve chart
- Strategy performance breakdown
- Risk manager status (Kelly, drawdown, streaks)
- Market discovery status
- Signal queue with confidence & agreement

Runs on http://localhost:8080
Uses Server-Sent Events (SSE) for real-time updates — no WebSocket dependency.
"""

import asyncio
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from data.gamma_client import GammaClient
from data.clob_client import ClobClient
from trading.v2_risk_manager import V2RiskManager
from trading.signal_ranker import SignalRanker

# ═══════════════════════════════════════════════════════════════════
# GLOBAL BOT STATE (shared between bot loop and dashboard server)
# ═══════════════════════════════════════════════════════════════════
STATE = {
    'started_at': None,
    'version': Config.VERSION,
    'version_name': Config.VERSION_NAME,
    'mode': Config.TRADING_MODE,
    'collateral': 'pUSD',
    'scan_round': 0,
    'uptime_seconds': 0,
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
        'halted': False,
        'reason': '',
        'drawdown_pct': 0,
        'peak_balance': Config.STARTING_BALANCE,
        'consecutive_wins': 0,
        'consecutive_losses': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0,
    },
    # Strategy stats
    'strategy_stats': {},
    # Logs
    'logs': [],
}

SSE_CLIENTS = []


def add_log(level: str, msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = {'ts': ts, 'level': level, 'msg': msg}
    STATE['logs'].append(entry)
    if len(STATE['logs']) > 1000:
        STATE['logs'] = STATE['logs'][-1000:]
    print(f"[{ts}] [{level:5}] {msg}", flush=True)
    # Push to SSE clients
    push_sse({'type': 'log', 'data': entry})


def push_sse(data):
    """Push event to all connected SSE clients."""
    msg = f"data: {json.dumps(data)}\n\n"
    for client in SSE_CLIENTS[:]:
        try:
            client.wfile.write(msg.encode())
            client.wfile.flush()
        except Exception:
            SSE_CLIENTS.remove(client)


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD HTML
# ═══════════════════════════════════════════════════════════════════
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>5MIN_TRADE v2.1 — Live Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'JetBrains Mono', 'Fira Code', monospace; background: #0a0e17; color: #e0e6ed; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%); border-bottom: 1px solid #30363d; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 18px; color: #58a6ff; }
.header .version { color: #8b949e; font-size: 12px; }
.header .status { display: flex; gap: 12px; align-items: center; }
.badge { padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.badge-live { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
.badge-paper { background: #f0883e22; color: #f0883e; border: 1px solid #f0883e; }
.badge-pusd { background: #3fb95033; color: #3fb950; border: 1px solid #3fb950; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; padding: 16px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.card h3 { color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
.stat-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; }
.stat-row:last-child { border: none; }
.stat-label { color: #8b949e; }
.stat-value { font-weight: 600; }
.stat-value.green { color: #3fb950; }
.stat-value.red { color: #f85149; }
.stat-value.blue { color: #58a6ff; }
.stat-value.gold { color: #d29922; }
.big-number { font-size: 28px; font-weight: 700; margin: 8px 0; }
.pnl-positive { color: #3fb950; }
.pnl-negative { color: #f85149; }
.log-container { max-height: 300px; overflow-y: auto; font-size: 11px; line-height: 1.6; }
.log-entry { padding: 2px 8px; border-left: 3px solid transparent; }
.log-entry.INFO { border-color: #58a6ff; }
.log-entry.SIGNAL { border-color: #d29922; }
.log-entry.PAPER { border-color: #3fb950; }
.log-entry.WARN { border-color: #f0883e; }
.log-entry.ERROR { border-color: #f85149; }
.log-entry.RISK { border-color: #f85149; }
.log-ts { color: #484f58; }
.log-level { font-weight: 600; width: 50px; display: inline-block; }
.signal-card { background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 10px; margin: 6px 0; }
.signal-header { display: flex; justify-content: space-between; align-items: center; }
.signal-coin { font-weight: 700; color: #58a6ff; }
.signal-dir { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.signal-dir.UP { background: #3fb95022; color: #3fb950; }
.signal-dir.DOWN { background: #f8514922; color: #f85149; }
.signal-conf { font-size: 20px; font-weight: 700; }
.signal-meta { font-size: 11px; color: #8b949e; margin-top: 4px; }
.chart-container { width: 100%; height: 120px; position: relative; }
.chart-svg { width: 100%; height: 100%; }
.progress-bar { height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; margin: 4px 0; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.strategy-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.strategy-name { flex: 1; font-size: 12px; }
.strategy-count { color: #58a6ff; font-weight: 600; }
.market-row { font-size: 11px; padding: 4px 0; display: flex; gap: 8px; }
.market-coin { color: #58a6ff; font-weight: 600; width: 36px; }
.market-tf { color: #8b949e; width: 30px; }
.market-time { color: #d29922; width: 50px; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; animation: pulse 2s infinite; display: inline-block; }
.footer { text-align: center; padding: 12px; color: #484f58; font-size: 11px; border-top: 1px solid #21262d; }
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>⚡ 5MIN_TRADE v2.1 — Microstructure Edge</h1>
        <span class="version">Polymarket V2 | pUSD Collateral | CTF Exchange V2</span>
    </div>
    <div class="status">
        <span class="live-dot"></span>
        <span class="badge badge-paper" id="mode-badge">PAPER</span>
        <span class="badge badge-pusd">pUSD</span>
        <span id="uptime" style="color:#8b949e;font-size:11px;">00:00:00</span>
    </div>
</div>

<div class="grid">
    <!-- Balance Card -->
    <div class="card">
        <h3>💰 Balance & PnL</h3>
        <div class="big-number" id="balance">100.00 pUSD</div>
        <div class="stat-row"><span class="stat-label">Total PnL</span><span class="stat-value" id="total-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Daily PnL</span><span class="stat-value" id="daily-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Return</span><span class="stat-value" id="return-pct">0.0%</span></div>
        <div class="chart-container"><svg class="chart-svg" id="equity-chart"></svg></div>
    </div>

    <!-- Risk Card -->
    <div class="card">
        <h3>🛡️ Risk Manager</h3>
        <div class="stat-row"><span class="stat-label">Win Rate</span><span class="stat-value green" id="win-rate">0%</span></div>
        <div class="stat-row"><span class="stat-label">W / L</span><span class="stat-value" id="win-loss">0 / 0</span></div>
        <div class="stat-row"><span class="stat-label">Streak</span><span class="stat-value" id="streak">—</span></div>
        <div class="stat-row"><span class="stat-label">Drawdown</span><span class="stat-value red" id="drawdown">0.0%</span></div>
        <div class="stat-row"><span class="stat-label">Kelly Fraction</span><span class="stat-value blue">25%</span></div>
        <div class="stat-row"><span class="stat-label">Status</span><span class="stat-value green" id="risk-status">Active</span></div>
    </div>

    <!-- Signals Card -->
    <div class="card" style="grid-column: span 1;">
        <h3>🎯 Latest Signals (<span id="signal-count">0</span> total)</h3>
        <div id="signals-container"></div>
    </div>

    <!-- Strategy Performance -->
    <div class="card">
        <h3>📊 Strategy Performance</h3>
        <div id="strategy-container">
            <div class="strategy-row"><span class="strategy-name">microstructure_maker</span><span class="strategy-count">0</span></div>
            <div class="strategy-row"><span class="strategy-name">momentum_breakout</span><span class="strategy-count">0</span></div>
            <div class="strategy-row"><span class="strategy-name">volume_imbalance</span><span class="strategy-count">0</span></div>
            <div class="strategy-row"><span class="strategy-name">mean_reversion</span><span class="strategy-count">0</span></div>
            <div class="strategy-row"><span class="strategy-name">maker_edge</span><span class="strategy-count">0</span></div>
            <div class="strategy-row"><span class="strategy-name">longshot_bias</span><span class="strategy-count">0</span></div>
        </div>
    </div>

    <!-- Active Markets -->
    <div class="card">
        <h3>🌐 Active Markets (<span id="market-count">0</span>)</h3>
        <div id="markets-container"></div>
    </div>

    <!-- Live Log -->
    <div class="card" style="grid-column: 1 / -1;">
        <h3>📋 Live Log (last 100)</h3>
        <div class="log-container" id="log-container"></div>
    </div>
</div>

<div class="footer">
    5min_trade v2.1.0 (Microstructure Edge) | Research: Becker 2026 + 186K Market Backtest | Scan #<span id="scan-round">0</span>
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
    fetch('/api/state')
        .then(r => r.json())
        .then(state => {
            // Balance
            document.getElementById('balance').textContent = state.balance.toFixed(2) + ' pUSD';
            const pnl = state.total_pnl;
            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' pUSD';
            pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'green' : 'red');

            const dailyPnl = state.daily_pnl;
            const dailyEl = document.getElementById('daily-pnl');
            dailyEl.textContent = (dailyPnl >= 0 ? '+' : '') + dailyPnl.toFixed(2);
            dailyEl.className = 'stat-value ' + (dailyPnl >= 0 ? 'green' : 'red');

            const ret = ((state.balance - state.starting_balance) / state.starting_balance * 100);
            const retEl = document.getElementById('return-pct');
            retEl.textContent = (ret >= 0 ? '+' : '') + ret.toFixed(1) + '%';
            retEl.className = 'stat-value ' + (ret >= 0 ? 'green' : 'red');

            // Risk
            const r = state.risk;
            document.getElementById('win-rate').textContent = r.win_rate.toFixed(0) + '%';
            document.getElementById('win-loss').textContent = `${r.wins} / ${r.losses}`;
            const streak = r.consecutive_wins > 0 ? `W${r.consecutive_wins} 🔥` : r.consecutive_losses > 0 ? `L${r.consecutive_losses} ❄️` : '—';
            document.getElementById('streak').textContent = streak;
            document.getElementById('drawdown').textContent = r.drawdown_pct.toFixed(1) + '%';
            document.getElementById('risk-status').textContent = r.halted ? '🚨 HALTED' : '✅ Active';
            document.getElementById('risk-status').className = 'stat-value ' + (r.halted ? 'red' : 'green');

            // Signals
            document.getElementById('signal-count').textContent = state.total_signals;
            const sigContainer = document.getElementById('signals-container');
            sigContainer.innerHTML = state.last_signals.slice(0, 5).map(s => `
                <div class="signal-card">
                    <div class="signal-header">
                        <span><span class="signal-coin">${s.coin}</span> <span class="signal-dir ${s.dir}">${s.dir}</span></span>
                        <span class="signal-conf">${(s.conf*100).toFixed(0)}%</span>
                    </div>
                    <div class="signal-meta">${'⭐'.repeat(Math.min(s.agreement||1, 3))} ${s.strategy} | Limit: ${s.limit ? s.limit.toFixed(3) : 'MKT'}</div>
                </div>
            `).join('');

            // Markets
            document.getElementById('market-count').textContent = state.markets_found;
            const mktContainer = document.getElementById('markets-container');
            mktContainer.innerHTML = state.active_markets.slice(0, 8).map(m => `
                <div class="market-row">
                    <span class="market-coin">${m.coin}</span>
                    <span class="market-tf">${m.tf}m</span>
                    <span class="market-time">${m.secs}s</span>
                    <span style="color:#8b949e;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${m.q}</span>
                </div>
            `).join('');

            // Strategy stats
            const stratContainer = document.getElementById('strategy-container');
            const strats = state.strategy_stats || {};
            stratContainer.innerHTML = Object.entries(strats).map(([name, count]) => `
                <div class="strategy-row"><span class="strategy-name">${name}</span><span class="strategy-count">${count}</span></div>
            `).join('') || '<div style="color:#484f58">Waiting for signals...</div>';

            // Scan round
            document.getElementById('scan-round').textContent = state.scan_round;

            // Mode badge
            const modeBadge = document.getElementById('mode-badge');
            modeBadge.textContent = state.mode.toUpperCase();
            modeBadge.className = 'badge ' + (state.mode === 'live' ? 'badge-live' : 'badge-paper');

            // Equity chart
            drawEquityChart(state.equity_curve);

            // Logs
            const logContainer = document.getElementById('log-container');
            const logs = state.logs.slice(-100);
            logContainer.innerHTML = logs.map(l => `
                <div class="log-entry ${l.level}"><span class="log-ts">${l.ts}</span> <span class="log-level">${l.level}</span> ${l.msg}</div>
            `).join('');
            logContainer.scrollTop = logContainer.scrollHeight;
        })
        .catch(() => {});
}

function drawEquityChart(curve) {
    if (!curve || curve.length < 2) return;
    const svg = document.getElementById('equity-chart');
    const w = svg.clientWidth || 300;
    const h = svg.clientHeight || 120;
    const min = Math.min(...curve) * 0.98;
    const max = Math.max(...curve) * 1.02;
    const range = max - min || 1;
    const points = curve.map((v, i) => {
        const x = (i / (curve.length - 1)) * w;
        const y = h - ((v - min) / range) * h;
        return `${x},${y}`;
    }).join(' ');
    const lastVal = curve[curve.length - 1];
    const color = lastVal >= curve[0] ? '#3fb950' : '#f85149';
    svg.innerHTML = `
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" opacity="0.8"/>
        <polyline points="0,${h} ${points} ${w},${h}" fill="${color}" opacity="0.1"/>
    `;
}

// Poll every 2 seconds
setInterval(fetchState, 2000);
fetchState();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════════════════════════════════════
class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/' or path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())

        elif path == '/api/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(STATE).encode())

        elif path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(STATE['logs'][-200:]).encode())

        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard_server(port=8080):
    """Start dashboard HTTP server in background thread."""
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ═══════════════════════════════════════════════════════════════════
# BOT LOOP
# ═══════════════════════════════════════════════════════════════════
async def bot_loop():
    if '--live' in sys.argv:
        Config.TRADING_MODE = 'live'
    elif '--paper' in sys.argv:
        Config.TRADING_MODE = 'paper'

    STATE['mode'] = Config.TRADING_MODE
    STATE['started_at'] = datetime.now(timezone.utc).isoformat()

    Config.print_status()

    # Start dashboard
    port = int(os.getenv('DASHBOARD_PORT', '8080'))
    start_dashboard_server(port)
    add_log("INIT", f"🌐 Dashboard running on http://localhost:{port}")

    # Initialize
    add_log("INIT", f"Starting 5min_trade v{Config.VERSION} ({Config.VERSION_NAME})")
    gamma = GammaClient()
    clob = ClobClient()
    risk_mgr = V2RiskManager(Config.STARTING_BALANCE)
    signal_ranker = SignalRanker()

    add_log("INIT", f"Strategies: {signal_ranker.get_strategy_names()}")
    add_log("INIT", f"Collateral: pUSD | Exchange: CTF V2 | Kelly={Config.KELLY_FRACTION}")

    # CLOB init for live
    if Config.TRADING_MODE == 'live' and Config.is_live_ready():
        add_log("INIT", "Connecting to CLOB V2...")
        try:
            pk = Config.POLY_PRIVATE_KEY.strip()
            funder = Config.get_funder_address()
            client = clob.init_py_clob_client(pk, funder, Config.POLY_SIGNATURE_TYPE)
            if client:
                add_log("INIT", "✅ CLOB V2 connected!")
            else:
                add_log("WARN", "CLOB returned None — paper fallback")
        except Exception as e:
            add_log("ERROR", f"CLOB init failed: {e}")

    start_time = time.time()
    scan_round = 0

    while True:
        scan_round += 1
        STATE['scan_round'] = scan_round
        STATE['uptime_seconds'] = int(time.time() - start_time)

        add_log("SCAN", f"Round #{scan_round} | {risk_mgr.get_status_line()}")

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
            add_log("RISK", f"⚠️ {reason}")
            await asyncio.sleep(30)
            continue

        # Discover markets
        try:
            markets = gamma.discover_markets()
        except Exception as e:
            add_log("ERROR", f"Market discovery: {e}")
            markets = []

        STATE['markets_found'] = len(markets) if markets else 0
        STATE['active_markets'] = [
            {'coin': m['coin'], 'tf': m['timeframe'], 'secs': m['seconds_remaining'], 'q': m['question'][:60]}
            for m in (markets or [])[:12]
        ]

        if not markets:
            add_log("SCAN", "No active markets. Waiting...")
            await asyncio.sleep(10)
            continue

        add_log("SCAN", f"Found {len(markets)} active markets")

        # Context
        context = {
            'clob': clob,
            'risk_mgr': risk_mgr,
            'seconds_remaining': markets[0].get('seconds_remaining', 300),
        }

        # Signal generation
        try:
            signals = await signal_ranker.get_ranked_signals(markets, context)
        except Exception as e:
            add_log("ERROR", f"Signal gen: {e}")
            signals = []

        STATE['total_signals'] += len(signals)
        STATE['last_signals'] = [
            {'coin': s.coin, 'dir': s.direction, 'conf': s.confidence,
             'strategy': s.strategy, 'limit': s.limit_price,
             'agreement': s.metadata.get('agreement_count', 1)}
            for s in (signals or [])[:8]
        ]

        # Strategy stats
        strat_counts = STATE.get('strategy_stats', {})
        for s in signals:
            strat_counts[s.strategy] = strat_counts.get(s.strategy, 0) + 1
        STATE['strategy_stats'] = strat_counts

        if signals:
            add_log("SIGNAL", f"🎯 {len(signals)} signals:")
            for i, sig in enumerate(signals[:5]):
                agr = sig.metadata.get('agreement_count', 1)
                stars = '⭐' * min(agr, 3)
                add_log("SIGNAL", f"  #{i+1} {stars} {sig.coin} {sig.direction} | "
                        f"{sig.confidence:.0%} | {sig.strategy}")

                if Config.is_paper():
                    size = risk_mgr.calculate_position_size(sig.confidence, sig.strategy)
                    if size >= Config.POLYMARKET_MIN_ORDER_SIZE:
                        add_log("PAPER", f"    📋 {Config.format_balance(size)} | {sig.rationale[:70]}")
                        STATE['total_trades'] += 1
        else:
            add_log("SCAN", "No signals above threshold")

        # Equity curve
        STATE['equity_curve'].append(risk_mgr.balance)
        if len(STATE['equity_curve']) > 500:
            STATE['equity_curve'] = STATE['equity_curve'][-500:]

        # Heartbeat
        clob.send_heartbeat()

        await asyncio.sleep(5)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("⚡ 5MIN_TRADE v2.1 — Dashboard + Bot")
    print("=" * 60)
    try:
        asyncio.run(bot_loop())
    except KeyboardInterrupt:
        add_log("SYSTEM", "Bot stopped by user")
        print("\n👋 Bye!", flush=True)
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        import traceback
        traceback.print_exc()
