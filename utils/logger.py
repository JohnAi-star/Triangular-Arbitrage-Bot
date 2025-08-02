import logging
import colorlog
from logging.handlers import RotatingFileHandler
import os
import sys
from datetime import datetime

def setup_logger(name: str, log_level: str = 'INFO') -> logging.Logger:
    """Setup comprehensive logging with both file and console output."""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers - if logger already has handlers, return it
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Prevent propagation to root logger to avoid duplicates
    logger.propagate = False
    
    # Force UTF-8 encoding for Windows compatibility
    if sys.platform.startswith('win'):
        # Set console encoding to UTF-8 on Windows
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            # Python < 3.7 fallback
            pass
    
    # Console handler with colors
    console_handler = colorlog.StreamHandler(sys.stdout)
    if sys.platform.startswith('win'):
        # Use plain text format on Windows to avoid Unicode issues
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
    else:
        # Use Unicode format on Unix systems
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
        backupCount=5,
        encoding='utf-8'  # Force UTF-8 encoding for file logs
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
        backupCount=10,
        encoding='utf-8'  # Force UTF-8 encoding for trade logs
    )
    trade_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    trade_handler.setFormatter(trade_formatter)
    trade_logger.addHandler(trade_handler)
    
    return trade_logger