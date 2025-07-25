from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
import asyncio

class BaseExchange(ABC):
    """Abstract base class for exchange implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.is_connected = False
        
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the exchange."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""
        pass
    
    @abstractmethod
    async def get_trading_pairs(self) -> List[str]:
        """Get all available trading pairs."""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information for a symbol."""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get orderbook for a symbol."""
        pass
    
    @abstractmethod
    async def start_websocket_stream(self, symbols: List[str], callback) -> None:
        """Start WebSocket stream for real-time price updates."""
        pass
    
    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        """Place a market order."""
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balances."""
        pass
    
    @abstractmethod
    async def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        """Get trading fees for a symbol (maker, taker)."""
        pass
    
    @abstractmethod
    async def check_bnb_balance(self) -> float:
        """Check BNB balance for fee discounts."""
        pass