import os
from typing import Dict, Any
from dotenv import load_dotenv
from config.exchanges_config import SUPPORTED_EXCHANGES

load_dotenv()

class Config:
    """Configuration management for the arbitrage bot."""
    
    # Multi-Exchange Configuration
    EXCHANGE_CREDENTIALS = {}
    
    # Load credentials for all supported exchanges
    for exchange_id in SUPPORTED_EXCHANGES.keys():
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
    
    # Trading Parameters
    MIN_PROFIT_PERCENTAGE: float = float(os.getenv('MIN_PROFIT_PERCENTAGE', '0.08'))  # 0.08% minimum for consistent profit
    MAX_TRADE_AMOUNT: float = float(os.getenv('MAX_TRADE_AMOUNT', '25'))  # $25 per trade for better profit margins
    USE_FEE_TOKENS: bool = os.getenv('USE_FEE_TOKENS', 'true').lower() == 'true'
    PRIORITIZE_ZERO_FEE: bool = os.getenv('PRIORITIZE_ZERO_FEE', 'true').lower() == 'true'
    
    # Development flags
    FORCE_FAKE_OPPORTUNITY: bool = False  # Disable fake opportunities for live trading
    MIN_PROFIT_THRESHOLD: float = float(os.getenv('MIN_PROFIT_THRESHOLD', '0.08'))  # 0.08% minimum threshold
    
    # Bot Configuration
    ENABLE_MANUAL_CONFIRMATION: bool = False  # No manual confirmation for auto-trading
    AUTO_TRADING_MODE: bool = True  # Enable auto-trading by default
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    PAPER_TRADING: bool = False  # ALWAYS LIVE TRADING - NO PAPER MODE
    BACKTESTING_MODE: bool = os.getenv('BACKTESTING_MODE', 'false').lower() == 'true'
    
    @classmethod
    def update_auto_trading(cls, enabled: bool) -> None:
        """Update auto-trading setting and persist to environment."""
        cls.AUTO_TRADING_MODE = enabled
        # In a production environment, you might want to update the .env file
        # For now, we'll just update the runtime value
        
    # WebSocket Configuration
    WEBSOCKET_RECONNECT_ATTEMPTS: int = 5
    WEBSOCKET_RECONNECT_DELAY: int = 5
    
    # Slippage and Risk Management
    MAX_SLIPPAGE_PERCENTAGE: float = 0.05  # 0.05%
    ORDER_TIMEOUT_SECONDS: int = 30
    MAX_POSITION_SIZE_USD: float = float(os.getenv('MAX_POSITION_SIZE_USD', '1000'))
    
    # GUI Configuration
    GUI_UPDATE_INTERVAL: int = 1000  # milliseconds
    MAX_OPPORTUNITIES_DISPLAY: int = 50
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration parameters."""
        # For GUI mode, we need real credentials to access balance
        has_valid_exchange = any(
            cred['enabled'] for cred in cls.EXCHANGE_CREDENTIALS.values()
        )
        
        if not has_valid_exchange:
            # For GUI, we can still run without credentials but warn user
            print("⚠️  WARNING: No valid exchange credentials found!")
            print("   Limited functionality - cannot access real account balance.")
            print("   Configure API credentials in .env for full functionality.")
            return True  # Allow GUI to start
            
        if cls.MIN_PROFIT_PERCENTAGE <= 0:
            print("❌ ERROR: MIN_PROFIT_PERCENTAGE must be greater than 0")
            return False
            
        if cls.MAX_TRADE_AMOUNT <= 0:
            print("❌ ERROR: MAX_TRADE_AMOUNT must be greater than 0")
            return False
            
        return True
    
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
            'enabled_exchanges': [
                ex_id for ex_id, cred in cls.EXCHANGE_CREDENTIALS.items() 
                if cred['enabled']
            ]
        }