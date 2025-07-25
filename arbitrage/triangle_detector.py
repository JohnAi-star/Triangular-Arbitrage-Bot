import asyncio
from typing import List, Dict, Any, Set, Tuple
from itertools import combinations
from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
from exchanges.base_exchange import BaseExchange
from utils.logger import setup_logger

class TriangleDetector:
    """Detects triangular arbitrage opportunities."""
    
    def __init__(self, exchange: BaseExchange, config: Dict[str, Any]):
        self.exchange = exchange
        self.config = config
        self.logger = setup_logger('TriangleDetector')
        self.price_cache = {}
        self.triangles = []
        
    async def initialize(self) -> None:
        """Initialize the detector with trading pairs."""
        self.logger.info("Initializing triangle detector...")
        trading_pairs = await self.exchange.get_trading_pairs()
        self.triangles = self._find_triangles(trading_pairs)
        self.logger.info(f"Found {len(self.triangles)} potential triangles")
        
    def _find_triangles(self, pairs: List[str]) -> List[Tuple[str, str, str]]:
        """Find all possible triangular combinations."""
        triangles = []
        
        # Parse pairs into base/quote currencies
        currencies = set()
        pair_map = {}
        
        for pair in pairs:
            if '/' in pair:
                base, quote = pair.split('/')
                currencies.add(base)
                currencies.add(quote)
                pair_map[f"{base}/{quote}"] = pair
                pair_map[f"{quote}/{base}"] = pair
        
        # Find triangular combinations
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
                        triangles.append((base, intermediate, quote))
        
        return triangles
    
    async def update_prices(self, price_data: Dict[str, Any]) -> None:
        """Update price cache from WebSocket data."""
        if 'stream' in price_data and 'data' in price_data:
            data = price_data['data']
            symbol = data.get('s', '').upper()
            
            # Convert symbol format (BTCUSDT -> BTC/USDT)
            formatted_symbol = self._format_symbol(symbol)
            
            self.price_cache[formatted_symbol] = {
                'bid': float(data.get('b', 0)),
                'ask': float(data.get('a', 0)),
                'timestamp': data.get('E', 0)
            }
    
    def _format_symbol(self, symbol: str) -> str:
        """Format symbol from WebSocket to standard format."""
        # This is a simplified version - in production, you'd need
        # a more robust mapping based on exchange specifications
        common_quotes = ['USDT', 'BTC', 'ETH', 'BNB', 'USDC']
        for quote in common_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
        return symbol
    
    async def scan_opportunities(self) -> List[ArbitrageOpportunity]:
        """Scan for triangular arbitrage opportunities."""
        opportunities = []
        initial_amount = self.config.get('max_trade_amount', 100)
        
        for base, intermediate, quote in self.triangles:
            try:
                opportunity = await self._calculate_triangle_profit(
                    base, intermediate, quote, initial_amount
                )
                
                if opportunity and opportunity.is_profitable:
                    min_profit = self.config.get('min_profit_percentage', 0.1)
                    if opportunity.profit_percentage >= min_profit:
                        opportunities.append(opportunity)
                        
            except Exception as e:
                self.logger.error(f"Error calculating triangle {base}-{intermediate}-{quote}: {e}")
                continue
        
        return opportunities
    
    async def _calculate_triangle_profit(
        self, 
        base: str, 
        intermediate: str, 
        quote: str, 
        initial_amount: float
    ) -> ArbitrageOpportunity:
        """Calculate profit for a specific triangle."""
        
        pair1 = f"{base}/{intermediate}"
        pair2 = f"{intermediate}/{quote}"
        pair3 = f"{base}/{quote}"
        
        # Get current prices
        price1 = self.price_cache.get(pair1)
        price2 = self.price_cache.get(pair2)
        price3 = self.price_cache.get(pair3)
        
        if not all([price1, price2, price3]):
            return None
        
        # Calculate the arbitrage path: BASE -> INTERMEDIATE -> QUOTE -> BASE
        
        # Step 1: Sell BASE for INTERMEDIATE
        amount_after_step1 = initial_amount * price1['bid']
        step1 = TradeStep(
            symbol=pair1,
            side='sell',
            quantity=initial_amount,
            price=price1['bid'],
            expected_amount=amount_after_step1
        )
        
        # Step 2: Sell INTERMEDIATE for QUOTE
        amount_after_step2 = amount_after_step1 * price2['bid']
        step2 = TradeStep(
            symbol=pair2,
            side='sell',
            quantity=amount_after_step1,
            price=price2['bid'],
            expected_amount=amount_after_step2
        )
        
        # Step 3: Buy BASE with QUOTE
        final_amount = amount_after_step2 / price3['ask']
        step3 = TradeStep(
            symbol=pair3,
            side='buy',
            quantity=amount_after_step2,
            price=price3['ask'],
            expected_amount=final_amount
        )
        
        # Calculate fees
        maker_fee, taker_fee = await self.exchange.get_trading_fees(pair1)
        estimated_fees = (
            initial_amount * taker_fee +
            amount_after_step1 * taker_fee +
            amount_after_step2 * taker_fee
        )
        
        # Estimate slippage
        max_slippage = self.config.get('max_slippage_percentage', 0.05) / 100
        estimated_slippage = initial_amount * max_slippage
        
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
        
        return opportunity