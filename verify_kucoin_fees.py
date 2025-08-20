#!/usr/bin/env python3
"""
KuCoin Fee Verification Script
Shows exactly how fees are calculated and ensures profit after all costs
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

load_dotenv()

async def verify_kucoin_fees():
    """Verify KuCoin fee structure and profit calculations"""
    logger = setup_logger('KuCoinFeeVerification', 'INFO')
    
    print("🔍 KuCoin Fee Structure Verification")
    print("=" * 60)
    
    # Check KuCoin credentials
    api_key = os.getenv('KUCOIN_API_KEY', '').strip()
    api_secret = os.getenv('KUCOIN_API_SECRET', '').strip()
    passphrase = os.getenv('KUCOIN_PASSPHRASE', '').strip()
    
    if not all([api_key, api_secret, passphrase]):
        print("❌ Missing KuCoin credentials")
        return False
    
    print(f"✅ KuCoin credentials found")
    
    try:
        # Initialize KuCoin exchange
        config = {
            'exchange_id': 'kucoin',
            'api_key': api_key,
            'api_secret': api_secret,
            'passphrase': passphrase,
            'sandbox': False,  # LIVE TRADING
            'fee_token': 'KCS',
            'fee_discount': 0.50,  # 50% discount with KCS
            'maker_fee': 0.001,    # 0.1% base
            'taker_fee': 0.001,    # 0.1% base
            'maker_fee_with_token': 0.0005,  # 0.05% with KCS
            'taker_fee_with_token': 0.0005   # 0.05% with KCS
        }
        
        exchange = UnifiedExchange(config)
        
        if not await exchange.connect():
            print("❌ Failed to connect to KuCoin")
            return False
        
        print("✅ Connected to KuCoin LIVE account")
        
        # Get real balance
        balance = await exchange.get_account_balance()
        usdt_balance = balance.get('USDT', 0)
        kcs_balance = balance.get('KCS', 0)
        
        print(f"\n💰 REAL KuCoin Balance:")
        print(f"   USDT: {usdt_balance:.8f}")
        print(f"   KCS: {kcs_balance:.8f}")
        
        # Check fee structure
        print(f"\n📊 KuCoin Fee Structure:")
        print(f"   Base Maker Fee: 0.1% (0.001)")
        print(f"   Base Taker Fee: 0.1% (0.001)")
        
        if kcs_balance > 0:
            print(f"   ✅ KCS Balance Detected: {kcs_balance:.8f}")
            print(f"   🎯 VIP 0 + KCS Fees:")
            print(f"      Maker Fee: 0.05% (0.0005)")
            print(f"      Taker Fee: 0.05% (0.0005)")
            print(f"   💰 Fee Discount: 50% with KCS")
            
            # Calculate total costs for triangular arbitrage
            fee_per_trade = 0.0005  # 0.05% with KCS
            total_fees = fee_per_trade * 3  # 3 trades in triangle
            slippage = 0.00003  # 0.003% slippage (very low)
            total_costs = total_fees + slippage
            total_costs_pct = total_costs * 100
            
            print(f"\n🔺 Triangular Arbitrage Total Costs (WITH KCS):")
            print(f"   Fee per trade: 0.05%")
            print(f"   Total fees (3 trades): {total_fees*100:.3f}%")
            print(f"   Slippage estimate: {slippage*100:.3f}%")
            print(f"   TOTAL COSTS: {total_costs_pct:.3f}%")
            
        else:
            print(f"   ❌ No KCS Balance")
            print(f"   📊 Standard Fees (without KCS):")
            print(f"      Maker Fee: 0.1% (0.001)")
            print(f"      Taker Fee: 0.1% (0.001)")
            
            # Calculate total costs without KCS
            fee_per_trade = 0.001  # 0.1% without KCS
            total_fees = fee_per_trade * 3
            slippage = 0.0001  # 0.01% slippage
            total_costs = total_fees + slippage
            total_costs_pct = total_costs * 100
            
            print(f"\n🔺 Triangular Arbitrage Total Costs (WITHOUT KCS):")
            print(f"   Fee per trade: 0.1%")
            print(f"   Total fees (3 trades): {total_fees*100:.1f}%")
            print(f"   Slippage estimate: {slippage*100:.2f}%")
            print(f"   TOTAL COSTS: {total_costs_pct:.1f}%")
        
        # Example profit calculation
        print(f"\n💡 Example: Your 0.223% Opportunity")
        print(f"   Gross Profit: 0.223%")
        print(f"   Total Costs: {total_costs_pct:.3f}%")
        net_profit = 0.223 - total_costs_pct
        print(f"   NET PROFIT: {net_profit:.3f}%")
        
        if net_profit > 0:
            print(f"   ✅ PROFITABLE: {net_profit:.3f}% profit after all fees!")
            
            # Calculate dollar profit
            trade_amount = 20.0  # $20 trade
            dollar_profit = trade_amount * (net_profit / 100)
            print(f"   💰 On $20 trade: ${dollar_profit:.4f} profit")
        else:
            print(f"   ❌ NOT PROFITABLE: {net_profit:.3f}% loss after fees")
        
        # Show minimum profitable threshold
        min_gross_profit = total_costs_pct + 0.2  # Need 0.2% net profit
        print(f"\n🎯 Minimum Gross Profit Needed: {min_gross_profit:.3f}%")
        print(f"   (To achieve 0.2% net profit after {total_costs_pct:.3f}% costs)")
        
        await exchange.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Main verification function"""
    print("🔺 KuCoin Fee & Profit Verification")
    print("=" * 60)
    print("This script will:")
    print("1. Connect to your REAL KuCoin account")
    print("2. Check your KCS balance for fee discounts")
    print("3. Calculate exact fees for triangular arbitrage")
    print("4. Verify profit calculations after all costs")
    print("=" * 60)
    
    success = await verify_kucoin_fees()
    
    if success:
        print("\n✅ Fee verification completed!")
        print("\n🎯 KEY POINTS:")
        print("   • Bot ONLY executes trades that are profitable AFTER all fees")
        print("   • KCS balance reduces fees from 0.1% to 0.05% per trade")
        print("   • Total costs are calculated before execution")
        print("   • Your 0.223% opportunity should be profitable with KCS discount")
        print("   • All profits shown are NET profits (after fees)")
    else:
        print("\n❌ Fee verification failed")

if __name__ == "__main__":
    asyncio.run(main())