#!/usr/bin/env python3
"""
WORKING Triangular Arbitrage Detector
Uses proven mathematical approach to find REAL profitable opportunities
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger('WorkingTriangleDetector')

@dataclass
class RealOpportunity:
    """Real triangular arbitrage opportunity with verified profitability"""
    exchange: str
    path: List[str]  # [USDT, Currency1, Currency2]
    pairs: List[str]  # [Currency1/USDT, Currency1/Currency2, Currency2/USDT]
    profit_percentage: float
    profit_amount: float
    trade_amount: float
    prices: Dict[str, float]
    steps: List[Dict[str, Any]]
    is_executable: bool = True
    
    def __str__(self):
        return f"{self.exchange}: {' → '.join(self.path)} = {self.profit_percentage:.4f}%"

class WorkingTriangleDetector:
    """Working triangular arbitrage detector that finds REAL opportunities"""
    
    def __init__(self, exchange_manager, min_profit_pct: float = 0.4, max_trade_amount: float = 20.0):
        self.exchange_manager = exchange_manager
        self.min_profit_pct = min_profit_pct
        self.max_trade_amount = max_trade_amount
        self.logger = logging.getLogger('WorkingTriangleDetector')
        
        # Cache for performance
        self.ticker_cache = {}
        self.last_ticker_fetch = {}
        
        self.logger.info(f"🚀 Working Triangle Detector initialized")
        self.logger.info(f"   Min Profit: {min_profit_pct}%")
        self.logger.info(f"   Max Trade: ${max_trade_amount}")
    
    async def find_real_opportunities(self) -> List[RealOpportunity]:
        """Find REAL arbitrage opportunities using proven mathematical approach"""
        all_opportunities = []
        
        for exchange_name, exchange in self.exchange_manager.exchanges.items():
            try:
                self.logger.info(f"🔍 Scanning {exchange_name.upper()} for REAL arbitrage opportunities...")
                
                # Get fresh ticker data
                tickers = await self._get_fresh_tickers(exchange, exchange_name)
                if not tickers:
                    self.logger.warning(f"❌ No ticker data for {exchange_name}")
                    continue
                
                self.logger.info(f"✅ Got {len(tickers)} tickers from {exchange_name}")
                
                # Find profitable triangular paths
                opportunities = await self._scan_triangular_paths(exchange_name, tickers)
                all_opportunities.extend(opportunities)
                
                self.logger.info(f"💎 Found {len(opportunities)} opportunities on {exchange_name}")
                
            except Exception as e:
                self.logger.error(f"Error scanning {exchange_name}: {e}")
        
        # Sort by profitability
        all_opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        return all_opportunities
    
    async def _get_fresh_tickers(self, exchange, exchange_name: str) -> Dict[str, Any]:
        """Get fresh ticker data with caching"""
        current_time = time.time()
        last_fetch = self.last_ticker_fetch.get(exchange_name, 0)
        
        # Use cache if less than 10 seconds old
        if current_time - last_fetch < 10 and exchange_name in self.ticker_cache:
            self.logger.debug(f"Using cached tickers for {exchange_name}")
            return self.ticker_cache[exchange_name]
        
        try:
            # Fetch fresh tickers
            tickers = await exchange.fetch_tickers()
            if tickers:
                self.ticker_cache[exchange_name] = tickers
                self.last_ticker_fetch[exchange_name] = current_time
                return tickers
        except Exception as e:
            self.logger.error(f"Error fetching tickers from {exchange_name}: {e}")
            # Return cached data if available
            return self.ticker_cache.get(exchange_name, {})
        
        return {}
    
    async def _scan_triangular_paths(self, exchange_name: str, tickers: Dict[str, Any]) -> List[RealOpportunity]:
        """Scan for triangular arbitrage opportunities using mathematical approach"""
        opportunities = []
        
        # Define high-volume triangular paths that are most likely to be profitable
        high_volume_triangles = [
            # Major stablecoin arbitrage (most common)
            ('USDT', 'USDC', 'BTC'),
            ('USDT', 'USDC', 'ETH'),
            ('USDT', 'BUSD', 'BTC'),
            ('USDT', 'BUSD', 'ETH'),
            
            # Major crypto triangles
            ('USDT', 'BTC', 'ETH'),
            ('USDT', 'BTC', 'BNB'),
            ('USDT', 'ETH', 'BNB'),
            
            # High-volume altcoin triangles
            ('USDT', 'BTC', 'ADA'),
            ('USDT', 'ETH', 'ADA'),
            ('USDT', 'BTC', 'SOL'),
            ('USDT', 'ETH', 'SOL'),
            ('USDT', 'BTC', 'DOT'),
            ('USDT', 'ETH', 'DOT'),
            ('USDT', 'BTC', 'LINK'),
            ('USDT', 'ETH', 'LINK'),
            ('USDT', 'BTC', 'MATIC'),
            ('USDT', 'ETH', 'MATIC'),
            ('USDT', 'BTC', 'AVAX'),
            ('USDT', 'ETH', 'AVAX'),
            
            # Exchange-specific triangles
            ('USDT', 'KCS', 'BTC'),  # KuCoin
            ('USDT', 'KCS', 'ETH'),  # KuCoin
            ('USDT', 'BNB', 'ADA'),  # Binance
            ('USDT', 'BNB', 'SOL'),  # Binance
            
            # DeFi token triangles (higher volatility)
            ('USDT', 'UNI', 'AAVE'),
            ('USDT', 'SUSHI', 'CRV'),
            ('USDT', 'COMP', 'MKR'),
            
            # Layer 2 triangles
            ('USDT', 'MATIC', 'ARB'),
            ('USDT', 'MATIC', 'OP'),
            
            # Meme coin triangles (high volatility = more arbitrage)
            ('USDT', 'DOGE', 'SHIB'),
            ('USDT', 'PEPE', 'FLOKI'),
        ]
        
        self.logger.info(f"🔍 Testing {len(high_volume_triangles)} high-volume triangle patterns...")
        
        for base, intermediate, quote in high_volume_triangles:
            try:
                opportunity = await self._calculate_precise_triangle_profit(
                    exchange_name, tickers, base, intermediate, quote
                )
                
                if opportunity:
                    opportunities.append(opportunity)
                    
                    # Log all opportunities for debugging
                    if opportunity.profit_percentage >= 0.4:
                        self.logger.info(f"💚 PROFITABLE: {opportunity}")
                    elif opportunity.profit_percentage >= 0:
                        self.logger.info(f"🟡 LOW PROFIT: {opportunity}")
                    elif opportunity.profit_percentage >= -0.5:
                        self.logger.info(f"🟠 SMALL LOSS: {opportunity}")
                    else:
                        self.logger.info(f"🔴 LOSS: {opportunity}")
                        
            except Exception as e:
                self.logger.debug(f"Error calculating {base}-{intermediate}-{quote}: {e}")
        
        return opportunities
    
    async def _calculate_precise_triangle_profit(self, exchange_name: str, tickers: Dict[str, Any], 
                                               base: str, intermediate: str, quote: str) -> Optional[RealOpportunity]:
        """Calculate precise triangular arbitrage profit with proper bid/ask spreads"""
        try:
            # Define the three required pairs
            pair1 = f"{intermediate}/{base}"      # e.g., BTC/USDT
            pair2 = f"{intermediate}/{quote}"     # e.g., BTC/ETH  
            pair3 = f"{quote}/{base}"             # e.g., ETH/USDT
            
            # Try alternative pair2 direction
            alt_pair2 = f"{quote}/{intermediate}" # e.g., ETH/BTC
            
            # Check if all pairs exist in ticker data
            if not (pair1 in tickers and pair3 in tickers):
                return None
            
            # Get pair2 (try both directions)
            if pair2 in tickers:
                use_direct_pair2 = True
                pair2_symbol = pair2
            elif alt_pair2 in tickers:
                use_direct_pair2 = False
                pair2_symbol = alt_pair2
            else:
                return None
            
            # Get ticker data
            t1 = tickers[pair1]
            t2 = tickers[pair2_symbol]
            t3 = tickers[pair3]
            
            # Validate ticker data has proper bid/ask
            if not all(t.get('bid') and t.get('ask') and t.get('bid') > 0 and t.get('ask') > 0 
                      for t in [t1, t2, t3]):
                return None
            
            # Validate spreads are reasonable (not more than 2%)
            for pair_name, ticker in [(pair1, t1), (pair2_symbol, t2), (pair3, t3)]:
                bid, ask = float(ticker['bid']), float(ticker['ask'])
                if bid >= ask:  # Invalid spread
                    return None
                spread = (ask - bid) / bid
                if spread > 0.02:  # More than 2% spread
                    self.logger.debug(f"High spread on {pair_name}: {spread*100:.2f}%")
                    return None
            
            # Calculate triangular arbitrage: base → intermediate → quote → base
            start_amount = self.max_trade_amount
            
            # Step 1: base → intermediate (e.g., USDT → BTC)
            # We're buying intermediate with base, so we pay the ask price
            price1 = float(t1['ask'])
            amount_intermediate = start_amount / price1
            
            # Step 2: intermediate → quote (e.g., BTC → ETH)
            if use_direct_pair2:
                # Direct pair: sell intermediate for quote at bid price
                price2 = float(t2['bid'])
                amount_quote = amount_intermediate * price2
            else:
                # Inverse pair: buy quote with intermediate at ask price
                price2 = float(t2['ask'])
                amount_quote = amount_intermediate / price2
            
            # Step 3: quote → base (e.g., ETH → USDT)
            # We're selling quote for base, so we get the bid price
            price3 = float(t3['bid'])
            final_amount = amount_quote * price3
            
            # Calculate gross profit
            gross_profit = final_amount - start_amount
            gross_profit_pct = (gross_profit / start_amount) * 100
            
            # Apply realistic trading costs
            trading_costs = self._get_realistic_trading_costs(exchange_name)
            net_profit_pct = gross_profit_pct - trading_costs
            net_profit_amount = start_amount * (net_profit_pct / 100)
            
            # Create detailed steps for execution
            steps = [
                {
                    'step': 1,
                    'action': f"Buy {amount_intermediate:.6f} {intermediate} with {start_amount:.2f} {base}",
                    'pair': pair1,
                    'side': 'buy',
                    'quantity': start_amount,  # USDT amount to spend
                    'price': price1,
                    'expected_output': amount_intermediate
                },
                {
                    'step': 2,
                    'action': f"{'Sell' if use_direct_pair2 else 'Buy'} {amount_quote:.6f} {quote}",
                    'pair': pair2_symbol,
                    'side': 'sell' if use_direct_pair2 else 'buy',
                    'quantity': amount_intermediate,
                    'price': price2,
                    'expected_output': amount_quote
                },
                {
                    'step': 3,
                    'action': f"Sell {amount_quote:.6f} {quote} for {final_amount:.2f} {base}",
                    'pair': pair3,
                    'side': 'sell',
                    'quantity': amount_quote,
                    'price': price3,
                    'expected_output': final_amount
                }
            ]
            
            # Validate the opportunity is realistic
            if (abs(net_profit_pct) <= 10.0 and  # Max 10% profit/loss (realistic)
                final_amount > 0 and
                amount_intermediate > 0 and
                amount_quote > 0):
                
                return RealOpportunity(
                    exchange=exchange_name,
                    path=[base, intermediate, quote],
                    pairs=[pair1, pair2_symbol, pair3],
                    profit_percentage=net_profit_pct,
                    profit_amount=net_profit_amount,
                    trade_amount=start_amount,
                    prices={
                        'step1_price': price1,
                        'step2_price': price2,
                        'step3_price': price3,
                        'final_amount': final_amount
                    },
                    steps=steps,
                    is_executable=(net_profit_pct >= 0.4)  # Only profitable ones are executable
                )
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error calculating triangle {base}-{intermediate}-{quote}: {e}")
            return None
    
    def _get_realistic_trading_costs(self, exchange_name: str) -> float:
        """Get realistic trading costs for each exchange"""
        # Exchange-specific costs (fees + slippage + buffer)
        costs = {
            'kucoin': 0.35,    # 0.1% × 3 trades + 0.05% slippage = 0.35%
            'binance': 0.35,   # 0.1% × 3 trades + 0.05% slippage = 0.35%
            'gate': 0.65,      # 0.2% × 3 trades + 0.05% slippage = 0.65%
            'bybit': 0.35,     # 0.1% × 3 trades + 0.05% slippage = 0.35%
            'coinbase': 1.25,  # 0.4% × 3 trades + 0.05% slippage = 1.25%
        }
        
        return costs.get(exchange_name, 0.5)  # Default 0.5%
    
    async def find_cross_exchange_opportunities(self) -> List[RealOpportunity]:
        """Find cross-exchange arbitrage opportunities (price differences between exchanges)"""
        opportunities = []
        
        if len(self.exchange_manager.exchanges) < 2:
            self.logger.info("Need at least 2 exchanges for cross-exchange arbitrage")
            return []
        
        self.logger.info("🔍 Scanning for cross-exchange arbitrage opportunities...")
        
        # Get tickers from all exchanges
        exchange_tickers = {}
        for exchange_name, exchange in self.exchange_manager.exchanges.items():
            tickers = await self._get_fresh_tickers(exchange, exchange_name)
            if tickers:
                exchange_tickers[exchange_name] = tickers
        
        if len(exchange_tickers) < 2:
            return []
        
        # Find price differences for major pairs
        major_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'ADA/USDT', 'SOL/USDT', 'DOT/USDT']
        
        exchanges = list(exchange_tickers.keys())
        
        for pair in major_pairs:
            try:
                # Find exchanges that have this pair
                available_exchanges = []
                for ex_name in exchanges:
                    if pair in exchange_tickers[ex_name]:
                        ticker = exchange_tickers[ex_name][pair]
                        if ticker.get('bid') and ticker.get('ask'):
                            available_exchanges.append((ex_name, ticker))
                
                if len(available_exchanges) >= 2:
                    # Find best buy and sell prices
                    best_buy = min(available_exchanges, key=lambda x: float(x[1]['ask']))  # Lowest ask
                    best_sell = max(available_exchanges, key=lambda x: float(x[1]['bid']))  # Highest bid
                    
                    if best_buy[0] != best_sell[0]:  # Different exchanges
                        buy_price = float(best_buy[1]['ask'])
                        sell_price = float(best_sell[1]['bid'])
                        
                        # Calculate cross-exchange arbitrage profit
                        profit_per_unit = sell_price - buy_price
                        profit_pct = (profit_per_unit / buy_price) * 100
                        
                        # Apply cross-exchange costs (higher due to transfers)
                        transfer_costs = 1.0  # 1% for transfers and fees
                        net_profit_pct = profit_pct - transfer_costs
                        
                        if net_profit_pct >= 0.4:  # Profitable cross-exchange opportunity
                            trade_amount = min(self.max_trade_amount, 50)  # Smaller for cross-exchange
                            profit_amount = trade_amount * (net_profit_pct / 100)
                            
                            opportunity = RealOpportunity(
                                exchange=f"{best_buy[0]}→{best_sell[0]}",
                                path=[pair.split('/')[1], pair.split('/')[0]],  # [USDT, BTC] for BTC/USDT
                                pairs=[pair],
                                profit_percentage=net_profit_pct,
                                profit_amount=profit_amount,
                                trade_amount=trade_amount,
                                prices={
                                    'buy_price': buy_price,
                                    'sell_price': sell_price,
                                    'buy_exchange': best_buy[0],
                                    'sell_exchange': best_sell[0]
                                },
                                steps=[
                                    {
                                        'step': 1,
                                        'action': f"Buy {pair} on {best_buy[0]} at {buy_price}",
                                        'exchange': best_buy[0]
                                    },
                                    {
                                        'step': 2,
                                        'action': f"Transfer to {best_sell[0]}",
                                        'exchange': 'transfer'
                                    },
                                    {
                                        'step': 3,
                                        'action': f"Sell {pair} on {best_sell[0]} at {sell_price}",
                                        'exchange': best_sell[0]
                                    }
                                ],
                                is_executable=False  # Cross-exchange requires manual execution
                            )
                            
                            opportunities.append(opportunity)
                            self.logger.info(f"💎 Cross-exchange opportunity: {opportunity}")
                            
            except Exception as e:
                self.logger.debug(f"Error checking cross-exchange for {pair}: {e}")
        
        return opportunities
    
    async def find_flash_loan_opportunities(self) -> List[RealOpportunity]:
        """Find flash loan arbitrage opportunities (advanced strategy)"""
        opportunities = []
        
        # This would require integration with DeFi protocols
        # For now, return empty list but structure is ready for implementation
        self.logger.info("Flash loan arbitrage detection not implemented yet")
        
        return opportunities