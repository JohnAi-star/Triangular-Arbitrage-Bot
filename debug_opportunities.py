#!/usr/bin/env python3
"""
Debug script to check opportunity detection and profit calculations from REAL Binance account
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from utils.logger import setup_logger
from utils.websocket_manager import WebSocketManager

load_dotenv()

async def debug_opportunities():
    """Debug opportunity detection from REAL Binance account"""
    logger = setup_logger('DebugOpportunities', 'INFO')
    
    print("🔍 Debugging REAL Binance Opportunity Detection")
    print("=" * 60)
    
    # Check API credentials first
    api_key = os.getenv('BINANCE_API_KEY', '').strip()
    api_secret = os.getenv('BINANCE_API_SECRET', '').strip()
    
    if not api_key or not api_secret:
        print("❌ CRITICAL: No Binance API credentials found!")
        print("   Please set BINANCE_API_KEY and BINANCE_API_SECRET in .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    print(f"✅ API Secret found: {'*' * len(api_secret)}")
    
    try:
        # Initialize WebSocket manager for real-time updates
        websocket_manager = WebSocketManager()
        websocket_manager.run_in_background()
        
        # Initialize exchange manager with REAL Binance connection
        print("\n🚀 Connecting to REAL Binance account...")
        exchange_manager = MultiExchangeManager()
        success = await exchange_manager.initialize_exchanges(['binance'])
        
        if not success:
            print("❌ Failed to connect to Binance")
            print("   Check your API credentials and internet connection")
            return False
        
        print("✅ Connected to REAL Binance account!")
        
        # Get exchange instance and verify connection
        binance_exchange = exchange_manager.get_exchange('binance')
        if not binance_exchange:
            print("❌ Could not get Binance exchange instance")
            return False
        
        # Test real balance detection
        print("\n💰 Testing REAL balance detection...")
        balance = await binance_exchange.get_account_balance()
        if balance:
            total_currencies = len(balance)
            print(f"✅ Balance detected: {total_currencies} currencies with balance")
            
            # Show top balances
            sorted_balance = sorted(balance.items(), key=lambda x: x[1], reverse=True)
            print("📊 Top balances:")
            for currency, amount in sorted_balance[:10]:
                if amount > 0.001:  # Only show significant balances
                    print(f"   {currency}: {amount:.8f}")
        else:
            print("⚠️  No balance detected (account may be empty)")
        
        # Initialize detector with OPTIMIZED settings for finding opportunities
        print("\n🎯 Initializing opportunity detector...")
        detector = MultiExchangeDetector(
            exchange_manager,
            websocket_manager,
            {
                'min_profit_percentage': 0.001,  # Very low threshold to find ANY opportunities
                'max_trade_amount': 100
            }
        )
        
        await detector.initialize()
        
        # Check how many triangles were built
        triangles = detector.triangle_paths.get('binance', [])
        print(f"✅ Built {len(triangles)} triangular paths for Binance")
        
        if triangles:
            print("📋 Sample triangular paths:")
            for i, triangle in enumerate(triangles[:5]):  # Show first 5
                path = " → ".join(triangle[:3])
                print(f"   {i+1}. {path}")
        else:
            print("⚠️  No triangular paths built - this may be the issue!")
        
        # Test ticker data fetching
        print("\n📊 Testing REAL market data fetching...")
        tickers = await binance_exchange.fetch_tickers()
        if tickers:
            print(f"✅ Fetched {len(tickers)} real-time tickers from Binance")
            
            # Show sample ticker data
            sample_pairs = ['BTC/USDT', 'ETH/USDT', 'BTC/ETH', 'BNB/USDT', 'ETH/BNB']
            print("📈 Sample ticker data:")
            for pair in sample_pairs:
                if pair in tickers:
                    ticker = tickers[pair]
                    bid = ticker.get('bid', 0)
                    ask = ticker.get('ask', 0)
                    last = ticker.get('last', 0)
                    print(f"   {pair}: bid={bid:.8f}, ask={ask:.8f}, last={last:.8f}")
                else:
                    print(f"   {pair}: NOT AVAILABLE")
        else:
            print("❌ Failed to fetch ticker data")
            return False
        
        # Now scan for REAL opportunities with multiple thresholds
        print("\n🔍 Scanning for REAL arbitrage opportunities...")
        
        thresholds = [0.001, 0.01, 0.05, 0.1]  # Test multiple profit thresholds
        
        for threshold in thresholds:
            print(f"\n--- Testing with {threshold}% minimum profit threshold ---")
            detector.min_profit_pct = threshold
            
            opportunities = await detector.scan_all_opportunities()
            
            print(f"Found {len(opportunities)} opportunities at {threshold}% threshold")
            
            if opportunities:
                print("💎 REAL Opportunities found:")
                for i, opp in enumerate(opportunities[:10]):  # Show first 10
                    print(f"   {i+1}. {opp.exchange} - {' → '.join(opp.triangle_path[:3])}")
                    print(f"      Profit: {opp.profit_percentage:.6f}%")
                    print(f"      Amount: ${opp.profit_amount:.6f}")
                    print(f"      Volume: ${opp.initial_amount:.2f}")
                    print(f"      Profitable: {opp.is_profitable}")
                    print()
                
                # Found opportunities, no need to test higher thresholds
                break
            else:
                print(f"   No opportunities found at {threshold}% threshold")
        
        # Test scanning for opportunities
        opportunities = await detector.scan_all_opportunities()
        if not opportunities:
            print("\n🔍 DEBUGGING: Manual triangle calculation test...")
            
            # Test manual calculation with real prices
            test_triangles = [
                # Use pairs that actually exist on Binance
                ('BTC', 'USDT', 'USDC'),  # BTC/USDT, USDT/USDC, BTC/USDC
                ('ETH', 'USDT', 'USDC'),  # ETH/USDT, USDT/USDC, ETH/USDC  
                ('BNB', 'USDT', 'USDC'),  # BNB/USDT, USDT/USDC, BNB/USDC
                ('BTC', 'USDT', 'BNB'),   # BTC/USDT, USDT/BNB, BTC/BNB (if exists)
                ('ETH', 'USDT', 'BNB'),   # ETH/USDT, USDT/BNB, ETH/BNB (if exists)
            ]
            
            for base, intermediate, quote in test_triangles:
                # Try different pair combinations since Binance doesn't have all direct pairs
                possible_pairs = [
                    (f"{base}/{intermediate}", f"{intermediate}/{quote}", f"{base}/{quote}"),
                    (f"{base}/{intermediate}", f"{quote}/{intermediate}", f"{base}/{quote}"),
                    (f"{intermediate}/{base}", f"{intermediate}/{quote}", f"{base}/{quote}"),
                    (f"{intermediate}/{base}", f"{quote}/{intermediate}", f"{base}/{quote}"),
                ]
                
                for pair1, pair2, pair3 in possible_pairs:
                    if all(pair in tickers for pair in [pair1, pair2, pair3]):
                        print(f"\n🧮 Manual calculation: {base} → {intermediate} → {quote} → {base}")
                        print(f"   Using pairs: {pair1}, {pair2}, {pair3}")
                        
                        t1, t2, t3 = tickers[pair1], tickers[pair2], tickers[pair3]
                        
                        if all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
                            # Calculate arbitrage manually
                            start_amount = 100  # $100 test
                            
                            # Step 1: Base → Intermediate
                            if pair1.startswith(base):
                                amount1 = start_amount * t1['bid']  # Sell base for intermediate
                                print(f"   Step 1: {start_amount:.2f} {base} → {amount1:.6f} {intermediate} (sell at {t1['bid']:.8f})")
                            else:
                                amount1 = start_amount / t1['ask']  # Buy intermediate with base
                                print(f"   Step 1: {start_amount:.2f} {base} → {amount1:.6f} {intermediate} (buy at {t1['ask']:.8f})")
                            
                            # Step 2: Intermediate → Quote
                            if pair2.startswith(intermediate):
                                amount2 = amount1 * t2['bid']  # Sell intermediate for quote
                                print(f"   Step 2: {amount1:.6f} {intermediate} → {amount2:.6f} {quote} (sell at {t2['bid']:.8f})")
                            else:
                                amount2 = amount1 / t2['ask']  # Buy quote with intermediate
                                print(f"   Step 2: {amount1:.6f} {intermediate} → {amount2:.6f} {quote} (buy at {t2['ask']:.8f})")
                            
                            # Step 3: Quote → Base
                            if pair3.startswith(quote):
                                final_amount = amount2 * t3['bid']  # Sell quote for base
                                print(f"   Step 3: {amount2:.6f} {quote} → {final_amount:.6f} {base} (sell at {t3['bid']:.8f})")
                            else:
                                final_amount = amount2 / t3['ask']  # Buy base with quote
                                print(f"   Step 3: {amount2:.6f} {quote} → {final_amount:.6f} {base} (buy at {t3['ask']:.8f})")
                            
                            # Calculate profit
                            profit = final_amount - start_amount
                            profit_pct = (profit / start_amount) * 100
                            
                            # Apply realistic costs
                            total_costs = 0.4  # 0.4% total costs (fees + slippage + buffer)
                            net_profit_pct = profit_pct - total_costs
                            
                            print(f"   Result: {start_amount:.6f} → {final_amount:.6f} = {profit_pct:.6f}% gross")
                            print(f"   Net Profit: {net_profit_pct:.6f}% (after {total_costs}% costs)")
                            
                            if net_profit_pct > 0.1:
                                print(f"   ✅ PROFITABLE OPPORTUNITY FOUND!")
                            else:
                                print(f"   ❌ Not profitable (below 0.1%)")
                            break
                        else:
                            print(f"   ⚠️  Missing price data for {base}-{intermediate}-{quote}")
                else:
                    print(f"   ⚠️  No valid pair combinations found for {base}-{intermediate}-{quote}")
        
        # Cleanup
        await exchange_manager.disconnect_all()
        websocket_manager.stop()
        
        print("\n" + "=" * 60)
        print("✅ Debug completed!")
        print("\nIf no opportunities were found, this could mean:")
        print("1. Current market conditions don't have arbitrage opportunities")
        print("2. Binance has very efficient pricing (minimal arbitrage)")
        print("3. Try lowering the minimum profit threshold further")
        print("4. Market volatility may be too low at this time")
        print("5. Consider checking during high-volume trading periods")
        
        return True
        
    except Exception as e:
        logger.error(f"Debug failed: {e}", exc_info=True)
        print(f"\n❌ Debug failed with error: {e}")
        return False

if __name__ == "__main__":
    print("🔺 REAL Binance Opportunity Debug Tool")
    print("=" * 60)
    
    try:
        success = asyncio.run(debug_opportunities())
        if success:
            print("\n🎉 Debug completed successfully!")
        else:
            print("\n❌ Debug failed. Check the output above for details.")
    except KeyboardInterrupt:
        print("\n\nDebug interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")