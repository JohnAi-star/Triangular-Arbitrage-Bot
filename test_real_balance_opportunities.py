#!/usr/bin/env python3
"""
Test script to verify real balance-based opportunity detection
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from utils.logger import setup_logger
from utils.websocket_manager import WebSocketManager

load_dotenv()

async def test_real_balance_opportunities():
    """Test real balance-based opportunity detection"""
    logger = setup_logger('TestRealBalance', 'INFO')
    
    print("🔍 Testing REAL Balance-Based Opportunity Detection")
    print("=" * 60)
    
    # Check API credentials
    api_key = os.getenv('BINANCE_API_KEY', '').strip()
    api_secret = os.getenv('BINANCE_API_SECRET', '').strip()
    
    if not api_key or not api_secret:
        print("❌ CRITICAL: No Binance API credentials found!")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    
    try:
        # Initialize WebSocket manager
        websocket_manager = WebSocketManager()
        websocket_manager.run_in_background()
        
        # Initialize exchange manager
        print("\n🚀 Connecting to Binance...")
        exchange_manager = MultiExchangeManager()
        success = await exchange_manager.initialize_exchanges(['binance'])
        
        if not success:
            print("❌ Failed to connect to Binance")
            return False
        
        print("✅ Connected to Binance!")
        
        # Get real balance
        binance_exchange = exchange_manager.get_exchange('binance')
        if not binance_exchange:
            print("❌ Could not get Binance exchange instance")
            return False
        
        print("\n💰 Fetching REAL account balance...")
        balance = await binance_exchange.get_account_balance()
        
        if not balance:
            print("❌ No balance detected")
            return False
        
        print("✅ REAL BALANCE DETECTED:")
        total_usd = 0
        for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True):
            print(f"   {currency}: {amount:.8f}")
            # Rough USD calculation
            if currency in ['USDT', 'USDC', 'BUSD']:
                total_usd += amount
            elif currency == 'BTC':
                total_usd += amount * 95000
            elif currency == 'ETH':
                total_usd += amount * 3200
            elif currency == 'BNB':
                total_usd += amount * 650
        
        print(f"💵 Estimated Total: ~${total_usd:.2f} USD")
        
        if total_usd < 1:
            print("⚠️ Very low balance - may not find tradeable opportunities")
        
        # Initialize detector
        print("\n🎯 Initializing opportunity detector...")
        detector = MultiExchangeDetector(
            exchange_manager,
            websocket_manager,
            {
                'min_profit_percentage': 0.5,  # 0.5% minimum
                'max_trade_amount': 100.0
            }
        )
        
        await detector.initialize()
        
        # Scan for REAL opportunities
        print("\n🔍 Scanning for REAL opportunities based on your balance...")
        opportunities = await detector.scan_all_opportunities()
        
        if opportunities:
            print(f"💎 Found {len(opportunities)} REAL TRADEABLE opportunities!")
            print("\n📊 OPPORTUNITIES YOU CAN ACTUALLY TRADE:")
            
            for i, opp in enumerate(opportunities[:10], 1):
                print(f"\n{i}. {opp.exchange.upper()}")
                print(f"   Path: {' → '.join(opp.triangle_path[:3])}")
                print(f"   Profit: {opp.profit_percentage:.4f}% (${opp.profit_amount:.4f})")
                print(f"   Trade Amount: ${opp.initial_amount:.2f}")
                print(f"   ✅ TRADEABLE: You have the required balance!")
                
                if hasattr(opp, 'is_profitable') and opp.is_profitable:
                    print(f"   🎯 STATUS: Ready to execute")
                else:
                    print(f"   ⚠️ STATUS: Below profit threshold")
        else:
            print("❌ No tradeable opportunities found")
            print("\nPossible reasons:")
            print("1. Current market conditions don't have arbitrage")
            print("2. Your balance is too low for minimum trade amounts")
            print("3. Market spreads are too tight")
            print("4. Try again during higher volatility periods")
        
        # Cleanup
        await exchange_manager.disconnect_all()
        websocket_manager.stop()
        
        return len(opportunities) > 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("🔺 REAL Balance-Based Opportunity Test")
    print("=" * 60)
    
    try:
        success = asyncio.run(test_real_balance_opportunities())
        if success:
            print("\n🎉 Test completed - Found tradeable opportunities!")
        else:
            print("\n❌ Test completed - No opportunities found")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")