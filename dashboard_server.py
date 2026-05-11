#!/usr/bin/env python3
"""
Ultra Dashboard Server - Serves REAL data to the dashboard
Reads from log file + bot_status.json
"""

import json
import time
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import webbrowser

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

LOG_FILE = Path("logs/live_trading.log")
STATUS_FILE = Path("logs/bot_status.json")
DASHBOARD_FILE = Path("ultra_dashboard.html")
PORT = 8080


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves dashboard + API endpoints"""

    def __init__(self, *args, **kwargs):
        self.directory = str(Path(__file__).parent)
        super().__init__(*args, directory=self.directory, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        if self.path == '/api/status':
            self.send_json_response(self.get_status())
        elif self.path == '/api/logs':
            count = int(self.headers.get('X-Log-Count', '100'))
            self.send_json_response(self.get_logs(count))
        elif self.path == '/api/markets':
            self.send_json_response(self.get_markets())
        elif self.path == '/api/pnl':
            self.send_json_response(self.get_pnl_data())
        else:
            # Serve static files (dashboard HTML, etc.)
            super().do_GET()

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))

    def get_status(self):
        """Get bot status"""
        status = {
            'online': True,
            'mode': 'live',
            'timestamp': time.time(),
            'uptime': 0,
            'balance': 2.30,
            'markets_found': 0,
            'trades_placed': 0,
            'trades_filled': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'connected': {
                'binance': False,
                'polymarket': True,
                'polygon': True,
                'wallet': True,
            },
        }

        # Read from status file
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, 'r') as f:
                    file_status = json.load(f)
                    status.update({
                        'round': file_status.get('round', 0),
                        'uptime': file_status.get('uptime_seconds', 0),
                        'balance': file_status.get('balance', 2.30),
                        'markets_found': file_status.get('markets_found', 0),
                        'connected': file_status.get('connected', status['connected']),
                        'stats': file_status.get('stats', {}),
                    })
            except:
                pass

        return status

    def get_logs(self, count=100):
        """Get recent logs from the log file"""
        logs = []

        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-count:]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            logs.append({
                                'time': entry.get('timestamp', ''),
                                'level': entry.get('level', 'INFO'),
                                'category': entry.get('category', 'SYSTEM'),
                                'message': entry.get('message', ''),
                                'data': entry.get('data', {}),
                            })
                        except json.JSONDecodeError:
                            logs.append({
                                'time': '--:--:--',
                                'level': 'INFO',
                                'category': 'RAW',
                                'message': line[:200],
                                'data': {},
                            })
            except Exception as e:
                logs.append({
                    'time': '--:--:--',
                    'level': 'ERROR',
                    'category': 'SYSTEM',
                    'message': f'Error reading log file: {e}',
                    'data': {},
                })

        return logs

    def get_markets(self):
        """Get current markets from status file"""
        if STATUS_FILE.exists():
            try:
                with open(STATUS_FILE, 'r') as f:
                    status = json.load(f)
                    return status.get('markets', [])
            except:
                pass
        return []

    def get_pnl_data(self):
        """Get P&L data from trade logs"""
        pnl_data = []
        cumulative = 0

        if LOG_FILE.exists():
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get('category') == 'TRADE' and 'filled' in entry.get('message', '').lower():
                                pnl = entry.get('data', {}).get('pnl', 0)
                                cumulative += pnl
                                pnl_data.append({
                                    'time': entry.get('timestamp', ''),
                                    'pnl': pnl,
                                    'cumulative': cumulative,
                                })
                        except:
                            pass
            except:
                pass

        return pnl_data


def start_server():
    """Start the dashboard server"""
    handler = DashboardHandler
    server = HTTPServer(('0.0.0.0', PORT), handler)
    print(f"Dashboard server running at http://localhost:{PORT}")
    print(f"Opening dashboard...")
    webbrowser.open(f'http://localhost:{PORT}/ultra_dashboard.html')
    server.serve_forever()


if __name__ == '__main__':
    # Ensure directories exist
    LOG_FILE.parent.mkdir(exist_ok=True)
    start_server()