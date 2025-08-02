"""
Multi-exchange manager and triangle detector for arbitrage opportunities.
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

print(f"Multi-Exchange Manager (Commit: {GIT_COMMIT})")
# -----------------------------------------------

import asyncio
from typing import Dict, List, Any, Optional, Tuple
from exchanges.base_exchange import BaseExchange
from config.exchanges_config import SUPPORTED_EXCHANGES
from config.config import Config
from utils.logger import setup_logger


class MultiExchangeManager:
    """Manages connections to multiple exchanges and detects arbitrage triangles."""

    def __init__(self):
        self.logger = setup_logger('MultiExchangeManager')
        self.exchanges: Dict[str, BaseExchange] = {}
        self.connected_exchanges: List[str] = []
        self.triangles: Dict[str, List[Tuple[str, str, str]]] = {}

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
        """Create exchange instance with proper configuration."""
        from exchanges.unified_exchange import UnifiedExchange

        exchange_config = SUPPORTED_EXCHANGES[exchange_id]
        credentials = Config.EXCHANGE_CREDENTIALS.get(exchange_id, {})

        # Log credential status for debugging
        api_key = credentials.get('api_key', '').strip()
        api_secret = credentials.get('api_secret', '').strip()
        
        self.logger.info(f"🔑 Checking credentials for {exchange_id}:")
        self.logger.info(f"   API Key: {'SET (' + api_key[:8] + '...)' if api_key else 'MISSING'}")
        self.logger.info(f"   API Secret: {'SET' if api_secret else 'MISSING'}")
        self.logger.info(f"   Enabled: {credentials.get('enabled', False)}")
        
        if not credentials.get('enabled'):
            self.logger.error(f"❌ No valid credentials for {exchange_id}")
            return None

        config = {
            'exchange_id': exchange_id,
            'api_key': api_key,
            'api_secret': api_secret,
            'passphrase': credentials.get('passphrase', ''),  # For KuCoin
            'sandbox': credentials.get('sandbox', False),  # Default to live trading
            'fee_token': exchange_config.get('fee_token'),
            'fee_discount': exchange_config.get('fee_discount', 0.0),
            'zero_fee_pairs': exchange_config.get('zero_fee_pairs', []),
            'maker_fee': exchange_config.get('maker_fee', 0.001),
            'taker_fee': exchange_config.get('taker_fee', 0.001),
            'paper_trading': Config.PAPER_TRADING
        }

        return UnifiedExchange(config)

    async def get_all_trading_pairs(self) -> Dict[str, List[str]]:
        """Fetch all trading pairs from connected exchanges."""
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

    async def build_triangles(self) -> None:
        """Build valid triangular arbitrage opportunities for all exchanges."""
        self.triangles.clear()

        for exchange_id, exchange in self.exchanges.items():
            try:
                pairs = await exchange.get_trading_pairs()
                valid_pairs = set(pairs)

                triangles = []
                for pair1 in valid_pairs:
                    base1, quote1 = pair1.split('/')
                    for pair2 in valid_pairs:
                        if pair2 == pair1:
                            continue
                        if base1 in pair2 or quote1 in pair2:
                            for pair3 in valid_pairs:
                                if pair3 in (pair1, pair2):
                                    continue
                                combined = {base1, quote1}
                                combined.update(pair2.split('/'))
                                combined.update(pair3.split('/'))
                                if len(combined) == 3:
                                    triangles.append((pair1, pair2, pair3))

                unique_triangles = list({tuple(sorted(tri)) for tri in triangles})
                self.triangles[exchange_id] = unique_triangles

                self.logger.info(
                    f"Found {len(unique_triangles)} valid triangles for {exchange_id}"
                )

            except Exception as e:
                self.logger.error(f"Error building triangles for {exchange_id}: {e}")
                self.triangles[exchange_id] = []

    async def start_all_websockets(self, callback) -> None:
        """Start WebSocket streams for all connected exchanges."""
        tasks = []

        for exchange_id, exchange in self.exchanges.items():
            try:
                pairs = await exchange.get_trading_pairs()
                limited_pairs = pairs[:100]

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

    def get_triangles(self, exchange_id: str) -> List[Tuple[str, str, str]]:
        """Get prebuilt triangles for a specific exchange."""
        return self.triangles.get(exchange_id, [])