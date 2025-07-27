"""
Multi-exchange triangular arbitrage detector.
"""

import asyncio
from typing import List, Dict, Any, Set, Tuple
from itertools import combinations, permutations
from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
from exchanges.multi_exchange_manager import MultiExchangeManager
from config.exchanges_config import PRIORITY_CURRENCIES, MIN_LIQUIDITY_USD
from utils.logger import setup_logger

class MultiExchangeDetector:
    """Detects triangular arbitrage opportunities across multiple exchanges."""
    
    def __init__(self, exchange_manager: MultiExchangeManager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.config = config
        self.logger = setup_logger('MultiExchangeDetector')
        self.price_cache = {}
        self.triangles = {}
        self.volume_cache = {}
        
    async def initialize(self) -> None:
        """Initialize the detector with trading pairs from all exchanges."""
        self.logger.info("Initializing multi-exchange triangle detector...")
        
        all_pairs = await self.exchange_manager.get_all_trading_pairs()
        
        for exchange_id, pairs in all_pairs.items():
            self.triangles[exchange_id] = self._find_triangles(pairs)
            self.logger.info(f"Found {len(self.triangles[exchange_id])} triangles for {exchange_id}")
        
        total_triangles = sum(len(triangles) for triangles in self.triangles.values())
        self.logger.info(f"Total triangles across all exchanges: {total_triangles}")
    
    def _find_triangles(self, pairs: List[str]) -> List[Tuple[str, str, str]]:
        """Find all possible triangular combinations for an exchange."""
        triangles = []
        
        # Parse pairs into currencies
        currencies = set()
        pair_map = {}
        
        for pair in pairs:
            if '/' in pair:
                base, quote = pair.split('/')
                currencies.add(base)
                currencies.add(quote)
                pair_map[f"{base}/{quote}"] = pair
                pair_map[f"{quote}/{base}"] = pair
        
        # Prioritize triangles with major currencies
        priority_currencies = set(PRIORITY_CURRENCIES)
        
        # Find triangular combinations, prioritizing major currencies
        for base in currencies:
            for intermediate in currencies:
                if intermediate == base:
                    continue
                for quote in currencies:
                    if quote == base or quote == intermediate:
                        continue
                    
                    # Check if all three pairs exist
                    pair1 = f"{base}/{intermediate}"
                    pair2 = f"{intermediate}/{quote}"
                    pair3 = f"{base}/{quote}"
                    
                    if (pair1 in pair_map and 
                        pair2 in pair_map and 
                        pair3 in pair_map):
                        
                        # Prioritize triangles with major currencies
                        priority_score = sum(1 for curr in [base, intermediate, quote] 
                                           if curr in priority_currencies)
                        
                        triangles.append((base, intermediate, quote, priority_score))
        
        # Sort by priority score (descending)
        triangles.sort(key=lambda x: x[3], reverse=True)
        
        # Return only the triangle tuples (without priority score)
        return [(base, intermediate, quote) for base, intermediate, quote, _ in triangles]
    
    async def update_prices(self, price_data: Dict[str, Any]) -> None:
        """Update price cache from WebSocket data."""
        try:
            exchange = price_data.get('exchange')
            data = price_data.get('data', {})
            
            if exchange and 'symbol' in data:
                symbol = data['symbol']
                
                if exchange not in self.price_cache:
                    self.price_cache[exchange] = {}
                
                self.price_cache[exchange][symbol] = {
                    'bid': data.get('bid', 0),
                    'ask': data.get('ask', 0),
                    'last': data.get('last', 0),
                    'volume': data.get('volume', 0),
                    'timestamp': data.get('timestamp', 0)
                }
                
                # Update volume cache for liquidity filtering
                if exchange not in self.volume_cache:
                    self.volume_cache[exchange] = {}
                
                self.volume_cache[exchange][symbol] = data.get('volume', 0)
                
        except Exception as e:
            self.logger.error(f"Error updating prices: {e}")
    
    async def scan_all_opportunities(self) -> List[ArbitrageOpportunity]:
        """Scan for triangular arbitrage opportunities across all exchanges."""
        self.logger.info("Starting scan for all opportunities...")
        all_opportunities = []
        
        for exchange_id in self.exchange_manager.get_connected_exchanges():
            try:
                self.logger.info(f"Scanning opportunities for {exchange_id}")
                opportunities = await self.scan_exchange_opportunities(exchange_id)
                self.logger.info(f"Found {len(opportunities)} opportunities on {exchange_id}")
                all_opportunities.extend(opportunities)
            except Exception as e:
                self.logger.error(f"Error scanning {exchange_id}: {e}")
        
        self.logger.info(f"Total opportunities found across all exchanges: {len(all_opportunities)}")
        
        # Sort by profit percentage (descending) but don't filter by profitability
        all_opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Apply zero-fee prioritization
        if self.config.get('prioritize_zero_fee', True):
            all_opportunities = self._prioritize_zero_fee_opportunities(all_opportunities)
        
        # Cap at 200 opportunities to prevent frontend flooding
        final_opportunities = all_opportunities[:200]
        self.logger.info(f"Returning {len(final_opportunities)} final opportunities")
        
        return final_opportunities
    
    async def scan_exchange_opportunities(self, exchange_id: str) -> List[ArbitrageOpportunity]:
        """Scan for opportunities on a specific exchange."""
        opportunities = []
        exchange = self.exchange_manager.get_exchange(exchange_id)
        
        if not exchange or exchange_id not in self.triangles:
            self.logger.warning(f"Exchange {exchange_id} not available or no triangles found")
            return opportunities
        
        initial_amount = self.config.get('max_trade_amount', 100)
        triangles_to_check = self.triangles[exchange_id][:100]  # Limit triangles
        self.logger.info(f"Checking {len(triangles_to_check)} triangles for {exchange_id}")
        
        for i, (base, intermediate, quote) in enumerate(triangles_to_check):
            try:
                opportunity = await self._calculate_triangle_profit(
                    exchange_id, base, intermediate, quote, initial_amount
                )
                
                if opportunity:
                    opportunity.exchange = exchange_id
                    opportunities.append(opportunity)
                    
                    # Detailed logging for each triangle
                    self.logger.info(
                        f"Triangle {base}-{intermediate}-{quote} on {exchange_id}: "
                        f"Profit: {opportunity.profit_percentage:.4f}% "
                        f"({opportunity.profit_amount:.6f} {base}), "
                        f"Initial: {opportunity.initial_amount:.6f}, "
                        f"Final: {opportunity.final_amount:.6f}, "
                        f"Net: {opportunity.net_profit:.6f}"
                    )
                        
            except Exception as e:
                if i < 5:  # Only log first 5 errors to avoid spam
                    self.logger.error(f"Error calculating triangle {base}-{intermediate}-{quote} on {exchange_id}: {e}")
                continue
        
        self.logger.info(f"Found {len(opportunities)} total opportunities on {exchange_id}")
        return opportunities
    
    async def _calculate_triangle_profit(
        self, 
        exchange_id: str,
        base: str, 
        intermediate: str, 
        quote: str, 
        initial_amount: float
    ) -> ArbitrageOpportunity:
        """Calculate profit for a specific triangle on a specific exchange."""
        
        pair1 = f"{base}/{intermediate}"
        pair2 = f"{intermediate}/{quote}"
        pair3 = f"{base}/{quote}"
        
        # Get current prices from cache
        exchange_prices = self.price_cache.get(exchange_id, {})
        price1 = exchange_prices.get(pair1)
        price2 = exchange_prices.get(pair2)
        price3 = exchange_prices.get(pair3)
        
        if not all([price1, price2, price3]):
            # Fallback to direct API call if not in cache
            exchange = self.exchange_manager.get_exchange(exchange_id)
            if not exchange:
                return None
            
            try:
                price1 = await exchange.get_ticker(pair1) if not price1 else price1
                price2 = await exchange.get_ticker(pair2) if not price2 else price2
                price3 = await exchange.get_ticker(pair3) if not price3 else price3
                
                if not all([price1.get('bid'), price2.get('bid'), price3.get('ask')]):
                    return None
                    
            except Exception:
                return None
        
        # Guard against invalid prices - prevent division by zero and negative prices
        try:
            bid1 = float(price1.get('bid', 0))
            bid2 = float(price2.get('bid', 0))
            ask3 = float(price3.get('ask', 0))
            
            if bid1 <= 0 or bid2 <= 0 or ask3 <= 0:
                return None
        except (ValueError, TypeError):
            return None
        
        # Convert initial amount to float for safety
        try:
            initial_amount = float(initial_amount)
            if initial_amount <= 0:
                return None
        except (ValueError, TypeError):
            return None
        
        # Calculate the arbitrage path: BASE -> INTERMEDIATE -> QUOTE -> BASE
        
        # Step 1: Sell BASE for INTERMEDIATE
        amount_after_step1 = initial_amount * bid1
        step1 = TradeStep(
            symbol=pair1,
            side='sell',
            quantity=initial_amount,
            price=bid1,
            expected_amount=amount_after_step1
        )
        
        # Step 2: Sell INTERMEDIATE for QUOTE
        amount_after_step2 = amount_after_step1 * bid2
        step2 = TradeStep(
            symbol=pair2,
            side='sell',
            quantity=amount_after_step1,
            price=bid2,
            expected_amount=amount_after_step2
        )
        
        # Step 3: Buy BASE with QUOTE
        final_amount = amount_after_step2 / ask3
        
        # Sanity clamp - prevent unrealistic final amounts
        if final_amount <= 0 or final_amount > initial_amount * 10:  # 10x cap
            return None
        
        step3 = TradeStep(
            symbol=pair3,
            side='buy',
            quantity=amount_after_step2,
            price=ask3,
            expected_amount=final_amount
        )
        
        # Calculate normalized profit with validation
        profit_amount = final_amount - initial_amount
        profit_percentage = (profit_amount / initial_amount) * 100
        
        # Discard unrealistic profit spikes
        if abs(profit_percentage) > 100:  # discard unrealistic spikes
            return None
        
        # Calculate fees
        exchange = self.exchange_manager.get_exchange(exchange_id)
        maker_fee, taker_fee = await exchange.get_trading_fees(pair1)
        
        # Check for zero-fee pairs
        exchange_config = exchange.config
        zero_fee_pairs = exchange_config.get('zero_fee_pairs', [])
        
        fee1 = 0 if pair1 in zero_fee_pairs else initial_amount * taker_fee
        fee2 = 0 if pair2 in zero_fee_pairs else amount_after_step1 * taker_fee
        fee3 = 0 if pair3 in zero_fee_pairs else amount_after_step2 * taker_fee
        
        estimated_fees = fee1 + fee2 + fee3
        
        # Estimate slippage (more conservative for higher volumes)
        base_slippage = 0.001  # 0.1% base slippage
        volume_factor = min(initial_amount / 1000, 1.0)  # Scale with trade size
        estimated_slippage = initial_amount * base_slippage * (1 + volume_factor)
        
        # Create opportunity
        opportunity = ArbitrageOpportunity(
            base_currency=base,
            intermediate_currency=intermediate,
            quote_currency=quote,
            pair1=pair1,
            pair2=pair2,
            pair3=pair3,
            steps=[step1, step2, step3],
            initial_amount=initial_amount,
            final_amount=final_amount,
            estimated_fees=estimated_fees,
            estimated_slippage=estimated_slippage
        )
        
        # Set normalized profit values
        opportunity.profit_amount = profit_amount
        opportunity.profit_percentage = profit_percentage
        
        return opportunity
    
    async def _check_liquidity(self, exchange_id: str, opportunity: ArbitrageOpportunity) -> bool:
        """Check if the opportunity has sufficient liquidity."""
        try:
            exchange = self.exchange_manager.get_exchange(exchange_id)
            if not exchange:
                return False
            
            # Check volume for each pair
            volume_cache = self.volume_cache.get(exchange_id, {})
            
            for step in opportunity.steps:
                symbol = step.symbol
                volume = volume_cache.get(symbol, 0)
                
                # Estimate USD volume (simplified)
                usd_volume = volume * step.price  # Rough approximation
                
                if usd_volume < MIN_LIQUIDITY_USD:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking liquidity: {e}")
            return False
    
    def _prioritize_zero_fee_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> List[ArbitrageOpportunity]:
        """Prioritize opportunities with zero-fee pairs."""
        zero_fee_opportunities = []
        regular_opportunities = []
        
        for opportunity in opportunities:
            # Check if any step involves a zero-fee pair
            has_zero_fee = False
            
            if hasattr(opportunity, 'exchange'):
                exchange = self.exchange_manager.get_exchange(opportunity.exchange)
                if exchange:
                    zero_fee_pairs = exchange.config.get('zero_fee_pairs', [])
                    has_zero_fee = any(step.symbol in zero_fee_pairs for step in opportunity.steps)
            
            if has_zero_fee:
                zero_fee_opportunities.append(opportunity)
            else:
                regular_opportunities.append(opportunity)
        
        # Return zero-fee opportunities first, then regular ones
        return zero_fee_opportunities + regular_opportunities