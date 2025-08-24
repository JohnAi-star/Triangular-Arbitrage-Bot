#!/usr/bin/env python3
"""
Test KuCoin Opportunity Detection
Verify that KuCoin shows profitable opportunities with optimized settings
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from utils.logger import setup_logger
from utils.websocket_manager import WebSocketManager

load_dotenv()

async def test_kucoin_opportunities():
    """Test KuCoin opportunity detection with optimized settings"""
    logger = setup_logger('KuCoinTest', 'INFO')
    
    print("🔍 Testing KuCoin Profitable Opportunity Detection")
    print("=" * 60)
    
    # Check KuCoin credentials
    api_key = os.getenv('KUCOIN_API_KEY', '').strip()
    api_secret = os.getenv('KUCOIN_API_SECRET', '').strip()
    passphrase = os.getenv('KUCOIN_PASSPHRASE', '').strip()
    
    if not all([api_key, api_secret, passphrase]):
        print("❌ Missing KuCoin credentials")
        print("   Set KUCOIN_API_KEY, KUCOIN_API_SECRET, and KUCOIN_PASSPHRASE in .env file")
        return False
    
    print(f"✅ KuCoin credentials found")
    
    try:
        # Initialize WebSocket manager
        websocket_manager = WebSocketManager()
        websocket_manager.run_in_background()
        
        # Initialize exchange manager with KuCoin only
        exchange_manager = MultiExchangeManager()
        success = await exchange_manager.initialize_exchanges(['kucoin'])
        
        if not success:
            print("❌ Failed to connect to KuCoin")
            return False
        
        print("✅ Connected to KuCoin successfully!")
        
        # Get KuCoin exchange instance
        kucoin_exchange = exchange_manager.get_exchange('kucoin')
        
        # Check balance and KCS status
        balance = await kucoin_exchange.get_account_balance()
        usdt_balance = balance.get('USDT', 0.0)
        kcs_balance = balance.get('KCS', 0.0)
        
        print(f"\n💰 KuCoin Account Balance:")
        print(f"   USDT: {usdt_balance:.2f}")
        print(f"   KCS: {kcs_balance:.6f}")
        
        if kcs_balance > 0.01:
            print(f"✅ KCS detected - will use 0.05% fees (50% discount)")
            total_costs = 0.155  # 0.15% fees + 0.005% slippage
        else:
            print(f"📊 No KCS - will use 0.1% standard fees")
            total_costs = 0.305  # 0.3% fees + 0.005% slippage
        
        print(f"💰 Total Trading Costs: {total_costs:.3f}%")
        print(f"🎯 Minimum Gross Profit Needed: {total_costs + 0.3:.3f}% (for 0.3% net profit)")
        
        # Initialize detector with optimized settings
        detector = MultiExchangeDetector(
            exchange_manager,
            websocket_manager,
            {
                'min_profit_percentage': 0.3,  # Lowered threshold
                'max_trade_amount': 20.0
            }
        )
        
        await detector.initialize()
        
        # Scan for opportunities
        print(f"\n🔍 Scanning KuCoin for profitable opportunities...")
        opportunities = await detector.scan_all_opportunities()
        
        if opportunities:
            profitable_opportunities = [opp for opp in opportunities if opp.is_profitable]
            visible_opportunities = [opp for opp in opportunities if opp.profit_percentage >= 0.1]
            
            print(f"📊 KuCoin Results:")
            print(f"   Total opportunities: {len(opportunities)}")
            print(f"   Profitable (≥0.3%): {len(profitable_opportunities)}")
            print(f"   Visible (≥0.1%): {len(visible_opportunities)}")
            
            if profitable_opportunities:
                print(f"\n💎 PROFITABLE KuCoin Opportunities (≥0.3%):")
                for i, opp in enumerate(profitable_opportunities[:10]):
                    tradeable = "✅ TRADEABLE" if opp.is_tradeable else f"❌ Need ${opp.required_balance:.2f} USDT"
                    print(f"   {i+1}. {' → '.join(opp.triangle_path)} = {opp.profit_percentage:.4f}% (${opp.profit_amount:.4f}) | {tradeable}")
            
            if visible_opportunities and not profitable_opportunities:
                print(f"\n📊 VISIBLE KuCoin Opportunities (0.1-0.3%):")
                for i, opp in enumerate(visible_opportunities[:10]):
                    print(f"   {i+1}. {' → '.join(opp.triangle_path)} = {opp.profit_percentage:.4f}% (${opp.profit_amount:.4f})")
                print(f"\n💡 These opportunities are close to profitable!")
                print(f"   With better market conditions or lower fees, they could become profitable")
        else:
            print(f"❌ No opportunities found on KuCoin")
            print(f"\n🔧 Troubleshooting suggestions:")
            print(f"   1. Market volatility may be low right now")
            print(f"   2. Try again during high-volume trading periods")
            print(f"   3. Consider lowering the minimum profit threshold temporarily")
            print(f"   4. Ensure KCS balance for fee discounts")
        
        # Cleanup
        await exchange_manager.disconnect_all()
        websocket_manager.stop()
        
        return len(opportunities) > 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    print("🔺 KuCoin Opportunity Detection Test")
    print("=" * 60)
    
    try:
        success = asyncio.run(test_kucoin_opportunities())
        if success:
            print("\n🎉 Test completed! KuCoin should now show opportunities.")
            print("\n🚀 Next steps:")
            print("1. Run the main GUI: python main_gui.py")
            print("2. Select only KuCoin exchange")
            print("3. Enable auto-trading")
            print("4. Start the bot")
        else:
            print("\n❌ Test failed. Check the output above for details.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")