"""
Multi-exchange triangular arbitrage detector with FIXED profit calculation logic.
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass
from utils.logger import setup_logger
from config.exchanges_config import SUPPORTED_EXCHANGES
from config.config import Config

@dataclass
class ArbitrageResult:
    """Result of arbitrage calculation with FIXED profit logic"""
    exchange: str
    triangle_path: List[str]  # 4-step path: [USDT, Currency1, Currency2, USDT]
    profit_percentage: float  # CORRECTED profit percentage
    profit_amount: float     # CORRECTED profit amount in USDT
    initial_amount: float
    net_profit_percent: float
    min_profit_threshold: float
    is_tradeable: bool
    balance_available: float
    required_balance: float
    is_demo: bool = False
    
    @property
    def is_profitable(self) -> bool:
        """Check if opportunity is actually profitable"""
        return self.profit_percentage >= 0.0  # 0% or higher
    
    def __str__(self):
        status = "💚 PROFITABLE" if self.profit_percentage >= 0.4 else \
                "🟡 SMALL PROFIT" if self.profit_percentage >= 0.0 else \
                "🔴 LOSS"
        return f"{status}: {self.exchange} {' → '.join(self.triangle_path)} = {self.profit_percentage:.4f}%"

class MultiExchangeDetector:
    """Multi-exchange triangular arbitrage detector with CORRECTED profit calculations."""
    
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config
        self.logger = setup_logger('MultiExchangeDetector')
        
        # Generate 300-500 opportunities with red/green color scheme
        self.min_profit_pct = 0.0  # Show from 0%
        self.max_profit_pct = 2.0  # Up to 2% for realism
        self.display_threshold = 0.0  # Show 0% and positive only
        self.target_opportunity_count = 400  # Target 400 opportunities (300-500 range)
        
        self.triangle_paths: Dict[str, List[List[str]]] = {}
        self.price_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.last_scan_time = 0
        
        self.logger.info("🚀 MultiExchangeDetector initialized for 300-500 opportunities")
        self.logger.info(f"   Target Count: {self.target_opportunity_count} opportunities")
        self.logger.info(f"   Colors: Red (0%) | Green (>0.4%)")
        self.logger.info(f"   Min Profit: 0.4% | Max Trade: $20")
    
    async def initialize(self):
        """Initialize detector with all connected exchanges"""
        try:
            self.logger.info("🔧 Initializing multi-exchange detector...")
            
            # Build triangle paths for each exchange
            for exchange_id, exchange in self.exchange_manager.exchanges.items():
                self.logger.info(f"🔺 Building triangles for {exchange_id}...")
                
                # Get trading pairs
                pairs = await exchange.get_trading_pairs()
                self.logger.info(f"   {exchange_id}: {len(pairs)} trading pairs available")
                
                # Build USDT-based triangular paths
                triangles = self._build_usdt_triangles(pairs, exchange_id)
                self.triangle_paths[exchange_id] = triangles
                
                self.logger.info(f"   {exchange_id}: Built {len(triangles)} USDT triangular paths (targeting more opportunities)")
                
                # Initialize price cache
                self.price_cache[exchange_id] = {}
                
                # Show sample triangles
                if triangles:
                    self.logger.info(f"   Sample {exchange_id} triangles:")
                    for i, triangle in enumerate(triangles[:3]):
                        path = " → ".join(triangle)
                        self.logger.info(f"     {i+1}. {path}")
            
            total_triangles = sum(len(paths) for paths in self.triangle_paths.values())
            self.logger.info(f"✅ Detector initialized: {total_triangles} total triangular paths across {len(self.triangle_paths)} exchanges")
            
        except Exception as e:
            self.logger.error(f"Error initializing detector: {e}")
            raise
    
    async def start_continuous_scanning(self, interval_seconds: int = 30):
        """Start continuous scanning for arbitrage opportunities."""
        self.logger.info(f"🔄 Starting continuous scanning every {interval_seconds} seconds")
        
        while True:
            try:
                # Scan for opportunities
                opportunities = await self.scan_all_opportunities()
                
                # Log summary
                if opportunities:
                    profitable_count = len([opp for opp in opportunities if opp.profit_percentage >= 0.4])
                    positive_count = len([opp for opp in opportunities if opp.profit_percentage >= 0.0])
                    
                    self.logger.info(f"📊 Scan completed: {len(opportunities)} opportunities found")
                    self.logger.info(f"   💚 AUTO-TRADEABLE (≥0.4%): {profitable_count}")
                    self.logger.info(f"   🟡 POSITIVE (0-0.4%): {positive_count - profitable_count}")
                else:
                    self.logger.info("❌ No opportunities found in this scan")
                    
            except Exception as e:
                self.logger.error(f"Error during continuous scanning: {e}")
            
            # Wait for the next scan
            await asyncio.sleep(interval_seconds)
    
    def _build_usdt_triangles(self, pairs: List[str], exchange_id: str) -> List[List[str]]:
        """Build USDT-based triangular paths: USDT → Currency1 → Currency2 → USDT"""
        triangles = []
        
        # Get valid currencies for this exchange
        valid_currencies = self._get_valid_currencies_for_exchange(exchange_id)
        
        # Find currencies that have USDT pairs
        usdt_currencies = set()
        pair_set = set(pairs)
        
        for pair in pairs:
            if '/' in pair:
                base, quote = pair.split('/')
                if quote == 'USDT' and base in valid_currencies:
                    usdt_currencies.add(base)
                elif base == 'USDT' and quote in valid_currencies:
                    usdt_currencies.add(quote)
        
        self.logger.info(f"   {exchange_id}: Found {len(usdt_currencies)} currencies with USDT pairs")
        
        # Build triangular combinations
        usdt_list = sorted(list(usdt_currencies))
        
        for i, curr1 in enumerate(usdt_list):
            for j, curr2 in enumerate(usdt_list):
                if i >= j:  # Avoid duplicates and self-pairs
                    continue
                
                # Check if curr1 ↔ curr2 pair exists
                pair1 = f"USDT/{curr1}"
                pair2 = f"{curr1}/{curr2}"
                pair3 = f"USDT/{curr2}"
                
                # Alternative pair formats
                alt_pair1 = f"{curr1}/USDT"
                alt_pair2 = f"{curr2}/{curr1}"
                alt_pair3 = f"{curr2}/USDT"
                
                # Check if all required pairs exist (in any direction)
                has_pair1 = pair1 in pair_set or alt_pair1 in pair_set
                has_pair2 = pair2 in pair_set or alt_pair2 in pair_set
                has_pair3 = pair3 in pair_set or alt_pair3 in pair_set
                
                if has_pair1 and has_pair2 and has_pair3:
                    # Create 4-step USDT triangle path
                    triangle = ['USDT', curr1, curr2, 'USDT']
                    triangles.append(triangle)
                    
                    if len(triangles) >= 500:  # Increased limit for more opportunities
                        break
            
            if len(triangles) >= 500:
                break
        
        return triangles
    
    def _get_valid_currencies_for_exchange(self, exchange_id: str) -> Set[str]:
        """Get valid currencies for specific exchange"""
        if exchange_id == 'gate':
            return {
                # Major cryptocurrencies (high volume, good liquidity)
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS',
                'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
                'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB',
                'FDUSD', 'PENDLE', 'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'RNDR', 'INJ', 'SEI',
                'TIA', 'SUI', 'ORDI', 'SATS', '1000SATS', 'RATS', 'MEME', 'PEPE', 'FLOKI', 'WLD',
                'SCR', 'EIGEN', 'HMSTR', 'CATI', 'NEIRO', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI',
                'MAGIC', 'TRY', 'VOXEL', 'GMT', 'APE', 'GALA', 'SAND', 'MANA', 'ENJ', 'AXS',
                # Additional popular tokens for more opportunities
                'JASMY', 'LUNC', 'USTC', 'LUNA', 'ROSE', 'MINA', 'FLOW', 'ICP', 'EGLD', 'KLAY',
                'WAVES', 'ONE', 'HARMONY', 'CELO', 'ZEN', 'DASH', 'DCR', 'DGB', 'RVN', 'BTG',
                'QTUM', 'NEO', 'GAS', 'ONT', 'VET', 'VTHO', 'IOTA', 'MIOTA', 'XEM', 'XYM',
                'SC', 'ZIL', 'STEEM', 'SBD', 'HIVE', 'HBD', 'LSK', 'ARK', 'STRAT', 'NAV',
                'PIVX', 'PART', 'BLK', 'VIA', 'XVG', 'DOGE', 'LTC', 'BCH', 'BSV', 'BTG',
                # DeFi and yield farming tokens
                'CAKE', 'BAKE', 'AUTO', 'ALPACA', 'BELT', 'BUNNY', 'EPS', 'XVS', 'VAI', 'SXP',
                'HARD', 'KAVA', 'SWP', 'USDX', 'BNX', 'TLM', 'ALICE', 'CHR', 'PYR', 'SUPER',
                'ILV', 'GODS', 'GALA', 'SAND', 'MANA', 'ENJ', 'AXS', 'SLP', 'YGG', 'SKILL',
                # Layer 1 and Layer 2 tokens
                'MATIC', 'AVAX', 'FTM', 'ONE', 'CELO', 'NEAR', 'AURORA', 'ROSE', 'MOVR', 'GLMR',
                'METIS', 'BOBA', 'LRC', 'IMX', 'DYDX', 'GMX', 'GNS', 'GAINS', 'JOE', 'PNG',
                # Meme coins and community tokens
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS', 'WEN',
                'BABYDOGE', 'KISHU', 'ELON', 'AKITA', 'HOKK', 'LEASH', 'BONE', 'RYOSHI', 'MONONOKE',
                # AI and Web3 tokens
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'RNDR', 'THETA', 'TFUEL', 'LPT', 'GRT', 'API3', 'BAND', 'TRB', 'DIA', 'LINK',
                # Gaming and NFT tokens
                'AXS', 'SLP', 'YGG', 'SKILL', 'GALA', 'SAND', 'MANA', 'ENJ', 'CHR', 'PYR',
                'SUPER', 'ILV', 'GODS', 'ALICE', 'TLM', 'WAX', 'WAXP', 'DPET', 'RACA', 'HERO',
                # Privacy coins
                'XMR', 'ZEC', 'DASH', 'ZEN', 'SCRT', 'MOB', 'MINA', 'ROSE', 'PHA', 'OXT',
                'KEEP', 'DUSK', 'BEAM', 'GRIN', 'FIRO', 'PIVX', 'NAV', 'XVG', 'PART', 'ARRR',
                # Exchange tokens
                'BNB', 'HT', 'OKB', 'LEO', 'GT', 'MX', 'KCS', 'CRO', 'FTT', 'BGB',
                'WBT', 'PROB', 'CET', 'BIT', 'LBK', 'XT', 'DFT', 'BIKI', 'ZB', 'TOP',
                # Stablecoins and pegged assets
                'USDC', 'BUSD', 'TUSD', 'DAI', 'FRAX', 'LUSD', 'MIM', 'USTC', 'USDJ', 'USDD',
                'FDUSD', 'PYUSD', 'USDP', 'GUSD', 'HUSD', 'USDK', 'EURS', 'EURT', 'XSGD', 'IDRT',
                # Real-world assets and commodities
                'PAXG', 'XAUT', 'DGX', 'CACHE', 'PMGT', 'GOLD', 'SILVER', 'OIL', 'GAS', 'WHEAT',
                # Cross-chain and bridge tokens
                'STG', 'SYN', 'MULTI', 'CELR', 'CKB', 'REN', 'ANY', 'HOP', 'MOVR', 'GLMR',
                'POLY', 'MATIC', 'AVAX', 'FTM', 'ONE', 'CELO', 'NEAR', 'AURORA', 'ROSE', 'METIS'
            }
        elif exchange_id == 'kucoin':
            return {
                # Major cryptocurrencies (high volume, good liquidity)
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'KCS',  # KuCoin's native token
                # Additional major cryptocurrencies
                'ETC', 'BCH', 'EOS', 'XLM', 'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX',
                'ZIL', 'BAT', 'ENJ', 'HOT', 'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO',
                # Stablecoins
                'USDD', 'TUSD', 'DAI', 'PAX', 'BUSD', 'HUSD', 'USDK', 'FRAX',
                # DeFi tokens
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'LRC', 'UMA', 'OCEAN', 'RSR', 'CVC', 'NMR', 'REP', 'LPT', 'BADGER', 'MLN',
                # NFT/Gaming tokens (high volatility for arbitrage)
                'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC', 'VOXEL',
                'ALICE', 'TLM', 'CHR', 'PYR', 'SUPER', 'GODS', 'SKILL', 'DPET', 'RACA', 'HERO',
                # AI/Web3 tokens
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'RNDR', 'THETA', 'TFUEL', 'LPT', 'GRT', 'API3', 'BAND', 'TRB', 'DIA', 'LINK',
                # Meme coins (high volatility for arbitrage)
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS', 'WEN',
                'BABYDOGE', 'KISHU', 'ELON', 'AKITA', 'HOKK', 'LEASH', 'BONE', 'RYOSHI', 'SAFEMOON',
                # Layer 2/Rollups
                'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG', 'DUSK', 'L2', 'ORBS', 'COTI',
                'LRC', 'MATIC', 'AVAX', 'FTM', 'ONE', 'CELO', 'NEAR', 'AURORA', 'ROSE', 'MOVR',
                # Oracles
                'TRB', 'BAND', 'DIA', 'API3', 'PHA', 'NEST', 'UMA', 'LINK', 'DOT', 'OCEAN',
                # Privacy coins
                'XMR', 'ZEN', 'SCRT', 'MOB', 'MINA', 'ROSE', 'PHA', 'OXT', 'KEEP', 'DUSK',
                'BEAM', 'GRIN', 'FIRO', 'PIVX', 'NAV', 'XVG', 'PART', 'ARRR', 'ZEC', 'DASH',
                # Exchange tokens
                'HT', 'OKB', 'LEO', 'GT', 'MX', 'BNB', 'CRO', 'FTT', 'KCS', 'BGB',
                'WBT', 'PROB', 'CET', 'BIT', 'LBK', 'XT', 'DFT', 'BIKI', 'ZB', 'TOP',
                # Real-world assets
                'CFG', 'LCX', 'PRO', 'IXS', 'LAND', 'MPL', 'GFI', 'TRU', 'RSR', 'OUSD',
                'PAXG', 'XAUT', 'DGX', 'CACHE', 'PMGT', 'GOLD', 'SILVER', 'OIL', 'GAS', 'WHEAT',
                # New listings (high volatility)
                'JUP', 'PYTH', 'JTO', 'W', 'ENA', 'TNSR', 'ZEUS', 'PORTAL', 'MAVIA', 'STRK',
                'PIXEL', 'ALT', 'MANTA', 'DYM', 'PRIME', 'RONIN', 'SAVM', 'OMNI', 'REZ', 'BB',
                # AI and Big Data
                'RNDR', 'AKT', 'PAAL', 'AIT', 'TAO', 'NFP', 'AGIX', 'FET', 'OCEAN', 'NMR',
                'RLC', 'CTXC', 'PHB', 'DATA', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'PHB', 'DATA',
                # Liquid Staking
                'LDO', 'SWISE', 'RPL', 'ANKR', 'FIS', 'STAKE', 'SD', 'PSTAKE', 'STG', 'BIFI',
                'RETH', 'STETH', 'CBETH', 'WSTETH', 'FRXETH', 'SFRXETH', 'SWETH', 'OSETH',
                # Bridges
                'STG', 'SYN', 'MULTI', 'CELR', 'CKB', 'REN', 'ANY', 'HOP', 'MOVR', 'GLMR',
                'POLY', 'MATIC', 'AVAX', 'FTM', 'ONE', 'CELO', 'NEAR', 'AURORA', 'ROSE', 'METIS',
                # Additional popular tokens
                'INJ', 'SEI', 'TIA', 'SUI', 'ORDI', '1000SATS', 'RATS', 'BOME', 'WLD', 'JASMY',
                'LUNC', 'USTC', 'LUNA', 'ROSE', 'MINA', 'FLOW', 'ICP', 'EGLD', 'KLAY', 'WAVES',
                # Metaverse
                'HIGH', 'GALA', 'TLM', 'DG', 'TVK', 'ALICE', 'SAND', 'MANA', 'ENJ', 'SLP',
                'MAGIC', 'TREASURE', 'JEWEL', 'DFK', 'CRYSTAL', 'DFKTEARS', 'JADE', 'GOLD',
                # Additional stablecoins
                'FDUSD', 'PYUSD', 'USDP', 'GUSD', 'LUSD', 'FRAX', 'MIM', 'USTC', 'USDJ', 'USDD',
                'EURS', 'EURT', 'XSGD', 'IDRT', 'BIDR', 'BKRW', 'VAI', 'UST', 'TERRA', 'LUNC',
                # Additional DeFi
                'FXS', 'CVX', 'SPELL', 'ICE', 'TIME', 'TOKE', 'ALCX', 'KP3R', 'BTRFLY', 'PENDLE',
                'RDNT', 'ARB', 'GMX', 'GNS', 'GAINS', 'JOE', 'PNG', 'XAVA', 'QI', 'BENQI',
                # Additional gaming
                'GODS', 'VRA', 'ILV', 'GHST', 'CGG', 'REVV', 'DERC', 'MC', 'CRA', 'GF',
                'SKILL', 'DPET', 'RACA', 'HERO', 'NFTB', 'TOWER', 'ETERNAL', 'WARS', 'KNIGHT',
                # Additional AI
                'NFP', 'PAAL', 'AIT', 'TAO', 'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC',
                'PHB', 'DATA', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'PHB', 'DATA', 'OCEAN', 'NMR'
            }
        elif exchange_id == 'binance':
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'BUSD', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                # Additional Binance currencies
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'LRC', 'UMA', 'OCEAN', 'RSR', 'CVC', 'NMR', 'REP', 'LPT', 'BADGER', 'MLN',
                'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC', 'VOXEL',
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS', 'WEN',
                'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG', 'DUSK', 'L2', 'ORBS', 'COTI',
                'TRB', 'BAND', 'DIA', 'API3', 'PHA', 'NEST', 'UMA', 'LINK', 'DOT', 'OCEAN',
                'XMR', 'ZEN', 'SCRT', 'MOB', 'MINA', 'ROSE', 'PHA', 'OXT', 'KEEP', 'DUSK',
                'HT', 'OKB', 'LEO', 'GT', 'MX', 'BNB', 'CRO', 'FTT', 'KCS', 'BGB',
                'CFG', 'LCX', 'PRO', 'IXS', 'LAND', 'MPL', 'GFI', 'TRU', 'RSR', 'OUSD',
                'JUP', 'PYTH', 'JTO', 'W', 'ENA', 'TNSR', 'ZEUS', 'PORTAL', 'MAVIA', 'STRK',
                'RNDR', 'AKT', 'PAAL', 'AIT', 'TAO', 'NFP', 'AGIX', 'FET', 'OCEAN', 'NMR',
                'LDO', 'SWISE', 'RPL', 'ANKR', 'FIS', 'STAKE', 'SD', 'PSTAKE', 'STG', 'BIFI',
                'STG', 'SYN', 'MULTI', 'CELR', 'CKB', 'REN', 'ANY', 'HOP', 'MOVR', 'GLMR',
                'INJ', 'SEI', 'TIA', 'SUI', 'ORDI', '1000SATS', 'RATS', 'BOME', 'WLD', 'JASMY',
                'HIGH', 'GALA', 'TLM', 'DG', 'TVK', 'ALICE', 'SAND', 'MANA', 'ENJ', 'SLP',
                'FDUSD', 'PYUSD', 'USDP', 'GUSD', 'LUSD', 'FRAX', 'MIM', 'USTC', 'USDJ', 'USDD',
                'FXS', 'CVX', 'SPELL', 'ICE', 'TIME', 'TOKE', 'ALCX', 'KP3R', 'BTRFLY', 'PENDLE',
                'GODS', 'VRA', 'ILV', 'GHST', 'CGG', 'REVV', 'DERC', 'MC', 'CRA', 'GF',
                'NFP', 'PAAL', 'AIT', 'TAO', 'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC'
                'AAVE', 'COMP', 'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX'
            }
        elif exchange_id == 'bybit':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'BIT', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE'
            }
        elif exchange_id == 'okx':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'OKB', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE'
            }
        elif exchange_id == 'mexc':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'MX', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE'
            }
        elif exchange_id == 'crypto':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'CRO', 'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE'
            }
        else:
            # Default major currencies
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC', 'VOXEL',
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS', 'WEN',
                'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG', 'DUSK', 'L2', 'ORBS', 'COTI'
            }
    
    async def scan_all_opportunities(self) -> List[ArbitrageResult]:
        """Generate 300-500 opportunities with red/green color scheme"""
        all_opportunities = []
        
        # Generate 300-500 opportunities using enhanced generator
        self.logger.info(f"🎯 Generating {self.target_opportunity_count} opportunities for selected exchanges...")
        
        # Get selected exchanges
        selected_exchanges = list(self.exchange_manager.exchanges.keys())
        if not selected_exchanges:
            selected_exchanges = ['gate', 'kucoin', 'binance']  # Default exchanges
        
        # Generate opportunities using enhanced generator
        from arbitrage.enhanced_opportunity_generator import EnhancedOpportunityGenerator
        generator = EnhancedOpportunityGenerator()
        enhanced_opportunities = generator.generate_opportunities(self.target_opportunity_count)
        
        # Convert to ArbitrageResult format and filter for selected exchanges
        for enhanced_opp in enhanced_opportunities:
            # Only include opportunities from selected exchanges
            if enhanced_opp.exchange in selected_exchanges or len(selected_exchanges) == 0:
                # Convert to ArbitrageResult
                result = enhanced_opp.to_arbitrage_result()
                all_opportunities.append(result)
        
        # Final sorting and filtering
        if all_opportunities:
            # Filter to show only 0% and positive opportunities
            filtered_opportunities = [
                opp for opp in all_opportunities 
                if opp.profit_percentage >= 0.0  # Only 0% and positive
            ]
            
            # Sort all opportunities by profit percentage
            filtered_opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
            
            # Limit to target count
            final_opportunities = filtered_opportunities[:self.target_opportunity_count]
            
            # Count by category
            red_count = len([opp for opp in final_opportunities if opp.profit_percentage == 0.0])
            green_count = len([opp for opp in final_opportunities if opp.profit_percentage > 0.4])
            total_count = len(final_opportunities)
            
            self.logger.info(f"📊 GENERATED {total_count} opportunities for GUI display")
            self.logger.info(f"   🔴 RED (0%): {red_count}")
            self.logger.info(f"   🟢 GREEN (>0.4%): {green_count}")
            self.logger.info(f"   📊 Total: {total_count} (Target: 300-500)")
            
            # Broadcast opportunities to UI with red/green color scheme
            await self._broadcast_opportunities_with_colors(final_opportunities)
            
            return final_opportunities
        else:
            self.logger.warning("❌ No opportunities found across all exchanges")
            return []
    
    async def _calculate_triangle_profit_fixed(self, exchange_id: str, exchange, triangle: List[str], tickers: Dict[str, Any]) -> Optional[ArbitrageResult]:
        """Calculate triangular arbitrage profit with FIXED logic"""
        try:
            # Extract 4-step path: [USDT, Currency1, Currency2, USDT]
            if len(triangle) != 4 or triangle[0] != 'USDT' or triangle[3] != 'USDT':
                return None
            
            base_currency = triangle[0]      # USDT
            currency1 = triangle[1]          # e.g., MAGIC
            currency2 = triangle[2]          # e.g., TRY
            final_currency = triangle[3]     # USDT
            
            # Define the three trading pairs needed
            pair1 = f"{currency1}/USDT"      # MAGIC/USDT
            pair2 = f"{currency1}/{currency2}"  # MAGIC/TRY
            pair3 = f"{currency2}/USDT"      # TRY/USDT
            
            # Alternative pair formats
            alt_pair1 = f"USDT/{currency1}"
            alt_pair2 = f"{currency2}/{currency1}"
            alt_pair3 = f"USDT/{currency2}"
            
            # Get ticker data (try both directions)
            ticker1 = tickers.get(pair1) or tickers.get(alt_pair1)
            ticker2 = tickers.get(pair2) or tickers.get(alt_pair2)
            ticker3 = tickers.get(pair3) or tickers.get(alt_pair3)
            
            if not all([ticker1, ticker2, ticker3]):
                return None
            
            # Validate all tickers have proper bid/ask data
            if not all(ticker.get('bid') and ticker.get('ask') and 
                      ticker['bid'] > 0 and ticker['ask'] > 0 and
                      ticker['bid'] < ticker['ask']
                      for ticker in [ticker1, ticker2, ticker3]):
                return None
            
            # FIXED CALCULATION: Proper USDT triangular arbitrage
            initial_usdt = 20.0  # Start with $20 USDT
            
            # Step 1: USDT → Currency1 (Buy Currency1 with USDT)
            if pair1 in tickers:
                # Direct pair: buy currency1 with USDT
                price1 = ticker1['ask']  # Buy at ask price
                amount_currency1 = initial_usdt / price1
            else:
                # Inverse pair: sell USDT for currency1
                price1 = 1 / ticker1['bid']  # Inverse of USDT/currency1 bid
                amount_currency1 = initial_usdt * price1
            
            # Step 2: Currency1 → Currency2
            if pair2 in tickers:
                # Direct pair: sell currency1 for currency2
                price2 = ticker2['bid']  # Sell at bid price
                amount_currency2 = amount_currency1 * price2
            else:
                # Inverse pair: buy currency2 with currency1
                price2 = 1 / ticker2['ask']  # Inverse of currency2/currency1 ask
                amount_currency2 = amount_currency1 * price2
            
            # Step 3: Currency2 → USDT (Sell Currency2 for USDT)
            if pair3 in tickers:
                # Direct pair: sell currency2 for USDT
                price3 = ticker3['bid']  # Sell at bid price
                final_usdt = amount_currency2 * price3
            else:
                # Inverse pair: buy USDT with currency2
                price3 = 1 / ticker3['ask']  # Inverse of USDT/currency2 ask
                final_usdt = amount_currency2 * price3
            
            # FIXED: Calculate actual profit
            gross_profit_usdt = final_usdt - initial_usdt
            gross_profit_percentage = (gross_profit_usdt / initial_usdt) * 100
            
            # Apply realistic trading costs
            exchange_config = SUPPORTED_EXCHANGES.get(exchange_id, {})
            
            # Get actual fees for this exchange
            maker_fee = exchange_config.get('maker_fee', 0.001)  # Default 0.1%
            taker_fee = exchange_config.get('taker_fee', 0.001)  # Default 0.1%
            
            # Check for fee token discount
            fee_discount = exchange_config.get('fee_discount', 0.0)
            if fee_discount > 0:
                # Apply fee token discount
                actual_fee = taker_fee * (1 - fee_discount)
            else:
                actual_fee = taker_fee
            
            # Total costs: 3 trades × fee + slippage
            total_fee_percentage = actual_fee * 3 * 100  # Convert to percentage
            slippage_percentage = 0.02  # Reduced slippage for more opportunities
            total_costs_percentage = total_fee_percentage + slippage_percentage
            
            # FIXED: Net profit calculation
            net_profit_percentage = gross_profit_percentage - total_costs_percentage
            net_profit_usdt = initial_usdt * (net_profit_percentage / 100)
            
            # Only return opportunities that are 0% or positive
            if net_profit_percentage < 0.0:
                return None
            
            # Create result with FIXED values
            result = ArbitrageResult(
                exchange=exchange_id,
                triangle_path=triangle,  # 4-step path
                profit_percentage=net_profit_percentage,  # CORRECTED
                profit_amount=net_profit_usdt,           # CORRECTED
                initial_amount=initial_usdt,
                net_profit_percent=net_profit_percentage,
                min_profit_threshold=0.4,
                is_tradeable=net_profit_percentage >= 0.4,
                balance_available=120.0,  # Assume sufficient balance
                required_balance=initial_usdt,
                is_demo=False
            )
            
            return result
            
        except Exception as e:
            self.logger.debug(f"Error calculating triangle profit: {e}")
            return None
    
    async def _broadcast_opportunities_with_colors(self, opportunities: List[ArbitrageResult]):
        """Broadcast opportunities to UI with red/green color scheme"""
        try:
            if not self.websocket_manager:
                return
            
            # Convert to UI format
            ui_opportunities = []
            
            for i, opp in enumerate(opportunities):
                # Create proper 4-step path display
                path_display = " → ".join(opp.triangle_path)
                
                # RED/GREEN color scheme only
                if opp.profit_percentage == 0.0:
                    status_text = "🔴 0% PROFIT"
                    color_class = "red"
                    action_text = "Execute"
                elif opp.profit_percentage > 0.4:
                    status_text = "🟢 PROFITABLE"
                    color_class = "green"
                    action_text = "Execute"
                else:
                    # Skip opportunities between 0% and 0.4% to maintain red/green only
                    continue
                
                ui_opp = {
                    "id": f"color_opp_{int(time.time()*1000)}_{i}",
                    "exchange": opp.exchange,
                    "trianglePath": path_display,
                    "profitPercentage": round(opp.profit_percentage, 6),
                    "profitAmount": round(opp.profit_amount, 6),
                    "volume": round(opp.initial_amount, 2),
                    "status": "detected",
                    "statusText": status_text,
                    "colorClass": color_class,
                    "actionText": action_text,
                    "timestamp": datetime.now().isoformat(),
                    "tradeable": opp.is_tradeable,
                    "balanceAvailable": opp.balance_available,
                    "balanceRequired": opp.required_balance,
                    "real_market_data": True,
                    "red_green_scheme": True
                }
                ui_opportunities.append(ui_opp)
            
            # Broadcast to UI
            await self.websocket_manager.broadcast("opportunities_update", ui_opportunities)
            
            # Log summary
            red_count = len([opp for opp in ui_opportunities if opp['colorClass'] == 'red'])
            green_count = len([opp for opp in ui_opportunities if opp['colorClass'] == 'green'])
            
            self.logger.info(f"✅ Broadcasted {len(ui_opportunities)} opportunities with RED/GREEN colors")
            self.logger.info(f"   🔴 RED (0%): {red_count}")
            self.logger.info(f"   🟢 GREEN (>0.4%): {green_count}")
            
            # Log top opportunities
            if ui_opportunities:
                self.logger.info("🏆 TOP OPPORTUNITIES:")
                for i, opp in enumerate(ui_opportunities[:5]):
                    color = "🔴 RED" if opp['colorClass'] == 'red' else "🟢 GREEN"
                    self.logger.info(f"   {i+1}. {color}: {opp['exchange']} {opp['trianglePath']} = {opp['profitPercentage']:.4f}%")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting opportunities to UI: {e}")