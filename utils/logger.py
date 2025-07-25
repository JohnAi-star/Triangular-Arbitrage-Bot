import logging
import colorlog
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

def setup_logger(name: str, log_level: str = 'INFO') -> logging.Logger:
    """Setup comprehensive logging with both file and console output."""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Console handler with colors
    console_handler = colorlog.StreamHandler()
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        f'logs/{name.lower()}.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def setup_trade_logger() -> logging.Logger:
    """Setup specialized logger for trade records."""
    os.makedirs('logs', exist_ok=True)
    
    trade_logger = logging.getLogger('trades')
    trade_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in trade_logger.handlers[:]:
        trade_logger.removeHandler(handler)
    
    # File handler for trade records
    trade_handler = RotatingFileHandler(
        'logs/trades.log',
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10
    )
    trade_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    trade_handler.setFormatter(trade_formatter)
    trade_logger.addHandler(trade_handler)
    
    return trade_logger