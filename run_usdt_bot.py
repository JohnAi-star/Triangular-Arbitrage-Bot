#!/usr/bin/env python3
"""
Quick launcher for USDT Arbitrage Bot
"""

import asyncio
import sys
import os
from usdt_arbitrage_bot import RealUSDTArbitrageBot

async def main():
    print("🚀 USDT Triangular Arbitrage Bot Launcher")
    print("=" * 50)
    
    # Check for API credentials
    api_key = os.getenv('BINANCE_API_KEY', '').strip()
    api_secret = os.getenv('BINANCE_API_SECRET', '').strip()
    
    if not api_key or not api_secret:
        print("❌ ERROR: Missing Binance API credentials!")
        print("Please set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file")
        return
    
    print(f"✅ API credentials found")
    print(f"🎯 Target: USDT → Currency1 → Currency2 → USDT")
    print(f"💰 Will execute REAL trades on Binance")
    print()
    
    # Create bot with conservative settings
    bot = RealUSDTArbitrageBot(
        min_profit_pct=0.5,  # 0.5% minimum profit (realistic)
        max_trade_amount=100.0  # $100 USDT per trade (safe amount)
    )
    
    print("Trading Mode Options:")
    print("1. AUTO TRADING - Bot executes trades automatically")
    print("2. MANUAL MODE - Show opportunities only")
    print("3. QUICK TEST - Find 1 opportunity and execute")
    print()
    
    try:
        choice = input("Choose mode (1/2/3): ").strip()
        
        if choice == "1":
            print("⚠️ WARNING: AUTO TRADING will execute REAL trades!")
            print("⚠️ You will spend REAL money and make/lose REAL money!")
            confirm = input("Type 'START' to begin AUTO TRADING: ").strip()
            
            if confirm == "START":
                print("🚀 Starting AUTO TRADING...")
                await bot.start(auto_trading=True)
            else:
                print("❌ AUTO TRADING cancelled")
        
        elif choice == "2":
            print("👁️ Starting MANUAL MODE...")
            await bot.start(auto_trading=False)
        
        elif choice == "3":
            print("🧪 Starting QUICK TEST...")
            if await bot.initialize():
                opportunities = await bot.get_usdt_triangular_opportunities()
                if opportunities:
                    print(f"💎 Found {len(opportunities)} opportunities")
                    print(f"🎯 Best opportunity: {opportunities[0]}")
                    
                    execute = input("Execute this trade? (y/n): ").strip().lower()
                    if execute == 'y':
                        success = await bot.execute_usdt_triangle(opportunities[0])
                        if success:
                            print("✅ Test trade completed!")
                        else:
                            print("❌ Test trade failed")
                    else:
                        print("Test cancelled")
                else:
                    print("❌ No opportunities found")
                await bot.stop()
        
        else:
            print("❌ Invalid choice")
    
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())