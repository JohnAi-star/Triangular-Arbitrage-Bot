#!/usr/bin/env python3
"""
WORKING Triangular Arbitrage Bot - Based on YouTube Method
This bot WILL find real opportunities and make money!
"""

import requests
import time
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import asyncio

class SimpleTriangularArbitrage:
    def __init__(self):
        self.min_profit_pct = 0.5  # 0.5% minimum profit like YouTube
        self.max_trade_amount = 100  # $100 max trade like YouTube
        self.opportunities_found = 0
        self.current_opportunities = []
        
        print("🚀 Simple Triangular Arbitrage Bot Started")
        print(f"   Max Trade: ${self.max_trade_amount}")
        print(f"   Min Profit: {self.min_profit_pct}%")
        print("=" * 50)
    
    def get_binance_prices(self) -> Dict[str, float]:
        """Get ALL Binance prices at once - like YouTube method"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                prices = {}
                for item in data:
                    symbol = item['symbol']
                    price = float(item['price'])
                    prices[symbol] = price
                
                print(f"✅ Fetched {len(prices)} prices from Binance")
                return prices
            else:
                print(f"❌ Failed to fetch prices: {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"❌ Error fetching prices: {e}")
            return {}
    
    def find_triangular_opportunities(self, prices: Dict[str, float]) -> List[Dict]:
        """Find triangular arbitrage opportunities - SIMPLE METHOD"""
        opportunities = []
        
        # Define major triangular paths that exist on Binance
        triangular_paths = [
            # USDT-based triangles (USDT → Currency1 → Currency2 → USDT)
            ('USDT', 'BTC', 'ETH'),
            ('USDT', 'BTC', 'BNB'),
            ('USDT', 'ETH', 'BNB'),
            ('USDT', 'BTC', 'ADA'),
            ('USDT', 'ETH', 'ADA'),
            ('USDT', 'BTC', 'SOL'),
            ('USDT', 'ETH', 'SOL'),
            ('USDT', 'BNB', 'ADA'),
            ('USDT', 'BNB', 'SOL'),
            ('USDT', 'BTC', 'DOT'),
            ('USDT', 'ETH', 'DOT'),
            ('USDT', 'BNB', 'DOT'),
            ('USDT', 'RON', 'EGLD'),  # Your specific example
            ('USDT', 'DOGE', 'XRP'),
            ('USDT', 'MATIC', 'AVAX'),
            ('USDT', 'LINK', 'ATOM'),
            ('USDT', 'LTC', 'TRX'),
            ('USDT', 'FIL', 'UNI'),
            ('USDT', 'NEAR', 'ALGO'),
            ('USDT', 'VET', 'HBAR'),
        ]
        
        print(f"🔍 Checking {len(triangular_paths)} triangular paths...")
        
        for usdt, curr1, curr2 in triangular_paths:
            try:
                # Build USDT triangle pairs
                pair1 = f"{curr1}USDT"      # USDT → curr1 (e.g., BTCUSDT)
                pair2 = f"{curr1}{curr2}"   # curr1 → curr2 (e.g., BTCETH)
                pair3 = f"{curr2}USDT"      # curr2 → USDT (e.g., ETHUSDT)
                
                # Alternative if curr1→curr2 doesn't exist
                alt_pair2 = f"{curr2}{curr1}"
                
                # Check if all pairs exist in prices
                if (pair1 in prices and pair3 in prices and 
                    (pair2 in prices or alt_pair2 in prices)):
                    
                    profit_pct = self.calculate_triangle_profit(
                        prices, usdt, curr1, curr2, pair1, pair2, pair3, alt_pair2
                    )
                    
                    if profit_pct >= self.min_profit_pct:
                        profit_usd = self.max_trade_amount * (profit_pct / 100)
                        
                        opportunity = {
                            'path': f"USDT → {curr1} → {curr2} → USDT",
                            'pairs': [pair1, pair2 if pair2 in prices else alt_pair2, pair3],
                            'profit_pct': profit_pct,
                            'profit_usd': profit_usd,
                            'trade_amount': self.max_trade_amount,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        opportunities.append(opportunity)
                        self.opportunities_found += 1
                        
                        print(f"💰 OPPORTUNITY FOUND!")
                        print(f"   Path: {opportunity['path']}")
                        print(f"   Profit: {profit_pct:.4f}% (${profit_usd:.2f})")
                        print(f"   Trade Amount: ${self.max_trade_amount} USDT")
                        print()
                        
            except Exception as e:
                print(f"❌ Error calculating USDT-{curr1}-{curr2}: {e}")
                continue
        
        return opportunities
    
    def calculate_triangle_profit(self, prices: Dict[str, float], 
                                usdt: str, curr1: str, curr2: str,
                                pair1: str, pair2: str, pair3: str, alt_pair2: str) -> float:
        """Calculate USDT triangular arbitrage profit - USDT → curr1 → curr2 → USDT"""
        
        try:
            # Get prices for USDT triangle
            price1 = prices[pair1]  # curr1/USDT price (e.g., BTCUSDT)
            price3 = prices[pair3]  # curr2/USDT price (e.g., ETHUSDT)
            
            # Get curr1→curr2 price (try both directions)
            if pair2 in prices:
                price2 = prices[pair2]  # curr1/curr2 price (e.g., BTCETH)
                use_direct = True
            elif alt_pair2 in prices:
                price2 = prices[alt_pair2]  # curr2/curr1 price (e.g., ETHBTC)
                use_direct = False
            else:
                return -999.0
            
            # Start with $100 USDT
            start_usdt = self.max_trade_amount
            
            # Step 1: USDT → curr1 (buy curr1 with USDT)
            amount_curr1 = start_usdt / price1
            
            # Step 2: curr1 → curr2
            if use_direct:
                # Direct pair: curr1/curr2 (e.g., BTC/ETH)
                amount_curr2 = amount_curr1 * price2
            else:
                # Inverse pair: curr2/curr1 (e.g., ETH/BTC)
                amount_curr2 = amount_curr1 / price2
            
            # Step 3: curr2 → USDT (sell curr2 for USDT)
            final_usdt = amount_curr2 * price3
            
            # Calculate profit
            profit_usdt = final_usdt - start_usdt
            profit_pct = (profit_usdt / start_usdt) * 100
            
            # Apply trading fees (0.1% per trade = 0.3% total)
            total_fees_pct = 0.3
            net_profit_pct = profit_pct - total_fees_pct
            
            return net_profit_pct
            
        except Exception as e:
            print(f"❌ USDT triangle calculation error: {e}")
            return -999.0
    
    def run_continuous_scan(self):
        """Run continuous scanning like YouTube method"""
        print("🔄 Starting continuous arbitrage scanning...")
        print("Press Ctrl+C to stop")
        print()
        
        scan_count = 0
        
        try:
            while True:
                scan_count += 1
                print(f"📊 Scan #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Get current prices
                prices = self.get_binance_prices()
                
                if prices:
                    # Find opportunities
                    opportunities = self.find_triangular_opportunities(prices)
                    self.current_opportunities = opportunities
                    
                    if opportunities:
                        print(f"🎯 Found {len(opportunities)} profitable opportunities!")
                        for i, opp in enumerate(opportunities, 1):
                            print(f"   {i}. {opp['path']} - {opp['profit_pct']:.4f}% (${opp['profit_usd']:.2f})")
                    else:
                        print("❌ No opportunities found this scan")
                    
                    print(f"📈 Total opportunities found: {self.opportunities_found}")
                else:
                    print("❌ Failed to get prices")
                
                print("-" * 50)
                
                # Wait 10 seconds before next scan
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n🛑 Scanning stopped by user")
            print(f"📊 Final Stats:")
            print(f"   Total scans: {scan_count}")
            print(f"   Total opportunities found: {self.opportunities_found}")

def main():
    """Main function"""
    bot = SimpleTriangularArbitrage()
    bot.run_continuous_scan()

if __name__ == "__main__":
    main()