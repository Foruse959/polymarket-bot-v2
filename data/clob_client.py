"""
CLOB API Client — Orderbook & Order Execution (V2)

Uses py-clob-client-v2 for V2 order format:
- No feeRateBps (fees set at match time)
- Timestamp field in orders
- Builder attribution support
- $1 minimum trade size (FOK orders, no 5-share rule)
"""

import math
import requests
from typing import Dict, List, Optional, Tuple, Any

from config import Config


class ClobClient:
    """Client for Polymarket's CLOB API — V2 order format."""

    def __init__(self):
        self.base_url = Config.get_clob_url()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'5min-trade-bot-v2/{Config.VERSION}',
            'Accept': 'application/json',
        })
        self.fallback_prices: Dict[str, float] = {}
        self._py_clob_client = None
        self._api_creds = None
        self._is_v2 = False  # Track which SDK we're using

    def set_fallback_price(self, token_id: str, price: float):
        self.fallback_prices[token_id] = price

    def get_price(self, token_id: str) -> Optional[float]:
        try:
            url = f"{self.base_url}/price"
            resp = self.session.get(url, params={'token_id': token_id}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get('price', 0))
        except Exception:
            pass
        return self.fallback_prices.get(token_id)

    def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        prices = {}
        for tid in token_ids:
            p = self.get_price(tid)
            if p is not None:
                prices[tid] = p
        return prices

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        if not token_id:
            return None
        try:
            url = f"{self.base_url}/book"
            resp = self.session.get(url, params={'token_id': token_id}, timeout=10)
            if resp.status_code != 200:
                return self._fallback_orderbook(token_id)
            data = resp.json()
            bids = sorted(
                [(float(b['price']), float(b['size'])) for b in data.get('bids', [])],
                key=lambda x: x[0], reverse=True
            )
            asks = sorted(
                [(float(a['price']), float(a['size'])) for a in data.get('asks', [])],
                key=lambda x: x[0]
            )
            if bids or asks:
                best_bid = bids[0][0] if bids else 0.0
                best_ask = asks[0][0] if asks else 1.0
                spread = best_ask - best_bid
                mid = (best_bid + best_ask) / 2 if (best_bid + best_ask) > 0 else 0.5
                bid_depth = sum(p * s for p, s in bids[:10])
                ask_depth = sum(p * s for p, s in asks[:10])
                total_depth = bid_depth + ask_depth
                imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0
                return {
                    'token_id': token_id, 'bids': bids, 'asks': asks,
                    'best_bid': best_bid, 'best_ask': best_ask,
                    'spread': spread,
                    'spread_pct': (spread / best_ask * 100) if best_ask > 0 else 0,
                    'spread_bps': (spread / best_ask * 10000) if best_ask > 0 else 0,
                    'mid_price': mid,
                    'bid_depth': bid_depth, 'ask_depth': ask_depth,
                    'imbalance': imbalance,
                }
        except Exception as e:
            pass
        return self._fallback_orderbook(token_id)

    def _fallback_orderbook(self, token_id: str) -> Optional[Dict]:
        price = self.fallback_prices.get(token_id)
        if price and price > 0:
            spread = 0.02
            best_bid = max(0.01, price - spread / 2)
            best_ask = min(0.99, price + spread / 2)
            return {
                'token_id': token_id,
                'bids': [(best_bid, 100.0)], 'asks': [(best_ask, 100.0)],
                'best_bid': best_bid, 'best_ask': best_ask,
                'spread': spread,
                'spread_pct': (spread / best_ask * 100) if best_ask > 0 else 0,
                'spread_bps': (spread / best_ask * 10000) if best_ask > 0 else 0,
                'mid_price': price,
                'bid_depth': best_bid * 100, 'ask_depth': best_ask * 100,
                'imbalance': 0.0, '_synthetic': True,
            }
        return None

    def get_dual_orderbook(self, up_token: str, down_token: str) -> Optional[Dict]:
        up_book = self.get_orderbook(up_token)
        down_book = self.get_orderbook(down_token)

        if not up_book and not down_book:
            return None
        if not up_book and down_book:
            up_book = {
                'token_id': up_token, 'bids': [], 'asks': [(0.99, 100.0)],
                'best_bid': 0.01, 'best_ask': 0.99, 'spread': 0.98,
                'spread_pct': 98.0, 'spread_bps': 9800, 'mid_price': 0.50,
                'bid_depth': 0, 'ask_depth': 99.0, 'imbalance': -1.0,
            }
        elif not down_book and up_book:
            down_book = {
                'token_id': down_token, 'bids': [], 'asks': [(0.99, 100.0)],
                'best_bid': 0.01, 'best_ask': 0.99, 'spread': 0.98,
                'spread_pct': 98.0, 'spread_bps': 9800, 'mid_price': 0.50,
                'bid_depth': 0, 'ask_depth': 99.0, 'imbalance': -1.0,
            }

        combined_bid = up_book['best_bid'] + down_book['best_bid']
        combined_ask = up_book['best_ask'] + down_book['best_ask']

        return {
            'up': up_book, 'down': down_book,
            'combined_bid': combined_bid, 'combined_ask': combined_ask,
            'arb_opportunity': combined_ask < 1.0,
            'arb_profit_bps': (1.0 - combined_ask) * 10000 if combined_ask < 1.0 else 0,
        }

    def get_market_trades(self, token_id: str, limit: int = 100) -> List[Dict]:
        try:
            url = f"{self.base_url}/trades"
            resp = self.session.get(url, params={'token_id': token_id, 'limit': limit}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get('trades', [])
        except Exception:
            pass
        return []

    def get_order(self, order_id: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/order/{order_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_orders(self, address: str, status: str = 'open') -> List[Dict]:
        try:
            url = f"{self.base_url}/orders"
            resp = self.session.get(url, params={'address': address, 'status': status}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get('orders', [])
        except Exception:
            pass
        return []

    def get_balance(self, address: str, token_id: str = None) -> Dict:
        try:
            url = f"{self.base_url}/balance"
            params = {'address': address}
            if token_id:
                params['token_id'] = token_id
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {'balance': '0', 'allowance': '0'}

    # ── V2 SDK INITIALIZATION ──

    def init_py_clob_client(self, private_key: str, funder: str = None,
                           signature_type: int = 0) -> Any:
        """
        Initialize py-clob-client-v2 for V2 order format.
        
        V2 changes:
        - No feeRateBps in orders (fees set at match time)
        - timestamp field required
        - Builder attribution via builder_config
        - Uses py_clob_client_v2 package
        """
        # Try V2 SDK first
        try:
            return self._init_v2_client(private_key, funder, signature_type)
        except ImportError:
            print("[CLOB] py-clob-client-v2 not available, falling back to v1", flush=True)
        except Exception as e:
            print(f"[CLOB] V2 init failed: {e}, trying v1 fallback", flush=True)

        # Fallback to V1 SDK
        return self._init_v1_client(private_key, funder, signature_type)

    def _init_v2_client(self, private_key: str, funder: str, signature_type: int) -> Any:
        """Initialize V2 Python SDK"""
        from py_clob_client_v2 import ClobClient as PyClobClientV2
        from py_clob_client_v2.clob_types import BuilderConfig as V2BuilderConfig

        pk = private_key.strip()
        if not pk.startswith('0x'):
            pk = '0x' + pk

        chain_id = Config.POLY_CHAIN_ID

        # Builder config for attribution & fee discounts
        builder_config = None
        builder_code = '0x0000000000000000000000000000000000000000000000000000000000000000'
        if Config.POLY_BUILDER_CODE:
            builder_code = Config.POLY_BUILDER_CODE.strip()
            try:
                builder_config = V2BuilderConfig(
                    builder_address=Config.POLY_PROXY_WALLET.strip() if Config.POLY_PROXY_WALLET else '',
                    builder_code=builder_code,
                )
                print(f"[CLOB] V2 Builder config set (code={builder_code[:10]}...)", flush=True)
            except Exception as e:
                print(f"[CLOB] V2 Builder config failed: {e}", flush=True)

        # Initialize V2 client
        client = PyClobClientV2(
            host=self.base_url,
            chain_id=chain_id,
            key=pk,
            signature_type=signature_type,
            funder=funder,
            builder_config=builder_config,
        )

        # Derive API credentials
        print(f"[CLOB] V2: Creating API credentials...", flush=True)
        try:
            api_key = client.create_or_derive_api_key()
        except Exception as e:
            print(f"[CLOB] V2: API key creation failed ({e}), trying derive...", flush=True)
            try:
                api_key = client.derive_api_key()
            except Exception as e2:
                print(f"[CLOB] V2: API key derive also failed: {e2}", flush=True)
                raise RuntimeError(f"Failed to get V2 API credentials: {e2}")
        
        client.set_api_creds(api_key)
        self._api_creds = api_key

        # Test connection
        try:
            ok = client.get_ok()
            print(f"[CLOB] V2 connection test: {ok}", flush=True)
        except Exception as e:
            print(f"[CLOB] V2 connection test failed (non-fatal): {e}", flush=True)

        self._py_clob_client = client
        self._is_v2 = True
        self._builder_code = builder_code
        print(f"[OK] py-clob-client-V2 initialized (sig_type={signature_type})", flush=True)
        print(f"[CLOB] Host: {self.base_url}", flush=True)
        print(f"[CLOB] Funder: {funder[:10]}...{funder[-4:] if funder else 'None'}", flush=True)
        return client

    def _init_v1_client(self, private_key: str, funder: str, signature_type: int) -> Any:
        """Fallback: Initialize V1 Python SDK"""
        from py_clob_client.client import ClobClient as PyClobClient
        from py_clob_client.clob_types import ApiCreds

        pk = private_key.strip()
        if not pk.startswith('0x'):
            pk = '0x' + pk

        chain_id = Config.POLY_CHAIN_ID

        # Builder config for v1
        builder_config = None
        if Config.POLY_BUILDER_API_KEY and Config.POLY_BUILDER_SECRET and Config.POLY_BUILDER_PASSPHRASE:
            try:
                from py_builder_signing_sdk.config import BuilderConfig
                from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
                builder_config = BuilderConfig(
                    local_builder_creds=BuilderApiKeyCreds(
                        key=Config.POLY_BUILDER_API_KEY.strip(),
                        secret=Config.POLY_BUILDER_SECRET.strip(),
                        passphrase=Config.POLY_BUILDER_PASSPHRASE.strip(),
                    )
                )
                print(f"[CLOB] V1 Builder config set", flush=True)
            except Exception as e:
                print(f"[CLOB] V1 Builder config failed: {e}", flush=True)

        client = PyClobClient(
            host=self.base_url,
            key=pk,
            chain_id=chain_id,
            signature_type=signature_type,
            funder=funder,
            builder_config=builder_config,
        )

        print(f"[CLOB] V1: Deriving API credentials...", flush=True)
        self._api_creds = client.create_or_derive_api_creds()
        client.set_api_creds(self._api_creds)

        try:
            ok = client.get_ok()
            print(f"[CLOB] V1 connection test: {ok}", flush=True)
        except Exception as e:
            print(f"[CLOB] V1 connection test failed (non-fatal): {e}", flush=True)

        self._py_clob_client = client
        self._is_v2 = False
        print(f"[OK] py-clob-client V1 (0.34.6) initialized (sig_type={signature_type})", flush=True)
        return client

    # ── ORDER PLACEMENT ──

    def place_market_order(self, token_id: str, side: str, size_usdc: float,
                          price: float = None, taker_fee_rate: float = None) -> Optional[Dict]:
        """Place a FOK (Fill-or-Kill) market order — $1 minimum, no 5-share rule."""
        if not self._py_clob_client:
            print("[CLOB] Client not initialized", flush=True)
            return None

        # Enforce minimum $1
        size_usdc = max(size_usdc, Config.POLYMARKET_MIN_ORDER_SIZE_USDC)

        try:
            if self._is_v2:
                return self._place_order_v2(token_id, side, size_usdc, price, 'FOK')
            else:
                return self._place_order_v1(token_id, side, size_usdc, price, 'FOK')
        except Exception as e:
            print(f"[CLOB] FOK order failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None

    def place_limit_order(self, token_id: str, side: str, price: float,
                         size_usdc: float, expiration: str = "GTC") -> Optional[Dict]:
        """Place a limit order (GTC or FOK) — $1 minimum."""
        if not self._py_clob_client:
            print("[CLOB] Client not initialized", flush=True)
            return None

        # Enforce minimum $1
        size_usdc = max(size_usdc, Config.POLYMARKET_MIN_ORDER_SIZE_USDC)

        is_fok = expiration.upper() in ('FOK', 'IOC')

        try:
            if self._is_v2:
                return self._place_order_v2(token_id, side, size_usdc, price, expiration.upper())
            else:
                return self._place_order_v1(token_id, side, size_usdc, price, expiration.upper())
        except Exception as e:
            print(f"[CLOB] Order failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None

    def _calculate_shares(self, price: float, size_usdc: float, is_fok: bool = True) -> Tuple[float, float]:
        """Calculate shares for order. FOK: min 1 share. GTC: min 5 shares."""
        price = round(float(price), 2)
        price = max(0.01, min(0.99, price))

        min_shares = 1 if is_fok else 5

        shares = math.floor(size_usdc / price * 100) / 100
        if shares < min_shares:
            shares = float(min_shares)

        # GCD-align for precision
        P = int(round(price * 100))
        S = int(math.floor(shares * 100))
        if P > 0 and S > 0:
            step = 100 // math.gcd(P, 100)
            S = (S // step) * step
            if S < min_shares * 100:
                S = ((min_shares * 100 + step - 1) // step) * step
            shares = S / 100.0

        order_amount = round(price * shares, 2)
        # If still below $1, bump shares up
        if order_amount < Config.POLYMARKET_MIN_ORDER_SIZE_USDC:
            shares = math.ceil(Config.POLYMARKET_MIN_ORDER_SIZE_USDC / price * 100) / 100
            shares = max(float(min_shares), shares)
            order_amount = round(price * shares, 2)

        return shares, order_amount

    def _place_order_v2(self, token_id: str, side: str, size_usdc: float,
                       price: float, order_type: str) -> Optional[Dict]:
        """Place order using V2 SDK (no feeRateBps, timestamp + metadata fields)"""
        from py_clob_client_v2.clob_types import OrderArgs as OrderArgsV2, OrderType as V2OrderType, PartialCreateOrderOptions
        from py_clob_client_v2.order_builder.constants import BUY, SELL

        side_const = BUY if side.upper() == 'BUY' else SELL

        if price is None or price <= 0:
            price = 0.50
        # Clamp price to valid range (tick_size=0.01)
        price = max(0.01, min(0.99, round(price, 2)))

        is_fok = order_type in ('FOK', 'IOC')
        shares, order_amount = self._calculate_shares(price, size_usdc, is_fok)

        # V2 order args include builder_code and metadata
        builder_code = getattr(self, '_builder_code', '0x0000000000000000000000000000000000000000000000000000000000000000')

        print(f"[CLOB] V2 {order_type} {side} {shares:.2f} shares @ ${price:.2f} = ${order_amount:.2f} | token={token_id[:20]}...", flush=True)

        order_args = OrderArgsV2(
            token_id=token_id,
            side=side_const,
            price=price,
            size=shares,
            builder_code=builder_code,
        )

        # V2 options: tick_size and neg_risk
        # Check neg_risk from market data (updown markets vary)
        neg_risk = getattr(self, '_current_neg_risk', False)
        options = PartialCreateOrderOptions(
            tick_size="0.01",
            neg_risk=neg_risk,
        )

        signed_order = self._py_clob_client.create_order(order_args, options)

        # Map order type
        v2_order_type = V2OrderType.FOK if is_fok else V2OrderType.GTC
        resp = self._py_clob_client.post_order(signed_order, v2_order_type)

        order_id = resp.get('orderID') or resp.get('order_id') or resp.get('id', 'unknown')
        print(f"[CLOB] V2 response: order_id={order_id} resp={resp}", flush=True)

        return {
            'order_id': order_id,
            'status': resp.get('status', 'UNKNOWN'),
            'price': price,
            'size': shares,
            'size_usdc': order_amount,
            'side': side,
            'type': order_type,
        }

    def _place_order_v1(self, token_id: str, side: str, size_usdc: float,
                       price: float, order_type: str) -> Optional[Dict]:
        """Place order using V1 SDK (legacy fallback)"""
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL

        side_const = BUY if side.upper() == 'BUY' else SELL

        if price is None or price <= 0:
            price = 0.50

        is_fok = order_type in ('FOK', 'IOC')
        shares, order_amount = self._calculate_shares(price, size_usdc, is_fok)

        print(f"[CLOB] V1 {order_type} {side} {shares:.2f} shares @ ${price:.2f} = ${order_amount:.2f} | token={token_id[:20]}...", flush=True)

        order_args = OrderArgs(
            token_id=token_id,
            side=side_const,
            price=price,
            size=shares,
        )

        signed_order = self._py_clob_client.create_order(order_args)
        v1_order_type = OrderType.FOK if is_fok else OrderType.GTC
        resp = self._py_clob_client.post_order(signed_order, v1_order_type)

        order_id = resp.get('orderID') or resp.get('order_id') or resp.get('id', 'unknown')
        print(f"[CLOB] V1 response: order_id={order_id} resp={resp}", flush=True)

        return {
            'order_id': order_id,
            'status': resp.get('status', 'UNKNOWN'),
            'price': price,
            'size': shares,
            'size_usdc': order_amount,
            'side': side,
            'type': order_type,
        }

    def cancel_order(self, order_id: str) -> bool:
        if not self._py_clob_client:
            return False
        try:
            self._py_clob_client.cancel(order_id)
            return True
        except Exception as e:
            print(f"❌ Cancel order failed: {e}", flush=True)
            return False

    def cancel_all_orders(self) -> bool:
        if not self._py_clob_client:
            return False
        try:
            self._py_clob_client.cancel_all()
            return True
        except Exception as e:
            print(f"❌ Cancel all orders failed: {e}", flush=True)
            return False

    def get_mid_price(self, token_id: str) -> Optional[float]:
        book = self.get_orderbook(token_id)
        if book:
            return book['mid_price']
        return self.get_price(token_id)

    def calculate_maker_edge(self, token_id: str, side: str,
                            target_price: float = None) -> Optional[Dict]:
        book = self.get_orderbook(token_id)
        if not book:
            return None
        mid = book['mid_price']
        best_bid = book['best_bid']
        best_ask = book['best_ask']
        spread_bps = book['spread_bps']

        if side.upper() == 'BUY':
            reference = best_bid
            edge_vs_mid = (mid - target_price) / mid * 10000 if target_price else (mid - best_bid) / mid * 10000
        else:
            reference = best_ask
            edge_vs_mid = (target_price - mid) / mid * 10000 if target_price else (best_ask - mid) / mid * 10000

        return {
            'mid_price': mid, 'best_bid': best_bid, 'best_ask': best_ask,
            'spread_bps': spread_bps,
            'reference_price': reference, 'target_price': target_price or reference,
            'edge_bps': edge_vs_mid, 'edge_pct': edge_vs_mid / 100,
        }

    def send_heartbeat(self) -> bool:
        """V2: Send heartbeat to keep orders alive. No-op if client not initialized."""
        if not self._py_clob_client:
            return False
        try:
            if hasattr(self._py_clob_client, 'heartbeat'):
                self._py_clob_client.heartbeat()
                return True
        except Exception:
            pass
        return False
