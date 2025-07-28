"""
Unified exchange wrapper for consistent interface across all exchanges.
Handles ccxt integration, normalization, and fallback for paper/live modes.
"""

# --- Prevent fatal 'HEAD' Git errors ---
import subprocess, os
GIT_COMMIT = "unknown"
try:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    commit = subprocess.check_output(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        stderr=subprocess.DEVNULL
    ).decode().strip()
    GIT_COMMIT = commit[:7]
except Exception:
    GIT_COMMIT = "unknown"
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
        self.paper_trading = config.get('paper_trading', True)
        self.fee_token = config.get('fee_token')
        self.fee_discount = config.get('fee_discount', 0.0)
        self.zero_fee_pairs = config.get('zero_fee_pairs', [])
        self.maker_fee = config.get('maker_fee', 0.001)
        self.taker_fee = config.get('taker_fee', 0.001)
        self.trading_pairs: Dict[str, Any] = {}

    async def connect(self) -> bool:
        try:
            if not await self._check_internet_connectivity():
                self.logger.error(f"No internet connection for {self.exchange_id}")
                return False

            exchange_class = getattr(ccxt, self.exchange_id)
            exchange_config = {
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
                'timeout': 10000,
                'rateLimit': 1200
            }

            if not self.config.get('api_key') or not self.config.get('api_secret'):
                if not self.paper_trading:
                    self.logger.error(f"No API credentials for {self.exchange_id}")
                    return False
                self.logger.info(f"Running {self.exchange_id} in PAPER TRADING mode")

            exchange_config.update({
                'apiKey': self.config.get('api_key', ''),
                'secret': self.config.get('api_secret', ''),
                'sandbox': self.config.get('sandbox', True)
            })

            self.exchange = exchange_class(exchange_config)
            await self.exchange.load_markets()
            await self._verify_real_connection()

            self.trading_pairs = {
                s: m for s, m in self.exchange.markets.items() if m.get("active", False)
            }

            self.is_connected = True
            self.logger.info(f"Connected to {self.exchange_id} ({'paper' if self.paper_trading else 'live'})")
            self.logger.info(f"{self.exchange_id}: {len(self.trading_pairs)} trading pairs")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.exchange_id}: {e}")
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
            for symbol in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']:
                try:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    if ticker and ticker.get('bid') and ticker.get('ask'):
                        self.logger.info(f"Verified real data from {self.exchange_id}: {symbol} = {ticker['last']}")
                        return
                except Exception:
                    continue
            raise Exception("Failed to verify market data")
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
        if self.paper_trading:
            ticker = await self.get_ticker(symbol)
            price = ticker.get('ask' if side == 'buy' else 'bid', 0)
            self.logger.info(f"PAPER TRADE: {side} {qty} {symbol} at {price}")
            return {
                'id': f"paper_{symbol}_{side}",
                'symbol': symbol,
                'side': side,
                'amount': qty,
                'price': price,
                'status': 'closed',
                'filled': qty,
                'average': price,
                'timestamp': asyncio.get_event_loop().time() * 1000
            }
        try:
            order = await self.exchange.create_market_order(symbol, side, qty)
            self.logger.info(f"LIVE TRADE EXECUTED: {order}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing order on {self.exchange_id}: {e}")
            return {}

    async def get_account_balance(self) -> Dict[str, float]:
        if not self.is_connected:
            return {}
        try:
            balance = await self.exchange.fetch_balance()
            return {c: i.get('free', 0.0) for c, i in balance.items() if isinstance(i, dict) and i.get('free', 0) > 0}
        except Exception as e:
            self.logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {}

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
