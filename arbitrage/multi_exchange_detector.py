#!/usr/bin/env python3
"""
LIVE TRADING Triangular Arbitrage Detector - Generates REAL profitable opportunities
"""

import asyncio
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MultiExchangeDetector')

# Major currencies for triangular arbitrage
MAJOR_CURRENCIES = {'BTC', 'ETH', 'USDT', 'BNB', 'USDC', 'BUSD', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'SOL', 'MATIC', 'AVAX'}

@dataclass
class ArbitrageResult:
    exchange: str
    triangle_path: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float
    net_profit_percent: float = 0.0
    min_profit_threshold: float = 0.05
    
    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable above threshold."""
        return self.net_profit_percent > self.min_profit_threshold and self.profit_percentage > 0

class MultiExchangeDetector:
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        
        # Configuration - LOWER thresholds for more opportunities
        self.min_profit_pct = max(0.01, float(config.get('min_profit_percentage', 0.05)))  # Minimum 0.01%
        self.max_trade_amount = float(config.get('max_trade_amount', 100))
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}
        
        logger.info(f"🎯 LIVE TRADING Detector initialized - Min Profit: {self.min_profit_pct}%, Max Trade: ${self.max_trade_amount}")

    async def initialize(self):
        """Initialize triangle detection for all exchanges"""
        logger.info("🚀 Initializing LIVE TRADING multi-exchange triangle detector...")
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = list(ex.trading_pairs.keys())
                logger.info(f"Processing {len(pairs)} pairs for {ex_name}")
                
                # Build REAL triangles with existing pairs
                triangles = self._build_real_triangles(pairs, ex_name)
                self.triangle_paths[ex_name] = triangles
                
                logger.info(f"✅ Built {len(triangles)} REAL triangles for {ex_name}")
                if triangles:
                    sample = " → ".join(triangles[0][:3])
                    logger.info(f"Sample triangle: {sample}")
                    
            except Exception as e:
                logger.error(f"Error building triangles for {ex_name}: {str(e)}", exc_info=True)
                self.triangle_paths[ex_name] = []
        
        total = sum(len(t) for t in self.triangle_paths.values())
        logger.info(f"🎯 Total REAL triangles across all exchanges: {total}")

    def _build_real_triangles(self, pairs: List[str], exchange_name: str) -> List[List[str]]:
        """Build REAL triangles using only existing trading pairs"""
        logger.info(f"🔧 Building REAL triangles from {len(pairs)} trading pairs on {exchange_name}...")
        
        # Parse existing pairs
        existing_pairs = set(pairs)
        currencies = set()
        
        for pair in pairs:
            if '/' in pair:
                base, quote = pair.split('/')
                # Add all currencies, not just major ones
                currencies.add(base)
                currencies.add(quote)
        
        # Filter to focus on major currencies for better opportunities
        major_currencies_found = currencies.intersection(MAJOR_CURRENCIES)
        logger.info(f"Found {len(currencies)} total currencies, {len(major_currencies_found)} major: {sorted(major_currencies_found)}")
        
        # Generate REAL triangular paths
        triangles = []
        
        # Build triangles dynamically from available currencies
        stable_coins = ['USDT', 'USDC', 'BUSD']
        major_bases = ['BTC', 'ETH', 'BNB']
        
        # Find available stable coins and major bases
        available_stables = [c for c in stable_coins if c in major_currencies_found]
        available_bases = [c for c in major_bases if c in major_currencies_found]
        available_alts = [c for c in major_currencies_found if c not in stable_coins and c not in major_bases]
        
        logger.info(f"Available: {len(available_stables)} stables, {len(available_bases)} bases, {len(available_alts)} alts")
        
        # Generate triangle patterns
        patterns_to_check = []
        
        # Base -> Alt -> Stable triangles
        for base in available_bases:
            for alt in available_alts[:10]:  # Limit to top 10 alts
                for stable in available_stables:
                    patterns_to_check.append((base, alt, stable))
        
        # Base -> Base -> Stable triangles
        for base1 in available_bases:
            for base2 in available_bases:
                if base1 != base2:
                    for stable in available_stables:
                        patterns_to_check.append((base1, base2, stable))
        
        logger.info(f"Checking {len(patterns_to_check)} potential triangle patterns...")
        
        for a, b, c in patterns_to_check:
            if a in major_currencies_found and b in major_currencies_found and c in major_currencies_found:
                # Check if all required pairs exist
                pair1 = f"{a}/{b}"
                pair2 = f"{b}/{c}"
                pair3 = f"{a}/{c}"
                
                if pair1 in existing_pairs and pair2 in existing_pairs and pair3 in existing_pairs:
                    triangle = [a, b, c, a]  # Complete cycle
                    triangles.append(triangle)
                    logger.info(f"✅ Valid triangle: {a} → {b} → {c} → {a} (pairs: {pair1}, {pair2}, {pair3})")
        
        # Add reverse patterns for more opportunities  
        original_count = len(triangles)
        for a, b, c in patterns_to_check:
            if a in major_currencies_found and b in major_currencies_found and c in major_currencies_found:
                # Reverse pattern: A → C → B → A
                pair1 = f"{a}/{c}"
                pair2 = f"{c}/{b}"
                pair3 = f"{a}/{b}"
                
                if pair1 in existing_pairs and pair2 in existing_pairs and pair3 in existing_pairs:
                    triangle = [a, c, b, a]  # Reverse cycle
                    if triangle not in triangles:
                        triangles.append(triangle)
                        logger.info(f"✅ Valid reverse triangle: {a} → {c} → {b} → {a} (pairs: {pair1}, {pair2}, {pair3})")
        
        logger.info(f"🎯 Generated {len(triangles)} REAL triangles ({original_count} forward, {len(triangles)-original_count} reverse)")
        return triangles[:100]  # Limit to top 100 for performance

    async def scan_all_opportunities(self) -> List[ArbitrageResult]:
        """Scan all exchanges for REAL profitable arbitrage opportunities"""
        all_results = []
        logger.info("🔍 Starting LIVE TRADING scan for opportunities...")

        for ex_name, triangles in self.triangle_paths.items():
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex or not triangles:
                logger.info(f"Skipping {ex_name}: no exchange or triangles")
                continue
            
            try:
                results = await self._scan_exchange_triangles(ex, triangles)
                all_results.extend(results)
                logger.info(f"💰 Found {len(results)} REAL opportunities on {ex_name}")
            except Exception as e:
                logger.error(f"Error scanning {ex_name}: {str(e)}", exc_info=True)

        # Sort by profit and prepare for UI
        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Show ALL opportunities above minimum threshold
        profitable_results = [
            result for result in all_results 
            if result.profit_percentage >= self.min_profit_pct
        ]
        
        logger.info(f"💎 Found {len(all_results)} total opportunities, {len(profitable_results)} above {self.min_profit_pct}% threshold")
        
        # Always broadcast opportunities
        await self._broadcast_opportunities(profitable_results)
        
        return profitable_results

    async def _scan_exchange_triangles(self, ex, triangles: List[List[str]]) -> List[ArbitrageResult]:
        """Scan triangles for REAL profitable opportunities"""
        results = []
        
        # Get REAL ticker data
        ticker = await self._get_ticker_data(ex)
        if not ticker:
            logger.warning(f"No ticker data for {ex.name}")
            return []

        logger.info(f"🔍 Scanning {len(triangles)} REAL triangles for {ex.name}")
        
        for i, path in enumerate(triangles):
            a, b, c, _ = path
            try:
                profit = await self._calculate_real_triangle_profit(ex, ticker, a, b, c)
                if profit and profit >= self.min_profit_pct:
                    result = ArbitrageResult(
                        exchange=ex.name,
                        triangle_path=path,
                        profit_percentage=profit,
                        profit_amount=(self.max_trade_amount * profit / 100),
                        initial_amount=self.max_trade_amount,
                        net_profit_percent=profit,
                        min_profit_threshold=self.min_profit_pct
                    )
                    results.append(result)
                    logger.info(f"💰 PROFITABLE: {a}→{b}→{c} = {profit:.4f}% profit")
                else:
                    logger.debug(f"Skipped {a}→{b}→{c}: {profit:.4f}% below {self.min_profit_pct}% threshold")
            except Exception as e:
                logger.debug(f"Skipping triangle {a}-{b}-{c}: {str(e)}")
        
        logger.info(f"✅ Found {len(results)} 🔴 LIVE profitable opportunities on {ex.name}")
        return results

    async def _calculate_real_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate REAL profit percentage using live market data"""
        try:
            # Build pair names
            pair1 = f"{a}/{b}"  # A→B
            pair2 = f"{b}/{c}"  # B→C  
            pair3 = f"{a}/{c}"  # A→C (for closing the triangle)

            logger.debug(f"🧮 Calculating REAL profit for {a}→{b}→{c} using pairs: {pair1}, {pair2}, {pair3}")
            
            # Get REAL prices from live market data
            if pair1 not in ticker or pair2 not in ticker or pair3 not in ticker:
                logger.debug(f"Missing price data: {pair1} in ticker: {pair1 in ticker}, {pair2} in ticker: {pair2 in ticker}, {pair3} in ticker: {pair3 in ticker}")
                return 0.0
            
            # Validate price data
            t1, t2, t3 = ticker[pair1], ticker[pair2], ticker[pair3]
            if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
                logger.debug(f"Invalid price data for {a}-{b}-{c}")
                return 0.0
            
            # Extract and validate prices
            price1 = float(t1['bid'])  # A/B bid (sell A for B)
            price2 = float(t2['bid'])  # B/C bid (sell B for C)
            price3 = float(t3['ask'])  # A/C ask (buy A with C)
            
            if price1 <= 0 or price2 <= 0 or price3 <= 0:
                logger.debug(f"Invalid prices: {price1}, {price2}, {price3}")
                return 0.0
            
            # CORRECTED ARBITRAGE CALCULATION
            start_amount = self.max_trade_amount
            
            # Step 1: A → B (sell A for B)
            # If we have 100 A and A/B = 0.5, we get 100 * 0.5 = 50 B
            amount_after_step1 = start_amount * price1
            logger.debug(f"Step 1: {start_amount:.6f} {a} → {amount_after_step1:.6f} {b} (price: {price1:.8f})")
            
            # Step 2: B → C (sell B for C)
            # If we have 50 B and B/C = 2000, we get 50 * 2000 = 100000 C
            amount_after_step2 = amount_after_step1 * price2
            logger.debug(f"Step 2: {amount_after_step1:.6f} {b} → {amount_after_step2:.6f} {c} (price: {price2:.8f})")
            
            # Step 3: C → A (buy A with C)
            # If we have 100000 C and A/C = 1000, we can buy 100000 / 1000 = 100 A
            final_amount = amount_after_step2 / price3
            logger.debug(f"Step 3: {amount_after_step2:.6f} {c} → {final_amount:.6f} {a} (price: {price3:.8f})")
            
            # Calculate profit percentage
            gross_profit = final_amount - start_amount
            profit_pct = (gross_profit / start_amount) * 100
            
            logger.debug(f"Calculation: {start_amount:.6f} {a} → {final_amount:.6f} {a} = {profit_pct:.4f}% profit")
            
            # SANITY CHECK: Cap unrealistic profits
            if profit_pct > 3.0:
                logger.warning(f"⚠️ Unrealistic profit detected, skipping: {profit_pct:.4f}% for {a}→{b}→{c}")
                return 0.0
            
            if profit_pct < -50.0:
                logger.warning(f"⚠️ Unrealistic loss detected, skipping: {profit_pct:.4f}% for {a}→{b}→{c}")
                return 0.0
            
            # Apply REAL trading fees (0.1% per trade = 0.3% total for 3 trades) 
            # Add slippage estimate (0.05% per trade = 0.15% total)
            total_costs = 0.3 + 0.15  # 0.45% total costs
            net_profit_pct = profit_pct - total_costs
            
            # Log detailed calculation for debugging
            logger.debug(f"Triangle {a}→{b}→{c}: Start={start_amount:.6f}, Final={final_amount:.6f}, "
                        f"Gross={profit_pct:.4f}%, Net={net_profit_pct:.4f}% (after {total_costs}% costs)")
            
            if net_profit_pct > self.min_profit_pct:
                logger.info(f"💎 PROFITABLE: {a}→{b}→{c} = {profit_pct:.4f}% gross, {net_profit_pct:.4f}% net")
            else:
                logger.debug(f"Opportunity skipped: {a}→{b}→{c} profit {net_profit_pct:.4f}% below threshold {self.min_profit_pct}%")
            
            return net_profit_pct
            
        except Exception as e:
            logger.error(f"Calculation failed for {a}-{b}-{c}: {str(e)}", exc_info=True)
            return 0.0

    async def _get_ticker_data(self, ex):
        """Get ticker data with smart caching"""
        current_time = asyncio.get_event_loop().time()
        last_fetch = self._last_ticker_time.get(ex.name, 0)
        
        # Use 5-second cache for faster updates
        if current_time - last_fetch < 5:
            ticker = self._last_tickers.get(ex.name, {})
            if ticker:
                logger.debug(f"Using cached tickers for {ex.name}")
                return ticker

        ticker = await self._safe_fetch_tickers(ex)
        if ticker:
            self._last_tickers[ex.name] = ticker
            self._last_ticker_time[ex.name] = current_time
        
        return ticker

    async def _safe_fetch_tickers(self, ex):
        """Fetch tickers with rate limiting protection"""
        try:
            await asyncio.sleep(0.2)  # Rate limiting
            tickers = await ex.fetch_tickers()
            logger.info(f"📊 Fetched {len(tickers)} 🔴 LIVE tickers from {ex.name}")
            return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers from {ex.name}: {str(e)}")
            return self._last_tickers.get(ex.name, {})

    async def _broadcast_opportunities(self, opportunities: List[ArbitrageResult]):
        """Format and broadcast REAL opportunities to UI"""
        payload = []
        
        for opp in opportunities:
            # Ensure we have valid profit data
            if not hasattr(opp, 'is_profitable') or not opp.is_profitable:
                logger.debug(f"Skipping non-profitable opportunity: {opp.profit_percentage:.4f}%")
                continue
                
            payload.append({
                'id': f"live_{int(datetime.now().timestamp()*1000)}_{len(payload)}",
                'exchange': opp.exchange,
                'trianglePath': " → ".join(opp.triangle_path[:3]),
                'profitPercentage': round(opp.profit_percentage, 4),
                'profitAmount': round(opp.profit_amount, 6),
                'volume': opp.initial_amount,
                'status': 'detected',
                'dataType': '🔴_LIVE_MARKET_DATA',
                'timestamp': datetime.now().isoformat()
            })
        
        logger.info(f"📡 Broadcasting {len(payload)} 🔴 LIVE opportunities to UI")
        
        # Broadcast via WebSocket
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                if hasattr(self.websocket_manager, 'broadcast_sync'):
                    # Use sync broadcast for GUI integration
                    self.websocket_manager.broadcast_sync('opportunities_update', payload)
                else:
                    # Use async broadcast for web interface
                    await self.websocket_manager.broadcast('opportunities_update', payload)
                logger.info("✅ Successfully broadcasted 🔴 LIVE opportunities to UI")
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
        else:
            logger.warning(f"⚠️ WebSocket manager not available for broadcasting")
            # Still log opportunities for debugging
            for opp in payload[:5]:  # Show first 5
                logger.info(f"💎 Opportunity: {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']}%")


if __name__ == "__main__":
    print("This module should be run through the web server interface")