#!/usr/bin/env python3
"""
FastAPI web server for triangular arbitrage bot
"""

import subprocess
import os
import asyncio
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils.trade_logger import get_trade_logger
from arbitrage.realtime_detector import RealtimeArbitrageDetector
import uvicorn
from dotenv import load_dotenv
load_dotenv()

# Logger setup
def setup_logger(name: str) -> logging.Logger:
    """Configure and return a logger instance"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    if not logger.hasHandlers():
        logger.addHandler(ch)

    return logger

# Get git commit hash safely
def get_git_commit() -> str:
    try:
        if os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".git")):
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            commit = subprocess.check_output(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return commit[:7]
        return "unknown"
    except Exception:
        return "unknown"

GIT_COMMIT = get_git_commit()
print(f"Starting Web Server (Commit: {GIT_COMMIT})")

# Application setup
app = FastAPI(title="Triangular Arbitrage Bot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WebSocketManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.logger = setup_logger('WebSocketManager')

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        self.logger.info(f"New client connected. Total: {len(self.connections)}")

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
            self.logger.info(f"Client disconnected. Total: {len(self.connections)}")

    async def broadcast(self, event: str, data: Any):
        """Broadcast message to all connected WebSocket clients"""
        message = json.dumps({"type": event, "data": data})
        disconnected = []
        for connection in self.connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to client: {str(e)}")
                disconnected.append(connection)
        
        for conn in disconnected:
            await self.disconnect(conn)

class BotConfig(BaseModel):
    minProfitPercentage: float
    maxTradeAmount: float
    autoTradingMode: bool
    paperTrading: bool
    selectedExchanges: List[str]

class ArbitrageWebServer:
    def __init__(self):
        self.logger = setup_logger('WebServer')
        self.websocket_manager = WebSocketManager()
        self.exchange_manager = None
        self.detector = None
        self.executor = None
        self.realtime_detector = None
        self.trade_logger = get_trade_logger(self.websocket_manager)
        self.running = False
        self.auto_trading = False
        self.opportunities: List[Dict[str, Any]] = []
        self.opportunities_cache: Dict[str, Any] = {}
        self.stats = {
            'opportunitiesFound': 0,
            'tradesExecuted': 0,
            'totalProfit': 0.0,
            'activeExchanges': 0
        }

        self._setup_routes()

    def _setup_routes(self):
        @app.get("/api/health")
        async def health_check():
            return {
                "status": "healthy",
                "commit": GIT_COMMIT,
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats
            }

        @app.post("/api/bot/start")
        async def start_bot(config: BotConfig):
            try:
                from config.config import Config
                Config.PAPER_TRADING = False
                Config.AUTO_TRADING_MODE = config.autoTradingMode
                
                # ENFORCE STRICT LIMITS
                enforced_min_profit = max(0.8, config.minProfitPercentage)  # Gate.io minimum 0.8% for safety
                enforced_max_trade = min(20.0, max(5.0, config.maxTradeAmount))  # Gate.io: min $5, max $20
                
                Config.MIN_PROFIT_PERCENTAGE = enforced_min_profit
                Config.MAX_TRADE_AMOUNT = enforced_max_trade

                self.auto_trading = config.autoTradingMode
                trading_mode = "🔴 LIVE GATE.IO"
                
                self.logger.info(f"🚀 Starting Gate.io bot with ENFORCED config:")
                self.logger.info(f"   Requested: minProfit={config.minProfitPercentage}%, maxTrade=${config.maxTradeAmount}")
                self.logger.info(f"   ENFORCED: minProfit={enforced_min_profit}%, maxTrade=${enforced_max_trade}")
                self.logger.info(f"   Gate.io Limits: min $5 order, max $20 trade (reduced for safety)")
                self.logger.info(f"   Settings: "
                                 f"autoTrade={config.autoTradingMode}, "
                                 f"liveTrading=TRUE, "
                                 f"mode={trading_mode}, "
                                 f"exchanges={config.selectedExchanges}")

                from exchanges.multi_exchange_manager import MultiExchangeManager
                self.exchange_manager = MultiExchangeManager()
                success = await self.exchange_manager.initialize_exchanges(config.selectedExchanges)
                if not success:
                    self.logger.warning("Exchange initialization had issues, but continuing...")
                    # Don't fail completely, allow bot to start for debugging

                from arbitrage.multi_exchange_detector import MultiExchangeDetector
                self.detector = MultiExchangeDetector(
                    self.exchange_manager,
                    self.websocket_manager,
                    {
                        'min_profit_percentage': enforced_min_profit,
                        'max_trade_amount': enforced_max_trade
                    }
                )
                
                # Initialize real-time detector for WebSocket-based detection
                self.realtime_detector = RealtimeArbitrageDetector(
                    min_profit_pct=0.01,  # Lower threshold to show more opportunities
                    max_trade_amount=100.0  # Fixed $100 maximum
                )
                
                # Start real-time WebSocket stream
                if await self.realtime_detector.initialize():
                    asyncio.create_task(self.realtime_detector.start_websocket_stream())
                    self.logger.info("✅ Real-time WebSocket detector started")
                
                try:
                    await self.detector.initialize()
                    self.logger.info("✅ Detector initialized successfully")
                except Exception as e:
                    self.logger.error(f"Detector initialization error: {e}")
                    # Continue anyway for debugging

                from arbitrage.trade_executor import TradeExecutor
                self.executor = TradeExecutor(
                    self.exchange_manager,
                    {
                        'auto_trading': config.autoTradingMode,
                        'paper_trading': False,
                        'enable_manual_confirmation': False
                    }
                )
                self.executor.set_websocket_manager(self.websocket_manager)

                self.running = True
                # Force scan immediately to show opportunities
                asyncio.create_task(self._immediate_scan())
                asyncio.create_task(self._continuous_scanning_loop())
                self.stats['activeExchanges'] = len(config.selectedExchanges)

                return {
                    "status": "success",
                    "message": "🚀 🔴 LIVE GATE.IO TRADING Bot started successfully",
                    'min_profit_percentage': enforced_min_profit,
                    'max_trade_amount': enforced_max_trade,
                    'exchange': 'gate.io',
                    'minimum_order': 5.0,
                    'auto_trading': config.autoTradingMode
                }
            except Exception as e:
                self.logger.error(f"Error starting bot: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/bot/stop")
        async def stop_bot():
            try:
                self.running = False
                self.auto_trading = False
                if self.exchange_manager:
                    await self.exchange_manager.disconnect_all()
                self.stats['activeExchanges'] = 0
                return {"status": "success", "message": "Bot stopped successfully"}
            except Exception as e:
                self.logger.error(f"Error stopping bot: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        async def _immediate_scan(self):
            """Perform immediate scan on startup to show opportunities quickly"""
            try:
                await asyncio.sleep(3)  # Wait for initialization
                self.logger.info("🚀 Performing immediate scan for ALL opportunities...")
                if self.detector and self.exchange_manager:
                    opportunities = await self.detector.scan_all_opportunities()
                    self.logger.info(f"✅ Immediate scan found {len(opportunities)} ALL opportunities")
            except Exception as e:
                self.logger.error(f"Error in immediate scan: {e}")

        @app.get("/api/opportunities")
        async def get_opportunities():
            return self.opportunities

        @app.get("/api/trades")
        async def get_trades():
            return self.trade_logger.get_recent_trades(50)

        @app.get("/api/trade-stats")
        async def get_trade_stats():
            return self.trade_logger.get_trade_statistics()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                await self.websocket_manager.disconnect(websocket)

    async def _immediate_scan(self):
        """Perform immediate scan on startup to show opportunities quickly"""
        try:
            await asyncio.sleep(3)  # Wait for initialization
            self.logger.info("🚀 Performing immediate scan for ALL opportunities...")
            if self.detector and self.exchange_manager:
                opportunities = await self.detector.scan_all_opportunities()
                self.logger.info(f"✅ Immediate scan found {len(opportunities)} ALL opportunities")
        except Exception as e:
            self.logger.error(f"Error in immediate scan: {e}")

    async def _continuous_scanning_loop(self):
        self.logger.info("🚀 Starting continuous scanning for ALL opportunities...")
        while self.running:
            try:
                if self.detector and self.exchange_manager:
                    scan_start = time.time()
                    opportunities = await self.detector.scan_all_opportunities()
                    scan_duration = (time.time() - scan_start) * 1000

                    # Convert ALL opportunities to UI format
                    ui_opportunities = []
                    for i, opp in enumerate(opportunities):
                        opp_id = f"real_opp_{int(time.time()*1000)}_{i}"
                        ui_opp = {
                            "id": opp_id,
                            "exchange": opp.exchange,
                            "trianglePath": " → ".join(opp.triangle_path[:3]),
                            "profitPercentage": round(opp.profit_percentage, 4),
                            "profitAmount": round(opp.profit_amount, 4),
                            "volume": round(opp.initial_amount, 2),
                            "status": "detected",
                            "dataType": "ALL_OPPORTUNITIES",
                            "timestamp": datetime.now().isoformat(),
                            "tradeable": getattr(opp, 'is_tradeable', False),
                            "balanceAvailable": getattr(opp, 'balance_available', 0.0),
                            "balanceRequired": getattr(opp, 'required_balance', 0.0),
                            "real_market_data": True,
                            "manual_execution": True
                        }
                        ui_opportunities.append(ui_opp)
                        self.opportunities_cache[opp_id] = {
                            'opportunity': opp,
                            'ui_data': ui_opp
                        }

                    self.opportunities = ui_opportunities[:100]  # Show up to 100 opportunities

                    if len(self.opportunities_cache) > 500:
                        old_keys = list(self.opportunities_cache.keys())[:-500]
                        for key in old_keys:
                            del self.opportunities_cache[key]

                    total_count = len(self.opportunities)
                    
                    self.stats['opportunitiesFound'] = total_count
                    await self.websocket_manager.broadcast("opportunities_update", self.opportunities)

                    if self.opportunities:
                        self.logger.info(f"💎 Scan complete ({scan_duration:.0f}ms): {total_count} ALL opportunities found")
                        
                        # Show top 5 opportunities
                        for i, opp in enumerate(self.opportunities[:3]):
                            self.logger.info(f"   {i+1}. {opp['exchange']}: {opp['trianglePath']} = {opp['profitPercentage']:.4f}% | Available for execution")
                    else:
                        self.logger.info(f"💎 Scan complete ({scan_duration:.0f}ms): No opportunities found in current market")

                    if self.auto_trading and self.executor:
                        # Auto-execute profitable opportunities
                        profitable_opportunities = [opp for opp in opportunities if opp.profit_percentage >= 0.1]
                        if profitable_opportunities:
                            await self._auto_execute_opportunities(profitable_opportunities)
                        else:
                            self.logger.info("🤖 Auto-trading enabled but no profitable opportunities found")
                
                await asyncio.sleep(5)  # Scan every 5 seconds
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {str(e)}", exc_info=True)
                await asyncio.sleep(10)
    
    async def _broadcast_all_opportunities_to_ui(self, opportunities):
        """Broadcast ALL opportunities to UI regardless of balance or tradeability"""
        try:
            # Convert opportunities to UI format
            ui_opportunities = []
            for i, opp in enumerate(opportunities):
                opp_id = f"ui_display_{int(time.time()*1000)}_{i}"
                ui_opp = {
                    "id": opp_id,
                    "exchange": opp.exchange,
                    "trianglePath": " → ".join(opp.triangle_path[:3]),
                    "profitPercentage": round(opp.profit_percentage, 4),
                    "profitAmount": round(opp.profit_amount, 4),
                    "volume": round(opp.initial_amount, 2),
                    "status": "detected",
                    "dataType": "UI_DISPLAY",
                    "timestamp": datetime.now().isoformat(),
                    "tradeable": getattr(opp, 'is_tradeable', False),
                    "balanceAvailable": getattr(opp, 'balance_available', 0.0),
                    "balanceRequired": getattr(opp, 'required_balance', 0.0),
                    "ui_display_only": True  # Mark as UI display opportunity
                }
                ui_opportunities.append(ui_opp)
            
            # Always broadcast to UI
            await self.websocket_manager.broadcast("opportunities_update", ui_opportunities)
            self.logger.info(f"📺 Broadcasted {len(ui_opportunities)} opportunities to UI for display")
            
        except Exception as e:
            self.logger.error(f"Error broadcasting opportunities to UI: {e}")
    
    async def _realtime_opportunity_integration(self):
        """Integrate real-time detector opportunities with main system"""
        self.logger.info("🌐 Starting real-time opportunity integration...")
        
        while self.running:
            try:
                if self.realtime_detector and self.realtime_detector.running:
                    # Check if detector has current_opportunities attribute
                    if hasattr(self.realtime_detector, 'current_opportunities'):
                        realtime_opps = getattr(self.realtime_detector, 'current_opportunities', [])
                        
                        if realtime_opps:
                            # Convert to our format and add to main opportunities
                            formatted_opps = []
                            for i, opp in enumerate(realtime_opps[-5:]):  # Last 5 opportunities
                                opp_id = f"realtime_{int(time.time()*1000)}_{i}"
                                formatted_opp = {
                                    'id': opp_id,
                                    'exchange': 'binance',
                                    'trianglePath': " → ".join(opp.path[:3]),
                                    'profitPercentage': round(opp.profit_percentage, 6),
                                    'profitAmount': round(opp.profit_amount, 6),
                                    'volume': opp.initial_amount,
                                    'status': 'detected',
                                    'dataType': 'REALTIME_WEBSOCKET',
                                    'timestamp': opp.timestamp.isoformat()
                                }
                                formatted_opps.append(formatted_opp)
                                
                                # Add to cache for execution
                                self.opportunities_cache[opp_id] = {
                                    'id': opp_id,
                                    'exchange': 'binance',
                                    'triangle_path': opp.path[:3],
                                    'profit_percentage': opp.profit_percentage,
                                    'profit_amount': opp.profit_amount,
                                    'initial_amount': opp.initial_amount,
                                    'steps': opp.steps,
                                    'timestamp': opp.timestamp.isoformat()
                                }
                            
                            # Broadcast to UI
                            if formatted_opps:
                                await self.websocket_manager.broadcast('opportunities_update', formatted_opps)
                                self.logger.info(f"📡 Integrated {len(formatted_opps)} real-time opportunities")
                
                await asyncio.sleep(3)  # Check every 3 seconds
                
            except Exception as e:
                self.logger.error(f"Error in real-time integration: {str(e)}")
                await asyncio.sleep(10)

    async def _auto_execute_opportunities(self, opportunities):
        try:
            # Filter for Gate.io USDT triangles only
            usdt_opportunities = [
                opp for opp in opportunities
                if (opp.profit_percentage >= 0.5 and  # Use 0.5% minimum for trading
                    opp.initial_amount >= 5.0 and     # Minimum $5
                    opp.initial_amount <= 20.0 and    # Maximum $20 (reduced for safety)
                    hasattr(opp, 'triangle_path') and
                    len(opp.triangle_path) >= 3 and
                    opp.triangle_path[0] == 'USDT')  # Only USDT triangles
            ]

            if not usdt_opportunities:
                self.logger.debug(f"🚫 AUTO-TRADE: No valid USDT triangles (need ≥0.5% profit, $5-$20 amount, start with USDT)")
                return

            # Execute top 2 most profitable USDT triangles
            sorted_opportunities = sorted(usdt_opportunities, key=lambda x: x.profit_percentage, reverse=True)
            for i, opportunity in enumerate(sorted_opportunities[:2]):
                try:
                    # ENFORCE Gate.io LIMITS  
                    trade_amount = max(5.0, min(opportunity.initial_amount, 20.0))
                    expected_profit_usd = trade_amount * (opportunity.profit_percentage / 100)
                    
                    self.logger.info(f"🤖 AUTO-EXECUTING TRADE #{i+1}:")
                    self.logger.info(f"   Exchange: {opportunity.exchange}")
                    self.logger.info(f"   Triangle: USDT → {opportunity.triangle_path[1]} → {opportunity.triangle_path[2]} → USDT")
                    self.logger.info(f"   Profit: {opportunity.profit_percentage:.4f}%")
                    self.logger.info(f"   Amount: ${trade_amount}")
                    self.logger.info(f"   Expected Profit: ${expected_profit_usd:.2f}")
                    
                    # Create executable opportunity with proper format
                    executable_opp = self._create_executable_opportunity(opportunity, trade_amount)
                    success = await self.executor.execute_arbitrage(executable_opp)

                    if success:
                        self.stats['tradesExecuted'] += 1
                        self.stats['totalProfit'] += expected_profit_usd
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'trianglePath': f"USDT → {opportunity.triangle_path[1]} → {opportunity.triangle_path[2]} → USDT",
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': expected_profit_usd,
                            'volume': trade_amount,
                            'status': 'completed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                        self.logger.info(f"✅ AUTO-TRADE SUCCESS: USDT triangle {opportunity.profit_percentage:.4f}% profit, ${expected_profit_usd:.2f} earned!")
                    else:
                        self.logger.warning(f"❌ AUTO-TRADE FAILED for USDT triangle on {opportunity.exchange}")
                        
                        # Log failed auto-trade
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_fail_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'trianglePath': f"USDT → {opportunity.triangle_path[1]} → {opportunity.triangle_path[2]} → USDT",
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': 0,
                            'volume': trade_amount,
                            'status': 'failed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                        
                    # Wait between trades
                    await asyncio.sleep(3)
                        
                except Exception as e:
                    self.logger.error(f"❌ Error in auto-execution #{i+1}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in auto-execute opportunities: {str(e)}")

    def _create_executable_opportunity(self, opportunity, trade_amount):
        """Create executable opportunity from ArbitrageResult"""
        from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep, OpportunityStatus
        
        # Extract triangle path
        triangle_path = opportunity.triangle_path
        if len(triangle_path) < 3:
            raise ValueError("Invalid triangle path")
        
        base_currency = triangle_path[0]  # USDT
        intermediate_currency = triangle_path[1]  # e.g., XRD
        quote_currency = triangle_path[2]  # e.g., ETH
        
        # Create trade steps for USDT triangle: USDT → intermediate → quote → USDT
        steps = [
            TradeStep(f"{intermediate_currency}/USDT", 'buy', trade_amount, 1.0, trade_amount),  # Buy intermediate with USDT
            TradeStep(f"{intermediate_currency}/{quote_currency}", 'sell', 1.0, 1.0, 1.0),      # Sell intermediate for quote
            TradeStep(f"{quote_currency}/USDT", 'sell', 1.0, 1.0, trade_amount * (1 + opportunity.profit_percentage/100))  # Sell quote for USDT
        ]
        
        executable_opportunity = ArbitrageOpportunity(
            base_currency=base_currency,
            intermediate_currency=intermediate_currency,
            quote_currency=quote_currency,
            pair1=f"{intermediate_currency}/USDT",
            pair2=f"{intermediate_currency}/{quote_currency}",
            pair3=f"{quote_currency}/USDT",
            steps=steps,
            initial_amount=trade_amount,
            final_amount=trade_amount * (1 + opportunity.profit_percentage/100),
            estimated_fees=trade_amount * 0.006,  # 0.6% fees for Gate.io
            estimated_slippage=trade_amount * 0.001
        )
        
        # Set additional attributes
        executable_opportunity.exchange = opportunity.exchange
        executable_opportunity.profit_percentage = opportunity.profit_percentage
        executable_opportunity.profit_amount = opportunity.profit_amount
        executable_opportunity.status = OpportunityStatus.DETECTED
        
        return executable_opportunity

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")

def main():
    server = ArbitrageWebServer()
    server.run()

if __name__ == "__main__":
    main()