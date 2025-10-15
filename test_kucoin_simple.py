#!/usr/bin/env python3
import os
import asyncio
import aiohttp
import hmac
import hashlib
import base64
import json
import time
from dotenv import load_dotenv

load_dotenv()

class SimpleKucoinTester:
    def __init__(self):
        self.api_key = os.getenv('KUCOIN_API_KEY')
        self.api_secret = os.getenv('KUCOIN_API_SECRET')
        self.api_passphrase = os.getenv('KUCOIN_PASSPHRASE')
        self.spot_base_url = "https://api.kucoin.com"
        self.futures_base_url = "https://api-futures.kucoin.com"
        self.session = None
        
    async def _ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = ""):
        """Generate KuCoin API signature"""
        message = f"{timestamp}{method}{endpoint}{body}"
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        passphrase = base64.b64encode(
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
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
    
    async def test_spot_connection(self):
        """Test KuCoin Spot API"""
        print("🔍 Testing Spot API...")
        try:
            await self._ensure_session()
            
            # Public endpoint first (no auth required)
            public_url = f"{self.spot_base_url}/api/v1/market/orderbook/level1?symbol=BTC-USDT"
            async with self.session.get(public_url) as response:
                data = await response.json()
                if data.get('code') == '200000':
                    price = float(data['data']['price'])
                    print(f"✅ SPOT PUBLIC: BTC Price = ${price:,.2f}")
                else:
                    print(f"❌ Spot public API error: {data}")
            
            # Test authenticated endpoint
            endpoint = "/api/v1/accounts"
            timestamp = str(int(time.time() * 1000))
            headers = self._generate_signature(timestamp, "GET", endpoint)
            
            url = f"{self.spot_base_url}{endpoint}"
            async with self.session.get(url, headers=headers) as response:
                data = await response.json()
                if data.get('code') == '200000':
                    print("✅ SPOT AUTH: Authentication successful")
                    return True
                else:
                    print(f"❌ Spot auth failed: {data.get('msg', 'Unknown error')}")
                    return False
                    
        except Exception as e:
            print(f"❌ Spot API error: {e}")
            return False
    
    async def test_futures_connection(self):
        """Test KuCoin Futures API"""
        print("🔍 Testing Futures API...")
        try:
            await self._ensure_session()
            
            # Public endpoint first
            public_url = f"{self.futures_base_url}/api/v1/contracts/active"
            async with self.session.get(public_url) as response:
                data = await response.json()
                if data.get('code') == '200000':
                    contracts = [c for c in data['data'] if 'XBT' in c['symbol']]
                    if contracts:
                        print(f"✅ FUTURES PUBLIC: Found {len(contracts)} BTC contracts")
                    else:
                        print("❌ No BTC contracts found")
                else:
                    print(f"❌ Futures public API error: {data}")
            
            # Test ticker with authentication
            endpoint = "/api/v1/ticker?symbol=XBTUSDTM"
            timestamp = str(int(time.time() * 1000))
            headers = self._generate_signature(timestamp, "GET", endpoint)
            
            url = f"{self.futures_base_url}{endpoint}"
            async with self.session.get(url, headers=headers) as response:
                data = await response.json()
                print(f"🔍 DEBUG Futures Response: {data}")  # Show raw response
                
                if data.get('code') == '200000' and 'data' in data:
                    price = float(data['data'].get('price', 0))
                    if price > 0:
                        print(f"✅ FUTURES AUTH: BTC Price = ${price:,.2f}")
                        return True
                    else:
                        print("❌ Got $0 price from futures API")
                else:
                    error_msg = data.get('msg', 'Unknown error')
                    print(f"❌ Futures auth failed: {error_msg}")
                    return False
                    
        except Exception as e:
            print(f"❌ Futures API error: {e}")
            return False
    
    async def test_without_auth(self):
        """Test without API keys first"""
        print("🔍 Testing without authentication...")
        try:
            await self._ensure_session()
            
            # Spot public
            spot_url = "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT"
            async with self.session.get(spot_url) as response:
                data = await response.json()
                if data.get('code') == '200000':
                    price = float(data['data']['price'])
                    print(f"✅ SPOT PUBLIC: BTC = ${price:,.2f}")
                else:
                    print(f"❌ Spot public failed: {data}")
            
            # Futures public  
            futures_url = "https://api-futures.kucoin.com/api/v1/contracts/active/XBTUSDTM"
            async with self.session.get(futures_url) as response:
                data = await response.json()
                if data.get('code') == '200000':
                    mark_price = float(data['data']['markPrice'])
                    print(f"✅ FUTURES PUBLIC: BTC = ${mark_price:,.2f}")
                else:
                    print(f"❌ Futures public failed: {data}")
                    
        except Exception as e:
            print(f"❌ Public API error: {e}")
    
    async def close(self):
        if self.session:
            await self.session.close()

async def main():
    tester = SimpleKucoinTester()
    
    print("=" * 50)
    print("KuCoin API Connection Test")
    print("=" * 50)
    
    # First test without authentication
    await tester.test_without_auth()
    
    print("\n" + "-" * 50)
    
    # Check if we have API keys
    if not tester.api_key or not tester.api_secret:
        print("❌ Missing API keys in .env file")
        return
    
    print("Testing with authentication...")
    
    # Test authenticated endpoints
    spot_ok = await tester.test_spot_connection()
    futures_ok = await tester.test_futures_connection()
    
    print("\n" + "=" * 50)
    print("FINAL RESULTS:")
    print(f"Spot API: {'✅ WORKING' if spot_ok else '❌ FAILED'}")
    print(f"Futures API: {'✅ WORKING' if futures_ok else '❌ FAILED'}")
    
    if spot_ok and futures_ok:
        print("🎉 Both APIs are working! Your bot should work now.")
    else:
        print("🔧 There are issues with your API configuration.")
    
    await tester.close()

if __name__ == "__main__":
    asyncio.run(main())