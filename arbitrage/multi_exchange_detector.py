#!/usr/bin/env python3
"""
LIVE TRADING Triangular Arbitrage Detector - Fixed for Real Binance Pairs
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
MAJOR_CURRENCIES = {'BTC', 'ETH', 'USDT', 'BNB', 'USDC', 'BUSD', 'ADA', 'DOT', 'LINK', 'LTC', 'XRP', 'SOL', 'MATIC', 'AVAX', 'DOGE', 'TRX', 'ATOM', 'FIL', 'UNI'}

@dataclass
class ArbitrageResult:
    exchange: str
    triangle_path: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float
    net_profit_percent: float = 0.0
    min_profit_threshold: float = 0.0001
    
    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable above threshold."""
        return self.net_profit_percent > self.min_profit_threshold and self.profit_percentage > 0

class MultiExchangeDetector:
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        
        # OPTIMIZED Configuration for PROFIT GENERATION
        self.min_profit_pct = max(0.5, float(config.get('min_profit_percentage', 0.5)))    # 0.5% minimum for profitability
        self.max_trade_amount = min(100, float(config.get('max_trade_amount', 100)))       # $100 maximum per trade
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}
        
        # Prevent duplicate logging by using a single logger instance
        self._logged_messages = set()
        
        logger.info(f"💰 PROFIT-OPTIMIZED Detector initialized - Min Profit: {self.min_profit_pct}%, Max Trade: ${self.max_trade_amount}")
        logger.info(f"🎯 Target: Generate consistent profits with ${self.max_trade_amount} trades at {self.min_profit_pct}%+ margins")

    async def initialize(self):
        """Initialize triangle detection for all exchanges"""
        logger.info("🚀 Initializing LIVE TRADING multi-exchange triangle detector...")
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = list(ex.trading_pairs.keys())
                logger.info(f"Processing {len(pairs)} pairs for {ex_name}")
                
                # Build REAL triangles with existing pairs
                triangles = self._build_real_triangles_from_available_pairs(pairs, ex_name)
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

    def _build_real_triangles_from_available_pairs(self, pairs: List[str], exchange_name: str) -> List[List[str]]:
        """Build triangles using ONLY the actual available pairs from Binance"""
        logger.info(f"💎 Building triangles from {len(pairs)} REAL Binance pairs...")
        
        # Parse all available pairs
        available_pairs = set(pairs)
        currencies = set()
        pair_map = {}
        
        for pair in pairs:
            if '/' in pair:
                base, quote = pair.split('/')
                currencies.add(base)
                currencies.add(quote)
                pair_map[pair] = True
        
        logger.info(f"Found {len(currencies)} currencies from {len(pairs)} pairs")
        
        # Focus on major currencies that actually exist
        major_found = currencies.intersection(MAJOR_CURRENCIES)
        logger.info(f"Major currencies available: {sorted(major_found)}")
        
        # Build triangles using ONLY available pairs
        triangles = []
        
        # Strategy: Find all possible 3-currency combinations where all 3 pairs exist
        major_list = list(major_found)
        
        for i, curr_a in enumerate(major_list):
            for j, curr_b in enumerate(major_list):
                if i >= j:  # Avoid duplicates
                    continue
                for k, curr_c in enumerate(major_list):
                    if k >= j or k == i:  # Avoid duplicates and self
                        continue
                    
                    # Check all possible pair combinations for this triangle
                    possible_pairs = [
                        f"{curr_a}/{curr_b}", f"{curr_b}/{curr_a}",
                        f"{curr_b}/{curr_c}", f"{curr_c}/{curr_b}",
                        f"{curr_a}/{curr_c}", f"{curr_c}/{curr_a}"
                    ]
                    
                    # Find which pairs actually exist
                    existing_pairs = [p for p in possible_pairs if p in available_pairs]
                    
                    if len(existing_pairs) >= 3:
                        # Try to build a valid triangle path
                        triangle = self._try_build_triangle_path(curr_a, curr_b, curr_c, available_pairs)
                        if triangle:
                            triangles.append(triangle)
                            if len(triangles) <= 20:  # Log first 20
                                logger.info(f"💰 Triangle: {' → '.join(triangle[:3])}")
        
        # Add some specific high-volume triangles if they exist
        specific_triangles = [
            # USDT-based triangles (most liquid)
            ('BTC', 'ETH', 'USDT'),
            ('BTC', 'BNB', 'USDT'),
            ('ETH', 'BNB', 'USDT'),
            ('BTC', 'ADA', 'USDT'),
            ('ETH', 'ADA', 'USDT'),
            ('BTC', 'SOL', 'USDT'),
            ('ETH', 'SOL', 'USDT'),
            ('BNB', 'ADA', 'USDT'),
            ('BNB', 'SOL', 'USDT'),
            
            # USDC-based triangles
            ('BTC', 'ETH', 'USDC'),
            ('BTC', 'BNB', 'USDC'),
            ('ETH', 'BNB', 'USDC'),
            
            # BUSD-based triangles (if available)
            ('BTC', 'ETH', 'BUSD'),
            ('BTC', 'BNB', 'BUSD'),
            ('ETH', 'BNB', 'BUSD'),
        ]
        
        for a, b, c in specific_triangles:
            if a in currencies and b in currencies and c in currencies:
                triangle = self._try_build_triangle_path(a, b, c, available_pairs)
                if triangle and triangle not in triangles:
                    triangles.append(triangle)
                    logger.info(f"💎 Added specific triangle: {' → '.join(triangle[:3])}")
        
        logger.info(f"✅ Built {len(triangles)} total triangles for {exchange_name}")
        return triangles if triangles else []

    def _try_build_triangle_path(self, a: str, b: str, c: str, available_pairs: set) -> List[str]:
        """Try to build a valid triangle path using available pairs"""
        # Try different path combinations
        paths_to_try = [
            # A → B → C → A
            [f"{a}/{b}", f"{b}/{c}", f"{c}/{a}"],
            [f"{b}/{a}", f"{b}/{c}", f"{c}/{a}"],
            [f"{a}/{b}", f"{c}/{b}", f"{c}/{a}"],
            [f"{b}/{a}", f"{c}/{b}", f"{c}/{a}"],
            
            # A → C → B → A
            [f"{a}/{c}", f"{c}/{b}", f"{b}/{a}"],
            [f"{c}/{a}", f"{c}/{b}", f"{b}/{a}"],
            [f"{a}/{c}", f"{b}/{c}", f"{b}/{a}"],
            [f"{c}/{a}", f"{b}/{c}", f"{b}/{a}"],
        ]
        
        for path_pairs in paths_to_try:
            if all(pair in available_pairs for pair in path_pairs):
                # Return the currency path
                return [a, b, c, a]
        
        return None

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
        """Calculate REAL profit percentage using live market data with flexible pair matching"""
        try:
            # Try all possible pair combinations to find what actually exists
            possible_combinations = [
                # Path 1: A→B→C→A
                {
                    'pairs': [f"{a}/{b}", f"{b}/{c}", f"{a}/{c}"],
                    'operations': ['sell_a_for_b', 'sell_b_for_c', 'buy_a_with_c']
                },
                # Path 2: A→C→B→A  
                {
                    'pairs': [f"{a}/{c}", f"{c}/{b}", f"{a}/{b}"],
                    'operations': ['sell_a_for_c', 'sell_c_for_b', 'buy_a_with_b']
                },
                # Path 3: Using inverted pairs
                {
                    'pairs': [f"{b}/{a}", f"{b}/{c}", f"{a}/{c}"],
                    'operations': ['buy_b_with_a', 'sell_b_for_c', 'buy_a_with_c']
                },
                # Path 4: Another inverted combination
                {
                    'pairs': [f"{a}/{b}", f"{c}/{b}", f"{a}/{c}"],
                    'operations': ['sell_a_for_b', 'buy_b_with_c', 'sell_a_for_c']
                }
            ]
            
            best_profit = -999.0
            
            for combo in possible_combinations:
                pairs = combo['pairs']
                operations = combo['operations']
                
                # Check if all pairs exist in ticker data
                if all(pair in ticker for pair in pairs):
                    try:
                        profit = self._calculate_path_profit(ticker, pairs, operations, a, b, c)
                        if profit > best_profit:
                            best_profit = profit
                            logger.debug(f"Found better path for {a}-{b}-{c}: {profit:.6f}% using {pairs}")
                    except Exception as e:
                        logger.debug(f"Path calculation failed for {pairs}: {e}")
                        continue
            
            if best_profit > -999.0:
                return best_profit
            else:
                logger.debug(f"No valid paths found for triangle {a}-{b}-{c}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Calculation failed for {a}-{b}-{c}: {str(e)}", exc_info=True)
            return 0.0

    def _calculate_simple_triangle_profit(self, ticker, pairs, a, b, c) -> float:
        """Calculate profit for a triangle using simple A→B→C→A logic"""
        start_amount = self.max_trade_amount
        
        logger.debug(f"Calculating triangle: {a}→{b}→{c}→{a} using pairs: {pairs}")
        
        # Get price data
        t1, t2, t3 = ticker[pairs[0]], ticker[pairs[1]], ticker[pairs[2]]
        
        # Validate price data
        if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
            raise ValueError("Invalid price data")
        
        # Determine the correct prices based on pair direction
        pair1, pair2, pair3 = pairs[0], pairs[1], pairs[2]
        
        # Step 1: A → B
        if pair1 == f"{a}/{b}":
            # Sell A for B, use bid price
            price1 = float(t1['bid'])
            amount_after_step1 = start_amount * price1
        elif pair1 == f"{b}/{a}":
            # Buy B with A, use ask price (inverted)
            price1 = float(t1['ask'])
            amount_after_step1 = start_amount / price1
        else:
            raise ValueError(f"Invalid pair1: {pair1} for {a}→{b}")
        
        # Step 2: B → C
        if pair2 == f"{b}/{c}":
            # Sell B for C, use bid price
            price2 = float(t2['bid'])
            amount_after_step2 = amount_after_step1 * price2
        elif pair2 == f"{c}/{b}":
            # Buy C with B, use ask price (inverted)
            price2 = float(t2['ask'])
            amount_after_step2 = amount_after_step1 / price2
        else:
            raise ValueError(f"Invalid pair2: {pair2} for {b}→{c}")
        
        # Step 3: C → A
        if pair3 == f"{c}/{a}":
            # Sell C for A, use bid price
            price3 = float(t3['bid'])
            final_amount = amount_after_step2 * price3
        elif pair3 == f"{a}/{c}":
            # Buy A with C, use ask price (inverted)
            price3 = float(t3['ask'])
            final_amount = amount_after_step2 / price3
        else:
            raise ValueError(f"Invalid pair3: {pair3} for {c}→{a}")
        
        logger.debug(f"Triangle calculation: {start_amount:.6f} {a} → {amount_after_step1:.6f} {b} → {amount_after_step2:.6f} {c} → {final_amount:.6f} {a}")
        
        # Calculate profit
        gross_profit = final_amount - start_amount
        profit_pct = (gross_profit / start_amount) * 100
        
        # Apply realistic trading costs
        # Binance fees: 0.1% per trade (0.075% with BNB discount)
        # 3 trades = 0.225% total fees
        # Slippage: ~0.05% per trade = 0.15% total
        # Buffer for market movement: 0.1%
        total_costs = 0.225 + 0.15 + 0.1  # 0.475% total costs
        
        net_profit_pct = profit_pct - total_costs
        
        logger.debug(f"Path result: Start={start_amount:.6f}, Final={final_amount:.6f}, "
                    f"Gross={profit_pct:.6f}%, Net={net_profit_pct:.6f}% (after {total_costs}% costs)")
        
        return net_profit_pct

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
        
        if payload:
            logger.info(f"📡 Broadcasting {len(payload)} 🔴 LIVE opportunities to UI")
        
        # Broadcast via WebSocket
        if self.websocket_manager:
            try:
                if hasattr(self.websocket_manager, 'broadcast'):
                    await self.websocket_manager.broadcast('opportunities_update', payload)
                    if payload:
                        logger.info("✅ Successfully broadcasted opportunities to UI via WebSocket")
                elif hasattr(self.websocket_manager, 'broadcast_sync'):
                    self.websocket_manager.broadcast_sync('opportunities_update', payload)
                    if payload:
                        logger.info("✅ Successfully broadcasted opportunities to UI via sync WebSocket")
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
        else:
            logger.debug("ℹ️ [INFO] UI broadcast disabled in this run (no WebSocket manager)")
            # Still log opportunities for debugging
            for opp in payload[:5]:  # Show first 5
                logger.info(f"💎 Opportunity: {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']}%")

        # Only return profitable opportunities above 0.5% net profit
        profitable_opportunities = [opp for opp in opportunities if opp.net_profit_percent >= 0.5]
        return profitable_opportunities

if __name__ == "__main__":
    print("This module should be run through the web server interface")