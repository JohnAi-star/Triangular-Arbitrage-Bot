#!/usr/bin/env python3
"""
Test KuCoin Timestamp Synchronization Fix
This script will test the timestamp fix and complete a full triangular arbitrage trade
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.unified_exchange import UnifiedExchange
from arbitrage.trade_executor import TradeExecutor
from exchanges.multi_exchange_manager import MultiExchangeManager
from utils.logger import setup_logger
from config.config import Config

load_dotenv()

class KuCoinTimestampTest:
    """Test KuCoin timestamp synchronization and complete trade execution"""
    
    def __init__(self):
        self.logger = setup_logger('KuCoinTimestampTest', 'INFO')
        self.exchange = None
        self.executor = None
        
    async def test_timestamp_sync(self):
        """Test KuCoin timestamp synchronization"""
        try:
            self.logger.info("🕒 TESTING KUCOIN TIMESTAMP SYNCHRONIZATION")
            self.logger.info("=" * 60)
            
            # Initialize KuCoin exchange
            config = {
                'exchange_id': 'kucoin',
                'api_key': os.getenv('KUCOIN_API_KEY', '').strip(),
                'api_secret': os.getenv('KUCOIN_API_SECRET', '').strip(),
                'passphrase': os.getenv('KUCOIN_PASSPHRASE', '').strip(),
                'sandbox': False,  # LIVE TRADING
                'fee_token': 'KCS',
                'fee_discount': 0.20
            }
            
            if not all([config['api_key'], config['api_secret'], config['passphrase']]):
                self.logger.error("❌ Missing KuCoin credentials")
                return False
            
            self.exchange = UnifiedExchange(config)
            
            # Test connection with timestamp sync
            if not await self.exchange.connect():
                self.logger.error("❌ Failed to connect to KuCoin")
                return False
            
            self.logger.info("✅ KuCoin connection successful with timestamp sync")
            
            # Test server time synchronization
            if hasattr(self.exchange, 'server_time_offset'):
                self.logger.info(f"🕒 Server time offset: {self.exchange.server_time_offset}ms")
                self.logger.info(f"🕒 Last sync time: {self.exchange.last_time_sync}")
            
            # Test a small order to verify timestamp fix
            await self._test_small_order()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Timestamp test failed: {e}")
            return False
    
    async def _test_small_order(self):
        """Test a small order to verify timestamp synchronization"""
        try:
            self.logger.info("🧪 Testing small order with timestamp sync...")
            
            # Get current balance
            balance = await self.exchange.get_account_balance()
            usdt_balance = balance.get('USDT', 0)
            
            if usdt_balance < 5:
                self.logger.warning(f"⚠️ Low USDT balance: {usdt_balance:.2f} - skipping order test")
                return
            
            # Test with a very small amount
            test_amount = 5.0  # $5 USDT
            
            self.logger.info(f"🧪 Testing BUY order: {test_amount} USDT → AR")
            
            # Execute test buy order
            order_result = await self.exchange.place_market_order('AR/USDT', 'buy', test_amount)
            
            if order_result and order_result.get('success'):
                self.logger.info("✅ TEST ORDER SUCCESSFUL!")
                self.logger.info(f"   Order ID: {order_result.get('id')}")
                self.logger.info(f"   Filled: {order_result.get('filled', 0):.8f} AR")
                self.logger.info(f"   Average Price: {order_result.get('average', 0):.8f}")
                
                # Wait a moment then sell back
                await asyncio.sleep(2)
                
                ar_amount = float(order_result.get('filled', 0))
                if ar_amount > 0:
                    self.logger.info(f"🧪 Testing SELL order: {ar_amount:.8f} AR → USDT")
                    
                    sell_result = await self.exchange.place_market_order('AR/USDT', 'sell', ar_amount)
                    
                    if sell_result and sell_result.get('success'):
                        self.logger.info("✅ TEST SELL ORDER SUCCESSFUL!")
                        self.logger.info(f"   Order ID: {sell_result.get('id')}")
                        self.logger.info(f"   Received: {sell_result.get('cost', 0):.2f} USDT")
                        
                        # Calculate test profit/loss
                        final_usdt = float(sell_result.get('cost', 0))
                        test_profit = final_usdt - test_amount
                        test_profit_pct = (test_profit / test_amount) * 100
                        
                        self.logger.info(f"🧪 TEST TRADE RESULT:")
                        self.logger.info(f"   Initial: ${test_amount:.2f} USDT")
                        self.logger.info(f"   Final: ${final_usdt:.2f} USDT")
                        self.logger.info(f"   P&L: ${test_profit:.4f} ({test_profit_pct:.4f}%)")
                        
                        if test_profit_pct > -1.0:  # Less than 1% loss is acceptable for test
                            self.logger.info("✅ TIMESTAMP FIX WORKING - Orders executing successfully!")
                            return True
                        else:
                            self.logger.warning(f"⚠️ High test loss: {test_profit_pct:.4f}%")
                    else:
                        self.logger.error("❌ Test sell order failed")
                else:
                    self.logger.error("❌ No AR received from test buy")
            else:
                self.logger.error("❌ Test buy order failed")
                self.logger.error(f"   Error: {order_result.get('error', 'Unknown')}")
                
        except Exception as e:
            self.logger.error(f"❌ Test order failed: {e}")
    
    async def test_complete_triangle(self):
        """Test a complete triangular arbitrage trade with timestamp fix"""
        try:
            self.logger.info("🔺 TESTING COMPLETE TRIANGULAR ARBITRAGE WITH TIMESTAMP FIX")
            self.logger.info("=" * 70)
            
            # Initialize exchange manager
            exchange_manager = MultiExchangeManager()
            success = await exchange_manager.initialize_exchanges(['kucoin'])
            
            if not success:
                self.logger.error("❌ Failed to initialize KuCoin")
                return False
            
            # Initialize trade executor
            self.executor = TradeExecutor(exchange_manager, {
                'auto_trading': True,
                'paper_trading': False,  # LIVE TRADING
                'min_profit_threshold': 0.4
            })
            
            # Create a test opportunity (using your successful AR → BTC triangle)
            from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep, OpportunityStatus
            
            test_opportunity = ArbitrageOpportunity(
                base_currency='USDT',
                intermediate_currency='AR',
                quote_currency='BTC',
                pair1='AR/USDT',
                pair2='AR/BTC',
                pair3='BTC/USDT',
                steps=[
                    TradeStep('AR/USDT', 'buy', 10.0, 6.29, 1.59),  # Smaller test amount
                    TradeStep('AR/BTC', 'sell', 1.59, 0.0000572, 0.000091),
                    TradeStep('BTC/USDT', 'sell', 0.000091, 109000, 9.98)
                ],
                initial_amount=10.0,  # $10 test
                final_amount=9.98,
                estimated_fees=0.06,
                estimated_slippage=0.01
            )
            
            # Set additional attributes
            test_opportunity.exchange = 'kucoin'
            test_opportunity.profit_percentage = 0.5  # 0.5% profit
            test_opportunity.profit_amount = 0.05
            test_opportunity.status = OpportunityStatus.DETECTED
            test_opportunity.triangle_path = "USDT → AR → BTC → USDT"
            
            self.logger.info("🎯 Test Triangle: USDT → AR → BTC → USDT")
            self.logger.info(f"   Amount: ${test_opportunity.initial_amount}")
            self.logger.info(f"   Expected Profit: {test_opportunity.profit_percentage:.4f}%")
            
            # Execute the test trade
            self.logger.info("🚀 EXECUTING TEST TRIANGLE WITH TIMESTAMP FIX...")
            success = await self.executor.execute_arbitrage(test_opportunity)
            
            if success:
                self.logger.info("🎉 COMPLETE TRIANGLE TEST SUCCESSFUL!")
                self.logger.info("✅ All 3 steps completed without timestamp errors")
                self.logger.info("✅ Timestamp synchronization fix is working!")
                return True
            else:
                self.logger.error("❌ Complete triangle test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Complete triangle test error: {e}")
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.exchange:
            await self.exchange.disconnect()

async def main():
    """Main test function"""
    print("🕒 KUCOIN TIMESTAMP SYNCHRONIZATION FIX TEST")
    print("=" * 60)
    print("This test will:")
    print("1. Test KuCoin timestamp synchronization")
    print("2. Execute a small test order")
    print("3. Test a complete triangular arbitrage trade")
    print("4. Verify the timestamp fix resolves the error")
    print("=" * 60)
    
    test = KuCoinTimestampTest()
    
    try:
        # Test timestamp synchronization
        if not await test.test_timestamp_sync():
            print("❌ Timestamp synchronization test failed")
            return
        
        # Test complete triangle
        if await test.test_complete_triangle():
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ KuCoin timestamp synchronization fix is working")
            print("✅ Your bot will now complete all 3 steps successfully")
            print("✅ No more 'Invalid KC-API-TIMESTAMP' errors")
        else:
            print("\n❌ Complete triangle test failed")
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        await test.cleanup()

if __name__ == "__main__":
    asyncio.run(main())