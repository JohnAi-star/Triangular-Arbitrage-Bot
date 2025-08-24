#!/usr/bin/env python3
"""
Real-Time Triangular Arbitrage Detector using Binance WebSocket
"""

import asyncio
import websockets
import json
import time
from typing import Dict, List, Any, Set, Tuple, Optional
from datetime import datetime
import logging
from dataclasses import dataclass
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('RealtimeDetector')

@dataclass
class TriangleOpportunity:
    """Real-time triangular arbitrage opportunity"""
    path: List[str]
    pairs: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float
    steps: List[Dict[str, Any]]
    timestamp: datetime
    
    def __str__(self):
        return f"{' → '.join(self.path)}: {self.profit_percentage:.4f}% (${self.profit_amount:.2f})"

class RealtimeArbitrageDetector:
    """Real-time triangular arbitrage detector using Binance WebSocket"""
    
    def __init__(self, min_profit_pct: float = 0.5, max_trade_amount: float = 100.0):
        self.min_profit_pct = min_profit_pct
        self.max_trade_amount = max_trade_amount
        
        # Real-time price data
        self.price_map: Dict[str, Dict[str, float]] = {}
        self.trading_pairs: Set[str] = set()
        self.triangular_paths: List[Tuple[str, str, str]] = []
        
        # WebSocket connection
        self.websocket = None
        self.running = False
        
        # Statistics and current opportunities
        self.opportunities_found = 0
        self.last_update_time = 0
        self.current_opportunities: List[TriangleOpportunity] = []
        
        logger.info(f"🚀 Real-Time Arbitrage Detector initialized")
        logger.info(f"   Min Profit: {min_profit_pct}%")
        logger.info(f"   Max Trade: ${max_trade_amount}")
    
    async def initialize(self):
        """Initialize trading pairs and build triangular paths"""
        logger.info("📡 Fetching Binance exchange info...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.binance.com/api/v3/exchangeInfo') as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract active trading pairs
                        for symbol_info in data['symbols']:
                            if symbol_info['status'] == 'TRADING':
                                symbol = f"{symbol_info['baseAsset']}/{symbol_info['quoteAsset']}"
                                self.trading_pairs.add(symbol)
                        
                        logger.info(f"✅ Loaded {len(self.trading_pairs)} active trading pairs")
                        
                        # Build triangular paths
                        self._build_triangular_paths()
                        
                        return True
                    else:
                        logger.error(f"Failed to fetch exchange info: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error initializing: {e}")
            return False
    
    def _build_triangular_paths(self):
        """Build all valid triangular arbitrage paths"""
        logger.info("🔺 Building triangular arbitrage paths...")
        
        # Extract all currencies
        currencies = set()
        pair_lookup = {}
        
        for pair in self.trading_pairs:
            base, quote = pair.split('/')
            currencies.add(base)
            currencies.add(quote)
            
            # Store both directions for lookup
            pair_lookup[f"{base}/{quote}"] = pair
            pair_lookup[f"{quote}/{base}"] = pair
        
        # Focus on major currencies for better liquidity
        major_currencies = {'BTC', 'ETH', 'USDT', 'BNB', 'USDC', 'BUSD', 'ADA', 'DOT', 'LINK', 'LTC'}
        available_majors = currencies.intersection(major_currencies)
        
        logger.info(f"🎯 Found {len(available_majors)} major currencies: {sorted(available_majors)}")
        
        # Build triangular paths
        paths_found = 0
        for base in available_majors:
            for intermediate in available_majors:
                if intermediate == base:
                    continue
                for quote in available_majors:
                    if quote in (base, intermediate):
                        continue
                    
                    # Check if all three pairs exist
                    pair1 = f"{base}/{intermediate}"
                    pair2 = f"{intermediate}/{quote}"
                    pair3 = f"{base}/{quote}"
                    
                    if all(self._pair_exists(p, pair_lookup) for p in [pair1, pair2, pair3]):
                        self.triangular_paths.append((base, intermediate, quote))
                        paths_found += 1
                        
                        if paths_found <= 10:  # Log first 10 paths
                            logger.info(f"   Path {paths_found}: {base} → {intermediate} → {quote} → {base}")
        
        logger.info(f"✅ Built {len(self.triangular_paths)} triangular paths")
    
    def _pair_exists(self, pair: str, pair_lookup: Dict[str, str]) -> bool:
        """Check if a trading pair exists (in either direction)"""
        base, quote = pair.split('/')
        return f"{base}/{quote}" in self.trading_pairs or f"{quote}/{base}" in self.trading_pairs
    
    async def start_websocket_stream(self):
        """Start Binance WebSocket stream for real-time price updates"""
        websocket_url = "wss://stream.binance.com:9443/ws/!ticker@arr"
        
        logger.info("🌐 Connecting to Binance WebSocket stream...")
        logger.info(f"   URL: {websocket_url}")
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries and not self.running:
            try:
                async with websockets.connect(websocket_url) as websocket:
                    self.websocket = websocket
                    self.running = True
                    logger.info("✅ Connected to Binance WebSocket stream")
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    
                    async for message in websocket:
                        try:
                            await self._handle_websocket_message(message)
                        except Exception as e:
                            logger.error(f"Error handling WebSocket message: {e}")
                            
            except Exception as e:
                retry_count += 1
                logger.error(f"WebSocket connection failed (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)  # Exponential backoff, max 30s
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max WebSocket retry attempts reached")
                    break
        
        self.running = False
        logger.info("WebSocket stream ended")
    
    async def _handle_websocket_message(self, message: str):
        """Handle incoming WebSocket ticker data"""
        try:
            data = json.loads(message)
            
            # Handle array of ticker data
            if isinstance(data, list):
                updates_processed = 0
                
                for ticker in data:
                    if self._update_price_map(ticker):
                        updates_processed += 1
                
                if updates_processed > 0:
                    self.last_update_time = time.time()
                    
                    # Scan for opportunities every 100 updates or every 5 seconds
                    if updates_processed >= 100 or time.time() - getattr(self, '_last_scan_time', 0) >= 5:
                        await self._scan_opportunities()
                        self._last_scan_time = time.time()
            
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _update_price_map(self, ticker: Dict[str, Any]) -> bool:
        """Update price map with new ticker data"""
        try:
            symbol = ticker.get('s', '')  # Symbol like 'BTCUSDT'
            bid_price = float(ticker.get('b', 0))  # Best bid price
            ask_price = float(ticker.get('a', 0))  # Best ask price
            
            if symbol and bid_price > 0 and ask_price > 0:
                # Convert BTCUSDT to BTC/USDT format
                formatted_symbol = self._format_symbol(symbol)
                
                if formatted_symbol:
                    self.price_map[formatted_symbol] = {
                        'bid': bid_price,
                        'ask': ask_price,
                        'timestamp': time.time()
                    }
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating price map: {e}")
            return False
    
    def _format_symbol(self, raw_symbol: str) -> Optional[str]:
        """Convert raw symbol (BTCUSDT) to formatted pair (BTC/USDT)"""
        # Common quote currencies in order of preference
        quote_currencies = ['USDT', 'USDC', 'BUSD', 'BTC', 'ETH', 'BNB']
        
        for quote in quote_currencies:
            if raw_symbol.endswith(quote):
                base = raw_symbol[:-len(quote)]
                formatted = f"{base}/{quote}"
                
                # Only return if this pair is in our trading pairs
                if formatted in self.trading_pairs:
                    return formatted
        
        return None
    
    async def _scan_opportunities(self):
        """Scan for triangular arbitrage opportunities"""
        if len(self.price_map) < 100:  # Need sufficient price data
            return
        
        opportunities = []
        paths_scanned = 0
        
        for base, intermediate, quote in self.triangular_paths:
            try:
                opportunity = self._calculate_triangle_profit(base, intermediate, quote)
                if opportunity and opportunity.profit_percentage >= self.min_profit_pct:
                    opportunities.append(opportunity)
                    self.opportunities_found += 1
                
                paths_scanned += 1
                
            except Exception as e:
                logger.debug(f"Error calculating triangle {base}-{intermediate}-{quote}: {e}")
        
        if opportunities:
            # Sort by profit percentage
            opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
            
            # Store current opportunities for integration
            self.current_opportunities = opportunities[:5]  # Keep top 5
            
            logger.info(f"💎 Found {len(opportunities)} profitable opportunities!")
            
            # Display top opportunities
            for i, opp in enumerate(opportunities[:5]):
                logger.info(f"   {i+1}. {opp}")
            
            # Emit opportunities (can be extended for WebSocket/API)
            await self._emit_opportunities(opportunities)
        
        if paths_scanned > 0:
            logger.debug(f"🔍 Scanned {paths_scanned} paths, found {len(opportunities)} profitable")
    
    def _calculate_triangle_profit(self, base: str, intermediate: str, quote: str) -> Optional[TriangleOpportunity]:
        """Calculate profit for a triangular arbitrage path"""
        try:
            # Define the three pairs needed
            pair1 = f"{base}/{intermediate}"
            pair2 = f"{intermediate}/{quote}"
            pair3 = f"{base}/{quote}"
            
            # Get price data (try both directions)
            price1 = self._get_pair_price(pair1, base, intermediate)
            price2 = self._get_pair_price(pair2, intermediate, quote)
            price3 = self._get_pair_price(pair3, base, quote)
            
            if not all([price1, price2, price3]):
                return None
            
            # Validate prices are reasonable and have proper spread
            for i, price_data in enumerate([price1, price2, price3]):
                bid = price_data['bid']
                ask = price_data['ask']
                
                if bid <= 0 or ask <= 0:
                    return None
                if bid >= ask:  # Bid should be less than ask
                    return None
                
                # Check spread is reasonable (not more than 5%)
                spread = (ask - bid) / bid
                if spread > 0.05:
                    return None
                    
                # Validate price ranges are reasonable
                if bid > 1000000 or ask > 1000000:
                    return None
            
            # Calculate triangular arbitrage with CORRECT math
            initial_amount = self.max_trade_amount
            
            # Step 1: base → intermediate
            if f"{base}/{intermediate}" in self.price_map:
                # Direct pair: sell base for intermediate
                amount_after_step1 = initial_amount * price1['bid']
                step1_action = f"SELL {initial_amount:.6f} {base} for {amount_after_step1:.6f} {intermediate}"
            elif f"{intermediate}/{base}" in self.price_map:
                # Inverted pair: buy intermediate with base
                amount_after_step1 = initial_amount / price1['ask']
                step1_action = f"BUY {amount_after_step1:.6f} {intermediate} with {initial_amount:.6f} {base}"
            else:
                return None
            
            # Validate step 1 result
            if amount_after_step1 <= 0 or amount_after_step1 > initial_amount * 1000:
                return None
            
            # Step 2: intermediate → quote
            if f"{intermediate}/{quote}" in self.price_map:
                # Direct pair: sell intermediate for quote
                amount_after_step2 = amount_after_step1 * price2['bid']
                step2_action = f"SELL {amount_after_step1:.6f} {intermediate} for {amount_after_step2:.6f} {quote}"
            elif f"{quote}/{intermediate}" in self.price_map:
                # Inverted pair: buy quote with intermediate
                amount_after_step2 = amount_after_step1 / price2['ask']
                step2_action = f"BUY {amount_after_step2:.6f} {quote} with {amount_after_step1:.6f} {intermediate}"
            else:
                return None
            
            # Validate step 2 result
            if amount_after_step2 <= 0 or amount_after_step2 > amount_after_step1 * 1000:
                return None
            
            # Step 3: quote → base (complete the triangle)
            if f"{quote}/{base}" in self.price_map:
                # Direct pair: sell quote for base
                final_amount = amount_after_step2 * price3['bid']
                step3_action = f"SELL {amount_after_step2:.6f} {quote} for {final_amount:.6f} {base}"
            elif f"{base}/{quote}" in self.price_map:
                # Inverted pair: buy base with quote
                final_amount = amount_after_step2 / price3['ask']
                step3_action = f"BUY {final_amount:.6f} {base} with {amount_after_step2:.6f} {quote}"
            else:
                return None
            
            # Validate final result
            if final_amount <= 0 or final_amount > initial_amount * 10:
                return None
            
            # Calculate profit
            gross_profit = final_amount - initial_amount
            gross_profit_pct = (gross_profit / initial_amount) * 100
            
            # Apply realistic trading costs (conservative)
            total_costs_pct = 0.3  # 0.3% total costs (0.1% per trade)
            trading_fees = initial_amount * (total_costs_pct / 100)
            net_profit = gross_profit - trading_fees
            net_profit_pct = (net_profit / initial_amount) * 100
            
            # Only return realistic opportunities
            if (net_profit_pct >= self.min_profit_pct and 
                net_profit_pct <= 5.0 and  # Max 5% profit (realistic)
                abs(gross_profit_pct) <= 100.0 and  # Sanity check
                final_amount > 0 and final_amount < initial_amount * 2):  # Realistic final amount
                
                return TriangleOpportunity(
                    path=[base, intermediate, quote],  # 3 currencies only
                    pairs=[pair1, pair2, pair3],
                    profit_percentage=net_profit_pct,
                    profit_amount=net_profit,
                    initial_amount=initial_amount,
                    steps=[
                        {'action': step1_action, 'amount_out': amount_after_step1},
                        {'action': step2_action, 'amount_out': amount_after_step2},
                        {'action': step3_action, 'amount_out': final_amount}
                    ],
                    timestamp=datetime.now()
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Error calculating triangle {base}-{intermediate}-{quote}: {e}")
            return None
    
    def _get_pair_price(self, pair: str, base: str, quote: str) -> Optional[Dict[str, float]]:
        """Get price data for a pair (try both directions)"""
        # Try direct pair
        if pair in self.price_map:
            price_data = self.price_map[pair]
            # Validate price data
            if (price_data.get('bid', 0) > 0 and 
                price_data.get('ask', 0) > 0 and
                price_data['bid'] <= price_data['ask'] and
                price_data['bid'] < 1000000):  # Reasonable price limit
                return price_data
        
        # Try reverse pair
        reverse_pair = f"{quote}/{base}"
        if reverse_pair in self.price_map:
            reverse_price = self.price_map[reverse_pair]
            # Validate and return inverted prices
            if (reverse_price.get('bid', 0) > 0 and 
                reverse_price.get('ask', 0) > 0 and
                reverse_price['bid'] <= reverse_price['ask']):
                try:
                    inverted_bid = 1 / reverse_price['ask']
                    inverted_ask = 1 / reverse_price['bid']
                    # Ensure inverted prices are reasonable
                    if inverted_bid > 0 and inverted_ask > 0 and inverted_bid <= inverted_ask:
                        return {
                            'bid': inverted_bid,
                            'ask': inverted_ask,
                            'timestamp': reverse_price['timestamp']
                        }
                except (ZeroDivisionError, OverflowError):
                    pass
        
        return None
    
    async def _emit_opportunities(self, opportunities: List[TriangleOpportunity]):
        """Emit opportunities (extend this for WebSocket/API integration)"""
        # For now, just log detailed information
        logger.info("📡 Emitting opportunities...")
        
        for opp in opportunities[:3]:  # Show top 3
            logger.info(f"🎯 PROFITABLE: {opp}")
            logger.info(f"   Steps:")
            for i, step in enumerate(opp.steps, 1):
                logger.info(f"     {i}. {step['action']}")
            logger.info(f"   Net Profit: ${opp.profit_amount:.2f} ({opp.profit_percentage:.4f}%)")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            'running': self.running,
            'trading_pairs': len(self.trading_pairs),
            'triangular_paths': len(self.triangular_paths),
            'price_updates': len(self.price_map),
            'opportunities_found': self.opportunities_found,
            'last_update': self.last_update_time
        }

async def main():
    """Main function for testing the real-time detector"""
    detector = RealtimeArbitrageDetector(min_profit_pct=0.1, max_trade_amount=100.0)
    
    # Initialize
    if not await detector.initialize():
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
    print("🚀 Real-Time Triangular Arbitrage Detector")
    print("=" * 50)
    asyncio.run(main())