#!/usr/bin/env python3
"""
Simple Triangular Arbitrage Detector
Fetches ALL Binance tickers and calculates triangular arbitrage opportunities
"""

import asyncio
import websockets
import json
import time
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimpleTriangleDetector')

@dataclass
class TriangleOpportunity:
    """Simple triangular arbitrage opportunity"""
    d1: str  # Base currency
    d2: str  # Intermediate currency  
    d3: str  # Quote currency
    lv1: str  # First pair symbol
    lv2: str  # Second pair symbol
    lv3: str  # Third pair symbol
    value: float  # Profit percentage
    tpath: str  # Trading path description
    
    def __str__(self):
        return f"{self.d1}→{self.d2}→{self.d3}→{self.d1}: {self.value:.3f}%"

class SimpleTriangleDetector:
    """Simple triangular arbitrage detector using Binance WebSocket - Based on JavaScript logic"""
    
    def __init__(self, min_profit_pct: float = 0.01):
        self.min_profit_pct = min_profit_pct
        self.pairs: List[Dict] = []
        self.sym_val_j: Dict[str, Dict[str, float]] = {}
        self.websocket = None
        self.running = False
        self.opportunities_found = 0
        self.current_opportunities: List[TriangleOpportunity] = []
        
        logger.info(f"🚀 Simple Triangle Detector initialized - Min Profit: {min_profit_pct}%")
    
    async def get_pairs(self):
        """Get trading pairs and build triangular paths - Exact JavaScript logic"""
        import aiohttp
        
        logger.info("📡 Fetching Binance exchange info...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.binance.com/api/v3/exchangeInfo') as response:
                if response.status == 200:
                    e_info = await response.json()
                    
                    # Get all unique symbols (currencies)
                    symbols = list(set([
                        asset for symbol_info in e_info['symbols']
                        if symbol_info['status'] == 'TRADING'
                        for asset in [symbol_info['baseAsset'], symbol_info['quoteAsset']]
                    ]))
                    
                    # Get valid trading pairs
                    valid_pairs = [
                        symbol_info['symbol'] for symbol_info in e_info['symbols']
                        if symbol_info['status'] == 'TRADING'
                    ]
                    
                    # Initialize price tracking
                    for symbol in valid_pairs:
                        self.sym_val_j[symbol] = {'bidPrice': 0, 'askPrice': 0}
                    
                    logger.info(f"✅ Found {len(symbols)} currencies and {len(valid_pairs)} trading pairs")
                    
                    # Build triangular paths - EXACT JavaScript logic
                    self.pairs = []
                    
                    for d1 in symbols:
                        for d2 in symbols:
                            for d3 in symbols:
                                if not (d1 == d2 or d2 == d3 or d3 == d1):
                                    lv1, lv2, lv3 = [], [], []
                                    l1, l2, l3 = '', '', ''
                                    
                                    # Level 1: d1 -> d2
                                    if f"{d1}{d2}" in self.sym_val_j:
                                        lv1.append(f"{d1}{d2}")
                                        l1 = 'num'
                                    if f"{d2}{d1}" in self.sym_val_j:
                                        lv1.append(f"{d2}{d1}")
                                        l1 = 'den'
                                    
                                    # Level 2: d2 -> d3
                                    if f"{d2}{d3}" in self.sym_val_j:
                                        lv2.append(f"{d2}{d3}")
                                        l2 = 'num'
                                    if f"{d3}{d2}" in self.sym_val_j:
                                        lv2.append(f"{d3}{d2}")
                                        l2 = 'den'
                                    
                                    # Level 3: d3 -> d1
                                    if f"{d3}{d1}" in self.sym_val_j:
                                        lv3.append(f"{d3}{d1}")
                                        l3 = 'num'
                                    if f"{d1}{d3}" in self.sym_val_j:
                                        lv3.append(f"{d1}{d3}")
                                        l3 = 'den'
                                    
                                    # If all three levels have valid pairs, add to triangular paths
                                    if lv1 and lv2 and lv3:
                                        self.pairs.append({
                                            'l1': l1, 'l2': l2, 'l3': l3,
                                            'd1': d1, 'd2': d2, 'd3': d3,
                                            'lv1': lv1[0], 'lv2': lv2[0], 'lv3': lv3[0],
                                            'value': -100, 'tpath': ''
                                        })
                    
                    logger.info(f"✅ Built {len(self.pairs)} triangular arbitrage paths")
                    return True
                else:
                    logger.error(f"Failed to fetch exchange info: {response.status}")
                    return False
    
    def process_data(self, data: str):
        """Process WebSocket ticker data - EXACT JavaScript logic"""
        try:
            data = json.loads(data)
            
            # Handle subscription confirmation message
            if isinstance(data, dict) and data.get('result') is None:
                logger.info("WebSocket subscription confirmed")
                return
            
            # Handle ticker array data
            if isinstance(data, list):
                
                # Update price data
                for d in data:
                    if isinstance(d, dict) and 's' in d:
                        symbol = d.get('s')
                        if symbol and symbol in self.sym_val_j:
                            bid_price = d.get('b', 0)
                            ask_price = d.get('a', 0)
                            
                            if bid_price and ask_price:
                                try:
                                    self.sym_val_j[symbol]['bidPrice'] = float(bid_price)
                                    self.sym_val_j[symbol]['askPrice'] = float(ask_price)
                                except (ValueError, TypeError):
                                    continue
                    else:
                        # Skip non-dict items or items without symbol
                        continue
                
                # Calculate arbitrage opportunities
                profitable_opportunities = []
                
                for pair_data in self.pairs:
                    # Check if all prices are available
                    lv1_data = self.sym_val_j.get(pair_data['lv1'], {})
                    lv2_data = self.sym_val_j.get(pair_data['lv2'], {})
                    lv3_data = self.sym_val_j.get(pair_data['lv3'], {})
                    
                    if (lv1_data.get('bidPrice', 0) > 0 and 
                        lv1_data.get('askPrice', 0) > 0 and
                        lv2_data.get('bidPrice', 0) > 0 and 
                        lv2_data.get('askPrice', 0) > 0 and
                        lv3_data.get('bidPrice', 0) > 0 and
                        lv3_data.get('askPrice', 0) > 0):
                        
                        # Level 1 calculation
                        if pair_data['l1'] == 'num':
                            lv_calc = lv1_data['bidPrice']
                            lv_str = f"{pair_data['d1']}→{pair_data['lv1']}[bid:{lv1_data['bidPrice']}]→{pair_data['d2']}<br/>"
                        else:
                            lv_calc = 1 / lv1_data['askPrice']
                            lv_str = f"{pair_data['d1']}→{pair_data['lv1']}[ask:{lv1_data['askPrice']}]→{pair_data['d2']}<br/>"
                        
                        # Level 2 calculation
                        if pair_data['l2'] == 'num':
                            lv_calc *= lv2_data['bidPrice']
                            lv_str += f"{pair_data['d2']}→{pair_data['lv2']}[bid:{lv2_data['bidPrice']}]→{pair_data['d3']}<br/>"
                        else:
                            lv_calc *= 1 / lv2_data['askPrice']
                            lv_str += f"{pair_data['d2']}→{pair_data['lv2']}[ask:{lv2_data['askPrice']}]→{pair_data['d3']}<br/>"
                        
                        # Level 3 calculation
                        if pair_data['l3'] == 'num':
                            lv_calc *= lv3_data['bidPrice']
                            lv_str += f"{pair_data['d3']}→{pair_data['lv3']}[bid:{lv3_data['bidPrice']}]→{pair_data['d1']}"
                        else:
                            lv_calc *= 1 / lv3_data['askPrice']
                            lv_str += f"{pair_data['d3']}→{pair_data['lv3']}[ask:{lv3_data['askPrice']}]→{pair_data['d1']}"
                        
                        # Calculate profit percentage with safety checks
                        try:
                            if lv_calc > 0 and lv_calc != float('inf'):
                                pair_data['tpath'] = lv_str
                                gross_profit_pct = (lv_calc - 1) * 100
                                
                                # Apply trading costs (0.3% total)
                                net_profit_pct = gross_profit_pct - 0.3
                                pair_data['value'] = round(net_profit_pct, 6)
                                
                                # Add to profitable opportunities if above threshold and realistic
                                if (pair_data['value'] > self.min_profit_pct and 
                                    pair_data['value'] < 10.0 and  # Max 10% profit (realistic)
                                    pair_data['value'] > -5.0):    # Min -5% loss (realistic)
                                    
                                    opportunity = TriangleOpportunity(
                                        d1=pair_data['d1'],
                                        d2=pair_data['d2'], 
                                        d3=pair_data['d3'],
                                        lv1=pair_data['lv1'],
                                        lv2=pair_data['lv2'],
                                        lv3=pair_data['lv3'],
                                        value=pair_data['value'],
                                        tpath=pair_data['tpath']
                                    )
                                    profitable_opportunities.append(opportunity)
                        except (ZeroDivisionError, OverflowError, ValueError):
                            continue
                
                # Sort by profit percentage (highest first)
                profitable_opportunities.sort(key=lambda x: x.value, reverse=True)
                
                # Update current opportunities
                self.current_opportunities = profitable_opportunities[:10]  # Top 10
                
                if profitable_opportunities:
                    self.opportunities_found += len(profitable_opportunities)
                    logger.info(f"💎 Found {len(profitable_opportunities)} REAL opportunities!")
                    
                    # Show top 5 opportunities
                    for i, opp in enumerate(profitable_opportunities[:5]):
                        logger.info(f"   {i+1}. {opp}")
            # Handle single ticker object (not in array)
            elif isinstance(data, dict) and 's' in data:
                symbol = data.get('s')
                if symbol and symbol in self.sym_val_j:
                    bid_price = data.get('b', 0)
                    ask_price = data.get('a', 0)
                    
                    if bid_price and ask_price:
                        try:
                            self.sym_val_j[symbol]['bidPrice'] = float(bid_price)
                            self.sym_val_j[symbol]['askPrice'] = float(ask_price)
                        except (ValueError, TypeError):
                            pass
            else:
                # Handle other message types (like subscription confirmations)
                logger.debug(f"Received non-array WebSocket message: {type(data)}")
                
        except Exception as e:
            logger.error(f"Error processing WebSocket data: {e}")
            # Only log debug info if it's a real error, not just data format issues
            if "has no attribute 'get'" not in str(e):
                logger.debug(f"Problematic data type: {type(data)}")
                if hasattr(data, '__len__') and len(str(data)) < 200:
                    logger.debug(f"Data content: {data}")
    
    async def start_websocket_stream(self):
        """Start Binance WebSocket stream - EXACT JavaScript logic"""
        websocket_url = "wss://stream.binance.com:9443/ws"
        
        logger.info("🌐 Connecting to Binance WebSocket stream...")
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(websocket_url) as websocket:
                    self.websocket = websocket
                    self.running = True
                    logger.info("✅ Connected to Binance WebSocket")
                    
                    # Subscribe to all ticker data
                    subscribe_message = {
                        "method": "SUBSCRIBE",
                        "params": ["!ticker@arr"],
                        "id": 121212131
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    logger.info("📡 Subscribed to all ticker data stream")
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    
                    # Process incoming messages
                    async for message in websocket:
                        try:
                            if message and message.strip():
                                self.process_data(message)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            logger.debug(f"Message that caused error: {message[:200]}...")
                            
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
    
    def get_current_opportunities(self) -> List[TriangleOpportunity]:
        """Get current profitable opportunities"""
        return self.current_opportunities.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            'running': self.running,
            'triangular_paths': len(self.pairs),
            'opportunities_found': self.opportunities_found,
            'current_opportunities': len(self.current_opportunities)
        }

async def main():
    """Test the simple triangle detector"""
    detector = SimpleTriangleDetector(min_profit_pct=0.01)  # 0.01% minimum
    
    # Initialize
    if not await detector.get_pairs():
        logger.error("Failed to initialize detector")
        return
    
    # Start WebSocket stream
    try:
        await detector.start_websocket_stream()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    print("🚀 Simple Triangular Arbitrage Detector")
    print("=" * 70)
    asyncio.run(main())