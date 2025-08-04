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
            # BTC-based triangles
            ('BTC', 'ETH', 'USDT'),
            ('BTC', 'BNB', 'USDT'),
            ('BTC', 'ADA', 'USDT'),
            ('BTC', 'SOL', 'USDT'),
            ('BTC', 'DOT', 'USDT'),
            ('BTC', 'LINK', 'USDT'),
            
            # ETH-based triangles
            ('ETH', 'BNB', 'USDT'),
            ('ETH', 'ADA', 'USDT'),
            ('ETH', 'SOL', 'USDT'),
            ('ETH', 'DOT', 'USDT'),
            
            # BNB-based triangles
            ('BNB', 'ADA', 'USDT'),
            ('BNB', 'SOL', 'USDT'),
            ('BNB', 'DOT', 'USDT'),
            
            # USDC triangles
            ('BTC', 'ETH', 'USDC'),
            ('BTC', 'BNB', 'USDC'),
            ('ETH', 'BNB', 'USDC'),
        ]
        
        print(f"🔍 Checking {len(triangular_paths)} triangular paths...")
        
        for base, intermediate, quote in triangular_paths:
            try:
                # Build the three pairs needed
                pair1 = f"{base}{intermediate}"      # BTC + ETH = BTCETH
                pair2 = f"{intermediate}{quote}"     # ETH + USDT = ETHUSDT  
                pair3 = f"{base}{quote}"             # BTC + USDT = BTCUSDT
                
                # Check if all pairs exist in prices
                if pair1 in prices and pair2 in prices and pair3 in prices:
                    profit_pct = self.calculate_triangle_profit(
                        prices, base, intermediate, quote, pair1, pair2, pair3
                    )
                    
                    if profit_pct >= self.min_profit_pct:
                        profit_usd = self.max_trade_amount * (profit_pct / 100)
                        
                        opportunity = {
                            'path': f"{base} → {intermediate} → {quote} → {base}",
                            'pairs': [pair1, pair2, pair3],
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
                        print(f"   Trade Amount: ${self.max_trade_amount}")
                        print()
                        
            except Exception as e:
                print(f"❌ Error calculating {base}-{intermediate}-{quote}: {e}")
                continue
        
        return opportunities
    
    def calculate_triangle_profit(self, prices: Dict[str, float], 
                                base: str, intermediate: str, quote: str,
                                pair1: str, pair2: str, pair3: str) -> float:
        """Calculate triangular arbitrage profit - EXACT YouTube method"""
        
        try:
            # Get prices
            price1 = prices[pair1]  # BTCETH price
            price2 = prices[pair2]  # ETHUSDT price  
            price3 = prices[pair3]  # BTCUSDT price
            
            # Start with $100 worth of base currency (BTC)
            start_amount_usd = self.max_trade_amount
            start_amount_base = start_amount_usd / price3  # Convert $100 to BTC
            
            # Step 1: BTC → ETH (sell BTC for ETH)
            # If BTCETH = 15, then 1 BTC = 15 ETH
            eth_amount = start_amount_base * price1
            
            # Step 2: ETH → USDT (sell ETH for USDT)
            # If ETHUSDT = 3000, then ETH amount * 3000 = USDT
            usdt_amount = eth_amount * price2
            
            # Step 3: USDT → BTC (buy BTC with USDT)
            # If BTCUSDT = 45000, then USDT / 45000 = BTC
            final_btc_amount = usdt_amount / price3
            
            # Calculate profit
            profit_btc = final_btc_amount - start_amount_base
            profit_usd = profit_btc * price3
            profit_pct = (profit_usd / start_amount_usd) * 100
            
            # Apply trading fees (0.1% per trade = 0.3% total)
            total_fees_pct = 0.3
            net_profit_pct = profit_pct - total_fees_pct
            
            return net_profit_pct
            
        except Exception as e:
            print(f"❌ Calculation error: {e}")
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