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
        self.running = False
        self.opportunities: List[Dict[str, Any]] = []
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
                self.logger.info("Starting bot with config: "
                                f"minProfit={config.minProfitPercentage}%, "
                                f"maxTrade={config.maxTradeAmount}, "
                                f"autoTrade={config.autoTradingMode}, "
                                f"paper={config.paperTrading}, "
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

                self.running = True
                asyncio.create_task(self._scanning_loop())

                self.stats['activeExchanges'] = len(config.selectedExchanges)
                return {"status": "success", "message": "Bot started successfully"}
            except Exception as e:
                self.logger.error(f"Error starting bot: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/bot/stop")
        async def stop_bot():
            try:
                self.running = False
                if self.exchange_manager:
                    await self.exchange_manager.disconnect_all()
                self.stats['activeExchanges'] = 0
                return {"status": "success", "message": "Bot stopped successfully"}
            except Exception as e:
                self.logger.error(f"Error stopping bot: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/opportunities")
        async def get_opportunities():
            return self.opportunities

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
                    self.opportunities = [
                        {
                            "id": f"opp_{int(time.time()*1000)}_{i}",
                            "exchange": opp.exchange,
                            "trianglePath": " → ".join(opp.triangle_path[:3]),
                            "profitPercentage": round(opp.profit_percentage, 4),
                            "profitAmount": round(opp.profit_amount, 4),
                            "volume": opp.initial_amount,
                            "status": "detected" if opp.profit_percentage > 0 else "low_profit",
                            "dataType": "REAL_MARKET_DATA",
                            "timestamp": datetime.now().isoformat()
                        }
                        for i, opp in enumerate(opportunities)
                        if abs(opp.profit_percentage) >= 0.01  # Show opportunities >= 0.01%
                    ][:200]  # Keep only latest 200 opportunities
                    
                    self.stats['opportunitiesFound'] = len(self.opportunities)
                    
                    # Broadcast opportunities update
                    await self.websocket_manager.broadcast("opportunities_update", self.opportunities)
                    
                    # Also log for debugging
                    if self.opportunities:
                        self.logger.info(f"Found {len(self.opportunities)} opportunities, broadcasting to {len(self.websocket_manager.connections)} clients")
                
                await asyncio.sleep(10)  # Scan every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {str(e)}", exc_info=True)
                await asyncio.sleep(15)  # Shorter delay on error

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")

def main():
    server = ArbitrageWebServer()
    server.run()

if __name__ == "__main__":
    main()