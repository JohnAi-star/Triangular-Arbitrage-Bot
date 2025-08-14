"""
Main GUI window for the triangular arbitrage bot.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import asyncio
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from utils.websocket_manager import WebSocketManager
from utils.trade_logger import get_trade_logger

from config.config import Config
from config.exchanges_config import SUPPORTED_EXCHANGES
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector
from arbitrage.trade_executor import TradeExecutor
from models.arbitrage_opportunity import ArbitrageOpportunity
from utils.logger import setup_logger

class ArbitrageBotGUI:
    """Main GUI application for the triangular arbitrage bot."""
    
    def __init__(self):
        self.logger = setup_logger('GUI')
        
        # Initialize WebSocket manager for real-time updates
        self.websocket_manager = WebSocketManager()
        self.websocket_manager.run_in_background()
        
        # Initialize trade logger with WebSocket manager
        self.trade_logger = get_trade_logger(self.websocket_manager)
        
        # Initialize components
        self.exchange_manager = MultiExchangeManager()
        self.detector = None
        self.executor = None
        
        # GUI state
        self.running = False
        self.opportunities = []
        self.selected_exchanges = []
        self.auto_trading = False
        
        # Setup GUI
        self.setup_gui()
        
        # Add GUI callback for WebSocket updates
        self.websocket_manager.add_callback(self._handle_websocket_message)
        
        # Start async event loop in separate thread
        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
    
    def _handle_websocket_message(self, message: Dict[str, Any]):
        """Handle WebSocket messages in the GUI."""
        try:
            event_type = message.get('type')
            data = message.get('data')
            
            if event_type == 'opportunities_update':
                # Update opportunities in GUI thread
                self.root.after(0, lambda: self._update_opportunities_from_websocket(data))
            elif event_type == 'trade_executed':
                # Update trade history in GUI thread
                self.root.after(0, lambda: self._update_trade_history_from_websocket(data))
            
            self.logger.info(f"Processed WebSocket message: {event_type}")
            
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
    
    def _update_opportunities_from_websocket(self, opportunities_data):
        """Update opportunities display from WebSocket data."""
        try:
            if isinstance(opportunities_data, list):
                # Convert WebSocket data to opportunity objects
                self.opportunities = []
                for opp_data in opportunities_data:
                    # Create a simple opportunity object for display
                    opportunity = type('Opportunity', (), {
                        'exchange': opp_data.get('exchange', 'Unknown'),
                        'triangle_path': opp_data.get('trianglePath', ''),
                        'profit_percentage': opp_data.get('profitPercentage', 0),
                        'profit_amount': opp_data.get('profitAmount', 0),
                        'initial_amount': opp_data.get('volume', 0),
                        'is_profitable': opp_data.get('profitPercentage', 0) > 0
                    })()
                    self.opportunities.append(opportunity)
                
                self.logger.info(f"Updated GUI with {len(self.opportunities)} opportunities from WebSocket")
        except Exception as e:
            self.logger.error(f"Error updating opportunities from WebSocket: {e}")
    
    def _update_trade_history_from_websocket(self, trade_data):
        """Update trade history from WebSocket data."""
        try:
            trade_info = f"Trade executed: {trade_data.get('exchange', 'Unknown')} - "
            trade_info += f"Profit: {trade_data.get('profitPercentage', 0):.4f}%"
            self.add_to_trading_history(trade_info)
        except Exception as e:
            self.logger.error(f"Error updating trade history from WebSocket: {e}")
    
    def setup_gui(self):
        """Setup the main GUI window."""
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Main window
        self.root = ctk.CTk()
        self.root.title("Triangular Arbitrage Bot - Multi-Exchange")
        self.root.geometry("1400x900")
        
        # Create main frames
        self.create_control_panel()
        self.create_opportunities_panel()
        self.create_trading_panel()
        self.create_statistics_panel()
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ctk.CTkLabel(self.root, textvariable=self.status_var)
        self.status_bar.pack(side="bottom", fill="x", padx=5, pady=2)
        
        # Start GUI update loop
        self.update_gui()
    
    def create_control_panel(self):
        """Create the control panel."""
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        # Exchange selection
        exchange_frame = ctk.CTkFrame(control_frame)
        exchange_frame.pack(side="left", fill="y", padx=5, pady=5)
        
        ctk.CTkLabel(exchange_frame, text="Select Exchanges:", font=("Arial", 14, "bold")).pack(pady=5)
        
        self.exchange_vars = {}
        for exchange_id, exchange_info in SUPPORTED_EXCHANGES.items():
            var = tk.BooleanVar(value=exchange_info.get('enabled', True))
            self.exchange_vars[exchange_id] = var
            
            checkbox = ctk.CTkCheckBox(
                exchange_frame,
                text=exchange_info['name'],
                variable=var,
                command=self.on_exchange_selection_changed
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
        
        # Trading controls
        trading_frame = ctk.CTkFrame(control_frame)
        trading_frame.pack(side="left", fill="y", padx=5, pady=5)
        
        ctk.CTkLabel(trading_frame, text="Trading Controls:", font=("Arial", 14, "bold")).pack(pady=5)
        
        # Start/Stop button
        self.start_button = ctk.CTkButton(
            trading_frame,
            text="Start Bot",
            command=self.toggle_bot,
            width=120,
            height=40
        )
        self.start_button.pack(pady=5)
        
        # Auto trading toggle
        self.auto_trading_var = tk.BooleanVar(value=Config.AUTO_TRADING_MODE)
        self.auto_trading_checkbox = ctk.CTkCheckBox(
            trading_frame,
            text="Auto Trading",
            variable=self.auto_trading_var,
            command=self.toggle_auto_trading
        )
        self.auto_trading_checkbox.pack(pady=5)
        
        # Settings frame
        settings_frame = ctk.CTkFrame(control_frame)
        settings_frame.pack(side="left", fill="y", padx=5, pady=5)
        
        ctk.CTkLabel(settings_frame, text="Settings:", font=("Arial", 14, "bold")).pack(pady=5)
        
        # Min profit setting
        ctk.CTkLabel(settings_frame, text="Min Profit %:").pack()
        self.min_profit_var = tk.DoubleVar(value=0.5)  # Fixed 0.5%
        self.min_profit_entry = ctk.CTkEntry(settings_frame, textvariable=self.min_profit_var, width=80)
        self.min_profit_entry.configure(state="disabled")  # Lock at 0.5%
        self.min_profit_entry.pack(pady=2)
        
        # Max trade amount setting
        ctk.CTkLabel(settings_frame, text="Max Trade Amount:").pack()
        self.max_trade_var = tk.DoubleVar(value=20.0)  # Fixed $20
        self.max_trade_entry = ctk.CTkEntry(settings_frame, textvariable=self.max_trade_var, width=80)
        self.max_trade_entry.configure(state="disabled")  # Lock at $20
        self.max_trade_entry.pack(pady=2)
        
        # Add label showing locked values
        ctk.CTkLabel(settings_frame, text="(Locked for optimal profit)", 
                    font=("Arial", 10), text_color="yellow").pack(pady=2)
    
    def create_opportunities_panel(self):
        """Create the opportunities display panel."""
        opportunities_frame = ctk.CTkFrame(self.root)
        opportunities_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        
        ctk.CTkLabel(opportunities_frame, text="Arbitrage Opportunities", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Create treeview for opportunities
        columns = ("Exchange", "Triangle", "Profit %", "Profit Amount", "Volume", "Action")
        self.opportunities_tree = ttk.Treeview(opportunities_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        for col in columns:
            self.opportunities_tree.heading(col, text=col)
        
        # Set specific column widths and alignments
        self.opportunities_tree.column("Exchange", width=80, anchor="center")
        self.opportunities_tree.column("Triangle", width=250, anchor="w")  # Wider for paths
        self.opportunities_tree.column("Profit %", width=80, anchor="e")
        self.opportunities_tree.column("Profit Amount", width=100, anchor="e")
        self.opportunities_tree.column("Volume", width=80, anchor="e")
        self.opportunities_tree.column("Action", width=80, anchor="center")
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(opportunities_frame, orient="vertical", command=self.opportunities_tree.yview)
        self.opportunities_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        tree_frame = tk.Frame(opportunities_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.opportunities_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind double-click event
        self.opportunities_tree.bind("<Double-1>", self.on_opportunity_double_click)
        
        # Execute selected button
        self.execute_button = ctk.CTkButton(
            opportunities_frame,
            text="Execute Selected",
            command=self.execute_selected_opportunity,
            width=150,
            height=35
        )
        self.execute_button.pack(pady=10)
    
    def create_trading_panel(self):
        """Create the trading history and controls panel."""
        trading_frame = ctk.CTkFrame(self.root)
        trading_frame.pack(side="right", fill="y", padx=10, pady=5)
        
        ctk.CTkLabel(trading_frame, text="Trading History", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Trading history listbox
        self.trading_history = tk.Listbox(trading_frame, width=40, height=20)
        self.trading_history.pack(padx=10, pady=5)
        
        # Clear history button
        clear_button = ctk.CTkButton(
            trading_frame,
            text="Clear History",
            command=self.clear_trading_history,
            width=120
        )
        clear_button.pack(pady=5)
    
    def create_statistics_panel(self):
        """Create the statistics panel."""
        stats_frame = ctk.CTkFrame(self.root)
        stats_frame.pack(side="bottom", fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(stats_frame, text="Statistics", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Statistics labels
        stats_info_frame = tk.Frame(stats_frame)
        stats_info_frame.pack(fill="x", padx=10, pady=5)
        
        self.stats_labels = {}
        stats_items = [
            ("Opportunities Found", "0"),
            ("Trades Executed", "0"),
            ("Total Profit", "$0.00"),
            ("Success Rate", "0%"),
            ("Active Exchanges", "0")
        ]
        
        for i, (label, initial_value) in enumerate(stats_items):
            frame = tk.Frame(stats_info_frame)
            frame.pack(side="left", fill="x", expand=True)
            
            tk.Label(frame, text=label + ":", font=("Arial", 10, "bold")).pack()
            var = tk.StringVar(value=initial_value)
            self.stats_labels[label.lower().replace(" ", "_")] = var
            tk.Label(frame, textvariable=var, font=("Arial", 12)).pack()
    
    def _run_async_loop(self):
        """Run the async event loop in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def toggle_bot(self):
        """Start or stop the bot."""
        if not self.running:
            self.start_bot()
        else:
            self.stop_bot()
    
    def start_bot(self):
        """Start the arbitrage bot."""
        selected_exchanges = [
            exchange_id for exchange_id, var in self.exchange_vars.items()
            if var.get()
        ]
        
        if not selected_exchanges:
            messagebox.showerror("Error", "Please select at least one exchange")
            return
        
        self.selected_exchanges = selected_exchanges
        self.running = True
        self.start_button.configure(text="Stop Bot")
        self.status_var.set("Starting bot...")
        
        # Start bot in async thread
        asyncio.run_coroutine_threadsafe(self._start_bot_async(), self.loop)
    
    async def _start_bot_async(self):
        """Async bot startup."""
        try:
            # Initialize exchanges
            if not await self.exchange_manager.initialize_exchanges(self.selected_exchanges):
                self.status_var.set("Failed to connect to exchanges")
                self.running = False
                self.start_button.configure(text="Start Bot")
                return
            
            # Display real balance after connection
            self.logger.info("💰 Displaying real account balances...")
            for ex_name, ex in self.exchange_manager.exchanges.items():
                try:
                    balance = await ex.get_account_balance()
                    if balance:
                        total_currencies = len(balance)
                        usd_value = 0.0
                        
                        # Calculate USD value if method exists
                        if hasattr(ex, '_calculate_usd_value'):
                            usd_value = await ex._calculate_usd_value(balance)
                        
                        self.logger.info(f"💰 {ex_name.upper()} BALANCE: {total_currencies} currencies, ~${usd_value:.2f} USD")
                        
                        # Show individual balances
                        for currency, amount in sorted(balance.items(), key=lambda x: x[1], reverse=True):
                            if amount > 0.001:
                                self.logger.info(f"   {currency}: {amount:.8f}")
                    else:
                        self.logger.warning(f"⚠️ No balance detected for {ex_name}")
                except Exception as e:
                    self.logger.error(f"Error displaying balance for {ex_name}: {e}")
            
            # Initialize detector
            self.detector = MultiExchangeDetector(
                self.exchange_manager, 
                self.websocket_manager,
                {
                    'min_profit_percentage': self.min_profit_var.get(),
                    'max_trade_amount': self.max_trade_var.get(),
                    'prioritize_zero_fee': Config.PRIORITIZE_ZERO_FEE
                }
            )
            await self.detector.initialize()
            
            # Initialize executor
            self.executor = TradeExecutor(self.exchange_manager, {
                'auto_trading': self.auto_trading_var.get(),
                'paper_trading': False,  # ALWAYS REAL TRADING
                'min_profit_threshold': Config.MIN_PROFIT_THRESHOLD
            })
            
            # Set WebSocket manager for trade executor
            self.executor.set_websocket_manager(self.websocket_manager)
            
            self.status_var.set("Bot running - scanning for opportunities...")
            
            # Start main bot loop
            await self._bot_main_loop()
            
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            self.status_var.set(f"Error: {str(e)}")
            self.running = False
            self.start_button.configure(text="Start Bot")
    
    async def _bot_main_loop(self):
        """Main bot scanning loop."""
        while self.running:
            try:
                # Scan for opportunities
                opportunities = await self.detector.scan_all_opportunities()
                
                # Update opportunities list
                self.opportunities = opportunities
                
                # Auto-execute if enabled
                if self.auto_trading_var.get():
                    # Filter for profitable opportunities only
                    profitable_opportunities = [
                        opp for opp in opportunities[:5]  # Top 5 opportunities  
                        if (getattr(opp, 'profit_percentage', 0) >= 0.5 and  # Fixed 0.5% threshold for Gate.io
                            hasattr(opp, 'triangle_path') and
                            isinstance(opp.triangle_path, list) and
                            len(opp.triangle_path) >= 3 and
                            opp.triangle_path[0] == 'USDT')  # Only USDT triangles
                    ]
                    
                    if profitable_opportunities:
                        self.logger.info(f"🤖 AUTO-TRADING: Found {len(profitable_opportunities)} profitable USDT opportunities (≥0.5%)")
                        
                        for i, opportunity in enumerate(profitable_opportunities[:2]):  # Execute top 2
                            try:
                                self.logger.info(f"🚀 AUTO-EXECUTING USDT Trade #{i+1}: {opportunity}")
                                
                                # Convert ArbitrageResult to proper format for execution
                                if hasattr(opportunity, 'triangle_path') and isinstance(opportunity.triangle_path, list):
                                    # This is an ArbitrageResult from detector
                                    executable_opportunity = self._convert_result_to_opportunity(opportunity)
                                    success = await self.executor.execute_arbitrage(executable_opportunity)
                                else:
                                    # Already a proper ArbitrageOpportunity
                                    success = await self.executor.execute_arbitrage(opportunity)
                                
                                    # This is an ArbitrageResult, convert to ArbitrageOpportunity
                                    from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep, OpportunityStatus
                                    
                                    # Create proper ArbitrageOpportunity object
                                    triangle_path = opportunity.triangle_path
                                    base_currency = triangle_path[0] if triangle_path else 'USDT'
                                    intermediate_currency = triangle_path[1] if len(triangle_path) > 1 else 'BTC'
                                    quote_currency = triangle_path[2] if len(triangle_path) > 2 else 'ETH'
                                    
                                    # Get real market prices for accurate trade steps
                                    trade_amount = max(20.0, min(opportunity.initial_amount, 50.0))
                                    
                                    # Get current market prices from the exchange
                                    try:
                                        ticker1 = await self.exchange_manager.get_exchange('gate').get_ticker(f"{intermediate_currency}/USDT")
                                        ticker2 = await self.exchange_manager.get_exchange('gate').get_ticker(f"{intermediate_currency}/{quote_currency}")
                                        ticker3 = await self.exchange_manager.get_exchange('gate').get_ticker(f"{quote_currency}/USDT")
                                        
                                        price1 = ticker1.get('ask', 1.0) if ticker1 else 1.0
                                        price2 = ticker2.get('bid', 1.0) if ticker2 else 1.0
                                        price3 = ticker3.get('bid', 1.0) if ticker3 else 1.0
                                        
                                        # Calculate realistic quantities
                                        qty1 = trade_amount  # USDT to spend
                                        qty2 = trade_amount / price1  # Amount of intermediate currency to sell
                                        qty3 = (trade_amount / price1) * price2  # Amount of quote currency to sell
                                        
                                    except Exception as e:
                                        self.logger.error(f"Error getting market prices: {e}")
                                        # Fallback to default values
                                        price1, price2, price3 = 1.0, 1.0, 1.0
                                        qty1, qty2, qty3 = trade_amount, trade_amount, trade_amount
                                    
                                    # Create trade steps for USDT triangle
                                    steps = [
                                        TradeStep(f"{intermediate_currency}/USDT", 'buy', qty1, price1, qty1),  # USDT amount to spend
                                        TradeStep(f"{intermediate_currency}/{quote_currency}", 'sell', qty2, price2, qty2 * price2),
                                        TradeStep(f"{quote_currency}/USDT", 'sell', qty3, price3, qty3 * price3)
                                    ]
                                    
                                    arbitrage_opportunity = ArbitrageOpportunity(
                                        base_currency=base_currency,
                                        intermediate_currency=intermediate_currency,
                                        quote_currency=quote_currency,
                                        pair1=f"{intermediate_currency}/USDT",
                                        pair2=f"{intermediate_currency}/{quote_currency}",
                                        pair3=f"{quote_currency}/USDT",
                                        steps=steps,
                                        initial_amount=trade_amount,
                                        final_amount=trade_amount + (trade_amount * opportunity.profit_percentage / 100),
                                        estimated_fees=trade_amount * 0.006,  # 0.6% fees for Gate.io
                                        estimated_slippage=trade_amount * 0.001
                                    )
                                    
                                    # Set exchange attribute for executor
                                    arbitrage_opportunity.exchange = opportunity.exchange
                                    arbitrage_opportunity.status = OpportunityStatus.DETECTED
                                    
                                    success = await self.executor.execute_arbitrage(arbitrage_opportunity)
                                
                                if success:
                                    self.add_to_trading_history(f"✅ AUTO-TRADE SUCCESS: {opportunity}")
                                    self.logger.info(f"✅ Auto-trade #{i+1} completed successfully!")
                                else:
                                    self.add_to_trading_history(f"❌ AUTO-TRADE FAILED: {opportunity}")
                                    self.logger.error(f"❌ Auto-trade #{i+1} failed")
                                    
                                # Wait between trades
                                await asyncio.sleep(2)
                                
                            except Exception as e:
                                self.logger.error(f"❌ Error in auto-execution #{i+1}: {e}")
                                self.add_to_trading_history(f"❌ AUTO-TRADE ERROR: {str(e)}")
                    else:
                        self.logger.debug(f"🤖 AUTO-TRADING: No profitable opportunities found (need ≥{self.min_profit_var.get()}% profit)")
                
                await asyncio.sleep(1)  # Scan every second
                
            except Exception as e:
                self.logger.error(f"Error in bot main loop: {e}")
                await asyncio.sleep(5)
    
    def stop_bot(self):
        """Stop the arbitrage bot."""
        self.running = False
        self.start_button.configure(text="Start Bot")
        self.status_var.set("Stopping bot...")
        
        # Stop bot in async thread
        asyncio.run_coroutine_threadsafe(self._stop_bot_async(), self.loop)
    
    async def _stop_bot_async(self):
        """Async bot shutdown."""
        try:
            await self.exchange_manager.disconnect_all()
            self.status_var.set("Bot stopped")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
            self.status_var.set("Error stopping bot")
    
    def update_gui(self):
        """Update GUI elements periodically."""
        try:
            # Update opportunities display
            self.update_opportunities_display()
            
            # Update statistics
            self.update_statistics()
            
        except Exception as e:
            self.logger.error(f"Error updating GUI: {e}")
        
        # Schedule next update
        self.root.after(Config.GUI_UPDATE_INTERVAL, self.update_gui)
    
    def _convert_result_to_opportunity(self, result):
        """Convert ArbitrageResult to ArbitrageOpportunity for execution"""
        from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep, OpportunityStatus
        
        # Extract triangle path
        triangle_path = getattr(result, 'triangle_path', [])
        if len(triangle_path) < 3:
            self.logger.error(f"❌ Invalid triangle path: {triangle_path}")
            raise ValueError(f"Invalid triangle path: {triangle_path}")
        
        # CRITICAL: Ensure USDT triangle format
        if triangle_path[0] != 'USDT':
            # Convert to USDT triangle format
            if 'USDT' in triangle_path:
                # Reorder to start with USDT
                usdt_index = triangle_path.index('USDT')
                triangle_path = triangle_path[usdt_index:] + triangle_path[:usdt_index]
            else:
                self.logger.error(f"❌ Non-USDT triangle rejected: {triangle_path}")
                raise ValueError(f"Only USDT triangles allowed: {triangle_path}")
        
        base_currency = triangle_path[0]  # Must be USDT
        intermediate_currency = triangle_path[1]  # e.g., XRP
        quote_currency = triangle_path[2]  # e.g., MXN
        
        self.logger.info(f"🔧 Converting to USDT triangle: {base_currency} → {intermediate_currency} → {quote_currency} → {base_currency}")
        
        # Create trade steps for USDT triangle with proper quantities
        trade_amount = max(5.0, min(20.0, getattr(result, 'initial_amount', 20.0)))  # $5-20 range for Gate.io
        
        # Get current market prices for accurate calculations
        try:
            # This will be filled with real prices during execution
            price1 = 1.0  # Will be updated with real Gate.io price
            price2 = 1.0  # Will be updated with real Gate.io price  
            price3 = 1.0  # Will be updated with real Gate.io price
            
            # Calculate realistic quantities
            qty1 = trade_amount  # USDT amount to spend
            qty2 = trade_amount / price1  # Estimated intermediate currency amount
            qty3 = qty2 * price2  # Estimated quote currency amount
            
        except Exception as e:
            self.logger.error(f"Error getting market prices: {e}")
            # Use safe defaults
            qty1 = trade_amount
            qty2 = trade_amount
            qty3 = trade_amount
        
        steps = [
            TradeStep(f"{intermediate_currency}/USDT", 'buy', qty1, price1, qty2),
            TradeStep(f"{intermediate_currency}/{quote_currency}", 'sell', qty2, price2, qty3),
            TradeStep(f"{quote_currency}/USDT", 'sell', qty3, price3, trade_amount * (1 + getattr(result, 'profit_percentage', 0)/100))  # Sell quote for USDT
        ]
        
        opportunity = ArbitrageOpportunity(
            base_currency=base_currency,
            intermediate_currency=intermediate_currency,
            quote_currency=quote_currency,
            pair1=f"{intermediate_currency}/USDT",
            pair2=f"{intermediate_currency}/{quote_currency}",
            pair3=f"{quote_currency}/USDT",
            steps=steps,
            initial_amount=trade_amount,
            final_amount=trade_amount * (1 + getattr(result, 'profit_percentage', 0)/100),
            estimated_fees=trade_amount * 0.006,  # 0.6% fees for Gate.io
            estimated_slippage=trade_amount * 0.001
        )
        
        # Set additional attributes
        arbitrage_opportunity.exchange = getattr(result, 'exchange', 'gate')
        arbitrage_opportunity.profit_percentage = getattr(result, 'profit_percentage', 0)
        arbitrage_opportunity.profit_amount = getattr(result, 'profit_amount', 0)
        opportunity.status = OpportunityStatus.DETECTED
        
        # Set triangle path using the setter
        arbitrage_opportunity.triangle_path = f"{base_currency} → {intermediate_currency} → {quote_currency} → {base_currency}"
        
        return opportunity
    
    def update_opportunities_display(self):
        """Update the opportunities treeview with proper triangle path formatting."""
        try:
            # Clear existing items
            for item in self.opportunities_tree.get_children():
                self.opportunities_tree.delete(item)
            
            # Add current opportunities
            for i, opportunity in enumerate(self.opportunities[:Config.MAX_OPPORTUNITIES_DISPLAY]):
                # Handle both ArbitrageOpportunity and ArbitrageResult objects
                if hasattr(opportunity, 'exchange'):
                    exchange = opportunity.exchange
                elif hasattr(opportunity, 'name'):
                    exchange = opportunity.name
                else:
                    exchange = 'Unknown'
                
                # Format the triangle path properly
                if hasattr(opportunity, 'triangle_path'):
                    if isinstance(opportunity.triangle_path, list):
                        # For USDT-based triangles: Always show as 4-step cycle
                        if len(opportunity.triangle_path) >= 3:
                            # 3 currencies: USDT, Currency1, Currency2 → show as USDT → Currency1 → Currency2 → USDT
                            path = f"{opportunity.triangle_path[0]} → {opportunity.triangle_path[1]} → {opportunity.triangle_path[2]} → {opportunity.triangle_path[0]}"
                        else:
                            path = ' → '.join(opportunity.triangle_path)
                    else:
                        path = str(opportunity.triangle_path)
                else:
                    path = 'Unknown Path'
                
                profit_pct = getattr(opportunity, 'profit_percentage', 0)
                profit_amt = getattr(opportunity, 'profit_amount', 0)
                initial_amt = getattr(opportunity, 'initial_amount', 0)
                
                # Check if profitable
                is_profitable = False
                if hasattr(opportunity, 'is_profitable'):
                    is_profitable = opportunity.is_profitable
                elif hasattr(opportunity, 'net_profit_percent'):
                    is_profitable = opportunity.net_profit_percent > 0.5
                else:
                    is_profitable = profit_pct > 0.5
                
                values = (
                    exchange,
                    path,
                    f"{profit_pct:.4f}%",
                    f"${profit_amt:.6f}",
                    f"${initial_amt:.2f}",
                    "Execute"
                )
                
                # Color code by profitability
                tags = ("profitable",) if is_profitable else ("unprofitable",)
                
                self.opportunities_tree.insert("", "end", values=values, tags=tags)
            
            # Configure tags
            self.opportunities_tree.tag_configure("profitable", background="lightgreen")
            self.opportunities_tree.tag_configure("unprofitable", background="lightcoral")
            
        except Exception as e:
            self.logger.error(f"Error updating opportunities display: {e}")
    
    def update_statistics(self):
        """Update statistics display."""
        try:
            connected_exchanges = len(self.exchange_manager.get_connected_exchanges())
            self.stats_labels["active_exchanges"].set(str(connected_exchanges))
            
            opportunities_count = len(self.opportunities)
            self.stats_labels["opportunities_found"].set(str(opportunities_count))
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
    
    def on_exchange_selection_changed(self):
        """Handle exchange selection changes."""
        if self.running:
            messagebox.showwarning("Warning", "Stop the bot before changing exchange selection")
            return
    
    def toggle_auto_trading(self):
        """Toggle auto trading mode."""
        self.auto_trading = self.auto_trading_var.get()
        if self.auto_trading:
            result = messagebox.askyesno(
                "Confirm Auto Trading",
                "Are you sure you want to enable auto trading? This will execute REAL trades automatically with REAL money on your exchange account!"
            )
            if not result:
                self.auto_trading_var.set(False)
                self.auto_trading = False
    
    def on_opportunity_double_click(self, event):
        """Handle double-click on opportunity."""
        try:
            selection = self.opportunities_tree.selection()
            if selection:
                item = self.opportunities_tree.item(selection[0])
                index = self.opportunities_tree.index(selection[0])
                
                if index < len(self.opportunities):
                    opportunity = self.opportunities[index]
                    self.show_opportunity_details(opportunity)
        except Exception as e:
            self.logger.error(f"Error handling opportunity double click: {e}")
    
    def show_opportunity_details(self, opportunity: ArbitrageOpportunity):
        """Show detailed information about an opportunity."""
        try:
            details_window = ctk.CTkToplevel(self.root)
            details_window.title("Opportunity Details")
            details_window.geometry("600x400")
            
            # Create scrollable text widget
            text_widget = tk.Text(details_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill="both", expand=True)
            
            # Insert opportunity details
            details = f"""
Arbitrage Opportunity Details
============================

Triangle Path: {opportunity.triangle_path}
Exchange: {getattr(opportunity, 'exchange', 'Multi-Exchange')}

Financial Details:
- Initial Amount: ${opportunity.initial_amount:.6f}
- Final Amount: ${opportunity.final_amount:.6f}
- Gross Profit: {opportunity.profit_percentage:.4f}% (${opportunity.profit_amount:.6f})
- Estimated Fees: ${opportunity.estimated_fees:.6f}
- Estimated Slippage: ${opportunity.estimated_slippage:.6f}
- Net Profit: ${opportunity.net_profit:.6f}

Trade Steps:
"""
            
            for i, step in enumerate(opportunity.steps, 1):
                details += f"{i}. {step.side.upper()} {step.quantity:.6f} {step.symbol} at {step.price:.8f}\n"
            
            details += f"""
Status: {opportunity.status.value}
Detected At: {opportunity.detected_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            text_widget.insert(tk.END, details)
            text_widget.configure(state="disabled")
            
            # Execute button
            execute_btn = ctk.CTkButton(
                details_window,
                text="Execute This Opportunity",
                command=lambda: self.execute_opportunity(opportunity, details_window)
            )
            execute_btn.pack(pady=10)
        except Exception as e:
            self.logger.error(f"Error showing opportunity details: {e}")
    
    def execute_selected_opportunity(self):
        """Execute the selected opportunity."""
        try:
            selection = self.opportunities_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select an opportunity to execute")
                return
            
            index = self.opportunities_tree.index(selection[0])
            if index < len(self.opportunities):
                opportunity = self.opportunities[index]
                asyncio.run_coroutine_threadsafe(
                    self.executor.execute_arbitrage(opportunity),
                    self.loop
                )
                self.add_to_trading_history(f"Manual execution: {opportunity}")
        except Exception as e:
            self.logger.error(f"Error executing selected opportunity: {e}")
            messagebox.showerror("Error", f"Failed to execute opportunity: {str(e)}")
    
    def execute_opportunity(self, opportunity: ArbitrageOpportunity, window=None):
        """Execute a specific opportunity."""
        try:
            if window:
                window.destroy()
            
            asyncio.run_coroutine_threadsafe(
                self.executor.execute_arbitrage(opportunity),
                self.loop
            )
            self.add_to_trading_history(f"Manual execution: {opportunity}")
        except Exception as e:
            self.logger.error(f"Error executing opportunity: {e}")
            messagebox.showerror("Error", f"Failed to execute opportunity: {str(e)}")
    
    def add_to_trading_history(self, message: str):
        """Add a message to the trading history."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.trading_history.insert(0, f"[{timestamp}] {message}")
            
            # Limit history size
            if self.trading_history.size() > 100:
                self.trading_history.delete(tk.END)
        except Exception as e:
            self.logger.error(f"Error adding to trading history: {e}")
    
    def clear_trading_history(self):
        """Clear the trading history."""
        try:
            self.trading_history.delete(0, tk.END)
        except Exception as e:
            self.logger.error(f"Error clearing trading history: {e}")
    
    def _is_valid_usdt_triangle(self, triangle_path) -> bool:
        """Validate that triangle path is a proper USDT triangle."""
        try:
            # Handle different formats
            if isinstance(triangle_path, str):
                path_parts = triangle_path.split(' → ')
                if len(path_parts) >= 3:
                    currencies = path_parts[:3]
                else:
                    return False
            elif isinstance(triangle_path, list):
                if len(triangle_path) >= 3:
                    currencies = triangle_path[:3]
                else:
                    return False
            else:
                return False
            
            # Must start with USDT
            if currencies[0] != 'USDT':
                return False
            
            # Validate all currencies exist on Gate.io
            valid_gateio_currencies = {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS',
                'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
                'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB',
                'FDUSD', 'PENDLE', 'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'RNDR', 'INJ', 'SEI',
                'TIA', 'SUI', 'ORDI', 'SATS', '1000SATS', 'RATS', 'MEME', 'PEPE', 'FLOKI', 'WLD',
                'SCR', 'EIGEN', 'HMSTR', 'CATI', 'NEIRO', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI'
            }
            
            return all(currency in valid_gateio_currencies for currency in currencies)
            
        except Exception as e:
            self.logger.error(f"Error validating USDT triangle: {e}")
            return False
    
    def run(self):
        """Start the GUI application."""
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Error running GUI: {e}")
        finally:
            # Cleanup
            self.running = False
            if hasattr(self, 'websocket_manager'):
                self.websocket_manager.stop()
            if hasattr(self, 'loop'):
                self.loop.call_soon_threadsafe(self.loop.stop)

def main():
    """Main entry point for the GUI application."""
    try:
        app = ArbitrageBotGUI()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()