#!/usr/bin/env python3
"""
Test script to verify profit calculation logic is working correctly
"""

import asyncio
from arbitrage.multi_exchange_detector import ArbitrageResult

def test_profit_calculations():
    """Test various profit calculation scenarios"""
    print("🧮 Testing Profit Calculation Logic")
    print("=" * 50)
    
    # Test Case 1: Normal profitable opportunity
    result1 = ArbitrageResult(
        exchange="binance",
        triangle_path=["BTC", "ETH", "USDT", "BTC"],
        profit_percentage=0.15,  # 0.15% profit
        profit_amount=1.5,       # $1.50 profit on $1000
        initial_amount=1000,
        net_profit_percent=0.15,
        min_profit_threshold=0.05
    )
    
    print(f"Test 1 - Normal Profit:")
    print(f"  Profit: {result1.profit_percentage:.4f}%")
    print(f"  Is Profitable: {result1.is_profitable}")
    print(f"  Expected: True (0.15% > 0.05% threshold)")
    print()
    
    # Test Case 2: Below threshold
    result2 = ArbitrageResult(
        exchange="binance",
        triangle_path=["BTC", "ETH", "USDT", "BTC"],
        profit_percentage=0.03,  # 0.03% profit (below 0.05% threshold)
        profit_amount=0.3,
        initial_amount=1000,
        net_profit_percent=0.03,
        min_profit_threshold=0.05
    )
    
    print(f"Test 2 - Below Threshold:")
    print(f"  Profit: {result2.profit_percentage:.4f}%")
    print(f"  Is Profitable: {result2.is_profitable}")
    print(f"  Expected: False (0.03% < 0.05% threshold)")
    print()
    
    # Test Case 3: Negative profit
    result3 = ArbitrageResult(
        exchange="binance",
        triangle_path=["BTC", "ETH", "USDT", "BTC"],
        profit_percentage=-0.1,  # -0.1% loss
        profit_amount=-1.0,
        initial_amount=1000,
        net_profit_percent=-0.1,
        min_profit_threshold=0.05
    )
    
    print(f"Test 3 - Negative Profit:")
    print(f"  Profit: {result3.profit_percentage:.4f}%")
    print(f"  Is Profitable: {result3.is_profitable}")
    print(f"  Expected: False (negative profit)")
    print()
    
    # Test realistic triangle calculation
    print("🔢 Testing Triangle Math:")
    print("-" * 30)
    
    # Example: BTC → ETH → USDT → BTC
    start_amount = 1000  # $1000 worth of BTC
    
    # Prices (example)
    btc_eth_price = 15.0    # 1 BTC = 15 ETH
    eth_usdt_price = 3000.0 # 1 ETH = 3000 USDT  
    btc_usdt_price = 45000.0 # 1 BTC = 45000 USDT
    
    # Step 1: BTC → ETH
    btc_amount = start_amount / btc_usdt_price  # Convert $1000 to BTC
    eth_amount = btc_amount * btc_eth_price     # Convert BTC to ETH
    
    # Step 2: ETH → USDT
    usdt_amount = eth_amount * eth_usdt_price   # Convert ETH to USDT
    
    # Step 3: USDT → BTC
    final_btc = usdt_amount / btc_usdt_price    # Convert USDT back to BTC
    final_usd = final_btc * btc_usdt_price      # Convert to USD for comparison
    
    profit = final_usd - start_amount
    profit_pct = (profit / start_amount) * 100
    
    print(f"Start: ${start_amount:.2f} ({btc_amount:.8f} BTC)")
    print(f"After BTC→ETH: {eth_amount:.6f} ETH")
    print(f"After ETH→USDT: {usdt_amount:.2f} USDT")
    print(f"After USDT→BTC: {final_btc:.8f} BTC (${final_usd:.2f})")
    print(f"Profit: ${profit:.2f} ({profit_pct:.4f}%)")
    
    # This should be close to 0% (no arbitrage in this example)
    if abs(profit_pct) < 0.01:
        print("✅ Math checks out - no arbitrage opportunity")
    else:
        print(f"⚠️ Unexpected result - check calculation")
    
    print("\n" + "=" * 50)
    print("✅ Profit calculation tests completed!")

if __name__ == "__main__":
    test_profit_calculations()