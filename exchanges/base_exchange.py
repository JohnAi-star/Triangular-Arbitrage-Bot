"""
Base abstract class for all exchange wrappers.
Defines the required interface for UnifiedExchange and any other exchange classes.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple, Callable


class BaseExchange(ABC):
    """Abstract base class for exchange implementations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exchange_id = config.get('exchange_id', 'unknown')
        self.is_connected = False

    # ---- Connection Management ----
    @abstractmethod
    async def connect(self) -> bool:
        """Establish a connection to the exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the exchange connection."""
        pass

    # ---- Market Data ----
    @abstractmethod
    async def get_trading_pairs(self) -> List[str]:
        """Return all available trading pairs on the exchange."""
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch the current ticker (bid/ask/last price) for a symbol."""
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 5) -> Dict[str, Any]:
        """Fetch order book (bids/asks) for a symbol."""
        pass

    # ---- WebSocket & Streaming ----
    @abstractmethod
    async def start_websocket_stream(self, symbols: List[str], callback: Callable) -> None:
        """Stream live ticker/order book updates via a callback."""
        pass

    # ---- Trading ----
    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """Place a market order (buy or sell)."""
        pass

    # ---- Account Data ----
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, float]:
        """Fetch available account balances."""
        pass

    @abstractmethod
    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Return (maker_fee, taker_fee) for a symbol."""
        pass

    @abstractmethod
    async def check_fee_token_balance(self) -> float:
        """
        Check balance of the exchange's fee token (like BNB or similar)
        to determine if fee discounts can be applied.
        """
        pass

    @abstractmethod
    async def check_bnb_balance(self) -> float:
        """
        Check BNB (or equivalent) balance explicitly for exchanges like Binance.
        """
        pass