#!/usr/bin/env python3
"""
Ultra-Fast Arbitrage Detector
Executes trades within 1-2 seconds of detection to capture real opportunities
"""

import asyncio
import time
import ccxt.async_support as ccxt
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class FastOpportunity:
    """Ultra-fast arbitrage opportunity with immediate execution capability"""
    exchange_id: str
    path: List[str]  # [USDT, Currency1, Currency2]
    pairs: List[str]  # Trading pairs
    profit_percentage: float
    profit_amount: float
    trade_amount: float
    prices: Dict[str, float]
    detected_at: float  # Timestamp
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.detected_at
    
    def __str__(self):
        return f"{self.exchange_id}: {' → '.join(self.path)} = +{self.profit_percentage:.4f}% (${self.profit_amount:.2f}) [Age: {self.age_seconds:.1f}s]"

class UltraFastArbitrageDetector:
    """Ultra-fast arbitrage detector with sub-second execution"""
    
    def __init__(self, min_profit_pct: float = 0.4, max_trade_amount: float = 20.0):
        self.min_profit_pct = min_profit_pct
        self.max_trade_amount = max_trade_amount
        self.logger = logging.getLogger('UltraFastDetector')
        
        # Exchange connections
        self.exchanges = {}
        self.running = False
        
        # Ultra-fast execution
        self.execution_queue = asyncio.Queue()
        self.current_opportunities = []
        
        # Statistics
        self.opportunities_detected = 0
        self.trades_executed = 0
        self.successful_trades = 0
        self.total_profit = 0.0
        
        self.logger.info(f"⚡ Ultra-Fast Arbitrage Detector initialized")
        self.logger.info(f"   Target: Sub-second execution")
        self.logger.info(f"   Min Profit: {min_profit_pct}%")
        self.logger.info(f"   Max Trade: ${max_trade_amount}")
    
    async def initialize_exchange(self, exchange_id: str = 'kucoin') -> bool:
        """Initialize single exchange for ultra-fast trading"""
        try:
            if exchange_id == 'kucoin':
                api_key = os.getenv('KUCOIN_API_KEY', '').strip()
                api_secret = os.getenv('KUCOIN_API_SECRET', '').strip()
                passphrase = os.getenv('KUCOIN_PASSPHRASE', '').strip()
                
                if not all([api_key, api_secret, passphrase]):
                    self.logger.error("❌ Missing KuCoin credentials")
                    return False
                
                self.exchanges[exchange_id] = ccxt.kucoin({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'password': passphrase,
                    'enableRateLimit': True,
                    'sandbox': False,  # LIVE TRADING
                    'options': {'defaultType': 'spot'}
                })
                
            elif exchange_id == 'binance':
                api_key = os.getenv('BINANCE_API_KEY', '').strip()
                api_secret = os.getenv('BINANCE_API_SECRET', '').strip()
                
                if not all([api_key, api_secret]):
                    self.logger.error("❌ Missing Binance credentials")
                    return False
                
                self.exchanges[exchange_id] = ccxt.binance({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'enableRateLimit': True,
                    'sandbox': False,  # LIVE TRADING
                    'options': {'defaultType': 'spot'}
                })
            
            # Test connection
            await self.exchanges[exchange_id].load_markets()
            balance = await self.exchanges[exchange_id].fetch_balance()
            
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            self.logger.info(f"✅ Connected to {exchange_id.upper()}")
            self.logger.info(f"💰 USDT Balance: {usdt_balance:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize {exchange_id}: {e}")
            return False
    
    async def ultra_fast_scan_and_execute(self, exchange_id: str = 'kucoin'):
        """Ultra-fast scan and execute in one operation"""
        self.logger.info(f"⚡ Starting ULTRA-FAST arbitrage on {exchange_id.upper()}")
        self.logger.info(f"   Target: Execute within 1-2 seconds of detection")
        
        exchange = self.exchanges[exchange_id]
        self.running = True
        
        # Start execution worker
        execution_task = asyncio.create_task(self._ultra_fast_executor())
        
        scan_count = 0
        
        try:
            while self.running:
                scan_count += 1
                scan_start = time.time()
                
                self.logger.info(f"⚡ ULTRA-FAST Scan #{scan_count} - {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                
                # Get fresh tickers (this is the bottleneck - optimize it)
                tickers = await exchange.fetch_tickers()
                ticker_time = (time.time() - scan_start) * 1000
                
                if not tickers:
                    await asyncio.sleep(1)
                    continue
                
                # Ultra-fast opportunity detection
                opportunities = await self._ultra_fast_detection(exchange_id, tickers)
                detection_time = (time.time() - scan_start) * 1000
                
                if opportunities:
                    self.logger.info(f"⚡ LIGHTNING FAST: Found {len(opportunities)} opportunities in {detection_time:.0f}ms")
                    
                    # Queue the BEST opportunity for immediate execution
                    best_opportunity = opportunities[0]
                    
                    # Only execute if opportunity is fresh (detected within last 2 seconds)
                    if best_opportunity.age_seconds < 2.0:
                        await self.execution_queue.put(best_opportunity)
                        self.logger.info(f"⚡ QUEUED FOR IMMEDIATE EXECUTION: {best_opportunity}")
                    else:
                        self.logger.warning(f"⚠️ Opportunity too old ({best_opportunity.age_seconds:.1f}s), skipping")
                
                total_scan_time = (time.time() - scan_start) * 1000
                self.logger.info(f"⚡ Scan complete: {total_scan_time:.0f}ms (ticker: {ticker_time:.0f}ms, detection: {detection_time:.0f}ms)")
                
                # Ultra-short delay for maximum speed
                await asyncio.sleep(0.2)  # 200ms between scans
                
        except KeyboardInterrupt:
            self.logger.info("⚡ Ultra-fast scanning stopped by user")
        finally:
            self.running = False
            execution_task.cancel()
    
    async def _ultra_fast_detection(self, exchange_id: str, tickers: Dict[str, Any]) -> List[FastOpportunity]:
        """Ultra-fast opportunity detection with minimal processing"""
        opportunities = []
        detection_start = time.time()
        
        # Focus on only the most liquid triangular paths for speed
        ultra_fast_triangles = [
            ('USDT', 'BTC', 'ETH'),    # Highest liquidity
            ('USDT', 'ETH', 'BTC'),    # Reverse
            ('USDT', 'BTC', 'USDC'),   # Stablecoin arbitrage
            ('USDT', 'ETH', 'USDC'),   # Stablecoin arbitrage
            ('USDT', 'BTC', 'BNB'),    # Major exchange token
            ('USDT', 'ETH', 'BNB'),    # Major exchange token
        ]
        
        # Add exchange-specific high-liquidity triangles
        if exchange_id == 'kucoin':
            ultra_fast_triangles.extend([
                ('USDT', 'KCS', 'BTC'),    # KuCoin native token
                ('USDT', 'KCS', 'ETH'),    # KuCoin native token
                ('USDT', 'BTC', 'KCS'),    # Reverse
                ('USDT', 'ETH', 'KCS'),    # Reverse
            ])
        
        for base, intermediate, quote in ultra_fast_triangles:
            try:
                opportunity = await self._calculate_ultra_fast_profit(
                    exchange_id, tickers, base, intermediate, quote, detection_start
                )
                
                if opportunity and opportunity.profit_percentage >= self.min_profit_pct:
                    opportunities.append(opportunity)
                    self.opportunities_detected += 1
                    
            except Exception as e:
                continue  # Skip errors for speed
        
        # Sort by profit (highest first)
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        return opportunities[:3]  # Return only top 3 for speed
    
    async def _calculate_ultra_fast_profit(self, exchange_id: str, tickers: Dict[str, Any], 
                                         base: str, intermediate: str, quote: str, 
                                         detection_time: float) -> Optional[FastOpportunity]:
        """Ultra-fast profit calculation with minimal overhead"""
        try:
            # Required pairs
            pair1 = f"{intermediate}/{base}"      # e.g., BTC/USDT
            pair2 = f"{intermediate}/{quote}"     # e.g., BTC/ETH
            pair3 = f"{quote}/{base}"             # e.g., ETH/USDT
            
            # Try alternative pair2
            alt_pair2 = f"{quote}/{intermediate}" # e.g., ETH/BTC
            
            # Quick validation - all pairs must exist
            if not (pair1 in tickers and pair3 in tickers):
                return None
            
            # Get pair2 (try both directions)
            if pair2 in tickers:
                use_direct = True
                pair2_symbol = pair2
                t2 = tickers[pair2]
            elif alt_pair2 in tickers:
                use_direct = False
                pair2_symbol = alt_pair2
                t2 = tickers[alt_pair2]
            else:
                return None
            
            # Get ticker data
            t1, t3 = tickers[pair1], tickers[pair3]
            
            # Quick price validation
            prices = [
                (t1.get('bid', 0), t1.get('ask', 0)),
                (t2.get('bid', 0), t2.get('ask', 0)),
                (t3.get('bid', 0), t3.get('ask', 0))
            ]
            
            if not all(bid > 0 and ask > 0 and bid < ask for bid, ask in prices):
                return None
            
            # ULTRA-FAST calculation using mid-prices for speed
            price1 = (float(t1['bid']) + float(t1['ask'])) / 2
            price2 = (float(t2['bid']) + float(t2['ask'])) / 2
            price3 = (float(t3['bid']) + float(t3['ask'])) / 2
            
            # Apply minimal execution cost (0.01% per trade)
            execution_cost = 0.0001  # 0.01% per trade
            price1_exec = price1 * (1 + execution_cost)
            price3_exec = price3 * (1 - execution_cost)
            
            if use_direct:
                price2_exec = price2 * (1 - execution_cost)
            else:
                price2_exec = price2 * (1 + execution_cost)
            
            # Calculate triangle
            start_amount = self.max_trade_amount
            
            # Step 1: base → intermediate
            amount_intermediate = start_amount / price1_exec
            
            # Step 2: intermediate → quote
            if use_direct:
                amount_quote = amount_intermediate * price2_exec
            else:
                amount_quote = amount_intermediate / price2_exec
            
            # Step 3: quote → base
            final_amount = amount_quote * price3_exec
            
            # Calculate profit
            gross_profit = final_amount - start_amount
            gross_profit_pct = (gross_profit / start_amount) * 100
            
            # Apply MINIMAL trading costs for ultra-fast execution
            if exchange_id == 'kucoin':
                total_costs = 0.15  # 0.15% with KCS discount
            elif exchange_id == 'binance':
                total_costs = 0.225  # 0.225% with BNB discount
            else:
                total_costs = 0.3  # 0.3% standard
            
            net_profit_pct = gross_profit_pct - total_costs
            net_profit_amount = start_amount * (net_profit_pct / 100)
            
            # Return opportunity if profitable
            if net_profit_pct >= self.min_profit_pct and abs(net_profit_pct) <= 5.0:
                return FastOpportunity(
                    exchange_id=exchange_id,
                    path=[base, intermediate, quote],
                    pairs=[pair1, pair2_symbol, pair3],
                    profit_percentage=net_profit_pct,
                    profit_amount=net_profit_amount,
                    trade_amount=start_amount,
                    prices={
                        'step1': price1_exec,
                        'step2': price2_exec,
                        'step3': price3_exec,
                        'final_amount': final_amount
                    },
                    detected_at=detection_time
                )
            
            return None
            
        except Exception as e:
            return None
    
    async def _ultra_fast_executor(self):
        """Ultra-fast execution worker - executes trades immediately"""
        self.logger.info("⚡ Ultra-fast executor started - will execute trades within 1 second")
        
        while self.running:
            try:
                # Wait for opportunities with timeout
                opportunity = await asyncio.wait_for(self.execution_queue.get(), timeout=1.0)
                
                # Check if opportunity is still fresh (under 3 seconds old)
                if opportunity.age_seconds > 3.0:
                    self.logger.warning(f"⚠️ Opportunity expired ({opportunity.age_seconds:.1f}s old), skipping")
                    continue
                
                # IMMEDIATE EXECUTION
                self.logger.info(f"⚡ IMMEDIATE EXECUTION: {opportunity}")
                success = await self._execute_ultra_fast_trade(opportunity)
                
                if success:
                    self.trades_executed += 1
                    self.successful_trades += 1
                    self.total_profit += opportunity.profit_amount
                    self.logger.info(f"🎉 ULTRA-FAST TRADE SUCCESS: +${opportunity.profit_amount:.4f} in {opportunity.age_seconds:.1f}s")
                else:
                    self.trades_executed += 1
                    self.logger.error(f"❌ Ultra-fast trade failed")
                
                # Brief pause to avoid overwhelming the exchange
                await asyncio.sleep(0.5)
                
            except asyncio.TimeoutError:
                continue  # No opportunities in queue
            except Exception as e:
                self.logger.error(f"Error in ultra-fast executor: {e}")
                await asyncio.sleep(1)
    
    async def _execute_ultra_fast_trade(self, opportunity: FastOpportunity) -> bool:
        """Execute trade with ultra-fast timing"""
        try:
            exchange = self.exchanges[opportunity.exchange_id]
            execution_start = time.time()
            
            self.logger.info(f"⚡ EXECUTING ULTRA-FAST TRADE:")
            self.logger.info(f"   Path: {' → '.join(opportunity.path)}")
            self.logger.info(f"   Profit: {opportunity.profit_percentage:.4f}%")
            self.logger.info(f"   Age: {opportunity.age_seconds:.1f}s")
            
            # Step 1: USDT → intermediate (e.g., USDT → BTC)
            pair1 = opportunity.pairs[0]  # BTC/USDT
            quantity1 = opportunity.trade_amount  # $20 USDT
            
            self.logger.info(f"⚡ Step 1: Buy {pair1} with ${quantity1}")
            order1 = await exchange.create_market_order(pair1, 'buy', quantity1)
            
            if not order1 or order1.get('status') != 'closed':
                self.logger.error(f"❌ Step 1 failed")
                return False
            
            amount_intermediate = float(order1['filled'])
            self.logger.info(f"✅ Step 1: Got {amount_intermediate:.8f} {opportunity.path[1]}")
            
            # Step 2: intermediate → quote (e.g., BTC → ETH)
            pair2 = opportunity.pairs[1]  # BTC/ETH or ETH/BTC
            
            self.logger.info(f"⚡ Step 2: Trade {pair2}")
            
            if pair2.startswith(opportunity.path[1]):  # Direct pair
                order2 = await exchange.create_market_order(pair2, 'sell', amount_intermediate)
            else:  # Inverse pair
                order2 = await exchange.create_market_order(pair2, 'buy', amount_intermediate)
            
            if not order2 or order2.get('status') != 'closed':
                self.logger.error(f"❌ Step 2 failed")
                return False
            
            amount_quote = float(order2['filled'])
            self.logger.info(f"✅ Step 2: Got {amount_quote:.8f} {opportunity.path[2]}")
            
            # Step 3: quote → USDT (e.g., ETH → USDT)
            pair3 = opportunity.pairs[2]  # ETH/USDT
            
            self.logger.info(f"⚡ Step 3: Sell {pair3}")
            order3 = await exchange.create_market_order(pair3, 'sell', amount_quote)
            
            if not order3 or order3.get('status') != 'closed':
                self.logger.error(f"❌ Step 3 failed")
                return False
            
            final_usdt = float(order3['cost'])
            execution_time = (time.time() - execution_start) * 1000
            
            # Calculate actual profit
            actual_profit = final_usdt - opportunity.trade_amount
            actual_profit_pct = (actual_profit / opportunity.trade_amount) * 100
            
            self.logger.info(f"🎉 ULTRA-FAST TRADE COMPLETED:")
            self.logger.info(f"   Initial: ${opportunity.trade_amount:.2f} USDT")
            self.logger.info(f"   Final: ${final_usdt:.2f} USDT")
            self.logger.info(f"   Actual Profit: ${actual_profit:.4f} ({actual_profit_pct:.4f}%)")
            self.logger.info(f"   Execution Time: {execution_time:.0f}ms")
            self.logger.info(f"   Total Time: {(time.time() - opportunity.detected_at)*1000:.0f}ms from detection")
            
            return actual_profit > 0
            
        except Exception as e:
            self.logger.error(f"❌ Ultra-fast execution failed: {e}")
            return False
    
    async def run(self, exchange_id: str = 'kucoin'):
        """Run the ultra-fast arbitrage bot"""
        if not await self.initialize_exchange(exchange_id):
            return
        
        try:
            await self.ultra_fast_scan_and_execute(exchange_id)
        finally:
            # Cleanup
            for exchange in self.exchanges.values():
                await exchange.close()
            
            # Final stats
            success_rate = (self.successful_trades / max(self.trades_executed, 1)) * 100
            self.logger.info(f"⚡ ULTRA-FAST ARBITRAGE COMPLETED:")
            self.logger.info(f"   Opportunities Detected: {self.opportunities_detected}")
            self.logger.info(f"   Trades Executed: {self.trades_executed}")
            self.logger.info(f"   Successful Trades: {self.successful_trades}")
            self.logger.info(f"   Success Rate: {success_rate:.1f}%")
            self.logger.info(f"   Total Profit: ${self.total_profit:.4f}")

async def main():
    """Test ultra-fast arbitrage"""
    print("⚡ ULTRA-FAST ARBITRAGE BOT")
    print("=" * 50)
    print("This bot will:")
    print("1. Detect opportunities in milliseconds")
    print("2. Execute trades within 1-2 seconds")
    print("3. Capture profits before prices move")
    print("=" * 50)
    
    detector = UltraFastArbitrageDetector(min_profit_pct=0.4, max_trade_amount=20.0)
    
    # Choose exchange
    print("\nChoose exchange:")
    print("1. KuCoin (recommended - good API speed)")
    print("2. Binance")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        exchange_id = 'kucoin' if choice == '1' else 'binance'
        
        print(f"\n⚡ Starting ultra-fast arbitrage on {exchange_id.upper()}...")
        await detector.run(exchange_id)
        
    except KeyboardInterrupt:
        print("\n⚡ Ultra-fast bot stopped by user")

if __name__ == "__main__":
    asyncio.run(main())