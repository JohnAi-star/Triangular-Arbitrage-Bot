"""
Multi-exchange manager for handling multiple exchange connections.
"""

import asyncio
import ccxt.async_support as ccxt
from typing import Dict, List, Any, Optional
from exchanges.base_exchange import BaseExchange
from config.exchanges_config import SUPPORTED_EXCHANGES
from config.config import Config
from utils.logger import setup_logger

class MultiExchangeManager:
    """Manages connections to multiple exchanges."""
    
    def __init__(self):
        self.logger = setup_logger('MultiExchangeManager')
        self.exchanges: Dict[str, BaseExchange] = {}
        self.connected_exchanges: List[str] = []
        
    async def initialize_exchanges(self, selected_exchanges: List[str] = None) -> bool:
        """Initialize selected exchanges."""
        if selected_exchanges is None:
            selected_exchanges = list(SUPPORTED_EXCHANGES.keys())
        
        success_count = 0
        
        for exchange_id in selected_exchanges:
            if exchange_id not in SUPPORTED_EXCHANGES:
                self.logger.warning(f"Unknown exchange: {exchange_id}")
                continue
                
            try:
                exchange = await self._create_exchange(exchange_id)
                if exchange and await exchange.connect():
                    self.exchanges[exchange_id] = exchange
                    self.connected_exchanges.append(exchange_id)
                    success_count += 1
                    self.logger.info(f"Successfully connected to {exchange_id}")
                else:
                    self.logger.error(f"Failed to connect to {exchange_id}")
                    
            except Exception as e:
                self.logger.error(f"Error initializing {exchange_id}: {e}")
        
        self.logger.info(f"Connected to {success_count}/{len(selected_exchanges)} exchanges")
        return success_count > 0
    
    async def _create_exchange(self, exchange_id: str) -> Optional[BaseExchange]:
        """Create exchange instance."""
        from exchanges.unified_exchange import UnifiedExchange
        
        exchange_config = SUPPORTED_EXCHANGES[exchange_id]
        credentials = Config.EXCHANGE_CREDENTIALS.get(exchange_id, {})
        
        if not credentials.get('enabled') and not Config.PAPER_TRADING:
            self.logger.warning(f"No credentials for {exchange_id}")
            return None
        
        config = {
            'exchange_id': exchange_id,
            'api_key': credentials.get('api_key', ''),
            'api_secret': credentials.get('api_secret', ''),
            'sandbox': credentials.get('sandbox', True),
            'fee_token': exchange_config.get('fee_token'),
            'fee_discount': exchange_config.get('fee_discount', 0.0),
            'zero_fee_pairs': exchange_config.get('zero_fee_pairs', []),
            'maker_fee': exchange_config.get('maker_fee', 0.001),
            'taker_fee': exchange_config.get('taker_fee', 0.001),
            'paper_trading': Config.PAPER_TRADING
        }
        
        return UnifiedExchange(config)
    
    async def get_all_trading_pairs(self) -> Dict[str, List[str]]:
        """Get trading pairs from all connected exchanges."""
        all_pairs = {}
        
        for exchange_id, exchange in self.exchanges.items():
            try:
                pairs = await exchange.get_trading_pairs()
                all_pairs[exchange_id] = pairs
                self.logger.info(f"{exchange_id}: {len(pairs)} trading pairs")
            except Exception as e:
                self.logger.error(f"Error getting pairs from {exchange_id}: {e}")
                all_pairs[exchange_id] = []
        
        return all_pairs
    
    async def start_all_websockets(self, callback) -> None:
        """Start WebSocket streams for all exchanges."""
        tasks = []
        
        for exchange_id, exchange in self.exchanges.items():
            try:
                pairs = await exchange.get_trading_pairs()
                # Limit pairs to avoid overwhelming the system
                limited_pairs = pairs[:100]  # Adjust as needed
                
                task = asyncio.create_task(
                    exchange.start_websocket_stream(limited_pairs, callback),
                    name=f"websocket_{exchange_id}"
                )
                tasks.append(task)
                
            except Exception as e:
                self.logger.error(f"Error starting WebSocket for {exchange_id}: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def disconnect_all(self) -> None:
        """Disconnect from all exchanges."""
        for exchange_id, exchange in self.exchanges.items():
            try:
                await exchange.disconnect()
                self.logger.info(f"Disconnected from {exchange_id}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {exchange_id}: {e}")
        
        self.exchanges.clear()
        self.connected_exchanges.clear()
    
    def get_exchange(self, exchange_id: str) -> Optional[BaseExchange]:
        """Get specific exchange instance."""
        return self.exchanges.get(exchange_id)
    
    def get_connected_exchanges(self) -> List[str]:
        """Get list of connected exchange IDs."""
        return self.connected_exchanges.copy()