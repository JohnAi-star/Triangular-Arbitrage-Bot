"""
Unified exchange wrapper for consistent interface across all exchanges.
"""

import ccxt.async_support as ccxt
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple, Callable
from exchanges.base_exchange import BaseExchange
from utils.logger import setup_logger

class UnifiedExchange(BaseExchange):
    """Unified exchange implementation using ccxt."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.exchange_id = config['exchange_id']
        self.logger = setup_logger(f'Exchange_{self.exchange_id.title()}')
        self.exchange: Optional[ccxt.Exchange] = None
        self.paper_trading = config.get('paper_trading', True)
        self.fee_token = config.get('fee_token')
        self.fee_discount = config.get('fee_discount', 0.0)
        self.zero_fee_pairs = config.get('zero_fee_pairs', [])
        self.maker_fee = config.get('maker_fee', 0.001)
        self.taker_fee = config.get('taker_fee', 0.001)
        
    async def connect(self) -> bool:
        """Connect to the exchange."""
        try:
            # Get the exchange class from ccxt
            exchange_class = getattr(ccxt, self.exchange_id)
            
            exchange_config = {
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            }
            
            # Add credentials if not in paper trading mode
            if not self.paper_trading:
                exchange_config.update({
                    'apiKey': self.config['api_key'],
                    'secret': self.config['api_secret'],
                    'sandbox': self.config.get('sandbox', True)
                })
            
            self.exchange = exchange_class(exchange_config)
            
            # Test connection by loading markets
            await self.exchange.load_markets()
            self.is_connected = True
            
            self.logger.info(f"Connected to {self.exchange_id} ({'paper' if self.paper_trading else 'live'} mode)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.exchange_id}: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""
        try:
            if self.exchange:
                await self.exchange.close()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.exchange_id}")
        except Exception as e:
            self.logger.error(f"Error disconnecting from {self.exchange_id}: {e}")
    
    async def get_trading_pairs(self) -> List[str]:
        """Get all active trading pairs."""
        try:
            markets = await self.exchange.load_markets()
            pairs = [
                symbol for symbol, market in markets.items()
                if market.get('active') and market.get('type') == 'spot'
            ]
            return pairs
        except Exception as e:
            self.logger.error(f"Error fetching trading pairs from {self.exchange_id}: {e}")
            return []
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker data for a symbol."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'exchange': self.exchange_id,
                'symbol': symbol,
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'timestamp': ticker.get('timestamp'),
                'volume': ticker.get('baseVolume', 0)
            }
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {symbol} on {self.exchange_id}: {e}")
            return {}
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book for a symbol."""
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit)
            return {
                'exchange': self.exchange_id,
                'symbol': symbol,
                'bids': orderbook.get('bids', [])[:limit],
                'asks': orderbook.get('asks', [])[:limit],
                'timestamp': orderbook.get('timestamp')
            }
        except Exception as e:
            self.logger.error(f"Error fetching orderbook for {symbol} on {self.exchange_id}: {e}")
            return {}
    
    async def start_websocket_stream(self, symbols: List[str], callback: Callable) -> None:
        """Start WebSocket stream for price updates."""
        # This is a simplified WebSocket implementation
        # In production, you'd implement exchange-specific WebSocket protocols
        
        while self.is_connected:
            try:
                # Simulate real-time updates by fetching tickers periodically
                for symbol in symbols[:20]:  # Limit to avoid rate limits
                    try:
                        ticker = await self.get_ticker(symbol)
                        if ticker:
                            await callback({
                                'exchange': self.exchange_id,
                                'type': 'ticker',
                                'data': ticker
                            })
                    except Exception as e:
                        self.logger.error(f"Error in WebSocket simulation for {symbol}: {e}")
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                self.logger.error(f"WebSocket error for {self.exchange_id}: {e}")
                await asyncio.sleep(5)
    
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Place a market order."""
        if self.paper_trading:
            # Simulate order execution
            ticker = await self.get_ticker(symbol)
            price = ticker.get('ask' if side == 'buy' else 'bid', 0)
            
            return {
                'id': f"paper_{self.exchange_id}_{symbol}_{side}_{quantity}",
                'symbol': symbol,
                'side': side,
                'amount': quantity,
                'price': price,
                'status': 'closed',
                'filled': quantity,
                'average': price,
                'timestamp': asyncio.get_event_loop().time() * 1000
            }
        
        try:
            order = await self.exchange.create_market_order(symbol, side, quantity)
            self.logger.info(f"Market order placed on {self.exchange_id}: {side} {quantity} {symbol}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing market order on {self.exchange_id}: {e}")
            return {}
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balances."""
        if self.paper_trading:
            # Return simulated balances
            return {
                'USDT': 10000.0,
                'BTC': 0.1,
                'ETH': 1.0,
                'BNB': 10.0
            }
        
        try:
            balance = await self.exchange.fetch_balance()
            return {
                currency: info.get('free', 0.0)
                for currency, info in balance.items()
                if isinstance(info, dict) and info.get('free', 0.0) > 0
            }
        except Exception as e:
            self.logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {}
    
    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Get trading fees for a symbol."""
        try:
            # Check if this is a zero-fee pair
            if symbol in self.zero_fee_pairs:
                return 0.0, 0.0
            
            # Apply fee token discount if available
            maker_fee = self.maker_fee
            taker_fee = self.taker_fee
            
            if self.fee_token and self.fee_discount > 0:
                fee_token_balance = await self.check_fee_token_balance()
                if fee_token_balance > 0:
                    maker_fee *= (1 - self.fee_discount)
                    taker_fee *= (1 - self.fee_discount)
            
            return maker_fee, taker_fee
            
        except Exception as e:
            self.logger.error(f"Error fetching fees for {symbol} on {self.exchange_id}: {e}")
            return self.maker_fee, self.taker_fee
    
    async def check_fee_token_balance(self) -> float:
        """Check fee token balance."""
        if not self.fee_token:
            return 0.0
        
        try:
            balance = await self.get_account_balance()
            return balance.get(self.fee_token, 0.0)
        except Exception as e:
            self.logger.error(f"Error checking {self.fee_token} balance on {self.exchange_id}: {e}")
            return 0.0