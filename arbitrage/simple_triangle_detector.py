#!/usr/bin/env python3
"""
Simple Triangular Arbitrage Detector
Fetches ALL Binance tickers and calculates triangular arbitrage opportunities
"""

import asyncio
import websockets
import json
import time
from typing import Dict, List, Any, Set, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('SimpleTriangleDetector')

@dataclass
class TriangleOpportunity:
    """Simple triangular arbitrage opportunity"""
    d1: str  # Base currency
    d2: str  # Intermediate currency  
    d3: str  # Quote currency
    lv1: str  # First pair symbol
    lv2: str  # Second pair symbol
    lv3: str  # Third pair symbol
    value: float  # Profit percentage
    tpath: str  # Trading path description
    
    def __str__(self):
        return f"{self.d1}→{self.d2}→{self.d3}→{self.d1}: {self.value:.3f}%"

class SimpleTriangleDetector:
    """Simple triangular arbitrage detector using Binance WebSocket - Based on JavaScript logic"""
    
    def __init__(self, min_profit_pct: float = 0.5, exchange_id: str = 'binance'):
        self.min_profit_pct = min_profit_pct
        self.exchange_id = exchange_id
        self.exchange_config = self._get_exchange_config(exchange_id)
        self.pairs: List[Dict] = []
        self.sym_val_j: Dict[str, Dict[str, float]] = {}
        self.websocket = None
        self.running = False
        self.opportunities_found = 0
        self.current_opportunities: List[TriangleOpportunity] = []
        
        logger.info(f"🚀 Simple Triangle Detector initialized for {self.exchange_config['name']}")
        logger.info(f"   Exchange: {self.exchange_config['name']}")
        logger.info(f"   API URL: {self.exchange_config['api_url']}")
        logger.info(f"   WebSocket URL: {self.exchange_config['websocket_url']}")
        logger.info(f"   Min Profit: {min_profit_pct}%")
    
    def _get_exchange_config(self, exchange_id: str) -> Dict[str, Any]:
        """Get exchange configuration"""
        from config.exchanges_config import SUPPORTED_EXCHANGES
        return SUPPORTED_EXCHANGES.get(exchange_id, SUPPORTED_EXCHANGES['binance'])
    
    async def get_pairs(self):
        """Get trading pairs and build triangular paths - Exact JavaScript logic"""
        import aiohttp
        
        logger.info("📡 Fetching exchange info...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.binance.com/api/v3/exchangeInfo') as response:
                if response.status == 200:
                    e_info = await response.json()
                    
                    # Get all unique symbols (currencies)
                    symbols = list(set([
                        asset for symbol_info in e_info['symbols']
                        if symbol_info['status'] == 'TRADING'
                        for asset in [symbol_info['baseAsset'], symbol_info['quoteAsset']]
                    ]))
                    
                    # Get valid trading pairs
                    valid_pairs = [
                        symbol_info['symbol'] for symbol_info in e_info['symbols']
                        if symbol_info['status'] == 'TRADING'
                    ]
                    
                    # Initialize price tracking
                    for symbol in valid_pairs:
                        self.sym_val_j[symbol] = {'bidPrice': 0, 'askPrice': 0}
                    
                    logger.info(f"✅ Found {len(symbols)} currencies and {len(valid_pairs)} trading pairs")
                    
                    # Build triangular paths - EXACT JavaScript logic
                    self.pairs = []
                    
                    for d1 in symbols:
                        for d2 in symbols:
                            for d3 in symbols:
                                if not (d1 == d2 or d2 == d3 or d3 == d1):
                                    lv1, lv2, lv3 = [], [], []
                                    l1, l2, l3 = '', '', ''
                                    
                                    # Level 1: d1 -> d2
                                    if f"{d1}{d2}" in self.sym_val_j:
                                        lv1.append(f"{d1}{d2}")
                                        l1 = 'num'
                                    if f"{d2}{d1}" in self.sym_val_j:
                                        lv1.append(f"{d2}{d1}")
                                        l1 = 'den'
                                    
                                    # Level 2: d2 -> d3
                                    if f"{d2}{d3}" in self.sym_val_j:
                                        lv2.append(f"{d2}{d3}")
                                        l2 = 'num'
                                    if f"{d3}{d2}" in self.sym_val_j:
                                        lv2.append(f"{d3}{d2}")
                                        l2 = 'den'
                                    
                                    # Level 3: d3 -> d1
                                    if f"{d3}{d1}" in self.sym_val_j:
                                        lv3.append(f"{d3}{d1}")
                                        l3 = 'num'
                                    if f"{d1}{d3}" in self.sym_val_j:
                                        lv3.append(f"{d1}{d3}")
                                        l3 = 'den'
                                    
                                    # If all three levels have valid pairs, add to triangular paths
                                    if lv1 and lv2 and lv3:
                                        self.pairs.append({
                                            'l1': l1, 'l2': l2, 'l3': l3,
                                            'd1': d1, 'd2': d2, 'd3': d3,
                                            'lv1': lv1[0], 'lv2': lv2[0], 'lv3': lv3[0],
                                            'value': -100, 'tpath': ''
                                        })
                    
                    logger.info(f"✅ Built {len(self.pairs)} triangular arbitrage paths")
                    return True
                else:
                    logger.error(f"Failed to fetch exchange info: {response.status}")
                    return False
    
    def process_data(self, data: str):
        """Process WebSocket data from the selected exchange"""
        try:
            data = json.loads(data)
            
            # Process based on exchange format
            if self.exchange_id == 'binance':
                self._process_binance_data(data)
            elif self.exchange_id == 'kucoin':
                self._process_kucoin_data(data)
            elif self.exchange_id == 'gate':
                self._process_gate_data(data)
            elif self.exchange_id == 'bybit':
                self._process_bybit_data(data)
            else:
                # Fallback to Binance format
                self._process_binance_data(data)
                
        except Exception as e:
            # Only log debug info if it's a real error, not just data format issues
            if "has no attribute 'get'" not in str(e):
                logger.debug(f"Problematic data type: {type(data)}")
                logger.debug(f"Data content: {str(data)[:200]}...")
            logger.error(f"Error processing {self.exchange_config['name']} WebSocket data: {e}")
    
    def _process_binance_data(self, data):
        """Process Binance WebSocket ticker data"""
        if isinstance(data, list):
            updates_processed = 0
            for ticker in data:
                if isinstance(ticker, dict):
                    symbol = ticker.get('s', '')
                    bid_price = ticker.get('b', 0)
                    ask_price = ticker.get('a', 0)
                    
                    if symbol and bid_price and ask_price and symbol in self.sym_val_j:
                        try:
                            self.sym_val_j[symbol]['bidPrice'] = float(bid_price)
                            self.sym_val_j[symbol]['askPrice'] = float(ask_price)
                            updates_processed += 1
                        except (ValueError, TypeError):
                            continue
            
            if updates_processed >= 50:
                self._calculate_opportunities()
    
    def _process_kucoin_data(self, data):
        """Process KuCoin WebSocket ticker data"""
        if data.get('type') == 'message' and data.get('topic') == '/market/ticker:all':
            ticker_data = data.get('data', {})
            symbol = ticker_data.get('symbol', '').replace('-', '')  # Convert BTC-USDT to BTCUSDT
            
            if symbol and symbol in self.sym_val_j:
                try:
                    self.sym_val_j[symbol]['bidPrice'] = float(ticker_data.get('buy', 0))
                    self.sym_val_j[symbol]['askPrice'] = float(ticker_data.get('sell', 0))
                    self._calculate_opportunities()
                except (ValueError, TypeError):
                    pass
    
    def _process_gate_data(self, data):
        """Process Gate.io WebSocket ticker data"""
        if data.get('method') == 'ticker.update':
            params = data.get('params', [])
            if len(params) >= 2:
                symbol = params[0].replace('_', '')  # Convert BTC_USDT to BTCUSDT
                ticker_data = params[1]
                
                if symbol and symbol in self.sym_val_j:
                    try:
                        # Gate.io ticker format: [change_percentage, last_price, quote_volume, base_volume, high_24h, low_24h, bid, ask]
                        if len(ticker_data) >= 8:
                            self.sym_val_j[symbol]['bidPrice'] = float(ticker_data[6])
                            self.sym_val_j[symbol]['askPrice'] = float(ticker_data[7])
                            self._calculate_opportunities()
                    except (ValueError, TypeError, IndexError):
                        pass
    
    def _process_bybit_data(self, data):
        """Process Bybit WebSocket ticker data"""
        if data.get('topic') == 'tickers.spot':
            ticker_data = data.get('data', {})
            symbol = ticker_data.get('symbol', '')  # Already in BTCUSDT format
            
            if symbol and symbol in self.sym_val_j:
                try:
                    self.sym_val_j[symbol]['bidPrice'] = float(ticker_data.get('bid1Price', 0))
                    self.sym_val_j[symbol]['askPrice'] = float(ticker_data.get('ask1Price', 0))
                    self._calculate_opportunities()
                except (ValueError, TypeError):
                    pass
    
    def _calculate_opportunities(self):
        """Calculate arbitrage opportunities - EXACT JavaScript logic"""
        try:
                
                profitable_opportunities = []
                
                # Define valid currencies for the selected exchange
                valid_currencies = self._get_valid_currencies_for_exchange()
                
                for pair_data in self.pairs:
                    # CRITICAL: Filter out triangles with invalid currencies
                    d1, d2, d3 = pair_data['d1'], pair_data['d2'], pair_data['d3']
                    
                    # Skip triangles with invalid currencies for this exchange
                    if not all(currency in valid_currencies for currency in [d1, d2, d3]):
                        continue
                    
                    # CRITICAL: Only process USDT-based triangles for profitability
                    if d1 != 'USDT':
                        continue
                    
                    # Check if all prices are available
                    lv1_data = self.sym_val_j.get(pair_data['lv1'], {})
                    lv2_data = self.sym_val_j.get(pair_data['lv2'], {})
                    lv3_data = self.sym_val_j.get(pair_data['lv3'], {})
                    
                    if (lv1_data.get('bidPrice', 0) > 0 and 
                        lv1_data.get('askPrice', 0) > 0 and
                        lv2_data.get('bidPrice', 0) > 0 and 
                        lv2_data.get('askPrice', 0) > 0 and
                        lv3_data.get('bidPrice', 0) > 0 and
                        lv3_data.get('askPrice', 0) > 0):
                        
                        # Level 1 calculation
                        if pair_data['l1'] == 'num':
                            lv_calc = lv1_data['bidPrice']
                            lv_str = f"{pair_data['d1']}→{pair_data['lv1']}[bid:{lv1_data['bidPrice']}]→{pair_data['d2']}<br/>"
                        else:
                            lv_calc = 1 / lv1_data['askPrice']
                            lv_str = f"{pair_data['d1']}→{pair_data['lv1']}[ask:{lv1_data['askPrice']}]→{pair_data['d2']}<br/>"
                        
                        # Level 2 calculation
                        if pair_data['l2'] == 'num':
                            lv_calc *= lv2_data['bidPrice']
                            lv_str += f"{pair_data['d2']}→{pair_data['lv2']}[bid:{lv2_data['bidPrice']}]→{pair_data['d3']}<br/>"
                        else:
                            lv_calc *= 1 / lv2_data['askPrice']
                            lv_str += f"{pair_data['d2']}→{pair_data['lv2']}[ask:{lv2_data['askPrice']}]→{pair_data['d3']}<br/>"
                        
                        # Level 3 calculation
                        if pair_data['l3'] == 'num':
                            lv_calc *= lv3_data['bidPrice']
                            lv_str += f"{pair_data['d3']}→{pair_data['lv3']}[bid:{lv3_data['bidPrice']}]→{pair_data['d1']}"
                        else:
                            lv_calc *= 1 / lv3_data['askPrice']
                            lv_str += f"{pair_data['d3']}→{pair_data['lv3']}[ask:{lv3_data['askPrice']}]→{pair_data['d1']}"
                        
                        # Calculate profit percentage with safety checks
                        try:
                            if lv_calc > 0 and lv_calc != float('inf'):
                                pair_data['tpath'] = lv_str
                                gross_profit_pct = (lv_calc - 1) * 100
                                
                                # Apply exchange-specific trading costs
                                trading_costs = self._get_trading_costs_for_exchange()
                                net_profit_pct = gross_profit_pct - trading_costs
                                pair_data['value'] = round(net_profit_pct, 6)
                                
                                # Add to profitable opportunities if above threshold and realistic
                                if (pair_data['value'] > self.min_profit_pct and 
                                    pair_data['value'] < 10.0 and  # Max 10% profit (realistic)
                                    pair_data['value'] > -5.0):    # Min -5% loss (realistic)
                                    
                                    opportunity = TriangleOpportunity(
                                        d1=pair_data['d1'],
                                        d2=pair_data['d2'], 
                                        d3=pair_data['d3'],
                                        lv1=pair_data['lv1'],
                                        lv2=pair_data['lv2'],
                                        lv3=pair_data['lv3'],
                                        value=pair_data['value'],
                                        tpath=pair_data['tpath']
                                    )
                                    profitable_opportunities.append(opportunity)
                                    self.opportunities_found += 1
                        except (ZeroDivisionError, OverflowError, ValueError):
                            continue
                
                # Sort by profit percentage (highest first)
                profitable_opportunities.sort(key=lambda x: x.value, reverse=True)
                
                # Update current opportunities
                self.current_opportunities = profitable_opportunities[:10]  # Top 10
                
                if profitable_opportunities:
                    # Only log if opportunities changed significantly
                    current_time = time.time()
                    if not hasattr(self, '_last_log_time') or current_time - self._last_log_time > 10:
                        logger.info(f"💎 Found {len(profitable_opportunities)} profitable opportunities on {self.exchange_config['name']}!")
                        for i, opp in enumerate(profitable_opportunities[:3]):
                            logger.info(f"   {i+1}. {opp}")
                        self._last_log_time = current_time
                
        except Exception as e:
            logger.error(f"Error calculating opportunities for {self.exchange_config['name']}: {e}")
    
    def _get_valid_currencies_for_exchange(self) -> Set[str]:
        """Get valid currencies for the selected exchange"""
        if self.exchange_id == 'gate':
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
        elif self.exchange_id == 'kucoin':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'KCS'  # KuCoin's native token
            }
        elif self.exchange_id == 'binance':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP'
            }
        elif self.exchange_id == 'bybit':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'BIT'  # Bybit's native token
            }
        else:
            # Default to major currencies
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET'
            }
    
    def _get_trading_costs_for_exchange(self) -> float:
        """Get trading costs percentage for the selected exchange"""
        if self.exchange_id == 'gate':
            return 0.6  # 0.6% total costs (0.2% per trade × 3 trades)
        elif self.exchange_id == 'kucoin':
            return 0.3  # 0.3% total costs (0.1% per trade × 3 trades)
        elif self.exchange_id == 'binance':
            return 0.3  # 0.3% total costs (0.1% per trade × 3 trades)
        elif self.exchange_id == 'bybit':
            return 0.3  # 0.3% total costs (0.1% per trade × 3 trades)
        else:
            return 0.4  # Default 0.4% total costs
    
    async def start_websocket_stream(self):
        """Start WebSocket stream for the selected exchange"""
        websocket_url = self.exchange_config['websocket_url']
        
        logger.info(f"🌐 Connecting to {self.exchange_config['name']} WebSocket...")
        logger.info(f"   URL: {websocket_url}")
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                async with websockets.connect(websocket_url) as websocket:
                    self.websocket = websocket
                    self.running = True
                    logger.info(f"✅ Connected to {self.exchange_config['name']} WebSocket")
                    
                    # Subscribe to all ticker data
                    subscribe_message = {
                        "method": "SUBSCRIBE",
                        "params": ["!ticker@arr"],
                        "id": 121212131
                    }
                    
                    await websocket.send(json.dumps(subscribe_message))
                    logger.info("📡 Subscribed to all ticker data stream")
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    
                    # Send exchange-specific subscription message
                    await self._send_subscription_message(websocket)
                    
                    # Process incoming messages
                    async for message in websocket:
                        try:
                            if message and message.strip():
                                self.process_data(message)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            logger.debug(f"Message that caused error: {message[:200]}...")
                            
            except Exception as e:
                retry_count += 1
                logger.error(f"{self.exchange_config['name']} WebSocket connection failed (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max {self.exchange_config['name']} WebSocket retry attempts reached")
                    break
        
        self.running = False
        logger.info(f"{self.exchange_config['name']} WebSocket stream ended")
    
    async def _send_subscription_message(self, websocket):
        """Send exchange-specific subscription message"""
        try:
            if self.exchange_id == 'binance':
                # Binance: Subscribe to all ticker data
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": ["!ticker@arr"],
                    "id": 121212131
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info("📡 Subscribed to Binance all ticker data stream")
                
            elif self.exchange_id == 'kucoin':
                # KuCoin: Subscribe to all ticker data
                subscribe_message = {
                    "id": int(time.time() * 1000),
                    "type": "subscribe",
                    "topic": "/market/ticker:all",
                    "response": True
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info("📡 Subscribed to KuCoin all ticker data stream")
                
            elif self.exchange_id == 'gate':
                # Gate.io: Subscribe to all ticker data
                subscribe_message = {
                    "method": "ticker.subscribe",
                    "params": [],
                    "id": 12345
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info("📡 Subscribed to Gate.io all ticker data stream")
                
            elif self.exchange_id == 'bybit':
                # Bybit: Subscribe to all ticker data
                subscribe_message = {
                    "op": "subscribe",
                    "args": ["tickers.spot"]
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info("📡 Subscribed to Bybit all ticker data stream")
            
            else:
                # Default to Binance format for unknown exchanges
                subscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": ["!ticker@arr"],
                    "id": 121212131
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"📡 Subscribed to {self.exchange_config['name']} ticker data (using Binance format)")
                
        except Exception as e:
            logger.error(f"Error sending subscription message to {self.exchange_config['name']}: {e}")
    
    def get_current_opportunities(self) -> List[TriangleOpportunity]:
        """Get current profitable opportunities"""
        return self.current_opportunities.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        return {
            'running': self.running,
            'triangular_paths': len(self.pairs),
            'opportunities_found': self.opportunities_found,
            'current_opportunities': len(self.current_opportunities)
        }

async def main():
    """Test the simple triangle detector"""
    detector = SimpleTriangleDetector(min_profit_pct=0.01)  # 0.01% minimum
    
    # Initialize
    if not await detector.get_pairs():
        logger.error("Failed to initialize detector")
        return
    
    # Start WebSocket stream
    try:
        await detector.start_websocket_stream()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    print("🚀 Simple Triangular Arbitrage Detector")
    print("=" * 70)
    asyncio.run(main())