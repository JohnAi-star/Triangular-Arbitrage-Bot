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

from config.config import Config
from config.exchanges_config import SUPPORTED_EXCHANGES
from exchanges.multi_exchange_manager import MultiExchangeManager
from arbitrage.multi_exchange_detector import MultiExchangeDetector  # FIXED IMPORT PATH
from arbitrage.trade_executor import TradeExecutor
from utils.websocket_manager import WebSocketManager
from utils.trade_logger import get_trade_logger
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
        self.min_profit_var = tk.DoubleVar(value=0.4)  # Set to 0.4% as requested
        self.min_profit_entry = ctk.CTkEntry(settings_frame, textvariable=self.min_profit_var, width=80)
        self.min_profit_entry.configure(state="normal")  # Allow changes
        self.min_profit_entry.pack(pady=2)
        
        # Max trade amount setting
        ctk.CTkLabel(settings_frame, text="Max Trade Amount:").pack()
        self.max_trade_var = tk.DoubleVar(value=20.0)
        self.max_trade_entry = ctk.CTkEntry(settings_frame, textvariable=self.max_trade_var, width=80)
        self.max_trade_entry.configure(state="normal")  # Allow changes
        self.max_trade_entry.pack(pady=2)
        
        # Add label showing exchange-specific optimization
        ctk.CTkLabel(settings_frame, text="(0% and positive opportunities only)", 
                    font=("Arial", 10), text_color="green").pack(pady=2)
    
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
        
        # Log selected exchanges and their fee structures
        from config.exchanges_config import SUPPORTED_EXCHANGES
        self.logger.info("🚀 Starting bot with selected exchanges:")
        for ex_id in selected_exchanges:
            ex_config = SUPPORTED_EXCHANGES.get(ex_id, {})
            self.logger.info(f"   {ex_config.get('name', ex_id)}:")
            self.logger.info(f"     Maker Fee: {ex_config.get('maker_fee', 0)*100:.3f}%")
            self.logger.info(f"     Taker Fee: {ex_config.get('taker_fee', 0)*100:.3f}%")
            if ex_config.get('fee_token'):
                self.logger.info(f"     Fee Token: {ex_config['fee_token']} "
                               f"(Maker: {ex_config.get('maker_fee_with_token', 0)*100:.3f}%, "
                               f"Taker: {ex_config.get('taker_fee_with_token', 0)*100:.3f}%)")
        
        self.selected_exchanges = selected_exchanges
        
        # Update configuration
        Config.MIN_PROFIT_THRESHOLD = self.min_profit_var.get()
        Config.MAX_TRADE_AMOUNT = self.max_trade_var.get()
        Config.AUTO_TRADING_MODE = self.auto_trading_var.get()
        
        # Run bot startup in async thread
        asyncio.run_coroutine_threadsafe(self._async_start_bot(selected_exchanges), self.loop)
        
        self.running = True
        self.start_button.configure(text="Stop Bot")
        self.status_var.set("Bot started - scanning for opportunities")
    
    async def _async_start_bot(self, selected_exchanges):
        """Async method to start the bot."""
        try:
            # Initialize exchange manager
            success = await self.exchange_manager.initialize_exchanges(selected_exchanges)
            if not success:
                self.logger.warning("Some exchanges failed to initialize, but continuing...")
            
            # Initialize detector with proper config
            self.detector = MultiExchangeDetector(
                self.exchange_manager,
                self.websocket_manager,
                {
                    'auto_trading': Config.AUTO_TRADING_MODE,
                    'min_profit_percentage': Config.MIN_PROFIT_THRESHOLD,
                    'max_trade_amount': Config.MAX_TRADE_AMOUNT
                }
            )
            
            await self.detector.initialize()
            
            # Initialize executor
            self.executor = TradeExecutor(
                self.exchange_manager,
                {
                    'auto_trading': Config.AUTO_TRADING_MODE,
                    'paper_trading': False,
                    'enable_manual_confirmation': False
                }
            )
            self.executor.set_websocket_manager(self.websocket_manager)
            
            # Set the executor for the detector
            self.detector.set_executor(self.executor)
            
            # Start continuous scanning
            asyncio.create_task(self.detector.start_continuous_scanning(interval_seconds=30))
            
            self.logger.info("✅ Bot started successfully with all components initialized")
            
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to start bot: {str(e)}"))
            self.running = False
            self.start_button.configure(text="Start Bot")
    
    def stop_bot(self):
        """Stop the arbitrage bot."""
        self.running = False
        self.start_button.configure(text="Start Bot")
        self.status_var.set("Bot stopped")
        
        # Run bot shutdown in async thread
        asyncio.run_coroutine_threadsafe(self._async_stop_bot(), self.loop)
    
    async def _async_stop_bot(self):
        """Async method to stop the bot."""
        try:
            if self.exchange_manager:
                await self.exchange_manager.disconnect_all()
            self.logger.info("Bot stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
    
    def toggle_auto_trading(self):
        """Toggle auto trading mode."""
        Config.AUTO_TRADING_MODE = self.auto_trading_var.get()
        status = "ENABLED" if Config.AUTO_TRADING_MODE else "DISABLED"
        self.logger.info(f"Auto trading {status}")
        self.status_var.set(f"Auto trading {status}")
    
    def on_exchange_selection_changed(self):
        """Handle exchange selection changes."""
        selected_count = sum(1 for var in self.exchange_vars.values() if var.get())
        self.status_var.set(f"{selected_count} exchanges selected")
    
    def on_opportunity_double_click(self, event):
        """Handle double-click on opportunity."""
        selection = self.opportunities_tree.selection()
        if selection:
            self.execute_selected_opportunity()
    
    def execute_selected_opportunity(self):
        """Execute the selected arbitrage opportunity."""
        selection = self.opportunities_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an opportunity to execute")
            return
        
        selected_item = selection[0]
        values = self.opportunities_tree.item(selected_item, 'values')
        
        if values and len(values) >= 3:
            exchange = values[0]
            triangle_path = values[1]
            profit_percentage = float(values[2].replace('%', ''))
            
            if profit_percentage < Config.MIN_PROFIT_THRESHOLD:
                messagebox.showwarning("Warning", 
                    f"Profit ({profit_percentage:.4f}%) is below minimum threshold ({Config.MIN_PROFIT_THRESHOLD}%)")
                return
            
            # Confirm execution
            confirm = messagebox.askyesno(
                "Confirm Execution",
                f"Execute arbitrage on {exchange}?\n"
                f"Path: {triangle_path}\n"
                f"Expected Profit: {profit_percentage:.4f}%"
            )
            
            if confirm:
                self.status_var.set(f"Executing trade on {exchange}...")
                # Here you would normally call the execution logic
                self.add_to_trading_history(f"Manual execution: {exchange} - {triangle_path} - {profit_percentage:.4f}%")
    
    def add_to_trading_history(self, message):
        """Add a message to the trading history."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.trading_history.insert(0, f"[{timestamp}] {message}")
        # Keep only the last 100 entries
        if self.trading_history.size() > 100:
            self.trading_history.delete(100, tk.END)
    
    def clear_trading_history(self):
        """Clear the trading history."""
        self.trading_history.delete(0, tk.END)
    
    def update_gui(self):
        """Update the GUI with current data."""
        try:
            # Update opportunities treeview
            self.opportunities_tree.delete(*self.opportunities_tree.get_children())
            
            for opportunity in self.opportunities:
                # RED/GREEN color scheme only
                if opportunity.profit_percentage == 0.0:
                    action = "🔴 0%"
                    profit_color = "red"
                elif opportunity.profit_percentage > 0.4:
                    action = "🟢 EXEC"
                    profit_color = "green"
                else:
                    # Skip opportunities between 0% and 0.4%
                    continue
                
                values = (
                    opportunity.exchange,
                    opportunity.triangle_path,
                    f"{opportunity.profit_percentage:.4f}%",
                    f"${opportunity.profit_amount:.6f}",
                    f"${opportunity.initial_amount:.2f}",
                    action
                )
                
                item = self.opportunities_tree.insert("", "end", values=values)
                
                # RED/GREEN color coding
                if opportunity.profit_percentage == 0.0:
                    self.opportunities_tree.item(item, tags=("red",))
                elif opportunity.profit_percentage > 0.4:
                    self.opportunities_tree.item(item, tags=("green",))
            
            # Configure RED/GREEN tags
            self.opportunities_tree.tag_configure("red", foreground="red")
            self.opportunities_tree.tag_configure("green", foreground="green")
            
            # Update statistics
            self.stats_labels["opportunities_found"].set(str(len(self.opportunities)))
            
            # Count red and green opportunities
            red_count = sum(1 for opp in self.opportunities if opp.profit_percentage == 0.0)
            green_count = sum(1 for opp in self.opportunities if opp.profit_percentage > 0.4)
            self.stats_labels["trades_executed"].set(f"R:{red_count} G:{green_count}")
            
        except Exception as e:
            self.logger.error(f"Error updating GUI: {e}")
        
        # Schedule next update
        self.root.after(1000, self.update_gui)
    
    def run(self):
        """Run the GUI application."""
        self.root.mainloop()

def main():
    """Main function to start the GUI."""
    app = ArbitrageBotGUI()
    app.run()

if __name__ == "__main__":
    main()