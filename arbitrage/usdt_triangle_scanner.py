#!/usr/bin/env python3
"""
Advanced USDT Triangle Scanner
Finds high-frequency USDT-based arbitrage opportunities
"""

import asyncio
import websockets
import json
import time
from typing import Dict, List, Any, Set
from datetime import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger('USDTScanner')

@dataclass
class USDTOpportunity:
    """USDT triangular opportunity"""
    path: str
    currency1: str
    currency2: str
    profit_pct: float
    profit_usd: float
    trade_amount: float
    pairs: List[str]
    prices: Dict[str, float]
    timestamp: datetime
    
    def __str__(self):
        return f"{self.path}: {self.profit_pct:.4f}% (${self.profit_usd:.2f})"

class USDTTriangleScanner:
    """Real-time USDT triangle scanner using WebSocket"""
    
    def __init__(self, min_profit_pct: float = 0.1, max_trade_amount: float = 50.0):
        self.min_profit_pct = min_profit_pct
        self.max_trade_amount = max_trade_amount
        
        # Price data
        self.prices: Dict[str, Dict[str, float]] = {}
        self.usdt_currencies: Set[str] = set()
        
        # WebSocket
        self.websocket = None
        self.running = False
        
        # Opportunities
        self.current_opportunities: List[USDTOpportunity] = []
        self.opportunities_found = 0
        
        logger.info(f"🔍 USDT Triangle Scanner initialized")
        logger.info(f"   Min Profit: {min_profit_pct}%")
        logger.info(f"   Max Trade: ${max_trade_amount} USDT")
    
    async def initialize(self):
        """Initialize scanner with Binance exchange info"""
        try:
            import aiohttp
            
            # Get exchange info
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.binance.com/api/v3/exchangeInfo') as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Find all USDT pairs
                        for symbol_info in data['symbols']:
                            if (symbol_info['status'] == 'TRADING' and 
                                symbol_info['quoteAsset'] == 'USDT'):
                                
                                base_asset = symbol_info['baseAsset']
                                self.usdt_currencies.add(base_asset)
                                
                                # Initialize price tracking
                                symbol = symbol_info['symbol']
                                self.prices[symbol] = {'bid': 0, 'ask': 0}
                        
                        logger.info(f"✅ Found {len(self.usdt_currencies)} USDT currencies")
                        logger.info(f"📊 Tracking {len(self.prices)} price feeds")
                        return True
                    else:
                        logger.error(f"Failed to get exchange info: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error initializing scanner: {e}")
            return False
    
    async def start_websocket_stream(self):
        """Start Binance WebSocket stream for USDT pairs"""
        websocket_url = "wss://stream.binance.com:9443/ws/!ticker@arr"
        
        logger.info("🌐 Connecting to Binance WebSocket...")
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(websocket_url) as websocket:
                    self.websocket = websocket
                    self.running = True
                    logger.info("✅ Connected to Binance WebSocket")
                    
                    retry_count = 0
                    
                    async for message in websocket:
                        try:
                            await self._process_websocket_message(message)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            
            except Exception as e:
                retry_count += 1
                logger.error(f"WebSocket connection failed (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max WebSocket retry attempts reached")
                    break
        
        self.running = False
        logger.info("WebSocket stream ended")
    
    async def _process_websocket_message(self, message: str):
        """Process WebSocket ticker data"""
        try:
            data = json.loads(message)
            
            if isinstance(data, list):
                # Update prices for USDT pairs only
                usdt_updates = 0
                
                for ticker in data:
                    if isinstance(ticker, dict):
                        symbol = ticker.get('s', '')
                        
                        # Only process USDT pairs
                        if symbol.endswith('USDT') and symbol in self.prices:
                            bid_price = ticker.get('b', 0)
                            ask_price = ticker.get('a', 0)
                            
                            if bid_price and ask_price:
                                try:
                                    self.prices[symbol]['bid'] = float(bid_price)
                                    self.prices[symbol]['ask'] = float(ask_price)
                                    usdt_updates += 1
                                except (ValueError, TypeError):
                                    continue
                
                # Scan for opportunities if we have enough updates
                if usdt_updates >= 50:  # Process when we have good data
                    await self._scan_usdt_opportunities()
                    
        except Exception as e:
            logger.error(f"Error processing WebSocket data: {e}")
    
    async def _scan_usdt_opportunities(self):
        """Scan for USDT triangular opportunities"""
        try:
            opportunities = []
            
            # Get list of currencies with valid prices
            valid_currencies = []
            for currency in self.usdt_currencies:
                symbol = f"{currency}USDT"
                if (symbol in self.prices and 
                    self.prices[symbol]['bid'] > 0 and 
                    self.prices[symbol]['ask'] > 0):
                    valid_currencies.append(currency)
            
            # Build USDT triangles
            for curr1 in valid_currencies:
                for curr2 in valid_currencies:
                    if curr1 != curr2:
                        opportunity = self._calculate_usdt_triangle(curr1, curr2)
                        if opportunity and opportunity.profit_pct >= self.min_profit_pct:
                            opportunities.append(opportunity)
                            self.opportunities_found += 1
            
            # Sort by profitability
            opportunities.sort(key=lambda x: x.profit_pct, reverse=True)
            
            # Update current opportunities
            self.current_opportunities = opportunities[:10]
            
            if opportunities:
                logger.info(f"💎 Found {len(opportunities)} USDT opportunities!")
                for i, opp in enumerate(opportunities[:3]):
                    logger.info(f"   {i+1}. {opp}")
                    
        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
    
    def _calculate_usdt_triangle(self, curr1: str, curr2: str) -> Optional[USDTOpportunity]:
        """Calculate USDT triangle: USDT → curr1 → curr2 → USDT"""
        try:
            # Required symbols
            symbol1 = f"{curr1}USDT"  # USDT → curr1
            symbol2 = f"{curr1}{curr2}"  # curr1 → curr2
            symbol3 = f"{curr2}USDT"  # curr2 → USDT
            
            # Alternative if curr1→curr2 doesn't exist
            alt_symbol2 = f"{curr2}{curr1}"
            
            # Check if all required prices exist
            if (symbol1 not in self.prices or symbol3 not in self.prices or
                (symbol2 not in self.prices and alt_symbol2 not in self.prices)):
                return None
            
            # Get prices
            price1_data = self.prices[symbol1]
            price3_data = self.prices[symbol3]
            
            if symbol2 in self.prices:
                price2_data = self.prices[symbol2]
                use_direct = True
            else:
                price2_data = self.prices[alt_symbol2]
                use_direct = False
            
            # Validate prices
            if not all(data['bid'] > 0 and data['ask'] > 0 
                      for data in [price1_data, price2_data, price3_data]):
                return None
            
            # Calculate triangle
            start_usdt = self.max_trade_amount
            
            # Step 1: USDT → curr1 (buy curr1 with USDT)
            price1 = price1_data['ask']  # Buy at ask
            amount_curr1 = start_usdt / price1
            
            # Step 2: curr1 → curr2
            if use_direct:
                # Direct: sell curr1 for curr2
                price2 = price2_data['bid']  # Sell at bid
                amount_curr2 = amount_curr1 * price2
            else:
                # Inverse: buy curr2 with curr1
                price2 = price2_data['ask']  # Buy at ask
                amount_curr2 = amount_curr1 / price2
            
            # Step 3: curr2 → USDT (sell curr2 for USDT)
            price3 = price3_data['bid']  # Sell at bid
            final_usdt = amount_curr2 * price3
            
            # Calculate profit
            gross_profit = final_usdt - start_usdt
            gross_profit_pct = (gross_profit / start_usdt) * 100
            
            # Apply costs (0.3% fees + 0.1% slippage)
            total_costs_pct = 0.4
            net_profit_pct = gross_profit_pct - total_costs_pct
            net_profit_usd = start_usdt * (net_profit_pct / 100)
            
            # Only return profitable and realistic opportunities
            if (net_profit_pct >= self.min_profit_pct and 
                net_profit_pct <= 3.0 and  # Max 3% (realistic)
                final_usdt > 0):
                
                path = f"USDT → {curr1} → {curr2} → USDT"
                pairs = [symbol1, symbol2 if use_direct else alt_symbol2, symbol3]
                
                return USDTOpportunity(
                    path=path,
                    currency1=curr1,
                    currency2=curr2,
                    profit_pct=net_profit_pct,
                    profit_usd=net_profit_usd,
                    trade_amount=start_usdt,
                    pairs=pairs,
                    prices={
                        'step1': price1,
                        'step2': price2,
                        'step3': price3,
                        'final_amount': final_usdt
                    },
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error calculating USDT triangle {curr1}-{curr2}: {e}")
            return None
    
    def get_current_opportunities(self) -> List[USDTOpportunity]:
        """Get current opportunities"""
        return self.current_opportunities.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics"""
        return {
            'running': self.running,
            'usdt_currencies': len(self.usdt_currencies),
            'price_feeds': len(self.prices),
            'opportunities_found': self.opportunities_found,
            'current_opportunities': len(self.current_opportunities)
        }

async def main():
    """Test the USDT scanner"""
    scanner = USDTTriangleScanner(min_profit_pct=0.05, max_trade_amount=50.0)
    
    if not await scanner.initialize():
        logger.error("Failed to initialize scanner")
        return
    
    try:
        await scanner.start_websocket_stream()
    except KeyboardInterrupt:
        logger.info("Scanner stopped by user")
    except Exception as e:
        logger.error(f"Scanner error: {e}")

if __name__ == "__main__":
    print("🔍 USDT Triangle Scanner")
    print("=" * 30)
    asyncio.run(main())