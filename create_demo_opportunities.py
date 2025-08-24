#!/usr/bin/env python3
"""
Demo Opportunity Generator
Creates realistic demo opportunities to show in the GUI when no real opportunities are found
"""

import asyncio
import random
import time
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

@dataclass
class DemoOpportunity:
    """Demo arbitrage opportunity for display"""
    exchange: str
    triangle_path: List[str]
    profit_percentage: float
    profit_amount: float
    initial_amount: float
    is_profitable: bool
    
    def __str__(self):
        return f"{self.exchange}: {' → '.join(self.triangle_path)} = {self.profit_percentage:.4f}%"

class DemoOpportunityGenerator:
    """Generates realistic demo opportunities for GUI display"""
    
    def __init__(self):
        self.exchanges = [
            'binance', 'kucoin', 'gate', 'bybit', 'okx', 'mexc', 'coinex', 
            'htx', 'poloniex', 'probit', 'hitbtc', 'bitfinex', 'bingx',
            'lbank', 'xt', 'bitget', 'whitebit', 'digifinex'
        ]
        
        # Expanded currency list for more triangular combinations
        self.currencies = [
            # Major cryptocurrencies
            'BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
            'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO',
            'VET', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV',
            'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC',
            
            # DeFi tokens
            'ZRX', 'STORJ', 'GRT', 'LRC', 'UMA', 'OCEAN', 'RSR', 'CVC', 'NMR',
            'REP', 'LPT', 'BADGER', 'MLN', 'FXS', 'CVX', 'SPELL', 'ICE', 'TIME',
            'TOKE', 'ALCX', 'KP3R', 'BTRFLY', 'PENDLE', 'RDNT', 'GMX', 'GNS',
            
            # Gaming and NFT tokens
            'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC',
            'VOXEL', 'ALICE', 'TLM', 'CHR', 'PYR', 'SUPER', 'GODS', 'SKILL',
            'DPET', 'RACA', 'HERO', 'VRA', 'GHST', 'CGG', 'REVV', 'DERC',
            
            # AI and Web3 tokens
            'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT',
            'TAO', 'RNDR', 'THETA', 'TFUEL', 'LPT', 'GRT', 'API3', 'BAND',
            'TRB', 'DIA', 'LINK', 'PHB', 'DATA', 'AKT',
            
            # Meme coins
            'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ',
            'LADYS', 'WEN', 'BABYDOGE', 'KISHU', 'ELON', 'AKITA', 'HOKK',
            'LEASH', 'BONE', 'RYOSHI', 'SAFEMOON',
            
            # Layer 2 and scaling
            'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG', 'DUSK', 'L2',
            'ORBS', 'COTI', 'MOVR', 'GLMR', 'POLY', 'ONE', 'CELO', 'AURORA',
            'ROSE', 'MINA', 'FLOW', 'EGLD', 'KLAY', 'WAVES', 'HARMONY',
            
            # Privacy coins
            'XMR', 'ZEN', 'SCRT', 'MOB', 'PHA', 'OXT', 'KEEP', 'BEAM',
            'GRIN', 'FIRO', 'PIVX', 'NAV', 'XVG', 'PART', 'ARRR', 'ZEC', 'DASH',
            
            # Exchange tokens
            'KCS', 'HT', 'OKB', 'LEO', 'GT', 'MX', 'CRO', 'FTT', 'BGB',
            'WBT', 'PROB', 'CET', 'BIT', 'LBK', 'XT', 'DFT', 'BIKI', 'ZB', 'TOP',
            
            # New and trending tokens
            'JUP', 'PYTH', 'JTO', 'W', 'ENA', 'TNSR', 'ZEUS', 'PORTAL', 'MAVIA',
            'STRK', 'PIXEL', 'ALT', 'MANTA', 'DYM', 'PRIME', 'RONIN', 'SAVM',
            'OMNI', 'REZ', 'BB', 'INJ', 'SEI', 'TIA', 'SUI', 'ORDI', '1000SATS',
            'RATS', 'BOME', 'WLD', 'JASMY', 'LUNC', 'USTC', 'LUNA',
            
            # Liquid staking
            'LDO', 'SWISE', 'RPL', 'ANKR', 'FIS', 'STAKE', 'SD', 'PSTAKE',
            'STG', 'BIFI', 'RETH', 'STETH', 'CBETH', 'WSTETH', 'FRXETH',
            
            # Cross-chain and bridges
            'SYN', 'MULTI', 'CKB', 'REN', 'ANY', 'HOP',
            
            # Additional popular tokens
            'HIGH', 'TREASURE', 'JEWEL', 'DFK', 'CRYSTAL', 'DFKTEARS', 'JADE',
            'GOLD', 'SILVER', 'OIL', 'GAS', 'WHEAT', 'CACHE', 'PMGT', 'PAXG',
            'XAUT', 'DGX', 'CFG', 'LCX', 'PRO', 'IXS', 'LAND', 'MPL', 'GFI',
            'TRU', 'RSR', 'OUSD', 'GAINS', 'JOE', 'PNG', 'XAVA', 'QI', 'BENQI',
            'MC', 'CRA', 'GF', 'NFTB', 'TOWER', 'ETERNAL', 'WARS', 'KNIGHT'
        ]
    
    def generate_demo_opportunities(self, count: int = 50) -> List[DemoOpportunity]:
        """Generate realistic demo opportunities"""
        opportunities = []
        
        for i in range(count):
            # Random exchange
            exchange = random.choice(self.exchanges)
            
            # Random USDT triangle: USDT → Currency1 → Currency2 → USDT
            currency1 = random.choice(self.currencies)
            currency2 = random.choice([c for c in self.currencies if c != currency1])
            triangle_path = ['USDT', currency1, currency2, 'USDT']
            
            # Generate realistic profit percentages (0% to 2% range)
            # Weight towards smaller profits for realism
            profit_weights = [
                (0.0, 0.1, 15),    # 0.0% to 0.1% - 15% chance
                (0.1, 0.3, 25),    # 0.1% to 0.3% - 25% chance  
                (0.3, 0.5, 20),    # 0.3% to 0.5% - 20% chance
                (0.5, 0.8, 15),    # 0.5% to 0.8% - 15% chance
                (0.8, 1.2, 10),    # 0.8% to 1.2% - 10% chance
                (1.2, 2.0, 10),    # 1.2% to 2.0% - 10% chance
                (2.0, 3.0, 5)      # 2.0% to 3.0% - 5% chance
            ]
            
            # Select profit range based on weights
            total_weight = sum(weight for _, _, weight in profit_weights)
            rand_val = random.randint(1, total_weight)
            cumulative = 0
            
            for min_profit, max_profit, weight in profit_weights:
                cumulative += weight
                if rand_val <= cumulative:
                    profit_percentage = random.uniform(min_profit, max_profit)
                    break
            else:
                profit_percentage = random.uniform(0.0, 0.5)  # Fallback
            
            # Calculate profit amount based on $20 trade
            initial_amount = 20.0
            profit_amount = initial_amount * (profit_percentage / 100)
            
            opportunity = DemoOpportunity(
                exchange=exchange,
                triangle_path=triangle_path,
                profit_percentage=profit_percentage,
                profit_amount=profit_amount,
                initial_amount=initial_amount,
                is_profitable=profit_percentage >= 0.0
            )
            
            opportunities.append(opportunity)
        
        # Sort by profit percentage (highest first)
        opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        return opportunities

def main():
    """Test the demo opportunity generator"""
    generator = DemoOpportunityGenerator()
    opportunities = generator.generate_demo_opportunities(100)
    
    print("🎯 Generated Demo Opportunities (0% and positive only):")
    print("=" * 80)
    
    profitable_count = len([opp for opp in opportunities if opp.profit_percentage >= 0.4])
    zero_positive_count = len([opp for opp in opportunities if 0.0 <= opp.profit_percentage < 0.4])
    
    print(f"💚 AUTO-TRADEABLE (≥0.4%): {profitable_count}")
    print(f"🟡 MANUAL/ZERO (0-0.4%): {zero_positive_count}")
    print(f"📊 Total Opportunities: {len(opportunities)}")
    print()
    
    # Show top 20 opportunities
    for i, opp in enumerate(opportunities[:20]):
        status = "💚 AUTO-TRADEABLE" if opp.profit_percentage >= 0.4 else "🟡 MANUAL/ZERO"
        path_str = " → ".join(opp.triangle_path)
        print(f"{i+1:2d}. {status}: {opp.exchange:10s} {path_str:30s} = {opp.profit_percentage:6.4f}% (${opp.profit_amount:6.4f})")

if __name__ == "__main__":
    main()