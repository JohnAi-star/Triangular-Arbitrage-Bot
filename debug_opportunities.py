#!/usr/bin/env python3
"""
Debug script to check opportunity detection and profit calculations
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from utils.logger import setup_logger

load_dotenv()

async def debug_opportunities():
    """Debug opportunity detection"""
    logger = setup_logger('DebugOpportunities')
    
    print("🔍 Debugging Opportunity Detection")
    print("=" * 50)
    
    try:
        # Initialize exchange manager
        exchange_manager = MultiExchangeManager()
        success = await exchange_manager.initialize_exchanges(['binance'])
        
        if not success:
            print("❌ Failed to connect to exchanges")
            return
        
        print("✅ Connected to exchanges")
        
        # Initialize detector with debug settings
        detector = MultiExchangeDetector(
            exchange_manager,
            None,  # No WebSocket manager for debugging
            {
                'min_profit_percentage': 0.001,  # Even lower threshold for testing
                'max_trade_amount': 100
            }
        )
        
        await detector.initialize()
        print(f"✅ Detector initialized with {sum(len(t) for t in detector.triangle_paths.values())} triangles")
        
        # Scan for opportunities
        print("\n🔍 Scanning for opportunities...")
        opportunities = await detector.scan_all_opportunities()
        
        print(f"\n📊 Results:")
        print(f"Found {len(opportunities)} opportunities")
        
        for i, opp in enumerate(opportunities[:10]):  # Show first 10
            print(f"\n{i+1}. {opp.exchange} - {' → '.join(opp.triangle_path[:3])}")
            print(f"   Profit: {opp.profit_percentage:.6f}%")
            print(f"   Amount: ${opp.profit_amount:.6f}")
            print(f"   Is Profitable: {opp.is_profitable}")
            if hasattr(opp, 'net_profit_percent'):
                print(f"   Net Profit %: {opp.net_profit_percent:.6f}%")
            if hasattr(opp, 'min_profit_threshold'):
                print(f"   Threshold: {opp.min_profit_threshold:.6f}%")
        
        if not opportunities:
            print("\n⚠️ No opportunities found. This could mean:")
            print("1. Market conditions don't have arbitrage opportunities")
            print("2. Profit calculation logic needs adjustment")
            print("3. Price data is not being fetched correctly")
            print("4. All opportunities are below the minimum threshold")
            print(f"5. Current threshold is {detector.min_profit_pct:.6f}%")
            
            # Test price fetching
            print("\n🔍 Testing price fetching...")
            exchange = exchange_manager.get_exchange('binance')
            if exchange:
                ticker = await exchange.get_ticker('BTC/USDT')
                print(f"BTC/USDT ticker: {ticker}")
                
                tickers = await exchange.fetch_tickers()
                print(f"Total tickers fetched: {len(tickers)}")
                
                # Show sample tickers
                sample_pairs = ['BTC/USDT', 'ETH/USDT', 'BTC/ETH']
                for pair in sample_pairs:
                    if pair in tickers:
                        t = tickers[pair]
                        print(f"{pair}: bid={t.get('bid')}, ask={t.get('ask')}, last={t.get('last')}")
                
                # Test manual triangle calculation
                print("\n🧮 Manual Triangle Test:")
                if all(pair in tickers for pair in ['ETH/BTC', 'BTC/USDT', 'ETH/USDT']):
                    eth_btc = tickers['ETH/BTC']
                    btc_usdt = tickers['BTC/USDT'] 
                    eth_usdt = tickers['ETH/USDT']
                    
                    print(f"ETH/BTC: bid={eth_btc.get('bid')}, ask={eth_btc.get('ask')}")
                    print(f"BTC/USDT: bid={btc_usdt.get('bid')}, ask={btc_usdt.get('ask')}")
                    print(f"ETH/USDT: bid={eth_usdt.get('bid')}, ask={eth_usdt.get('ask')}")
                    
                    # Manual calculation: ETH → BTC → USDT → ETH
                    start_eth = 100
                    btc_amount = start_eth * eth_btc.get('bid', 0)
                    usdt_amount = btc_amount * btc_usdt.get('bid', 0)
                    final_eth = usdt_amount / eth_usdt.get('ask', 1)
                    profit_pct = ((final_eth - start_eth) / start_eth) * 100
                    print(f"Manual calc: {start_eth} ETH → {btc_amount:.8f} BTC → {usdt_amount:.2f} USDT → {final_eth:.6f} ETH")
                    print(f"Manual profit: {profit_pct:.6f}%")
        
        await exchange_manager.disconnect_all()
        
    except Exception as e:
        logger.error(f"Debug failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(debug_opportunities())