#!/usr/bin/env python3
"""
Complete Triangular Arbitrage Detector for Binance
Handles all pair formats and properly calculates arbitrage opportunities
"""

import asyncio
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
logger = logging.getLogger('MultiExchangeDetector')

# Major currencies to consider for triangles
MAJOR_CURRENCIES = {'BTC', 'ETH', 'USDT', 'BNB', 'USDC'}

@dataclass
class ArbitrageResult:
    exchange: str
    triangle_path: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float

class MultiExchangeDetector:
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        
        # Configuration
        self.min_profit_pct = float(config.get('min_profit_percentage', 0.1))
        self.max_trade_amount = float(config.get('max_trade_amount', 100))
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}

    async def initialize(self):
        """Initialize triangle detection for all exchanges"""
        logger.info("Initializing multi-exchange triangle detector...")
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = list(ex.trading_pairs.keys())
                triangles = self._find_triangles(pairs, ex_name)
                self.triangle_paths[ex_name] = triangles
                
                logger.info(f"Built {len(triangles)} VALID triangles for {ex_name}")
                if triangles:
                    sample = " → ".join(triangles[0][:3])
                    logger.info(f"Sample triangle: {sample}")
            except Exception as e:
                logger.error(f"Error building triangles for {ex_name}: {str(e)}", exc_info=True)
                self.triangle_paths[ex_name] = []
        
        total = sum(len(t) for t in self.triangle_paths.values())
        logger.info(f"Total VALID triangles across all exchanges: {total}")

    def _find_triangles(self, pairs: List[str], exchange_name: str) -> List[List[str]]:
        """Generate valid triangular arbitrage paths with proper exchange-specific handling"""
        logger.info(f"Building triangles from {len(pairs)} trading pairs on {exchange_name}...")
        
        # Step 1: Build complete pair mapping and connection graph
        pair_graph = {}
        valid_pairs = set()
        
        for pair_str in pairs:
            base, quote = self._parse_pair(pair_str, exchange_name)
            if not base or not quote:
                continue
                
            valid_pairs.add((base, quote))
            pair_graph.setdefault(base, set()).add(quote)
            
            # For Binance, also check if inverse pair exists
            if exchange_name.lower() == 'binance':
                inverse_pair = f"{quote}{base}"
                if inverse_pair in pairs:
                    valid_pairs.add((quote, base))
                    pair_graph.setdefault(quote, set()).add(base)
        
        logger.info(f"Found {len(valid_pairs)} valid currency connections")
        
        # Step 2: Generate all possible triangles
        triangles = []
        currencies = sorted(MAJOR_CURRENCIES & set(pair_graph.keys()))
        
        for a in currencies:
            for b in pair_graph.get(a, set()):
                for c in pair_graph.get(b, set()):
                    # Check if we can complete the triangle (C→A or A→C)
                    if (c, a) in valid_pairs or (a, c) in valid_pairs:
                        triangles.append([a, b, c, a])
        
        logger.info(f"Generated {len(triangles)} valid triangles")
        return triangles

    def _parse_pair(self, pair_str: str, exchange_name: str) -> Tuple[str, str]:
        """Parse trading pair into base and quote currencies"""
        try:
            if exchange_name.lower() == 'binance':
                # Handle Binance format (BTCUSDT)
                for curr in MAJOR_CURRENCIES:
                    if pair_str.startswith(curr):
                        base = curr
                        quote = pair_str[len(curr):]
                        if quote in MAJOR_CURRENCIES:
                            return base, quote
                    elif pair_str.endswith(curr):
                        base = pair_str[:-len(curr)]
                        quote = curr
                        if base in MAJOR_CURRENCIES:
                            return base, quote
            else:
                # Handle standard format (BTC/USDT)
                if '/' in pair_str:
                    base, quote = pair_str.split('/')
                    if base in MAJOR_CURRENCIES and quote in MAJOR_CURRENCIES:
                        return base, quote
        except Exception:
            pass
        return None, None

    async def scan_all_opportunities(self) -> List[ArbitrageResult]:
        """Scan all exchanges for profitable arbitrage opportunities"""
        all_results = []
        logger.info("Starting scan for all opportunities...")

        for ex_name, triangles in self.triangle_paths.items():
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex or not triangles:
                continue
            
            try:
                results = await self._scan_exchange_triangles(ex, triangles)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error scanning {ex_name}: {str(e)}", exc_info=True)

        # Sort by profit and prepare UI payload
        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)
        await self._broadcast_opportunities(all_results)
        
        return all_results

    async def _scan_exchange_triangles(self, ex, triangles: List[List[str]]) -> List[ArbitrageResult]:
        """Scan triangles for a specific exchange"""
        results = []
        ticker = await self._get_ticker_data(ex)
        if not ticker:
            return results

        logger.info(f"Scanning {min(len(triangles), 100)} triangles for {ex.name}")
        
        for path in triangles[:100]:  # Limit to 100 triangles per scan
            a, b, c, _ = path
            try:
                profit = await self._calculate_triangle_profit(ex, ticker, a, b, c)
                if profit and profit >= self.min_profit_pct:
                    results.append(ArbitrageResult(
                        exchange=ex.name,
                        triangle_path=path,
                        profit_percentage=profit,
                        profit_amount=(self.max_trade_amount * profit / 100),
                        initial_amount=self.max_trade_amount
                    ))
            except Exception as e:
                logger.debug(f"Skipping triangle {a}-{b}-{c}: {str(e)}")
        
        return results

    async def _calculate_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate profit percentage for a specific triangle path"""
        # Get all required pairs
        p1 = f"{a}{b}" if ex.name.lower() == 'binance' else f"{a}/{b}"
        p2 = f"{b}{c}" if ex.name.lower() == 'binance' else f"{b}/{c}"
        p3_direct = f"{c}{a}" if ex.name.lower() == 'binance' else f"{c}/{a}"
        p3_inverse = f"{a}{c}" if ex.name.lower() == 'binance' else f"{a}/{c}"

        # Get prices for all legs
        _, ask1 = self._get_prices(ticker, p1)
        _, ask2 = self._get_prices(ticker, p2)
        
        # Calculate amount after first two legs
        amount = self.max_trade_amount / ask1  # A→B
        amount = amount / ask2  # B→C
        
        # Try direct return pair first
        if p3_direct in ticker:
            bid3, _ = self._get_prices(ticker, p3_direct)
            final_amount = amount * bid3  # C→A
        # Fall back to inverse pair
        elif p3_inverse in ticker:
            _, ask3 = self._get_prices(ticker, p3_inverse)
            final_amount = amount / ask3  # C→A via inverse
        else:
            raise ValueError("No valid return path")
        
        return ((final_amount - self.max_trade_amount) / self.max_trade_amount) * 100

    async def _get_ticker_data(self, ex):
        """Get ticker data with caching and rate limiting"""
        current_time = asyncio.get_event_loop().time()
        last_fetch = self._last_ticker_time.get(ex.name, 0)
        
        if current_time - last_fetch < 10:  # 10 second cache
            ticker = self._last_tickers.get(ex.name, {})
            logger.info(f"Using cached tickers for {ex.name}")
        else:
            ticker = await self._safe_fetch_tickers(ex)
            if ticker:
                self._last_tickers[ex.name] = ticker
                self._last_ticker_time[ex.name] = current_time
        
        return ticker

    async def _safe_fetch_tickers(self, ex):
        """Fetch tickers with error handling"""
        try:
            await asyncio.sleep(1)  # Rate limiting
            tickers = await ex.fetch_tickers()
            logger.info(f"Fetched {len(tickers)} fresh tickers from {ex.name}")
            return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers from {ex.name}: {str(e)}")
            return self._last_tickers.get(ex.name, {})

    def _get_prices(self, ticker, symbol):
        """Get bid/ask prices with validation"""
        t = ticker.get(symbol, {})
        bid = float(t.get('bid', 0))
        ask = float(t.get('ask', 0))
        if bid <= 0 or ask <= 0:
            raise ValueError(f"Invalid prices for {symbol}")
        return bid, ask

    async def _broadcast_opportunities(self, opportunities: List[ArbitrageResult]):
        """Format and broadcast opportunities to UI"""
        payload = []
        for opp in opportunities:
            if opp.profit_percentage >= self.min_profit_pct:
                payload.append({
                    'exchange': opp.exchange,
                    'path': " → ".join(opp.triangle_path[:3]),
                    'profit_pct': round(opp.profit_percentage, 4),
                    'profit_amount': round(opp.profit_amount, 8),  # More precision for crypto
                    'initial_amount': opp.initial_amount,
                    'timestamp': datetime.now().isoformat()
                })
        
        if hasattr(self.websocket_manager, 'broadcast'):
            await self.websocket_manager.broadcast('opportunities', payload)
        logger.info(f"Broadcasted {len(payload)} opportunities to UI")


if __name__ == "__main__":
    print("This module should be run through the web server interface")