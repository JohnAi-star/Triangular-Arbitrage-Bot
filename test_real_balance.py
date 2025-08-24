#!/usr/bin/env python3
"""
Test Real Balance Fetching from KuCoin and Gate.io
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

load_dotenv()

async def test_real_balance():
    """Test real balance fetching from multiple exchanges"""
    logger = setup_logger('RealBalanceTest', 'INFO')
    
    print("🔍 Testing REAL Balance Fetching")
    print("=" * 60)
    
    # Test KuCoin
    print("\n🔧 Testing KuCoin Balance...")
    api_key = os.getenv('KUCOIN_API_KEY', '').strip()
    api_secret = os.getenv('KUCOIN_API_SECRET', '').strip()
    passphrase = os.getenv('KUCOIN_PASSPHRASE', '').strip()
    
    if all([api_key, api_secret, passphrase]):
        try:
            config = {
                'exchange_id': 'kucoin',
                'api_key': api_key,
                'api_secret': api_secret,
                'passphrase': passphrase,
                'sandbox': False,
                'fee_token': 'KCS',
                'fee_discount': 0.50,
                'maker_fee': 0.001,
                'taker_fee': 0.001,
                'maker_fee_with_token': 0.0005,
                'taker_fee_with_token': 0.0005
            }
            
            exchange = UnifiedExchange(config)
            
            if await exchange.connect():
                balance = await exchange.get_account_balance()
                if balance:
                    total_usd = await exchange._calculate_usd_value(balance)
                    print(f"✅ KuCoin REAL Balance: ~${total_usd:.2f} USD")
                    
                    # Show top balances
                    for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True)[:10]:
                        if amount > 0.001:
                            print(f"   {currency}: {amount:.8f}")
                    
                    # Check KCS balance specifically
                    kcs_balance = balance.get('KCS', 0)
                    if kcs_balance > 0:
                        print(f"✅ KCS Balance: {kcs_balance:.8f} (fee discount available)")
                    else:
                        print(f"⚠️ No KCS balance (standard fees apply)")
                else:
                    print("❌ No balance data retrieved from KuCoin")
                
                await exchange.disconnect()
            else:
                print("❌ Failed to connect to KuCoin")
        except Exception as e:
            print(f"❌ KuCoin test failed: {e}")
    else:
        print("❌ KuCoin credentials missing")
    
    # Test Gate.io
    print("\n🔧 Testing Gate.io Balance...")
    api_key = os.getenv('GATE_API_KEY', '').strip()
    api_secret = os.getenv('GATE_API_SECRET', '').strip()
    
    if all([api_key, api_secret]):
        try:
            config = {
                'exchange_id': 'gate',
                'api_key': api_key,
                'api_secret': api_secret,
                'sandbox': False,
                'fee_token': 'GT',
                'fee_discount': 0.55,
                'maker_fee': 0.002,
                'taker_fee': 0.002,
                'maker_fee_with_token': 0.0009,
                'taker_fee_with_token': 0.0009
            }
            
            exchange = UnifiedExchange(config)
            
            if await exchange.connect():
                balance = await exchange.get_account_balance()
                if balance:
                    total_usd = await exchange._calculate_usd_value(balance)
                    print(f"✅ Gate.io REAL Balance: ~${total_usd:.2f} USD")
                    
                    # Show top balances
                    for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True)[:10]:
                        if amount > 0.001:
                            print(f"   {currency}: {amount:.8f}")
                    
                    # Check GT balance specifically
                    gt_balance = balance.get('GT', 0)
                    if gt_balance > 0:
                        print(f"✅ GT Balance: {gt_balance:.8f} (fee discount available)")
                    else:
                        print(f"⚠️ No GT balance (standard fees apply)")
                else:
                    print("❌ No balance data retrieved from Gate.io")
                
                await exchange.disconnect()
            else:
                print("❌ Failed to connect to Gate.io")
        except Exception as e:
            print(f"❌ Gate.io test failed: {e}")
    else:
        print("❌ Gate.io credentials missing")
    
    print("\n" + "=" * 60)
    print("✅ Balance test completed!")
    print("\nIf balances were detected:")
    print("1. The bot will now show real balance in logs")
    print("2. Auto-trading will work with your real balance")
    print("3. Profitable opportunities should be visible")

if __name__ == "__main__":
    asyncio.run(test_real_balance())