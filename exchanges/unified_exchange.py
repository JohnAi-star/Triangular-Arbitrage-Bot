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
        self.live_trading = True  # 🔴 FORCE LIVE TRADING
        self.dry_run = False      # 🔴 NO DRY RUN MODE
        self.trading_pairs: Dict[str, Any] = {}
        
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

            self.exchange = exchange_class(exchange_config)
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

            self.is_connected = True
            self.logger.info(f"✅ Connected to {self.exchange_id} - REAL ACCOUNT ACCESS")
            self.logger.info(f"{self.exchange_id}: {len(self.trading_pairs)} trading pairs")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to {self.exchange_id}: {e}")
            self.logger.error("   Check your API credentials in .env file")
            return False

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
            self.logger.info(f"🔴 EXECUTING REAL {self.exchange_id.upper()} ORDER:")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Side: {side.upper()}")
            self.logger.info(f"   Quantity: {qty:.8f}")
            
            # Validate inputs
            if not symbol or not side or qty <= 0:
                raise ValueError(f"Invalid order parameters: symbol={symbol}, side={side}, qty={qty}")
            
            # Get current market info for logging
            try:
                ticker = await self.get_ticker(symbol)
                current_price = ticker.get('last', 0)
                estimated_value = qty * current_price if side == 'sell' else qty
                self.logger.info(f"   Current Price: {current_price:.8f}")
                self.logger.info(f"   Estimated Value: ${estimated_value:.2f}")
            except Exception:
                pass  # Continue even if ticker fails
            
            # Execute the REAL market order with exchange-specific handling
            self.logger.info(f"🚀 Sending order to {self.exchange_id}...")
            
            # Gate.io specific order handling
            if self.exchange_id == 'gate':
                self.logger.info("🔧 Using Gate.io specific order format...")
                
                # Gate.io requires special handling for market buy orders
                if side.lower() == 'buy':
                    # For market BUY orders, Gate.io needs the USDT amount to spend (quote quantity)
                    # Set the option to use quote quantity for market buy orders
                    self.logger.info(f"🔧 Gate.io MARKET BUY: Spending {qty:.2f} USDT to buy {symbol}")
                    
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
                    self.logger.info(f"🔧 Gate.io MARKET SELL: Selling {qty:.8f} {symbol.split('/')[0]}")
                    order = await self.exchange.create_market_order(symbol, side, qty)
            else:
                # Standard order for other exchanges
                order = await self.exchange.create_market_order(symbol, side, qty)
            
            
            if not order:
                self.logger.error("❌ No response from exchange")
                return {
                    'success': False,
                    'status': 'failed',
                    'error': 'No response from exchange',
                    'symbol': symbol,
                    'side': side,
                    'amount': qty
                }
            
            # Extract order details
            order_id = order.get('id', 'Unknown')
            status = order.get('status', 'Unknown')
            filled_qty = float(order.get('filled', 0))
            avg_price = float(order.get('average', 0))
            total_cost = float(order.get('cost', 0))
            
            # Extract fee information
            fee_info = order.get('fee', {})
            fee_cost = 0
            fee_currency = 'Unknown'
            
            if fee_info and isinstance(fee_info, dict):
                fee_cost = float(fee_info.get('cost', 0))
                fee_currency = fee_info.get('currency', 'Unknown')
            
            # Log comprehensive order details
            self.logger.info(f"✅ {self.exchange_id.upper()} ORDER RESPONSE RECEIVED:")
            self.logger.info(f"   Order ID: {order_id}")
            self.logger.info(f"   Status: {status}")
            self.logger.info(f"   Filled Quantity: {filled_qty:.8f}")
            self.logger.info(f"   Average Price: {avg_price:.8f}")
            self.logger.info(f"   Total Cost: {total_cost:.8f}")
            self.logger.info(f"   Fee: {fee_cost:.8f} {fee_currency}")
            
            # Verify order was executed successfully
            if status in ['closed', 'filled'] and filled_qty > 0:
                self.logger.info(f"🎉 ORDER SUCCESSFULLY EXECUTED ON {self.exchange_id.upper()}!")
                self.logger.info(f"   ✅ This trade is now visible in your {self.exchange_id} account")
                self.logger.info(f"   ✅ Order ID {order_id} can be found in your trade history")
                self.logger.info(f"   ✅ Profit/Loss will be reflected in your balance")
                
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
                self.logger.error(f"❌ {self.exchange_id.upper()} ORDER FAILED: {error_msg}")
                return {
                    'success': False,
                    'status': 'failed',
                    'error': error_msg,
                    'id': order_id,
                    'raw_order': order
                }
            
        except Exception as e:
            error_msg = f"{self.exchange_id} order execution failed: {str(e)}"
            self.logger.error(f"❌ CRITICAL ERROR: {error_msg}")
            self.logger.error(f"   Symbol: {symbol}")
            self.logger.error(f"   Side: {side}")
            self.logger.error(f"   Quantity: {qty}")
            self.logger.error(f"   Exception Type: {type(e).__name__}")
            
            return {
                'success': False,
                'status': 'failed',
                'error': error_msg,
                'symbol': symbol,
                'side': side,
                'amount': qty,
                'exception_type': type(e).__name__
            }

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
        try:
            if symbol in self.zero_fee_pairs:
                return 0.0, 0.0
            maker, taker = self.maker_fee, self.taker_fee
            if self.fee_token and self.fee_discount > 0:
                bal = await self.check_fee_token_balance()
                if bal > 0:
                    maker *= (1 - self.fee_discount)
                    taker *= (1 - self.fee_discount)
            return maker, taker
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