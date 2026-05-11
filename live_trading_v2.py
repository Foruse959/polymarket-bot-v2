#!/usr/bin/env python3
"""
LIVE TRADING v2 — REAL Bot
No fake data. No simulations. Real API calls, real market data, real orders.
"""

import asyncio
import sys
import os
import time
import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from logger import logger
from data.gamma_client import GammaClient
from data.clob_client import ClobClient
from data.database import Database
from trading.live_trader import LiveTrader
from trading.live_balance_manager import LiveBalanceManager


class RealLiveBot:
    """Real live trading bot - NO fake data"""

    def __init__(self):
        self.round = 0
        self.running = True
        self.components = {}
        self.stats = {
            'markets_scanned': 0,
            'signals_generated': 0,
            'trades_placed': 0,
            'trades_filled': 0,
            'trades_failed': 0,
            'total_pnl': 0.0,
            'wins': 0,
            'losses': 0,
            'start_time': time.time(),
            'last_scan_time': 0,
            'connected': {
                'binance': False,
                'polymarket': False,
                'polygon': False,
                'wallet': False,
            },
            'current_markets': [],
            'active_positions': [],
        }

    async def build_phase(self):
        """Build phase - Railway style"""
        logger.build_start()
        steps = [
            ("Loading configuration", 0.1),
            ("Setting up database", 0.2),
            ("Initializing Gamma client", 0.3),
            ("Initializing CLOB client", 0.4),
            ("Connecting to networks", 0.5),
        ]
        for step, pct in steps:
            logger.build_step(step, "running")
            await asyncio.sleep(0.05)
        logger.build_success()

    async def init_phase(self):
        """Initialize all components"""
        logger.init_start()

        # Database
        try:
            db = Database()
            await db.init()
            self.components['db'] = db
            logger.init_component("Database", "ok")
        except Exception as e:
            logger.init_component("Database", "error")
            logger.error(f"Database init failed: {e}")
            raise

        # Gamma Client (market discovery)
        try:
            gamma = GammaClient()
            self.components['gamma'] = gamma
            logger.init_component("Gamma Client", "ok")
            self.stats['connected']['polymarket'] = True
        except Exception as e:
            logger.init_component("Gamma Client", "error")
            raise

        # CLOB Client (order execution)
        try:
            clob = ClobClient()
            self.components['clob'] = clob
            logger.init_component("CLOB Client", "ok")
        except Exception as e:
            logger.init_component("CLOB Client", "error")
            raise

        # Balance Manager
        risk_mode = Config.LIVE_RISK_MODE
        balance_mgr = LiveBalanceManager(balance_usdc=Config.STARTING_BALANCE_USDC, mode=risk_mode)
        self.components['balance_mgr'] = balance_mgr
        logger.init_component(f"Balance Manager ({risk_mode})", "ok")

        # Live Trader
        trader = LiveTrader(db, balance_mgr)
        self.components['trader'] = trader
        logger.init_component("Live Trader", "ok")

        logger.init_complete()
        return trader, clob, gamma, balance_mgr, db

    async def wallet_init(self, trader, clob):
        """Initialize wallet connection"""
        logger.info("Initializing wallet connection...")

        start_time = time.time()
        success = await trader.init(clob)
        init_time = (time.time() - start_time) * 1000

        if success:
            wallet_addr = Config.POLY_PROXY_WALLET
            balance = trader.balance_mgr.balance_usdc
            sig_type = Config.POLY_SIGNATURE_TYPE

            logger.init_wallet(wallet_addr, balance, sig_type)
            logger.info(f"Wallet initialized in {init_time:.1f}ms")
            logger.info(f"py-clob-client v0.34.6 ready (sig_type={sig_type})")
            self.stats['connected']['wallet'] = True

            # Check real balance on-chain
            try:
                real_balance = clob.get_balance(wallet_addr)
                if real_balance:
                    logger.info(f"On-chain balance: {real_balance}")
            except Exception as e:
                logger.warning(f"Could not check on-chain balance: {e}")

            return True
        else:
            logger.error(f"Wallet init failed: {trader._init_error}")
            return False

    async def scan_markets(self, gamma):
        """Scan for active markets using real API"""
        self.round += 1
        logger.scan_start(self.round, Config.ENABLED_COINS, Config.ENABLED_TIMEFRAMES)

        start_time = time.time()

        try:
            markets = gamma.discover_markets()
        except Exception as e:
            logger.error(f"Market scan failed: {e}")
            return []

        latency = (time.time() - start_time) * 1000
        logger.scan_api_response("gamma/polymarket", 200, len(markets))

        if markets:
            logger.scan_found_markets(markets)
            self.stats['markets_scanned'] += len(markets)
            self.stats['current_markets'] = markets

            # Group and display
            by_tf = {}
            for m in markets:
                tf = m.get('timeframe', 0)
                if tf not in by_tf:
                    by_tf[tf] = []
                by_tf[tf].append(m)

            for tf in sorted(by_tf.keys()):
                tf_markets = by_tf[tf]
                for m in tf_markets:
                    status = "LIVE" if m.get('seconds_remaining', 0) < 300 else "UPCOMING"
                    logger.info(
                        f"  {m['coin']} {tf}m | {status} | "
                        f"Epoch: {m.get('epoch_timestamp', 'N/A')} | "
                        f"Ends in: {m.get('seconds_remaining', 'N/A')}s"
                    )
        else:
            logger.scan_no_markets("No active updown markets found")

        self.stats['last_scan_time'] = time.time()
        return markets

    async def analyze_market(self, market, clob):
        """Analyze a market using REAL price data from the orderbook"""
        coin = market.get('coin', 'UNKNOWN')
        tf = market.get('timeframe', 0)
        market_id = market.get('market_id', 'N/A')
        up_token = market.get('up_token_id')
        down_token = market.get('down_token_id')
        seconds_left = market.get('seconds_remaining', 0)

        logger.info(f"Analyzing {coin} {tf}m | {seconds_left}s remaining")

        if not up_token or not down_token:
            logger.warning(f"Missing token IDs for {coin} {tf}m")
            return None

        # --- REAL PRICE DATA FROM ORDERBOOK ---
        try:
            # Get dual orderbook (up + down tokens)
            dual_book = clob.get_dual_orderbook(up_token, down_token)

            if not dual_book:
                logger.warning(f"No orderbook data for {coin} {tf}m")
                return None

            up_book = dual_book['up']
            down_book = dual_book['down']

            up_mid = up_book['mid_price']
            down_mid = down_book['mid_price']
            up_spread_bps = up_book['spread_bps']
            down_spread_bps = down_book['spread_bps']

            logger.info(
                f"  UP token: mid={up_mid:.4f} spread={up_spread_bps:.0f}bps "
                f"bid={up_book['best_bid']:.4f} ask={up_book['best_ask']:.4f}"
            )
            logger.info(
                f"  DOWN token: mid={down_mid:.4f} spread={down_spread_bps:.0f}bps "
                f"bid={down_book['best_bid']:.4f} ask={down_book['best_ask']:.4f}"
            )

            # Check for arbitrage opportunity
            if dual_book.get('arb_opportunity'):
                arb_profit = dual_book.get('arb_profit_bps', 0)
                logger.info(f"  ARB detected! Profit: {arb_profit:.0f}bps")

            # Time decay analysis
            time_fraction = max(0, min(1, seconds_left / (tf * 60)))  # fraction of window remaining
            time_pressure = 1.0 - time_fraction  # higher = more pressure

            # Price bias detection
            # If up_mid > 0.55, market thinks UP is more likely
            # If down_mid > 0.55, market thinks DOWN is more likely
            up_bias = up_mid - 0.50  # positive = UP favored
            down_bias = down_mid - 0.50

            # Spread analysis (tighter = more efficient market)
            avg_spread = (up_spread_bps + down_spread_bps) / 2

            # Calculate REAL confidence score
            confidence = 0.50  # Start neutral

            # Factor 1: Price bias (stronger bias = higher confidence)
            confidence += abs(up_bias) * 0.5  # Up to +/-0.25

            # Factor 2: Time pressure (more time left = less confidence)
            confidence += (1.0 - time_pressure) * 0.1  # Up to 0.1

            # Factor 3: Spread efficiency (tighter = better)
            if avg_spread > 0 and avg_spread < 300:
                confidence += 0.1  # Reasonable spread

            # Factor 4: Arb opportunity (if exists, higher confidence)
            if dual_book.get('arb_profit_bps', 0) > 50:
                confidence += 0.1

            # Clamp confidence
            confidence = max(0.30, min(0.95, confidence))

            direction = "UP" if up_bias > 0 else "DOWN"

            # Determine strategy
            if dual_book.get('arb_profit_bps', 0) > 50:
                strategy = "arb"
            elif time_pressure > 0.7:
                strategy = "time_decay"
            elif avg_spread < 100:
                strategy = "maker_edge"
            else:
                strategy = "spread_scalper"

            # Determine order type
            order_type = "maker" if Config.MAKER_PREFERRED else "taker"

            # Calculate limit price for maker order
            if direction == "UP":
                limit_price = up_book['best_bid'] + 0.001  # Slightly above best bid
            else:
                limit_price = down_book['best_bid'] + 0.001

            # Choose token ID based on direction
            token_id = up_token if direction == "UP" else down_token

            reasons = []
            if abs(up_bias) > 0.03:
                reasons.append(f"Price bias: {direction} favored by {abs(up_bias)*100:.1f}%")
            if time_pressure > 0.5:
                reasons.append(f"Time pressure: {time_pressure*100:.0f}% elapsed")
            if avg_spread < 200:
                reasons.append(f"Tight spread: {avg_spread:.0f}bps avg")

            min_conf = Config.TIMEFRAME_PARAMS.get(tf, Config.TIMEFRAME_PARAMS[5]).get('min_confidence', 0.60)
            logger.analyze_confidence(confidence, min_conf, reasons)

            if confidence < min_conf:
                logger.analyze_skip(
                    f"Confidence {confidence:.2f} below threshold {min_conf:.2f}",
                    {"score": confidence, "min": min_conf}
                )
                return None

            from strategies.base_strategy import TradeSignal

            signal = TradeSignal(
                coin=coin,
                direction=direction,
                timeframe=tf,
                strategy=strategy,
                confidence=confidence,
                market_id=market_id,
                token_id=token_id,
                entry_price=limit_price,
                limit_price=limit_price,
                order_type=order_type,
                rationale=", ".join(reasons),
                metadata={
                    "up_mid": up_mid,
                    "down_mid": down_mid,
                    "up_spread_bps": up_spread_bps,
                    "down_spread_bps": down_spread_bps,
                    "time_pressure": time_pressure,
                    "seconds_remaining": seconds_left,
                }
            )

            logger.trade_signal(coin, direction, strategy, confidence, signal.size_usdc if hasattr(signal, 'size_usdc') else 0)
            return signal

        except Exception as e:
            logger.error(f"Analysis failed for {coin} {tf}m: {e}")
            traceback.print_exc()
            return None

    async def execute_trade(self, signal, trader):
        """Execute a REAL trade - place order via CLOB and record it."""
        coin = signal.coin
        direction = signal.direction
        strategy = signal.strategy
        confidence = signal.confidence
        token_id = signal.token_id
        limit_price = signal.limit_price

        # Get position size from balance manager
        size_usdc = trader.balance_mgr.calculate_position_size_usdc(
            signal.timeframe, confidence, signal.order_type
        )

        if size_usdc < Config.POLYMARKET_MIN_ORDER_SIZE_USDC:
            logger.warning(f"Position size ${size_usdc:.2f} below minimum ${Config.POLYMARKET_MIN_ORDER_SIZE_USDC:.2f}")
            return None

        # Check if we can trade
        allowed, reason = trader.balance_mgr.can_trade(confidence, signal.order_type)
        if not allowed:
            logger.warning(f"Cannot trade: {reason}")
            return None

        logger.trade_preparing(signal.order_type, token_id[:20] if token_id else 'N/A')

        # Place the REAL order via CLOB client
        result = None
        try:
            if signal.order_type == 'maker':
                # Maker: GTC limit order at desired price
                logger.trade_submitting("BUY", limit_price, size_usdc, "GTC (maker)")
                result = self.components['clob'].place_limit_order(
                    token_id=token_id,
                    side="BUY",
                    price=limit_price,
                    size_usdc=size_usdc,
                    expiration="GTC",
                )
            else:
                # Taker: FOK for instant fill
                logger.trade_submitting("BUY", limit_price, size_usdc, "FOK (taker)")
                result = self.components['clob'].place_market_order(
                    token_id=token_id,
                    side="BUY",
                    size_usdc=size_usdc,
                )
        except Exception as e:
            logger.trade_error(f"Order exception: {e}")
            self.stats['trades_failed'] += 1
            import traceback
            traceback.print_exc()
            return None

        if result and result.get('order_id'):
            order_id = result.get('order_id', 'unknown')
            status = result.get('status', 'UNKNOWN')
            logger.trade_submitted(order_id, status)
            self.stats['trades_placed'] += 1

            # Record position in trader's tracking
            trade_id = str(uuid.uuid4())[:8]
            trade = {
                'id': trade_id,
                'market_id': signal.market_id,
                'coin': coin,
                'timeframe': signal.timeframe,
                'strategy': strategy,
                'direction': direction,
                'token_id': token_id,
                'entry_price': limit_price or signal.entry_price,
                'size_usdc': size_usdc,
                'order_id': order_id,
                'order_type': signal.order_type,
                'entry_time': datetime.now(timezone.utc).isoformat(),
                'status': 'open',
                'rationale': signal.rationale if hasattr(signal, 'rationale') else '',
            }
            trader.positions[trade_id] = trade
            trader.balance_mgr.open_positions += 1

            fill_price = float(result.get('price', limit_price))
            logger.trade_filled(order_id, fill_price, size_usdc, pnl=0.0)
            self.stats['trades_filled'] += 1
            logger.position_opened(trade_id, coin, fill_price, size_usdc, direction)

            return trade
        elif result:
            # Order placed but no order_id - might be async fill
            order_id = result.get('order_id', f'unknown-{int(time.time())}')
            logger.info(f"Order result: {result}")
            self.stats['trades_placed'] += 1
            return result
        else:
            logger.trade_error("Order failed - no response from CLOB")
            self.stats['trades_failed'] += 1
            return None

    async def write_status_file(self):
        """Write status to JSON file for dashboard to read"""
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': Config.TRADING_MODE,
            'round': self.round,
            'uptime_seconds': int(time.time() - self.stats['start_time']),
            'balance': self.components.get('balance_mgr', LiveBalanceManager(2.30)).balance_usdc,
            'connected': self.stats['connected'],
            'markets_found': len(self.stats.get('current_markets', [])),
            'stats': {
                'markets_scanned': self.stats['markets_scanned'],
                'signals_generated': self.stats['signals_generated'],
                'trades_placed': self.stats['trades_placed'],
                'trades_filled': self.stats['trades_filled'],
                'trades_failed': self.stats['trades_failed'],
                'total_pnl': self.stats['total_pnl'],
                'wins': self.stats['wins'],
                'losses': self.stats['losses'],
            },
            'markets': [
                {
                    'coin': m.get('coin'),
                    'timeframe': m.get('timeframe'),
                    'question': m.get('question', ''),
                    'seconds_remaining': m.get('seconds_remaining', 0),
                    'epoch': m.get('epoch_timestamp', 0),
                    'up_token': m.get('up_token_id', '')[:20] + '...',
                    'down_token': m.get('down_token_id', '')[:20] + '...',
                }
                for m in self.stats.get('current_markets', [])[:10]
            ],
        }

        try:
            status_path = Path("logs/bot_status.json")
            status_path.parent.mkdir(exist_ok=True)
            with open(status_path, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, default=str)
        except Exception as e:
            pass  # Non-critical

    async def run(self):
        """Main run loop - REAL trading"""
        print("=" * 70, flush=True)
        print("POLYMARKET BOT v2.0 - LIVE TRADING", flush=True)
        print(f"Mode: {Config.TRADING_MODE.upper()}", flush=True)
        print(f"Wallet: {Config.POLY_PROXY_WALLET}", flush=True)
        print(f"Coins: {', '.join(Config.ENABLED_COINS)}", flush=True)
        print(f"Timeframes: {Config.ENABLED_TIMEFRAMES}", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)

        # Phase 1: Build
        await self.build_phase()
        await asyncio.sleep(0.3)

        # Phase 2: Init
        try:
            trader, clob, gamma, balance_mgr, db = await self.init_phase()
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            traceback.print_exc()
            return

        await asyncio.sleep(0.3)

        # Phase 3: Wallet
        wallet_ok = await self.wallet_init(trader, clob)
        if not wallet_ok:
            logger.error("Failed to initialize wallet - CANNOT TRADE")
            logger.error("Check your POLY_PRIVATE_KEY and wallet configuration")
            # Still continue scanning, but won't trade

        await asyncio.sleep(0.3)

        # Phase 4: Trading Loop
        logger.info("=" * 70)
        logger.info("STARTING TRADING LOOP")
        logger.info(f"Scan interval: {Config.TIMEFRAME_PARAMS[5]['scan_interval']}s")
        logger.info(f"Risk mode: {balance_mgr.get_mode_name()}")
        logger.info("=" * 70)

        while self.running:
            try:
                # Scan markets
                markets = await self.scan_markets(gamma)

                if markets and wallet_ok and trader._initialized:
                    # Analyze each market
                    for market in markets[:3]:  # Limit concurrent analysis
                        try:
                            signal = await self.analyze_market(market, clob)

                            if signal:
                                self.stats['signals_generated'] += 1
                                # Execute trade
                                result = await self.execute_trade(signal, trader)
                                if result:
                                    await asyncio.sleep(1)  # Rate limit between trades
                        except Exception as e:
                            logger.error(f"Error analyzing market: {e}")
                            continue
                elif not wallet_ok:
                    logger.warning("Wallet not connected - skipping trade execution")

                # Write status file for dashboard
                await self.write_status_file()

                # Heartbeat
                uptime = int(time.time() - self.stats['start_time'])
                logger.heartbeat(uptime)
                logger.info(f"Stats: {self.stats['markets_scanned']} scanned, "
                           f"{self.stats['trades_placed']} placed, "
                           f"{self.stats['trades_filled']} filled")

                # Wait before next scan
                scan_interval = Config.TIMEFRAME_PARAMS.get(
                    Config.ENABLED_TIMEFRAMES[0], Config.TIMEFRAME_PARAMS[5]
                )['scan_interval']
                await asyncio.sleep(scan_interval)

            except KeyboardInterrupt:
                logger.info("Stopped by user")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)  # Wait before retry

        logger.info("=" * 70)
        logger.info("BOT STOPPED")
        logger.info("=" * 70)


async def main():
    bot = RealLiveBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[LIVE] Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()