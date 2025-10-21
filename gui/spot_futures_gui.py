import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import asyncio
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchanges.unified_exchange import UnifiedExchange
from exchanges.kucoin_futures_exchange import KuCoinFuturesExchange
from arbitrage.spot_futures_detector import SpotFuturesDetector
from arbitrage.spot_futures_executor import SpotFuturesExecutor
from arbitrage.spot_futures_monitor import SpotFuturesMonitor
from utils.trade_logger import get_trade_logger
from utils.logger import setup_logger
from dotenv import load_dotenv

load_dotenv()

class SpotFuturesGUI:
    def __init__(self):
        self.logger = setup_logger('SpotFuturesGUI')

        self.trade_logger = get_trade_logger()

        self.spot_exchange = None
        self.futures_exchange = None
        self.detector = None
        self.executor = None
        self.monitor = None

        self.running = False
        self.opportunities = []
        self.auto_trading = False

        self.setup_gui()

        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()

    def setup_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Spot-Futures Arbitrage Bot - KuCoin")
        self.root.geometry("1400x900")

        self.create_control_panel()
        self.create_opportunities_panel()
        self.create_trading_panel()
        self.create_statistics_panel()

        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ctk.CTkLabel(self.root, textvariable=self.status_var)
        self.status_bar.pack(side="bottom", fill="x", padx=5, pady=2)

        self.update_gui()

    def create_control_panel(self):
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(side="top", fill="x", padx=10, pady=5)

        trading_frame = ctk.CTkFrame(control_frame)
        trading_frame.pack(side="left", fill="y", padx=5, pady=5)

        ctk.CTkLabel(trading_frame, text="Trading Controls:", font=("Arial", 14, "bold")).pack(pady=5)

        self.start_button = ctk.CTkButton(
            trading_frame,
            text="Start Bot",
            command=self.toggle_bot,
            width=120,
            height=40
        )
        self.start_button.pack(pady=5)

        self.auto_trading_var = tk.BooleanVar(value=False)
        self.auto_trading_checkbox = ctk.CTkCheckBox(
            trading_frame,
            text="Auto Trading",
            variable=self.auto_trading_var,
            command=self.toggle_auto_trading
        )
        self.auto_trading_checkbox.pack(pady=5)

        settings_frame = ctk.CTkFrame(control_frame)
        settings_frame.pack(side="left", fill="y", padx=5, pady=5)

        ctk.CTkLabel(settings_frame, text="Settings:", font=("Arial", 14, "bold")).pack(pady=5)

        ctk.CTkLabel(settings_frame, text="Min Profit %:").pack()
        self.min_profit_var = tk.DoubleVar(value=0.3)
        self.min_profit_entry = ctk.CTkEntry(settings_frame, textvariable=self.min_profit_var, width=80)
        self.min_profit_entry.pack(pady=2)

        ctk.CTkLabel(settings_frame, text="Trade Amount ($):").pack()
        self.trade_amount_var = tk.DoubleVar(value=20.0)
        self.trade_amount_entry = ctk.CTkEntry(settings_frame, textvariable=self.trade_amount_var, width=80)
        self.trade_amount_entry.pack(pady=2)

    def create_opportunities_panel(self):
        opportunities_frame = ctk.CTkFrame(self.root)
        opportunities_frame.pack(side="left", fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(opportunities_frame, text="Spot-Futures Opportunities", font=("Arial", 16, "bold")).pack(pady=5)

        columns = ("Symbol", "Direction", "Spot Price", "Futures Price", "Spread %", "Profit %", "Action")
        self.opportunities_tree = ttk.Treeview(opportunities_frame, columns=columns, show="headings", height=25)

        for col in columns:
            self.opportunities_tree.heading(col, text=col)

        self.opportunities_tree.column("Symbol", width=100, anchor="center")
        self.opportunities_tree.column("Direction", width=150, anchor="w")
        self.opportunities_tree.column("Spot Price", width=110, anchor="e")
        self.opportunities_tree.column("Futures Price", width=110, anchor="e")
        self.opportunities_tree.column("Spread %", width=90, anchor="e")
        self.opportunities_tree.column("Profit %", width=90, anchor="e")
        self.opportunities_tree.column("Action", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(opportunities_frame, orient="vertical", command=self.opportunities_tree.yview)
        self.opportunities_tree.configure(yscrollcommand=scrollbar.set)

        tree_frame = tk.Frame(opportunities_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.opportunities_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.opportunities_tree.bind("<Double-1>", self.on_opportunity_double_click)

        self.execute_button = ctk.CTkButton(
            opportunities_frame,
            text="Execute Selected",
            command=self.execute_selected_opportunity,
            width=150,
            height=35
        )
        self.execute_button.pack(pady=10)

    def create_trading_panel(self):
        trading_frame = ctk.CTkFrame(self.root)
        trading_frame.pack(side="right", fill="y", padx=10, pady=5)

        ctk.CTkLabel(trading_frame, text="Trading History", font=("Arial", 16, "bold")).pack(pady=5)

        self.trading_history = tk.Listbox(trading_frame, width=50, height=30)
        self.trading_history.pack(padx=10, pady=5)

        clear_button = ctk.CTkButton(
            trading_frame,
            text="Clear History",
            command=self.clear_trading_history,
            width=120
        )
        clear_button.pack(pady=5)

    def create_statistics_panel(self):
        stats_frame = ctk.CTkFrame(self.root)
        stats_frame.pack(side="bottom", fill="x", padx=10, pady=5)

        ctk.CTkLabel(stats_frame, text="Statistics", font=("Arial", 16, "bold")).pack(pady=5)

        stats_info_frame = tk.Frame(stats_frame)
        stats_info_frame.pack(fill="x", padx=10, pady=5)

        self.stats_labels = {}
        stats_items = [
            ("Opportunities Found", "0"),
            ("Trades Executed", "0"),
            ("Total Profit", "$0.00"),
            ("Success Rate", "0%")
        ]

        for i, (label, initial_value) in enumerate(stats_items):
            frame = tk.Frame(stats_info_frame)
            frame.pack(side="left", fill="x", expand=True)

            tk.Label(frame, text=label + ":", font=("Arial", 10, "bold")).pack()
            var = tk.StringVar(value=initial_value)
            self.stats_labels[label.lower().replace(" ", "_")] = var
            tk.Label(frame, textvariable=var, font=("Arial", 12)).pack()

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def toggle_bot(self):
        if not self.running:
            self.start_bot()
        else:
            self.stop_bot()

    def start_bot(self):
        self.running = True
        self.start_button.configure(text="Stop Bot")
        self.status_var.set("Starting bot...")

        asyncio.run_coroutine_threadsafe(self._start_bot_async(), self.loop)

    async def _start_bot_async(self):
        try:
            api_key = os.getenv('KUCOIN_API_KEY', '')
            api_secret = os.getenv('KUCOIN_API_SECRET', '')
            api_passphrase = os.getenv('KUCOIN_PASSPHRASE', '')

            if not all([api_key, api_secret, api_passphrase]):
                self.status_var.set("Error: Missing API credentials")
                self.running = False
                self.start_button.configure(text="Start Bot")
                return

            self.logger.info("Creating spot exchange...")
            spot_config = {
                'exchange_id': 'kucoin',
                'api_key': api_key,
                'api_secret': api_secret,
                'passphrase': api_passphrase,
                'sandbox': False
            }
            self.spot_exchange = UnifiedExchange(spot_config)

            self.logger.info("Creating futures exchange...")
            self.futures_exchange = KuCoinFuturesExchange(
                api_key=api_key,
                api_secret=api_secret,
                api_passphrase=api_passphrase,
                is_sandbox=False
            )

            await self.spot_exchange.connect()
            await self.futures_exchange.connect()

            self.logger.info("Testing connections...")
            spot_ticker = await self.spot_exchange.get_ticker('BTC/USDT')
            futures_ticker = await self.futures_exchange.get_ticker('BTC/USDT')

            self.logger.info(f"Spot BTC: ${spot_ticker['last']:.2f}")
            self.logger.info(f"Futures BTC: ${futures_ticker['last']:.2f}")

            self.detector = SpotFuturesDetector(self.spot_exchange, self.futures_exchange)

            self.executor = SpotFuturesExecutor(
                self.spot_exchange,
                self.futures_exchange,
                self.trade_logger
            )

            self.monitor = SpotFuturesMonitor(
                self.detector,
                self.executor,
                self.trade_logger
            )

            self.status_var.set("Bot running - scanning for opportunities...")

            await self._bot_main_loop()

        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            self.status_var.set(f"Error: {str(e)}")
            self.running = False
            self.start_button.configure(text="Start Bot")

    async def _bot_main_loop(self):
        scan_count = 0
        while self.running:
            try:
                opportunities = await self.detector.scan_opportunities(self.min_profit_var.get())

                self.opportunities = opportunities
                scan_count += 1

                if opportunities and self.auto_trading_var.get():
                    for opportunity in opportunities[:1]:
                        if opportunity.is_tradeable:
                            try:
                                result = await self.executor.execute_arbitrage(
                                    opportunity,
                                    self.trade_amount_var.get()
                                )

                                if 'position_id' in result:
                                    self.add_to_trading_history(f"Auto-trade executed: {opportunity.symbol} - {result['position_id']}")
                                    self.logger.info(f"Trade success: {result}")
                                else:
                                    self.add_to_trading_history(f"Trade failed: {opportunity.symbol}")

                            except Exception as e:
                                self.logger.error(f"Trade execution error: {e}")
                                self.add_to_trading_history(f"Error: {str(e)}")

                if scan_count % 10 == 0:
                    self.logger.info(f"Scans: {scan_count} | Opportunities: {len(opportunities)}")

                await asyncio.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Error in bot main loop: {e}")
                await asyncio.sleep(5)

    def stop_bot(self):
        self.running = False
        self.start_button.configure(text="Start Bot")
        self.status_var.set("Stopping bot...")

        asyncio.run_coroutine_threadsafe(self._stop_bot_async(), self.loop)

    async def _stop_bot_async(self):
        try:
            if self.monitor:
                self.monitor.stop_monitoring()

            if self.futures_exchange and hasattr(self.futures_exchange, 'close'):
                await self.futures_exchange.close()

            self.status_var.set("Bot stopped")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
            self.status_var.set("Error stopping bot")

    def update_gui(self):
        try:
            self.update_opportunities_display()
            self.update_statistics()
        except Exception as e:
            self.logger.error(f"Error updating GUI: {e}")

        self.root.after(500, self.update_gui)

    def update_opportunities_display(self):
        try:
            for item in self.opportunities_tree.get_children():
                self.opportunities_tree.delete(item)

            for opportunity in self.opportunities[:50]:
                symbol = opportunity.symbol
                direction = opportunity.direction.value.replace('_', ' ').title()
                spot_price = f"${opportunity.spot_price:.2f}"
                futures_price = f"${opportunity.futures_price:.2f}"
                spread_pct = f"{'+' if opportunity.spread_percentage >= 0 else ''}{opportunity.spread_percentage:.4f}%"
                profit_pct = f"{opportunity.profit_percentage:.4f}%"
                action = "Execute" if opportunity.is_tradeable else "Monitor"

                values = (symbol, direction, spot_price, futures_price, spread_pct, profit_pct, action)

                if opportunity.is_tradeable:
                    tags = ("green",)
                else:
                    tags = ("red",)

                self.opportunities_tree.insert("", "end", values=values, tags=tags)

            self.opportunities_tree.tag_configure("green", background="lightgreen", foreground="darkgreen")
            self.opportunities_tree.tag_configure("red", background="lightcoral", foreground="darkred")

        except Exception as e:
            self.logger.error(f"Error updating opportunities display: {e}")

    def update_statistics(self):
        try:
            opportunities_count = len(self.opportunities)
            self.stats_labels["opportunities_found"].set(str(opportunities_count))

            tradeable_count = len([o for o in self.opportunities if o.is_tradeable])
            self.stats_labels["trades_executed"].set(str(tradeable_count))

        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")

    def toggle_auto_trading(self):
        self.auto_trading = self.auto_trading_var.get()
        if self.auto_trading:
            result = messagebox.askyesno(
                "Confirm Auto Trading",
                "Enable auto trading? This will execute REAL trades with REAL money!"
            )
            if not result:
                self.auto_trading_var.set(False)
                self.auto_trading = False

    def on_opportunity_double_click(self, event):
        try:
            selection = self.opportunities_tree.selection()
            if selection:
                index = self.opportunities_tree.index(selection[0])

                if index < len(self.opportunities):
                    opportunity = self.opportunities[index]
                    self.show_opportunity_details(opportunity)
        except Exception as e:
            self.logger.error(f"Error handling opportunity double click: {e}")

    def show_opportunity_details(self, opportunity):
        try:
            details_window = ctk.CTkToplevel(self.root)
            details_window.title("Opportunity Details")
            details_window.geometry("600x400")

            text_widget = tk.Text(details_window, wrap=tk.WORD, padx=10, pady=10)
            text_widget.pack(fill="both", expand=True)

            details = f"""
Spot-Futures Opportunity Details
================================

Symbol: {opportunity.symbol}
Direction: {opportunity.direction.value}

Prices:
- Spot Price: ${opportunity.spot_price:.2f}
- Futures Price: ${opportunity.futures_price:.2f}

Profitability:
- Spread: {opportunity.spread_percentage:.4f}%
- Estimated Fees: {opportunity.estimated_fees:.4f}%
- Net Profit: {opportunity.profit_percentage:.4f}%

Status: {"TRADEABLE" if opportunity.is_tradeable else "MONITORING"}
Timestamp: {datetime.fromtimestamp(opportunity.timestamp).strftime('%Y-%m-%d %H:%M:%S')}
"""

            text_widget.insert(tk.END, details)
            text_widget.configure(state="disabled")

            if opportunity.is_tradeable:
                execute_btn = ctk.CTkButton(
                    details_window,
                    text="Execute This Opportunity",
                    command=lambda: self.execute_opportunity(opportunity, details_window)
                )
                execute_btn.pack(pady=10)
        except Exception as e:
            self.logger.error(f"Error showing opportunity details: {e}")

    def execute_selected_opportunity(self):
        try:
            selection = self.opportunities_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select an opportunity to execute")
                return

            index = self.opportunities_tree.index(selection[0])
            if index < len(self.opportunities):
                opportunity = self.opportunities[index]

                if not opportunity.is_tradeable:
                    messagebox.showwarning("Warning", "This opportunity is not currently tradeable")
                    return

                asyncio.run_coroutine_threadsafe(
                    self._execute_opportunity_async(opportunity),
                    self.loop
                )
                self.add_to_trading_history(f"Manual execution: {opportunity.symbol}")
        except Exception as e:
            self.logger.error(f"Error executing selected opportunity: {e}")
            messagebox.showerror("Error", f"Failed to execute opportunity: {str(e)}")

    async def _execute_opportunity_async(self, opportunity):
        try:
            result = await self.executor.execute_arbitrage(opportunity, self.trade_amount_var.get())

            if 'position_id' in result:
                self.add_to_trading_history(f"Success: {opportunity.symbol} - {result['position_id']}")
            else:
                self.add_to_trading_history(f"Failed: {opportunity.symbol}")

        except Exception as e:
            self.logger.error(f"Error in async execution: {e}")
            self.add_to_trading_history(f"Error: {str(e)}")

    def execute_opportunity(self, opportunity, window=None):
        try:
            if window:
                window.destroy()

            asyncio.run_coroutine_threadsafe(
                self._execute_opportunity_async(opportunity),
                self.loop
            )
            self.add_to_trading_history(f"Manual execution: {opportunity.symbol}")
        except Exception as e:
            self.logger.error(f"Error executing opportunity: {e}")
            messagebox.showerror("Error", f"Failed to execute opportunity: {str(e)}")

    def add_to_trading_history(self, message: str):
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.trading_history.insert(0, f"[{timestamp}] {message}")

            if self.trading_history.size() > 100:
                self.trading_history.delete(tk.END)
        except Exception as e:
            self.logger.error(f"Error adding to trading history: {e}")

    def clear_trading_history(self):
        try:
            self.trading_history.delete(0, tk.END)
        except Exception as e:
            self.logger.error(f"Error clearing trading history: {e}")

    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Error running GUI: {e}")
        finally:
            self.running = False
            if hasattr(self, 'loop'):
                self.loop.call_soon_threadsafe(self.loop.stop)

def main():
    try:
        app = SpotFuturesGUI()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
