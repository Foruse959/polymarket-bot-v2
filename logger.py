#!/usr/bin/env python3
"""
ULTRA DETAILED LOGGER - Railway-style logging for every action
"""

import json
import time
from datetime import datetime
from pathlib import Path
from collections import deque
import threading

class UltraLogger:
    """Logs EVERYTHING like Railway does"""
    
    def __init__(self, max_logs=1000):
        self.logs = deque(maxlen=max_logs)
        self.log_file = Path("logs/live_trading.log")
        self.log_file.parent.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        
    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def _write(self, level, category, message, data=None):
        """Write a log entry"""
        entry = {
            "timestamp": self._timestamp(),
            "level": level,
            "category": category,
            "message": message,
            "data": data or {},
            "unix_time": time.time()
        }
        
        with self.lock:
            self.logs.append(entry)
            
            # Write to file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        
        return entry
    
    # BUILD PHASE
    def build_start(self):
        return self._write("BUILD", "BUILD", "Starting build...")
    
    def build_step(self, step, status="running"):
        return self._write("BUILD", "BUILD", f"Step: {step}", {"step": step, "status": status})
    
    def build_success(self):
        return self._write("SUCCESS", "BUILD", "Build completed successfully")
    
    def build_error(self, error):
        return self._write("ERROR", "BUILD", f"Build failed: {error}")
    
    # INITIALIZATION
    def init_start(self):
        return self._write("INFO", "INIT", "Initializing bot components...")
    
    def init_component(self, name, status):
        emoji = "✓" if status == "ok" else "✗"
        return self._write("INFO", "INIT", f"{emoji} {name}", {"component": name, "status": status})
    
    def init_wallet(self, address, balance, sig_type):
        return self._write("INFO", "WALLET", f"Wallet initialized", {
            "address": address,
            "balance": balance,
            "sig_type": sig_type,
            "network": "Polygon"
        })
    
    def init_complete(self):
        return self._write("SUCCESS", "INIT", "All components initialized")
    
    # MARKET SCANNING
    def scan_start(self, round_num, coins, timeframes):
        return self._write("INFO", "SCAN", f"🔄 Round {round_num}: Scanning markets...", {
            "round": round_num,
            "coins": coins,
            "timeframes": timeframes
        })
    
    def scan_api_call(self, url, method="GET"):
        return self._write("DEBUG", "API", f"→ {method} {url}")
    
    def scan_api_response(self, url, status, items_count):
        return self._write("DEBUG", "API", f"← {status} | {items_count} items", {
            "url": url,
            "status": status,
            "count": items_count
        })
    
    def scan_found_markets(self, markets):
        return self._write("INFO", "SCAN", f"📊 Found {len(markets)} markets", {
            "count": len(markets),
            "markets": [{"id": m.get("id", "N/A")[:8], "coin": m.get("coin"), "tf": m.get("timeframe")} for m in markets[:5]]
        })
    
    def scan_no_markets(self, reason):
        return self._write("WARN", "SCAN", f"⚠ No markets found: {reason}")
    
    # OPPORTUNITY ANALYSIS
    def analyze_start(self, market_id, coin, tf):
        return self._write("INFO", "ANALYZE", f"🔍 Analyzing {coin} {tf}m", {
            "market_id": market_id[:16] if market_id else "N/A",
            "coin": coin,
            "timeframe": tf
        })
    
    def analyze_price(self, source, price, latency_ms):
        return self._write("DEBUG", "PRICE", f"{source}: ${price:.2f} ({latency_ms}ms)", {
            "source": source,
            "price": price,
            "latency_ms": latency_ms
        })
    
    def analyze_indicator(self, name, value, signal):
        emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "⚪"
        return self._write("DEBUG", "INDICATOR", f"{emoji} {name}: {value:.4f} ({signal})", {
            "indicator": name,
            "value": value,
            "signal": signal
        })
    
    def analyze_confidence(self, score, threshold, reasons):
        status = "✅ PASS" if score >= threshold else "❌ FAIL"
        return self._write("INFO", "CONFIDENCE", f"Score: {score:.2f}/1.00 (min: {threshold:.2f}) {status}", {
            "score": score,
            "threshold": threshold,
            "pass": score >= threshold,
            "reasons": reasons
        })
    
    def analyze_skip(self, reason, details=None):
        return self._write("INFO", "SKIP", f"⏭ Skipped: {reason}", details)
    
    # TRADING
    def trade_signal(self, coin, direction, strategy, confidence, size_usdc):
        emoji = "🚀" if direction == "BUY" else "🔻"
        return self._write("SUCCESS", "SIGNAL", f"{emoji} SIGNAL: {coin} {direction} | {strategy} | {confidence:.0%} | ${size_usdc:.2f}", {
            "coin": coin,
            "direction": direction,
            "strategy": strategy,
            "confidence": confidence,
            "size_usdc": size_usdc
        })
    
    def trade_preparing(self, order_type, token_id):
        return self._write("INFO", "TRADE", f"📝 Preparing {order_type} order...", {
            "order_type": order_type,
            "token_id": token_id[:20] if token_id else "N/A"
        })
    
    def trade_submitting(self, side, price, size, order_type):
        return self._write("INFO", "TRADE", f"📤 Submitting order: {side} ${size:.2f} @ ${price:.3f} ({order_type})", {
            "side": side,
            "price": price,
            "size": size,
            "order_type": order_type
        })
    
    def trade_submitted(self, order_id, status):
        return self._write("SUCCESS", "TRADE", f"✅ Order submitted: {order_id[:16]}... (Status: {status})", {
            "order_id": order_id,
            "status": status
        })
    
    def trade_error(self, error, context=None):
        return self._write("ERROR", "TRADE", f"❌ Trade failed: {error}", {"context": context})
    
    def trade_filled(self, order_id, fill_price, fill_size, pnl=None):
        return self._write("SUCCESS", "TRADE", f"💰 Order filled: ${fill_size:.2f} @ ${fill_price:.3f}", {
            "order_id": order_id,
            "fill_price": fill_price,
            "fill_size": fill_size,
            "pnl": pnl
        })
    
    # POSITIONS
    def position_opened(self, position_id, coin, entry_price, size, direction):
        return self._write("INFO", "POSITION", f"📈 Position opened: {coin} {direction} ${size:.2f} @ ${entry_price:.3f}", {
            "position_id": position_id,
            "coin": coin,
            "entry_price": entry_price,
            "size": size,
            "direction": direction
        })
    
    def position_update(self, position_id, current_price, unrealized_pnl):
        emoji = "🟢" if unrealized_pnl > 0 else "🔴"
        return self._write("DEBUG", "POSITION", f"{emoji} Position {position_id[:8]}: P&L ${unrealized_pnl:+.3f}", {
            "position_id": position_id,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl
        })
    
    def position_closed(self, position_id, exit_price, realized_pnl, reason):
        emoji = "🟢" if realized_pnl > 0 else "🔴"
        return self._write("INFO", "POSITION", f"{emoji} Position closed: ${realized_pnl:+.3f} ({reason})", {
            "position_id": position_id,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
            "reason": reason
        })
    
    # SYSTEM
    def heartbeat(self, uptime_seconds, memory_mb=None):
        return self._write("DEBUG", "SYSTEM", f"💓 Heartbeat | Uptime: {uptime_seconds}s", {
            "uptime": uptime_seconds,
            "memory_mb": memory_mb
        })
    
    def error(self, error, stack_trace=None):
        return self._write("ERROR", "SYSTEM", f"💥 Error: {error}", {"stack_trace": stack_trace})
    
    def warning(self, message):
        return self._write("WARN", "SYSTEM", f"⚠ {message}")
    
    def info(self, message):
        return self._write("INFO", "SYSTEM", message)
    
    def get_recent_logs(self, count=100, category=None, level=None):
        """Get recent logs with filtering"""
        with self.lock:
            logs = list(self.logs)
        
        if category:
            logs = [l for l in logs if l["category"] == category]
        if level:
            logs = [l for l in logs if l["level"] == level]
        
        return logs[-count:]
    
    def get_logs_for_dashboard(self):
        """Get logs formatted for dashboard"""
        logs = self.get_recent_logs(200)
        return [{
            "time": l["timestamp"],
            "level": l["level"],
            "category": l["category"],
            "message": l["message"],
            "data": l["data"]
        } for l in logs]

# Global logger instance
logger = UltraLogger()
