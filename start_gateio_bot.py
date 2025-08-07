#!/usr/bin/env python3
"""
Start Gate.io Arbitrage Bot with Real Trading
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import ArbitrageBotGUI
from config.config import Config

load_dotenv()

def main():
    """Start Gate.io arbitrage bot"""
    print("""
    🔴 REAL MONEY Gate.io Triangular Arbitrage Bot
    ============================================
    🔴 REAL MONEY bot for Gate.io triangular arbitrage
    
    Features:
    - Real-time Gate.io balance detection
    - USDT-based triangular arbitrage (USDT→Currency1→Currency2→USDT)
    - Manual and automatic REAL MONEY trading
    - 🔴 REAL MONEY TRADING ONLY - NO SIMULATION
    - All trades visible in Gate.io account
    - Real profit/loss tracking
    
    Starting GUI...
    """)
    
    # Check Gate.io credentials
    api_key = os.getenv('GATEIO_API_KEY', '').strip()
    api_secret = os.getenv('GATEIO_API_SECRET', '').strip()
    
    if not api_key or not api_secret:
        print("⚠️ WARNING: No Gate.io API credentials found!")
        print("   Set GATEIO_API_KEY and GATEIO_API_SECRET in .env file")
        print("   Bot will show demo opportunities only")
    else:
        print(f"✅ Gate.io credentials found: {api_key[:8]}...{api_key[-4:]}")
        print("✅ Will connect to REAL Gate.io account")
    
    # Force real trading mode
    Config.PAPER_TRADING = False
    Config.AUTO_TRADING_MODE = False  # Start with manual mode
    
    try:
        # Create and run GUI
        app = ArbitrageBotGUI()
        print("✅ GUI initialized for Gate.io trading")
        print("✅ Paper trading DISABLED - REAL TRADING ONLY")
        print("✅ Auto-trading available in GUI")
        
        app.run()
        return 0
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())