#!/usr/bin/env python3
"""
5MIN_TRADE v2.2 Beast Mode — Dashboard + Autonomous Bot

BEAST MODE FEATURES:
- 5-tier balance system (SURVIVAL -> SEED -> COMFORT -> AGGRESSIVE -> FULL SEND)
- Tier-aware signal filtering (low balance = only 4+ strategy agreement)
- Parallel orderbook fetching (10x speed)
- Live HTML dashboard with ALL logs
- Telegram coin selector + status commands
- Autonomous entry + TP/SL + auto-exit
- Multi-strategy ensemble voting (7 strategies)
- Technical indicator fusion (RSI+MACD+BB+EMA)

Usage:
    python dashboard.py --paper    # Simulated
    python dashboard.py --live     # Real pUSD
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
from data.market_cache import MarketCache
from data.oracle_ws import get_oracle_ws
from trading.v2_risk_manager import V2RiskManager
from trading.signal_ranker import SignalRanker
from trading.autonomous_executor import AutonomousExecutor
from bot.telegram_ui import TelegramUI


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
    'markets_found': 0,
    'active_markets': [],
    'total_signals': 0,
    'last_signals': [],
    'total_trades': 0,
    'open_positions': [],
    'closed_trades': [],
    'balance': Config.STARTING_BALANCE,
    'starting_balance': Config.STARTING_BALANCE,
    'total_pnl': 0.0,
    'daily_pnl': 0.0,
    'equity_curve': [Config.STARTING_BALANCE],
    'risk': {},
    'tier': {},
    'strategy_stats': {},
    'logs': [],
    'errors': [],
    'last_scan_at': None,
    'scan_duration_ms': 0,
}

LOG_COLORS = {
    'DEBUG': '\033[90m', 'INFO': '\033[36m', 'INIT': '\033[35m',
    'SCAN': '\033[34m', 'SIGNAL': '\033[33m', 'TRADE': '\033[32m',
    'PAPER': '\033[92m', 'RISK': '\033[91m', 'WARN': '\033[93m',
    'ERROR': '\033[31m', 'FATAL': '\033[41m', 'TIER': '\033[36m',
}
RESET = '\033[0m'


def add_log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = {'ts': ts, 'level': level, 'msg': msg}
    STATE['logs'].append(entry)
    if len(STATE['logs']) > 2000:
        STATE['logs'] = STATE['logs'][-2000:]
    if level in ('ERROR', 'FATAL'):
        STATE['errors'].append(entry)
        if len(STATE['errors']) > 100:
            STATE['errors'] = STATE['errors'][-100:]
    color = LOG_COLORS.get(level, '')
    print(f"{color}[{ts}] [{level:6}] {msg}{RESET}", flush=True)
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/beast_trading.log", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def add_error(msg, exc=None):
    """
    Log an ERROR with full stack trace when an exception is given.
    Tracebacks are split across log entries (not truncated) so every frame
    is visible in the dashboard and file logs.
    """
    add_log("ERROR", msg)
    if exc is not None:
        tb = traceback.format_exc()
        for line in tb.rstrip().split('\n'):
            if line.strip():
                add_log("ERROR", f"  {line}")


def add_error(msg, exc=None):
    """
    Log an ERROR with full stack trace when an exception is given.
    Tracebacks are split across log entries (not truncated) so every frame
    is visible in the dashboard and file logs.
    """
    add_log("ERROR", msg)
    if exc is not None:
        tb = traceback.format_exc()
        for line in tb.rstrip().split('\n'):
            if line.strip():
                add_log("ERROR", f"  {line}")


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>5MIN_TRADE v2.2 Beast Mode</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'JetBrains Mono','Fira Code','Menlo',monospace;background:#0a0e17;color:#e0e6ed;min-height:100vh;font-size:13px}
.header{background:linear-gradient(135deg,#1a1f2e 0%,#0d1117 100%);border-bottom:2px solid #30363d;padding:14px 24px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.header h1{font-size:16px;color:#58a6ff;font-weight:700}
.header .sub{color:#8b949e;font-size:11px;margin-top:2px}
.header .status{display:flex;gap:10px;align-items:center}
.badge{padding:4px 10px;border-radius:4px;font-size:10px;font-weight:700;text-transform:uppercase}
.badge-live{background:#da363322;color:#f85149;border:1px solid #f85149}
.badge-paper{background:#d2992222;color:#d29922;border:1px solid #d29922}
.badge-pusd{background:#3fb95022;color:#3fb950;border:1px solid #3fb950}
.badge-tier{padding:4px 12px;border-radius:16px;font-size:11px;font-weight:700}
.badge-SURVIVAL{background:#f0883e22;color:#f0883e;border:1px solid #f0883e}
.badge-SEED{background:#3fb95022;color:#3fb950;border:1px solid #3fb950}
.badge-COMFORT{background:#58a6ff22;color:#58a6ff;border:1px solid #58a6ff}
.badge-AGGRESSIVE{background:#d2992222;color:#d29922;border:1px solid #d29922}
.badge-FULL{background:#b392f033;color:#b392f0;border:1px solid #b392f0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px;padding:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.card h3{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.stat-row{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #21262d;font-size:12px}
.stat-row:last-child{border:none}
.stat-label{color:#8b949e}
.stat-value{font-weight:600}
.stat-value.green{color:#3fb950}.stat-value.red{color:#f85149}.stat-value.blue{color:#58a6ff}
.big-number{font-size:24px;font-weight:700;margin:4px 0}
.log-container{max-height:480px;overflow-y:auto;font-size:10.5px;line-height:1.55;padding:4px;background:#0d1117;border-radius:4px}
.log-container::-webkit-scrollbar{width:6px}
.log-container::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}
.log-entry{padding:1px 6px;border-left:3px solid transparent;margin:1px 0}
.log-entry.INFO{border-color:#58a6ff}.log-entry.INIT{border-color:#b392f0}
.log-entry.SCAN{border-color:#58a6ff}.log-entry.SIGNAL{border-color:#d29922}
.log-entry.PAPER,.log-entry.TRADE{border-color:#3fb950;background:#3fb95011}
.log-entry.RISK{border-color:#f85149;background:#f8514911}
.log-entry.TIER{border-color:#b392f0;background:#b392f011}
.log-entry.WARN{border-color:#f0883e}
.log-entry.ERROR,.log-entry.FATAL{border-color:#f85149;background:#da363322;color:#f85149;font-weight:600}
.log-entry.DEBUG{border-color:#484f58;color:#6e7681}
.log-ts{color:#484f58}
.log-level{font-weight:700;width:55px;display:inline-block}
.signal-card{background:#1c2128;border:1px solid #30363d;border-radius:4px;padding:8px;margin:4px 0;font-size:11px}
.signal-header{display:flex;justify-content:space-between;align-items:center}
.signal-coin{font-weight:700;color:#58a6ff}
.signal-dir{padding:1px 6px;border-radius:3px;font-size:10px;font-weight:700}
.signal-dir.UP{background:#3fb95022;color:#3fb950}
.signal-dir.DOWN,.signal-dir.SELL_UP{background:#f8514922;color:#f85149}
.signal-conf{font-size:18px;font-weight:700}
.signal-meta{font-size:10px;color:#8b949e;margin-top:4px}
.chart-container{width:100%;height:110px}
.chart-svg{width:100%;height:100%}
.strategy-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:11px}
.strategy-name{flex:1}
.strategy-count{color:#58a6ff;font-weight:700}
.market-row{font-size:10.5px;padding:3px 0;display:flex;gap:8px;border-bottom:1px dashed #21262d}
.market-coin{color:#58a6ff;font-weight:700;width:38px}
.market-tf{color:#8b949e;width:26px}.market-time{color:#d29922;width:42px}
.position-table{width:100%;font-size:11px;border-collapse:collapse}
.position-table th{text-align:left;padding:6px 4px;border-bottom:1px solid #30363d;color:#8b949e;font-weight:600;font-size:10px;text-transform:uppercase}
.position-table td{padding:5px 4px;border-bottom:1px dashed #21262d;font-size:11px}
.position-table tr:hover{background:#1c2128}
.coin-chips{display:flex;gap:6px;flex-wrap:wrap}
.coin-chip{padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;background:#21262d;color:#8b949e;border:1px solid #30363d}
.coin-chip.active{background:#58a6ff33;color:#58a6ff;border-color:#58a6ff}
.tier-card{background:linear-gradient(135deg,#1c2128,#161b22);border:2px solid;border-radius:8px;padding:14px;margin-bottom:10px}
.tier-card.SURVIVAL{border-color:#f0883e}
.tier-card.SEED{border-color:#3fb950}
.tier-card.COMFORT{border-color:#58a6ff}
.tier-card.AGGRESSIVE{border-color:#d29922}
.tier-card.FULL{border-color:#b392f0}
.tier-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.tier-name{font-size:16px;font-weight:700}
.tier-desc{font-size:11px;color:#8b949e;margin-top:4px}
.tier-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:8px;font-size:10px}
.tier-stat{text-align:center;padding:6px;background:#0d1117;border-radius:4px}
.tier-stat-label{color:#8b949e;font-size:9px;text-transform:uppercase}
.tier-stat-value{color:#58a6ff;font-weight:700;font-size:13px;margin-top:2px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.live-dot{width:8px;height:8px;border-radius:50%;background:#3fb950;animation:pulse 1.8s infinite;display:inline-block}
.live-dot.stopped{background:#f85149;animation:none}
.footer{text-align:center;padding:10px;color:#484f58;font-size:10px;border-top:1px solid #21262d}
.error-banner{background:#da363322;border:1px solid #f85149;padding:8px 12px;margin:0 14px 14px;border-radius:4px;color:#f85149;font-size:11px;display:none}
.error-banner.show{display:block}
.wallet{font-family:monospace;font-size:10px;color:#8b949e}
</style>
</head>
<body>
<div class="header">
    <div>
        <h1>BEAST 5MIN_TRADE v2.2</h1>
        <div class="sub">Polymarket V2 | pUSD | 5-tier balance system | Autonomous</div>
    </div>
    <div class="status">
        <span class="live-dot" id="live-dot"></span>
        <span class="badge-tier" id="tier-badge">SURVIVAL</span>
        <span class="badge badge-paper" id="mode-badge">PAPER</span>
        <span class="badge badge-pusd">pUSD</span>
        <span id="uptime" style="color:#8b949e;font-size:11px;">00:00:00</span>
    </div>
</div>

<div class="error-banner" id="error-banner"></div>

<div class="grid">
    <div class="card" style="grid-column:1/-1;padding:0;border:none;background:transparent">
        <div class="tier-card SURVIVAL" id="tier-card">
            <div class="tier-header">
                <div>
                    <span class="tier-name" id="tier-emoji-name">SURVIVAL</span>
                    <div class="tier-desc" id="tier-description">Ultra-low balance — only highest conviction trades</div>
                </div>
                <span class="big-number" id="tier-balance">0.00 pUSD</span>
            </div>
            <div class="tier-stats">
                <div class="tier-stat"><div class="tier-stat-label">Min Confidence</div><div class="tier-stat-value" id="tier-min-conf">70%</div></div>
                <div class="tier-stat"><div class="tier-stat-label">Min Strategies</div><div class="tier-stat-value" id="tier-min-agree">4+</div></div>
                <div class="tier-stat"><div class="tier-stat-label">Max Positions</div><div class="tier-stat-value" id="tier-max-pos">1</div></div>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>Balance and PnL <span class="badge badge-pusd" id="onchain-indicator" style="display:none">On-chain</span></h3>
        <div class="big-number" id="balance">100.00 pUSD</div>
        <div class="stat-row"><span class="stat-label">Wallet</span><span class="stat-value wallet" id="wallet-addr">—</span></div>
        <div class="stat-row"><span class="stat-label">Total PnL</span><span class="stat-value" id="total-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Daily PnL</span><span class="stat-value" id="daily-pnl">+0.00</span></div>
        <div class="stat-row"><span class="stat-label">Return</span><span class="stat-value" id="return-pct">0.0%</span></div>
        <div class="chart-container"><svg class="chart-svg" id="equity-chart"></svg></div>
    </div>

    <div class="card">
        <h3>Risk Manager</h3>
        <div class="stat-row"><span class="stat-label">Win Rate</span><span class="stat-value green" id="win-rate">0%</span></div>
        <div class="stat-row"><span class="stat-label">W / L</span><span class="stat-value" id="win-loss">0 / 0</span></div>
        <div class="stat-row"><span class="stat-label">Streak</span><span class="stat-value" id="streak">—</span></div>
        <div class="stat-row"><span class="stat-label">Drawdown</span><span class="stat-value red" id="drawdown">0.0%</span></div>
        <div class="stat-row"><span class="stat-label">Kelly Fraction</span><span class="stat-value blue">25%</span></div>
        <div class="stat-row"><span class="stat-label">Status</span><span class="stat-value green" id="risk-status">Active</span></div>
        <div class="stat-row"><span class="stat-label">Open positions</span><span class="stat-value blue" id="open-count">0</span></div>
    </div>

    <div class="card">
        <h3>Enabled Coins <span style="color:#484f58;font-size:10px;">(edit via Telegram /coins)</span></h3>
        <div class="coin-chips" id="coin-chips"></div>
        <div style="margin-top:12px;font-size:10.5px;color:#8b949e;">
            Timeframes: <span id="tfs">5,15</span>min<br>
            Strategies: 7 active (indicator fusion + microstructure)<br>
            Scan time: <span id="scan-ms">—</span>ms
        </div>
    </div>

    <div class="card">
        <h3>Latest Signals <span style="color:#484f58;">(<span id="signal-count">0</span>)</span></h3>
        <div id="signals-container"></div>
    </div>

    <div class="card">
        <h3>Strategy Activity</h3>
        <div id="strategy-container"></div>
    </div>

    <div class="card">
        <h3>Active Markets <span style="color:#484f58;">(<span id="market-count">0</span>)</span></h3>
        <div id="markets-container" style="max-height:300px;overflow-y:auto;"></div>
    </div>

    <div class="card" style="grid-column:1/-1;">
        <h3>Open Positions <span style="color:#484f58;">(live TP/SL tracking)</span></h3>
        <table class="position-table">
            <thead><tr>
                <th>Coin</th><th>Dir</th><th>Strategy</th><th>Conf</th><th>Size</th>
                <th>Entry</th><th>Current</th><th>PnL %</th><th>PnL pUSD</th>
                <th>TP</th><th>SL</th><th>Age</th>
            </tr></thead>
            <tbody id="positions-body"><tr><td colspan="12" style="color:#484f58;padding:14px;text-align:center;">No open positions</td></tr></tbody>
        </table>
    </div>

    <div class="card" style="grid-column:1/-1;">
        <h3>Recent Closed Trades <span style="color:#484f58;">(last 15)</span></h3>
        <table class="position-table">
            <thead><tr>
                <th>Coin</th><th>Dir</th><th>Strategy</th><th>Entry</th><th>Exit</th>
                <th>PnL %</th><th>PnL pUSD</th><th>Status</th>
            </tr></thead>
            <tbody id="closed-body"><tr><td colspan="8" style="color:#484f58;padding:14px;text-align:center;">No closed trades yet</td></tr></tbody>
        </table>
    </div>

    <div class="card" style="grid-column:1/-1;">
        <h3>Full Live Log <span style="color:#484f58;">(last 500 entries)</span></h3>
        <div class="log-container" id="log-container"></div>
    </div>
</div>

<div class="footer">
    5min_trade v2.2.0 Beast Mode | Scan #<span id="scan-round">0</span> | Last: <span id="last-scan">—</span>
</div>

<script>
let startTime = Date.now();
function updateUptime(){
    const s=Math.floor((Date.now()-startTime)/1000);
    document.getElementById('uptime').textContent=
        String(Math.floor(s/3600)).padStart(2,'0')+':'+String(Math.floor(s%3600/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');
}
setInterval(updateUptime,1000);

function escapeHtml(s){if(!s)return '';return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

function fetchState(){
    fetch('/api/state').then(r=>r.json()).then(state=>{
        const tier=state.tier||{};
        const tierName=tier.name||'SURVIVAL';
        const tierEmoji=tier.emoji||'';
        const shortName=tierName==='FULL SEND'?'FULL':tierName;
        document.getElementById('tier-card').className='tier-card '+shortName;
        document.getElementById('tier-emoji-name').textContent=tierEmoji+' '+tierName;
        document.getElementById('tier-description').textContent=tier.description||'—';
        document.getElementById('tier-balance').textContent=(state.balance||0).toFixed(2)+' pUSD';
        document.getElementById('tier-min-conf').textContent=((tier.min_confidence||0.7)*100).toFixed(0)+'%';
        document.getElementById('tier-min-agree').textContent=(tier.min_agreement||4)+'+';
        document.getElementById('tier-max-pos').textContent=tier.max_positions||1;
        document.getElementById('tier-badge').textContent=tierEmoji+' '+tierName;
        document.getElementById('tier-badge').className='badge-tier badge-'+shortName;

        document.getElementById('balance').textContent=(state.balance||0).toFixed(2)+' pUSD';
        if(state.onchain_balance!==null&&state.onchain_balance!==undefined)
            document.getElementById('onchain-indicator').style.display='inline-block';
        document.getElementById('wallet-addr').textContent=state.wallet_address
            ?state.wallet_address.slice(0,8)+'...'+state.wallet_address.slice(-6):'not set';

        const pnl=state.total_pnl||0;
        const pnlEl=document.getElementById('total-pnl');
        pnlEl.textContent=(pnl>=0?'+':'')+pnl.toFixed(2)+' pUSD';
        pnlEl.className='stat-value '+(pnl>=0?'green':'red');
        const daily=state.daily_pnl||0;
        const dEl=document.getElementById('daily-pnl');
        dEl.textContent=(daily>=0?'+':'')+daily.toFixed(2);
        dEl.className='stat-value '+(daily>=0?'green':'red');
        const sb=state.starting_balance||100;
        const ret=((state.balance-sb)/sb*100);
        const retEl=document.getElementById('return-pct');
        retEl.textContent=(ret>=0?'+':'')+ret.toFixed(1)+'%';
        retEl.className='stat-value '+(ret>=0?'green':'red');

        const r=state.risk||{};
        document.getElementById('win-rate').textContent=(r.win_rate||0).toFixed(0)+'%';
        document.getElementById('win-loss').textContent=(r.wins||0)+' / '+(r.losses||0);
        const streak=r.consecutive_wins>0?'W'+r.consecutive_wins+' HOT':r.consecutive_losses>0?'L'+r.consecutive_losses+' COLD':'—';
        document.getElementById('streak').textContent=streak;
        document.getElementById('drawdown').textContent=(r.drawdown_pct||0).toFixed(1)+'%';
        document.getElementById('risk-status').textContent=r.halted?'HALTED: '+(r.reason||''):'Active';
        document.getElementById('risk-status').className='stat-value '+(r.halted?'red':'green');
        document.getElementById('open-count').textContent=(state.open_positions||[]).length;

        const supported=['BTC','ETH','SOL','XRP'];
        document.getElementById('coin-chips').innerHTML=supported.map(c=>{
            const active=(state.enabled_coins||[]).includes(c);
            return '<span class="coin-chip '+(active?'active':'')+'">'+(active?'ON':'OFF')+' '+c+'</span>';
        }).join('');
        document.getElementById('scan-ms').textContent=state.scan_duration_ms||'—';

        document.getElementById('signal-count').textContent=state.total_signals||0;
        const sigs=state.last_signals||[];
        document.getElementById('signals-container').innerHTML=sigs.length?sigs.slice(0,6).map(s=>{
            const stars='*'.repeat(Math.min(s.agreement||1,4));
            return '<div class="signal-card"><div class="signal-header">'+
                '<span><span class="signal-coin">'+s.coin+'</span>'+
                ' <span class="signal-dir '+s.dir+'">'+s.dir+'</span>'+
                ' <span style="color:#d29922;font-size:10px;">'+(s.tier||'')+'</span></span>'+
                '<span class="signal-conf">'+(s.conf*100).toFixed(0)+'%</span></div>'+
                '<div class="signal-meta">'+stars+' '+s.strategy+' | Limit: '+(s.limit?s.limit.toFixed(3):'MKT')+'</div></div>';
        }).join(''):'<div style="color:#484f58;text-align:center;padding:20px;">Waiting for signals...</div>';

        document.getElementById('market-count').textContent=state.markets_found||0;
        const mkts=state.active_markets||[];
        document.getElementById('markets-container').innerHTML=mkts.length?mkts.map(m=>
            '<div class="market-row"><span class="market-coin">'+m.coin+'</span>'+
            '<span class="market-tf">'+m.tf+'m</span><span class="market-time">'+m.secs+'s</span>'+
            '<span style="color:#8b949e;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+m.q+'</span></div>'
        ).join(''):'<div style="color:#484f58;text-align:center;padding:20px;">Scanning...</div>';

        const strats=state.strategy_stats||{};
        document.getElementById('strategy-container').innerHTML=Object.keys(strats).length
            ?Object.entries(strats).sort((a,b)=>b[1]-a[1]).map(([n,c])=>
                '<div class="strategy-row"><span class="strategy-name">'+n+'</span><span class="strategy-count">'+c+'</span></div>'
            ).join(''):'<div style="color:#484f58;text-align:center;padding:20px;">Waiting...</div>';

        const positions=state.open_positions||[];
        document.getElementById('positions-body').innerHTML=positions.length?positions.map(p=>{
            const cls=p.pnl_pct>=0?'green':'red';
            const age=p.elapsed_sec<60?p.elapsed_sec+'s':Math.floor(p.elapsed_sec/60)+'m';
            return '<tr><td><span style="color:#58a6ff;font-weight:700;">'+p.coin+'</span></td>'+
                '<td><span class="signal-dir '+p.direction+'">'+p.direction+'</span></td>'+
                '<td style="color:#8b949e;">'+p.strategy.substring(0,14)+'</td>'+
                '<td>'+(p.confidence*100).toFixed(0)+'%</td>'+
                '<td>'+p.size_pusd.toFixed(2)+'</td>'+
                '<td>'+p.entry_price.toFixed(3)+'</td>'+
                '<td>'+p.current_price.toFixed(3)+'</td>'+
                '<td class="'+cls+'" style="font-weight:700;">'+(p.pnl_pct>=0?'+':'')+p.pnl_pct.toFixed(1)+'%</td>'+
                '<td class="'+cls+'" style="font-weight:700;">'+(p.pnl_pusd>=0?'+':'')+p.pnl_pusd.toFixed(2)+'</td>'+
                '<td style="color:#3fb950;">+'+p.tp_pct.toFixed(0)+'%</td>'+
                '<td style="color:#f85149;">'+p.sl_pct.toFixed(0)+'%</td>'+
                '<td style="color:#8b949e;">'+age+'</td></tr>';
        }).join(''):'<tr><td colspan="12" style="color:#484f58;padding:14px;text-align:center;">No open positions</td></tr>';

        const closed=state.closed_trades||[];
        document.getElementById('closed-body').innerHTML=closed.length?closed.slice(0,15).map(t=>{
            const cls=t.pnl_pusd>=0?'green':'red';
            return '<tr><td><span style="color:#58a6ff;font-weight:700;">'+t.coin+'</span></td>'+
                '<td><span class="signal-dir '+t.direction+'">'+t.direction+'</span></td>'+
                '<td style="color:#8b949e;">'+t.strategy.substring(0,16)+'</td>'+
                '<td>'+t.entry_price.toFixed(3)+'</td>'+
                '<td>'+t.current_price.toFixed(3)+'</td>'+
                '<td class="'+cls+'" style="font-weight:700;">'+(t.pnl_pct>=0?'+':'')+t.pnl_pct.toFixed(1)+'%</td>'+
                '<td class="'+cls+'" style="font-weight:700;">'+(t.pnl_pusd>=0?'+':'')+t.pnl_pusd.toFixed(2)+'</td>'+
                '<td style="color:#8b949e;font-size:10px;">'+t.status+'</td></tr>';
        }).join(''):'<tr><td colspan="8" style="color:#484f58;padding:14px;text-align:center;">No closed trades yet</td></tr>';

        document.getElementById('scan-round').textContent=state.scan_round||0;
        document.getElementById('last-scan').textContent=state.last_scan_at||'—';
        const mb=document.getElementById('mode-badge');
        mb.textContent=(state.mode||'PAPER').toUpperCase();
        mb.className='badge '+(state.mode==='live'?'badge-live':'badge-paper');
        drawEquityChart(state.equity_curve||[]);

        const lc=document.getElementById('log-container');
        const logs=(state.logs||[]).slice(-500);
        const atBottom=(lc.scrollTop+lc.clientHeight)>=(lc.scrollHeight-20);
        lc.innerHTML=logs.map(l=>
            '<div class="log-entry '+l.level+'"><span class="log-ts">'+l.ts+'</span> <span class="log-level">'+l.level+'</span> '+escapeHtml(l.msg)+'</div>'
        ).join('');
        if(atBottom)lc.scrollTop=lc.scrollHeight;

        const errors=(state.errors||[]).slice(-1);
        const banner=document.getElementById('error-banner');
        if(errors.length>0){banner.textContent='! '+errors[0].msg;banner.classList.add('show');}
        else banner.classList.remove('show');
    }).catch(()=>document.getElementById('live-dot').classList.add('stopped'));
}

function drawEquityChart(curve){
    if(!curve||curve.length<2)return;
    const svg=document.getElementById('equity-chart');
    const w=svg.clientWidth||300,h=svg.clientHeight||110;
    const min=Math.min(...curve)*0.98,max=Math.max(...curve)*1.02;
    const range=max-min||1;
    const points=curve.map((v,i)=>{
        const x=(i/(curve.length-1))*w;
        const y=h-((v-min)/range)*h;
        return x+','+y;
    }).join(' ');
    const last=curve[curve.length-1];
    const color=last>=curve[0]?'#3fb950':'#f85149';
    svg.innerHTML='<polyline points="'+points+'" fill="none" stroke="'+color+'" stroke-width="2" opacity="0.9"/>'+
        '<polyline points="0,'+h+' '+points+' '+w+','+h+'" fill="'+color+'" opacity="0.12"/>';
}

setInterval(fetchState,1500);
fetchState();
</script>
</body>
</html>"""


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


async def bot_loop():
    if '--live' in sys.argv:
        Config.TRADING_MODE = 'live'
    elif '--paper' in sys.argv:
        Config.TRADING_MODE = 'paper'

    STATE['mode'] = Config.TRADING_MODE
    STATE['started_at'] = datetime.now(timezone.utc).isoformat()
    STATE['enabled_coins'] = list(Config.ENABLED_COINS)

    Config.print_status()

    port = int(os.getenv('DASHBOARD_PORT', '8080'))
    server, actual_port = start_dashboard_server(port)
    if server:
        add_log("INIT", f"Dashboard running on http://localhost:{actual_port}")

    add_log("INIT", "=" * 58)
    add_log("INIT", f"5MIN_TRADE v{Config.VERSION} ({Config.VERSION_NAME})")
    add_log("INIT", f"Mode: {Config.TRADING_MODE.upper()} | Collateral: pUSD")
    add_log("INIT", f"Coins: {', '.join(Config.ENABLED_COINS)} | TF: {Config.ENABLED_TIMEFRAMES}")
    add_log("INIT", f"Starting balance: {Config.format_balance(Config.STARTING_BALANCE)}")
    add_log("INIT", "=" * 58)

    gamma = GammaClient()
    clob = ClobClient()
    risk_mgr = V2RiskManager(Config.STARTING_BALANCE, log_callback=add_log)
    signal_ranker = SignalRanker(log_callback=add_log)
    executor = AutonomousExecutor(risk_mgr, clob, log_callback=add_log)
    price_feed = get_price_feed()
    market_cache = MarketCache(clob, ttl_seconds=2.0)
    oracle_ws = get_oracle_ws()

    tier = risk_mgr.get_tier()
    add_log("TIER", f"STARTING TIER: {tier.emoji} {tier.name}")
    add_log("TIER", f"   {tier.description}")
    add_log("TIER", f"   Min confidence: {tier.min_confidence:.0%} | Min agreement: {tier.min_agreement}+ strategies")
    add_log("TIER", f"   Bet size: {tier.bet_pct_min:.0f}-{tier.bet_pct_max:.0f}% of balance | Max positions: {tier.max_positions}")

    add_log("INIT", f"Strategies: {signal_ranker.get_strategy_names()}")
    add_log("INIT", f"Autonomous executor ready (entry + TP/SL + auto-exit)")
    add_log("INIT", f"Parallel market cache (2s TTL, 8 workers)")

    wallet = Config.derive_wallet_address()
    funder = Config.get_funder_address()
    STATE['wallet_address'] = wallet or ''
    if wallet:
        add_log("INIT", f"Wallet: {wallet[:8]}...{wallet[-6:]}")

    if Config.TRADING_MODE == 'live':
        if not Config.is_live_ready():
            add_log("ERROR", "LIVE mode but POLY_PRIVATE_KEY not set")
            return
        add_log("INIT", "Connecting to CLOB V2...")
        try:
            client = clob.init_py_clob_client(Config.POLY_PRIVATE_KEY.strip(), funder, Config.POLY_SIGNATURE_TYPE)
            if client:
                add_log("INIT", "CLOB V2 connected")
        except ClobAuthError as e:
            add_log("FATAL", "CLOB AUTH FAILED — see instructions below:")
            for line in str(e).split('\n'):
                add_log("ERROR", line)
            add_log("WARN", "Bot continues in READ-ONLY mode. Fix auth to trade.")
        except Exception as e:
            add_log("ERROR", f"CLOB init failed: {e}")

    if wallet:
        add_log("INIT", "Checking on-chain pUSD balance (5 RPC fallbacks)...")
        onchain = clob.get_pusd_balance_onchain(wallet)
        if onchain is not None:
            STATE['onchain_balance'] = onchain
            add_log("INIT", f"On-chain pUSD: {onchain:.2f}")
            if Config.TRADING_MODE == 'live':
                if onchain < Config.POLYMARKET_MIN_ORDER_SIZE:
                    add_log("FATAL", f"Balance too low: {onchain:.2f} < {Config.POLYMARKET_MIN_ORDER_SIZE:.2f}")
                    add_log("FATAL", "Deposit USDC on polymarket.com (auto-wraps to pUSD)")
                    add_log("FATAL", "Bot stopping — cannot trade with insufficient balance.")
                    return
                risk_mgr.balance = onchain
                risk_mgr.starting_balance = onchain
                risk_mgr.peak_balance = onchain
                STATE['starting_balance'] = onchain
                add_log("INFO", f"Synced balance to on-chain: {onchain:.2f} pUSD")
        else:
            # All RPCs failed — in live mode this is fatal
            if Config.TRADING_MODE == 'live':
                add_log("FATAL", "All 5 Polygon RPC endpoints failed.")
                add_log("FATAL", "Cannot start live bot without confirmed on-chain balance.")
                add_log("FATAL", "Check your internet/firewall, then restart.")
                return
            add_log("WARN", "Could not read on-chain balance (RPC issue) — paper mode continuing")
    elif Config.TRADING_MODE == 'live':
        add_log("FATAL", "Live mode but no wallet address derivable from POLY_PRIVATE_KEY")
        return

    tg = TelegramUI(state_provider=lambda: STATE, executor=executor)
    if tg.available():
        tg.run_in_thread()
        add_log("INIT", "Telegram bot started (/status /coins /positions /recent)")
    else:
        add_log("WARN", "Telegram disabled (TOKEN not set)")

    # Start Binance oracle WebSocket (1s klines for front-running Polymarket)
    asyncio.create_task(oracle_ws.start())
    add_log("INIT", "Binance oracle WS starting in background (1s klines for BTC lead)")

    add_log("INIT", "")
    add_log("INIT", "BEAST MODE ACTIVE — scanning markets")
    add_log("INIT", "")

    start_time = time.time()
    scan_round = 0
    last_balance_check = 0

    while True:
        scan_started = time.time()
        try:
            scan_round += 1
            STATE['scan_round'] = scan_round
            STATE['uptime_seconds'] = int(time.time() - start_time)
            STATE['last_scan_at'] = datetime.now(timezone.utc).strftime("%H:%M:%S")
            STATE['enabled_coins'] = list(Config.ENABLED_COINS)

            add_log("SCAN", f"Round #{scan_round} | {risk_mgr.get_status_line()}")

            if Config.TRADING_MODE == 'live' and wallet and (time.time() - last_balance_check > 60):
                onchain = clob.get_pusd_balance_onchain(wallet)
                if onchain is not None:
                    STATE['onchain_balance'] = onchain
                last_balance_check = time.time()

            if tg.is_paused():
                add_log("INFO", "Paused via Telegram, /resume to continue")
                await asyncio.sleep(15)
                continue

            can_trade, reason = risk_mgr.can_trade()
            STATE['risk'] = risk_mgr.get_stats()
            STATE['tier'] = {
                'name': risk_mgr.current_tier.name,
                'emoji': risk_mgr.current_tier.emoji,
                'description': risk_mgr.current_tier.description,
                'min_confidence': risk_mgr.current_tier.min_confidence,
                'min_agreement': risk_mgr.current_tier.min_agreement,
                'max_positions': risk_mgr.current_tier.max_positions,
            }
            STATE['balance'] = risk_mgr.balance
            STATE['total_pnl'] = risk_mgr.total_pnl
            STATE['daily_pnl'] = risk_mgr.daily_pnl

            if not can_trade:
                add_log("RISK", f"Trading blocked: {reason}")
                await asyncio.sleep(30)
                continue

            try:
                markets = gamma.discover_markets()
            except Exception as e:
                add_log("ERROR", f"Market discovery failed: {e}")
                markets = []

            STATE['markets_found'] = len(markets) if markets else 0
            STATE['active_markets'] = [
                {'coin': m['coin'], 'tf': m['timeframe'], 'secs': m['seconds_remaining'],
                 'q': m['question'][:60]} for m in (markets or [])[:12]
            ]

            if not markets:
                add_log("SCAN", "No active markets. Waiting 10s...")
                await asyncio.sleep(10)
                continue

            coins_count = len(set(m['coin'] for m in markets))
            tf_count = len(set(m['timeframe'] for m in markets))
            add_log("SCAN", f"Found {len(markets)} markets ({coins_count} coins x {tf_count} TFs)")

            if executor.open_positions:
                pos_tokens = [p.token_id for p in executor.open_positions.values()]
                current_prices = await market_cache.get_mid_prices(pos_tokens)
                closed_this_scan = await executor.monitor_positions(
                    {k: v for k, v in current_prices.items() if v is not None}
                )
                if closed_this_scan:
                    add_log("INFO", f"Closed {len(closed_this_scan)} positions this scan")

            STATE['open_positions'] = executor.get_positions_snapshot()
            STATE['closed_trades'] = executor.get_closed_snapshot(15)

            context = {
                'clob': clob,
                'risk_mgr': risk_mgr,
                'price_feed': price_feed,
                'market_cache': market_cache,
                'oracle_ws': oracle_ws,
            }

            try:
                signals = await signal_ranker.get_ranked_signals(markets, context)
            except Exception as e:
                add_error(f"Signal generation: {e}", e)
                signals = []

            STATE['total_signals'] += len(signals)
            STATE['last_signals'] = [
                {'coin': s.coin, 'dir': s.direction, 'conf': s.confidence,
                 'strategy': s.strategy, 'limit': s.limit_price,
                 'agreement': s.metadata.get('agreement_count', 1),
                 'tier': s.metadata.get('conviction_tier', 'SINGLE')}
                for s in (signals or [])[:8]
            ]

            strat_counts = STATE.get('strategy_stats', {})
            for s in signals:
                for ss in s.metadata.get('strategies_agreeing', [s.strategy]):
                    strat_counts[ss] = strat_counts.get(ss, 0) + 1
            STATE['strategy_stats'] = strat_counts

            if not signals:
                add_log("SCAN", f"No signals above {risk_mgr.current_tier.min_confidence:.0%} "
                               f"(tier {risk_mgr.current_tier.name}) this scan")
            else:
                add_log("SIGNAL", f"{len(signals)} signals (tier {risk_mgr.current_tier.emoji}{risk_mgr.current_tier.name} "
                                  f"min_agree={risk_mgr.current_tier.min_agreement}+):")
                for i, sig in enumerate(signals[:5]):
                    agr = sig.metadata.get('agreement_count', 1)
                    ctier = sig.metadata.get('conviction_tier', 'SINGLE')
                    stars = '*' * min(agr, 4)
                    limit_str = f"@ {sig.limit_price:.3f}" if sig.limit_price else "@ MKT"
                    add_log("SIGNAL", f"  #{i+1} {stars} [{ctier}] {sig.coin} {sig.direction} "
                                     f"{sig.confidence:.0%} {limit_str} | {sig.strategy}")

                max_this_scan = min(len(signals), risk_mgr.current_tier.max_positions - risk_mgr.open_positions)
                # PARALLEL signal execution — fire every entry at the same
                # moment instead of sequentially (old: blocked 300ms each)
                if max_this_scan > 0:
                    exec_tasks = [executor.execute_signal(sig) for sig in signals[:max_this_scan]]
                    exec_results = await asyncio.gather(*exec_tasks, return_exceptions=True)
                    executed = 0
                    for i, result in enumerate(exec_results):
                        if isinstance(result, Exception):
                            add_error(f"Execute signal #{i+1}: {result}", result)
                        elif result is not None:
                            executed += 1
                            STATE['total_trades'] += 1
                else:
                    executed = 0

                if executed > 0:
                    add_log("SCAN", f"Executed {executed}/{max_this_scan} signals")

            STATE['equity_curve'].append(risk_mgr.balance)
            if len(STATE['equity_curve']) > 500:
                STATE['equity_curve'] = STATE['equity_curve'][-500:]

            clob.send_heartbeat()
            STATE['scan_duration_ms'] = int((time.time() - scan_started) * 1000)

            # Fast scan cadence: 2s between scans. Oracle lead signals die
            # in ~8s, so 5s was too slow. Gamma's discover_markets has its
            # own caching so we don't hammer the API.
            await asyncio.sleep(2)

        except Exception as e:
            add_error(f"Main loop: {e}", e)
            await asyncio.sleep(10)


if __name__ == "__main__":
    print("=" * 60)
    print("5MIN_TRADE v2.2 Beast Mode")
    print("=" * 60)
    try:
        asyncio.run(bot_loop())
    except KeyboardInterrupt:
        add_log("INFO", "Bot stopped by user")
        print("\nGoodbye", flush=True)
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        traceback.print_exc()
