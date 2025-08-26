#!/usr/bin/env python3
"""
Test Real Profitable Opportunities
This script will find and test REAL profitable arbitrage opportunities
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.enhanced_triangle_detector import EnhancedTriangleDetector
from arbitrage.market_efficiency_analyzer import MarketEfficiencyAnalyzer
from utils.logger import setup_logger
from config.config import Config

load_dotenv()

class RealOpportunityTester:
    """Test and find real profitable arbitrage opportunities"""
    
    def __init__(self):
        self.logger = setup_logger('RealOpportunityTester', 'INFO')
        self.exchange_manager = None
        self.enhanced_detector = None
        self.market_analyzer = None
        
    async def test_all_methods(self):
        """Test all methods to find profitable opportunities"""
        try:
            self.logger.info("🚀 TESTING ALL METHODS TO FIND REAL PROFITABLE OPPORTUNITIES")
            self.logger.info("=" * 80)
            
            # Initialize exchange manager
            self.exchange_manager = MultiExchangeManager()
            
            # Test different exchanges
            exchanges_to_test = ['kucoin', 'binance', 'gate']
            
            for exchange_id in exchanges_to_test:
                await self._test_exchange_opportunities(exchange_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            return False
    
    async def _test_exchange_opportunities(self, exchange_id: str):
        """Test opportunities on a specific exchange"""
        try:
            self.logger.info(f"\n🔍 TESTING {exchange_id.upper()} FOR PROFITABLE OPPORTUNITIES")
            self.logger.info("-" * 60)
            
            # Connect to exchange
            success = await self.exchange_manager.initialize_exchanges([exchange_id])
            if not success:
                self.logger.error(f"❌ Failed to connect to {exchange_id}")
                return
            
            self.logger.info(f"✅ Connected to {exchange_id}")
            
            # Get exchange instance
            exchange = self.exchange_manager.get_exchange(exchange_id)
            if not exchange:
                self.logger.error(f"❌ Could not get {exchange_id} instance")
                return
            
            # Check balance
            balance = await exchange.get_account_balance()
            if balance:
                total_usd = await exchange._calculate_usd_value(balance) if hasattr(exchange, '_calculate_usd_value') else 0
                self.logger.info(f"💰 {exchange_id.upper()} Balance: ~${total_usd:.2f} USD")
                
                # Show major balances
                major_balances = {k: v for k, v in balance.items() if v > 0.001}
                if major_balances:
                    self.logger.info(f"   Major balances: {major_balances}")
            
            # Initialize enhanced detector
            self.enhanced_detector = EnhancedTriangleDetector(
                self.exchange_manager, min_profit_pct=0.1, max_trade_amount=20.0  # Lower threshold for testing
            )
            
            # Test Method 1: Enhanced Triangle Detection
            self.logger.info(f"\n🎯 METHOD 1: Enhanced Triangle Detection")
            enhanced_opportunities = await self.enhanced_detector.find_profitable_opportunities()
            
            if enhanced_opportunities:
                profitable = [o for o in enhanced_opportunities if o.profit_percentage >= 0.4]
                close_opportunities = [o for o in enhanced_opportunities if 0.1 <= o.profit_percentage < 0.4]
                
                self.logger.info(f"💎 Enhanced Method Results:")
                self.logger.info(f"   Profitable (≥0.4%): {len(profitable)}")
                self.logger.info(f"   Close (0.1-0.4%): {len(close_opportunities)}")
                
                if profitable:
                    self.logger.info(f"🎉 FOUND PROFITABLE OPPORTUNITIES:")
                    for i, opp in enumerate(profitable[:5]):
                        self.logger.info(f"   {i+1}. {opp}")
                elif close_opportunities:
                    self.logger.info(f"📊 Close opportunities (need optimization):")
                    for i, opp in enumerate(close_opportunities[:5]):
                        self.logger.info(f"   {i+1}. {opp}")
            else:
                self.logger.info(f"❌ No opportunities found with enhanced method")
            
            # Test Method 2: Cross-Exchange Arbitrage
            if len(self.exchange_manager.exchanges) >= 2:
                self.logger.info(f"\n🎯 METHOD 2: Cross-Exchange Arbitrage")
                cross_opportunities = await self.enhanced_detector.find_cross_exchange_opportunities()
                
                if cross_opportunities:
                    self.logger.info(f"💎 Cross-Exchange Opportunities:")
                    for i, opp in enumerate(cross_opportunities[:3]):
                        self.logger.info(f"   {i+1}. {opp}")
                else:
                    self.logger.info(f"❌ No cross-exchange opportunities")
            
            # Test Method 3: Flash Arbitrage (High Volatility)
            self.logger.info(f"\n🎯 METHOD 3: Flash Arbitrage Detection")
            flash_opportunities = await self.enhanced_detector.find_flash_arbitrage_opportunities()
            
            if flash_opportunities:
                self.logger.info(f"🔥 Flash Arbitrage Opportunities:")
                for i, opp in enumerate(flash_opportunities[:3]):
                    self.logger.info(f"   {i+1}. {opp}")
            else:
                self.logger.info(f"❌ No flash arbitrage opportunities (low volatility)")
            
            # Market Analysis
            self.logger.info(f"\n📊 MARKET ANALYSIS FOR {exchange_id.upper()}")
            self.market_analyzer = MarketEfficiencyAnalyzer(self.exchange_manager)
            analyses = await self.market_analyzer.analyze_market_conditions()
            
            for analysis in analyses:
                if analysis.exchange == exchange_id:
                    self.logger.info(f"📈 Market Efficiency Analysis:")
                    self.logger.info(f"   Average Spread: {analysis.average_spread:.4f}%")
                    self.logger.info(f"   Volatility Score: {analysis.volatility_score:.1f}/10")
                    self.logger.info(f"   Arbitrage Potential: {analysis.arbitrage_potential}")
                    self.logger.info(f"   Best Trading Times: {', '.join(analysis.best_trading_times)}")
            
            # Cleanup
            await self.exchange_manager.disconnect_all()
            
        except Exception as e:
            self.logger.error(f"Error testing {exchange_id}: {e}")
    
    async def suggest_profitable_alternatives(self):
        """Suggest alternative profitable strategies"""
        self.logger.info(f"\n💡 ALTERNATIVE PROFITABLE STRATEGIES")
        self.logger.info("=" * 60)
        
        strategies = await self.market_analyzer.suggest_profitable_strategies()
        
        for strategy in strategies['strategies']:
            self.logger.info(f"🎯 {strategy['name']}:")
            self.logger.info(f"   Description: {strategy['description']}")
            self.logger.info(f"   Profit Potential: {strategy['profit_potential']}")
            self.logger.info(f"   Risk Level: {strategy['risk']}")
            self.logger.info(f"   Best For: {strategy['suitable_for']}")
            self.logger.info("")
        
        self.logger.info(f"💭 Current Market Advice:")
        self.logger.info(f"   {strategies['current_market_advice']}")

async def main():
    """Main test function"""
    print("🔍 REAL PROFITABLE OPPORTUNITY TESTER")
    print("=" * 80)
    print("This will test multiple methods to find REAL profitable opportunities:")
    print("1. Enhanced Triangle Detection (optimized calculations)")
    print("2. Cross-Exchange Arbitrage (price differences)")
    print("3. Flash Arbitrage (high volatility periods)")
    print("4. Market Efficiency Analysis")
    print("5. Alternative Profitable Strategies")
    print("=" * 80)
    
    tester = RealOpportunityTester()
    
    try:
        # Test all methods
        success = await tester.test_all_methods()
        
        if success:
            # Suggest alternatives
            await tester.suggest_profitable_alternatives()
            
            print("\n" + "=" * 80)
            print("🎉 TESTING COMPLETED!")
            print("\n🚀 NEXT STEPS:")
            print("1. If profitable opportunities were found, run the GUI with those settings")
            print("2. If no arbitrage opportunities, consider the alternative strategies")
            print("3. Try again during high volatility periods (market crashes, news events)")
            print("4. Consider cross-exchange arbitrage if you have multiple accounts")
            print("5. Use the optimized settings in your main bot")
            print("=" * 80)
        else:
            print("\n❌ Testing failed. Check the logs above for details.")
            
    except KeyboardInterrupt:
        print("\n\nTesting interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())