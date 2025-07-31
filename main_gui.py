#!/usr/bin/env python3
"""
Main entry point for the GUI-based triangular arbitrage bot.
"""

import sys
import os
import asyncio
import tkinter as tk
from tkinter import messagebox

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import Config
from gui.main_window import ArbitrageBotGUI
from utils.logger import setup_logger

# Import and start web server for React frontend
try:
    from api.web_server import start_web_server_background
    WEB_SERVER_AVAILABLE = True
except ImportError:
    WEB_SERVER_AVAILABLE = False

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import ccxt
        import customtkinter
        import matplotlib
        import pandas
        import numpy
        return True
    except ImportError as e:
        messagebox.showerror(
            "Missing Dependencies",
            f"Required dependency not found: {e}\n\n"
            "Please install all dependencies:\n"
            "pip install -r requirements.txt"
        )
        return False

def check_configuration():
    """Check if configuration is valid."""
    if not Config.validate():
        messagebox.showwarning(
            "Configuration Error",
            "❌ CRITICAL: No valid exchange credentials found for LIVE TRADING!\n\n"
            "The bot requires REAL API credentials to fetch market data,\n"
            "for LIVE TRADING mode.\n\n"
            "Please configure your API credentials in the .env file:\n"
            "- BINANCE_API_KEY=your_api_key\n"
            "- BINANCE_API_SECRET=your_api_secret\n\n"
            "🔴 LIVE TRADING requires real exchange connections."
        )
        return False
    return True

def main():
    """Main entry point."""
    print("""
    🔺 🔴 LIVE TRADING Multi-Exchange Triangular Arbitrage Bot
    ==========================================
    🔴 LIVE TRADING bot for detecting and executing triangular arbitrage
    opportunities across multiple cryptocurrency exchanges.
    
    Features:
    - Real-time opportunity detection
    - Multi-exchange support (Binance, Bybit, KuCoin, etc.)
    - Manual and automatic 🔴 LIVE trading modes
    - 🔴 LIVE TRADING ONLY - NO PAPER MODE
    - Zero-fee pair prioritization
    - Comprehensive logging and statistics
    - Real-time WebSocket updates in GUI
    
    Starting GUI...
    """)
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Check configuration
    if not check_configuration():
        return 1
    
    try:
        # Create and run GUI application
        app = ArbitrageBotGUI()
        
        print("✅ GUI initialized with WebSocket manager")
        print("✅ Real-time opportunity updates enabled")
        
        app.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n{e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())