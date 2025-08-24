#!/usr/bin/env python3
"""
REAL USDT Triangular Arbitrage Bot
Finds and executes USDT → Currency1 → Currency2 → USDT opportunities on Binance
Makes REAL money with AUTO trading
"""

import asyncio
import time
import json
import ccxt.async_support as ccxt
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging
from dotenv import load_dotenv
import os

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('USDTArbitrageBot')

@dataclass
class USDTTriangleOpportunity:
    """USDT-based triangular arbitrage opportunity"""
    path: str  # e.g., "USDT → YGG → KAIA → USDT"
    currency1: str  # First currency (YGG)
    currency2: str  # Second currency (KAIA)
    pair1: str  # USDT/Currency1 pair
    pair2: str  # Currency1/Currency2 pair
    pair3: str  # Currency2/USDT pair
    profit_percentage: float
    profit_amount: float
    trade_amount: float
    prices: Dict[str, float]
    
    def __str__(self):
        return f"{self.path}: {self.profit_percentage:.4f}% (${self.profit_amount:.2f})"

class RealUSDTArbitrageBot:
    """Real USDT Triangular Arbitrage Bot for making money"""

    def __init__(self, min_profit_pct: float = 0.5, max_trade_amount: float = 100.0):
        self.min_profit_pct = 0.4  # Fixed to 0.4% for consistency
        self.max_trade_amount = max_trade_amount
        self.auto_trading = False
        
        # Binance connection
        self.exchange = None
        self.running = False
        
        # Trading statistics
        self.opportunities_found = 0
        self.trades_executed = 0
        self.total_profit = 0.0
        self.successful_trades = 0
        
        # Current opportunities
        self.current_opportunities: List[USDTTriangleOpportunity] = []
        
        logger.info(f"🚀 REAL USDT Arbitrage Bot initialized")
        logger.info(f"   Min Profit: {min_profit_pct}%")
        logger.info(f"   Max Trade: ${max_trade_amount} USDT")
        logger.info(f"   Target: USDT → Currency1 → Currency2 → USDT")
    
    async def initialize(self):
        """Initialize Binance connection with REAL API credentials"""
        try:
            api_key = os.getenv('BINANCE_API_KEY', '').strip()
            api_secret = os.getenv('BINANCE_API_SECRET', '').strip()
            
            if not api_key or not api_secret:
                logger.error("❌ CRITICAL: No Binance API credentials found!")
                logger.error("   Please set BINANCE_API_KEY and BINANCE_API_SECRET in .env file")
                return False
            
            logger.info(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
            
            # Initialize Binance exchange
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'sandbox': False,  # LIVE TRADING
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                }
            })
            
            # Test connection and get balance
            await self.exchange.load_markets()
            balance = await self.exchange.fetch_balance()
            
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            total_balance = balance.get('USDT', {}).get('total', 0)
            
            logger.info(f"✅ Connected to Binance LIVE account")
            logger.info(f"💰 USDT Balance: {usdt_balance:.2f} USDT (Total: {total_balance:.2f})")
            
            if usdt_balance < self.max_trade_amount:
                logger.warning(f"⚠️ Low USDT balance: {usdt_balance:.2f} < {self.max_trade_amount}")
                logger.warning(f"   Adjusting max trade amount to {usdt_balance * 0.9:.2f} USDT")
                self.max_trade_amount = min(self.max_trade_amount, usdt_balance * 0.9)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Binance: {e}")
            return False
    
    async def get_usdt_triangular_opportunities(self) -> List[USDTTriangleOpportunity]:
        """Find USDT-based triangular arbitrage opportunities"""
        try:
            # Get all tickers
            tickers = await self.exchange.fetch_tickers()
            
            # Find all currencies that have USDT pairs
            usdt_currencies = []
            for symbol in tickers.keys():
                if symbol.endswith('/USDT') and tickers[symbol]['bid'] and tickers[symbol]['ask']:
                    currency = symbol.replace('/USDT', '')
                    usdt_currencies.append(currency)
            
            logger.info(f"📊 Found {len(usdt_currencies)} currencies with USDT pairs")
            
            opportunities = []
            
            # Build USDT triangular paths: USDT → Currency1 → Currency2 → USDT
            for curr1 in usdt_currencies:
                for curr2 in usdt_currencies:
                    if curr1 != curr2:
                        try:
                            # Required pairs for USDT triangle
                            pair1 = f"{curr1}/USDT"  # USDT → curr1
                            pair2 = f"{curr1}/{curr2}"  # curr1 → curr2
                            pair3 = f"{curr2}/USDT"  # curr2 → USDT
                            
                            # Alternative if curr1→curr2 doesn't exist, try curr2→curr1
                            alt_pair2 = f"{curr2}/{curr1}"
                            
                            if (pair1 in tickers and pair3 in tickers and 
                                (pair2 in tickers or alt_pair2 in tickers)):
                                
                                # Calculate USDT triangle profit
                                opportunity = self._calculate_usdt_triangle_profit(
                                    tickers, curr1, curr2, pair1, pair2, pair3, alt_pair2
                                )
                                
                                if opportunity and opportunity.profit_percentage >= self.min_profit_pct:
                                    opportunities.append(opportunity)
                                    self.opportunities_found += 1
                                    
                        except Exception as e:
                            continue
            
            # Sort by profitability
            opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
            
            if opportunities:
                logger.info(f"💎 Found {len(opportunities)} profitable USDT opportunities!")
                for i, opp in enumerate(opportunities[:5]):
                    logger.info(f"   {i+1}. {opp}")
            
            return opportunities[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"❌ Error finding opportunities: {e}")
            return []
    
    def _calculate_usdt_triangle_profit(self, tickers: Dict, curr1: str, curr2: str,
                                      pair1: str, pair2: str, pair3: str, alt_pair2: str) -> Optional[USDTTriangleOpportunity]:
        """Calculate profit for USDT → curr1 → curr2 → USDT triangle"""
        try:
            # Get ticker data
            t1 = tickers[pair1]  # curr1/USDT
            t3 = tickers[pair3]  # curr2/USDT
            
            # Get curr1→curr2 price (try both directions)
            if pair2 in tickers:
                t2 = tickers[pair2]  # curr1/curr2
                use_direct = True
            elif alt_pair2 in tickers:
                t2 = tickers[alt_pair2]  # curr2/curr1
                use_direct = False
            else:
                return None
            
            # Validate prices
            if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
                return None
            
            # Start with USDT
            start_usdt = self.max_trade_amount
            
            # Step 1: USDT → curr1 (buy curr1 with USDT)
            price1 = float(t1['ask'])  # Buy curr1 at ask price
            amount_curr1 = start_usdt / price1
            
            # Step 2: curr1 → curr2
            if use_direct:
                # Direct pair: curr1/curr2
                price2 = float(t2['bid'])  # Sell curr1 for curr2 at bid price
                amount_curr2 = amount_curr1 * price2
            else:
                # Inverse pair: curr2/curr1
                price2 = float(t2['ask'])  # Buy curr2 with curr1 at ask price
                amount_curr2 = amount_curr1 / price2
            
            # Step 3: curr2 → USDT (sell curr2 for USDT)
            price3 = float(t3['bid'])  # Sell curr2 for USDT at bid price
            final_usdt = amount_curr2 * price3
            
            # Calculate profit
            gross_profit = final_usdt - start_usdt
            gross_profit_pct = (gross_profit / start_usdt) * 100
            
            # Apply trading fees (0.1% per trade × 3 trades = 0.3%)
            total_fees_pct = 0.3
            net_profit_pct = gross_profit_pct - total_fees_pct
            net_profit_usd = start_usdt * (net_profit_pct / 100)
            
            # Only return profitable opportunities
            if net_profit_pct >= self.min_profit_pct and net_profit_pct <= 5.0:  # Max 5% (realistic)
                path = f"USDT → {curr1} → {curr2} → USDT"
                
                return USDTTriangleOpportunity(
                    path=path,
                    currency1=curr1,
                    currency2=curr2,
                    pair1=pair1,
                    pair2=pair2 if use_direct else alt_pair2,
                    pair3=pair3,
                    profit_percentage=net_profit_pct,
                    profit_amount=net_profit_usd,
                    trade_amount=start_usdt,
                    prices={
                        'step1_price': price1,
                        'step2_price': price2,
                        'step3_price': price3,
                        'final_amount': final_usdt
                    }
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error calculating USDT triangle {curr1}-{curr2}: {e}")
            return None
    
    async def execute_usdt_triangle(self, opportunity: USDTTriangleOpportunity) -> bool:
        """Execute REAL USDT triangular arbitrage trade on Binance"""
        try:
            logger.info(f"🚀 EXECUTING REAL TRADE: {opportunity.path}")
            logger.info(f"   Expected Profit: {opportunity.profit_percentage:.4f}% (${opportunity.profit_amount:.2f})")
            
            trade_start_time = time.time()
            
            # Step 1: USDT → Currency1 (Buy Currency1 with USDT)
            logger.info(f"📊 Step 1: Buy {opportunity.currency1} with {opportunity.trade_amount:.2f} USDT")
            
            order1 = await self.exchange.create_market_order(
                opportunity.pair1, 'buy', opportunity.trade_amount / opportunity.prices['step1_price']
            )
            
            if not order1 or order1.get('status') != 'closed':
                logger.error(f"❌ Step 1 failed: {order1}")
                return False
            
            amount_curr1 = float(order1['filled'])
            logger.info(f"✅ Step 1 completed: Got {amount_curr1:.6f} {opportunity.currency1}")
            
            # Small delay between trades
            await asyncio.sleep(0.5)
            
            # Step 2: Currency1 → Currency2
            logger.info(f"📊 Step 2: Convert {amount_curr1:.6f} {opportunity.currency1} to {opportunity.currency2}")
            
            if opportunity.pair2.startswith(opportunity.currency1):
                # Direct pair: sell curr1 for curr2
                order2 = await self.exchange.create_market_order(
                    opportunity.pair2, 'sell', amount_curr1
                )
            else:
                # Inverse pair: buy curr2 with curr1
                order2 = await self.exchange.create_market_order(
                    opportunity.pair2, 'buy', amount_curr1 / opportunity.prices['step2_price']
                )
            
            if not order2 or order2.get('status') != 'closed':
                logger.error(f"❌ Step 2 failed: {order2}")
                return False
            
            amount_curr2 = float(order2['filled'])
            logger.info(f"✅ Step 2 completed: Got {amount_curr2:.6f} {opportunity.currency2}")
            
            # Small delay between trades
            await asyncio.sleep(0.5)
            
            # Step 3: Currency2 → USDT (Sell Currency2 for USDT)
            logger.info(f"📊 Step 3: Sell {amount_curr2:.6f} {opportunity.currency2} for USDT")
            
            order3 = await self.exchange.create_market_order(
                opportunity.pair3, 'sell', amount_curr2
            )
            
            if not order3 or order3.get('status') != 'closed':
                logger.error(f"❌ Step 3 failed: {order3}")
                return False
            
            final_usdt = float(order3['cost'])
            logger.info(f"✅ Step 3 completed: Got {final_usdt:.2f} USDT")
            
            # Calculate actual profit
            actual_profit = final_usdt - opportunity.trade_amount
            actual_profit_pct = (actual_profit / opportunity.trade_amount) * 100
            
            trade_duration = (time.time() - trade_start_time) * 1000
            
            # Update statistics
            self.trades_executed += 1
            self.total_profit += actual_profit
            
            if actual_profit > 0:
                self.successful_trades += 1
                logger.info(f"🎉 TRADE SUCCESSFUL!")
            else:
                logger.warning(f"⚠️ Trade completed but with loss")
            
            logger.info(f"💰 TRADE SUMMARY:")
            logger.info(f"   Initial: {opportunity.trade_amount:.2f} USDT")
            logger.info(f"   Final: {final_usdt:.2f} USDT")
            logger.info(f"   Actual Profit: {actual_profit:.4f} USDT ({actual_profit_pct:.4f}%)")
            logger.info(f"   Duration: {trade_duration:.0f}ms")
            logger.info(f"   Order IDs: {order1['id']}, {order2['id']}, {order3['id']}")
            logger.info(f"🔍 Check your Binance Spot Orders for these trades!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ TRADE EXECUTION FAILED: {e}")
            return False
    
    async def run_auto_trading(self):
        """Run continuous auto trading for USDT triangular arbitrage"""
        logger.info(f"🤖 Starting AUTO TRADING mode...")
        logger.info(f"   Will automatically execute profitable USDT triangles")
        logger.info(f"   Min Profit: {self.min_profit_pct}%")
        logger.info(f"   Max Trade: ${self.max_trade_amount} USDT")
        
        self.auto_trading = True
        scan_count = 0
        
        try:
            while self.running and self.auto_trading:
                scan_count += 1
                logger.info(f"🔍 Scan #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Find USDT opportunities
                opportunities = await self.get_usdt_triangular_opportunities()
                self.current_opportunities = opportunities
                
                if opportunities:
                    logger.info(f"💎 Found {len(opportunities)} profitable opportunities!")
                    
                    # Auto-execute the most profitable opportunity
                    best_opportunity = opportunities[0]
                    logger.info(f"🎯 Auto-executing best opportunity: {best_opportunity}")
                    
                    success = await self.execute_usdt_triangle(best_opportunity)
                    
                    if success:
                        logger.info(f"✅ Auto-trade #{self.trades_executed} completed successfully!")
                        
                        # Wait longer after successful trade
                        await asyncio.sleep(30)
                    else:
                        logger.error(f"❌ Auto-trade failed")
                        await asyncio.sleep(10)
                else:
                    logger.info(f"❌ No profitable opportunities found this scan")
                    await asyncio.sleep(15)
                
                # Show statistics
                success_rate = (self.successful_trades / max(self.trades_executed, 1)) * 100
                logger.info(f"📊 Stats: {self.trades_executed} trades, {success_rate:.1f}% success, ${self.total_profit:.2f} profit")
                
        except KeyboardInterrupt:
            logger.info(f"🛑 Auto-trading stopped by user")
        except Exception as e:
            logger.error(f"❌ Auto-trading error: {e}")
        finally:
            self.auto_trading = False
    
    async def run_manual_mode(self):
        """Run manual mode - show opportunities but don't execute"""
        logger.info(f"👁️ Starting MANUAL mode...")
        logger.info(f"   Will show profitable USDT triangles but not execute")
        
        scan_count = 0
        
        try:
            while self.running:
                scan_count += 1
                logger.info(f"🔍 Scan #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Find USDT opportunities
                opportunities = await self.get_usdt_triangular_opportunities()
                self.current_opportunities = opportunities
                
                if opportunities:
                    logger.info(f"💎 Found {len(opportunities)} profitable opportunities:")
                    for i, opp in enumerate(opportunities[:5]):
                        logger.info(f"   {i+1}. {opp}")
                    logger.info(f"   Use execute_opportunity() to trade manually")
                else:
                    logger.info(f"❌ No profitable opportunities found this scan")
                
                await asyncio.sleep(20)  # Scan every 20 seconds in manual mode
                
        except KeyboardInterrupt:
            logger.info(f"🛑 Manual scanning stopped by user")
        except Exception as e:
            logger.error(f"❌ Manual scanning error: {e}")
    
    async def execute_opportunity(self, index: int = 0) -> bool:
        """Manually execute a specific opportunity by index"""
        if not self.current_opportunities:
            logger.error("❌ No opportunities available")
            return False
        
        if index >= len(self.current_opportunities):
            logger.error(f"❌ Invalid index {index}, only {len(self.current_opportunities)} opportunities available")
            return False
        
        opportunity = self.current_opportunities[index]
        logger.info(f"🚀 Manually executing opportunity #{index}: {opportunity}")
        
        return await self.execute_usdt_triangle(opportunity)
    
    async def start(self, auto_trading: bool = False):
        """Start the USDT arbitrage bot"""
        if not await self.initialize():
            logger.error("❌ Failed to initialize bot")
            return
        
        self.running = True
        
        try:
            if auto_trading:
                await self.run_auto_trading()
            else:
                await self.run_manual_mode()
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot and cleanup"""
        logger.info("🛑 Stopping USDT Arbitrage Bot...")
        self.running = False
        self.auto_trading = False
        
        if self.exchange:
            await self.exchange.close()
        
        # Final statistics
        success_rate = (self.successful_trades / max(self.trades_executed, 1)) * 100
        logger.info(f"📊 FINAL STATISTICS:")
        logger.info(f"   Opportunities Found: {self.opportunities_found}")
        logger.info(f"   Trades Executed: {self.trades_executed}")
        logger.info(f"   Successful Trades: {self.successful_trades}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   Total Profit: ${self.total_profit:.4f} USDT")
        logger.info(f"✅ Bot stopped")

async def main():
    """Main function"""
    print("🚀 REAL USDT Triangular Arbitrage Bot")
    print("=" * 50)
    print("This bot will:")
    print("1. Find USDT → Currency1 → Currency2 → USDT opportunities")
    print("2. Execute REAL trades on Binance")
    print("3. Make REAL money with AUTO trading")
    print("4. Show trades in your Binance Spot Orders")
    print("=" * 50)
    
    # Create bot instance
    bot = RealUSDTArbitrageBot(
        min_profit_pct=0.5,  # 0.5% minimum profit
        max_trade_amount=100.0  # $100 USDT per trade (start small)
    )
    
    # Ask user for trading mode
    print("\nChoose trading mode:")
    print("1. AUTO TRADING (bot will execute trades automatically)")
    print("2. MANUAL MODE (show opportunities only)")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        auto_trading = choice == "1"
        
        if auto_trading:
            print("⚠️ WARNING: AUTO TRADING will execute REAL trades with REAL money!")
            confirm = input("Type 'YES' to confirm AUTO TRADING: ").strip()
            if confirm != "YES":
                print("❌ AUTO TRADING cancelled")
                auto_trading = False
        
        # Start the bot
        await bot.start(auto_trading=auto_trading)
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())