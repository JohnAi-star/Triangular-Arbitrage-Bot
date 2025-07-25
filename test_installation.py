#!/usr/bin/env python3
"""
Test script to verify the bot installation and configuration.
"""

import sys
import asyncio
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing module imports...")
    
    modules = {
        'ccxt': 'CCXT cryptocurrency exchange library',
        'websockets': 'WebSocket client/server library',
        'dotenv': 'Python-dotenv for environment variables',
        'numpy': 'NumPy for numerical computing',
        'pandas': 'Pandas for data analysis',
        'aiofiles': 'Async file operations',
        'colorlog': 'Colored logging output'
    }
    
    failed_imports = []
    
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"✅ {module} - {description}")
        except ImportError as e:
            print(f"❌ {module} - FAILED: {e}")
            failed_imports.append(module)
    
    return len(failed_imports) == 0, failed_imports

def test_configuration():
    """Test configuration loading."""
    print("\n🔧 Testing configuration...")
    
    try:
        from config.config import Config
        
        # Test basic config loading
        print(f"✅ Configuration loaded")
        print(f"   - Min profit: {Config.MIN_PROFIT_PERCENTAGE}%")
        print(f"   - Max trade amount: {Config.MAX_TRADE_AMOUNT}")
        print(f"   - Sandbox mode: {Config.BINANCE_SANDBOX}")
        print(f"   - Manual confirmation: {Config.ENABLE_MANUAL_CONFIRMATION}")
        
        # Test validation
        if Config.BINANCE_API_KEY and Config.BINANCE_API_SECRET:
            print("✅ API credentials configured")
            if Config.validate():
                print("✅ Configuration validation passed")
                return True, "Configuration is valid"
            else:
                print("⚠️  Configuration validation failed")
                return False, "Invalid configuration parameters"
        else:
            print("⚠️  API credentials not configured")
            return False, "Please set BINANCE_API_KEY and BINANCE_API_SECRET in .env"
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False, str(e)

async def test_exchange_connection():
    """Test exchange connection."""
    print("\n🔗 Testing exchange connection...")
    
    try:
        from exchanges.binance_exchange import BinanceExchange
        from config.config import Config
        
        if not Config.BINANCE_API_KEY or not Config.BINANCE_API_SECRET:
            print("⚠️  Skipping connection test - no API credentials")
            return True, "Skipped (no credentials)"
        
        exchange_config = {
            'api_key': Config.BINANCE_API_KEY,
            'api_secret': Config.BINANCE_API_SECRET,
            'sandbox': Config.BINANCE_SANDBOX,
            'bnb_fee_discount': Config.BNB_FEE_DISCOUNT
        }
        
        exchange = BinanceExchange(exchange_config)
        
        if await exchange.connect():
            print("✅ Exchange connection successful")
            
            # Test basic functionality
            pairs = await exchange.get_trading_pairs()
            print(f"✅ Retrieved {len(pairs)} trading pairs")
            
            balance = await exchange.get_account_balance()
            if balance:
                print(f"✅ Account balance retrieved ({len(balance)} currencies)")
            else:
                print("⚠️  No account balance (empty account or API restrictions)")
            
            await exchange.disconnect()
            return True, "Exchange connection successful"
        else:
            print("❌ Exchange connection failed")
            return False, "Could not connect to exchange"
            
    except Exception as e:
        print(f"❌ Exchange connection test failed: {e}")
        return False, str(e)

def test_file_structure():
    """Test that all required files exist."""
    print("\n📁 Testing file structure...")
    
    required_files = [
        'main.py',
        'config/config.py',
        'exchanges/base_exchange.py',
        'exchanges/binance_exchange.py',
        'arbitrage/triangle_detector.py',
        'arbitrage/trade_executor.py',
        'models/arbitrage_opportunity.py',
        'utils/logger.py',
        'requirements.txt',
        '.env.example'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    return len(missing_files) == 0, missing_files

async def main():
    """Run all tests."""
    print("🔺 Triangular Arbitrage Bot - Installation Test")
    print("=" * 60)
    
    all_passed = True
    
    # Test file structure
    files_ok, missing_files = test_file_structure()
    if not files_ok:
        print(f"\n❌ Missing files: {missing_files}")
        all_passed = False
    
    # Test imports
    imports_ok, failed_imports = test_imports()
    if not imports_ok:
        print(f"\n❌ Failed imports: {failed_imports}")
        print("Run: pip install -r requirements.txt")
        all_passed = False
    
    # Test configuration
    config_ok, config_msg = test_configuration()
    if not config_ok:
        print(f"\n⚠️  Configuration issue: {config_msg}")
        # Don't fail completely for config issues
    
    # Test exchange connection (only if imports and config are OK)
    if imports_ok and config_ok:
        exchange_ok, exchange_msg = await test_exchange_connection()
        if not exchange_ok:
            print(f"\n⚠️  Exchange connection issue: {exchange_msg}")
            # Don't fail completely for connection issues in test mode
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 All critical tests passed!")
        print("\nYour bot installation is ready.")
        if not config_ok:
            print("⚠️  Remember to configure your .env file before running the bot.")
        print("\nTo start the bot: python main.py")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("\nFor help:")
        print("1. Run setup.py to install dependencies")
        print("2. Check that all files are present")
        print("3. Configure .env with your API credentials")
    
    return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error during testing: {e}")
        sys.exit(1)