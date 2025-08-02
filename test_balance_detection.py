#!/usr/bin/env python3
"""
Test script to debug balance detection issues
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

load_dotenv()

async def test_balance_detection():
    """Test balance detection and USD conversion"""
    logger = setup_logger('TestBalance')
    
    print("🔍 Testing Balance Detection")
    print("=" * 50)
    
    # Configuration
    config = {
        'exchange_id': 'binance',
        'api_key': os.getenv('BINANCE_API_KEY'),
        'api_secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'paper_trading': False
    }
    
    if not config['api_key'] or not config['api_secret']:
        logger.error("❌ No API credentials found")
        return False
    
    try:
        logger.info("🚀 Testing balance detection...")
        exchange = UnifiedExchange(config)
        
        if not await exchange.connect():
            logger.error("❌ Failed to connect to Binance")
            return False
        
        logger.info("✅ Connected to Binance")
        
        # Test raw balance fetch
        logger.info("📊 Fetching raw balance...")
        raw_balance = await exchange.exchange.fetch_balance()
        logger.info(f"Raw balance keys: {list(raw_balance.keys())}")
        
        # Test processed balance
        logger.info("💰 Testing processed balance...")
        balance = await exchange.get_account_balance()
        logger.info(f"Processed balance: {balance}")
        
        if balance:
            logger.info("✅ Balance detection working!")
            
            # Test USD calculation
            logger.info("💵 Testing USD calculation...")
            usd_value = await exchange._calculate_usd_value(balance)
            logger.info(f"Total USD value: ${usd_value:.2f}")
            
            # Show detailed breakdown
            logger.info("📋 Balance breakdown:")
            for currency, amount in balance.items():
                logger.info(f"   {currency}: {amount:.8f}")
                
        else:
            logger.error("❌ No balance detected")
            
            # Debug raw balance structure
            logger.info("🔍 Debugging raw balance structure...")
            for key, value in raw_balance.items():
                if key not in ['info', 'timestamp', 'datetime']:
                    logger.info(f"   {key}: {value} (type: {type(value)})")
        
        await exchange.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("🔺 Balance Detection Test")
    print("=" * 50)
    
    try:
        success = asyncio.run(test_balance_detection())
        if success:
            print("\n✅ Balance detection test completed!")
        else:
            print("\n❌ Balance detection test failed.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")