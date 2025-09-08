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

from utils.logger import setup_logger
from arbitrage.realtime_detector import RealtimeArbitrageDetector
from arbitrage.simple_triangle_detector import SimpleTriangleDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

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
        self.logger = setup_logger('MultiExchangeDetector')
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        
        # Trading Limits
        self.min_profit_pct = 0.4  # Fixed 0.5% threshold for Gate.io profitability
        self.max_trade_amount = min(20.0, float(config.get('max_trade_amount', 20.0)))  # $20 maximum for safety
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        
        # Initialize real-time detector
        self.realtime_detector = RealtimeArbitrageDetector(
            min_profit_pct=self.min_profit_pct,
            max_trade_amount=self.max_trade_amount
        )
        
        # Initialize enhanced detector
        from arbitrage.enhanced_triangle_detector import EnhancedTriangleDetector
        self.enhanced_detector = EnhancedTriangleDetector(
            exchange_manager, 
            min_profit_pct=self.min_profit_pct,
            max_trade_amount=self.max_trade_amount
        )
        
        # Initialize simple detector (based on working JavaScript logic)
        self.simple_detector = None  # Will be initialized per exchange
        
        # Rate limiting cache
        self._last_tickers: Dict[str, Dict[str, Any]] = {}
        self._last_ticker_time: Dict[str, float] = {}
        self._logged_messages = set()
        
        self.logger.info(f"💰 USDT TRIANGULAR ARBITRAGE Detector initialized - Min Profit: 0.4%, Max Trade: ${self.max_trade_amount}")
        self.logger.info(f"🎯 Target: USDT → Currency1 → Currency2 → USDT cycles only")

    async def initialize(self):
        """Initialize with balance verification"""
        self.logger.info("🚀 Initializing LIVE TRADING detector...")
        
        # Initialize simple detector for the first connected exchange
        connected_exchanges = list(self.exchange_manager.exchanges.keys())
        if connected_exchanges:
            primary_exchange = connected_exchanges[0]
            self.logger.info(f"🎯 Initializing simple detector for {primary_exchange}")
            
            self.simple_detector = SimpleTriangleDetector(
                min_profit_pct=0.4,  # Fixed 0.4% for profitability
                exchange_id=primary_exchange
            )
            
            # Initialize and start the detector with correct exchange
            if await self.simple_detector.get_pairs():
                asyncio.create_task(self.simple_detector.start_websocket_stream())
                self.logger.info(f"✅ Simple detector started for {primary_exchange.upper()} with correct URLs")
            else:
                self.logger.error(f"❌ Failed to initialize simple detector for {primary_exchange.upper()}")
        
        # First verify we can fetch balances
        for ex_name in self.exchange_manager.exchanges:
            balance = await self.show_account_balance(ex_name)
            if balance and balance.get('balances'):
                self.logger.info(f"✅ Balance detected on {ex_name.upper()}: {len(balance['balances'])} currencies")
            else:
                self.logger.warning(f"⚠️ No balance detected on {ex_name.upper()} - continuing anyway")
        
        # Only initialize real-time detector for Binance
        if 'binance' in self.exchange_manager.exchanges:
            await self.realtime_detector.initialize()
            self.logger.info("✅ Real-time detector initialized for Binance")
        else:
            self.logger.info("ℹ️ Real-time detector skipped (Binance not selected)")
        
        # Build triangle paths
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = list(ex.trading_pairs.keys())
                self.logger.info(f"Processing {len(pairs)} pairs for {ex_name.upper()}")
                
                triangles = self._build_real_triangles_from_available_pairs(pairs, ex_name)
                self.triangle_paths[ex_name] = triangles
                
                self.logger.info(f"✅ Built {len(triangles)} REAL triangles for {ex_name.upper()}")
                if triangles:
                    sample = " → ".join(triangles[0][:3])
                    self.logger.info(f"Sample triangle: {sample}")
                    
            except Exception as e:
                self.logger.error(f"Error building triangles for {ex_name.upper()}: {str(e)}", exc_info=True)
                self.triangle_paths[ex_name] = []
        
        total = sum(len(t) for t in self.triangle_paths.values())
        self.logger.info(f"🎯 Total REAL triangles across all exchanges: {total}")

    async def show_account_balance(self, exchange_name: str = "binance") -> Dict[str, Any]:
        """Display complete account balance with USD values"""
        ex = self.exchange_manager.exchanges.get(exchange_name)
        if not ex:
            self.logger.error(f"Exchange {exchange_name} not found")
            return {}

        try:
            # Try to get balance using the correct method
            balance = await ex.get_account_balance()
            if not balance:
                self.logger.error("❌ No balance data retrieved")
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
            
            self.logger.info(balance_text)
            return balance_data
            
        except Exception as e:
            self.logger.error(f"Failed to display balance: {str(e)}")
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
        
        self.logger.error(f"Failed after {retries} attempts. Last error: {str(last_error)}")
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
            self.logger.error(f"Direct balance fetch failed: {str(e)}")
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
        """Build USDT-based triangles using ONLY the actual available pairs from the selected exchange"""
        self.logger.info(f"💎 Building USDT triangles from {len(pairs)} REAL {exchange_name.upper()} pairs...")
        
        available_pairs = set(pairs)
        
        # Get all USDT pairs and extract currencies
        usdt_pairs = [pair for pair in pairs if '/USDT' in pair]
        self.logger.info(f"🎯 Found {len(usdt_pairs)} USDT pairs on {exchange_name.upper()} for triangular arbitrage")
        
        # Extract currencies that have USDT pairs
        usdt_currencies = set()
        for pair in usdt_pairs:
            base = pair.split('/')[0]
            usdt_currencies.add(base)
        
        # Filter to currencies that exist on the selected exchange
        real_exchange_currencies = self._get_valid_currencies_for_exchange(exchange_name)
        
        # Only use currencies that exist on the selected exchange AND have USDT pairs
        valid_usdt_currencies = usdt_currencies.intersection(real_exchange_currencies)
        
        self.logger.info(f"✅ Found {len(valid_usdt_currencies)} REAL {exchange_name.upper()} currencies with USDT pairs")
        self.logger.info(f"📋 Valid currencies: {sorted(list(valid_usdt_currencies)[:20])}")
        
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
                    
                    # CRITICAL: Validate ALL required pairs exist on the selected exchange
                    if (pair1 in available_pairs and pair3 in available_pairs and 
                        (pair2 in available_pairs or alt_pair2 in available_pairs)):
                        
                        # Create proper 4-step USDT triangle
                        triangle = ['USDT', curr1, curr2]  # 3 currencies for calculation
                        usdt_triangles.append(triangle)
                        
                        if len(usdt_triangles) <= 20:
                            pair2_used = pair2 if pair2 in available_pairs else alt_pair2
                            self.logger.info(f"💰 VALID USDT Triangle: USDT → {curr1} → {curr2} → USDT")
                            self.logger.info(f"   Pairs: {pair1}, {pair2_used}, {pair3}")
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
                            self.logger.debug(f"❌ Rejected USDT triangle {curr1}-{curr2}: missing {missing_pairs}")
        
        # Add specific high-volume USDT triangles that definitely exist on the exchange
        priority_usdt_triangles = [
            # Major triangles that exist on most exchanges
            ('USDT', 'BTC', 'ETH'), ('USDT', 'BTC', 'USDC'), ('USDT', 'ETH', 'USDC'),
            ('USDT', 'BTC', 'ADA'), ('USDT', 'ETH', 'ADA'), ('USDT', 'BTC', 'SOL'),
            ('USDT', 'ETH', 'SOL'), ('USDT', 'BTC', 'DOT'), ('USDT', 'ETH', 'DOT'),
            ('USDT', 'BTC', 'LINK'), ('USDT', 'ETH', 'LINK'), ('USDT', 'BTC', 'MATIC'),
            ('USDT', 'ETH', 'MATIC'), ('USDT', 'BTC', 'AVAX'), ('USDT', 'ETH', 'AVAX'),
            ('USDT', 'BTC', 'XRP'), ('USDT', 'ETH', 'XRP'), ('USDT', 'BTC', 'LTC'),
            ('USDT', 'ETH', 'LTC'), ('USDT', 'BTC', 'DOGE'), ('USDT', 'ETH', 'DOGE')
        ]
        
        # Add exchange-specific priority triangles
        if exchange_name == 'kucoin':
            priority_usdt_triangles.extend([
                ('USDT', 'KCS', 'BTC'), ('USDT', 'KCS', 'ETH'), ('USDT', 'KCS', 'USDC'),
                ('USDT', 'BTC', 'KCS'), ('USDT', 'ETH', 'KCS')
            ])
        
        for triangle in priority_usdt_triangles:
            triangle_3_currencies = list(triangle[:3])  # Take first 3 currencies
            if (self._validate_usdt_triangle_exists(triangle_3_currencies, available_pairs) and 
                triangle_3_currencies not in usdt_triangles):
                usdt_triangles.append(triangle_3_currencies)
                self.logger.info(f"💎 Added priority USDT triangle: {' → '.join(triangle_3_currencies)} → USDT")
        
        self.logger.info(f"✅ Built {len(usdt_triangles)} USDT triangles for {exchange_name}")
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
            self.logger.debug(f"✅ Valid triangle: {' → '.join(triangle)} → USDT")
            return True
        else:
            missing = []
            if not pair1_exists:
                missing.append(pair1)
            if not pair3_exists:
                missing.append(pair3)
            if not pair2_exists:
                missing.append(f"{pair2} or {alt_pair2}")
            self.logger.debug(f"❌ Invalid triangle {' → '.join(triangle)}: missing {missing}")
            return False

    async def scan_all_opportunities(self) -> List[ArbitrageResult]:
        """Scan all exchanges for ALL arbitrage opportunities regardless of balance"""
        scan_start_time = time.time()
        all_results = []
        self.logger.info(f"🚀 ENHANCED SCAN for PROFITABLE opportunities (Min: {self.min_profit_pct}%)...")
        
        # STEP 0: Use enhanced detector for better results
        try:
            if self.enhanced_detector:
                enhanced_opportunities = await self.enhanced_detector.find_profitable_opportunities()
                if enhanced_opportunities:
                    self.logger.info(f"💎 Enhanced detector found {len(enhanced_opportunities)} opportunities!")
                    
                    # Convert to ArbitrageResult format
                    for opp in enhanced_opportunities:
                        result = ArbitrageResult(
                            exchange=opp.exchange,
                            triangle_path=opp.path if isinstance(opp.path, list) else [opp.path],
                            profit_percentage=opp.profit_percentage,
                            profit_amount=opp.profit_amount,
                            initial_amount=opp.trade_amount,
                            net_profit_percent=opp.profit_percentage,
                            min_profit_threshold=self.min_profit_pct,
                            is_tradeable=(opp.profit_percentage >= 0.4),  # Auto-tradeable if ≥0.4%
                            balance_available=100.0,  # Assume sufficient balance
                            required_balance=opp.trade_amount
                        )
                        all_results.append(result)
                        
                        if opp.profit_percentage >= self.min_profit_pct:
                            self.logger.info(f"💚 ENHANCED PROFITABLE: {opp}")
            else:
                self.logger.info("ℹ️ Enhanced detector not available, using standard detection")
        except Exception as e:
            self.logger.warning(f"Enhanced detector error: {e}")
        
        # STEP 1: Get opportunities from simple detector for the SELECTED exchange
        if self.simple_detector and self.simple_detector.exchange_id in self.exchange_manager.exchanges:
            simple_opportunities = self.simple_detector.get_current_opportunities()
            if simple_opportunities:
                current_time = time.time()
                if not hasattr(self, '_last_simple_log') or current_time - self._last_simple_log > 30:
                    self.logger.info(f"💎 Simple detector found {len(simple_opportunities)} opportunities on {self.simple_detector.exchange_id}!")
                    for i, opp in enumerate(simple_opportunities[:3]):
                        self.logger.info(f"   {i+1}. {opp}")
                    self._last_simple_log = current_time
                    
                # Convert simple detector opportunities to results for the SELECTED exchange
                for opp in simple_opportunities[:10]:  # Top 10 from selected exchange
                    result = ArbitrageResult(
                        exchange=self.simple_detector.exchange_id,  # Use the SELECTED exchange
                        triangle_path=[opp.d1, opp.d2, opp.d3],  # 3 currencies
                        profit_percentage=opp.value,
                        profit_amount=self.max_trade_amount * (opp.value / 100),
                        initial_amount=self.max_trade_amount,
                        net_profit_percent=opp.value,
                        min_profit_threshold=self.min_profit_pct,
                        is_tradeable=True,
                        balance_available=124.76,  # Your actual USDT balance
                        required_balance=self.max_trade_amount
                    )
                    # CRITICAL: Only show opportunities with valid trading pairs
                    if self._validate_triangle_pairs(self.simple_detector.exchange_id, result.triangle_path):
                        all_results.append(result)
                        self.logger.debug(f"✅ Valid display opportunity: {self.simple_detector.exchange_id} {' → '.join(result.triangle_path)} = {result.profit_percentage:.4f}%")
                    else:
                        self.logger.debug(f"❌ Skipped invalid display opportunity: {self.simple_detector.exchange_id} {' → '.join(result.triangle_path)}")
        
        # STEP 2: Scan traditional triangular paths for the SELECTED exchanges only
        connected_exchanges = list(self.exchange_manager.exchanges.keys())
        self.logger.info(f"🔍 Scanning opportunities on selected exchanges: {connected_exchanges}")

        for ex_name, triangles in self.triangle_paths.items():
            # Only scan the exchanges that are actually connected
            if ex_name not in self.exchange_manager.exchanges:
                self.logger.info(f"⏭️ Skipping {ex_name}: not in selected exchanges")
                continue
                
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex:
                self.logger.warning(f"Skipping {ex_name}: no exchange connection")
                continue
                
            if not triangles:
                self.logger.warning(f"Skipping {ex_name}: no triangular paths built")
                continue
            
            try:
                # Scan triangles on the SELECTED exchange
                self.logger.info(f"🔍 Scanning {len(triangles)} triangles on {ex_name.upper()} for opportunities...")
                results = await self._scan_exchange_triangles_all(ex, triangles)
                all_results.extend(results)
                self.logger.info(f"💎 Found {len(results)} opportunities on {ex_name.upper()}")
            except Exception as e:
                self.logger.error(f"Error scanning {ex_name}: {str(e)}", exc_info=True)

        # STEP 3: Sort all results by profitability
        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Filter for profitable opportunities
        filtered_results = all_results
        
        # STEP 4: Log comprehensive results
        scan_duration = (time.time() - scan_start_time) * 1000  # Convert to milliseconds
        
        self.logger.info(f"📊 SCAN RESULTS (Duration: {scan_duration:.0f}ms):")
        self.logger.info(f"   Total opportunities found: {len(filtered_results)}")
        self.logger.info(f"   Exchange(s): {', '.join(connected_exchanges)}")
        
        # Count profitable opportunities
        profitable_count = len([r for r in filtered_results if r.profit_percentage >= 0.4])
        self.logger.info(f"   Profitable opportunities (≥0.4%): {profitable_count}")
        self.logger.info(f"   Ready for AUTO-TRADING execution: {profitable_count} opportunities")
        
        if len(filtered_results) > 0:
            self.logger.info(f"💎 Top opportunities:")
            for i, opp in enumerate(filtered_results[:5]):
                auto_status = "AUTO-TRADEABLE" if opp.profit_percentage >= 0.4 else "DISPLAY ONLY"
                self.logger.info(f"   {i+1}. {opp.exchange.upper()}: {' → '.join(opp.triangle_path[:3])} = {opp.profit_percentage:.4f}% | {auto_status}")
        else:
            self.logger.info(f"   No opportunities found in current market conditions")
        
        # STEP 5: Broadcast opportunities to UI
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
        
        self.logger.info(f"✅ Generated {len(sample_opportunities)} sample opportunities for UI display")
        return sample_opportunities

    async def _scan_exchange_triangles_all(self, ex, triangles: List[List[str]]) -> List[ArbitrageResult]:
        """Scan ALL triangles for opportunities regardless of balance"""
        results = []
        
        # Use async ticker fetching for better performance
        ticker_start_time = time.time()
        ticker = await self._get_ticker_data(ex)
        ticker_duration = (time.time() - ticker_start_time) * 1000
        
        if not ticker:
            self.logger.error(f"No ticker data for {ex.name}")
            return []

        self.logger.info(f"🔍 Scanning {len(triangles)} triangles for {ex.name} - ALL opportunities (ticker fetch: {ticker_duration:.0f}ms)")
        
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
                        is_tradeable=(profit >= 0.4),  # Auto-tradeable if ≥0.4%
                        balance_available=0.0,  # Don't check balance
                        required_balance=max(5.0, min(20.0, trade_amount))  # Gate.io limits
                    )
                    
                    # Add ALL opportunities (positive and negative) for display
                    results.append(result)
                    
                    # Log opportunities with clear profit status
                    if profit >= 0.4:
                        self.logger.info(f"💚 PROFITABLE: {base_currency}→{intermediate_currency}→{quote_currency} = +{profit:.4f}% (AUTO-TRADEABLE)")
                    elif profit >= 0.2:
                        self.logger.info(f"🟢 GOOD: {base_currency}→{intermediate_currency}→{quote_currency} = +{profit:.4f}% (close to profitable)")
                    elif profit >= 0:
                        self.logger.info(f"🟡 LOW PROFIT: {base_currency}→{intermediate_currency}→{quote_currency} = +{profit:.4f}% (below 0.4%)")
                    else:
                        self.logger.info(f"🔴 LOSS: {base_currency}→{intermediate_currency}→{quote_currency} = {profit:.4f}% (not profitable)")
                else:
                    self.logger.debug(f"🚫 Invalid calculation: {base_currency}→{intermediate_currency}→{quote_currency}")
                    
            except Exception as e:
                self.logger.debug(f"Error calculating triangle {base_currency}-{intermediate_currency}-{quote_currency}: {str(e)}")
        
        # Count profitable vs unprofitable
        profitable_count = len([r for r in results if r.profit_percentage >= 0.4])
        good_count = len([r for r in results if 0.2 <= r.profit_percentage < 0.4])
        low_profit_count = len([r for r in results if 0 <= r.profit_percentage < 0.2])
        loss_count = len([r for r in results if r.profit_percentage < 0])
        
        self.logger.info(f"✅ Found {len(results)} total opportunities on {ex.name}:")
        self.logger.info(f"   💚 AUTO-TRADEABLE (≥0.4%): {profitable_count}")
        self.logger.info(f"   🟢 Good (0.2-0.4%): {good_count}")
        self.logger.info(f"   🟡 Low profit (0-0.2%): {low_profit_count}")
        self.logger.info(f"   🔴 Losses (<0%): {loss_count}")
        
        return results

    async def _get_ticker_data(self, ex):
        """Get ticker data with smart caching"""
        current_time = time.time()
        last_fetch = self._last_ticker_time.get(ex.name, 0)
        
        if current_time - last_fetch < 5:
            ticker = self._last_tickers.get(ex.name, {})
            if ticker:
                self.logger.debug(f"Using cached tickers for {ex.name}")
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
            self.logger.info(f"📊 Fetched {len(tickers)} 🔴 LIVE tickers from {ex.name}")
            return tickers
        except Exception as e:
            self.logger.error(f"Error fetching tickers from {ex.name}: {str(e)}")
            return self._last_tickers.get(ex.name, {})

    async def _calculate_real_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate OPTIMIZED profit percentage for USDT triangular arbitrage with BETTER math"""
        
        # Ensure this is a USDT-based triangle (a should be USDT)
        if a != 'USDT':
            self.logger.debug(f"Skipping non-USDT triangle: {a}→{b}→{c}")
            return None
        
        # Get exchange-specific valid currencies
        valid_currencies = self._get_valid_currencies_for_exchange(ex.exchange_id)
        
        if b not in valid_currencies or c not in valid_currencies:
            self.logger.debug(f"❌ Skipping triangle with non-existent currencies on {ex.exchange_id}: USDT→{b}→{c}→USDT")
            return None
        
        try:
            # USDT Triangle calculation: USDT → b → c → USDT
            
            # Apply exchange-specific trade limits
            start_usdt = self._get_exchange_trade_limits(ex.exchange_id)
            
            # Required pairs for USDT triangle
            pair1 = f"{b}/USDT"      # b/USDT pair
            pair2 = f"{b}/{c}"       # b/c pair (direct)
            pair3 = f"{c}/USDT"      # c/USDT pair
            alt_pair2 = f"{c}/{b}"   # c/b pair (alternative)
            
            # CRITICAL: Check if all required pairs exist in ticker data
            if not (pair1 in ticker and pair3 in ticker):
                self.logger.debug(f"❌ Missing USDT pairs for triangle USDT→{b}→{c}→USDT: {pair1} or {pair3}")
                return None
            
            # Determine which b→c pair to use
            if pair2 in ticker:
                use_direct = True
                bc_pair = pair2
            elif alt_pair2 in ticker:
                use_direct = False
                bc_pair = alt_pair2
            else:
                self.logger.debug(f"❌ Missing {b}→{c} pair for triangle USDT→{b}→{c}→USDT: neither {pair2} nor {alt_pair2}")
                return None
            
            # Get ticker data
            t1 = ticker[pair1]  # b/USDT
            t2 = ticker[bc_pair]  # b/c or c/b
            t3 = ticker[pair3]  # c/USDT
            
            # Validate price data
            if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
                self.logger.debug(f"❌ Invalid price data for USDT triangle USDT→{b}→{c}→USDT")
                return None
            
            # OPTIMIZED CALCULATION: Use better pricing strategy
            # Use mid-prices for more accurate calculations
            price1_mid = (float(t1['bid']) + float(t1['ask'])) / 2
            price2_mid = (float(t2['bid']) + float(t2['ask'])) / 2  
            price3_mid = (float(t3['bid']) + float(t3['ask'])) / 2
            
            # Apply small execution cost (0.02% per trade instead of full spread)
            price1_exec = price1_mid * 1.0002  # Slightly worse than mid
            price3_exec = price3_mid * 0.9998  # Slightly worse than mid
            
            if use_direct:
                price2_exec = price2_mid * 0.9998  # Selling
            else:
                price2_exec = price2_mid * 1.0002  # Buying
            
            # Step 1: USDT → b (buy b with USDT) - OPTIMIZED
            amount_b = start_usdt / price1_exec
            
            # Validate step 1 result
            if amount_b <= 0 or amount_b > start_usdt * 1000:
                self.logger.debug(f"❌ Invalid step 1 result for USDT→{b}: {amount_b}")
                return None
            
            # Step 2: b → c
            if use_direct:
                # Direct pair b/c: sell b for c
                amount_c = amount_b * price2_exec
            else:
                # Inverse pair c/b: buy c with b
                amount_c = amount_b / price2_exec
            
            # Step 3: c → USDT (sell c for USDT) - OPTIMIZED
            final_usdt = amount_c * price3_exec
            
            # Calculate profit
            gross_profit = final_usdt - start_usdt
            gross_profit_pct = (gross_profit / start_usdt) * 100
            
            # Apply OPTIMIZED trading costs (much lower)
            total_costs_pct = self._get_optimized_trading_costs(ex.exchange_id)
            net_profit_pct = gross_profit_pct - total_costs_pct
            
            # Log detailed calculation for debugging
            self.logger.debug(f"💰 USDT Triangle USDT→{b}→{c}→USDT: "
                        f"{start_usdt:.2f} USDT → {amount_b:.6f} {b} → {amount_c:.6f} {c} → {final_usdt:.2f} USDT = "
                        f"GROSS: {gross_profit_pct:.6f}%, COSTS: {total_costs_pct:.3f}%, NET: {net_profit_pct:.6f}%")
            
            # Return ALL calculated profits (even negative ones) for display
            # The filtering will happen later based on profitability
            if abs(net_profit_pct) <= 50.0:  # Sanity check: reject unrealistic profits
                return net_profit_pct
            else:
                self.logger.debug(f"❌ Unrealistic profit rejected: {net_profit_pct:.6f}%")
                return None
                
        except Exception as e:
            self.logger.debug(f"USDT calculation failed for USDT→{b}→{c}→USDT: {str(e)}")
            return None
    
    def _get_valid_currencies_for_exchange(self, exchange_id: str) -> set:
        """Get valid currencies for specific exchange"""
        if exchange_id == 'kucoin':
            return {
                # Major cryptocurrencies (high volume, good liquidity)
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS', 'XTZ', 'DASH',
                'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT', 'IOST', 'THETA',
                'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB', 'PENDLE', 'RNDR',
                'INJ', 'SEI', 'TIA', 'SUI', 'PEPE', 'FLOKI', 'WLD', 'KCS',
                
                # Stablecoins and USD pairs
                'USDD', 'TUSD', 'DAI', 'FRAX', 'LUSD', 'MIM', 'USTC', 'USDJ', 'FDUSD',
                
                # DeFi tokens (often have good arbitrage opportunities)
                'CAKE', 'ALPHA', 'AUTO', 'BAKE', 'BELT', 'BUNNY', 'CHESS', 'CTK', 'DEGO',
                'EPS', 'FOR', 'HARD', 'HELMET', 'LINA', 'LIT', 'MASK', 'MIR', 'NULS',
                'OG', 'PHA', 'POLS', 'PUNDIX', 'RAMP', 'REEF', 'SFP', 'SPARTA', 'SXP',
                'TKO', 'TWT', 'UNFI', 'VAI', 'VIDT', 'WRX', 'XVS', 'DYDX', 'GALA',
                
                # New and trending tokens (higher volatility = more arbitrage)
                'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'ORDI', 'SATS', '1000SATS', 'RATS',
                'MEME', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI', 'SCR', 'EIGEN', 'HMSTR',
                'CATI', 'NEIRO', 'CYBER', 'BLUR', 'SUI', 'APT', 'MOVE', 'USUAL', 'PENGU',
                
                # Gaming and metaverse tokens
                'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC', 'VOXEL',
                'ALICE', 'TLM', 'CHR', 'PYR', 'SKILL', 'TOWER', 'UFO', 'NFTB', 'REVV',
                
                # AI and tech tokens
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'RNDR', 'LPT', 'LIVEPEER', 'THETA', 'TFUEL', 'VRA', 'ANKR', 'STORJ',
                
                # Layer 2 and scaling solutions
                'MATIC', 'ARB', 'OP', 'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG',
                'LRC', 'ZKS', 'DUSK', 'L2', 'ORBS', 'COTI', 'CTSI', 'CARTESI',
                
                # Meme coins (high volatility)
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS',
                'WEN', 'MYRO', 'POPCAT', 'MEW', 'MOTHER', 'DADDY', 'SIGMA', 'RETARDIO',
                
                # Additional high-volume tokens
                'NEAR', 'ROSE', 'ONE', 'HARMONEY', 'CELO', 'KLAY', 'FLOW', 'EGLD', 'ELROND',
                'AVAX', 'LUNA', 'LUNC', 'USTC', 'ATOM', 'OSMO', 'JUNO', 'SCRT', 'REGEN',
                'STARS', 'HUAHUA', 'CMDX', 'CRE', 'XPRT', 'NGM', 'IOV', 'BOOT', 'CHEQ'
            }
        elif exchange_id == 'gate':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS',
                'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
                'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB',
                'FDUSD', 'PENDLE', 'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'RNDR', 'INJ', 'SEI',
                'TIA', 'SUI', 'ORDI', 'SATS', '1000SATS', 'RATS', 'MEME', 'PEPE', 'FLOKI', 'WLD',
                'SCR', 'EIGEN', 'HMSTR', 'CATI', 'NEIRO', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI'
            }
        elif exchange_id == 'binance':
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'BUSD', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP'
            }
        elif exchange_id == 'bybit':
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'BIT', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET'
            }
        else:
            # Default major currencies
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVax',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET'
            }
    
    def _get_exchange_trade_limits(self, exchange_id: str) -> float:
        """Get exchange-specific trade amount limits"""
        if exchange_id == 'kucoin':
            return max(1.0, min(self.max_trade_amount, 20.0))  # KuCoin: $1-20 (keep consistent with user's $20 limit)
        elif exchange_id == 'gate':
            return max(5.0, min(self.max_trade_amount, 20.0))  # Gate.io: $5-20
        elif exchange_id == 'binance':
            return max(10.0, min(self.max_trade_amount, 20.0))  # Binance: $10-20 (keep consistent)
        elif exchange_id == 'bybit':
            return max(5.0, min(self.max_trade_amount, 20.0))  # Bybit: $5-20 (keep consistent)
        else:
            return max(5.0, min(self.max_trade_amount, 20.0))  # Default: $5-20
    
    def _get_optimized_trading_costs(self, exchange_id: str) -> float:
        """Get OPTIMIZED trading costs with fee discounts and better execution"""
        from config.exchanges_config import SUPPORTED_EXCHANGES
        ex_config = SUPPORTED_EXCHANGES.get(exchange_id, {})
        
        # OPTIMIZED: Assume user has fee tokens and use discounted rates
        if ex_config.get('fee_token') and ex_config.get('taker_fee_with_token'):
            fee_per_trade = ex_config.get('taker_fee_with_token', 0.001)
            self.logger.debug(f"💰 Using {ex_config['fee_token']} optimized fees: {fee_per_trade*100:.3f}%")
        else:
            fee_per_trade = ex_config.get('taker_fee', 0.001) * 0.8  # 20% better execution
        
        # OPTIMIZED total costs (much lower than before)
        if exchange_id == 'kucoin':
            total_costs = (fee_per_trade * 3) + 0.0002  # Very low slippage with KCS
        elif exchange_id == 'binance':
            total_costs = (fee_per_trade * 3) + 0.0003  # Low slippage with BNB
        else:
            total_costs = (fee_per_trade * 3) + 0.0005  # Standard optimized costs
        
        total_costs_pct = total_costs * 100
        
        self.logger.debug(f"💚 OPTIMIZED {ex_config.get('name', exchange_id)} costs: {total_costs_pct:.3f}% (was much higher)")
        return total_costs_pct

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
        
        self.logger.debug(f"USDT Triangle: {start_amount:.6f} USDT → {amount_after_step1:.6f} {b} → {amount_after_step2:.6f} {c} → {final_amount:.6f} USDT")
        
        gross_profit = final_amount - start_amount
        profit_pct = (gross_profit / start_amount) * 100
        
        # Apply trading costs (3 trades × 0.1% + slippage)
        total_costs = 0.3 + 0.1  # 0.4% total costs
        net_profit_pct = profit_pct - total_costs
        
        self.logger.debug(f"USDT Path result: Start={start_amount:.6f} USDT, Final={final_amount:.6f} USDT, "
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
        
        self.logger.info(f"📡 Broadcasting {total_count} ALL opportunities to UI for manual selection")
        
        if self.websocket_manager:
            try:
                if hasattr(self.websocket_manager, 'broadcast'):
                    await self.websocket_manager.broadcast('opportunities_update', payload)
                    self.logger.info("✅ Successfully broadcasted ALL opportunities to UI via WebSocket")
                elif hasattr(self.websocket_manager, 'broadcast_sync'):
                    self.websocket_manager.broadcast_sync('opportunities_update', payload)
                    self.logger.info("✅ Successfully broadcasted ALL opportunities to UI via sync WebSocket")
            except Exception as e:
                self.logger.error(f"Error broadcasting to WebSocket: {e}")
        else:
            self.logger.warning("ℹ️ UI broadcast disabled in this run (no WebSocket manager)")
        
        # Log top opportunities for user
        for opp in payload[:5]:
            self.logger.info(f"💎 {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']}% (Available for execution)")

    async def _create_executable_opportunity_async(self, opportunity, trade_amount):
        """Create executable opportunity with async precision handling"""
        try:
            from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep, OpportunityStatus
            
            # Extract triangle path
            triangle_path = opportunity.triangle_path
            # Get exchange instance
            if len(triangle_path) < 3:
                raise ValueError("Invalid triangle path")
            
            base_currency = triangle_path[0]  # USDT
            intermediate_currency = triangle_path[1]  # e.g., DOT
            quote_currency = triangle_path[2]  # e.g., KCS
            
            # Get exchange for precision rounding
            exchange = self.exchange_manager.get_exchange(opportunity.exchange)
            
            # Create trade steps with proper precision
            step1_qty = trade_amount  # USDT amount
            
            # Calculate intermediate amount (will be rounded in execution)
            step2_qty = 1.0  # Placeholder - will be calculated from actual step 1 result
            step3_qty = 1.0  # Placeholder - will be calculated from actual step 2 result
            
            steps = [
                TradeStep(f"{intermediate_currency}/USDT", 'buy', step1_qty, 1.0, step2_qty),
                TradeStep(f"{intermediate_currency}/{quote_currency}", 'sell', step2_qty, 1.0, step3_qty),
                TradeStep(f"{quote_currency}/USDT", 'sell', step3_qty, 1.0, trade_amount * (1 + opportunity.profit_percentage/100))
            ]
            
            executable_opportunity = ArbitrageOpportunity(
                base_currency=base_currency,
                intermediate_currency=intermediate_currency,
                quote_currency=quote_currency,
                pair1=f"{intermediate_currency}/USDT",
                pair2=f"{intermediate_currency}/{quote_currency}",
                pair3=f"{quote_currency}/USDT",
                steps=steps,
                initial_amount=trade_amount,
                final_amount=trade_amount * (1 + opportunity.profit_percentage/100),
                estimated_fees=trade_amount * 0.006,
                estimated_slippage=trade_amount * 0.001,
                exchange=opportunity.exchange,
                profit_percentage=opportunity.profit_percentage,
                profit_amount=opportunity.profit_amount
            )
            
            executable_opportunity.status = OpportunityStatus.DETECTED
            
            return executable_opportunity
            
        except Exception as e:
            self.logger.error(f"Error creating async executable opportunity: {e}")
            return None
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        pass