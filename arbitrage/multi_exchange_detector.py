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
        self.min_profit_pct = 0.5  # Fixed 0.5% threshold for Gate.io profitability
        self.max_trade_amount = min(20.0, float(config.get('max_trade_amount', 20.0)))  # $20 maximum for safety
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Initialize real-time detector
        self.realtime_detector = RealtimeArbitrageDetector(
            min_profit_pct=self.min_profit_pct,
            max_trade_amount=self.max_trade_amount
        )
        
        # Initialize simple detector (based on working JavaScript logic)
        self.simple_detector = None  # Will be initialized per exchange
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}
        self._logged_messages = set()
        
        logger.info(f"💰 USDT TRIANGULAR ARBITRAGE Detector initialized - Min Profit: 0.5%, Max Trade: ${self.max_trade_amount}")
        logger.info(f"🎯 Target: USDT → Currency1 → Currency2 → USDT cycles only")

    async def initialize(self):
        """Initialize with balance verification"""
        logger.info("🚀 Initializing LIVE TRADING detector...")
        
        # Initialize simple detector for the first connected exchange
        connected_exchanges = list(self.exchange_manager.exchanges.keys())
        if connected_exchanges:
            primary_exchange = connected_exchanges[0]
            logger.info(f"🎯 Initializing simple detector for {primary_exchange}")
            
            self.simple_detector = SimpleTriangleDetector(
                min_profit_pct=0.5,  # Fixed 0.5% for profitability
                exchange_id=primary_exchange
            )
            
            # Initialize and start the detector with correct exchange
            if await self.simple_detector.get_pairs():
                asyncio.create_task(self.simple_detector.start_websocket_stream())
                logger.info(f"✅ Simple detector started for {primary_exchange} with correct URLs")
            else:
                logger.error(f"❌ Failed to initialize simple detector for {primary_exchange}")
        
        # First verify we can fetch balances
        for ex_name in self.exchange_manager.exchanges:
            balance = await self.show_account_balance(ex_name)
            if balance and balance.get('balances'):
                logger.info(f"✅ Balance detected on {ex_name}: {len(balance['balances'])} currencies")
            else:
                logger.warning(f"⚠️ No balance detected on {ex_name} - continuing anyway")
        
        # Initialize real-time detector
        await self.realtime_detector.initialize()
        
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
        """Build USDT-based triangles using ONLY the actual available pairs from Binance"""
        logger.info(f"💎 Building USDT triangles from {len(pairs)} REAL Binance pairs...")
        
        available_pairs = set(pairs)
        
        # Get all USDT pairs and extract currencies
        usdt_pairs = [pair for pair in pairs if '/USDT' in pair]
        logger.info(f"🎯 Found {len(usdt_pairs)} USDT pairs for triangular arbitrage")
        
        # Extract currencies that have USDT pairs
        usdt_currencies = set()
        for pair in usdt_pairs:
            base = pair.split('/')[0]
            usdt_currencies.add(base)
        
        # Filter to only major/real currencies that exist on Gate.io
        real_gateio_currencies = {
            'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
            'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
            'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
            'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
            'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'LTC', 'EOS',
            'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
            'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB'
        }
        
        # Only use currencies that exist on Gate.io AND have USDT pairs
        valid_usdt_currencies = usdt_currencies.intersection(real_gateio_currencies)
        
        logger.info(f"✅ Found {len(valid_usdt_currencies)} REAL Gate.io currencies with USDT pairs")
        logger.info(f"📋 Valid currencies: {sorted(list(valid_usdt_currencies)[:20])}")
        
        # Build USDT triangular paths: USDT → curr1 → curr2 → USDT
        usdt_triangles = []
        
        for curr1 in valid_usdt_currencies:
            for curr2 in valid_usdt_currencies:
                if curr1 != curr2:
                    # Required pairs for USDT triangle
                    pair1 = f"{curr1}/USDT"      # USDT → curr1
                    pair2 = f"{curr1}/{curr2}"   # curr1 → curr2
                    pair3 = f"{curr2}/USDT"      # curr2 → USDT
                    
                    # Alternative if curr1→curr2 doesn't exist
                    alt_pair2 = f"{curr2}/{curr1}"
                    
                    # CRITICAL: Validate ALL required pairs exist on Gate.io
                    if (pair1 in available_pairs and pair3 in available_pairs and 
                        (pair2 in available_pairs or alt_pair2 in available_pairs)):
                        
                        # Create proper 4-step USDT triangle
                        triangle = ['USDT', curr1, curr2]  # 3 currencies for calculation
                        usdt_triangles.append(triangle)
                        
                        if len(usdt_triangles) <= 20:
                            pair2_used = pair2 if pair2 in available_pairs else alt_pair2
                            logger.info(f"💰 VALID USDT Triangle: USDT → {curr1} → {curr2} → USDT")
                            logger.info(f"   Pairs: {pair1}, {pair2_used}, {pair3}")
                    else:
                        # Log missing pairs for debugging
                        missing_pairs = []
                        if pair1 not in available_pairs:
                            missing_pairs.append(pair1)
                        if pair3 not in available_pairs:
                            missing_pairs.append(pair3)
                        if pair2 not in available_pairs and alt_pair2 not in available_pairs:
                            missing_pairs.append(f"{pair2} or {alt_pair2}")
                        
                        if len(usdt_triangles) < 5:  # Only log first few for debugging
                            logger.debug(f"❌ Rejected USDT triangle {curr1}-{curr2}: missing {missing_pairs}")
        
        # Add specific high-volume USDT triangles that definitely exist on Gate.io
        priority_usdt_triangles = [
            # Only include triangles with currencies that definitely exist on Gate.io
            ('USDT', 'BTC', 'ETH'), ('USDT', 'BTC', 'USDC'), ('USDT', 'ETH', 'USDC'),
            ('USDT', 'BTC', 'ADA'), ('USDT', 'ETH', 'ADA'), ('USDT', 'BTC', 'SOL'),
            ('USDT', 'ETH', 'SOL'), ('USDT', 'BTC', 'DOT'), ('USDT', 'ETH', 'DOT'),
            ('USDT', 'BTC', 'LINK'), ('USDT', 'ETH', 'LINK'), ('USDT', 'BTC', 'MATIC'),
            ('USDT', 'ETH', 'MATIC'), ('USDT', 'BTC', 'AVAX'), ('USDT', 'ETH', 'AVAX'),
            ('USDT', 'BTC', 'XRP'), ('USDT', 'ETH', 'XRP'), ('USDT', 'BTC', 'LTC'),
            ('USDT', 'ETH', 'LTC'), ('USDT', 'BTC', 'DOGE'), ('USDT', 'ETH', 'DOGE')
        ]
        
        for triangle in priority_usdt_triangles:
            triangle_3_currencies = list(triangle[:3])  # Take first 3 currencies
            if (self._validate_usdt_triangle_exists(triangle_3_currencies, available_pairs) and 
                triangle_3_currencies not in usdt_triangles):
                usdt_triangles.append(triangle_3_currencies)
                logger.info(f"💎 Added priority USDT triangle: {' → '.join(triangle_3_currencies)} → USDT")
        
        logger.info(f"✅ Built {len(usdt_triangles)} USDT triangles for {exchange_name}")
        return usdt_triangles if usdt_triangles else []

    def _validate_usdt_triangle_exists(self, triangle: List[str], available_pairs: set) -> bool:
        """Validate that a USDT triangle has all required pairs on Gate.io"""
        if len(triangle) != 3 or triangle[0] != 'USDT':
            return False
            
        usdt, curr1, curr2 = triangle
        
        # Required pairs for USDT triangle
        pair1 = f"{curr1}/USDT"      # USDT → curr1
        pair2 = f"{curr1}/{curr2}"   # curr1 → curr2
        pair3 = f"{curr2}/USDT"      # curr2 → USDT
        
        # Alternative if curr1→curr2 doesn't exist
        alt_pair2 = f"{curr2}/{curr1}"
        
        # Check if all required pairs exist
        pair1_exists = pair1 in available_pairs
        pair3_exists = pair3 in available_pairs
        pair2_exists = pair2 in available_pairs or alt_pair2 in available_pairs
        
        if pair1_exists and pair2_exists and pair3_exists:
            logger.debug(f"✅ Valid triangle: {' → '.join(triangle)} → USDT")
            return True
        else:
            missing = []
            if not pair1_exists:
                missing.append(pair1)
            if not pair3_exists:
                missing.append(pair3)
            if not pair2_exists:
                missing.append(f"{pair2} or {alt_pair2}")
            logger.debug(f"❌ Invalid triangle {' → '.join(triangle)}: missing {missing}")
            return False

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
            # Only log if we have new opportunities
            current_time = time.time()
            if not hasattr(self, '_last_simple_log') or current_time - self._last_simple_log > 30:
                logger.info(f"💎 Simple detector found {len(simple_opportunities)} opportunities!")
                for i, opp in enumerate(simple_opportunities[:3]):
                    logger.info(f"   {i+1}. {opp}")
                self._last_simple_log = current_time
                
            # Convert simple detector opportunities to results
            for opp in simple_opportunities[:5]:  # Top 5 only
                # Only add Gate.io compatible opportunities
                if any(currency in ['EGLD', 'RON', 'USDC', 'BTC', 'USDT'] for currency in [opp.d1, opp.d2, opp.d3]):
                    result = ArbitrageResult(
                        exchange='gate',  # Use Gate.io since that's what we're connected to
                        triangle_path=[opp.d1, opp.d2, opp.d3],  # 3 currencies
                        profit_percentage=opp.value,
                        profit_amount=self.max_trade_amount * (opp.value / 100),
                        initial_amount=self.max_trade_amount,
                        net_profit_percent=opp.value,
                        min_profit_threshold=self.min_profit_pct,
                        is_tradeable=True,
                        balance_available=120.0,  # Your USDT balance
                        required_balance=self.max_trade_amount
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
        
        # Show ALL opportunities (let user decide what to execute)
        filtered_results = all_results
        
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
                        initial_amount=max(5.0, min(20.0, trade_amount)),  # Gate.io: min $5, max $20
                        net_profit_percent=profit,
                        min_profit_threshold=self.min_profit_pct,
                        is_tradeable=True,  # Show all as potentially tradeable
                        balance_available=0.0,  # Don't check balance
                        required_balance=max(5.0, min(20.0, trade_amount))  # Gate.io limits
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
        """Calculate REAL profit percentage for USDT triangular arbitrage: USDT → b → c → USDT"""
        
        # Ensure this is a USDT-based triangle (a should be USDT)
        if a != 'USDT':
            logger.debug(f"Skipping non-USDT triangle: {a}→{b}→{c}")
            return 0.0
        
        # CRITICAL: Validate currencies exist on Gate.io
        valid_gateio_currencies = {
            'BTC', 'ETH', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
            'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
            'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
            'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
            'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS',
            'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
            'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB'
            'FDUSD', 'PENDLE', 'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'RNDR', 'INJ', 'SEI',
            'TIA', 'SUI', 'ORDI', 'SATS', '1000SATS', 'RATS', 'MEME', 'PEPE', 'FLOKI', 'WLD',
            'SCR', 'EIGEN', 'HMSTR', 'CATI', 'NEIRO', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI'
        }
        
        if b not in valid_gateio_currencies or c not in valid_gateio_currencies:
            logger.debug(f"❌ Skipping triangle with non-existent currencies: USDT→{b}→{c}→USDT")
            return 0.0
        
        try:
            # USDT Triangle calculation: USDT → b → c → USDT
            
            start_usdt = max(5.0, min(self.max_trade_amount, 20.0))  # $5-20 range for Gate.io
            
            # Required pairs for USDT triangle
            pair1 = f"{b}/USDT"      # b/USDT pair
            pair2 = f"{b}/{c}"       # b/c pair (direct)
            pair3 = f"{c}/USDT"      # c/USDT pair
            alt_pair2 = f"{c}/{b}"   # c/b pair (alternative)
            
            # CRITICAL: Check if all required pairs exist in ticker data
            if not (pair1 in ticker and pair3 in ticker):
                logger.debug(f"❌ Missing USDT pairs for triangle USDT→{b}→{c}→USDT: {pair1} or {pair3}")
                return 0.0
            
            # Determine which b→c pair to use
            if pair2 in ticker:
                use_direct = True
                bc_pair = pair2
            elif alt_pair2 in ticker:
                use_direct = False
                bc_pair = alt_pair2
            else:
                logger.debug(f"❌ Missing {b}→{c} pair for triangle USDT→{b}→{c}→USDT: neither {pair2} nor {alt_pair2}")
                return 0.0
            
            # Get ticker data
            t1 = ticker[pair1]  # b/USDT
            t2 = ticker[bc_pair]  # b/c or c/b
            t3 = ticker[pair3]  # c/USDT
            
            # Validate price data
            if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
                logger.debug(f"❌ Invalid price data for USDT triangle USDT→{b}→{c}→USDT")
                return 0.0
            
            # Validate prices are reasonable
            prices = [float(t1['ask']), float(t1['bid']), float(t2['ask']), float(t2['bid']), 
                     float(t3['ask']), float(t3['bid'])]
            if any(p <= 0 or p > 1000000 for p in prices):
                logger.debug(f"❌ Unreasonable prices for USDT triangle USDT→{b}→{c}→USDT")
                return 0.0
            
            # Step 1: USDT → b (buy b with USDT)
            price1 = float(t1['ask'])  # Buy b at ask price
            amount_b = start_usdt / price1
            
            # Validate step 1 result
            if amount_b <= 0 or amount_b > start_usdt * 1000:
                logger.debug(f"❌ Invalid step 1 result for USDT→{b}: {amount_b}")
                return 0.0
            
            # Step 2: b → c
            if use_direct:
                # Direct pair b/c: sell b for c
                price2 = float(t2['bid'])  # Sell b at bid price
                amount_c = amount_b * price2
            else:
                # Inverse pair c/b: buy c with b
                price2 = float(t2['ask'])  # Buy c at ask price
                amount_c = amount_b / price2
            
            # Validate step 2 result
            if amount_c <= 0 or amount_c > amount_b * 1000:
                logger.debug(f"❌ Invalid step 2 result for {b}→{c}: {amount_c}")
                return 0.0
            
            # Step 3: c → USDT (sell c for USDT)
            price3 = float(t3['bid'])  # Sell c at bid price
            final_usdt = amount_c * price3
            
            # Validate final result
            if final_usdt <= 0 or final_usdt > start_usdt * 10:
                logger.debug(f"❌ Invalid final result for {c}→USDT: {final_usdt}")
                return 0.0
            
            # Calculate profit
            gross_profit = final_usdt - start_usdt
            gross_profit_pct = (gross_profit / start_usdt) * 100
            
            # Apply realistic trading costs for Gate.io
            total_costs_pct = 0.6  # 0.6% total costs (0.2% per trade × 3 trades)
            net_profit_pct = gross_profit_pct - total_costs_pct
            
            logger.debug(f"USDT Triangle USDT→{b}→{c}→USDT: "
                        f"{start_usdt:.2f} USDT → {amount_b:.6f} {b} → {amount_c:.6f} {c} → {final_usdt:.2f} USDT = "
                        f"{net_profit_pct:.6f}% net profit")
            
            # Return profitable opportunities (lowered threshold to 0.5%)
            if net_profit_pct >= 0.5 and net_profit_pct <= 3.0:  # Minimum 0.5%, maximum 3.0%
                return net_profit_pct
            else:
                return 0.0
                
        except Exception as e:
            logger.debug(f"USDT calculation failed for USDT→{b}→{c}→USDT: {str(e)}")
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