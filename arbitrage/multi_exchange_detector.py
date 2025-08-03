#!/usr/bin/env python3
"""
LIVE TRADING Triangular Arbitrage Detector with Enhanced Balance Display
"""

import asyncio
import time
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass
from arbitrage.realtime_detector import RealtimeArbitrageDetector

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
    
    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable above threshold."""
        return self.net_profit_percent > self.min_profit_threshold and self.profit_percentage > 0

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
            if not balance or balance.get('total_usd', 0) <= 0:
                logger.warning(f"⚠️ No balance detected on {ex_name} - please verify API permissions")
        
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
            balance_data = await ex.fetch_complete_balance()
            
            if not balance_data or not balance_data.get('balances'):
                logger.error("❌ No balance data retrieved")
                return {}
                
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
        major_list = list(major_found)
        
        for i, curr_a in enumerate(major_list):
            for j, curr_b in enumerate(major_list):
                if i >= j:
                    continue
                for k, curr_c in enumerate(major_list):
                    if k >= j or k == i:
                        continue
                    
                    possible_pairs = [
                        f"{curr_a}/{curr_b}", f"{curr_b}/{curr_a}",
                        f"{curr_b}/{curr_c}", f"{curr_c}/{curr_b}",
                        f"{curr_a}/{curr_c}", f"{curr_c}/{curr_a}"
                    ]
                    
                    existing_pairs = [p for p in possible_pairs if p in available_pairs]
                    
                    if len(existing_pairs) >= 3:
                        triangle = self._try_build_triangle_path(curr_a, curr_b, curr_c, available_pairs)
                        if triangle:
                            triangles.append(triangle)
                            if len(triangles) <= 20:
                                logger.info(f"💰 Triangle: {' → '.join(triangle[:3])}")
        
        specific_triangles = [
            ('BTC', 'ETH', 'USDT'), ('BTC', 'BNB', 'USDT'), ('ETH', 'BNB', 'USDT'),
            ('BTC', 'ADA', 'USDT'), ('ETH', 'ADA', 'USDT'), ('BTC', 'SOL', 'USDT'),
            ('ETH', 'SOL', 'USDT'), ('BNB', 'ADA', 'USDT'), ('BNB', 'SOL', 'USDT'),
            ('BTC', 'ETH', 'USDC'), ('BTC', 'BNB', 'USDC'), ('ETH', 'BNB', 'USDC'),
            ('BTC', 'ETH', 'BUSD'), ('BTC', 'BNB', 'BUSD'), ('ETH', 'BNB', 'BUSD'),
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
        """Scan all exchanges for REAL profitable arbitrage opportunities"""
        all_results = []
        logger.info(f"🔍 Starting LIVE TRADING scan (Max: ${self.max_trade_amount}, Min Profit: {self.min_profit_pct}%)...")
        
        if 'binance' in self.exchange_manager.exchanges and self.realtime_detector.running:
            logger.info("📡 Using real-time WebSocket data for Binance")

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

        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        profitable_results = [
            result for result in all_results 
            if result.profit_percentage >= self.min_profit_pct and result.initial_amount <= self.max_trade_amount
        ]
        
        filtered_by_profit = len([r for r in all_results if r.profit_percentage < self.min_profit_pct])
        filtered_by_amount = len([r for r in all_results if r.initial_amount > self.max_trade_amount])
        
        logger.info(f"💎 FILTERING RESULTS:")
        logger.info(f"   Total found: {len(all_results)}")
        logger.info(f"   Filtered by profit (<{self.min_profit_pct}%): {filtered_by_profit}")
        logger.info(f"   Filtered by amount (>${self.max_trade_amount}): {filtered_by_amount}")
        logger.info(f"   ✅ VALID OPPORTUNITIES: {len(profitable_results)}")
        
        await self._broadcast_opportunities(profitable_results)
        
        return profitable_results

    async def _scan_exchange_triangles(self, ex, triangles: List[List[str]]) -> List[ArbitrageResult]:
        """Scan triangles for REAL profitable opportunities"""
        results = []
        
        ticker = await self._get_ticker_data(ex)
        if not ticker:
            logger.warning(f"No ticker data for {ex.name}")
            return []

        logger.info(f"🔍 Scanning {len(triangles)} REAL triangles for {ex.name}")
        
        if hasattr(self, 'realtime_detector') and self.realtime_detector:
            try:
                realtime_stats = self.realtime_detector.get_statistics()
                if realtime_stats.get('opportunities_found', 0) > 0:
                    logger.info(f"📡 Real-time detector found {realtime_stats['opportunities_found']} opportunities")
            except Exception as e:
                logger.debug(f"Could not get real-time detector stats: {e}")
        
        for i, path in enumerate(triangles):
            a, b, c, _ = path
            try:
                if self.max_trade_amount > 100.0:
                    logger.warning(f"🚫 Trade amount ${self.max_trade_amount} exceeds $100 limit, capping at $100")
                    trade_amount = 100.0
                else:
                    trade_amount = self.max_trade_amount
                
                profit = await self._calculate_real_triangle_profit(ex, ticker, a, b, c)
                
                if profit and profit >= self.min_profit_pct and trade_amount <= 100.0:
                    result = ArbitrageResult(
                        exchange=ex.name,
                        triangle_path=path,
                        profit_percentage=profit,
                        profit_amount=(trade_amount * profit / 100),
                        initial_amount=trade_amount,
                        net_profit_percent=profit,
                        min_profit_threshold=self.min_profit_pct
                    )
                    results.append(result)
                    logger.info(f"💰 VALID OPPORTUNITY: {a}→{b}→{c} = {profit:.4f}% profit (${trade_amount})")
                elif profit and profit < self.min_profit_pct:
                    logger.debug(f"🚫 REJECTED (low profit): {a}→{b}→{c} = {profit:.4f}% < {self.min_profit_pct}%")
                elif trade_amount > 100.0:
                    logger.debug(f"🚫 REJECTED (high amount): {a}→{b}→{c} = ${trade_amount} > $100")
                else:
                    logger.debug(f"🚫 REJECTED: {a}→{b}→{c} = {profit:.4f}%")
            except Exception as e:
                logger.debug(f"Skipping triangle {a}-{b}-{c}: {str(e)}")
        
        logger.info(f"✅ Found {len(results)} VALID opportunities on {ex.name} (≥{self.min_profit_pct}%, ≤$100)")
        return results

    async def _calculate_real_triangle_profit(self, ex, ticker, a: str, b: str, c: str) -> float:
        """Calculate REAL profit percentage using live market data"""
        try:
            possible_combinations = [
                {
                    'pairs': [f"{a}/{b}", f"{b}/{c}", f"{a}/{c}"],
                    'operations': ['sell_a_for_b', 'sell_b_for_c', 'buy_a_with_c']
                },
                {
                    'pairs': [f"{a}/{c}", f"{c}/{b}", f"{a}/{b}"],
                    'operations': ['sell_a_for_c', 'sell_c_for_b', 'buy_a_with_b']
                },
                {
                    'pairs': [f"{b}/{a}", f"{b}/{c}", f"{a}/{c}"],
                    'operations': ['buy_b_with_a', 'sell_b_for_c', 'buy_a_with_c']
                },
                {
                    'pairs': [f"{a}/{b}", f"{c}/{b}", f"{a}/{c}"],
                    'operations': ['sell_a_for_b', 'buy_b_with_c', 'sell_a_for_c']
                }
            ]
            
            best_profit = -999.0
            
            for combo in possible_combinations:
                pairs = combo['pairs']
                operations = combo['operations']
                
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

    def _calculate_path_profit(self, ticker, pairs: List[str], operations: List[str], a: str, b: str, c: str) -> float:
        """Calculate profit for a specific path"""
        start_amount = self.max_trade_amount
        
        t1, t2, t3 = ticker[pairs[0]], ticker[pairs[1]], ticker[pairs[2]]
        
        if not all(t.get('bid') and t.get('ask') for t in [t1, t2, t3]):
            raise ValueError("Invalid price data")
        
        # Step 1: First trade
        if operations[0] == 'sell_a_for_b':
            price1 = float(t1['bid'])
            amount_after_step1 = start_amount * price1
        elif operations[0] == 'buy_b_with_a':
            price1 = float(t1['ask'])
            amount_after_step1 = start_amount / price1
        else:
            raise ValueError(f"Invalid operation: {operations[0]}")
        
        # Step 2: Second trade
        if operations[1] == 'sell_b_for_c':
            price2 = float(t2['bid'])
            amount_after_step2 = amount_after_step1 * price2
        elif operations[1] == 'buy_b_with_c':
            price2 = float(t2['ask'])
            amount_after_step2 = amount_after_step1 / price2
        else:
            raise ValueError(f"Invalid operation: {operations[1]}")
        
        # Step 3: Third trade
        if operations[2] == 'sell_c_for_a':
            price3 = float(t3['bid'])
            final_amount = amount_after_step2 * price3
        elif operations[2] == 'buy_a_with_c':
            price3 = float(t3['ask'])
            final_amount = amount_after_step2 / price3
        else:
            raise ValueError(f"Invalid operation: {operations[2]}")
        
        logger.debug(f"Triangle calculation: {start_amount:.6f} {a} → {amount_after_step1:.6f} {b} → {amount_after_step2:.6f} {c} → {final_amount:.6f} {a}")
        
        gross_profit = final_amount - start_amount
        profit_pct = (gross_profit / start_amount) * 100
        
        total_costs = 0.225 + 0.15 + 0.1  # 0.475% total costs
        net_profit_pct = profit_pct - total_costs
        
        logger.debug(f"Path result: Start={start_amount:.6f}, Final={final_amount:.6f}, "
                    f"Gross={profit_pct:.6f}%, Net={net_profit_pct:.6f}% (after {total_costs}% costs)")
        
        return net_profit_pct

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
        """Format and broadcast REAL opportunities to UI"""
        payload = []
        
        for opp in opportunities:
            if not hasattr(opp, 'is_profitable') or not opp.is_profitable:
                logger.debug(f"🚫 UI FILTER: Non-profitable {opp.profit_percentage:.4f}%")
                continue
                
            if opp.initial_amount > 100.0:
                logger.debug(f"🚫 UI FILTER: Amount ${opp.initial_amount} > $100")
                continue
                
            if opp.profit_percentage < 0.5:
                logger.debug(f"🚫 UI FILTER: Profit {opp.profit_percentage:.4f}% < 0.5%")
                continue
                
            payload.append({
                'id': f"live_{int(datetime.now().timestamp()*1000)}_{len(payload)}",
                'exchange': opp.exchange,
                'trianglePath': " → ".join(opp.triangle_path[:3]),
                'profitPercentage': round(opp.profit_percentage, 4),
                'profitAmount': round(opp.profit_amount, 6),
                'volume': min(opp.initial_amount, 100.0),
                'status': 'detected',
                'dataType': 'LIVE_FILTERED_DATA',
                'timestamp': datetime.now().isoformat()
            })
        
        if payload:
            logger.info(f"📡 Broadcasting {len(payload)} VALID opportunities to UI (≥0.5%, ≤$100)")
        
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
            for opp in payload[:5]:
                logger.info(f"💎 Opportunity: {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']}%")

        return [opp for opp in opportunities if opp.net_profit_percent >= 0.5]

if __name__ == "__main__":
    from exchange_manager import ExchangeManager
    
    async def main():
        config = {
            'min_profit_percentage': 0.5,
            'max_trade_amount': 100.0,
            'api_key': 'YOUR_API_KEY',
            'api_secret': 'YOUR_API_SECRET'
        }
        
        exchange_manager = ExchangeManager(config)
        await exchange_manager.initialize_exchanges(['binance'])
        
        detector = MultiExchangeDetector(
            exchange_manager=exchange_manager,
            websocket_manager=None,
            config=config
        )
        
        # Test balance display
        await detector.show_account_balance("binance")
        
        # Initialize normally
        await detector.initialize()
        
        # Run periodic scans
        while True:
            await detector.scan_all_opportunities()
            await asyncio.sleep(60)  # Scan every 60 seconds
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")