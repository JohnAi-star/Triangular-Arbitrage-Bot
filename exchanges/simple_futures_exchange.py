"""
Simple futures exchange adapter that wraps UnifiedExchange
"""

import logging
from exchanges.unified_exchange import UnifiedExchange

class SimpleFuturesExchange:
    """Simple adapter for futures trading using UnifiedExchange"""
    
    def __init__(self, config: dict):
        self.exchange = UnifiedExchange(config)
        self.logger = logging.getLogger(__name__)
    
    async def get_ticker(self, symbol: str):
        """Get ticker price"""
        return await self.exchange.get_ticker(symbol)
    
    async def get_futures_balance(self, currency: str = "USDT") -> float:
        """Get futures balance - placeholder implementation"""
        try:
            balance = await self.exchange.get_account_balance()
            return balance.get(currency, {}).get('free', 0.0)
        except:
            return 0.0
    
    async def close(self):
        """Close the exchange"""
        if hasattr(self.exchange, 'close'):
            await self.exchange.close()