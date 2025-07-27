#!/usr/bin/env python3
"""
FastAPI web server for the triangular arbitrage bot.
Provides REST API and WebSocket endpoints for the web interface.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from config.config import Config
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from arbitrage.trade_executor import TradeExecutor
from models.arbitrage_opportunity import ArbitrageOpportunity
from utils.logger import setup_logger

# Start the web server automatically when imported
import threading
import time
# Pydantic models for API
class BotConfig(BaseModel):
    minProfitPercentage: float
    maxTradeAmount: float
    autoTradingMode: bool
    paperTrading: bool
    selectedExchanges: List[str]

class BotStats(BaseModel):
    opportunitiesFound: int
    tradesExecuted: int
    totalProfit: float
    successRate: float
    activeExchanges: int

class ArbitrageWebServer:
    """Web server for the arbitrage bot."""
    
    def __init__(self):
        self.logger = setup_logger('WebServer')
        self.app = FastAPI(title="Triangular Arbitrage Bot API")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Bot components
        self.exchange_manager = MultiExchangeManager()
        self.detector = None
        self.executor = None
        self.running = False
        
        # Statistics
        self.stats = {
            'opportunitiesFound': 0,
            'tradesExecuted': 0,
            'totalProfit': 0.0,
            'successRate': 0.0,
            'activeExchanges': 0
        }
        
        # WebSocket connections
        self.websocket_connections: List[WebSocket] = []
        
        # Current opportunities
        self.opportunities: List[Dict[str, Any]] = []
        
        self.setup_routes()
    
    def setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @self.app.post("/api/bot/start")
        async def start_bot(config: BotConfig):
            """Start the arbitrage bot."""
            try:
                self.logger.info(f"Starting bot with config: {config}")
                
                # Initialize exchanges
                success = await self.exchange_manager.initialize_exchanges(
                    config.selectedExchanges
                )
                
                if not success:
                    raise HTTPException(status_code=400, detail="Failed to connect to exchanges")
                
                # Initialize detector
                detector_config = {
                    'min_profit_percentage': config.minProfitPercentage,
                    'max_trade_amount': config.maxTradeAmount,
                    'prioritize_zero_fee': True
                }
                
                self.detector = MultiExchangeDetector(self.exchange_manager, detector_config)
                await self.detector.initialize()
                
                # Initialize executor
                executor_config = {
                    'auto_trading': config.autoTradingMode,
                    'paper_trading': config.paperTrading,
                    'enable_manual_confirmation': not config.autoTradingMode
                }
                
                self.executor = TradeExecutor(self.exchange_manager, executor_config)
                
                # Start scanning
                self.running = True
                asyncio.create_task(self._scanning_loop())
                
                self.stats['activeExchanges'] = len(config.selectedExchanges)
                
                return {"status": "success", "message": "Bot started successfully"}
                
            except Exception as e:
                self.logger.error(f"Error starting bot: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/bot/stop")
        async def stop_bot():
            """Stop the arbitrage bot."""
            try:
                self.running = False
                await self.exchange_manager.disconnect_all()
                self.stats['activeExchanges'] = 0
                
                return {"status": "success", "message": "Bot stopped successfully"}
                
            except Exception as e:
                self.logger.error(f"Error stopping bot: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/opportunities")
        async def get_opportunities():
            """Get current arbitrage opportunities."""
            return self.opportunities
        
        @self.app.post("/api/opportunities/{opportunity_id}/execute")
        async def execute_opportunity(opportunity_id: str):
            """Execute a specific arbitrage opportunity."""
            try:
                # Find the opportunity
                opportunity_data = None
                for opp in self.opportunities:
                    if opp['id'] == opportunity_id:
                        opportunity_data = opp
                        break
                
                if not opportunity_data:
                    raise HTTPException(status_code=404, detail="Opportunity not found")
                
                # Convert to ArbitrageOpportunity object (simplified)
                # In production, you'd properly reconstruct the object
                success = True  # Simulate execution
                
                if success:
                    self.stats['tradesExecuted'] += 1
                    self.stats['totalProfit'] += opportunity_data.get('profitAmount', 0)
                    
                    # Update opportunity status
                    opportunity_data['status'] = 'completed'
                    
                    # Broadcast update
                    await self._broadcast_update({
                        'type': 'opportunity_executed',
                        'data': opportunity_data
                    })
                
                return {"status": "success", "executed": success}
                
            except Exception as e:
                self.logger.error(f"Error executing opportunity: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stats")
        async def get_stats():
            """Get bot statistics."""
            return self.stats
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Keep connection alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
    
    async def _scanning_loop(self):
        """Main scanning loop for opportunities."""
        while self.running:
            try:
                if self.detector:
                    opportunities = await self.detector.scan_all_opportunities()
                    
                    # Convert opportunities to dict format
                    opportunity_dicts = []
                    for opp in opportunities:
                        opp_dict = {
                            'id': f"opp_{int(datetime.now().timestamp() * 1000)}",
                            'exchange': getattr(opp, 'exchange', 'Unknown'),
                            'trianglePath': opp.triangle_path,
                            'profitPercentage': opp.profit_percentage,
                            'profitAmount': opp.profit_amount,
                            'volume': opp.initial_amount,
                            'status': 'detected',
                            'timestamp': datetime.now().isoformat()
                        }
                        opportunity_dicts.append(opp_dict)
                    
                    # Update opportunities list
                    self.opportunities = opportunity_dicts[:50]  # Keep latest 50
                    self.stats['opportunitiesFound'] += len(opportunities)
                    
                    # Broadcast to WebSocket clients
                    if opportunity_dicts:
                        await self._broadcast_update({
                            'type': 'opportunities_update',
                            'data': opportunity_dicts
                        })
                
                await asyncio.sleep(2)  # Scan every 2 seconds
                
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {e}")
                await asyncio.sleep(5)
    
    async def _broadcast_update(self, message: Dict[str, Any]):
        """Broadcast update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = []
        
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message_str)
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            self.websocket_connections.remove(ws)
    
    def run(self, host: str = "localhost", port: int = 8000):
        """Run the web server."""
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="info")

# Global server instance
_server_instance = None
_server_thread = None

def start_web_server_background():
    """Start the web server in a background thread."""
    global _server_instance, _server_thread
    
    if _server_instance is None:
        _server_instance = ArbitrageWebServer()
        
        def run_server():
            try:
                _server_instance.run(host="0.0.0.0", port=8000)
            except Exception as e:
                print(f"Web server error: {e}")
        
        _server_thread = threading.Thread(target=run_server, daemon=True)
        _server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        print("🌐 Web server started on http://localhost:8000")
        print("🔗 Frontend can now connect to backend API")

def main():
    """Main entry point for the web server."""
    server = ArbitrageWebServer()
    server.run()

if __name__ == "__main__":
    main()