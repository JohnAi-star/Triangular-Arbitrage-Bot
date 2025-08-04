#!/usr/bin/env python3
"""
Test the working triangular arbitrage bot
"""

from simple_arbitrage_bot import SimpleTriangularArbitrage
import time

def test_bot():
    print("🧪 Testing Simple Triangular Arbitrage Bot")
    print("=" * 50)
    
    bot = SimpleTriangularArbitrage()
    
    # Test price fetching
    print("📊 Testing price fetching...")
    prices = bot.get_binance_prices()
    
    if prices:
        print(f"✅ Successfully fetched {len(prices)} prices")
        
        # Show some sample prices
        sample_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'BTCETH', 'ETHBNB']
        print("\n📈 Sample prices:")
        for pair in sample_pairs:
            if pair in prices:
                print(f"   {pair}: ${prices[pair]:,.2f}")
        
        # Test opportunity detection
        print("\n🔍 Testing opportunity detection...")
        opportunities = bot.find_triangular_opportunities(prices)
        
        if opportunities:
            print(f"🎯 Found {len(opportunities)} opportunities!")
            for opp in opportunities:
                print(f"   💰 {opp['path']}: {opp['profit_pct']:.4f}% (${opp['profit_usd']:.2f})")
        else:
            print("❌ No opportunities found in this test")
            print("   This is normal - opportunities are rare and brief")
        
        print(f"\n📊 Total opportunities found: {bot.opportunities_found}")
        
    else:
        print("❌ Failed to fetch prices")
        return False
    
    return True

if __name__ == "__main__":
    success = test_bot()
    
    if success:
        print("\n✅ Bot test completed successfully!")
        print("\nTo run continuous scanning:")
        print("python simple_arbitrage_bot.py")
    else:
        print("\n❌ Bot test failed")