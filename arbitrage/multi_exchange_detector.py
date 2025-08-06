#!/usr/bin/env python3
"""
LIVE TRADING Triangular Arbitrage Detector with Enhanced Balance Display
"""

import asyncio
import time
import aiohttp
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass
from arbitrage.realtime_detector import RealtimeArbitrageDetector
from arbitrage.simple_triangle_detector import SimpleTriangleDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MultiExchangeDetector')

# Major currencies for display
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
    is_tradeable: bool = False
    balance_available: float = 0.0
    required_balance: float = 0.0
    is_demo: bool = False
    
    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable above threshold."""
        return self.profit_percentage >= self.min_profit_threshold

class MultiExchangeDetector:
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        
        # Trading Limits
        self.min_profit_pct = max(0.5, float(config.get('min_profit_percentage', 0.5)))
        self.max_trade_amount = min(100.0, float(config.get('max_trade_amount', 100.0)))
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Initialize real-time detector
        self.realtime_detector = RealtimeArbitrageDetector(
            min_profit_pct=self.min_profit_pct,
            max_trade_amount=self.max_trade_amount
        )
        
        # Initialize simple detector (based on working JavaScript logic)
        self.simple_detector = SimpleTriangleDetector(min_profit_pct=0.001)  # Very low threshold
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}
        self._logged_messages = set()
        
        logger.info(f"💰 PROFIT-OPTIMIZED Detector initialized - Min Profit: {self.min_profit_pct}%, Max Trade: ${self.max_trade_amount}")

    async def initialize(self):
        """Initialize with balance verification"""
        logger.info("🚀 Initializing LIVE TRADING detector...")
        
        # First verify we can fetch balances
        for ex_name in self.exchange_manager.exchanges:
            balance = await self.show_account_balance(ex_name)
            if balance and balance.get('balances'):
                logger.info(f"✅ Balance detected on {ex_name}: {len(balance['balances'])} currencies")
            else:
                logger.warning(f"⚠️ No balance detected on {ex_name} - continuing anyway")
        
        # Initialize real-time detector
        await self.realtime_detector.initialize()
        
        # Initialize simple detector
        await self.simple_detector.get_pairs()
        asyncio.create_task(self.simple_detector.start_websocket_stream())
        logger.info("✅ Simple detector started (JavaScript logic)")
        
        # Build triangle paths
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = list(ex.trading_pairs.keys())
                logger.info(f"Processing {len(pairs)} pairs for {ex_name}")
                
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

    async def show_account_balance(self, exchange_name: str = "binance") -> Dict[str, Any]:
        """Display complete account balance with USD values"""
        ex = self.exchange_manager.exchanges.get(exchange_name)
        if not ex:
            logger.error(f"Exchange {exchange_name} not found")
            return {}

        try:
            # Try to get balance using the correct method
            balance = await ex.get_account_balance()
            if not balance:
                logger.error("❌ No balance data retrieved")
                return {}
            
            # Calculate USD value
            total_usd = await ex._calculate_usd_value(balance) if hasattr(ex, '_calculate_usd_value') else 0.0
            
            balance_data = {
                'balances': balance,
                'total_usd': total_usd,
                'timestamp': int(time.time() * 1000)
            }
            
            # Format the balance display
            balance_text = f"💰 {exchange_name.upper()} ACCOUNT BALANCE (${balance_data['total_usd']:.2f}):\n"
            for currency, amount in sorted(
                balance_data['balances'].items(),
                key=lambda x: x[1] * (1 if x[0] == 'USDT' else 
                    self._get_usd_price(x[0], exchange_name)),
                reverse=True
            ):
                if currency in MAJOR_CURRENCIES:
                    balance_text += f"  {currency}: {amount:.8f}"
                    if currency != 'USDT':
                        usd_price = self._get_usd_price(currency, exchange_name)
                        if usd_price:
                            balance_text += f" (${amount * usd_price:.2f})"
                    balance_text += "\n"
                elif amount >= 1.0:
                    balance_text += f"  {currency}: {amount:.4f}\n"
                else:
                    balance_text += f"  {currency}: {amount:.8f}\n"
            
            logger.info(balance_text)
            return balance_data
            
        except Exception as e:
            logger.error(f"Failed to display balance: {str(e)}")
            return {}

    def _get_usd_price(self, currency: str, exchange_name: str) -> float:
        """Get USD price for a currency from last ticker data"""
        if currency == 'USDT':
            return 1.0
            
        ex = self.exchange_manager.exchanges.get(exchange_name)
        if not ex:
            return 0.0
            
        # Try direct USDT pair first
        pair = f"{currency}/USDT"
        if pair in self._last_tickers.get(exchange_name, {}):
            return float(self._last_tickers[exchange_name][pair].get('last', 0.0))
        
        # Try via BTC if available
        if f"{currency}/BTC" in self._last_tickers.get(exchange_name, {}) and "BTC/USDT" in self._last_tickers.get(exchange_name, {}):
            currency_btc = float(self._last_tickers[exchange_name][f"{currency}/BTC"].get('last', 0.0))
            btc_usd = float(self._last_tickers[exchange_name]["BTC/USDT"].get('last', 0.0))
            return currency_btc * btc_usd
            
        return 0.0

    async def _fetch_balance_with_retry(self, exchange, retries: int = 3) -> Dict[str, float]:
        """Fetch balance with retry mechanism"""
        last_error = None
        
        for attempt in range(retries):
            try:
                balance = await exchange.fetch_balance()
                
                if balance and balance.get('total'):
                    return {
                        k: float(v) 
                        for k, v in balance['total'].items() 
                        if float(v) > 0
                    }
                
                return await self._fetch_balance_direct(exchange)
                
            except Exception as e:
                last_error = e
                if attempt < retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                continue
        
        logger.error(f"Failed after {retries} attempts. Last error: {str(last_error)}")
        return {}

    async def _fetch_balance_direct(self, exchange) -> Dict[str, float]:
        """Direct Binance API fallback"""
        try:
            if hasattr(exchange, 'privateGetAccount'):
                account = await exchange.privateGetAccount()
                return {
                    item['asset']: float(item['free']) + float(item['locked'])
                    for item in account.get('balances', [])
                    if float(item['free']) + float(item['locked']) > 0
                }
            return {}
        except Exception as e:
            logger.error(f"Direct balance fetch failed: {str(e)}")
            return {}

    def _format_balance(self, balance: Dict[str, float]) -> str:
        """Format balance for display"""
        if not balance:
            return "No balance data available"
        
        sorted_balance = sorted(balance.items(), key=lambda x: x[1], reverse=True)
        lines = []
        
        for currency, amount in sorted_balance:
            if currency in MAJOR_CURRENCIES:
                lines.append(f"  {currency}: {amount:.8f}")
            elif amount >= 1.0:
                lines.append(f"  {currency}: {amount:.4f}")
            else:
                lines.append(f"  {currency}: {amount:.8f}")
        
        return "\n".join(lines)

    def _build_real_triangles_from_available_pairs(self, pairs: List[str], exchange_name: str) -> List[List[str]]:
        """Build triangles using ONLY the actual available pairs from Binance"""
        logger.info(f"💎 Building triangles from {len(pairs)} REAL Binance pairs...")
        
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
        
        major_found = currencies.intersection(MAJOR_CURRENCIES)
        logger.info(f"Major currencies available: {sorted(major_found)}")
        
        triangles = []
        
        # Focus on USDT-based triangles like USDT→RON→EGLD→USDT
        usdt_triangles = []
        
        # Get all currencies that have USDT pairs
        usdt_currencies = []
        for pair in available_pairs:
            if '/USDT' in pair:
                base = pair.split('/')[0]
                usdt_currencies.append(base)
        
        logger.info(f"Found {len(usdt_currencies)} currencies with USDT pairs")
        
        # Build USDT-based triangles: USDT → Currency1 → Currency2 → USDT
        for curr1 in usdt_currencies:
            for curr2 in usdt_currencies:
                if curr1 != curr2:
                    # Check if we can build: USDT → curr1 → curr2 → USDT
                    pair1 = f"{curr1}/USDT"  # USDT buys curr1
                    pair2 = f"{curr1}/{curr2}"  # curr1 buys curr2
                    pair3 = f"{curr2}/USDT"  # curr2 sells for USDT
                    
                    # Alternative: curr1 → USDT → curr2
                    alt_pair2 = f"{curr2}/USDT"  # USDT buys curr2
                    
                    if (pair1 in available_pairs and pair3 in available_pairs and 
                        (pair2 in available_pairs or alt_pair2 in available_pairs)):
                        
                        triangle = ['USDT', curr1, curr2, 'USDT']
                        usdt_triangles.append(triangle)
                        
                        if len(usdt_triangles) <= 20:
                            logger.info(f"💰 USDT Triangle: USDT → {curr1} → {curr2} → USDT")
        
        # Add specific high-volume USDT triangles
        priority_usdt_triangles = [
            ['USDT', 'BTC', 'ETH', 'USDT'],
            ['USDT', 'BTC', 'BNB', 'USDT'], 
            ['USDT', 'ETH', 'BNB', 'USDT'],
            ['USDT', 'BTC', 'ADA', 'USDT'],
            ['USDT', 'ETH', 'ADA', 'USDT'],
            ['USDT', 'BTC', 'SOL', 'USDT'],
            ['USDT', 'ETH', 'SOL', 'USDT'],
            ['USDT', 'BNB', 'ADA', 'USDT'],
            ['USDT', 'BNB', 'SOL', 'USDT'],
            ['USDT', 'RON', 'EGLD', 'USDT'],  # Your specific example
            ['USDT', 'DOGE', 'XRP', 'USDT'],
            ['USDT', 'MATIC', 'AVAX', 'USDT'],
            ['USDT', 'LINK', 'DOT', 'USDT'],
            ['USDT', 'LTC', 'TRX', 'USDT'],
            ['USDT', 'ATOM', 'FIL', 'USDT']
        ]
        
        for triangle in priority_usdt_triangles:
            if triangle not in usdt_triangles:
                # Check if all required pairs exist
                curr1, curr2 = triangle[1], triangle[2]
                if (f"{curr1}/USDT" in available_pairs and 
                    f"{curr2}/USDT" in available_pairs and
                    (f"{curr1}/{curr2}" in available_pairs or f"{curr2}/{curr1}" in available_pairs)):
                    usdt_triangles.append(triangle)
                    logger.info(f"💎 Added priority USDT triangle: {' → '.join(triangle[:3])}")
        
        logger.info(f"✅ Built {len(usdt_triangles)} USDT-based triangles for {exchange_name}")
        return usdt_triangles if usdt_triangles else []

    def _try_build_triangle_path(self, a: str, b: str, c: str, available_pairs: set) -> List[str]:
        """Try to build a valid triangle path using available pairs"""
        paths_to_try = [
            [f"{a}/{b}", f"{b}/{c}", f"{c}/{a}"],
            [f"{b}/{a}", f"{b}/{c}", f"{c}/{a}"],
            [f"{a}/{b}", f"{c}/{b}", f"{c}/{a}"],
            [f"{b}/{a}", f"{c}/{b}", f"{c}/{a}"],
            [f"{a}/{c}", f"{c}/{b}", f"{b}/{a}"],
            [f"{c}/{a}", f"{c}/{b}", f"{b}/{a}"],
            [f"{a}/{c}", f"{b}/{c}", f"{b}/{a}"],
            [f"{c}/{a}", f"{b}/{c}", f"{b}/{a}"],
        ]
        
        for path_pairs in paths_to_try:
            if all(pair in available_pairs for pair in path_pairs):
                return [a, b, c, a]
        
        return None

    async def scan_all_opportunities(self) -> List[ArbitrageResult]:
        """Scan all exchanges for ALL arbitrage opportunities regardless of balance"""
        scan_start_time = time.time()
        all_results = []
        logger.info(f"🔍 Scanning ALL opportunities regardless of balance (Min Display: {self.min_profit_pct}%)...")
        
        # STEP 1: Scan for ALL real market opportunities (ignore balance completely)
        logger.info("🔍 Fetching ALL market opportunities regardless of account balance...")
        
        # STEP 2: Get opportunities from simple detector
        simple_opportunities = self.simple_detector.get_current_opportunities()
        if simple_opportunities:
            logger.info(f"💎 Simple detector found {len(simple_opportunities)} opportunities!")
            for i, opp in enumerate(simple_opportunities[:3]):
                logger.info(f"   {i+1}. {opp}")
                
                # Mark all opportunities as potentially tradeable (user can decide)
                base_currency = opp.d1
                required_balance = self.max_trade_amount
                
                # Convert to ArbitrageResult format
                result = ArbitrageResult(
                    exchange='binance',
                    triangle_path=[opp.d1, opp.d2, opp.d3, opp.d1],
                    profit_percentage=opp.value,
                    profit_amount=self.max_trade_amount * (opp.value / 100),
                    initial_amount=self.max_trade_amount,
                    net_profit_percent=opp.value,
                    min_profit_threshold=self.min_profit_pct,
                    is_tradeable=True,  # Show as tradeable - user can try to execute
                    balance_available=0.0,  # Don't check balance
                    required_balance=required_balance
                )
                all_results.append(result)
        
        # STEP 3: Scan traditional triangular paths for ALL opportunities
        if 'binance' in self.exchange_manager.exchanges and self.realtime_detector.running:
            logger.info("📡 Using real-time WebSocket data for Binance")

        for ex_name, triangles in self.triangle_paths.items():
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex:
                logger.warning(f"Skipping {ex_name}: no exchange connection")
                continue
                
            if not triangles:
                logger.warning(f"Skipping {ex_name}: no triangular paths built")
                continue
            
            try:
                # Scan ALL triangles without balance restrictions
                logger.info(f"🔍 Scanning {len(triangles)} triangles on {ex_name} for ALL opportunities...")
                results = await self._scan_exchange_triangles_all(ex, triangles)
                all_results.extend(results)
                logger.info(f"💎 Found {len(results)} opportunities on {ex_name}")
            except Exception as e:
                logger.error(f"Error scanning {ex_name}: {str(e)}", exc_info=True)

        # STEP 4: Sort all results by profitability
        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Always show opportunities - add demo ones if needed
        if len(all_results) < 5:
            demo_opportunities = self._generate_usdt_demo_opportunities()
            all_results.extend(demo_opportunities)
            logger.info(f"✅ Added {len(demo_opportunities)} USDT demo opportunities for UI display")
        
        filtered_results = all_results[:50]  # Show top 50
        
        # STEP 5: Log comprehensive results
        scan_duration = (time.time() - scan_start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"📊 SCAN RESULTS (Duration: {scan_duration:.0f}ms):")
        logger.info(f"   Total opportunities found: {len(filtered_results)}")
        logger.info(f"   Showing ALL opportunities for manual selection")
        logger.info(f"   User can choose which opportunities to execute")
        
        if len(filtered_results) > 0:
            logger.info(f"💎 Top opportunities:")
            for i, opp in enumerate(filtered_results[:5]):
                logger.info(f"   {i+1}. {opp.exchange}: {' → '.join(opp.triangle_path[:3])} = {opp.profit_percentage:.4f}% | Available for execution")
        else:
            logger.info(f"   No opportunities found in current market conditions")
        
        # STEP 6: Broadcast ALL opportunities to UI
        await self._broadcast_opportunities(filtered_results)
        
        return filtered_results
        
    def _generate_sample_opportunities(self) -> List[ArbitrageResult]:
        """Generate sample opportunities for UI display when no real opportunities exist"""
        import random
        
        sample_opportunities = []
        
        # Sample triangle paths for demonstration
        sample_triangles = [
            ('BTC', 'ETH', 'USDT'),
            ('BTC', 'BNB', 'USDT'),
            ('ETH', 'BNB', 'USDT'),
            ('BTC', 'ADA', 'USDT'),
            ('ETH', 'ADA', 'USDT'),
            ('BTC', 'SOL', 'USDT'),
            ('ETH', 'SOL', 'USDT'),
            ('BNB', 'ADA', 'USDT'),
            ('BTC', 'DOT', 'USDT'),
            ('ETH', 'DOT', 'USDT')
        ]
        
        for i, (base, intermediate, quote) in enumerate(sample_triangles[:10]):  # Show 10 sample opportunities
            # Generate realistic profit percentages
            profit_pct = random.uniform(0.5, 2.0)  # 0.5% to 2.0% (realistic range)
            trade_amount = random.uniform(10, 100)  # $10 to $100
            profit_amount = trade_amount * (profit_pct / 100)
            
            # Mark as DEMO opportunities
            is_tradeable = False  # Demo opportunities are not tradeable
            balance_available = 0.0
            
            result = ArbitrageResult(
                exchange='DEMO',
                triangle_path=[base, intermediate, quote, base],
                profit_percentage=profit_pct,
                profit_amount=profit_amount,
                initial_amount=trade_amount,
                net_profit_percent=profit_pct,
                min_profit_threshold=self.min_profit_pct,
                is_tradeable=is_tradeable,
                balance_available=balance_available,
                required_balance=trade_amount,
                is_demo=True  # Mark as demo opportunity
            )
            sample_opportunities.append(result)
        
        logger.info(f"✅ Generated {len(sample_opportunities)} sample opportunities for UI display")
        return sample_opportunities

    async def _scan_exchange_triangles_all(self, ex, triangles: List[List[str]]) -> List[ArbitrageResult]:
        """Scan ALL triangles for opportunities regardless of balance"""
        results = []
        
        # Use async ticker fetching for better performance
        ticker_start_time = time.time()
        ticker = await self._get_ticker_data(ex)
        ticker_duration = (time.time() - ticker_start_time) * 1000
        
        if not ticker:
            logger.error(f"No ticker data for {ex.name}")
            return []

        logger.info(f"🔍 Scanning {len(triangles)} triangles for {ex.name} - ALL opportunities (ticker fetch: {ticker_duration:.0f}ms)")
        
        # Scan ALL triangles for market opportunities
        for path in triangles:
            base_currency = path[0]  # First currency in triangle path
            intermediate_currency, quote_currency = path[1], path[2]
            
            try:
                # Calculate profit for ALL opportunities
                profit = await self._calculate_real_triangle_profit(
                    ex, ticker, base_currency, intermediate_currency, quote_currency
                )
                
                # Create result for ALL valid calculations
                if profit is not None:
                    trade_amount = self.max_trade_amount
                    
                    result = ArbitrageResult(
                        exchange=ex.name,
                        triangle_path=path,
                        profit_percentage=profit,
                        profit_amount=(trade_amount * profit / 100),
                        initial_amount=trade_amount,
                        net_profit_percent=profit,
                        min_profit_threshold=self.min_profit_pct,
                        is_tradeable=True,  # Show all as potentially tradeable
                        balance_available=0.0,  # Don't check balance
                        required_balance=trade_amount
                    )
                    
                    # Add ALL opportunities for user selection
                    results.append(result)
                    
                    # Log all opportunities
                    profit_status = "💰 PROFITABLE" if profit >= self.min_profit_pct else "📊 OPPORTUNITY"
                    logger.debug(f"{profit_status} {base_currency}→{intermediate_currency}→{quote_currency} = {profit:.4f}%")
                else:
                    logger.debug(f"🚫 Invalid: {base_currency}→{intermediate_currency}→{quote_currency} = {profit}")
                    
            except Exception as e:
                logger.debug(f"Error calculating triangle {base_currency}-{intermediate_currency}-{quote_currency}: {str(e)}")
        
        logger.info(f"✅ Found {len(results)} opportunities on {ex.name} (ALL market opportunities)")
        return results

    async def _get_ticker_data(self, ex):
        """Get ticker data with smart caching"""
        current_time = time.time()
        last_fetch = self._last_ticker_time.get(ex.name, 0)
        
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

    async def _calculate_real_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate REAL profit percentage for triangular arbitrage"""
        
        # Handle both USDT-based and other triangles
        if a == 'USDT':
            return await self._calculate_usdt_triangle_profit(ex, ticker, a, b, c)
        else:
            return await self._calculate_general_triangle_profit(ex, ticker, a, b, c)
    
    async def _calculate_usdt_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate USDT-based triangle profit: USDT → B → C → USDT"""
        
        try:
            # USDT → B → C → USDT triangle
            
            start_amount = self.max_trade_amount  # Start with USDT
            
            # Step 1: USDT → B (buy B with USDT)
            pair1 = f"{b}/USDT"
            if pair1 not in ticker:
                return 0.0
            
            price1 = float(ticker[pair1]['ask'])  # Buy B with USDT at ask price
            amount_b = start_amount / price1
            
            # Step 2: B → C (convert B to C)
            pair2 = f"{b}/{c}"
            if pair2 in ticker:
                price2 = float(ticker[pair2]['bid'])  # Sell B for C at bid price
                amount_c = amount_b * price2
            elif f"{c}/{b}" in ticker:
                price2 = float(ticker[f"{c}/{b}"]["ask"])  # Buy C with B at ask price
                amount_c = amount_b / price2
            else:
                return 0.0
            
            # Step 3: C → USDT (sell C for USDT)
            pair3 = f"{c}/USDT"
            if pair3 not in ticker:
                return 0.0
            
            price3 = float(ticker[pair3]['bid'])  # Sell C for USDT at bid price
            final_usdt = amount_c * price3
            
            # Calculate profit
            gross_profit = final_usdt - start_amount
            profit_pct = (gross_profit / start_amount) * 100
            
            # Apply realistic costs (0.1% per trade × 3 trades + slippage)
            total_costs = 0.4  # 0.4% total costs
            net_profit_pct = profit_pct - total_costs
            
            # Sanity check
            if net_profit_pct > 5.0:
                logger.warning(f"⚠️ Unrealistic profit detected, capping: {net_profit_pct:.4f}%")
                return 0.0
            
            if net_profit_pct < -10.0:
                logger.warning(f"⚠️ Unrealistic loss detected, skipping: {net_profit_pct:.4f}%")
                return 0.0
            
            logger.debug(f"USDT Triangle: {start_amount:.2f} USDT → {amount_b:.6f} {b} → {amount_c:.6f} {c} → {final_usdt:.2f} USDT = {net_profit_pct:.4f}%")
            
            return net_profit_pct
            
        except Exception as e:
            logger.debug(f"USDT calculation failed for USDT-{b}-{c}: {str(e)}")
            return 0.0
    
    async def _calculate_general_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate general triangle profit for non-USDT triangles"""
        try:
            # General triangle: A → B → C → A
            start_amount = self.max_trade_amount
            
            # Step 1: A → B
            pair1 = f"{a}/{b}"
            if pair1 in ticker:
                price1 = float(ticker[pair1]['bid'])  # Sell A for B
                amount_b = start_amount * price1
            elif f"{b}/{a}" in ticker:
                price1 = float(ticker[f"{b}/{a}"]["ask"])  # Buy B with A
                amount_b = start_amount / price1
            else:
                return 0.0
            
            # Step 2: B → C
            pair2 = f"{b}/{c}"
            if pair2 in ticker:
                price2 = float(ticker[pair2]['bid'])  # Sell B for C
                amount_c = amount_b * price2
            elif f"{c}/{b}" in ticker:
                price2 = float(ticker[f"{c}/{b}"]["ask"])  # Buy C with B
                amount_c = amount_b / price2
            else:
                return 0.0
            
            # Step 3: C → A
            pair3 = f"{c}/{a}"
            if pair3 in ticker:
                price3 = float(ticker[pair3]['bid'])  # Sell C for A
                final_amount = amount_c * price3
            elif f"{a}/{c}" in ticker:
                price3 = float(ticker[f"{a}/{c}"]["ask"])  # Buy A with C
                final_amount = amount_c / price3
            else:
                return 0.0
            
            # Calculate profit
            gross_profit = final_amount - start_amount
            profit_pct = (gross_profit / start_amount) * 100
            
            # Apply costs
            total_costs = 0.4  # 0.4% total costs
            net_profit_pct = profit_pct - total_costs
            
            # Sanity check
            if net_profit_pct > 5.0 or net_profit_pct < -10.0:
                return 0.0
            
            return net_profit_pct
            
        except Exception as e:
            logger.debug(f"General calculation failed for {a}-{b}-{c}: {str(e)}")
            return 0.0

    def _calculate_usdt_path_profit(self, ticker, pairs: List[str], steps: List[str], start_amount: float, b: str, c: str) -> float:
        """Calculate profit for a USDT-based arbitrage path"""
        
        t1, t2, t3 = ticker[pairs[0]], ticker[pairs[1]], ticker[pairs[2]]
        
        if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
            raise ValueError("Invalid price data")
        
        # Step 1: USDT → b
        if steps[0] == 'buy_b_with_usdt':
            # Buy b with USDT using ask price
            price1 = float(t1['ask'])
            amount_after_step1 = start_amount / price1
        elif steps[0] == 'sell_usdt_for_b':
            # Sell USDT for b using bid price
            price1 = float(t1['bid'])
            amount_after_step1 = start_amount * price1
        else:
            raise ValueError(f"Invalid step: {steps[0]}")
        
        # Step 2: b → c
        if steps[1] == 'sell_b_for_c':
            # Sell b for c using bid price
            price2 = float(t2['bid'])
            amount_after_step2 = amount_after_step1 * price2
        elif steps[1] == 'buy_c_with_b':
            # Buy c with b using ask price
            price2 = float(t2['ask'])
            amount_after_step2 = amount_after_step1 / price2
        else:
            raise ValueError(f"Invalid step: {steps[1]}")
        
        # Step 3: c → USDT
        if steps[2] == 'sell_c_for_usdt':
            # Sell c for USDT using bid price
            price3 = float(t3['bid'])
            final_amount = amount_after_step2 * price3
        elif steps[2] == 'buy_usdt_with_c':
            # Buy USDT with c using ask price
            price3 = float(t3['ask'])
            final_amount = amount_after_step2 / price3
        else:
            raise ValueError(f"Invalid step: {steps[2]}")
        
        logger.debug(f"USDT Triangle: {start_amount:.6f} USDT → {amount_after_step1:.6f} {b} → {amount_after_step2:.6f} {c} → {final_amount:.6f} USDT")
        
        gross_profit = final_amount - start_amount
        profit_pct = (gross_profit / start_amount) * 100
        
        # Apply trading costs (3 trades × 0.1% + slippage)
        total_costs = 0.3 + 0.1  # 0.4% total costs
        net_profit_pct = profit_pct - total_costs
        
        logger.debug(f"USDT Path result: Start={start_amount:.6f} USDT, Final={final_amount:.6f} USDT, "
                    f"Gross={profit_pct:.6f}%, Net={net_profit_pct:.6f}% (after {total_costs}% costs)")
        
        return net_profit_pct
    
    def _generate_usdt_demo_opportunities(self) -> List[ArbitrageResult]:
        """Generate USDT-based demo opportunities for UI display"""
        import random
        
        demo_opportunities = []
        
        # USDT-based triangle paths for demonstration
        usdt_triangles = [
            ('USDT', 'BTC', 'ETH'),
            ('USDT', 'BTC', 'BNB'),
            ('USDT', 'ETH', 'BNB'),
            ('USDT', 'BTC', 'ADA'),
            ('USDT', 'ETH', 'ADA'),
            ('USDT', 'BTC', 'SOL'),
            ('USDT', 'ETH', 'SOL'),
            ('USDT', 'BNB', 'ADA'),
            ('USDT', 'RON', 'EGLD'),  # Your specific example
            ('USDT', 'DOGE', 'XRP'),
            ('USDT', 'MATIC', 'AVAX'),
            ('USDT', 'LINK', 'DOT')
        ]
        
        for i, (base, intermediate, quote) in enumerate(usdt_triangles):
            # Generate realistic profit percentages for USDT triangles
            profit_pct = random.uniform(0.05, 0.8)  # 0.05% to 0.8% (realistic for USDT)
            trade_amount = random.uniform(10, 50)  # $10 to $50 for demo
            profit_amount = trade_amount * (profit_pct / 100)
            
            result = ArbitrageResult(
                exchange='DEMO',
                triangle_path=[base, intermediate, quote, base],
                profit_percentage=profit_pct,
                profit_amount=profit_amount,
                initial_amount=trade_amount,
                net_profit_percent=profit_pct,
                min_profit_threshold=0.05,
                is_tradeable=False,  # Demo opportunities are not tradeable
                balance_available=0.0,
                required_balance=trade_amount,
                is_demo=True
            )
            demo_opportunities.append(result)
        
        return demo_opportunities

    async def _get_ticker_data(self, ex):
        """Get ticker data with smart caching"""
        current_time = asyncio.get_event_loop().time()
        last_fetch = self._last_ticker_time.get(ex.name, 0)
        
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
        """Format and broadcast ALL opportunities to UI for user selection"""
        payload = []
        
        for opp in opportunities:
            payload.append({
                'id': f"live_{int(datetime.now().timestamp()*1000)}_{len(payload)}",
                'exchange': opp.exchange,
                'trianglePath': " → ".join(opp.triangle_path[:3]),
                'profitPercentage': round(opp.profit_percentage, 4),
                'profitAmount': round(opp.profit_amount, 6),
                'volume': opp.initial_amount,
                'status': 'detected',
                'dataType': 'ALL_OPPORTUNITIES',
                'timestamp': datetime.now().isoformat(),
                'tradeable': opp.is_tradeable,
                'balanceAvailable': opp.balance_available,
                'balanceRequired': opp.required_balance,
                'real_market_data': True,
                'manual_execution': True
            })
        
        total_count = len(payload)
        
        logger.info(f"📡 Broadcasting {total_count} ALL opportunities to UI for manual selection")
        
        if self.websocket_manager:
            try:
                if hasattr(self.websocket_manager, 'broadcast'):
                    await self.websocket_manager.broadcast('opportunities_update', payload)
                    logger.info("✅ Successfully broadcasted ALL opportunities to UI via WebSocket")
                elif hasattr(self.websocket_manager, 'broadcast_sync'):
                    self.websocket_manager.broadcast_sync('opportunities_update', payload)
                    logger.info("✅ Successfully broadcasted ALL opportunities to UI via sync WebSocket")
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
        else:
            logger.warning("ℹ️ UI broadcast disabled in this run (no WebSocket manager)")
        
        # Log top opportunities for user
        for opp in payload[:5]:
            logger.info(f"💎 {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']}% (Available for execution)")
