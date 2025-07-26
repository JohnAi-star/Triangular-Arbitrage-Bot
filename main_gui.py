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
    if not Config.validate() and not Config.PAPER_TRADING:
        messagebox.showwarning(
            "Configuration Warning",
            "No exchange credentials configured.\n\n"
            "The bot will run in paper trading mode only.\n"
            "To enable live trading, configure your API credentials in the .env file."
        )
    return True

def main():
    """Main entry point."""
    print("""
    🔺 Multi-Exchange Triangular Arbitrage Bot
    ==========================================
    GUI-driven bot for detecting and executing triangular arbitrage
    opportunities across multiple cryptocurrency exchanges.
    
    Features:
    - Real-time opportunity detection
    - Multi-exchange support (Binance, Bybit, KuCoin, etc.)
    - Manual and automatic trading modes
    - Paper trading and backtesting
    - Zero-fee pair prioritization
    - Comprehensive logging and statistics
    
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
        app.run()
        return 0
        
        if not self.paper_trading_var.get():
            # Switching to live trading
            result = messagebox.askyesno(
                "⚠️ LIVE TRADING WARNING",
                "You are about to enable LIVE TRADING mode!\n\n"
                "This will execute REAL trades with REAL money on the exchanges.\n"
                "Make sure you:\n"
                "• Have tested thoroughly in paper trading mode\n"
                "• Understand the risks involved\n"
                "• Have set appropriate trade limits\n\n"
                "Are you sure you want to enable live trading?"
            )
            if not result:
                self.paper_trading_var.set(True)
                return
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n{e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())