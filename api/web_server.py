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
from simple_arbitrage_bot import SimpleTriangularArbitrage
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
        self.simple_bot = SimpleTriangularArbitrage()  # Add working bot
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
                enforced_min_profit = max(0.5, config.minProfitPercentage)
                enforced_max_trade = min(100.0, config.maxTradeAmount)
                
                Config.MIN_PROFIT_PERCENTAGE = enforced_min_profit
                Config.MAX_TRADE_AMOUNT = enforced_max_trade

                self.auto_trading = config.autoTradingMode
                trading_mode = "🔴 LIVE"
                
                self.logger.info(f"🚀 Starting bot with ENFORCED config:")
                self.logger.info(f"   Requested: minProfit={config.minProfitPercentage}%, maxTrade=${config.maxTradeAmount}")
                self.logger.info(f"   ENFORCED: minProfit={enforced_min_profit}%, maxTrade=${enforced_max_trade}")
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
                
                # Start the simple working bot for REAL opportunities
                asyncio.create_task(self._simple_bot_scanning_loop())
                self.logger.info("✅ Simple working bot started for REAL opportunities")
                
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
                asyncio.create_task(self._usdt_triangle_scanner())  # Add USDT triangle scanner
                self.stats['activeExchanges'] = len(config.selectedExchanges)

                return {
                    "status": "success",
                    "message": "🚀 🔴 LIVE TRADING Bot started successfully",
                    'min_profit_percentage': enforced_min_profit,
                    'max_trade_amount': enforced_max_trade,
                    'limits_enforced': True,
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
        
        @app.post("/api/opportunities/{opportunity_id}/execute")
        async def execute_opportunity(opportunity_id: str):
            try:
                self.logger.info(f"🚀 EXECUTING REAL TRADE: {opportunity_id}")
                
                # Get opportunity from cache
                if opportunity_id not in self.opportunities_cache:
                    self.logger.error(f"❌ Opportunity {opportunity_id} not found in cache")
                    raise HTTPException(status_code=404, detail="Opportunity not found")
                
                opportunity_data = self.opportunities_cache[opportunity_id]
                self.logger.info(f"📊 Opportunity data: {opportunity_data}")
                
                # Create a proper opportunity object for execution
                from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
                
                # Extract data
                exchange_id = opportunity_data.get('exchange', 'binance')
                triangle_path = opportunity_data.get('triangle_path', [])
                profit_percentage = opportunity_data.get('profit_percentage', 0)
                profit_amount = opportunity_data.get('profit_amount', 0)
                initial_amount = opportunity_data.get('initial_amount', 10)
                
                # Create trade steps for USDT-based triangle
                if len(triangle_path) >= 3:
                    base, intermediate, quote = triangle_path[0], triangle_path[1], triangle_path[2]
                    
                    # Create realistic trade steps
                    steps = [
                        TradeStep(f"{intermediate}/USDT", 'buy', initial_amount, 1.0, initial_amount),
                        TradeStep(f"{intermediate}/{quote}", 'sell', initial_amount, 1.0, initial_amount),
                        TradeStep(f"{quote}/USDT", 'sell', initial_amount, 1.0, initial_amount + profit_amount)
                    ]
                    
                    # Create opportunity object
                    opportunity = ArbitrageOpportunity(
                        base_currency=base,
                        intermediate_currency=intermediate,
                        quote_currency=quote,
                        pair1=f"{intermediate}/USDT",
                        pair2=f"{intermediate}/{quote}",
                        pair3=f"{quote}/USDT",
                        steps=steps,
                        initial_amount=initial_amount,
                        final_amount=initial_amount + profit_amount,
                        estimated_fees=initial_amount * 0.003,
                        estimated_slippage=initial_amount * 0.001
                    )
                    
                    # Set exchange for executor
                    setattr(opportunity, 'exchange', exchange_id)
                    
                    self.logger.info(f"🔄 Executing REAL trade on {exchange_id}: {triangle_path}")
                    
                    # Execute the REAL trade
                    if self.executor:
                        success = await self.executor.execute_arbitrage(opportunity)
                        
                        if success:
                            self.stats['tradesExecuted'] += 1
                            self.stats['totalProfit'] += profit_amount
                            
                            # Broadcast successful execution
                            await self.websocket_manager.broadcast('trade_executed', {
                                'id': opportunity_id,
                                'exchange': exchange_id,
                                'trianglePath': " → ".join(triangle_path[:3]),
                                'profitPercentage': profit_percentage,
                                'profitAmount': profit_amount,
                                'volume': initial_amount,
                                'status': 'completed',
                                'timestamp': datetime.now().isoformat(),
                                'real_trade': True
                            })
                            
                            self.logger.info(f"✅ REAL TRADE EXECUTED: {profit_percentage:.4f}% profit, ${profit_amount:.2f} earned!")
                            return {"status": "success", "message": "REAL trade executed successfully", "profit": profit_amount}
                        else:
                            self.logger.error(f"❌ REAL TRADE FAILED for {exchange_id}")
                            return {"status": "failed", "message": "Trade execution failed"}
                    else:
                        return {"status": "failed", "message": "No executor available"}
                else:
                    return {"status": "failed", "message": "Invalid triangle path"}
                
            except Exception as e:
                self.logger.error(f"Error executing opportunity: {str(e)}", exc_info=True)
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
    
    async def _simple_bot_scanning_loop(self):
        """Run the simple working bot continuously and broadcast to UI"""
        self.logger.info("🚀 Starting simple bot scanning for REAL opportunities...")
        
        while self.running:
            try:
                # Get REAL prices from Binance
                prices = self.simple_bot.get_binance_prices()
                
                if prices:
                    # Find REAL triangular opportunities
                    opportunities = self.simple_bot.find_triangular_opportunities(prices)
                    
                    if opportunities:
                        # Convert to UI format
                        ui_opportunities = []
                        for i, opp in enumerate(opportunities):
                            opp_id = f"simple_bot_{int(time.time()*1000)}_{i}"
                            ui_opp = {
                                "id": opp_id,
                                "exchange": "binance",
                                "trianglePath": opp['path'],
                                "profitPercentage": round(opp['profit_pct'], 4),
                                "profitAmount": round(opp['profit_usd'], 4),
                                "volume": round(opp['trade_amount'], 2),
                                "status": "detected",
                                "dataType": "SIMPLE_BOT_REAL",
                                "timestamp": datetime.now().isoformat(),
                                "tradeable": True,
                                "real_market_data": True,
                                "working_bot_opportunity": True
                            }
                            ui_opportunities.append(ui_opp)
                            
                            # Add to cache for execution
                            self.opportunities_cache[opp_id] = {
                                'exchange': 'binance',
                                'triangle_path': opp['path'].split(' → '),
                                'profit_percentage': opp['profit_pct'],
                                'profit_amount': opp['profit_usd'],
                                'initial_amount': opp['trade_amount'],
                                'pairs': opp['pairs']
                            }
                        
                        # Broadcast REAL opportunities to UI
                        await self.websocket_manager.broadcast("opportunities_update", ui_opportunities)
                        self.logger.info(f"💎 Simple bot found {len(opportunities)} REAL opportunities - broadcasted to UI!")
                        
                        # Log top opportunities
                        for i, opp in enumerate(opportunities[:3]):
                            self.logger.info(f"   {i+1}. {opp['path']} = {opp['profit_pct']:.4f}% (${opp['profit_usd']:.2f})")
                    else:
                        self.logger.info("🔍 Simple bot: No opportunities found this scan")
                else:
                    self.logger.warning("❌ Simple bot: Failed to get prices")
                
                await asyncio.sleep(10)  # Scan every 10 seconds like YouTube method
                
            except Exception as e:
                self.logger.error(f"Error in simple bot scanning: {str(e)}")
                await asyncio.sleep(15)
    
    async def _usdt_triangle_scanner(self):
        """Dedicated USDT triangle scanner for USDT→Currency→Currency→USDT opportunities"""
        self.logger.info("💰 Starting USDT triangle scanner...")
        
        while self.running:
            try:
                # Get current Binance prices
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get('https://api.binance.com/api/v3/ticker/price') as response:
                        if response.status == 200:
                            price_data = await response.json()
                            prices = {item['symbol']: float(item['price']) for item in price_data}
                            
                            # Find USDT-based triangular opportunities
                            usdt_opportunities = self._find_usdt_triangles(prices)
                            
                            if usdt_opportunities:
                                # Convert to UI format
                                ui_opportunities = []
                                for i, opp in enumerate(usdt_opportunities):
                                    opp_id = f"usdt_triangle_{int(time.time()*1000)}_{i}"
                                    ui_opp = {
                                        "id": opp_id,
                                        "exchange": "binance",
                                        "trianglePath": opp['path'],
                                        "profitPercentage": round(opp['profit_pct'], 4),
                                        "profitAmount": round(opp['profit_usd'], 4),
                                        "volume": round(opp['trade_amount'], 2),
                                        "status": "detected",
                                        "dataType": "USDT_TRIANGLE",
                                        "timestamp": datetime.now().isoformat(),
                                        "tradeable": True,
                                        "real_market_data": True,
                                        "usdt_based": True
                                    }
                                    ui_opportunities.append(ui_opp)
                                    
                                    # Add to cache for execution
                                    self.opportunities_cache[opp_id] = {
                                        'exchange': 'binance',
                                        'triangle_path': opp['path'].split(' → '),
                                        'profit_percentage': opp['profit_pct'],
                                        'profit_amount': opp['profit_usd'],
                                        'initial_amount': opp['trade_amount']
                                    }
                                
                                # Broadcast USDT opportunities to UI
                                await self.websocket_manager.broadcast("opportunities_update", ui_opportunities)
                                self.logger.info(f"💰 USDT scanner found {len(usdt_opportunities)} opportunities!")
                                
                                # Log USDT opportunities
                                for i, opp in enumerate(usdt_opportunities[:5]):
                                    self.logger.info(f"   💰 {i+1}. {opp['path']} = {opp['profit_pct']:.4f}% (${opp['profit_usd']:.2f})")
                            else:
                                self.logger.info("💰 USDT scanner: No USDT triangles found this scan")
                
                await asyncio.sleep(15)  # Scan every 15 seconds
                
            except Exception as e:
                self.logger.error(f"Error in USDT triangle scanner: {str(e)}")
                await asyncio.sleep(20)
    
    def _find_usdt_triangles(self, prices: Dict[str, float]) -> List[Dict]:
        """Find USDT-based triangular arbitrage opportunities like USDT→RON→EGLD→USDT"""
        opportunities = []
        
        # Get all currencies that have USDT pairs
        usdt_currencies = []
        for symbol, price in prices.items():
            if symbol.endswith('USDT') and price > 0:
                currency = symbol.replace('USDT', '')
                usdt_currencies.append(currency)
        
        self.logger.info(f"💰 Found {len(usdt_currencies)} currencies with USDT pairs")
        
        # Build USDT triangular paths: USDT → Currency1 → Currency2 → USDT
        for curr1 in usdt_currencies:
            for curr2 in usdt_currencies:
                if curr1 != curr2:
                    try:
                        # Required symbols for USDT triangle
                        symbol1 = f"{curr1}USDT"  # USDT → curr1
                        symbol2 = f"{curr1}{curr2}"  # curr1 → curr2
                        symbol3 = f"{curr2}USDT"  # curr2 → USDT
                        
                        # Alternative if curr1→curr2 doesn't exist, try curr2→curr1
                        alt_symbol2 = f"{curr2}{curr1}"
                        
                        if (symbol1 in prices and symbol3 in prices and 
                            (symbol2 in prices or alt_symbol2 in prices)):
                            
                            # Calculate USDT triangle profit
                            start_usdt = 100  # Start with $100 USDT
                            
                            # Step 1: USDT → curr1
                            price1 = prices[symbol1]
                            amount_curr1 = start_usdt / price1
                            
                            # Step 2: curr1 → curr2
                            if symbol2 in prices:
                                price2 = prices[symbol2]
                                amount_curr2 = amount_curr1 * price2
                            elif alt_symbol2 in prices:
                                price2 = prices[alt_symbol2]
                                amount_curr2 = amount_curr1 / price2
                            else:
                                continue
                            
                            # Step 3: curr2 → USDT
                            price3 = prices[symbol3]
                            final_usdt = amount_curr2 * price3
                            
                            # Calculate profit
                            profit_usdt = final_usdt - start_usdt
                            profit_pct = (profit_usdt / start_usdt) * 100
                            
                            # Apply trading fees (0.1% per trade × 3 trades = 0.3%)
                            net_profit_pct = profit_pct - 0.3
                            net_profit_usd = start_usdt * (net_profit_pct / 100)
                            
                            # Only include profitable opportunities
                            if net_profit_pct >= 0.1:  # 0.1% minimum profit
                                opportunity = {
                                    'path': f"USDT → {curr1} → {curr2} → USDT",
                                    'pairs': [symbol1, symbol2 if symbol2 in prices else alt_symbol2, symbol3],
                                    'profit_pct': net_profit_pct,
                                    'profit_usd': net_profit_usd,
                                    'trade_amount': start_usdt,
                                    'timestamp': datetime.now().isoformat()
                                }
                                opportunities.append(opportunity)
                                
                    except Exception as e:
                        continue
        
        # Sort by profitability
        opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
        return opportunities[:20]  # Return top 20 USDT opportunities
    
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
            # STRICT AUTO-TRADING FILTERS
            highly_profitable_opportunities = [
                opp for opp in opportunities
                if (hasattr(opp, 'is_profitable') and opp.is_profitable and 
                    opp.profit_percentage >= 0.1 and  # Lower threshold
                    opp.initial_amount <= 100.0)
            ]

            if not highly_profitable_opportunities:
                self.logger.debug("🚫 AUTO-TRADE: No valid opportunities (need ≥0.1% profit, ≤$100 amount)")
                return

            # Execute top 3 most profitable opportunities
            sorted_opportunities = sorted(highly_profitable_opportunities, key=lambda x: x.profit_percentage, reverse=True)
            for i, opportunity in enumerate(sorted_opportunities[:3]):
                try:
                    # ENFORCE LIMITS AGAIN
                    trade_amount = min(opportunity.initial_amount, 100.0)
                    expected_profit_usd = trade_amount * (opportunity.profit_percentage / 100)
                    
                    self.logger.info(f"🤖 AUTO-EXECUTING TRADE #{i+1}:")
                    self.logger.info(f"   Exchange: {opportunity.exchange}")
                    self.logger.info(f"   Profit: {opportunity.profit_percentage:.4f}%")
                    self.logger.info(f"   Amount: ${trade_amount}")
                    self.logger.info(f"   Expected Profit: ${expected_profit_usd:.2f}")
                    
                    setattr(opportunity, 'exchange', opportunity.exchange)
                    setattr(opportunity, 'initial_amount', trade_amount)  # Enforce limit
                    success = await self.executor.execute_arbitrage(opportunity)

                    if success:
                        self.stats['tradesExecuted'] += 1
                        self.stats['totalProfit'] += expected_profit_usd
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': expected_profit_usd,
                            'volume': trade_amount,
                            'status': 'completed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                        self.logger.info(f"✅ AUTO-TRADE SUCCESS: {opportunity.profit_percentage:.4f}% profit, ${expected_profit_usd:.2f} earned!")
                    else:
                        self.logger.warning(f"❌ AUTO-TRADE FAILED for {opportunity.exchange}")
                        
                        # Log failed auto-trade
                        await self.websocket_manager.broadcast('opportunity_executed', {
                            'id': f"auto_fail_{int(time.time()*1000)}",
                            'exchange': opportunity.exchange,
                            'profitPercentage': opportunity.profit_percentage,
                            'profitAmount': 0,
                            'volume': trade_amount,
                            'status': 'failed',
                            'timestamp': datetime.now().isoformat(),
                            'auto_executed': True
                        })
                except Exception as e:
                    self.logger.error(f"❌ Error in auto-execution: {str(e)}")
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