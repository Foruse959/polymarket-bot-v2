"""
CLOB API Client — V2 Orderbook & Order Execution (BEAST MODE)

Fully fixed for the "Could not create api key" error.

WHY THE ERROR HAPPENS:
- Polymarket requires your wallet to be "enabled for trading" BEFORE
  API keys can be derived. This means visiting polymarket.com, connecting
  your wallet, and signing the "Enable Trading" EIP-712 message once.
- The SDK calls create_or_derive_api_key() which posts to /auth/api-key.
  If the wallet is not yet registered/enabled, the server returns 400
  with body {"error":"Could not create api key"}.

WHAT THIS CLIENT DOES:
- First tries derive_api_key() (uses existing registered credentials)
- Falls back to create_api_key() (creates new if allowed)
- Provides a CRYSTAL-CLEAR error message telling the user what to do
- Supports manual API creds via .env (POLY_API_KEY / POLY_API_SECRET / POLY_PASSPHRASE)
- Paper mode works WITHOUT any CLOB connection
"""

import math
import json
import time
import requests
from typing import Dict, List, Optional, Tuple, Any

from config import Config


class ClobAuthError(Exception):
    """Raised when CLOB auth fails with clear instructions."""
    pass


class ClobClient:
    """Client for Polymarket's CLOB API — V2 order format."""

    def __init__(self):
        self.base_url = Config.get_clob_url()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'5min-trade-bot-v{Config.VERSION}',
            'Accept': 'application/json',
        })
        self.fallback_prices: Dict[str, float] = {}
        self._py_clob_client = None
        self._api_creds = None
        self._is_v2 = False
        self._builder_code = '0x' + '0' * 64
        self._wallet_address = ''

    # ───────────────────────────────────────────────────────────────
    # READ-ONLY (no auth required)
    # ───────────────────────────────────────────────────────────────

    def set_fallback_price(self, token_id: str, price: float):
        self.fallback_prices[token_id] = price

    def get_price(self, token_id: str) -> Optional[float]:
        try:
            resp = self.session.get(f"{self.base_url}/midpoint",
                                    params={'token_id': token_id}, timeout=5)
            if resp.status_code == 200:
                return float(resp.json().get('mid', 0))
        except Exception:
            pass
        try:
            resp = self.session.get(f"{self.base_url}/price",
                                    params={'token_id': token_id, 'side': 'BUY'}, timeout=5)
            if resp.status_code == 200:
                return float(resp.json().get('price', 0))
        except Exception:
            pass
        return self.fallback_prices.get(token_id)

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        if not token_id:
            return None
        try:
            resp = self.session.get(f"{self.base_url}/book",
                                    params={'token_id': token_id}, timeout=10)
            if resp.status_code != 200:
                return self._fallback_orderbook(token_id)
            data = resp.json()
            bids = sorted([(float(b['price']), float(b['size'])) for b in data.get('bids', [])],
                          key=lambda x: x[0], reverse=True)
            asks = sorted([(float(a['price']), float(a['size'])) for a in data.get('asks', [])],
                          key=lambda x: x[0])
            if not (bids or asks):
                return self._fallback_orderbook(token_id)
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
        except Exception:
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
        if not up_book:
            up_book = self._synthetic_book(up_token)
        if not down_book:
            down_book = self._synthetic_book(down_token)
        combined_bid = up_book['best_bid'] + down_book['best_bid']
        combined_ask = up_book['best_ask'] + down_book['best_ask']
        net_flow = up_book.get('imbalance', 0) - down_book.get('imbalance', 0)
        return {
            'up': up_book, 'down': down_book,
            'combined_bid': combined_bid, 'combined_ask': combined_ask,
            'arb_opportunity': combined_ask < 1.0,
            'arb_profit_bps': (1.0 - combined_ask) * 10000 if combined_ask < 1.0 else 0,
            'net_flow_signal': net_flow,
        }

    def _synthetic_book(self, token_id):
        return {
            'token_id': token_id, 'bids': [], 'asks': [(0.99, 100.0)],
            'best_bid': 0.01, 'best_ask': 0.99, 'spread': 0.98,
            'spread_pct': 98.0, 'spread_bps': 9800, 'mid_price': 0.50,
            'bid_depth': 0, 'ask_depth': 99.0, 'imbalance': -1.0, '_synthetic': True,
        }

    def get_mid_price(self, token_id: str) -> Optional[float]:
        book = self.get_orderbook(token_id)
        return book['mid_price'] if book else self.get_price(token_id)

    def get_balance(self, address: str, token_id: str = None) -> Dict:
        try:
            params = {'address': address}
            if token_id:
                params['token_id'] = token_id
            resp = self.session.get(f"{self.base_url}/balance", params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {'balance': '0', 'allowance': '0'}

    # Fallback RPC endpoints (tried in order if primary fails)
    _RPC_FALLBACKS = [
        "https://polygon-bor-rpc.publicnode.com",
        "https://rpc.ankr.com/polygon",
        "https://1rpc.io/matic",
        "https://polygon.llamarpc.com",
        "https://polygon-rpc.com",
    ]

    def get_pusd_balance_onchain(self, wallet_address: str) -> Optional[float]:
        """
        Read pUSD balance directly from Polygon RPC (no API key needed).
        
        Tries user-configured RPC first, then 5 public fallbacks in order.
        Returns None only if ALL endpoints fail.
        """
        if not wallet_address:
            return None

        try:
            from web3 import Web3
        except ImportError:
            print(f"[CLOB] web3 not installed, skipping on-chain balance", flush=True)
            return None

        erc20_abi = [{
            "constant": True, "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }]

        # Build RPC list: user-configured first, then fallbacks
        rpcs = []
        if Config.POLYGON_RPC_URL:
            rpcs.append(Config.POLYGON_RPC_URL)
        rpcs.extend([r for r in self._RPC_FALLBACKS if r not in rpcs])

        last_error = None
        for rpc in rpcs:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
                if not w3.is_connected():
                    continue
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(Config.PUSD_CONTRACT),
                    abi=erc20_abi
                )
                raw = contract.functions.balanceOf(
                    Web3.to_checksum_address(wallet_address)
                ).call()
                return raw / 1e6  # pUSD has 6 decimals
            except Exception as e:
                last_error = f"{rpc}: {e}"
                continue

        print(f"[CLOB] All {len(rpcs)} RPC endpoints failed. Last error: {last_error}", flush=True)
        return None

    # ───────────────────────────────────────────────────────────────
    # AUTH INITIALIZATION (THE CRUCIAL PART)
    # ───────────────────────────────────────────────────────────────

    def init_py_clob_client(self, private_key: str, funder: str = None,
                            signature_type: int = 0) -> Any:
        """
        Initialize py-clob-client-v2 with bulletproof auth flow.
        
        Flow:
          1. Check if user provided manual API creds in .env → use them
          2. Try derive_api_key() (wallet was already enabled on polymarket.com)
          3. Try create_api_key() (new wallet setup)
          4. If ALL fail → raise ClobAuthError with clear instructions
        """
        pk = private_key.strip()
        if not pk.startswith('0x'):
            pk = '0x' + pk

        # Store wallet address for balance queries
        try:
            from eth_account import Account
            self._wallet_address = Account.from_key(pk).address
        except Exception:
            pass

        try:
            return self._init_v2_client(pk, funder, signature_type)
        except ImportError as e:
            print(f"[CLOB] ⚠️  py-clob-client-v2 not installed: {e}", flush=True)
            print(f"[CLOB] 💡 Install: pip install py-clob-client-v2", flush=True)
            raise ClobAuthError("py-clob-client-v2 not installed. Run: pip install py-clob-client-v2")
        except ClobAuthError:
            raise  # Bubble up our clear error
        except Exception as e:
            print(f"[CLOB] ⚠️  V2 init failed: {e}. Trying V1 fallback...", flush=True)
            try:
                return self._init_v1_client(pk, funder, signature_type)
            except Exception as e2:
                raise ClobAuthError(self._format_auth_error(str(e2)))

    def _init_v2_client(self, pk: str, funder: str, signature_type: int) -> Any:
        """Initialize V2 Python SDK with proper auth sequence."""
        from py_clob_client_v2 import ClobClient as PyClobClientV2
        from py_clob_client_v2.clob_types import BuilderConfig as V2BuilderConfig, ApiCreds

        chain_id = Config.POLY_CHAIN_ID

        # Builder config (for order attribution)
        builder_config = None
        builder_code = '0x' + '0' * 64
        if Config.POLY_BUILDER_CODE:
            builder_code = Config.POLY_BUILDER_CODE.strip()
            try:
                builder_config = V2BuilderConfig(
                    builder_address=Config.POLY_PROXY_WALLET.strip() if Config.POLY_PROXY_WALLET else self._wallet_address,
                    builder_code=builder_code,
                )
                print(f"[CLOB] ✅ Builder code configured: {builder_code[:10]}...", flush=True)
            except Exception as e:
                print(f"[CLOB] ⚠️  Builder config failed (non-fatal): {e}", flush=True)

        client = PyClobClientV2(
            host=self.base_url,
            chain_id=chain_id,
            key=pk,
            signature_type=signature_type,
            funder=funder,
            builder_config=builder_config,
        )

        # ═══════════════════════════════════════════════════════════
        # AUTH FLOW (4 attempts in order of preference)
        # ═══════════════════════════════════════════════════════════
        api_key_obj = None
        auth_method = None
        last_error = None

        # METHOD 1: Use manual API creds from .env (if provided)
        if Config.POLY_API_KEY and Config.POLY_API_SECRET and Config.POLY_PASSPHRASE:
            try:
                print(f"[CLOB] 🔑 Using manual API creds from .env", flush=True)
                api_key_obj = ApiCreds(
                    api_key=Config.POLY_API_KEY.strip(),
                    api_secret=Config.POLY_API_SECRET.strip(),
                    api_passphrase=Config.POLY_PASSPHRASE.strip(),
                )
                auth_method = "manual_env"
            except Exception as e:
                last_error = f"Manual creds failed: {e}"
                print(f"[CLOB] ⚠️  {last_error}", flush=True)

        # METHOD 2: Derive existing (if wallet already enabled on polymarket.com)
        if api_key_obj is None:
            try:
                print(f"[CLOB] 🔑 Attempting derive_api_key() (existing registration)...", flush=True)
                api_key_obj = client.derive_api_key()
                auth_method = "derived"
                print(f"[CLOB] ✅ Derived existing API credentials!", flush=True)
            except Exception as e:
                last_error = f"Derive failed: {e}"
                print(f"[CLOB] ⚠️  Derive failed: {e}", flush=True)

        # METHOD 3: Create new (if wallet supports it)
        if api_key_obj is None:
            try:
                print(f"[CLOB] 🔑 Attempting create_api_key() (new registration)...", flush=True)
                api_key_obj = client.create_api_key()
                auth_method = "created"
                print(f"[CLOB] ✅ Created new API credentials!", flush=True)
            except Exception as e:
                last_error = f"Create failed: {e}"
                print(f"[CLOB] ⚠️  Create failed: {e}", flush=True)

        # METHOD 4: create_or_derive (catchall)
        if api_key_obj is None:
            try:
                print(f"[CLOB] 🔑 Attempting create_or_derive_api_key()...", flush=True)
                api_key_obj = client.create_or_derive_api_key()
                auth_method = "create_or_derive"
                print(f"[CLOB] ✅ create_or_derive succeeded!", flush=True)
            except Exception as e:
                last_error = f"create_or_derive failed: {e}"
                print(f"[CLOB] ⚠️  create_or_derive failed: {e}", flush=True)

        # All methods failed → raise clear error
        if api_key_obj is None:
            raise ClobAuthError(self._format_auth_error(last_error or "All auth methods failed"))

        client.set_api_creds(api_key_obj)
        self._api_creds = api_key_obj

        # Connection test
        try:
            ok = client.get_ok()
            print(f"[CLOB] ✅ Connection test passed: {ok}", flush=True)
        except Exception as e:
            print(f"[CLOB] ⚠️  Connection test failed (non-fatal): {e}", flush=True)

        self._py_clob_client = client
        self._is_v2 = True
        self._builder_code = builder_code
        print(f"[CLOB] ✅✅✅ CLOB V2 READY (auth={auth_method}, sig_type={signature_type})", flush=True)
        print(f"[CLOB]      Host:   {self.base_url}", flush=True)
        print(f"[CLOB]      Wallet: {self._wallet_address[:8]}...{self._wallet_address[-4:]}", flush=True)
        if funder:
            print(f"[CLOB]      Funder: {funder[:8]}...{funder[-4:]}", flush=True)
        return client

    def _init_v1_client(self, pk: str, funder: str, signature_type: int) -> Any:
        """V1 fallback."""
        from py_clob_client.client import ClobClient as PyClobClient
        chain_id = Config.POLY_CHAIN_ID
        client = PyClobClient(host=self.base_url, key=pk, chain_id=chain_id,
                              signature_type=signature_type, funder=funder)
        self._api_creds = client.create_or_derive_api_creds()
        client.set_api_creds(self._api_creds)
        self._py_clob_client = client
        self._is_v2 = False
        print(f"[CLOB] ✅ V1 fallback initialized", flush=True)
        return client

    def _format_auth_error(self, underlying: str) -> str:
        """Return a crystal-clear error message with action items."""
        wallet = self._wallet_address or "your wallet"
        return (
            "\n" + "═" * 70 + "\n"
            "❌ POLYMARKET CLOB AUTH FAILED — Wallet not enabled for trading\n"
            "═" * 70 + "\n"
            f"Underlying error: {underlying}\n\n"
            "🔧 HOW TO FIX (2 options):\n\n"
            "  OPTION A: Enable trading on polymarket.com (RECOMMENDED)\n"
            "  ──────────────────────────────────────────────────────\n"
            "  1. Go to https://polymarket.com\n"
            "  2. Connect your wallet (the one with this private key):\n"
            f"       {wallet}\n"
            "  3. Click 'Enable Trading' and sign the popup message\n"
            "     (EIP-712 ClobAuth — FREE, no gas cost)\n"
            "  4. Deposit some USDC → it auto-wraps to pUSD\n"
            "  5. Restart the bot\n\n"
            "  OPTION B: Use manual API credentials in .env\n"
            "  ──────────────────────────────────────────────\n"
            "  If you already have CLOB API creds, set in .env:\n"
            "       POLY_API_KEY=your_key\n"
            "       POLY_API_SECRET=your_secret\n"
            "       POLY_PASSPHRASE=your_passphrase\n"
            "  Get them from polymarket.com → Settings → API\n\n"
            "  💡 FOR NOW: Run in paper mode to test strategies:\n"
            "       python dashboard.py --paper\n"
            "═" * 70
        )

    # ───────────────────────────────────────────────────────────────
    # ORDER PLACEMENT
    # ───────────────────────────────────────────────────────────────

    def place_market_order(self, token_id: str, side: str, size_pusd: float,
                           price: float = None) -> Optional[Dict]:
        if not self._py_clob_client:
            print("[CLOB] ❌ Client not initialized — cannot place order", flush=True)
            return None
        size_pusd = max(size_pusd, Config.POLYMARKET_MIN_ORDER_SIZE)
        try:
            if self._is_v2:
                return self._place_order_v2(token_id, side, size_pusd, price, 'FOK')
            else:
                return self._place_order_v1(token_id, side, size_pusd, price, 'FOK')
        except Exception as e:
            print(f"[CLOB] ❌ FOK order failed: {e}", flush=True)
            return None

    def place_limit_order(self, token_id: str, side: str, price: float,
                          size_pusd: float, expiration: str = "GTC",
                          neg_risk: bool = False) -> Optional[Dict]:
        if not self._py_clob_client:
            print("[CLOB] ❌ Client not initialized — cannot place limit order", flush=True)
            return None
        size_pusd = max(size_pusd, Config.POLYMARKET_MIN_ORDER_SIZE)
        try:
            if self._is_v2:
                return self._place_order_v2(token_id, side, size_pusd, price, expiration.upper(), neg_risk)
            else:
                return self._place_order_v1(token_id, side, size_pusd, price, expiration.upper())
        except Exception as e:
            print(f"[CLOB] ❌ Limit order failed: {e}", flush=True)
            return None

    def _calculate_shares(self, price, size_pusd, is_fok=True):
        price = round(float(price), 2)
        price = max(0.01, min(0.99, price))
        min_shares = 1 if is_fok else 5
        shares = math.floor(size_pusd / price * 100) / 100
        if shares < min_shares:
            shares = float(min_shares)
        P = int(round(price * 100))
        S = int(math.floor(shares * 100))
        if P > 0 and S > 0:
            step = 100 // math.gcd(P, 100)
            S = (S // step) * step
            if S < min_shares * 100:
                S = ((min_shares * 100 + step - 1) // step) * step
            shares = S / 100.0
        order_amount = round(price * shares, 2)
        if order_amount < Config.POLYMARKET_MIN_ORDER_SIZE:
            shares = math.ceil(Config.POLYMARKET_MIN_ORDER_SIZE / price * 100) / 100
            shares = max(float(min_shares), shares)
            order_amount = round(price * shares, 2)
        return shares, order_amount

    def _place_order_v2(self, token_id, side, size_pusd, price, order_type, neg_risk=False):
        from py_clob_client_v2.clob_types import (
            OrderArgs as OrderArgsV2, OrderType as V2OrderType, PartialCreateOrderOptions
        )
        from py_clob_client_v2.order_builder.constants import BUY, SELL

        side_const = BUY if side.upper() == 'BUY' else SELL
        if price is None or price <= 0:
            price = 0.50
        price = max(0.01, min(0.99, round(price, 2)))
        is_fok = order_type in ('FOK', 'IOC', 'FAK')
        shares, order_amount = self._calculate_shares(price, size_pusd, is_fok)

        print(f"[CLOB] 📤 V2 {order_type} {side} {shares:.2f}sh @ ${price:.2f} = ${order_amount:.2f} pUSD", flush=True)

        order_args = OrderArgsV2(
            token_id=token_id, side=side_const, price=price, size=shares,
            builder_code=self._builder_code,
        )
        options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=neg_risk)
        signed_order = self._py_clob_client.create_order(order_args, options)
        type_map = {'GTC': V2OrderType.GTC, 'FOK': V2OrderType.FOK, 'FAK': V2OrderType.FAK}
        v2_type = type_map.get(order_type, V2OrderType.GTC)
        resp = self._py_clob_client.post_order(signed_order, v2_type)
        order_id = resp.get('orderID') or resp.get('order_id') or resp.get('id', 'unknown')
        status = resp.get('status', 'UNKNOWN')
        print(f"[CLOB] ✅ Order placed: id={order_id} status={status}", flush=True)
        return {
            'order_id': order_id, 'status': status,
            'price': price, 'size': shares, 'size_pusd': order_amount,
            'side': side, 'type': order_type,
        }

    def _place_order_v1(self, token_id, side, size_pusd, price, order_type):
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL
        side_const = BUY if side.upper() == 'BUY' else SELL
        if price is None or price <= 0:
            price = 0.50
        is_fok = order_type in ('FOK', 'IOC')
        shares, order_amount = self._calculate_shares(price, size_pusd, is_fok)
        order_args = OrderArgs(token_id=token_id, side=side_const, price=price, size=shares)
        signed_order = self._py_clob_client.create_order(order_args)
        v1_type = OrderType.FOK if is_fok else OrderType.GTC
        resp = self._py_clob_client.post_order(signed_order, v1_type)
        order_id = resp.get('orderID') or resp.get('order_id') or resp.get('id', 'unknown')
        return {
            'order_id': order_id, 'status': resp.get('status', 'UNKNOWN'),
            'price': price, 'size': shares, 'size_pusd': order_amount,
            'side': side, 'type': order_type,
        }

    def cancel_order(self, order_id: str) -> bool:
        if not self._py_clob_client:
            return False
        try:
            self._py_clob_client.cancel(order_id)
            return True
        except Exception as e:
            print(f"[CLOB] ❌ Cancel failed: {e}", flush=True)
            return False

    def cancel_all_orders(self) -> bool:
        if not self._py_clob_client:
            return False
        try:
            self._py_clob_client.cancel_all()
            return True
        except Exception as e:
            print(f"[CLOB] ❌ Cancel all failed: {e}", flush=True)
            return False

    def send_heartbeat(self) -> bool:
        """V2: Keep orders alive. No-op if client not initialized."""
        if not self._py_clob_client:
            return False
        try:
            if hasattr(self._py_clob_client, 'heartbeat'):
                self._py_clob_client.heartbeat()
                return True
        except Exception:
            pass
        return False

    # ───────────────────────────────────────────────────────────────
    # ORDER STATUS TRACKING
    # ───────────────────────────────────────────────────────────────

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Fetch full order record from CLOB.
        Returns dict with at least: status, size_matched (str), size (str).

        Status values observed from V2:
          LIVE       — open, unmatched
          MATCHED    — fully filled
          CANCELED   — canceled by user or system
          DELAYED    — processing
          UNMATCHED  — never filled (FOK failed)
          REJECTED   — rejected by validation

        Returns None on failure (e.g. network).
        """
        if not self._py_clob_client or not order_id:
            return None
        try:
            order = self._py_clob_client.get_order(order_id)
            # SDK returns a dict; normalize keys we rely on
            if not isinstance(order, dict):
                try:
                    order = dict(order)
                except Exception:
                    return None
            # Normalize status
            status = (order.get('status') or order.get('state') or 'UNKNOWN')
            order['status'] = str(status).upper()
            return order
        except Exception as e:
            msg = str(e).lower()
            # 404 / not-found often means order was instantly matched and
            # pruned from the open-order store — treat as possibly-filled
            if 'not found' in msg or '404' in msg:
                return {'status': 'NOT_FOUND', '_gone': True}
            return None

    def is_order_filled(self, order_id: str) -> Tuple[Optional[bool], Optional[Dict]]:
        """
        Returns (filled_bool, raw_order).
          filled_bool = True  if fully or partially matched
          filled_bool = False if still LIVE/DELAYED (pending)
          filled_bool = None  if terminal non-fill (CANCELED / UNMATCHED /
                              REJECTED / NOT_FOUND) — caller should drop it
        """
        raw = self.get_order_status(order_id)
        if raw is None:
            return False, None  # network hiccup — treat as still pending

        status = raw.get('status', 'UNKNOWN')

        try:
            size_matched = float(raw.get('size_matched', 0) or 0)
        except (ValueError, TypeError):
            size_matched = 0.0

        if size_matched > 0 or status == 'MATCHED':
            return True, raw

        if status in ('CANCELED', 'CANCELLED', 'UNMATCHED', 'REJECTED',
                      'EXPIRED', 'NOT_FOUND'):
            return None, raw

        # LIVE / DELAYED / UNKNOWN — still pending
        return False, raw

    def get_trades_for_order(self, order_id: str) -> List[Dict]:
        """Return fills list for a given order_id (used to compute avg price)."""
        if not self._py_clob_client:
            return []
        try:
            from py_clob_client_v2.clob_types import TradeParams
            trades = self._py_clob_client.get_trades(
                TradeParams(id=order_id), only_first_page=True
            ) or []
            return list(trades)
        except Exception:
            return []

    def get_fill_price(self, order_id: str, fallback: float = 0.0) -> float:
        """Average fill price for this order, or fallback."""
        trades = self.get_trades_for_order(order_id)
        if not trades:
            return fallback
        total_sz = 0.0
        total_px = 0.0
        for t in trades:
            try:
                sz = float(t.get('size', 0) or 0)
                px = float(t.get('price', 0) or 0)
                if sz > 0 and px > 0:
                    total_sz += sz
                    total_px += sz * px
            except Exception:
                continue
        return (total_px / total_sz) if total_sz > 0 else fallback

    def place_fok_order(self, token_id: str, side: str, price: float,
                        size_pusd: float, neg_risk: bool = False) -> Optional[Dict]:
        """
        Place a fill-or-kill limit order.
        Used for high-conviction entries where we need immediate execution
        at a specific price (taker-style) — either fully fills or cancels.
        """
        if not self._py_clob_client:
            print("[CLOB] ❌ Client not initialized — cannot place FOK order", flush=True)
            return None
        size_pusd = max(size_pusd, Config.POLYMARKET_MIN_ORDER_SIZE)
        try:
            if self._is_v2:
                return self._place_order_v2(token_id, side, size_pusd, price, 'FOK', neg_risk)
            else:
                return self._place_order_v1(token_id, side, size_pusd, price, 'FOK')
        except Exception as e:
            print(f"[CLOB] ❌ FOK order failed: {e}", flush=True)
            return None

    def is_initialized(self) -> bool:
        return self._py_clob_client is not None

    def get_wallet_address(self) -> str:
        return self._wallet_address
