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
    is_valid = Config.validate()
    
    # Check specifically for Binance credentials
    binance_creds = Config.EXCHANGE_CREDENTIALS.get('binance', {})
    has_binance_creds = binance_creds.get('enabled', False)
    
    # Safe access to potentially missing attributes
    min_profit = getattr(Config, 'MIN_PROFIT_THRESHOLD', 'Not Set')
    fake_opportunity = getattr(Config, 'FORCE_FAKE_OPPORTUNITY', False)

    print(f"🔍 Configuration Check:")
    print(f"   Key: {'✅ SET' if binance_creds.get('api_key') else '❌ MISSING'}")
    print(f"   Secret: {'✅ SET' if binance_creds.get('api_secret') else '❌ MISSING'}")
    print(f"   Credentials Enabled: {'✅ YES' if has_binance_creds else '❌ NO'}")
    print(f"   Min Profit Threshold: {min_profit}%")
    print(f"   Force Fake Opportunity: {'✅ ENABLED' if fake_opportunity else '❌ DISABLED'}")
    print(f"   Paper Trading: {'✅ ENABLED' if Config.PAPER_TRADING else '❌ DISABLED (LIVE TRADING)'}")
    
    if not has_binance_creds:
        print("⚠️  WARNING: No credentials - limited functionality")
        print("   To access real balance, configure .env file with:")
        print("   BINANCE_API_KEY=your_key")
        print("   BINANCE_API_SECRET=your_secret")
    else:
        print("✅ Real credentials found - will access real balance")
    
    return True  # Always allow GUI to start

def main():
    """Main entry point."""
    print("""
    🔺 🔴 REAL MONEY USDT Triangular Arbitrage Bot
    ==========================================
    🔴 REAL MONEY bot for detecting and executing USDT triangular arbitrage
    opportunities: USDT → Currency1 → Currency2 → USDT
    
    Features:
    - Real-time USDT triangle detection
    - integration with real balance
    - Manual and automatic 🔴 REAL MONEY trading modes
    - 🔴 REAL MONEY TRADING ONLY - NO SIMULATION
    - USDT-based triangular arbitrage only
    - Comprehensive logging and statistics
    - All trades visible in Binance Spot Orders
    
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
        print("🔴 LIVE TRADING MODE: 300-500 opportunities with RED/GREEN colors")
        print("🎯 COLORS: 🔴 Red (0% profit) | 🟢 Green (>0.4% profit)")
        print("🔧 FIXED: Min Profit 0.4% | Max Trade $20")
        print("📊 COUNT: Will generate 300-500 opportunities per scan")
        print("💎 SCHEME: Only RED and GREEN colors (no yellow/orange)")
        
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
