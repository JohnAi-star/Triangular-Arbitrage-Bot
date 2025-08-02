import sys
import asyncio
import signal
from typing import Dict, Any
from config.config import Config
from exchanges.unified_exchange import UnifiedExchange
from arbitrage.triangle_detector import TriangleDetector
from arbitrage.trade_executor import TradeExecutor
from utils.logger import setup_logger

def safe_unicode_text(text: str) -> str:
    """Convert Unicode symbols to Windows-safe equivalents."""
    if sys.platform.startswith('win'):
        replacements = {
            '→': '->',
            '✅': '[OK]',
            '❌': '[FAIL]',
            '🔁': '[RETRY]',
            '💰': '$',
            '📊': '[STATS]',
            '🎯': '[TARGET]',
            '⚠️': '[WARN]',
            '🚀': '[START]',
            '🔺': '[BOT]'
        }
        for unicode_char, ascii_equiv in replacements.items():
            text = text.replace(unicode_char, ascii_equiv)
    return text

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
                self.logger.error(safe_unicode_text("❌ CRITICAL: Invalid configuration!"))
                self.logger.error("The bot requires REAL API credentials to fetch market data.")
                self.logger.error("Please configure your .env file with valid exchange credentials.")
                return False
            
            self.logger.info(safe_unicode_text("✅ Configuration validated - real exchange credentials found"))
            self.logger.info("Initializing Triangular Arbitrage Bot...")
            
            # Log trading mode clearly
            trading_mode = "PAPER TRADING (SIMULATION)" if Config.PAPER_TRADING else "LIVE TRADING (REAL MONEY)"
            self.logger.info(f"Trading Mode: {trading_mode}")
            
            self.logger.info(f"Configuration: {Config.to_dict()}")
            
            # Initialize exchange
            exchange_config = {
                'exchange_id': 'binance',
                'api_key': Config.BINANCE_API_KEY,
                'api_secret': Config.BINANCE_API_SECRET,
                'sandbox': Config.BINANCE_SANDBOX,
                'fee_token': 'BNB',
                'fee_discount': 0.25,
                'websocket_reconnect_attempts': Config.WEBSOCKET_RECONNECT_ATTEMPTS,
                'websocket_reconnect_delay': Config.WEBSOCKET_RECONNECT_DELAY
            }
            
            self.exchange = UnifiedExchange(exchange_config)
            
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
        self.logger.info(safe_unicode_text("🚀 Starting Triangular Arbitrage Bot..."))
        
        # Log current trading mode
        mode = "PAPER TRADING" if Config.PAPER_TRADING else "LIVE TRADING"
        self.logger.info(f"Bot starting in {mode} mode")
        
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
                    self.logger.info(safe_unicode_text(f"🎯 Opportunity #{self.opportunities_found}: {opportunity}"))
                    
                    # Execute if profitable
                    if await self.executor.execute_arbitrage(opportunity):
                        self.trades_executed += 1
                        self.logger.info(safe_unicode_text(f"✅ Trade #{self.trades_executed} completed successfully"))
                    else:
                        self.logger.info(safe_unicode_text("❌ Trade execution failed or declined"))
                
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
                    safe_unicode_text(f"📊 Status - Opportunities found: {self.opportunities_found}, "
                    f"Trades executed: {self.trades_executed}"
                    )
                )
                
                if balance:
                    top_balances = sorted(
                        balance.items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:5]
                    
                    balance_str = ", ".join([f"{k}: {v:.6f}" for k, v in top_balances])
                    self.logger.info(safe_unicode_text(f"💰 Top balances - {balance_str}"))
                
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
    startup_text = safe_unicode_text("""
    [BOT] Triangular Arbitrage Bot
    ==========================
    Production-ready bot for detecting and executing triangular arbitrage opportunities.
    
    Press Ctrl+C to stop the bot gracefully.""")
    
    print(startup_text)
    
    # Show current trading mode prominently
    mode = "PAPER TRADING (SIMULATION)" if Config.PAPER_TRADING else "LIVE TRADING (REAL MONEY)"
    print(f"\n    Current Mode: {mode}")
    if not Config.PAPER_TRADING:
        print("    WARNING: This will execute REAL trades with REAL money!")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(safe_unicode_text("\nGoodbye! [WAVE]"))