import asyncio
import logging
from typing import List, Dict, Optional
from models.spot_futures_opportunity import SpotFuturesOpportunity, ArbitrageDirection

class SpotFuturesDetector:
    def __init__(self, spot_exchange, futures_exchange):
        self.spot_exchange = spot_exchange
        self.futures_exchange = futures_exchange
        self.logger = logging.getLogger(__name__)
        
        # Major crypto pairs for spot-futures arbitrage
        self.symbols = [
            'BTC-USDT', 'ETH-USDT', 'ADA-USDT', 'DOT-USDT', 
            'LINK-USDT', 'LTC-USDT', 'BCH-USDT', 'XRP-USDT',
            'EOS-USDT', 'TRX-USDT'
        ]
        
    async def get_spot_price(self, symbol: str) -> Optional[float]:
        """Get spot price for symbol"""
        try:
            # Convert BTC-USDT to BTC/USDT format for spot
            spot_symbol = symbol.replace('-', '/')
            ticker = await self.spot_exchange.get_ticker(spot_symbol)
            return float(ticker['last'])
        except Exception as e:
            self.logger.debug(f"Error getting spot price for {symbol}: {e}")
            return None
    
    async def get_futures_price(self, symbol: str) -> Optional[float]:
        """Get futures price for symbol using UnifiedExchange"""
        try:
            # For futures, we might need to use a different symbol format
            # Try both with and without / in symbol
            futures_symbol = symbol.replace('-', '/')
            ticker = await self.futures_exchange.get_ticker(futures_symbol)
            return float(ticker['last'])
        except Exception as e:
            self.logger.debug(f"Error getting futures price for {symbol}: {e}")
            return None
    
    def calculate_spread(self, spot_price: float, futures_price: float) -> tuple:
        """Calculate spread between spot and futures"""
        if spot_price == 0:
            return 0, ArbitrageDirection.SPOT_PREMIUM
            
        spread_percentage = ((futures_price - spot_price) / spot_price) * 100
        
        if spread_percentage > 0:
            direction = ArbitrageDirection.FUTURES_PREMIUM
        else:
            direction = ArbitrageDirection.SPOT_PREMIUM
            
        return spread_percentage, direction
    
    async def scan_opportunities(self, min_profit_threshold: float = 0.5) -> List[SpotFuturesOpportunity]:
        """Scan for arbitrage opportunities"""
        opportunities = []
        
        for symbol in self.symbols:
            try:
                # Get prices concurrently for speed
                spot_price, futures_price = await asyncio.gather(
                    self.get_spot_price(symbol),
                    self.get_futures_price(symbol),
                    return_exceptions=True
                )
                
                # Check if prices are valid
                if (isinstance(spot_price, Exception) or 
                    isinstance(futures_price, Exception) or
                    spot_price is None or futures_price is None):
                    continue
                
                # Calculate spread
                spread_percentage, direction = self.calculate_spread(spot_price, futures_price)
                
                # Create opportunity
                opportunity = SpotFuturesOpportunity(
                    symbol=symbol,
                    spot_price=spot_price,
                    futures_price=futures_price,
                    spread_percentage=spread_percentage,
                    direction=direction,
                    min_profit_threshold=min_profit_threshold
                )
                
                opportunities.append(opportunity)
                
                self.logger.debug(f"Scanned {symbol}: Spot=${spot_price:.2f}, Futures=${futures_price:.2f}, Spread={spread_percentage:.4f}%")
                
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        # Filter and sort opportunities
        tradeable_opportunities = [opp for opp in opportunities if opp.is_tradeable]
        tradeable_opportunities.sort(key=lambda x: abs(x.spread_percentage), reverse=True)
        
        return tradeable_opportunities
    
    async def continuous_scan(self, callback, interval: float = 1.0, min_profit_threshold: float = 0.5):
        """Continuously scan for opportunities and call callback when found"""
        while True:
            try:
                opportunities = await self.scan_opportunities(min_profit_threshold)
                
                if opportunities:
                    await callback(opportunities)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Error in continuous scan: {e}")
                await asyncio.sleep(interval)