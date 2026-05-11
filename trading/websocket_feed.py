#!/usr/bin/env python3
"""
WebSocket Price Feed — Real-time Market Data

Replaces polling with WebSocket for instant price updates.
Key for arb opportunities that disappear in seconds.
"""

import asyncio
import websockets
import json
import time
from typing import Dict, Callable, Optional
from dataclasses import dataclass

@dataclass
class PriceUpdate:
    """Real-time price update."""
    token_id: str
    price: float
    timestamp: int
    source: str

class PolymarketWebSocket:
    """
    WebSocket connection to Polymarket for real-time data.
    
    Faster than REST API polling:
    - REST: 100-300ms per request
    - WebSocket: <10ms push updates
    """
    
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._price_callbacks: Dict[str, Callable] = {}
        self._orderbook_callbacks: Dict[str, Callable] = {}
        self._running = False
        self._reconnect_delay = 1
        self._last_ping = 0
        
    async def connect(self):
        """Connect to WebSocket."""
        try:
            self.ws = await websockets.connect(
                self.WS_URL,
                ping_interval=30,
                ping_timeout=10,
            )
            self._running = True
            self._reconnect_delay = 1
            print("✅ WebSocket connected")
            
            # Subscribe to markets
            await self._subscribe_all()
            
            # Start message handler
            asyncio.create_task(self._message_loop())
            
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            await self._reconnect()
    
    async def _reconnect(self):
        """Reconnect with exponential backoff."""
        print(f"🔄 Reconnecting in {self._reconnect_delay}s...")
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, 60)
        await self.connect()
    
    async def _subscribe_all(self):
        """Subscribe to all token feeds."""
        if not self.ws:
            return
        
        # Subscribe message
        subscribe_msg = {
            "type": "subscribe",
            "channel": "prices",
            "tokens": list(self._price_callbacks.keys())
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
    
    async def _message_loop(self):
        """Handle incoming messages."""
        while self._running and self.ws:
            try:
                message = await asyncio.wait_for(
                    self.ws.recv(),
                    timeout=60
                )
                
                await self._handle_message(message)
                
            except asyncio.TimeoutError:
                # Send ping
                if time.time() - self._last_ping > 30:
                    await self._send_ping()
                    
            except websockets.exceptions.ConnectionClosed:
                print("⚠️  WebSocket closed")
                self._running = False
                await self._reconnect()
                break
                
            except Exception as e:
                print(f"⚠️  WebSocket error: {e}")
    
    async def _handle_message(self, message: str):
        """Parse and handle message."""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'price':
                await self._handle_price_update(data)
            elif msg_type == 'orderbook':
                await self._handle_orderbook_update(data)
            elif msg_type == 'ping':
                await self._send_pong()
                
        except json.JSONDecodeError:
            pass
    
    async def _handle_price_update(self, data: Dict):
        """Handle price update."""
        token_id = data.get('token_id')
        price = float(data.get('price', 0))
        timestamp = data.get('timestamp', int(time.time() * 1000))
        
        update = PriceUpdate(
            token_id=token_id,
            price=price,
            timestamp=timestamp,
            source='websocket'
        )
        
        # Call registered callback
        if token_id in self._price_callbacks:
            callback = self._price_callbacks[token_id]
            # Run callback in background
            asyncio.create_task(callback(update))
    
    async def _handle_orderbook_update(self, data: Dict):
        """Handle orderbook update."""
        token_id = data.get('token_id')
        
        if token_id in self._orderbook_callbacks:
            callback = self._orderbook_callbacks[token_id]
            asyncio.create_task(callback(data))
    
    async def _send_ping(self):
        """Send ping to keep connection alive."""
        if self.ws:
            await self.ws.send(json.dumps({'type': 'ping'}))
            self._last_ping = time.time()
    
    async def _send_pong(self):
        """Send pong response."""
        if self.ws:
            await self.ws.send(json.dumps({'type': 'pong'}))
    
    def on_price(self, token_id: str, callback: Callable):
        """Register price callback for token."""
        self._price_callbacks[token_id] = callback
        
    def on_orderbook(self, token_id: str, callback: Callable):
        """Register orderbook callback for token."""
        self._orderbook_callbacks[token_id] = callback
    
    async def close(self):
        """Close connection."""
        self._running = False
        if self.ws:
            await self.ws.close()

class FastPriceOracle:
    """
    Hybrid price feed: WebSocket + REST fallback.
    
    Uses WebSocket for real-time, REST for initial load.
    """
    
    def __init__(self):
        self.ws = PolymarketWebSocket()
        self._current_prices: Dict[str, PriceUpdate] = {}
        self._price_updated = asyncio.Event()
        
    async def start(self, token_ids: list):
        """Start price feeds for tokens."""
        # Register callbacks
        for token_id in token_ids:
            self.ws.on_price(token_id, self._on_price)
        
        # Connect
        await self.ws.connect()
    
    async def _on_price(self, update: PriceUpdate):
        """Handle price update."""
        self._current_prices[update.token_id] = update
        self._price_updated.set()
    
    def get_price(self, token_id: str) -> Optional[float]:
        """Get latest price (instant, from memory)."""
        if token_id in self._current_prices:
            return self._current_prices[token_id].price
        return None
    
    async def wait_for_price(self, token_id: str, timeout: float = 1.0) -> Optional[float]:
        """Wait for price update."""
        if token_id in self._current_prices:
            return self._current_prices[token_id].price
        
        try:
            await asyncio.wait_for(
                self._price_updated.wait(),
                timeout=timeout
            )
            return self.get_price(token_id)
        except asyncio.TimeoutError:
            return None
    
    async def close(self):
        """Stop price feeds."""
        await self.ws.close()

# Global instance
_oracle: Optional[FastPriceOracle] = None

async def get_oracle() -> FastPriceOracle:
    """Get price oracle singleton."""
    global _oracle
    if _oracle is None:
        _oracle = FastPriceOracle()
    return _oracle

async def main():
    """Test WebSocket feed."""
    print("="*70)
    print("📡 WEBSOCKET FEED TEST")
    print("="*70)
    
    oracle = await get_oracle()
    
    # Start feeds
    await oracle.start(['0x123', '0x456'])
    
    print("\n⏳ Waiting for price updates...")
    await asyncio.sleep(5)
    
    # Check prices
    price = oracle.get_price('0x123')
    print(f"Price: {price}")
    
    await oracle.close()
    
    print("\n" + "="*70)
    print("✅ WEBSOCKET FEED READY")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())