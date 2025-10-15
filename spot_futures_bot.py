#!/usr/bin/env python3
"""
Spot-Futures Arbitrage Bot - FIXED VERSION
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchanges.unified_exchange import UnifiedExchange
from exchanges.kucoin_futures_exchange import KuCoinFuturesExchange
from arbitrage.spot_futures_detector import SpotFuturesDetector
from arbitrage.spot_futures_executor import SpotFuturesExecutor
from arbitrage.spot_futures_monitor import SpotFuturesMonitor
from utils.trade_logger import get_trade_logger

class SpotFuturesBot:
    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()
        
        # Initialize exchanges using CORRECT classes
        self.spot_exchange = self._create_spot_exchange()
        self.futures_exchange = self._create_futures_exchange()
        
        # Initialize trade logger
        self.trade_logger = get_trade_logger()
        
        # Initialize components
        self.detector = SpotFuturesDetector(self.spot_exchange, self.futures_exchange)
        self.executor = SpotFuturesExecutor(self.spot_exchange, self.futures_exchange, self.trade_logger)
        self.monitor = SpotFuturesMonitor(self.detector, self.executor, self.trade_logger)
        
        self.is_running = False
        self.auto_trade = config.get('auto_trade', False)
        
        # Trading parameters
        self.min_profit_threshold = config.get('min_profit_threshold', 0.5)
        self.trade_amount = config.get('trade_amount', 20.0)
        self.check_interval = config.get('check_interval', 1.0)
        
        # Performance tracking
        self.opportunities_found = 0
        self.trades_executed = 0
        self.start_time = None
        
    def _create_spot_exchange(self):
        """Create spot exchange using UnifiedExchange with KuCoin"""
        self.logger.info("Creating spot exchange with sandbox=False (LIVE MODE)")

        # Create KuCoin spot exchange config
        spot_config = {
            'exchange_id': 'kucoin',
            'api_key': self.config['spot_api_key'],
            'api_secret': self.config['spot_api_secret'],
            'passphrase': self.config.get('spot_api_passphrase', ''),
            'sandbox': False
        }
        return UnifiedExchange(spot_config)
    
    def _create_futures_exchange(self):
        """Create futures exchange using KuCoinFuturesExchange class"""
        self.logger.info("Creating futures exchange with sandbox=False (LIVE MODE)")

        # Use KuCoinFuturesExchange with correct parameters
        return KuCoinFuturesExchange(
            api_key=self.config['futures_api_key'],
            api_secret=self.config['futures_api_secret'],
            api_passphrase=self.config.get('futures_api_passphrase', ''),
            is_sandbox=False
        )
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('spot_futures_bot.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def start(self):
        """Start the spot-futures arbitrage bot"""
        self.is_running = True
        self.start_time = datetime.now()
        
        mode = "LIVE TRADING"
        self.logger.info(f"Starting Spot-Futures Arbitrage Bot - {mode} MODE")
        self.logger.info(f"Configuration: Min Profit={self.min_profit_threshold}% | "
                        f"Trade Amount=${self.trade_amount} | Auto-Trade={self.auto_trade}")
        
        self.logger.warning("LIVE TRADING MODE - REAL MONEY AT RISK!")
        
        try:
            # Test API connections
            await self.test_connections()
            
            # Start position monitoring
            asyncio.create_task(self.monitor.start_monitoring())
            
            # Start opportunity scanning
            await self.monitor_opportunities()
            
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            await self.stop()
    
    async def test_connections(self):
        """Test API connections to both spot and futures"""
        self.logger.info("Testing API connections...")

        # Connect exchanges first
        await self.spot_exchange.connect()
        await self.futures_exchange.connect()

        # Test spot connection
        try:
            ticker = await self.spot_exchange.get_ticker('BTC/USDT')
            btc_price = ticker.get('last', 0)
            self.logger.info(f"Spot connection OK - BTC Price: ${btc_price:,.2f}")

        except Exception as e:
            self.logger.error(f"Spot connection failed: {e}")
            raise

        # Test futures connection
        try:
            ticker = await self.futures_exchange.get_ticker('BTC/USDT')
            btc_futures_price = ticker.get('last', 0)
            self.logger.info(f"Futures connection OK - BTC Futures Price: ${btc_futures_price:,.2f}")

            # Log the spread
            if btc_price > 0 and btc_futures_price > 0:
                spread = ((btc_futures_price - btc_price) / btc_price) * 100
                self.logger.info(f"Current Spot-Futures Spread: {spread:.4f}%")

        except Exception as e:
            self.logger.error(f"Futures connection failed: {e}")
            raise
    
    async def opportunity_callback(self, opportunities: List):
        """Callback when opportunities are found"""
        self.opportunities_found += len(opportunities)
        
        for opportunity in opportunities:
            self.logger.info(f"Opportunity: {opportunity}")
            
            if self.auto_trade and opportunity.is_tradeable:
                try:
                    result = await self.executor.execute_arbitrage(opportunity, self.trade_amount)
                    
                    if 'position_id' in result:
                        self.trades_executed += 1
                        self.logger.info(f"Auto-trade executed: {result['position_id']}")
                    else:
                        self.logger.warning(f"Trade execution failed: {result}")
                        
                except Exception as e:
                    self.logger.error(f"Trade execution error: {e}")
            else:
                # Just log the opportunity without trading
                self.logger.info(f"Opportunity found (auto-trade disabled): {opportunity.symbol} - {opportunity.spread_percentage:.4f}%")
    
    async def monitor_opportunities(self):
        """Monitor for arbitrage opportunities with status updates"""
        self.logger.info("Starting opportunity monitoring...")
    
        scan_count = 0
        last_status_time = asyncio.get_event_loop().time()
    
        while self.is_running:
            try:
                opportunities = await self.detector.scan_opportunities(self.min_profit_threshold)
                scan_count += 1
            
                if opportunities:
                    await self.opportunity_callback(opportunities)
            
                # Print status every 10 scans or 30 seconds
                current_time = asyncio.get_event_loop().time()
                if scan_count % 10 == 0 or (current_time - last_status_time) >= 30:
                    self.logger.info(f"Active scanning... Scans: {scan_count} | Opportunities found: {self.opportunities_found}")
                    last_status_time = current_time
            
                await asyncio.sleep(self.check_interval)
            
            except Exception as e:
                self.logger.error(f"Error in opportunity monitoring: {e}")
                await asyncio.sleep(5)
    
    async def stop(self):
        """Stop the bot and close all positions"""
        self.is_running = False
        self.logger.info("Stopping Spot-Futures Arbitrage Bot")
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        # Close all active positions
        active_positions = self.executor.get_active_positions()
        if active_positions:
            self.logger.info(f"Closing {len(active_positions)} active positions...")
            
            for position in active_positions:
                if position['status'] == 'open':
                    try:
                        await self.executor.close_position(position['position_id'])
                        self.logger.info(f"Closed position: {position['position_id']}")
                    except Exception as e:
                        self.logger.error(f"Error closing position {position['position_id']}: {e}")
        
        # Close exchange sessions
        if hasattr(self.futures_exchange, 'close'):
            await self.futures_exchange.close()

# Configuration - FIXED: Use environment variables
CONFIG = {
    'spot_api_key': os.getenv('KUCOIN_API_KEY', ''),
    'spot_api_secret': os.getenv('KUCOIN_API_SECRET', ''),
    'spot_api_passphrase': os.getenv('KUCOIN_PASSPHRASE', ''),
    'futures_api_key': os.getenv('KUCOIN_API_KEY', ''),
    'futures_api_secret': os.getenv('KUCOIN_API_SECRET', ''),
    'futures_api_passphrase': os.getenv('KUCOIN_PASSPHRASE', ''),
    'min_profit_threshold': 0.5,
    'trade_amount': 20.0,
    'check_interval': 1.0,
    'auto_trade': False,
    'sandbox': False
}

async def main():
    """Main entry point"""
    print("Spot-Futures Arbitrage Bot")
    print("==========================")
    
    # Load configuration
    config = CONFIG.copy()
    
    # Safety confirmation
    if not config.get('sandbox', True):
        print("WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!")
        confirmation = input("Type 'LIVE' to confirm live trading: ")
        if confirmation != 'LIVE':
            print("Switching to sandbox mode for safety")
            config['sandbox'] = True
    
    if config.get('auto_trade', False):
        print("WARNING: AUTO-TRADE ENABLED")
        confirmation = input("Type 'AUTO' to confirm auto-trading: ")
        if confirmation != 'AUTO':
            print("Disabling auto-trade for safety")
            config['auto_trade'] = False
    
    # Create and start bot
    bot = SpotFuturesBot(config)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nShutting down bot...")
        await bot.stop()
    except Exception as e:
        print(f"Fatal error: {e}")
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())