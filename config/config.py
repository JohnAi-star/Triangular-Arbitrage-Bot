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
        sandbox = os.getenv(f'{exchange_id.upper()}_SANDBOX', 'false').lower() == 'true'
        
        EXCHANGE_CREDENTIALS[exchange_id] = {
            'api_key': api_key,
            'api_secret': api_secret,
            'sandbox': sandbox,
            'enabled': bool(api_key and api_secret)
        }
    
    # Trading Parameters
    MIN_PROFIT_PERCENTAGE: float = float(os.getenv('MIN_PROFIT_PERCENTAGE', '0.1'))
    MAX_TRADE_AMOUNT: float = float(os.getenv('MAX_TRADE_AMOUNT', '100'))
    USE_FEE_TOKENS: bool = os.getenv('USE_FEE_TOKENS', 'true').lower() == 'true'
    PRIORITIZE_ZERO_FEE: bool = os.getenv('PRIORITIZE_ZERO_FEE', 'true').lower() == 'true'
    
    # Bot Configuration
    ENABLE_MANUAL_CONFIRMATION: bool = os.getenv('ENABLE_MANUAL_CONFIRMATION', 'true').lower() == 'true'
    AUTO_TRADING_MODE: bool = os.getenv('AUTO_TRADING_MODE', 'false').lower() == 'true'
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    PAPER_TRADING: bool = os.getenv('PAPER_TRADING', 'false').lower() == 'true'
    BACKTESTING_MODE: bool = os.getenv('BACKTESTING_MODE', 'false').lower() == 'true'
    
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
        # ALWAYS require at least one exchange with valid credentials
        has_valid_exchange = any(
            cred['enabled'] for cred in cls.EXCHANGE_CREDENTIALS.values()
        )
        
        # Even in paper trading, we need credentials to fetch real market data
        if not has_valid_exchange:
            print("❌ ERROR: No valid exchange credentials found!")
            print("   The bot requires real API credentials to fetch market data.")
            print("   Even in paper trading mode, real market data is needed.")
            print("   Please configure your API credentials in the .env file.")
            return False
            
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
            'enabled_exchanges': [
                ex_id for ex_id, cred in cls.EXCHANGE_CREDENTIALS.items() 
                if cred['enabled']
            ]
        }