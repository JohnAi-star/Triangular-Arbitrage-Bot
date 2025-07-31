#!/usr/bin/env python3
"""
Test script to verify API connection and balance detection
"""

import asyncio
import os
from dotenv import load_dotenv
import ccxt.async_support as ccxt

load_dotenv()

async def test_binance_connection():
    """Test Binance API connection and balance retrieval"""
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ No API credentials found in .env file")
        return False
    
    print(f"🔑 Testing API Key: {api_key[:8]}...{api_key[-4:]}")
    
    try:
        # Create exchange instance
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'sandbox': False,  # Use live trading
            'options': {'defaultType': 'spot'}
        })
        
        print("📡 Connecting to Binance...")
        
        # Load markets
        markets = await exchange.load_markets()
        print(f"✅ Connected! Found {len(markets)} trading pairs")
        
        # Test account info
        print("🔍 Fetching account information...")
        account = await exchange.fetch_balance()
        
        print("\n💰 Account Balance:")
        total_usd = 0
        balance_found = False
        
        for currency, info in account.items():
            if currency in ['info', 'timestamp', 'datetime']:
                continue
                
            if isinstance(info, dict):
                free = float(info.get('free', 0))
                used = float(info.get('used', 0))
                total = float(info.get('total', 0))
                
                if total > 0:
                    balance_found = True
                    print(f"  {currency}: {total:.8f} (free: {free:.8f}, used: {used:.8f})")
                    
                    # Rough USD conversion
                    if currency in ['USDT', 'USDC', 'BUSD']:
                        total_usd += total
                    elif currency == 'BTC':
                        total_usd += total * 45000
                    elif currency == 'ETH':
                        total_usd += total * 3000
                    elif currency == 'BNB':
                        total_usd += total * 300
        
        if not balance_found:
            print("  No balances found (account may be empty)")
        else:
            print(f"\n💵 Estimated Total: ~${total_usd:.2f} USD")
        
        # Test ticker data
        print("\n📊 Testing market data...")
        ticker = await exchange.fetch_ticker('BTC/USDT')
        print(f"  BTC/USDT: ${ticker['last']:.2f} (bid: ${ticker['bid']:.2f}, ask: ${ticker['ask']:.2f})")
        
        # Test trading pairs for triangles
        print(f"\n🔺 Testing triangle detection...")
        major_pairs = []
        for symbol in ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'BTC/ETH', 'BNB/BTC', 'ETH/BNB']:
            if symbol in markets:
                major_pairs.append(symbol)
                ticker = await exchange.fetch_ticker(symbol)
                print(f"  ✅ {symbol}: ${ticker['last']:.8f}")
        
        print(f"\n🎯 Found {len(major_pairs)} major pairs for triangular arbitrage")
        
        # Test a simple triangle calculation
        if len(major_pairs) >= 3:
            print("\n🧮 Testing triangle calculation (BTC→USDT→ETH→BTC)...")
            try:
                # Use available pairs instead of assuming BTC/ETH exists
                btc_usdt = await exchange.fetch_ticker('BTC/USDT')
                eth_usdt = await exchange.fetch_ticker('ETH/USDT') 
                
                # Calculate ETH/BTC rate from the two USDT pairs
                eth_btc_rate = eth_usdt['last'] / btc_usdt['last']
                
                # Simulate: 1 BTC → USDT → ETH → BTC
                initial_btc = 1.0
                usdt_amount = initial_btc * btc_usdt['bid']  # Sell BTC for USDT
                eth_amount = usdt_amount / eth_usdt['ask']   # Buy ETH with USDT
                final_btc = usdt_amount / btc_usdt['ask']   # Buy BTC with USDT
                
                # Alternative calculation using ETH
                final_btc_via_eth = eth_amount * eth_btc_rate
                
                profit = final_btc - initial_btc
                profit_pct = (profit / initial_btc) * 100
                
                profit_via_eth = final_btc_via_eth - initial_btc
                profit_pct_via_eth = (profit_via_eth / initial_btc) * 100
                
                print(f"  Initial: {initial_btc:.6f} BTC")
                print(f"  After USDT: {usdt_amount:.2f} USDT")
                print(f"  After ETH: {eth_amount:.6f} ETH")
                print(f"  Final: {final_btc:.6f} BTC")
                print(f"  Profit: {profit:.6f} BTC ({profit_pct:.4f}%)")
                
                print(f"  Alternative via ETH: {final_btc_via_eth:.6f} BTC ({profit_pct_via_eth:.4f}%)")
                
                if profit_pct > 0.05 or profit_pct_via_eth > 0.05:
                    print("  🎉 Profitable opportunity detected!")
                else:
                    print("  📉 No profit in this triangle (normal)")
                    
            except Exception as e:
                print(f"  ❌ Triangle calculation failed: {e}")
        
        await exchange.close()
        print("\n✅ API connection test completed successfully!")
        return True
        
    except ccxt.AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("   Check your API key and secret")
        if exchange:
            await exchange.close()
        return False
    except ccxt.PermissionDenied as e:
        print(f"❌ Permission denied: {e}")
        print("   Check API key permissions (need 'Enable Reading' + 'Spot & Margin Trading')")
        if exchange:
            await exchange.close()
        return False
    except ccxt.NetworkError as e:
        print(f"❌ Network error: {e}")
        print("   Check internet connection and IP restrictions")
        if exchange:
            await exchange.close()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if exchange:
            await exchange.close()
        return False

if __name__ == "__main__":
    print("🔺 Binance API Connection Test")
    print("=" * 50)
    
    try:
        success = asyncio.run(test_binance_connection())
        if success:
            print("\n🎉 All tests passed! Your bot should work correctly.")
        else:
            print("\n❌ Tests failed. Please fix the issues above.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")