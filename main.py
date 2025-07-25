import asyncio
import signal
import sys
from typing import Dict, Any
from config.config import Config
from exchanges.binance_exchange import BinanceExchange
from arbitrage.triangle_detector import TriangleDetector
from arbitrage.trade_executor import TradeExecutor
from utils.logger import setup_logger

class TriangularArbitrageBot:
    """Main triangular arbitrage bot."""
    
    def __init__(self):
        self.logger = setup_logger('ArbitrageBot', Config.LOG_LEVEL)
        self.exchange = None
        self.detector = None
        self.executor = None
        self.running = False
        self.opportunities_found = 0
        self.trades_executed = 0
        
    async def initialize(self) -> bool:
        """Initialize the bot components."""
        try:
            # Validate configuration
            if not Config.validate():
                self.logger.error("Invalid configuration. Please check your environment variables.")
                return False
            
            self.logger.info("Initializing Triangular Arbitrage Bot...")
            self.logger.info(f"Configuration: {Config.to_dict()}")
            
            # Initialize exchange
            exchange_config = {
                'api_key': Config.BINANCE_API_KEY,
                'api_secret': Config.BINANCE_API_SECRET,
                'sandbox': Config.BINANCE_SANDBOX,
                'bnb_fee_discount': Config.BNB_FEE_DISCOUNT,
                'websocket_reconnect_attempts': Config.WEBSOCKET_RECONNECT_ATTEMPTS,
                'websocket_reconnect_delay': Config.WEBSOCKET_RECONNECT_DELAY
            }
            
            self.exchange = BinanceExchange(exchange_config)
            
            if not await self.exchange.connect():
                self.logger.error("Failed to connect to exchange")
                return False
            
            # Initialize detector
            detector_config = {
                'min_profit_percentage': Config.MIN_PROFIT_PERCENTAGE,
                'max_trade_amount': Config.MAX_TRADE_AMOUNT,
                'max_slippage_percentage': Config.MAX_SLIPPAGE_PERCENTAGE
            }
            
            self.detector = TriangleDetector(self.exchange, detector_config)
            await self.detector.initialize()
            
            # Initialize executor
            executor_config = {
                'enable_manual_confirmation': Config.ENABLE_MANUAL_CONFIRMATION,
                'order_timeout_seconds': Config.ORDER_TIMEOUT_SECONDS
            }
            
            self.executor = TradeExecutor(self.exchange, executor_config)
            
            self.logger.info("Bot initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize bot: {e}")
            return False
    
    async def start(self) -> None:
        """Start the arbitrage bot."""
        if not await self.initialize():
            return
        
        self.running = True
        self.logger.info("🚀 Starting Triangular Arbitrage Bot...")
        
        try:
            # Get all trading pairs for WebSocket
            trading_pairs = await self.exchange.get_trading_pairs()
            
            # Start WebSocket stream
            websocket_task = asyncio.create_task(
                self.exchange.start_websocket_stream(
                    trading_pairs[:100],  # Limit for demo
                    self._handle_price_update
                )
            )
            
            # Start opportunity scanning
            scanning_task = asyncio.create_task(self._scan_loop())
            
            # Start status reporting
            status_task = asyncio.create_task(self._status_loop())
            
            # Wait for tasks
            await asyncio.gather(
                websocket_task,
                scanning_task,
                status_task,
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
        finally:
            await self.cleanup()
    
    async def _handle_price_update(self, data: Dict[str, Any]) -> None:
        """Handle WebSocket price updates."""
        try:
            await self.detector.update_prices(data)
        except Exception as e:
            self.logger.error(f"Error handling price update: {e}")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop for arbitrage opportunities."""
        while self.running:
            try:
                opportunities = await self.detector.scan_opportunities()
                
                for opportunity in opportunities:
                    self.opportunities_found += 1
                    self.logger.info(f"🎯 Opportunity #{self.opportunities_found}: {opportunity}")
                    
                    # Execute if profitable
                    if await self.executor.execute_arbitrage(opportunity):
                        self.trades_executed += 1
                        self.logger.info(f"✅ Trade #{self.trades_executed} completed successfully")
                    else:
                        self.logger.info("❌ Trade execution failed or declined")
                
                # Wait before next scan
                await asyncio.sleep(1)  # Adjust scan frequency as needed
                
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {e}")
                await asyncio.sleep(5)
    
    async def _status_loop(self) -> None:
        """Status reporting loop."""
        while self.running:
            try:
                # Check account balance
                balance = await self.exchange.get_account_balance()
                
                # Report status every 5 minutes
                self.logger.info(
                    f"📊 Status - Opportunities found: {self.opportunities_found}, "
                    f"Trades executed: {self.trades_executed}"
                )
                
                if balance:
                    top_balances = sorted(
                        balance.items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:5]
                    
                    balance_str = ", ".join([f"{k}: {v:.6f}" for k, v in top_balances])
                    self.logger.info(f"💰 Top balances - {balance_str}")
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error in status loop: {e}")
                await asyncio.sleep(300)
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("Shutting down bot...")
        self.running = False
        
        if self.exchange:
            await self.exchange.disconnect()
        
        self.logger.info("Bot shutdown complete")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

async def main():
    """Main entry point."""
    bot = TriangularArbitrageBot()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, bot._signal_handler)
    signal.signal(signal.SIGTERM, bot._signal_handler)
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nReceived interrupt signal, shutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    print("""
    🔺 Triangular Arbitrage Bot
    ==========================
    Production-ready bot for detecting and executing triangular arbitrage opportunities.
    
    Press Ctrl+C to stop the bot gracefully.
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")