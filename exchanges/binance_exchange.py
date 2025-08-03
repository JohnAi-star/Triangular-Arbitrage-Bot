#!/usr/bin/env python3
"""
Fixed Binance Exchange Implementation with Real Balance Display
"""

import asyncio
import time
import ccxt.async_support as ccxt
from typing import Dict, Any, List, Optional, Tuple, Callable
from exchanges.base_exchange import BaseExchange
from utils.logger import setup_logger

class BinanceExchange(BaseExchange):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = setup_logger('BinanceExchange')
        self.exchange = ccxt.binance({
            'apiKey': config['api_key'],
            'secret': config['api_secret'],
            'enableRateLimit': True,
            'sandbox': config.get('sandbox', False),
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to Binance with enhanced balance verification"""
        try:
            self.logger.info("🔗 Connecting to Binance...")
            
            # Load markets first
            await self.exchange.load_markets()
            self.logger.info("✅ Markets loaded successfully")
            
            # Test API connection with account info
            try:
                account_info = await self.exchange.fetch_balance()
                if not account_info:
                    raise Exception("No account info returned")
                self.logger.info("✅ Account info retrieved successfully")
            except Exception as e:
                self.logger.error(f"❌ Failed to fetch account info: {e}")
                return False
            
            # Get and display real balance
            balance = await self.get_account_balance()
            if balance:
                total_currencies = len(balance)
                total_usd = await self._calculate_usd_value(balance)
                
                self.logger.info(f"💰 REAL BINANCE BALANCE DETECTED:")
                self.logger.info(f"   Currencies with balance: {total_currencies}")
                self.logger.info(f"   Total USD value: ~${total_usd:.2f}")
                
                # Show individual balances
                for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True):
                    if amount > 0.001:  # Only show significant balances
                        self.logger.info(f"   {currency}: {amount:.8f}")
                
                self.is_connected = True
                self.logger.info("✅ Connected to Binance with REAL balance access")
                return True
            else:
                self.logger.warning("⚠️ Connected but no balance detected")
                self.is_connected = True
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Binance connection failed: {str(e)}")
            return False

    async def get_account_balance(self) -> Dict[str, float]:
        """Get real account balance with multiple fallback methods"""
        try:
            self.logger.debug("🔍 Fetching real Binance account balance...")
            
            # Method 1: Standard CCXT fetch_balance
            try:
                balance = await self.exchange.fetch_balance()
                if balance and balance.get('total'):
                    result = {}
                    for currency, info in balance.items():
                        if currency in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
                            continue
                        if isinstance(info, dict):
                            total_amount = float(info.get('total', 0))
                            if total_amount > 0:
                                result[currency] = total_amount
                                self.logger.debug(f"💰 Found {currency}: {total_amount:.8f}")
                    
                    if result:
                        self.logger.info(f"✅ Method 1 success: Found {len(result)} currencies with balance")
                        return result
            except Exception as e:
                self.logger.debug(f"Method 1 failed: {e}")
            
            # Method 2: Direct API call to account endpoint
            try:
                account = await self.exchange.privateGetAccount()
                if account and account.get('balances'):
                    result = {}
                    for item in account['balances']:
                        currency = item['asset']
                        free_balance = float(item['free'])
                        locked_balance = float(item['locked'])
                        total_balance = free_balance + locked_balance
                        
                        if total_balance > 0:
                            result[currency] = total_balance
                            self.logger.debug(f"💰 Found {currency}: {total_balance:.8f} (free: {free_balance:.8f}, locked: {locked_balance:.8f})")
                    
                    if result:
                        self.logger.info(f"✅ Method 2 success: Found {len(result)} currencies with balance")
                        return result
            except Exception as e:
                self.logger.debug(f"Method 2 failed: {e}")
            
            # Method 3: Try with different parameters
            try:
                balance = await self.exchange.fetch_balance({'type': 'spot'})
                if balance:
                    result = {}
                    for currency, amount in balance.get('total', {}).items():
                        if float(amount) > 0:
                            result[currency] = float(amount)
                    
                    if result:
                        self.logger.info(f"✅ Method 3 success: Found {len(result)} currencies with balance")
                        return result
            except Exception as e:
                self.logger.debug(f"Method 3 failed: {e}")
            
            self.logger.warning("⚠️ All balance fetch methods failed - returning empty balance")
            return {}
            
        except Exception as e:
            self.logger.error(f"❌ Critical error fetching balance: {e}")
            return {}

    async def _calculate_usd_value(self, balances: Dict[str, float]) -> float:
        """Calculate total USD value of balances"""
        if not balances:
            return 0.0
        
        total_usd = 0.0
        
        try:
            # Get current tickers for price conversion
            tickers = await self.exchange.fetch_tickers()
            
            for currency, amount in balances.items():
                if amount <= 0:
                    continue
                
                if currency in ['USDT', 'USDC', 'BUSD', 'USD']:
                    # Stablecoins = 1:1 USD
                    usd_value = amount
                    total_usd += usd_value
                    self.logger.debug(f"💵 {currency}: {amount:.8f} = ${usd_value:.2f}")
                else:
                    # Try to find USDT pair
                    pair = f"{currency}/USDT"
                    if pair in tickers:
                        price = float(tickers[pair]['last'])
                        usd_value = amount * price
                        total_usd += usd_value
                        self.logger.debug(f"💵 {currency}: {amount:.8f} × ${price:.2f} = ${usd_value:.2f}")
                    else:
                        # Try BTC pair then convert to USD
                        btc_pair = f"{currency}/BTC"
                        if btc_pair in tickers and 'BTC/USDT' in tickers:
                            btc_price = float(tickers[btc_pair]['last'])
                            btc_usd = float(tickers['BTC/USDT']['last'])
                            usd_value = amount * btc_price * btc_usd
                            total_usd += usd_value
                            self.logger.debug(f"💵 {currency}: {amount:.8f} via BTC = ${usd_value:.2f}")
                        else:
                            self.logger.debug(f"💵 {currency}: {amount:.8f} (no price data)")
        
        except Exception as e:
            self.logger.error(f"Error calculating USD value: {e}")
        
        return total_usd

    async def fetch_complete_balance(self) -> Dict[str, Any]:
        """Fetch complete balance with USD conversion for compatibility"""
        balances = await self.get_account_balance()
        total_usd = await self._calculate_usd_value(balances)
        
        return {
            'balances': balances,
            'total_usd': total_usd,
            'timestamp': int(time.time() * 1000)
        }

    async def get_trading_pairs(self) -> List[str]:
        """Get all active trading pairs"""
        try:
            if not hasattr(self, 'exchange') or not self.exchange.markets:
                await self.exchange.load_markets()
            
            return [
                symbol for symbol, market in self.exchange.markets.items()
                if market.get('active') and market.get('type') == 'spot'
            ]
        except Exception as e:
            self.logger.error(f"Error fetching trading pairs: {e}")
            return []

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker data"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'timestamp': ticker.get('timestamp'),
                'volume': ticker.get('baseVolume', 0)
            }
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Fetch order book"""
        try:
            ob = await self.exchange.fetch_order_book(symbol, limit)
            return {
                'symbol': symbol,
                'bids': ob.get('bids', [])[:limit],
                'asks': ob.get('asks', [])[:limit],
                'timestamp': ob.get('timestamp')
            }
        except Exception as e:
            self.logger.error(f"Error fetching order book for {symbol}: {e}")
            return {}

    async def start_websocket_stream(self, symbols: List[str], callback: Callable) -> None:
        """Stream ticker updates via WebSocket (simplified for now)"""
        max_attempts = self.config.get('websocket_reconnect_attempts', 5)
        attempts = 0

        while attempts < max_attempts and self.is_connected:
            try:
                self.logger.info(f"Starting price stream for {len(symbols)} symbols...")
                
                # Simplified: poll tickers every 2 seconds
                while self.is_connected:
                    try:
                        for symbol in symbols[:50]:  # Limit to avoid rate limits
                            ticker = await self.get_ticker(symbol)
                            if ticker.get('bid') and ticker.get('ask'):
                                await callback({
                                    'exchange': 'binance',
                                    'type': 'ticker',
                                    'data': ticker
                                })
                        await asyncio.sleep(2)
                    except Exception as e:
                        self.logger.error(f"Error in ticker stream: {e}")
                        break
                        
            except Exception as e:
                attempts += 1
                self.logger.error(f"WebSocket error (attempt {attempts}): {e}")
                if attempts < max_attempts:
                    await asyncio.sleep(5)
                else:
                    self.logger.error("Max WebSocket reconnect attempts reached")
                    break

    async def place_market_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Place a market order"""
        try:
            self.logger.info(f"🔴 PLACING REAL BINANCE ORDER: {side.upper()} {qty:.8f} {symbol}")
            
            order = await self.exchange.create_market_order(symbol, side, qty)
            
            if order and order.get('id'):
                self.logger.info(f"✅ Order executed: ID {order['id']}")
                return {
                    'success': True,
                    'id': order['id'],
                    'filled': order.get('filled', 0),
                    'average': order.get('average', 0),
                    'cost': order.get('cost', 0),
                    'fee': order.get('fee', {}),
                    'status': order.get('status', 'unknown')
                }
            else:
                return {'success': False, 'error': 'No order ID returned'}
                
        except Exception as e:
            self.logger.error(f"❌ Order failed: {e}")
            return {'success': False, 'error': str(e)}

    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Get trading fees for symbol"""
        try:
            # Check if BNB balance exists for fee discount
            bnb_balance = await self.check_bnb_balance()
            
            # Base Binance fees
            maker_fee = 0.001  # 0.1%
            taker_fee = 0.001  # 0.1%
            
            # Apply BNB discount if available
            if bnb_balance > 0:
                maker_fee *= 0.75  # 25% discount
                taker_fee *= 0.75
                
            return maker_fee, taker_fee
            
        except Exception as e:
            self.logger.error(f"Error fetching fees for {symbol}: {e}")
            return 0.001, 0.001

    async def check_fee_token_balance(self) -> float:
        """Check BNB balance for fee discount"""
        return await self.check_bnb_balance()

    async def check_bnb_balance(self) -> float:
        """Check BNB balance"""
        try:
            balance = await self.get_account_balance()
            return balance.get('BNB', 0.0)
        except Exception as e:
            self.logger.error(f"Error checking BNB balance: {e}")
            return 0.0

    async def disconnect(self) -> None:
        """Disconnect from exchange"""
        if self.is_connected:
            try:
                await self.exchange.close()
                self.is_connected = False
                self.logger.info("✅ Disconnected from Binance")
            except Exception as e:
                self.logger.error(f"Error during disconnect: {e}")