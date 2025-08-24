#!/usr/bin/env python3
"""
Enhanced Opportunity Generator
Generates many realistic arbitrage opportunities for display in the GUI
"""

import asyncio
import random
import time
from typing import List, Dict, Any, Set
from datetime import datetime
from dataclasses import dataclass
from utils.logger import setup_logger

@dataclass
class EnhancedOpportunity:
    """Enhanced arbitrage opportunity with realistic market data"""
    exchange: str
    triangle_path: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float
    is_profitable: bool
    is_tradeable: bool
    balance_available: float
    required_balance: float
    volume_24h: float
    liquidity_score: float
    
    def to_arbitrage_result(self):
        """Convert to ArbitrageResult format for compatibility"""
        from arbitrage.multi_exchange_detector import ArbitrageResult
        
        return ArbitrageResult(
            exchange=self.exchange,
            triangle_path=self.triangle_path,
            profit_percentage=self.profit_percentage,
            profit_amount=self.profit_amount,
            initial_amount=self.initial_amount,
            net_profit_percent=self.profit_percentage,
            min_profit_threshold=0.4,
            is_tradeable=self.is_tradeable,
            balance_available=self.balance_available,
            required_balance=self.required_balance,
            is_demo=True
        )

class EnhancedOpportunityGenerator:
    """Generates many realistic arbitrage opportunities"""
    
    def __init__(self):
        self.logger = setup_logger('EnhancedOpportunityGenerator')
        
        # All supported exchanges
        self.exchanges = [
            'binance', 'kucoin', 'gate', 'bybit', 'okx', 'mexc', 'coinex', 
            'htx', 'poloniex', 'probit', 'hitbtc', 'bitfinex', 'bingx',
            'lbank', 'xt', 'bitget', 'whitebit', 'digifinex', 'crypto'
        ]
        
        # Massive currency list for maximum triangular combinations
        self.major_currencies = [
            # Top 50 cryptocurrencies by market cap
            'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
            'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO',
            'VET', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV',
            'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC',
            'ZRX', 'STORJ', 'GRT', 'LRC', 'UMA', 'OCEAN', 'RSR', 'CVC', 'NMR',
            'REP', 'LPT', 'BADGER', 'MLN', 'ETC', 'BCH', 'EOS', 'XLM', 'XTZ'
        ]
        
        self.defi_currencies = [
            # DeFi ecosystem tokens
            'CAKE', 'BAKE', 'AUTO', 'ALPACA', 'BELT', 'BUNNY', 'EPS', 'XVS',
            'VAI', 'SXP', 'HARD', 'KAVA', 'SWP', 'USDX', 'BNX', 'RDNT',
            'GMX', 'GNS', 'GAINS', 'JOE', 'PNG', 'XAVA', 'QI', 'BENQI',
            'FXS', 'CVX', 'SPELL', 'ICE', 'TIME', 'TOKE', 'ALCX', 'KP3R',
            'BTRFLY', 'PENDLE', 'LDO', 'SWISE', 'RPL', 'ANKR', 'FIS', 'STAKE'
        ]
        
        self.gaming_currencies = [
            # Gaming and metaverse tokens
            'AXS', 'SLP', 'YGG', 'SKILL', 'GALA', 'SAND', 'MANA', 'ENJ',
            'CHR', 'PYR', 'SUPER', 'ILV', 'GODS', 'ALICE', 'TLM', 'WAX',
            'WAXP', 'DPET', 'RACA', 'HERO', 'VRA', 'GHST', 'CGG', 'REVV',
            'DERC', 'MC', 'CRA', 'GF', 'NFTB', 'TOWER', 'ETERNAL', 'WARS',
            'KNIGHT', 'HIGH', 'TREASURE', 'JEWEL', 'DFK', 'CRYSTAL', 'DFKTEARS'
        ]
        
        self.ai_currencies = [
            # AI and machine learning tokens
            'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL',
            'AIT', 'TAO', 'RNDR', 'THETA', 'TFUEL', 'LPT', 'GRT', 'API3',
            'BAND', 'TRB', 'DIA', 'PHB', 'DATA', 'AKT', 'ROSE', 'PHA'
        ]
        
        self.meme_currencies = [
            # Meme and community tokens
            'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ',
            'LADYS', 'WEN', 'BABYDOGE', 'KISHU', 'ELON', 'AKITA', 'HOKK',
            'LEASH', 'BONE', 'RYOSHI', 'SAFEMOON', 'DOGELON', 'SAITAMA',
            'JACY', 'LUFFY', 'GOKU', 'KUMA', 'TSUKA', 'VOLT', 'PUSSY', 'WOJAK'
        ]
        
        self.new_currencies = [
            # New and trending tokens (2024-2025)
            'JUP', 'PYTH', 'JTO', 'W', 'ENA', 'TNSR', 'ZEUS', 'PORTAL',
            'MAVIA', 'STRK', 'PIXEL', 'ALT', 'MANTA', 'DYM', 'PRIME',
            'RONIN', 'SAVM', 'OMNI', 'REZ', 'BB', 'SCR', 'EIGEN', 'HMSTR',
            'CATI', 'NEIRO', 'ETHFI', 'BLAST', 'MODE', 'SCROLL', 'LINEA',
            'BASE', 'ZORA', 'OPTIMISM', 'ARBITRUM', 'POLYGON', 'AVALANCHE'
        ]
        
        # Combine all currencies for maximum variety
        self.all_currencies = list(set(
            self.major_currencies + self.defi_currencies + self.gaming_currencies + 
            self.ai_currencies + self.meme_currencies + self.new_currencies
        ))
        
        self.logger.info(f"🚀 Enhanced Opportunity Generator initialized")
        self.logger.info(f"   Exchanges: {len(self.exchanges)}")
        self.logger.info(f"   Currencies: {len(self.all_currencies)}")
        self.logger.info(f"   Potential Triangles: {len(self.all_currencies) * (len(self.all_currencies) - 1) // 2}")
    
    def generate_opportunities(self, count: int = 200) -> List[EnhancedOpportunity]:
        """Generate opportunities with red/green color scheme (0% and >0.4% only)"""
        opportunities = []
        
        # Generate opportunities with red/green distribution
        for i in range(count):
            # Random exchange (weighted towards major exchanges)
            exchange_weights = {
                'binance': 20, 'kucoin': 15, 'gate': 15, 'bybit': 12, 'okx': 10,
                'mexc': 8, 'coinex': 5, 'htx': 5, 'poloniex': 3, 'probit': 2,
                'hitbtc': 2, 'bitfinex': 3, 'bingx': 2, 'lbank': 2, 'xt': 2,
                'bitget': 3, 'whitebit': 2, 'digifinex': 1, 'crypto': 3
            }
            
            exchange = random.choices(
                list(exchange_weights.keys()),
                weights=list(exchange_weights.values())
            )[0]
            
            # Select currencies with bias towards popular ones
            currency1 = random.choice(self.major_currencies + self.defi_currencies)
            currency2 = random.choice([c for c in self.all_currencies if c != currency1])
            
            # Create USDT triangle
            triangle_path = ['USDT', currency1, currency2, 'USDT']
            
            # RED/GREEN color scheme: 60% red (0%), 40% green (>0.4%)
            if random.random() < 0.6:
                # RED: Exactly 0% profit
                profit_percentage = 0.0
            else:
                # GREEN: >0.4% profit (0.4% to 2.0%)
                profit_percentage = random.uniform(0.4, 2.0)
            
            # Calculate amounts
            initial_amount = 20.0  # Fixed $20 max trade amount
            profit_amount = initial_amount * (profit_percentage / 100)
            
            # Generate realistic market data
            volume_24h = random.uniform(100000, 10000000)  # $100K to $10M daily volume
            liquidity_score = random.uniform(0.7, 1.0)    # High liquidity score
            balance_available = random.uniform(50, 500)    # $50 to $500 available
            
            opportunity = EnhancedOpportunity(
                exchange=exchange,
                triangle_path=triangle_path,
                profit_percentage=profit_percentage,
                profit_amount=profit_amount,
                initial_amount=initial_amount,
                is_profitable=profit_percentage >= 0.0,
                is_tradeable=profit_percentage >= 0.4 and balance_available >= initial_amount,
                balance_available=balance_available,
                required_balance=initial_amount,
                volume_24h=volume_24h,
                liquidity_score=liquidity_score
            )
            
            opportunities.append(opportunity)
        
        # Sort by profit percentage (highest first)
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Log summary
        red_count = len([opp for opp in opportunities if opp.profit_percentage == 0.0])
        green_count = len([opp for opp in opportunities if opp.profit_percentage > 0.4])
        
        self.logger.info(f"✅ Generated {len(opportunities)} opportunities with RED/GREEN scheme")
        self.logger.info(f"   🔴 RED (0%): {red_count}")
        self.logger.info(f"   🟢 GREEN (>0.4%): {green_count}")
        self.logger.info(f"   📊 Exchanges covered: {len(set(opp.exchange for opp in opportunities))}")
        self.logger.info(f"   🔺 Unique triangles: {len(set(' → '.join(opp.triangle_path) for opp in opportunities))}")
        
        return opportunities

async def main():
    """Test the enhanced opportunity generator"""
    generator = EnhancedOpportunityGenerator()
    opportunities = generator.generate_opportunities(300)  # Generate 300 opportunities
    
    print("🎯 Enhanced Arbitrage Opportunities (0% and positive only):")
    print("=" * 100)
    
    # Show statistics
    profitable_count = len([opp for opp in opportunities if opp.profit_percentage >= 0.4])
    zero_positive_count = len([opp for opp in opportunities if 0.0 <= opp.profit_percentage < 0.4])
    exchanges_used = len(set(opp.exchange for opp in opportunities))
    
    print(f"💚 AUTO-TRADEABLE (≥0.4%): {profitable_count}")
    print(f"🟡 MANUAL/ZERO (0-0.4%): {zero_positive_count}")
    print(f"📊 Total Opportunities: {len(opportunities)}")
    print(f"🏢 Exchanges Used: {exchanges_used}")
    print()
    
    # Show top 30 opportunities
    print("🏆 TOP 30 OPPORTUNITIES:")
    print("-" * 100)
    for i, opp in enumerate(opportunities[:30]):
        status = "💚 AUTO-TRADEABLE" if opp.profit_percentage >= 0.4 else "🟡 MANUAL/ZERO"
        path_str = " → ".join(opp.triangle_path)
        tradeable = "✅ TRADEABLE" if opp.is_tradeable else "❌ LOW BALANCE"
        
        print(f"{i+1:2d}. {status}: {opp.exchange:12s} {path_str:35s} = "
              f"{opp.profit_percentage:6.4f}% (${opp.profit_amount:7.4f}) | {tradeable}")
    
    print()
    print("🎯 All opportunities are 0% or positive (no negative opportunities shown)")
    print("💚 Green color for all opportunities (0% and positive)")
    print("🔴 LIVE TRADING mode with $20 max trade amount")

if __name__ == "__main__":
    asyncio.run(main())