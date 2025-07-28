#!/usr/bin/env python3
"""
FastAPI web server for the triangular arbitrage bot.
Provides REST API and WebSocket endpoints for the web interface.
"""

# --- Prevent fatal 'HEAD' Git errors ---
import subprocess, os
GIT_COMMIT = "unknown"
try:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    commit = subprocess.check_output(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        stderr=subprocess.DEVNULL
    ).decode().strip()
    GIT_COMMIT = commit[:7]
except Exception:
    GIT_COMMIT = "unknown"
print(f"Starting Web Server (Commit: {GIT_COMMIT})")
# -----------------------------------------------

import asyncio
import json
import threading
import time
from typing import Dict, List, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from arbitrage.trade_executor import TradeExecutor
from utils.logger import setup_logger


# ------------------ WebSocket Manager ------------------ #
class WebSocketManager:
    """Tracks active WebSocket clients and broadcasts messages."""
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def register(self, websocket: WebSocket):
        self.connections.append(websocket)

    async def unregister(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, event: str, data: Any):
        """Broadcast a JSON payload to all connected clients."""
        if not self.connections:
            return
        message = json.dumps({"type": event, "data": data})
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            if ws in self.connections:
                self.connections.remove(ws)


# ------------------ API Models ------------------ #
class BotConfig(BaseModel):
    minProfitPercentage: float
    maxTradeAmount: float
    autoTradingMode: bool
    paperTrading: bool
    selectedExchanges: List[str]


# ------------------ Web Server ------------------ #
class ArbitrageWebServer:
    """Web server for the arbitrage bot."""

    def __init__(self):
        self.logger = setup_logger('WebServer')
        self.app = FastAPI(title="Triangular Arbitrage Bot API")

        # Allow frontend origins (React/Vite)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*", "http://localhost:5173", "http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Core components
        self.exchange_manager = MultiExchangeManager()
        self.websocket_manager = WebSocketManager()  # <--- FIXED
        self.detector: MultiExchangeDetector = None
        self.executor: TradeExecutor = None
        self.running = False

        # Stats
        self.stats = {
            'opportunitiesFound': 0,
            'tradesExecuted': 0,
            'totalProfit': 0.0,
            'successRate': 0.0,
            'activeExchanges': 0
        }

        # Cached opportunities (max 200)
        self.opportunities: List[Dict[str, Any]] = []

        self._setup_routes()

    # ------------------ Routes ------------------ #
    def _setup_routes(self):
        @self.app.get("/api/health")
        async def health_check():
            return {"status": "healthy", "commit": GIT_COMMIT, "timestamp": datetime.now().isoformat()}

        @self.app.post("/api/bot/start")
        async def start_bot(config: BotConfig):
            try:
                self.logger.info(f"Starting bot with config: {config}")
                success = await self.exchange_manager.initialize_exchanges(config.selectedExchanges)
                if not success:
                    raise HTTPException(status_code=400, detail="Failed to connect to exchanges")

                # Initialize detector (now needs websocket_manager)
                detector_config = {
                    'min_profit_percentage': config.minProfitPercentage,
                    'max_trade_amount': config.maxTradeAmount,
                    'prioritize_zero_fee': True
                }
                self.detector = MultiExchangeDetector(self.exchange_manager, self.websocket_manager, detector_config)
                await self.detector.initialize()

                # Initialize trade executor
                executor_config = {
                    'auto_trading': config.autoTradingMode,
                    'paper_trading': config.paperTrading,
                    'enable_manual_confirmation': not config.autoTradingMode
                }
                self.executor = TradeExecutor(self.exchange_manager, executor_config)

                # Start scanning loop
                self.running = True
                asyncio.create_task(self._scanning_loop())

                self.stats['activeExchanges'] = len(config.selectedExchanges)
                return {"status": "success", "message": "Bot started successfully"}
            except Exception as e:
                self.logger.error(f"Error starting bot: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/bot/stop")
        async def stop_bot():
            try:
                self.running = False
                # Close all exchange clients cleanly
                for ex in self.exchange_manager.exchanges.values():
                    try:
                        await ex.close()
                    except Exception:
                        pass
                await self.exchange_manager.disconnect_all()
                self.stats['activeExchanges'] = 0
                return {"status": "success", "message": "Bot stopped successfully"}
            except Exception as e:
                self.logger.error(f"Error stopping bot: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/opportunities")
        async def get_opportunities():
            return self.opportunities

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            await self.websocket_manager.register(websocket)
            try:
                while True:
                    await websocket.receive_text()  # Keep-alive
            except WebSocketDisconnect:
                await self.websocket_manager.unregister(websocket)

    # ------------------ Background Loop ------------------ #
    async def _scanning_loop(self):
        self.logger.info("Starting opportunity scanning loop...")
        while self.running:
            try:
                if self.detector:
                    opportunities = await self.detector.scan_all_opportunities()

                    # Convert to frontend-friendly dicts
                    valid_opps = []
                    for opp in opportunities:
                        try:
                            p_pct = float(opp.profit_percentage)
                            p_amt = float(opp.profit_amount)
                            volume = float(opp.initial_amount)
                            valid_opps.append({
                                'id': f"opp_{int(datetime.now().timestamp() * 1000)}_{len(valid_opps)}",
                                'exchange': getattr(opp, 'exchange', 'Unknown'),
                                'trianglePath': " → ".join(opp.triangle_path),
                                'profitPercentage': round(p_pct, 4),
                                'profitAmount': round(p_amt, 4),
                                'volume': round(volume, 4),
                                'status': 'detected',
                                'timestamp': datetime.now().isoformat()
                            })
                        except Exception:
                            continue

                    self.opportunities = valid_opps[:200]
                    self.stats['opportunitiesFound'] += len(valid_opps)
                    await self.websocket_manager.broadcast("opportunities_update", self.opportunities)
                else:
                    await self.websocket_manager.broadcast("opportunities_update", [])
                await asyncio.sleep(3)  # Reduced from 5 to maintain regular updates
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {e}")
                await self.websocket_manager.broadcast("opportunities_update", [])
                await asyncio.sleep(5)

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="info")


# ------------------ CLI Helpers ------------------ #
_server_instance = None
_server_thread = None

def start_web_server_background():
    global _server_instance, _server_thread
    if _server_instance is None:
        _server_instance = ArbitrageWebServer()
        def run_server():
            try:
                _server_instance.run()
            except Exception as e:
                print(f"Web server error: {e}")
        _server_thread = threading.Thread(target=run_server, daemon=True)
        _server_thread.start()
        time.sleep(2)
        print("🌐 Web server started on http://localhost:8000")

def main():
    server = ArbitrageWebServer()
    server.run()

if __name__ == "__main__":
    main()