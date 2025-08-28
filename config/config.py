import os
from typing import Dict, Any
from dotenv import load_dotenv
from config.exchanges_config import SUPPORTED_EXCHANGES

load_dotenv()

class Config:
    """Configuration management for the arbitrage bot."""

    # Multi-Exchange Configuration
    EXCHANGE_CREDENTIALS = {}

    for exchange_id in SUPPORTED_EXCHANGES.keys():
        # Handle Gate.io special case
        if exchange_id == 'gate':
            api_key = os.getenv('GATE_API_KEY', '') or os.getenv('GATE_API_KEY', '')
            api_secret = os.getenv('GATE_API_SECRET', '') or os.getenv('GATE_API_SECRET', '')
        else:
            api_key = os.getenv(f'{exchange_id.upper()}_API_KEY', '')
            api_secret = os.getenv(f'{exchange_id.upper()}_API_SECRET', '')
        
        passphrase = os.getenv(f'{exchange_id.upper()}_PASSPHRASE', '')  # For KuCoin
        sandbox = os.getenv(f'{exchange_id.upper()}_SANDBOX', 'false').lower() == 'true'

        EXCHANGE_CREDENTIALS[exchange_id] = {
            'api_key': api_key,
            'api_secret': api_secret,
            'passphrase': passphrase,
            'sandbox': sandbox,
            'enabled': bool(api_key and api_secret)
        }

    # Core Trading Parameters
    MIN_PROFIT_PERCENTAGE: float = 0.3    # ⚡ LOWERED to 0.3% for faster execution
    MIN_PROFIT_THRESHOLD: float = 0.3      # ⚡ 0.3% threshold allows more opportunities
    MAX_TRADE_AMOUNT: float = float(os.getenv('MAX_TRADE_AMOUNT', '20'))               # $20 USDT per trade (optimized for multi-exchange)
    MAX_POSITION_SIZE_USD: float = float(os.getenv('MAX_POSITION_SIZE_USD', '1000'))
    # Triangle generation limits
    REQUIRE_USDT_ANCHOR: bool = True
    MAX_TRIANGLES: int = int(os.getenv('MAX_TRIANGLES', '300'))  # Reduced for better performance
    MIN_VOLUME_USDT: float = float(os.getenv('MIN_VOLUME_USDT', '0'))  # optional filter if volumes available

    # Fee & Trading Mode
    USE_FEE_TOKENS: bool = os.getenv('USE_FEE_TOKENS', 'true').lower() == 'true'
    PRIORITIZE_ZERO_FEE: bool = os.getenv('PRIORITIZE_ZERO_FEE', 'true').lower() == 'true'
    SHOW_ALL_OPPORTUNITIES: bool = True  # Show all USDT-based opportunities

    # Runtime Feature Flags (defaulted to avoid crash)
    AUTO_TRADING_MODE: bool = os.getenv('AUTO_TRADING_MODE', 'false').lower() == 'true'
    ENABLE_MANUAL_CONFIRMATION: bool = os.getenv('ENABLE_MANUAL_CONFIRMATION', 'false').lower() == 'true'
    PAPER_TRADING: bool = False  # 🔴 ALWAYS REAL TRADING - NO PAPER TRADING
    LIVE_TRADING: bool = True    # 🔴 ENFORCE LIVE TRADING WITH REAL MONEY
    DRY_RUN: bool = False        # 🔴 NO DRY RUN - REAL ORDERS ONLY
    BACKTESTING_MODE: bool = os.getenv('BACKTESTING_MODE', 'false').lower() == 'false'
    
    # Scanning Configuration - Show ALL opportunities
    SCAN_ALL_OPPORTUNITIES: bool = True   # Scan all market opportunities
    IGNORE_BALANCE_CHECK: bool = True     # Don't check balance when scanning
    MANUAL_EXECUTION_MODE: bool = True    # Allow manual execution of any opportunity

    # Slippage and Order Risk
    MAX_SLIPPAGE_PERCENTAGE: float = 0.05
    ORDER_TIMEOUT_SECONDS: int = 30

    # GUI Settings
    GUI_UPDATE_INTERVAL: int = 1000  # ms
    MAX_OPPORTUNITIES_DISPLAY: int = 50

    # WebSocket
    WEBSOCKET_RECONNECT_ATTEMPTS: int = 5
    WEBSOCKET_RECONNECT_DELAY: int = 5

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration parameters."""
        has_valid_exchange = any(
            cred['enabled'] for cred in cls.EXCHANGE_CREDENTIALS.values()
        )

        if not has_valid_exchange:
            print("⚠️  WARNING: No valid exchange credentials found!")
            print("   Limited functionality - cannot access real account balance.")
            print("   Configure API credentials in .env for full functionality.")
            return True

        if cls.MIN_PROFIT_PERCENTAGE <= 0:
            print("❌ ERROR: MIN_PROFIT_PERCENTAGE must be greater than 0")
            return False

        if cls.MAX_TRADE_AMOUNT <= 0:
            print("❌ ERROR: MAX_TRADE_AMOUNT must be greater than 0")
            return False

        # Log the actual thresholds being used
        print(f"✅ Profit threshold: {cls.MIN_PROFIT_PERCENTAGE}%")
        print(f"✅ Max trade amount: ${cls.MAX_TRADE_AMOUNT}")

        return True

    @classmethod
    def update_auto_trading(cls, enabled: bool) -> None:
        """Update auto-trading setting and persist to environment (runtime only)."""
        cls.AUTO_TRADING_MODE = enabled

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'min_profit_percentage': cls.MIN_PROFIT_PERCENTAGE,
            'max_trade_amount': cls.MAX_TRADE_AMOUNT,
            'use_fee_tokens': cls.USE_FEE_TOKENS,
            'prioritize_zero_fee': cls.PRIORITIZE_ZERO_FEE,
            'manual_confirmation': cls.ENABLE_MANUAL_CONFIRMATION,
            'auto_trading_mode': cls.AUTO_TRADING_MODE,
            'paper_trading': cls.PAPER_TRADING,
            'backtesting_mode': cls.BACKTESTING_MODE,
            'live_trading': not cls.PAPER_TRADING,
            'require_usdt_anchor': cls.REQUIRE_USDT_ANCHOR,
            'max_triangles': cls.MAX_TRIANGLES,
            'min_volume_usdt': cls.MIN_VOLUME_USDT,
            'enabled_exchanges': [
                ex_id for ex_id, cred in cls.EXCHANGE_CREDENTIALS.items()
                if cred['enabled']
            ]
        }
