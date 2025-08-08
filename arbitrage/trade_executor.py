import sys
import asyncio
import time
import uuid
from typing import Dict, Any, List
from datetime import datetime
from models.arbitrage_opportunity import ArbitrageOpportunity, OpportunityStatus, TradeStep
from models.trade_log import TradeLog, TradeStepLog, TradeStatus, TradeDirection
from exchanges.multi_exchange_manager import MultiExchangeManager
from utils.logger import setup_logger, setup_trade_logger
from utils.trade_logger import get_trade_logger
from config.config import Config

def safe_unicode_text(text: str) -> str:
    """Convert Unicode symbols to Windows-safe equivalents."""
    if sys.platform.startswith('win'):
        replacements = {
            '→': '->',
            '✅': '[OK]',
            '❌': '[FAIL]',
            '🔁': '[RETRY]',
            '💰': '$',
            '📊': '[STATS]',
            '🎯': '[TARGET]',
            '⚠️': '[WARN]',
            '🚀': '[START]',
            '🔺': '[BOT]',
            '🤖': '[AUTO]',
            '🟡': '[PAPER]',
            '🔴': '[LIVE]'
        }
        for unicode_char, ascii_equiv in replacements.items():
            text = text.replace(unicode_char, ascii_equiv)
    return text

class TradeExecutor:
    """Executes triangular arbitrage trades across multiple exchanges."""
    
    def __init__(self, exchange_manager: MultiExchangeManager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.config = config
        self.logger = setup_logger('TradeExecutor')
        self.trade_logger = setup_trade_logger()
        self.detailed_trade_logger = get_trade_logger()
        self.auto_trading = config.get('auto_trading', False)
        self.paper_trading = False  # ALWAYS REAL TRADING WITH REAL MONEY
        
        # Log trading mode clearly
        trading_mode = "🔴 LIVE TRADING (REAL MONEY)" 
        self.logger.info(f"TradeExecutor initialized: {trading_mode}")
        self.logger.info(f"Auto-trading: {'ENABLED' if self.auto_trading else 'DISABLED'}")
        self.logger.info(f"🔴 LIVE TRADING: All trades will be executed with REAL money on your exchange account!")
        self.logger.info(f"✅ READY: Real-money trading enabled with enforced profit/amount limits.")
    
    def set_websocket_manager(self, websocket_manager):
        """Set WebSocket manager for trade broadcasting."""
        if websocket_manager:
            self.detailed_trade_logger = get_trade_logger(websocket_manager)
            self.logger.info("✅ WebSocket manager set for trade executor")
        else:
            self.logger.warning("⚠️ No WebSocket manager provided to trade executor")
        
    async def _verify_sufficient_balance(self, exchange, base_currency: str, required_amount: float) -> bool:
        """Verify sufficient balance for trading."""
        try:
            balance = await exchange.get_account_balance()
            available = balance.get(base_currency, 0.0)
            
            if available >= required_amount:
                self.logger.info(f"✅ Sufficient balance: {available:.6f} {base_currency} (need {required_amount:.6f})")
                return True
            else:
                self.logger.error(f"❌ Insufficient balance: {available:.6f} {base_currency} (need {required_amount:.6f})")
                return False
        except Exception as e:
            self.logger.error(f"Error checking balance: {e}")
            return False
    
    async def _get_real_market_price(self, exchange, symbol: str, side: str) -> float:
        """Get real-time market price for accurate execution."""
        try:
            ticker = await exchange.get_ticker(symbol)
            if side.lower() == 'buy':
                price = ticker.get('ask', 0)  # Buy at ask price
            else:
                price = ticker.get('bid', 0)  # Sell at bid price
            
            self.logger.info(f"📊 Real-time {symbol} {side} price: {price:.8f}")
            return float(price) if price else 0.0
        except Exception as e:
            self.logger.error(f"Error getting market price for {symbol}: {e}")
            return 0.0
    
    async def _execute_single_order(self, exchange, symbol: str, side: str, quantity: float, step_num: int) -> Dict[str, Any]:
        """Execute a single market order with detailed logging."""
        try:
            self.logger.info(f"🔄 STEP {step_num}: Executing REAL {side.upper()} order")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Quantity: {quantity:.8f}")
            self.logger.info(f"   Side: {side.upper()}")
            
            # Get current market price for logging
            market_price = await self._get_real_market_price(exchange, symbol, side)
            estimated_value = quantity * market_price if side == 'sell' else quantity
            self.logger.info(f"   Estimated Value: ${estimated_value:.2f}")
            
            # Execute the REAL order
            order_start_time = time.time()
            order = await exchange.place_market_order(symbol, side, quantity)
            execution_time = (time.time() - order_start_time) * 1000
            
            if order and order.get('id'):
                # Log successful order details
                order_id = order.get('id')
                filled_qty = float(order.get('filled', 0))
                avg_price = float(order.get('average', 0))
                total_cost = float(order.get('cost', 0))
                fee_info = order.get('fee', {})
                fee_cost = float(fee_info.get('cost', 0))
                fee_currency = fee_info.get('currency', 'Unknown')
                
                self.logger.info(f"✅ REAL ORDER EXECUTED SUCCESSFULLY:")
                self.logger.info(f"   Order ID: {order_id}")
                self.logger.info(f"   Filled: {filled_qty:.8f} {symbol}")
                self.logger.info(f"   Average Price: {avg_price:.8f}")
                self.logger.info(f"   Total Cost: {total_cost:.8f}")
                self.logger.info(f"   Fee: {fee_cost:.8f} {fee_currency}")
                self.logger.info(f"   Execution Time: {execution_time:.0f}ms")
                self.logger.info(f"   Status: {order.get('status', 'Unknown')}")
                
                # Verify order was filled
                if order.get('status') == 'closed' and filled_qty > 0:
                    self.logger.info(f"🎉 Order {order_id} FULLY FILLED - Trade recorded on Binance!")
                    return {
                        'success': True,
                        'order_id': order_id,
                        'filled_quantity': filled_qty,
                        'average_price': avg_price,
                        'total_cost': total_cost,
                        'fee_cost': fee_cost,
                        'fee_currency': fee_currency,
                        'execution_time_ms': execution_time,
                        'raw_order': order
                    }
                else:
                    self.logger.error(f"❌ Order {order_id} not fully filled: status={order.get('status')}, filled={filled_qty}")
                    return {'success': False, 'error': f'Order not filled: {order.get("status")}', 'order_id': order_id}
            else:
                self.logger.error(f"❌ Order execution failed - no order ID returned")
                return {'success': False, 'error': 'No order ID returned', 'raw_response': order}
                
        except Exception as e:
            self.logger.error(f"❌ CRITICAL: Order execution failed for {symbol} {side}: {str(e)}")
            return {'success': False, 'error': str(e), 'exception_type': type(e).__name__}
    
    async def request_confirmation(self, opportunity: ArbitrageOpportunity) -> bool:
        """Request manual confirmation for trade execution."""
        # Skip confirmation if auto-trading is enabled
        if self.auto_trading:
            self.logger.info(f"🤖 🔴 LIVE AUTO-TRADING: Executing without confirmation")
            return True
            
        # Skip confirmation if manual confirmation is disabled
        if not self.config.get('enable_manual_confirmation', True):
            self.logger.info(f"🤖 🔴 LIVE AUTO-TRADING: Manual confirmation disabled")
            return True
            
        # For live trading auto mode, execute immediately
        if self.auto_trading:
            self.logger.info(f"🔴 🤖 LIVE AUTO-TRADING: Executing immediately")
            return True
            
        print("\n" + "="*80)
        print("🔍 ARBITRAGE OPPORTUNITY DETECTED")
        print("="*80)
        print(f"Exchange: {getattr(opportunity, 'exchange', 'Multi-Exchange')}")
        print(f"Triangle Path: {opportunity.triangle_path}")
        print(f"Initial Amount: {opportunity.initial_amount:.6f} {opportunity.base_currency}")
        print(f"Expected Final Amount: {opportunity.final_amount:.6f} {opportunity.base_currency}")
        print(f"Gross Profit: {opportunity.profit_percentage:.4f}% ({opportunity.profit_amount:.6f} {opportunity.base_currency})")
        print(f"Estimated Fees: {opportunity.estimated_fees:.6f} {opportunity.base_currency}")
        print(f"Estimated Slippage: {opportunity.estimated_slippage:.6f} {opportunity.base_currency}")
        print(f"Net Profit: {opportunity.net_profit:.6f} {opportunity.base_currency}")
        
        mode_text = safe_unicode_text('🤖 🔴 LIVE AUTO-TRADING' if self.auto_trading else '🔴 LIVE TRADING (REAL MONEY)')
        print(f"Trading Mode: {mode_text}")
        
        print("\nTrade Steps:")
        for i, step in enumerate(opportunity.steps, 1):
            print(f"  {i}. {step.side.upper()} {step.quantity:.6f} {step.symbol} at {step.price:.8f}")
        print("="*80)
        
        warning_text = safe_unicode_text("⚠️  WARNING: This will execute REAL trades with REAL money!")
        print(warning_text)
        print(safe_unicode_text("⚠️  Make sure you understand the risks before proceeding!"))
        
        # AUTO-EXECUTE if auto-trading is enabled - NO PROMPTS
        if self.auto_trading:
            self.logger.info("🤖 🔴 LIVE AUTO-TRADING: Executing automatically")
            return True
        
        # Only prompt if manual mode
        prompt = "Execute REAL trade with REAL money? (y/n/q): "
        response = input(prompt).lower().strip()
        return response == 'y'
    
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute the triangular arbitrage trade."""
        # Validate opportunity profitability before execution
        if hasattr(opportunity, 'is_profitable') and not opportunity.is_profitable:
            self.logger.info(f"Skipping unprofitable opportunity: {opportunity.profit_percentage:.4f}%")
            return False
        
        if opportunity.profit_percentage < 0.05:  # Minimum 0.05% profit for execution
            self.logger.info(f"Opportunity skipped: profit {opportunity.profit_percentage:.4f}% below 0.5% threshold")
            return False
        
        # Enforce maximum trade amount
        if opportunity.initial_amount > 100:
            self.logger.warning(f"Trade amount ${opportunity.initial_amount:.2f} exceeds $100 limit, adjusting...")
            opportunity.initial_amount = 100
            
        start_time = datetime.now()
        trade_start_ms = time.time() * 1000
        trade_id = f"trade_{int(trade_start_ms)}_{uuid.uuid4().hex[:8]}"
        
        # Get the appropriate exchange
        exchange_id = getattr(opportunity, 'exchange', None)
        if not exchange_id:
            self.logger.warning("No exchange specified, defaulting to first available exchange")
            available_exchanges = list(self.exchange_manager.exchanges.keys())
            if available_exchanges:
                exchange_id = available_exchanges[0]
                self.logger.info(f"Using exchange: {exchange_id}")
            else:
                self.logger.error("No exchanges available")
                return False
        
        exchange = self.exchange_manager.get_exchange(exchange_id)
        if not exchange:
            self.logger.warning(f"Exchange {exchange_id} not available, trying alternatives...")
            # Try to get any available exchange
            available_exchanges = list(self.exchange_manager.exchanges.keys())
            if available_exchanges:
                exchange_id = available_exchanges[0]
                exchange = self.exchange_manager.get_exchange(exchange_id)
                self.logger.info(f"Using alternative exchange: {exchange_id}")
                # Update opportunity exchange
                if hasattr(opportunity, 'exchange'):
                    opportunity.exchange = exchange_id
            else:
                self.logger.error("No exchanges available for trading")
                return False
        
        # Initialize trade_log at the beginning to avoid scope issues
        trade_log = TradeLog(
            trade_id=trade_id,
            timestamp=start_time,
            exchange=exchange_id,
            triangle_path=opportunity.triangle_path.split(' → ') if isinstance(getattr(opportunity, 'triangle_path', None), str) else getattr(opportunity, 'triangle_path', ['Unknown']),
            status=TradeStatus.SUCCESS,  # Will be updated if failed
            initial_amount=opportunity.initial_amount,
            final_amount=0.0,  # Will be updated
            base_currency=opportunity.base_currency,
            expected_profit_amount=opportunity.profit_amount,
            expected_profit_percentage=opportunity.profit_percentage,
            actual_profit_amount=0.0,  # Will be calculated
            actual_profit_percentage=0.0,  # Will be calculated
            total_fees_paid=0.0,  # Will be accumulated
            total_slippage=0.0,  # Will be calculated
            net_pnl=0.0,  # Will be calculated
            total_duration_ms=0.0  # Will be calculated
        )
        
        try:
            # Request confirmation
            if not await self.request_confirmation(opportunity):
                opportunity.status = OpportunityStatus.EXPIRED
                self.logger.info("Trade execution declined by user")
                return False
            
            opportunity.status = OpportunityStatus.EXECUTING
            self.logger.info(f"Starting execution on {exchange_id}: {opportunity.triangle_path}")
            
            # Verify sufficient balance before starting
            if not await self._verify_sufficient_balance(exchange, opportunity.base_currency, opportunity.initial_amount):
                self.logger.error("❌ Insufficient balance for trade execution")
                opportunity.status = OpportunityStatus.FAILED
                return False
            
            # Log trade attempt
            execution_type = "AUTO" if self.auto_trading else "MANUAL"
            trading_mode = "🔴 LIVE USDT TRIANGLE"
            
            self.trade_logger.info(f"TRADE_ATTEMPT ({execution_type}): {opportunity.to_dict()}")
            self.logger.info(f"Starting {trading_mode} trade execution ({execution_type}): {opportunity.triangle_path}")
            self.logger.info(f"🎯 USDT Triangle: Will execute 3 sequential trades on Binance")
            self.logger.info(f"💰 Expected to turn {opportunity.initial_amount:.2f} USDT into {opportunity.final_amount:.2f} USDT")
            
            # Execute each step with REAL orders
            execution_results = []
            current_balance = opportunity.initial_amount
            order_ids = []  # Track all order IDs for verification
            
            for i, step in enumerate(opportunity.steps):
                try:
                    self.logger.info(f"🔄 EXECUTING USDT TRIANGLE STEP {i+1}/{len(opportunity.steps)} ({trading_mode}/{execution_type})")
                    self.logger.info(f"   Action: {step.side.upper()} {step.quantity:.6f} {step.symbol}")
                    self.logger.info(f"   Expected Price: {step.price:.8f}")
                    self.logger.info(f"🔴 REAL BINANCE ORDER: This will appear in your Spot Orders immediately")
                    
                    # Execute REAL market order
                    result = await self._execute_single_order(exchange, step.symbol, step.side, step.quantity, i+1)
                    
                    execution_results.append(result)
                    
                    if not result.get('success'):
                        raise Exception(f"Order execution failed: {result.get('error', 'Unknown error')}")
                    
                    # Extract execution details
                    order_id = result.get('order_id', 'N/A')
                    filled_qty = result.get('filled_quantity', 0)
                    avg_price = result.get('average_price', step.price)
                    fees_paid = result.get('fee_cost', 0)
                    execution_time_ms = result.get('execution_time_ms', 0)
                    
                    order_ids.append(order_id)
                    
                    # Calculate slippage
                    expected_price = step.price
                    slippage_pct = abs((avg_price - expected_price) / expected_price) * 100 if expected_price > 0 else 0
                    
                    # Log detailed step execution
                    self.logger.info(f"✅ USDT TRIANGLE STEP {i+1} COMPLETED SUCCESSFULLY:")
                    self.logger.info(f"   Order ID: {order_id}")
                    self.logger.info(f"   Filled: {filled_qty:.8f}")
                    self.logger.info(f"   Price: {avg_price:.8f} (expected {expected_price:.8f})")
                    self.logger.info(f"   Fees: {fees_paid:.8f}")
                    self.logger.info(f"   Slippage: {slippage_pct:.4f}%")
                    self.logger.info(f"   Duration: {execution_time_ms:.0f}ms")
                    self.logger.info(f"🔴 BINANCE: Order {order_id} is now visible in your Spot Orders")
                    
                    # Create detailed step log
                    step_log = TradeStepLog(
                        step_number=i + 1,
                        symbol=step.symbol,
                        direction=TradeDirection.BUY if step.side == 'buy' else TradeDirection.SELL,
                        expected_price=expected_price,
                        actual_price=avg_price,
                        expected_quantity=step.quantity,
                        actual_quantity=filled_qty,
                        expected_amount_out=step.expected_amount,
                        actual_amount_out=filled_qty if step.side == 'sell' else filled_qty * avg_price,
                        fees_paid=fees_paid,
                        execution_time_ms=execution_time_ms,
                        slippage_percentage=slippage_pct
                    )
                    
                    trade_log.steps.append(step_log)
                    trade_log.total_fees_paid += fees_paid
                    
                    # Update current balance for next step
                    if step.side == 'sell':
                        current_balance = filled_qty * avg_price  # Got quote currency
                    else:
                        current_balance = filled_qty  # Got base currency
                    
                    self.logger.info(f"   Updated Balance: {current_balance:.8f}")
                        
                except Exception as e:
                    self.logger.error(f"❌ CRITICAL ERROR in USDT triangle step {i+1}: {str(e)}")
                    opportunity.status = OpportunityStatus.FAILED
                    
                    # Update trade log for failure
                    trade_log.status = TradeStatus.FAILED
                    trade_log.error_message = str(e)
                    trade_log.failed_at_step = i + 1
                    trade_log.final_amount = current_balance
                    
                    # Log failed trade
                    self.trade_logger.error(f"TRADE_FAILED ({trading_mode}/{execution_type}): {opportunity.to_dict()} | Error: {str(e)}")
                    
                    # Calculate final metrics and log
                    trade_end_ms = time.time() * 1000
                    trade_log.total_duration_ms = trade_end_ms - trade_start_ms
                    await self.detailed_trade_logger.log_trade(trade_log)
                    
                    return False
            
            # All steps completed successfully
            self.logger.info(f"🎉 ALL USDT TRIANGLE STEPS COMPLETED SUCCESSFULLY!")
            self.logger.info(f"   Order IDs: {', '.join(order_ids)}")
            self.logger.info(f"🔴 BINANCE: Check your Spot Orders for these {len(order_ids)} trades!")
            self.logger.info(f"🔴 BINANCE: All trades are now visible in your Trade History")
            
            # Calculate actual profit
            actual_profit = current_balance - opportunity.initial_amount
            actual_profit_percentage = (actual_profit / opportunity.initial_amount) * 100
            
            opportunity.final_amount = current_balance
            opportunity.profit_amount = actual_profit
            opportunity.profit_percentage = actual_profit_percentage
            opportunity.status = OpportunityStatus.COMPLETED
            opportunity.execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update trade log with final results
            trade_end_ms = time.time() * 1000
            trade_log.final_amount = current_balance
            trade_log.total_duration_ms = trade_end_ms - trade_start_ms
            trade_log.total_slippage = sum(step.slippage_percentage / 100 * step.expected_amount_out for step in trade_log.steps)
            
            # Log final success
            self.logger.info(f"🎉 USDT TRIANGULAR ARBITRAGE TRADE COMPLETED SUCCESSFULLY!")
            self.logger.info(f"   Exchange: {exchange_id}")
            self.logger.info(f"   Trade ID: {trade_id}")
            self.logger.info(f"   Order IDs: {', '.join(order_ids)}")
            self.logger.info(f"   USDT Triangle: {opportunity.triangle_path}")
            self.logger.info(f"   Initial Amount: {opportunity.initial_amount:.8f} {opportunity.base_currency}")
            self.logger.info(f"   Final Amount: {current_balance:.8f} {opportunity.base_currency}")
            self.logger.info(f"   Actual Profit: {actual_profit:.8f} {opportunity.base_currency} ({actual_profit_percentage:.4f}%)")
            self.logger.info(f"   Total Fees: {trade_log.total_fees_paid:.8f}")
            self.logger.info(f"   Net P&L: {actual_profit - trade_log.total_fees_paid:.8f} {opportunity.base_currency}")
            self.logger.info(f"   Execution Time: {trade_log.total_duration_ms:.0f}ms")
            self.logger.info(f"🔴 BINANCE SPOT ORDERS: All {len(order_ids)} trades are now visible in your account!")
            self.logger.info(f"🔴 BINANCE BALANCE: Your USDT balance has been updated with the profit!")
            
            # Log successful trade
            self.trade_logger.info(f"TRADE_SUCCESS ({trading_mode}/{execution_type}): {opportunity.to_dict()}")
            
            # Log detailed trade
            await self.detailed_trade_logger.log_trade(trade_log)
            
            return True
            
        except Exception as e:
            opportunity.status = OpportunityStatus.FAILED
            opportunity.execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update trade log for unexpected failure
            trade_end_ms = time.time() * 1000
            trade_log.status = TradeStatus.FAILED
            trade_log.error_message = str(e)
            trade_log.final_amount = current_balance
            trade_log.total_duration_ms = trade_end_ms - trade_start_ms
            
            await self.detailed_trade_logger.log_trade(trade_log)
            
            execution_type = "AUTO" if self.auto_trading else "MANUAL" 
            trading_mode = "🔴 LIVE"
            self.logger.error(f"❌ ARBITRAGE EXECUTION FAILED on {exchange_id} ({trading_mode}/{execution_type}): {str(e)}")
            self.trade_logger.error(f"TRADE_FAILED ({trading_mode}/{execution_type}): {opportunity.to_dict()} | Error: {str(e)}")
            
            return False