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
import uvicorn

# Logger setup
def setup_logger(name: str) -> logging.Logger:
    """Configure and return a logger instance"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

# Get git commit hash safely
def get_git_commit() -> str:
    try:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        commit = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return commit[:7]
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
        message = json.dumps({"type": event, "data": data})
        for connection in self.connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to client: {str(e)}")
                await self.disconnect(connection)

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
        self.trade_logger = get_trade_logger(self.websocket_manager)
        self.running = False
        self.auto_trading = False
        self.opportunities: List[Dict[str, Any]] = []
        self.opportunities_cache: Dict[str, Any] = {}  # Cache for opportunity lookup
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
                # Update global config with user settings
                from config.config import Config
                Config.PAPER_TRADING = config.paperTrading
                Config.AUTO_TRADING_MODE = config.autoTradingMode
                
                self.auto_trading = config.autoTradingMode
                trading_mode = "PAPER" if config.paperTrading else "LIVE"
                self.logger.info("Starting bot with config: "
                                f"minProfit={config.minProfitPercentage}%, "
                                f"maxTrade={config.maxTradeAmount}, "
                                f"autoTrade={config.autoTradingMode}, "
                                f"paper={config.paperTrading}, "
                                f"mode={trading_mode}, "
                                f"exchanges={config.selectedExchanges}")

                # Initialize exchange manager
                from exchanges.multi_exchange_manager import MultiExchangeManager
                self.exchange_manager = MultiExchangeManager()
                success = await self.exchange_manager.initialize_exchanges(config.selectedExchanges)
                if not success:
                    raise HTTPException(status_code=400, detail="Exchange initialization failed")

                # Initialize detector
                from arbitrage.multi_exchange_detector import MultiExchangeDetector
                self.detector = MultiExchangeDetector(
                    self.exchange_manager,
                    self.websocket_manager,
                    {
                        'min_profit_percentage': config.minProfitPercentage,
                        'max_trade_amount': config.maxTradeAmount
                    }
                )
                await self.detector.initialize()

                # Initialize executor
                from arbitrage.trade_executor import TradeExecutor
                self.executor = TradeExecutor(
                    self.exchange_manager,
                    {
                        'auto_trading': config.autoTradingMode,
                        'paper_trading': config.paperTrading
                    }
                )
                
                # Set WebSocket manager for trade logging
                self.executor.set_websocket_manager(self.websocket_manager)

                self.running = True
                asyncio.create_task(self._scanning_loop())

                self.stats['activeExchanges'] = len(config.selectedExchanges)
                return {
                    "status": "success", 
                    "message": f"Bot started successfully in {trading_mode} mode",
                    "trading_mode": trading_mode,
                    "paper_trading": config.paperTrading
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

        @app.post("/api/bot/toggle-auto-trading")
        async def toggle_auto_trading(request: dict):
            try:
                self.auto_trading = request.get('autoTrading', False)
                self.logger.info(f"Auto-trading {'enabled' if self.auto_trading else 'disabled'}")
                
                # Update executor if it exists
                if self.executor:
                    self.executor.config['auto_trading'] = self.auto_trading
                
                # Broadcast the change to all clients
                await self.websocket_manager.broadcast('auto_trading_changed', {
                    'autoTrading': self.auto_trading
                })
                
                return {"status": "success", "autoTrading": self.auto_trading}
            except Exception as e:
                self.logger.error(f"Error toggling auto-trading: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/opportunities")
        async def get_opportunities():
            return self.opportunities
        
        @app.post("/api/opportunities/{opp_id}/execute")
        async def execute_opportunity(opp_id: str):
            try:
                self.logger.info(f"Manual execution requested for opportunity: {opp_id}")
                
                # Look up opportunity in cache
                if opp_id not in self.opportunities_cache:
                    self.logger.error(f"Opportunity {opp_id} not found in cache")
                    raise HTTPException(status_code=404, detail="Opportunity not found or expired")
                
                opportunity_data = self.opportunities_cache[opp_id]
                
                # Convert to ArbitrageOpportunity object for execution
                from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
                
                opportunity = ArbitrageOpportunity(
                    base_currency=opportunity_data.get('base_currency', 'BTC'),
                    intermediate_currency=opportunity_data.get('intermediate_currency', 'ETH'),
                    quote_currency=opportunity_data.get('quote_currency', 'USDT'),
                    pair1=f"{opportunity_data.get('base_currency', 'BTC')}/{opportunity_data.get('intermediate_currency', 'ETH')}",
                    pair2=f"{opportunity_data.get('intermediate_currency', 'ETH')}/{opportunity_data.get('quote_currency', 'USDT')}",
                    pair3=f"{opportunity_data.get('base_currency', 'BTC')}/{opportunity_data.get('quote_currency', 'USDT')}",
                    initial_amount=opportunity_data.get('volume', 100),
                    final_amount=opportunity_data.get('volume', 100) * (1 + opportunity_data.get('profit_pct', 0) / 100),
                    estimated_fees=opportunity_data.get('volume', 100) * 0.003,  # 0.3% estimated fees
                    estimated_slippage=opportunity_data.get('volume', 100) * 0.001  # 0.1% estimated slippage
                )
                
                # Set exchange attribute
                setattr(opportunity, 'exchange', opportunity_data.get('exchange', 'binance'))
                
                # Execute the trade
                if not self.executor:
                    raise HTTPException(status_code=400, detail="Trade executor not initialized")
                
                success = await self.executor.execute_arbitrage(opportunity)
                
                # Update stats
                if success:
                    self.stats['tradesExecuted'] += 1
                    self.stats['totalProfit'] += opportunity.profit_amount
                
                # Remove from cache after execution attempt
                del self.opportunities_cache[opp_id]
                
                return {
                    "status": "success" if success else "failed",
                    "opportunity_id": opp_id,
                    "executed": success,
                    "initial_amount": opportunity.initial_amount,
                    "final_amount": opportunity.final_amount,
                    "profit_amount": opportunity.profit_amount,
                    "profit_percentage": opportunity.profit_percentage
                }
                
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Error executing opportunity {opp_id}: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/trades")
        async def get_trades():
            """Get recent detailed trade logs."""
            return self.trade_logger.get_recent_trades(50)
        
        @app.get("/api/trade-stats")
        async def get_trade_stats():
            """Get comprehensive trade statistics."""
            return self.trade_logger.get_trade_statistics()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()  # Keep connection alive
            except WebSocketDisconnect:
                await self.websocket_manager.disconnect(websocket)

    async def _scanning_loop(self):
        self.logger.info("Starting opportunity scanning loop...")
        while self.running:
            try:
                if self.detector and self.exchange_manager:
                    opportunities = await self.detector.scan_all_opportunities()
                    
                    # Format opportunities for UI
                    self.opportunities = []
                    for i, opp in enumerate(opportunities):
                        if abs(opp.profit_percentage) >= 0.01:  # Show opportunities >= 0.01%
                            opp_id = f"opp_{int(time.time()*1000)}_{i}"
                            opportunity_data = {
                                "id": opp_id,
                                "exchange": opp.exchange,
                                "trianglePath": " → ".join(opp.triangle_path[:3]),
                                "profitPercentage": round(opp.profit_percentage, 4),
                                "profitAmount": round(opp.profit_amount, 4),
                                "volume": opp.initial_amount,
                                "status": "detected" if opp.profit_percentage > 0 else "low_profit",
                                "dataType": "REAL_MARKET_DATA",
                                "timestamp": datetime.now().isoformat(),
                                "base_currency": opp.triangle_path[0] if len(opp.triangle_path) > 0 else "BTC",
                                "intermediate_currency": opp.triangle_path[1] if len(opp.triangle_path) > 1 else "ETH",
                                "quote_currency": opp.triangle_path[2] if len(opp.triangle_path) > 2 else "USDT",
                                "profit_pct": opp.profit_percentage
                            }
                            self.opportunities.append(opportunity_data)
                            # Cache the opportunity for later execution
                            self.opportunities_cache[opp_id] = opportunity_data
                    self.opportunities = self.opportunities[:200]  # Keep only latest 200 opportunities
                    
                    # Clean old opportunities from cache (keep last 500)
                    if len(self.opportunities_cache) > 500:
                        old_keys = list(self.opportunities_cache.keys())[:-500]
                        for key in old_keys:
                            del self.opportunities_cache[key]
                    
                    self.stats['opportunitiesFound'] = len(self.opportunities)
                    
                    # Broadcast opportunities update
                    await self.websocket_manager.broadcast("opportunities_update", self.opportunities)
                    
                    # Auto-execute profitable opportunities if auto-trading is enabled
                    if self.auto_trading and self.executor:
                        await self._auto_execute_opportunities(opportunities)
                    
                    # Also log for debugging
                    if self.opportunities:
                        self.logger.info(f"Found {len(self.opportunities)} opportunities, broadcasting to {len(self.websocket_manager.connections)} clients")
                
                await asyncio.sleep(10)  # Scan every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {str(e)}", exc_info=True)
                await asyncio.sleep(15)  # Shorter delay on error

    async def _auto_execute_opportunities(self, opportunities):
        """Auto-execute profitable opportunities when auto-trading is enabled."""
        try:
            profitable_opportunities = [
                opp for opp in opportunities 
                if opp.profit_percentage > 0.1  # Only execute if > 0.1% profit
            ]
            
            # Limit to top 3 opportunities to avoid overtrading
            for opportunity in profitable_opportunities[:3]:
                try:
                    self.logger.info(f"Auto-executing opportunity: {opportunity.exchange} - {opportunity.profit_percentage:.4f}%")
                    
                    # Set exchange attribute for execution
                    setattr(opportunity, 'exchange', opportunity.exchange)
                    
                    success = await self.executor.execute_arbitrage(opportunity)
                    
                    if success:
                        self.stats['tradesExecuted'] += 1
                        self.stats['totalProfit'] += opportunity.profit_amount
                        
                        # Broadcast auto-execution result
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': opportunity.profit_amount,
                            'volume': opportunity.initial_amount,
                            'status': 'completed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                        
                        self.logger.info(f"Auto-execution successful: {opportunity.profit_percentage:.4f}% profit")
                    else:
                        self.logger.warning(f"Auto-execution failed for {opportunity.exchange}")
                        
                        # Broadcast failure
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': 0,
                            'volume': opportunity.initial_amount,
                            'status': 'failed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error in auto-execution: {str(e)}")
                    
        except Exception as e:
            self.logger.error(f"Error in auto-execute opportunities: {str(e)}")
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")

def main():
    server = ArbitrageWebServer()
    server.run()

if __name__ == "__main__":
    main()