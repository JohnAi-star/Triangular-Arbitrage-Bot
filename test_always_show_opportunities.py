#!/usr/bin/env python3
"""
Test script to verify opportunities always show in UI, even with zero balance
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from utils.logger import setup_logger
from utils.websocket_manager import WebSocketManager

load_dotenv()

async def test_always_show_opportunities():
    """Test that opportunities always show in UI regardless of balance"""
    logger = setup_logger('TestAlwaysShow', 'INFO')
    
    print("🔍 Testing ALWAYS SHOW Opportunities (Even with Zero Balance)")
    print("=" * 70)
    
    try:
        # Initialize WebSocket manager
        websocket_manager = WebSocketManager()
        websocket_manager.run_in_background()
        
        # Initialize exchange manager
        print("🚀 Connecting to exchanges...")
        exchange_manager = MultiExchangeManager()
        success = await exchange_manager.initialize_exchanges(['binance'])
        
        if not success:
            print("❌ Failed to connect to exchanges")
            return False
        
        print("✅ Connected to exchanges!")
        
        # Initialize detector with very low threshold
        print("🎯 Initializing detector with ALWAYS SHOW settings...")
        detector = MultiExchangeDetector(
            exchange_manager,
            websocket_manager,
            {
                'min_profit_percentage': 0.001,  # Very low threshold
                'max_trade_amount': 100.0,
                'always_show_opportunities': True,
                'force_ui_display': True
            }
        )
        
        await detector.initialize()
        
        # Test multiple scans to ensure opportunities always appear
        for scan_num in range(3):
            print(f"\n--- SCAN #{scan_num + 1} ---")
            opportunities = await detector.scan_all_opportunities()
            
            print(f"📊 Scan {scan_num + 1} Results:")
            print(f"   Total opportunities: {len(opportunities)}")
            
            if opportunities:
                print("💎 Opportunities found:")
                for i, opp in enumerate(opportunities[:5]):
                    exchange = opp.exchange
                    path = ' → '.join(opp.triangle_path[:3])
                    profit = opp.profit_percentage
                    tradeable = "✅ TRADEABLE" if opp.is_tradeable else "❌ Need balance"
                    demo_status = "📊 DEMO" if getattr(opp, 'is_demo', False) else "🔴 REAL"
                    
                    print(f"   {i+1}. {exchange}: {path} = {profit:.4f}% | {tradeable} | {demo_status}")
            else:
                print("❌ No opportunities found - this should NOT happen!")
            
            await asyncio.sleep(2)  # Wait between scans
        
        # Cleanup
        await exchange_manager.disconnect_all()
        websocket_manager.stop()
        
        print("\n" + "=" * 70)
        print("✅ Test completed!")
        
        if opportunities:
            print("🎉 SUCCESS: Opportunities are always showing in UI!")
            print("   - Real opportunities based on your balance")
            print("   - Demo opportunities for testing")
            print("   - UI will always have content to display")
        else:
            print("❌ ISSUE: No opportunities generated")
            print("   - Check the detector configuration")
            print("   - Verify sample opportunity generation")
        
        return len(opportunities) > 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("🔺 Always Show Opportunities Test")
    print("=" * 70)
    
    try:
        success = asyncio.run(test_always_show_opportunities())
        if success:
            print("\n🎉 Test PASSED - Opportunities will always show!")
        else:
            print("\n❌ Test FAILED - Check the issues above")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")