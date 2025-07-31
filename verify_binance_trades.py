#!/usr/bin/env python3
"""
Script to verify trades in your Binance account
This will show recent trades to confirm the bot is working
"""

import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt.async_support as ccxt

load_dotenv()

async def verify_binance_trades():
    """Verify recent trades in Binance account"""
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("❌ No API credentials found")
        return False
    
    try:
        # Create exchange instance
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'sandbox': False,
            'options': {'defaultType': 'spot'}
        })
        
        print("🔍 Fetching recent trades from your Binance account...")
        
        # Get recent trades for major pairs
        major_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'BTC/ETH']
        all_trades = []
        
        for symbol in major_pairs:
            try:
                # Get trades from last 24 hours
                since = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
                trades = await exchange.fetch_my_trades(symbol, since=since, limit=50)
                
                for trade in trades:
                    all_trades.append({
                        'symbol': symbol,
                        'id': trade['id'],
                        'timestamp': datetime.fromtimestamp(trade['timestamp'] / 1000),
                        'side': trade['side'],
                        'amount': trade['amount'],
                        'price': trade['price'],
                        'cost': trade['cost'],
                        'fee': trade['fee']
                    })
                    
            except Exception as e:
                print(f"⚠️  Could not fetch trades for {symbol}: {e}")
        
        # Sort trades by timestamp (newest first)
        all_trades.sort(key=lambda x: x['timestamp'], reverse=True)
        
        if not all_trades:
            print("📭 No recent trades found in the last 24 hours")
            print("   This is normal if you haven't executed any trades yet")
        else:
            print(f"📊 Found {len(all_trades)} recent trades:")
            print()
            print("Recent Trades (Last 24 Hours):")
            print("-" * 80)
            print(f"{'Time':<20} {'Symbol':<12} {'Side':<6} {'Amount':<15} {'Price':<12} {'Total':<12} {'Fee'}")
            print("-" * 80)
            
            for trade in all_trades[:20]:  # Show last 20 trades
                time_str = trade['timestamp'].strftime('%H:%M:%S')
                fee_str = f"{trade['fee']['cost']:.6f} {trade['fee']['currency']}" if trade['fee'] else "N/A"
                
                print(f"{time_str:<20} {trade['symbol']:<12} {trade['side']:<6} "
                      f"{trade['amount']:<15.8f} {trade['price']:<12.8f} "
                      f"{trade['cost']:<12.2f} {fee_str}")
        
        # Get current balances
        print("\n💰 Current Account Balances:")
        print("-" * 40)
        balance = await exchange.fetch_balance()
        
        total_usd = 0
        for currency, info in balance.items():
            if currency in ['info', 'timestamp', 'datetime']:
                continue
                
            if isinstance(info, dict):
                total = float(info.get('total', 0))
                if total > 0:
                    print(f"{currency:<8}: {total:.8f}")
                    
                    # Rough USD conversion
                    if currency in ['USDT', 'USDC', 'BUSD']:
                        total_usd += total
                    elif currency == 'BTC':
                        total_usd += total * 45000
                    elif currency == 'ETH':
                        total_usd += total * 3000
                    elif currency == 'BNB':
                        total_usd += total * 300
        
        print(f"\nEstimated Total: ~${total_usd:.2f} USD")
        
        # Check for arbitrage patterns
        print("\n🔍 Analyzing for Arbitrage Patterns:")
        print("-" * 40)
        
        # Look for rapid buy/sell sequences that might indicate arbitrage
        arbitrage_sequences = []
        for i in range(len(all_trades) - 2):
            trade1 = all_trades[i]
            trade2 = all_trades[i + 1]
            trade3 = all_trades[i + 2]
            
            # Check if trades happened within 5 minutes of each other
            time_diff1 = abs((trade1['timestamp'] - trade2['timestamp']).total_seconds())
            time_diff2 = abs((trade2['timestamp'] - trade3['timestamp']).total_seconds())
            
            if time_diff1 < 300 and time_diff2 < 300:  # Within 5 minutes
                # Check if it looks like a triangular pattern
                symbols = [trade1['symbol'], trade2['symbol'], trade3['symbol']]
                if len(set(symbols)) >= 2:  # At least 2 different symbols
                    arbitrage_sequences.append([trade1, trade2, trade3])
        
        if arbitrage_sequences:
            print(f"Found {len(arbitrage_sequences)} potential arbitrage sequences:")
            for i, seq in enumerate(arbitrage_sequences[:5]):  # Show first 5
                print(f"\nSequence {i+1}:")
                for trade in seq:
                    print(f"  {trade['timestamp'].strftime('%H:%M:%S')} - "
                          f"{trade['side']} {trade['amount']:.6f} {trade['symbol']} "
                          f"at {trade['price']:.6f}")
        else:
            print("No obvious arbitrage sequences detected")
            print("(This is normal if you haven't run arbitrage trades yet)")
        
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verifying trades: {e}")
        return False

if __name__ == "__main__":
    print("🔺 Binance Trade Verification")
    print("=" * 50)
    
    try:
        success = asyncio.run(verify_binance_trades())
        if success:
            print("\n✅ Trade verification completed!")
        else:
            print("\n❌ Trade verification failed.")
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")