import hmac
import hashlib
import base64
import json
import time
import aiohttp
import asyncio
from typing import Dict, List, Optional
from exchanges.base_exchange import BaseExchange

class KuCoinFuturesExchange(BaseExchange):
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, is_sandbox: bool = False):
        config = {
            'exchange_id': 'kucoin_futures',
            'api_key': api_key,
            'api_secret': api_secret,
            'is_sandbox': is_sandbox
        }
        super().__init__(config)
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = "https://api-futures.kucoin.com" if not is_sandbox else "https://api-sandbox-futures.kucoin.com"
        self.session = None
        
    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = "") -> Dict[str, str]:
        """FIXED: Correct signature generation for KuCoin Futures"""
        # Create the message to sign
        message = f"{timestamp}{method}{endpoint}{body}"
        
        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Generate passphrase signature (FIXED: use separate method)
        passphrase_signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                self.api_passphrase.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase_signature,  # FIXED: use the generated signature
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
    
    async def get_futures_ticker(self, symbol: str) -> Dict:
        """Get futures ticker price - FIXED VERSION"""
        await self._ensure_session()
        
        # Convert symbol to KuCoin Futures format
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        
        endpoint = f"/api/v1/ticker?symbol={kucoin_symbol}"
        timestamp = str(int(time.time() * 1000))
        headers = self._generate_signature(timestamp, "GET", endpoint)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, headers=headers) as response:
                data = await response.json()
                
                # Debug: Print the raw response
                print(f"🔍 DEBUG - Ticker Response for {symbol}: {data}")
                
                # FIXED: Proper response parsing
                if data.get('code') == '200000' and 'data' in data:
                    ticker_data = data['data']
                    return {
                        'symbol': symbol,
                        'last': float(ticker_data.get('price', 0)),
                        'bid': float(ticker_data.get('bestBidPrice', 0)),
                        'ask': float(ticker_data.get('bestAskPrice', 0)),
                        'high': float(ticker_data.get('highPrice', 0)),
                        'low': float(ticker_data.get('lowPrice', 0)),
                        'volume': float(ticker_data.get('size', 0)),
                        'timestamp': ticker_data.get('ts')
                    }
                else:
                    print(f"❌ Ticker API Error: {data.get('msg', 'Unknown error')}")
                    return {'last': 0, 'bid': 0, 'ask': 0}
                    
        except Exception as e:
            print(f"❌ Ticker request failed: {e}")
            return {'last': 0, 'bid': 0, 'ask': 0}

    def _convert_symbol_to_kucoin_futures(self, symbol: str) -> str:
        """Convert standard symbol format to KuCoin Futures format"""
        # Remove / and - from symbol
        clean_symbol = symbol.replace('/', '').replace('-', '')
        
        # KuCoin Futures uses XBT instead of BTC
        if 'BTC' in clean_symbol:
            clean_symbol = clean_symbol.replace('BTC', 'XBT')
        
        # Add 'M' for perpetual futures
        if not clean_symbol.endswith('M'):
            clean_symbol += 'M'
            
        return clean_symbol

    async def get_ticker(self, symbol: str) -> Dict:
        """Alias for get_futures_ticker for compatibility"""
        return await self.get_futures_ticker(symbol)
    
    async def test_connection(self) -> bool:
        """Test if API connection works"""
        try:
            ticker = await self.get_futures_ticker("BTC/USDT")
            price = ticker.get('last', 0)
            if price > 0:
                print(f"✅ Futures Connection OK - BTC Price: ${price:,.2f}")
                return True
            else:
                print("❌ Futures Connection Failed - Got $0 price")
                return False
        except Exception as e:
            print(f"❌ Futures Connection Error: {e}")
            return False
    
    async def create_futures_order(self, symbol: str, side: str, order_type: str, 
                                 size: float, price: Optional[float] = None,
                                 leverage: int = 1) -> Dict:
        """Create futures order"""
        await self._ensure_session()
        
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        endpoint = "/api/v1/orders"
        
        body = {
            "symbol": kucoin_symbol,
            "side": side,
            "type": order_type,
            "size": size,
            "leverage": leverage
        }
        if price:
            body["price"] = price
        
        timestamp = str(int(time.time() * 1000))
        body_str = json.dumps(body)
        headers = self._generate_signature(timestamp, "POST", endpoint, body_str)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.post(url, headers=headers, data=body_str) as response:
            return await response.json()
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for futures trading"""
        await self._ensure_session()
        
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        endpoint = "/api/v1/leverage"
        
        body = {
            "symbol": kucoin_symbol,
            "leverage": leverage
        }
        
        timestamp = str(int(time.time() * 1000))
        body_str = json.dumps(body)
        headers = self._generate_signature(timestamp, "POST", endpoint, body_str)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.post(url, headers=headers, data=body_str) as response:
            return await response.json()
    
    async def get_futures_position(self, symbol: str) -> Dict:
        """Get current futures position"""
        await self._ensure_session()
        
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        endpoint = f"/api/v1/position?symbol={kucoin_symbol}"
        
        timestamp = str(int(time.time() * 1000))
        headers = self._generate_signature(timestamp, "GET", endpoint)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, headers=headers) as response:
            return await response.json()
    
    async def close_futures_position(self, symbol: str) -> Dict:
        """Close futures position"""
        await self._ensure_session()
        
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        endpoint = "/api/v1/orders"
        
        body = {
            "symbol": kucoin_symbol,
            "type": "market",
            "size": 0,  # Close position
            "closeOrder": True
        }
        
        timestamp = str(int(time.time() * 1000))
        body_str = json.dumps(body)
        headers = self._generate_signature(timestamp, "POST", endpoint, body_str)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.post(url, headers=headers, data=body_str) as response:
            return await response.json()
    
    async def get_futures_balance(self, currency: str = "USDT") -> float:
        """Get futures account balance"""
        await self._ensure_session()
        endpoint = "/api/v1/account-overview"
        
        timestamp = str(int(time.time() * 1000))
        headers = self._generate_signature(timestamp, "GET", endpoint)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            if data.get('code') == '200000' and 'data' in data:
                # FIXED: Proper balance extraction
                account_data = data['data']
                if 'availableBalance' in account_data:
                    return float(account_data['availableBalance'])
            return 0.0
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()

    # ---- BaseExchange Required Methods ----

    async def connect(self) -> bool:
        """Establish connection to the exchange"""
        await self._ensure_session()
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        """Close the exchange connection"""
        await self.close()
        self.is_connected = False

    async def get_trading_pairs(self) -> List[str]:
        """Get all available trading pairs"""
        await self._ensure_session()
        endpoint = "/api/v1/contracts/active"
        
        timestamp = str(int(time.time() * 1000))
        headers = self._generate_signature(timestamp, "GET", endpoint)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            if data.get('code') == '200000' and 'data' in data:
                return [contract['symbol'] for contract in data['data']]
            return []

    async def get_orderbook(self, symbol: str, depth: int = 5) -> Dict:
        """Get orderbook for symbol"""
        await self._ensure_session()
        
        kucoin_symbol = self._convert_symbol_to_kucoin_futures(symbol)
        endpoint = f"/api/v1/level2/depth{depth}?symbol={kucoin_symbol}"
        
        timestamp = str(int(time.time() * 1000))
        headers = self._generate_signature(timestamp, "GET", endpoint)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, headers=headers) as response:
            data = await response.json()
            if data.get('code') == '200000' and 'data' in data:
                return {
                    'bids': [[float(p), float(s)] for p, s in data['data']['bids']],
                    'asks': [[float(p), float(s)] for p, s in data['data']['asks']]
                }
            return {'bids': [], 'asks': []}

    async def start_websocket_stream(self, symbols: List[str], callback) -> None:
        """Start websocket stream - not implemented for futures"""
        pass

    async def place_market_order(self, symbol: str, side: str, qty: float) -> Dict:
        """Place market order"""
        return await self.create_futures_order(
            symbol=symbol,
            side=side.lower(),
            order_type="market",
            size=qty
        )

    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balance"""
        balance_usdt = await self.get_futures_balance("USDT")
        return {"USDT": balance_usdt}

    async def get_trading_fees(self, symbol: str) -> tuple:
        """Get trading fees (maker, taker)"""
        return (0.0002, 0.0006)  # KuCoin Futures default fees

    async def check_fee_token_balance(self) -> float:
        """Check fee token balance - KuCoin uses USDT for fees"""
        return await self.get_futures_balance("USDT")

    async def check_bnb_balance(self) -> float:
        """Check BNB balance - not applicable for KuCoin"""
        return 0.0