#!/usr/bin/env python3
"""
Test script for the real-time arbitrage detector with enforced limits
"""

import asyncio
import signal
import sys
from arbitrage.realtime_detector import RealtimeArbitrageDetector

class TestRealtimeDetector:
    def __init__(self):
        self.detector = None
        self.running = True
    
    async def run_test(self):
        """Run the real-time detector test with enforced limits"""
        print("🚀 Testing Real-Time Arbitrage Detector with ENFORCED LIMITS")
        print("=" * 60)
        print("🚫 ENFORCED LIMITS:")
        print("   • Minimum Profit: 0.5%")
        print("   • Maximum Trade: $100")
        print("   • Trades over $100 will be REJECTED")
        print("   • Profits under 0.5% will be REJECTED")
        print("=" * 60)
        
        # Initialize detector with enforced limits
        self.detector = RealtimeArbitrageDetector(
            min_profit_pct=0.5,  # Lower threshold for testing: 0.5%
            max_trade_amount=100.0  # Reasonable trade amount: $100
        )
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            # Initialize
            print("📡 Initializing detector with realistic limits...")
            if not await self.detector.initialize():
                print("❌ Failed to initialize detector")
                return False
            
            print("✅ Detector initialized successfully")
            print(f"   Trading pairs: {len(self.detector.trading_pairs)}")
            print(f"   Triangular paths: {len(self.detector.triangular_paths)}")
            print(f"   Min Profit: {self.detector.min_profit_pct}%")
            print(f"   Max Trade: ${self.detector.max_trade_amount}")
            
            # Start WebSocket stream
            print("🌐 Starting WebSocket stream...")
            print("   This will run until you press Ctrl+C")
            print("   Watch for realistic opportunities!")
            print("-" * 60)
            
            await self.detector.start_websocket_stream()
            
        except KeyboardInterrupt:
            print("\n🛑 Stopping detector...")
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        
        return True
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n📡 Received signal {signum}, shutting down...")
        self.running = False
        if self.detector:
            self.detector.running = False

async def main():
    """Main test function"""
    test = TestRealtimeDetector()
    await test.run_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test completed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)