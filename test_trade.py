#!/usr/bin/env python3
"""
Test Real Trading with Gate.io Account
This script will execute a REAL trade on your Gate.io account for testing
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.unified_exchange import UnifiedExchange
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from arbitrage.trade_executor import TradeExecutor
from exchanges.multi_exchange_manager import MultiExchangeManager
from utils.websocket_manager import WebSocketManager
from utils.logger import setup_logger
from config.config import Config

load_dotenv()

class RealTradeTest:
    """Test real trading with Gate.io account"""
    
    def __init__(self):
        self.logger = setup_logger('RealTradeTest', 'INFO')
        self.exchange_manager = None
        self.detector = None
        self.executor = None
        
    async def test_gateio_connection(self):
        """Test Gate.io connection and balance"""
        try:
            # Check Gate.io credentials
            api_key = os.getenv('GATE_API_KEY', '').strip()
            api_secret = os.getenv('GATE_API_SECRET', '').strip()
            
            if not api_key or not api_secret:
                self.logger.error("❌ CRITICAL: No Gate.io API credentials found!")
                self.logger.error("Please set GATEIO_API_KEY and GATEIO_API_SECRET in your .env file")
                return False
            
            self.logger.info(f"✅ Gate.io API Key found: {api_key[:8]}...{api_key[-4:]}")
            
            # Initialize Gate.io exchange
            config = {
                'exchange_id': 'gateio',
                'api_key': api_key,
                'api_secret': api_secret,
                'sandbox': False,  # LIVE TRADING
                'fee_token': 'GT',
                'fee_discount': 0.15,
                'maker_fee': 0.002,
                'taker_fee': 0.002
            }
            
            exchange = UnifiedExchange(config)
            
            if not await exchange.connect():
                self.logger.error("❌ Failed to connect to Gate.io")
                return False
            
            # Get real balance
            balance = await exchange.get_account_balance()
            if balance:
                total_usd = await exchange._calculate_usd_value(balance)
                self.logger.info(f"💰 REAL GATE.IO BALANCE: ~${total_usd:.2f} USD")
                
                for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True):
                    if amount > 0.001:
                        self.logger.info(f"   {currency}: {amount:.8f}")
                
                if total_usd < 5:
                    self.logger.warning(f"⚠️ Low balance: ${total_usd:.2f} - minimum $5 recommended")
                    if total_usd > 0:
                        self.logger.info("✅ Balance detected but low - test will continue")
                else:
                    self.logger.info(f"✅ Sufficient balance for testing: ${total_usd:.2f}")
                
                await exchange.disconnect()
                return True
            else:
                self.logger.error("❌ No balance detected")
                await exchange.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Gate.io connection test failed: {e}")
            return False
    
    async def find_real_opportunities(self):
        """Find real arbitrage opportunities on Gate.io"""
        try:
            self.logger.info("🔍 Finding REAL arbitrage opportunities on Gate.io...")
            
            # Initialize WebSocket manager
            websocket_manager = WebSocketManager()
            websocket_manager.run_in_background()
            
            # Initialize exchange manager
            self.exchange_manager = MultiExchangeManager()
            success = await self.exchange_manager.initialize_exchanges(['gateio'])
            
            if not success:
                self.logger.error("❌ Failed to initialize Gate.io")
                return []
            
            # Initialize detector
            self.detector = MultiExchangeDetector(
                self.exchange_manager,
                websocket_manager,
                {
                    'min_profit_percentage': 0.1,  # 0.1% minimum for real trading
                    'max_trade_amount': 50  # $50 for testing
                }
            )
            
            await self.detector.initialize()
            
            # Scan for opportunities
            opportunities = await self.detector.scan_all_opportunities()
            
            if opportunities:
                self.logger.info(f"💎 Found {len(opportunities)} REAL opportunities on Gate.io!")
                
                # Show profitable opportunities
                profitable = [opp for opp in opportunities if opp.profit_percentage >= 0.5]
                
                if profitable:
                    self.logger.info(f"🎯 {len(profitable)} profitable opportunities (≥0.5%):")
                    for i, opp in enumerate(profitable[:5]):
                        self.logger.info(f"   {i+1}. {' → '.join(opp.triangle_path[:3])}: {opp.profit_percentage:.4f}% (${opp.profit_amount:.2f})")
                    
                    return profitable
                else:
                    self.logger.info("⚠️ No opportunities above 0.5% profit threshold")
                    self.logger.info("Showing all opportunities for reference:")
                    for i, opp in enumerate(opportunities[:10]):
                        self.logger.info(f"   {i+1}. {' → '.join(opp.triangle_path[:3])}: {opp.profit_percentage:.4f}%")
                    return []
            else:
                self.logger.info("❌ No opportunities found on Gate.io")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error finding opportunities: {e}")
            return []
    
    async def execute_test_trade(self, opportunity):
        """Execute a REAL test trade on Gate.io"""
        try:
            self.logger.info("🚀 EXECUTING REAL TEST TRADE ON GATE.IO...")
            self.logger.info(f"   Opportunity: {' → '.join(opportunity.triangle_path[:3])}")
            self.logger.info(f"   Expected Profit: {opportunity.profit_percentage:.4f}% (${opportunity.profit_amount:.2f})")
            self.logger.info("⚠️ WARNING: This will execute REAL trades with REAL money!")
            
            # Ask for confirmation
            print("\n" + "="*60)
            print("🔴 REAL TRADE CONFIRMATION")
            print("="*60)
            print(f"Exchange: Gate.io")
            print(f"Triangle: {' → '.join(opportunity.triangle_path[:3])}")
            print(f"Trade Amount: ${opportunity.initial_amount:.2f}")
            print(f"Expected Profit: {opportunity.profit_percentage:.4f}% (${opportunity.profit_amount:.2f})")
            print("⚠️ WARNING: This will execute REAL trades with REAL money!")
            print("⚠️ These trades will appear in your Gate.io account!")
            print("="*60)
            
            confirm = input("Type 'EXECUTE' to proceed with REAL trade: ").strip()
            
            if confirm != 'EXECUTE':
                self.logger.info("❌ Trade cancelled by user")
                return False
            
            # Initialize executor
            self.executor = TradeExecutor(self.exchange_manager, {
                'auto_trading': False,  # Manual execution
                'paper_trading': False,  # REAL TRADING
                'enable_manual_confirmation': False  # Already confirmed
            })
            
            # Execute the trade
            self.logger.info("🚀 Executing REAL trade on Gate.io...")
            success = await self.executor.execute_arbitrage(opportunity)
            
            if success:
                self.logger.info("🎉 REAL TRADE EXECUTED SUCCESSFULLY!")
                self.logger.info("✅ Check your Gate.io account for the executed trades")
                self.logger.info("✅ Your balance should reflect the profit/loss")
                return True
            else:
                self.logger.error("❌ Trade execution failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error executing test trade: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.exchange_manager:
            await self.exchange_manager.disconnect_all()

async def main():
    """Main test function"""
    print("🔴 REAL TRADING TEST - Gate.io")
    print("=" * 50)
    print("This script will:")
    print("1. Connect to your REAL Gate.io account")
    print("2. Find REAL arbitrage opportunities")
    print("3. Execute a REAL test trade")
    print("4. Show the trade in your Gate.io account")
    print("=" * 50)
    
    test = RealTradeTest()
    
    try:
        # Test connection
        if not await test.test_gateio_connection():
            print("❌ Gate.io connection test failed")
            return
        
        # Find opportunities
        opportunities = await test.find_real_opportunities()
        
        if not opportunities:
            print("❌ No profitable opportunities found for testing")
            print("Try again later when market conditions are more favorable")
            return
        
        # Select best opportunity
        best_opportunity = opportunities[0]
        print(f"\n🎯 Best opportunity found:")
        print(f"   Triangle: {' → '.join(best_opportunity.triangle_path[:3])}")
        print(f"   Profit: {best_opportunity.profit_percentage:.4f}% (${best_opportunity.profit_amount:.2f})")
        
        # Execute test trade
        success = await test.execute_test_trade(best_opportunity)
        
        if success:
            print("\n🎉 TEST TRADE COMPLETED SUCCESSFULLY!")
            print("✅ Check your Gate.io account for the executed trades")
            print("✅ Your balance should reflect the profit")
        else:
            print("\n❌ Test trade failed")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        await test.cleanup()

if __name__ == "__main__":
    asyncio.run(main())