#!/usr/bin/env python3
"""
Test script to verify API connection and balance detection
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

load_dotenv()

async def test_unified_exchange_connection():
    """Test Binance API connection and balance retrieval"""
    
    logger = setup_logger('TestConnection')
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ No API credentials found in .env file")
        return False
    
    logger.info(f"🔑 Testing API Key: {api_key[:8]}...{api_key[-4:]}")
    
    try:
        # Create unified exchange instance
        config = {
            'exchange_id': 'binance',
            'api_key': api_key,
            'api_secret': api_secret,
            'sandbox': False,
            'paper_trading': False,
            'fee_token': 'BNB',
            'fee_discount': 0.25
        }
        
        exchange = UnifiedExchange(config)
        
        logger.info("📡 Connecting to Binance...")
        
        if not await exchange.connect():
            logger.error("❌ Failed to connect to Binance")
            return False
        
        logger.info("✅ Connected! Testing balance detection...")
        
        # Test balance detection
        balance = await exchange.get_account_balance()
        
        if balance:
            logger.info("✅ Balance detection working!")
            logger.info(f"Found {len(balance)} currencies with balance")
            
            for currency, amount in balance.items():
                logger.info(f"  {currency}: {amount:.8f}")
        else:
            logger.warning("⚠️ No balance detected (account may be empty)")
        
        # Test ticker data
        logger.info("📊 Testing market data...")
        ticker = await exchange.get_ticker('BTC/USDT')
        if ticker and ticker.get('last'):
            logger.info(f"✅ BTC/USDT: ${ticker['last']:.2f}")
        else:
            logger.warning("⚠️ Failed to get ticker data")
        
        await exchange.disconnect()
        logger.info("✅ UnifiedExchange connection test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🔺 UnifiedExchange Connection Test")
    print("=" * 50)
    
    try:
        success = asyncio.run(test_unified_exchange_connection())
        if success:
            print("\n🎉 All tests passed! Your bot should work correctly.")
        else:
            print("\n❌ Tests failed. Please fix the issues above.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")