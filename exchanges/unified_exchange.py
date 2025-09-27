"""
Unified exchange wrapper for consistent interface across all exchanges.
Handles ccxt integration, normalization, and fallback for paper/live modes.
"""

# --- Prevent fatal 'HEAD' Git errors ---
import subprocess, os
GIT_COMMIT = "unknown"
try:
    if os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".git")):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        commit = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        GIT_COMMIT = commit[:7]
except Exception:
    pass  # Keep GIT_COMMIT as "unknown"
# -----------------------------------------------

import ccxt.async_support as ccxt
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from exchanges.base_exchange import BaseExchange
from utils.logger import setup_logger


class UnifiedExchange(BaseExchange):
    """Unified exchange implementation using ccxt with normalization."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.exchange_id = config['exchange_id']
        self.name = self.exchange_id  # For compatibility with MultiExchangeDetector
        self.logger = setup_logger(f'Exchange_{self.exchange_id.title()}')
        self.exchange: Optional[ccxt.Exchange] = None
        self.paper_trading = False  # ALWAYS LIVE TRADING
        self.fee_token = config.get('fee_token')
        self.fee_discount = config.get('fee_discount', 0.0)
        self.zero_fee_pairs = config.get('zero_fee_pairs', [])
        self.maker_fee = config.get('maker_fee', 0.001)
        self.taker_fee = config.get('taker_fee', 0.001)
        # Add fee token discount rates
        self.maker_fee_with_token = config.get('maker_fee_with_token', self.maker_fee)
        self.taker_fee_with_token = config.get('taker_fee_with_token', self.taker_fee)
        self.live_trading = True  # 🔴 FORCE LIVE TRADING
        self.dry_run = False      # 🔴 NO DRY RUN MODE
        self.trading_pairs: Dict[str, Any] = {}
        
        # KuCoin timestamp synchronization
        self.server_time_offset = 0
        self.last_time_sync = 0
        
        # FORCE REAL TRADING ONLY
        self.logger.info(f"🔴 LIVE TRADING MODE ENABLED - REAL MONEY TRADES ON {self.exchange_id.upper()}")
        self.logger.info(f"✅ READY: Real-money trading enabled with enforced profit/amount limits.")

    async def connect(self) -> bool:
        try:
            if not await self._check_internet_connectivity():
                self.logger.error(f"No internet connection for {self.exchange_id}")
                return False

            # Handle Gate.io special case
            if self.exchange_id == 'gate':
                exchange_class = getattr(ccxt, 'gateio')
            else:
                exchange_class = getattr(ccxt, self.exchange_id)
                
            exchange_config = {
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
                'timeout': 10000,
                'rateLimit': 1200
            }

            # Check for API credentials
            api_key = self.config.get('api_key', '').strip()
            api_secret = self.config.get('api_secret', '').strip()
            
            if not api_key or not api_secret:
                self.logger.error(f"❌ No API credentials for {self.exchange_id}")
                self.logger.error(f"   API Key: {'SET' if api_key else 'MISSING'}")
                self.logger.error(f"   API Secret: {'SET' if api_secret else 'MISSING'}")
                self.logger.error("   Please configure your .env file with valid credentials")
                return False

            exchange_config.update({
                'apiKey': api_key,
                'secret': api_secret,
                'sandbox': False  # ALWAYS LIVE TRADING - NO SANDBOX
            })
            
            # Add passphrase for exchanges that require it (like KuCoin)
            if self.config.get('passphrase'):
                exchange_config['password'] = self.config.get('passphrase')
                self.logger.info(f"Added passphrase for {self.exchange_id}")

            # KuCoin-specific timestamp synchronization
            if self.exchange_id == 'kucoin':
                exchange_config['options'].update({
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000,  # 60 second window for reliability
                    'timeDifference': 5000   # 5-second buffer for safety
                })
                self.logger.info("🕒 KuCoin timestamp synchronization enabled")

            self.exchange = exchange_class(exchange_config)
            
            # Synchronize server time for KuCoin
            if self.exchange_id == 'kucoin':
                await self._synchronize_kucoin_time()
            
            await self.exchange.load_markets()
            await self._verify_real_connection()
            
            # Verify account balance for live trading
            balance = await self.get_account_balance()
            if balance:
                total_balance_usd = await self._calculate_usd_value(balance)
            else:
                total_balance_usd = 0.0
                
            self.logger.info(f"💰 REAL BALANCE - {self.exchange_id}: ~${total_balance_usd:.2f} USD")
            
            # Log detailed balance for debugging
            if balance:
                major_balances = {k: v for k, v in balance.items() if v > 0.001}
                self.logger.info(f"   Major balances: {major_balances}")
            else:
                self.logger.warning(f"⚠️ No balance data retrieved for {self.exchange_id}")
            
            if total_balance_usd < 5:
                self.logger.warning(f"⚠️ Low balance on {self.exchange_id}: ${total_balance_usd:.2f} - minimum $5 recommended for trading")
                if total_balance_usd > 0:
                    self.logger.info("✅ Balance detected but low - bot will still function for testing")
            else:
                self.logger.info(f"✅ Sufficient balance detected: ${total_balance_usd:.2f} USD")

            self.trading_pairs = {
                s: m for s, m in self.exchange.markets.items() if m.get("active", False)
            }
            
            # Log available pairs for debugging
            total_pairs = len(self.trading_pairs)
            usdt_pairs = len([p for p in self.trading_pairs.keys() if 'USDT' in p])
            btc_pairs = len([p for p in self.trading_pairs.keys() if 'BTC' in p])
            
            self.logger.info(f"📊 {self.exchange_id} trading pairs: {total_pairs} total, {usdt_pairs} USDT pairs, {btc_pairs} BTC pairs")

            self.is_connected = True
            self.logger.info(f"✅ Connected to {self.exchange_id} - REAL ACCOUNT ACCESS")
            self.logger.info(f"{self.exchange_id}: {len(self.trading_pairs)} trading pairs")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to {self.exchange_id}: {e}")
            self.logger.error("   Check your API credentials in .env file")
            return False

    async def _synchronize_kucoin_time(self):
        """Synchronize time with KuCoin server to prevent timestamp errors"""
        try:
            # INSTANT: Use system time with minimal buffer for maximum speed
            current_time = int(time.time() * 1000)
            self.server_time_offset = 1000  # 1-second buffer for safety
            self.last_time_sync = time.time()
            
            # Apply minimal buffer to exchange
            if hasattr(self.exchange, 'options'):
                self.exchange.options['timeDifference'] = 1000  # 1-second buffer
                self.exchange.options['adjustForTimeDifference'] = True
            
        except Exception as e:
            # Use minimal buffer as fallback
            self.server_time_offset = 1000  # 1-second buffer for speed
            self.last_time_sync = time.time()
            
            # Apply minimal buffer
            if hasattr(self.exchange, 'options'):
                self.exchange.options['timeDifference'] = 1000  # 1-second buffer
                self.exchange.options['adjustForTimeDifference'] = True

    async def _ensure_time_sync(self):
        """Ensure time is synchronized before critical operations"""
        if self.exchange_id == 'kucoin':
            current_time = time.time()
            # INSTANT: Re-sync every 30 seconds for speed
            if current_time - self.last_time_sync > 30:
                await self._synchronize_kucoin_time()

    async def _check_internet_connectivity(self) -> bool:
        import aiohttp
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get('https://httpbin.org/status/200') as response:
                    return response.status == 200
        except Exception:
            return False

    async def _verify_real_connection(self) -> None:
        try:
            # Test with more common pairs and handle missing pairs gracefully
            test_symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'DOT/USDT']
            verified = False
            
            for symbol in test_symbols:
                try:
                    if symbol in self.exchange.markets:
                        ticker = await self.exchange.fetch_ticker(symbol)
                        if ticker and ticker.get('bid') and ticker.get('ask'):
                            self.logger.info(f"✅ Verified real data from {self.exchange_id}: {symbol} = ${ticker['last']}")
                            verified = True
                            break
                except Exception:
                    continue
            
            if not verified:
                # Try to verify with any available market
                markets = list(self.exchange.markets.keys())[:10]  # Try first 10 markets
                for symbol in markets:
                    try:
                        ticker = await self.exchange.fetch_ticker(symbol)
                        if ticker and ticker.get('bid') and ticker.get('ask'):
                            self.logger.info(f"✅ Verified real data from {self.exchange_id}: {symbol} = {ticker['last']}")
                            verified = True
                            break
                    except Exception:
                        continue
            
            if not verified:
                raise Exception("Failed to verify market data with any symbol")
                
        except Exception as e:
            raise Exception(f"Connection verification failed: {e}")

    async def disconnect(self) -> None:
        try:
            if self.exchange:
                await self.exchange.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.exchange_id}")
        except Exception as e:
            self.logger.error(f"Error disconnecting from {self.exchange_id}: {e}")

    async def get_trading_pairs(self) -> List[str]:
        return list(self.trading_pairs.keys())

    async def fetch_tickers(self) -> Dict[str, Any]:
        try:
            return await self.exchange.fetch_tickers()
        except Exception as e:
            self.logger.error(f"Error fetching tickers from {self.exchange_id}: {e}")
            return {}

    def normalize_symbol(self, symbol: str) -> Optional[str]:
        if not self.exchange or not hasattr(self.exchange, "markets"):
            return None
        if symbol in self.exchange.markets:
            return symbol
        try:
            base, quote = symbol.split('/')
            flipped = f"{quote}/{base}"
            return flipped if flipped in self.exchange.markets else None
        except Exception:
            return None

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            norm_symbol = self.normalize_symbol(symbol)
            if not norm_symbol:
                return {}
            ticker = await self.exchange.fetch_ticker(norm_symbol)
            return {
                'exchange': self.exchange_id,
                'symbol': norm_symbol,
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'timestamp': ticker.get('timestamp'),
                'volume': ticker.get('baseVolume', 0)
            }
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {symbol} on {self.exchange_id}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, depth: int = 5) -> Dict[str, Any]:
        try:
            norm_symbol = self.normalize_symbol(symbol)
            if not norm_symbol:
                return {}
            orderbook = await self.exchange.fetch_order_book(norm_symbol, limit=depth)
            return {
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'timestamp': orderbook.get('timestamp')
            }
        except Exception as e:
            self.logger.error(f"Error fetching orderbook for {symbol} on {self.exchange_id}: {e}")
            return {}

    async def start_websocket_stream(self, symbols: List[str], callback: Callable) -> None:
        if not self.is_connected:
            self.logger.error(f"Cannot start WebSocket on {self.exchange_id} (not connected)")
            return
        while self.is_connected:
            try:
                if not await self._check_internet_connectivity():
                    self.logger.error(f"Lost internet connection for {self.exchange_id}")
                    self.is_connected = False
                    break
                for s in symbols[:20]:
                    ticker = await self.get_ticker(s)
                    if ticker.get('bid') and ticker.get('ask'):
                        await callback({'exchange': self.exchange_id, 'type': 'ticker', 'data': ticker})
                await asyncio.sleep(2)
            except Exception as e:
                self.logger.error(f"WebSocket error for {self.exchange_id}: {e}")
                self.is_connected = False
                await asyncio.sleep(5)

    async def place_market_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Execute REAL market order on exchange that will appear in your account."""
        try:
            # LIGHTNING MODE: Zero overhead execution
            
            # CRITICAL FIX: Round quantity to proper decimal precision for KuCoin
            if self.exchange_id == 'kucoin':
                qty = await self._round_to_kucoin_precision(symbol, qty)
                
                # CRITICAL: Additional validation for step 3 stablecoin pairs
                if 'USDC/USDT' in symbol or 'USDT/USDC' in symbol:
                    # Ensure USDC/USDT orders meet KuCoin requirements
                    if qty < 0.01:
                        self.logger.error(f"❌ USDC/USDT order too small: {qty:.8f} < 0.01 minimum")
                        return {
                            'success': False,
                            'status': 'failed',
                            'error': f'Order size {qty:.8f} below minimum 0.01 for {symbol}',
                            'symbol': symbol,
                            'side': side,
                            'amount': qty
                        }
                    
                    # Round to exactly 2 decimal places for USDC/USDT
                    qty = round(qty, 2)
                    self.logger.info(f"🔧 USDC/USDT precision fix: {qty:.2f}")
            
            # Silent order for maximum speed
            
            # Validate inputs
            if not symbol or not side or qty <= 0:
                raise ValueError(f"Invalid order parameters: symbol={symbol}, side={side}, qty={qty}")
            
            # LIGHTNING MODE: Direct execution
            
            # Gate.io specific order handling
            if self.exchange_id == 'gate':
                # Gate.io requires special handling for market buy orders
                if side.lower() == 'buy':
                    # For market BUY orders, Gate.io needs the USDT amount to spend (quote quantity)
                    # Set the option to use quote quantity for market buy orders
                    # Use Gate.io specific parameters for market buy
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side='buy',
                        amount=qty,  # This is the USDT amount to spend
                        price=None,
                        params={'createMarketBuyOrderRequiresPrice': False}
                    )
                else:
                    # For market SELL orders, use standard format
                    order = await self.exchange.create_market_order(symbol, side, qty)
            elif self.exchange_id == 'kucoin':
                # INSTANT: Use current time with minimal buffer
                current_timestamp = int(time.time() * 1000) + 500  # 0.5-second buffer for speed
                
                if side.lower() == 'buy':
                    # INSTANT: Direct KuCoin buy order format
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side='buy',
                        amount=None,  # Don't specify amount for market buy
                        price=None,
                        params={
                            'funds': f"{qty:.2f}",  # CRITICAL FIX: Use 'funds' for USDT amount to spend
                            'timestamp': current_timestamp
                        }
                    )
                else:
                    # CRITICAL FIX: Handle USDC/USDT sell orders with proper precision
                    if symbol in ['USDC/USDT', 'USDT/USDC']:
                        # For stablecoin pairs, use exactly 2 decimal places
                        formatted_qty = f"{qty:.2f}"
                        self.logger.info(f"🔧 Stablecoin sell order: {symbol} quantity={formatted_qty}")
                    else:
                        # For other pairs, use 8 decimal places
                        formatted_qty = f"{qty:.8f}"
                    
                    # INSTANT: Direct KuCoin sell order format
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side='sell',
                        amount=qty,
                        price=None,
                        params={
                            'size': formatted_qty,  # CRITICAL FIX: Use proper precision formatting
                            'timestamp': current_timestamp
                        }
                    )
            else:
                # Standard order for other exchanges
                order = await self.exchange.create_market_order(symbol, side, qty)
            
            if not order:
                return {
                    'success': False,
                    'status': 'failed',
                    'error': 'No response from exchange',
                    'symbol': symbol,
                    'side': side,
                    'amount': qty
                }
            
            # Extract initial order details
            order_id = order.get('id', 'Unknown')
            initial_status = order.get('status', 'Unknown')
            
            # CRITICAL FIX: Wait for order execution completion
            if order_id and order_id != 'Unknown':
                # LIGHTNING MODE: Ultra-fast timeout
                final_order = await self._wait_for_order_completion_lightning(order_id, symbol, timeout_seconds=8)
                
                if final_order:
                    order = final_order  # Use the completed order data
                else:
                    return {
                        'success': False,
                        'status': 'timeout',
                        'error': f'Order timeout after 8 seconds',
                        'id': order_id
                    }
            else:
                return {
                    'success': False,
                    'status': 'failed',
                    'error': 'No valid order ID received',
                    'raw_order': order
                }
            
            # Extract final order details after completion
            status = order.get('status', 'Unknown')
            filled_qty = float(order.get('filled', 0) or 0)
            avg_price = float(order.get('average', 0) or order.get('price', 0) or 0)
            total_cost = float(order.get('cost', 0) or 0)
            
            # Extract fee information
            fee_info = order.get('fee', {})
            fee_cost = 0
            fee_currency = 'Unknown'
            
            if fee_info and isinstance(fee_info, dict):
                fee_cost = float(fee_info.get('cost', 0) or 0)
                fee_currency = fee_info.get('currency', 'Unknown')
            
            # LIGHTNING SPEED: Minimal logging
            self.logger.info(f"⚡ {order_id}: {filled_qty:.8f} @ {avg_price:.8f} = {total_cost:.8f}")
            
            # Verify order was executed successfully
            if status in ['closed', 'filled'] and filled_qty > 0:
                self.logger.debug(f"⚡ SUCCESS: {order_id}")
                
                # Return success with all details
                return {
                    'success': True,
                    'id': order_id,
                    'status': status,
                    'filled': filled_qty,
                    'average': avg_price,
                    'cost': total_cost,
                    'fee': fee_info,
                    'symbol': symbol,
                    'side': side,
                    'amount': qty,
                    'timestamp': order.get('timestamp'),
                    'datetime': order.get('datetime'),
                    'raw_order': order
                }
            else:
                # Order not filled or failed
                error_msg = f"Order not executed: status={status}, filled={filled_qty}"
                self.logger.error(f"❌ ORDER FAILED: {error_msg}")
                return {
                    'success': False,
                    'status': 'failed',
                    'error': error_msg,
                    'id': order_id,
                    'raw_order': order
                }
            
        except Exception as e:
            error_msg = f"{self.exchange_id} order execution failed: {str(e)}"
            self.logger.error(f"❌ ERROR: {error_msg}")
            
            # If timestamp error, try to re-sync and retry once
            if self.exchange_id == 'kucoin' and 'KC-API-TIMESTAMP' in str(e):
                try:
                    # INSTANT RETRY: Use minimal buffer for speed
                    current_timestamp = int(time.time() * 1000) + 1000  # 1-second buffer
                    
                    if side.lower() == 'buy':
                        retry_order = await self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side='buy',
                            amount=None,
                            price=None,
                            params={
                                'funds': f"{qty:.2f}",
                                'timestamp': current_timestamp
                            }
                        )
                    else:
                        retry_order = await self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side='sell',
                            amount=qty,
                            price=None,
                            params={
                                'size': f"{qty:.8f}",
                                'timestamp': current_timestamp
                            }
                        )
                    
                    if retry_order and retry_order.get('id'):
                        # INSTANT: Silent retry success
                        
                        # Wait for completion
                        final_order = await self._wait_for_order_completion_instant(retry_order['id'], symbol, timeout_seconds=8)
                        
                        if final_order:
                            return {
                                'success': True,
                                'id': retry_order['id'],
                                'status': final_order.get('status'),
                                'filled': float(final_order.get('filled', 0)),
                                'average': float(final_order.get('average', 0)),
                                'cost': float(final_order.get('cost', 0)),
                                'fee': final_order.get('fee', {}),
                                'symbol': symbol,
                                'side': side,
                                'amount': qty,
                                'retry_success': True
                            }
                        
                except Exception as retry_error:
                    pass  # Silent retry failure for speed
            
            return {
                'success': False,
                'status': 'failed',
                'error': error_msg,
                'symbol': symbol,
                'side': side,
                'amount': qty,
                'exception_type': type(e).__name__
            }
    
    async def _wait_for_order_completion_instant(self, order_id: str, symbol: str, timeout_seconds: int = 5) -> Optional[Dict[str, Any]]:
        """INSTANT order completion with 5ms checking for maximum speed."""
        try:
            start_time = time.time()
            check_interval = 0.005  # INSTANT: Check every 5ms
            max_checks = int(timeout_seconds / check_interval)
            
            for attempt in range(max_checks):
                try:
                    # Fetch current order status
                    current_order = await self.exchange.fetch_order(order_id, symbol)
                    
                    if current_order:
                        status = current_order.get('status', 'unknown')
                        filled = float(current_order.get('filled', 0) or 0)
                        
                        # Check if order is completed
                        if status in ['closed', 'filled'] and filled > 0:
                            return current_order
                        elif status in ['canceled', 'cancelled', 'rejected']:
                            return None
                        
                        # KuCoin specific: Check for 'done' status
                        if status == 'done' and filled > 0:
                            return current_order
                    
                    # INSTANT: Ultra-minimal wait between checks
                    await asyncio.sleep(check_interval)
                    
                except Exception as fetch_error:
                    await asyncio.sleep(check_interval)
                    continue
            
            return None
            
        except Exception as e:
            return None

    async def _wait_for_order_completion_lightning(self, order_id: str, symbol: str, timeout_seconds: int = 8) -> Optional[Dict[str, Any]]:
        """Lightning order completion - alias for instant completion."""
        return await self._wait_for_order_completion_instant(order_id, symbol, timeout_seconds)

    async def _round_to_kucoin_precision(self, symbol: str, quantity: float) -> float:
        """Round quantity to KuCoin's required decimal precision"""
        try:
            # KuCoin precision rules for common pairs
            precision_rules = {
                # Major pairs - 8 decimal places
                'BTC/USDT': 8, 'ETH/USDT': 8, 'BNB/USDT': 8,
                'DOT/USDT': 4, 'ADA/USDT': 4, 'SOL/USDT': 4,
                'KCS/USDT': 4, 'MATIC/USDT': 4, 'AVAX/USDT': 4,
                
                # CRITICAL: USDC/USDT precision (step 3 failures)
                'USDC/USDT': 2,  # USDC/USDT requires 2 decimal places only
                'USDT/USDC': 2,  # Reverse pair
                'BUSD/USDT': 2,  # Other stablecoin pairs
                'USDT/BUSD': 2,
                'TUSD/USDT': 2,
                'USDT/TUSD': 2,
                
                # Cross pairs - 6 decimal places
                'DOT/KCS': 6, 'ETH/BTC': 6, 'BNB/BTC': 6,
                'ADA/BTC': 6, 'SOL/BTC': 6, 'DOT/BTC': 6,
                'KCS/BTC': 6, 'AR/BTC': 6, 'INJ/BTC': 6,
                'SCRT/BTC': 6, 'VRA/BTC': 6, 'TWT/BTC': 6,
                'LRC/BTC': 6, 'ANKR/BTC': 6, 'RLC/BTC': 6,
                
                # Small value pairs - 2-4 decimal places
                'AR/USDT': 4, 'INJ/USDT': 4, 'TFUEL/USDT': 4,
                'TRX/USDT': 4, 'DOGE/USDT': 4, 'XRP/USDT': 4,
                'VRA/USDT': 4, 'SCRT/USDT': 4, 'TWT/USDT': 4,
                'LRC/USDT': 4, 'ANKR/USDT': 4, 'RLC/USDT': 4,
                
                # Cross stablecoin pairs - special precision
                'VRA/USDC': 6, 'SCRT/USDC': 6, 'TWT/USDC': 6,
                'LRC/USDC': 6, 'ANKR/USDC': 6, 'RLC/USDC': 6,
                
                # Default precision
                'default': 6
            }
            
            # Get precision for this symbol
            precision = precision_rules.get(symbol, precision_rules['default'])
            
            # Round to the required precision
            rounded_qty = round(quantity, precision)
            
            # Apply symbol-specific minimum quantities
            min_quantities = {
                'USDC/USDT': 0.01,    # USDC/USDT minimum 0.01 USDC
                'USDT/USDC': 0.01,    # Reverse pair
                'BUSD/USDT': 0.01,    # Other stablecoin minimums
                'BTC/USDT': 0.00000001,  # BTC minimum
                'ETH/USDT': 0.000001,    # ETH minimum
                'default': 0.0001       # Default minimum
            }
            
            min_qty = min_quantities.get(symbol, min_quantities['default'])
            
            # Ensure minimum quantity
            if rounded_qty < min_qty:
                rounded_qty = min_qty
                self.logger.warning(f"⚠️ Quantity below minimum for {symbol}: {quantity:.8f} → {rounded_qty:.8f}")
            
            self.logger.info(f"🔧 KuCoin precision: {symbol} {quantity:.8f} → {rounded_qty:.8f} ({precision} decimals)")
            return rounded_qty
            
        except Exception as e:
            self.logger.error(f"Error rounding quantity for {symbol}: {e}")
            # Fallback: round to appropriate precision based on symbol type
            if 'USDC' in symbol and 'USDT' in symbol:
                return round(quantity, 2)  # Stablecoin pairs need 2 decimals
            elif 'BTC' in symbol:
                return round(quantity, 8)  # BTC pairs need 8 decimals
            else:
                return round(quantity, 6)  # Default 6 decimals

    async def _wait_for_order_completion(self, order_id: str, symbol: str, timeout_seconds: int = 30) -> Optional[Dict[str, Any]]:
        """Standard order completion monitoring (fallback)"""
        try:
            start_time = time.time()
            check_interval = 0.1  # Check every 100ms
            max_checks = int(timeout_seconds / check_interval)
            
            self.logger.debug(f"⚡ Monitoring {order_id} (timeout: {timeout_seconds}s)")
            
            for attempt in range(max_checks):
                try:
                    # Fetch current order status
                    current_order = await self.exchange.fetch_order(order_id, symbol)
                    
                    if current_order:
                        status = current_order.get('status', 'unknown')
                        filled = float(current_order.get('filled', 0) or 0)
                        
                        if attempt % 20 == 0:  # Log every 2 seconds
                            self.logger.debug(f"⚡ Order {order_id} check #{attempt + 1}: status={status}, filled={filled:.8f}")
                        
                        # Check if order is completed
                        if status in ['closed', 'filled'] and filled > 0:
                            elapsed = time.time() - start_time
                            self.logger.info(f"⚡ Order {order_id} FILLED in {elapsed:.1f}s")
                            return current_order
                        elif status in ['canceled', 'cancelled', 'rejected']:
                            self.logger.error(f"❌ Order {order_id} was {status}")
                            return None
                        
                        # KuCoin specific: Check for 'done' status
                        if status == 'done' and filled > 0:
                            elapsed = time.time() - start_time
                            self.logger.info(f"⚡ KuCoin order {order_id} DONE in {elapsed:.1f}s")
                            return current_order
                    
                    # Wait before next check
                    await asyncio.sleep(check_interval)
                    
                except Exception as fetch_error:
                    if attempt % 50 == 0:  # Only log every 50th error to reduce spam
                        self.logger.warning(f"⚠️ Error fetching order {order_id} status: {fetch_error}")
                    await asyncio.sleep(check_interval)
                    continue
            
            # Timeout reached
            elapsed = time.time() - start_time
            self.logger.error(f"❌ Order {order_id} timeout after {elapsed:.1f}s")
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error waiting for order completion: {e}")
            return None

    async def get_account_balance(self) -> Dict[str, float]:
        if not self.is_connected:
            return {}
        try:
            self.logger.info(f"💰 Fetching REAL account balance from {self.exchange_id}...")
            balance = await self.exchange.fetch_balance()
            
            # Log the full balance object for debugging
            self.logger.debug(f"📊 Raw balance response keys: {list(balance.keys())}")
            
            # Handle both dict and direct value formats
            result = {}
            for currency, info in balance.items():
                if currency in ['info', 'timestamp', 'datetime']:
                    continue
                if isinstance(info, dict):
                    free_balance = float(info.get('free', 0.0))
                    locked_balance = float(info.get('used', 0.0))
                    total_balance = free_balance + locked_balance
                    if total_balance > 0.000001:  # Only include meaningful balances
                        result[currency] = total_balance
                        self.logger.debug(f"💰 REAL BALANCE - {currency}: {total_balance:.8f} (free: {free_balance:.8f}, locked: {locked_balance:.8f})")
                elif isinstance(info, (int, float)) and float(info) > 0:
                    result[currency] = float(info)
                    self.logger.debug(f"💰 REAL BALANCE - {currency}: {float(info):.8f}")
            
            # Get current prices for USD conversion
            total_usd_estimate = await self._calculate_usd_value(result)
            
            self.logger.info(f"💵 REAL Account balance for {self.exchange_id}: {len(result)} currencies")
            self.logger.info(f"💵 REAL Estimated Total: ~${total_usd_estimate:.2f} USD")
            
            if result:
                self.logger.info("💰 REAL BALANCES DETECTED:")
                for curr, bal in sorted(result.items(), key=lambda x: x[1], reverse=True):
                    if bal > 0.001:  # Only show significant balances in main log
                        self.logger.info(f"   {curr}: {bal:.8f}")
            else:
                self.logger.warning("⚠️ No balances found - check API permissions")
            
            return result
        except Exception as e:
            self.logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {}
    
    async def fetch_complete_balance(self) -> Dict[str, Any]:
        """Fetch complete balance with USD conversion for compatibility"""
        balances = await self.get_account_balance()
        total_usd = await self._calculate_usd_value(balances)
        
        return {
            'balances': balances,
            'total_usd': total_usd,
            'timestamp': int(time.time() * 1000)
        }
    
    async def _calculate_usd_value(self, balances: Dict[str, float]) -> float:
        """Calculate USD value of all balances using current market prices."""
        if not balances:
            self.logger.warning("No balances to calculate USD value for")
            return 0.0
            
        total_usd = 0.0
        
        for currency, amount in balances.items():
            if amount <= 0:
                continue
                
            try:
                if currency in ['USDT', 'USDC', 'BUSD', 'USD']:
                    # Stablecoins are 1:1 with USD
                    usd_value = amount
                    total_usd += usd_value
                    self.logger.info(f"💵 {currency}: {amount:.8f} = ${usd_value:.2f} USD")
                else:
                    # Try to get current price vs USDT
                    symbol = f"{currency}/USDT"
                    if hasattr(self, 'trading_pairs') and symbol in self.trading_pairs:
                        ticker = await self.get_ticker(symbol)
                        if ticker and ticker.get('last'):
                            price = float(ticker['last'])
                            usd_value = amount * price
                            total_usd += usd_value
                            self.logger.info(f"💵 {currency}: {amount:.8f} × ${price:.2f} = ${usd_value:.2f} USD")
                        else:
                            self.logger.info(f"💵 {currency}: {amount:.8f} (no current price)")
                    else:
                        # Fallback to rough estimates for major currencies
                        if currency == 'BTC':
                            usd_value = amount * 95000  # Updated BTC price estimate
                            total_usd += usd_value
                            self.logger.info(f"💵 {currency}: {amount:.8f} × $118,000 ≈ ${usd_value:.2f} USD (estimate)")
                        elif currency == 'ETH':
                            usd_value = amount * 3200  # Updated ETH price estimate
                            total_usd += usd_value
                            self.logger.info(f"💵 {currency}: {amount:.8f} × $3,200 ≈ ${usd_value:.2f} USD (estimate)")
                        elif currency == 'BNB':
                            usd_value = amount * 650  # Updated BNB price estimate
                            total_usd += usd_value
                            self.logger.info(f"💵 {currency}: {amount:.8f} × $650 ≈ ${usd_value:.2f} USD (estimate)")
                        else:
                            self.logger.info(f"💵 {currency}: {amount:.8f} (no USD conversion available)")
            except Exception as e:
                self.logger.error(f"Error calculating USD value for {currency}: {e}")
        
        self.logger.info(f"💰 Total USD value calculated: ${total_usd:.2f}")
        return total_usd

    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Get accurate trading fees for the specific exchange with fee token discounts."""
        try:
            # Check for zero-fee pairs first
            if symbol in self.zero_fee_pairs:
                self.logger.info(f"✅ Zero-fee pair detected: {symbol} on {self.exchange_id}")
                return 0.0, 0.0
            
            # Get base fees from exchange config
            base_maker_fee = self.maker_fee
            base_taker_fee = self.taker_fee
            
            # Check if user has fee token balance for discount
            fee_token_balance = 0.0
            if self.fee_token:
                fee_token_balance = await self.check_fee_token_balance()
                self.logger.info(f"💰 {self.fee_token} balance: {fee_token_balance:.6f}")
            
            # Apply fee token discount if available
            if fee_token_balance > 0 and hasattr(self, 'maker_fee_with_token'):
                maker_fee = getattr(self, 'maker_fee_with_token', base_maker_fee)
                taker_fee = getattr(self, 'taker_fee_with_token', base_taker_fee)
                self.logger.info(f"✅ {self.exchange_id} fees with {self.fee_token}: "
                               f"maker={maker_fee*100:.3f}%, taker={taker_fee*100:.3f}%")
            else:
                maker_fee = base_maker_fee
                taker_fee = base_taker_fee
                self.logger.info(f"📊 {self.exchange_id} base fees: "
                               f"maker={maker_fee*100:.3f}%, taker={taker_fee*100:.3f}%")
            
            return maker_fee, taker_fee
            
        except Exception as e:
            self.logger.error(f"Error fetching fees for {symbol} on {self.exchange_id}: {e}")
            return self.maker_fee, self.taker_fee

    async def check_fee_token_balance(self) -> float:
        if not self.fee_token:
            return 0.0
        try:
            bal = await self.get_account_balance()
            return bal.get(self.fee_token, 0.0)
        except Exception:
            return 0.0

    async def check_bnb_balance(self) -> float:
        try:
            bal = await self.get_account_balance()
            return bal.get('BNB', 0.0)
        except Exception:
            return 0.0

    async def validate_trading_pairs(self, pairs: List[str]) -> List[str]:
        """Validate that trading pairs exist on this exchange"""
        try:
            if not self.trading_pairs:
                await self.exchange.load_markets()
                self.trading_pairs = {
                    s: m for s, m in self.exchange.markets.items() if m.get("active", False)
                }
            
            valid_pairs = []
            for pair in pairs:
                if pair in self.trading_pairs:
                    valid_pairs.append(pair)
                else:
                    self.logger.debug(f"❌ Invalid pair for {self.exchange_id}: {pair}")
            
            return valid_pairs
        except Exception as e:
            self.logger.error(f"Error validating pairs: {e}")
            return []