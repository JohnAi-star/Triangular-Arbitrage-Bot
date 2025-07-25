import ccxt.async_support as ccxt  # Async version of ccxt
import asyncio
import websockets
import json
from typing import Dict, List, Any, Optional, Tuple, Callable
from exchanges.base_exchange import BaseExchange
from utils.logger import setup_logger


class BinanceExchange(BaseExchange):
    """Binance exchange implementation using ccxt (async) and WebSocket."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = setup_logger('BinanceExchange')
        self.exchange: Optional[ccxt.binance] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.websocket_url = "wss://stream.binance.com:9443/ws/"
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to Binance exchange."""
        try:
            self.exchange = ccxt.binance({
                'apiKey': self.config['api_key'],
                'secret': self.config['api_secret'],
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })

            # Load markets (test connection)
            await self.exchange.load_markets()
            self.is_connected = True
            self.logger.info("Successfully connected to Binance")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Binance: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        try:
            if self.websocket:
                await self.websocket.close()
            if self.exchange:
                await self.exchange.close()  # async_support has close()
            self.is_connected = False
            self.logger.info("Disconnected from Binance")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")

    async def get_trading_pairs(self) -> List[str]:
        """Get all active trading pairs."""
        try:
            markets = await self.exchange.load_markets()
            return [
                symbol for symbol, market in markets.items()
                if market.get('active') and market.get('type') == 'spot'
            ]
        except Exception as e:
            self.logger.error(f"Error fetching trading pairs: {e}")
            return []

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker data."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'timestamp': ticker.get('timestamp')
            }
        except Exception as e:
            self.logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Fetch order book."""
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
        """Stream ticker updates via WebSocket."""
        streams = [f"{s.lower().replace('/', '')}@ticker" for s in symbols]
        url = f"{self.websocket_url}{'/'.join(streams)}"
        max_attempts = self.config.get('websocket_reconnect_attempts', 5)
        attempts = 0

        while attempts < max_attempts:
            try:
                self.logger.info(f"Connecting to WebSocket stream...")
                async with websockets.connect(url) as ws:
                    self.websocket = ws
                    attempts = 0
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            await callback(data)
                        except Exception as e:
                            self.logger.error(f"Error handling WebSocket message: {e}")
            except Exception as e:
                attempts += 1
                self.logger.error(f"WebSocket error (attempt {attempts}): {e}")
                if attempts < max_attempts:
                    await asyncio.sleep(self.config.get('websocket_reconnect_delay', 5))
                else:
                    self.logger.error("Max WebSocket reconnect attempts reached")
                    break

    async def place_market_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Place a market order."""
        try:
            order = await self.exchange.create_market_order(symbol, side, qty)
            self.logger.info(f"Market order placed: {side} {qty} {symbol}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing market order: {e}")
            return {}

    async def get_account_balance(self) -> Dict[str, float]:
        """Fetch balances."""
        try:
            bal = await self.exchange.fetch_balance()
            return {
                c: info.get('free', 0.0)
                for c, info in bal.items()
                if isinstance(info, dict) and info.get('free', 0.0) > 0
            }
        except Exception as e:
            self.logger.error(f"Error fetching balances: {e}")
            return {}

    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Fetch trading fees."""
        try:
            fees = await self.exchange.fetch_trading_fees()
            s_fees = fees.get(symbol, fees.get('trading', {}))
            maker = s_fees.get('maker', 0.001)
            taker = s_fees.get('taker', 0.001)
            if self.config.get('bnb_fee_discount', True):
                bnb = await self.check_bnb_balance()
                if bnb > 0:
                    maker *= 0.75
                    taker *= 0.75
            return maker, taker
        except Exception as e:
            self.logger.error(f"Error fetching fees: {e}")
            return 0.001, 0.001

    async def check_bnb_balance(self) -> float:
        """Check available BNB."""
        try:
            bal = await self.exchange.fetch_balance()
            return bal.get('BNB', {}).get('free', 0.0)
        except Exception as e:
            self.logger.error(f"Error checking BNB balance: {e}")
            return 0.0
