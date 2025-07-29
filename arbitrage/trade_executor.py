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
        # Always check global config for paper trading setting
        self.paper_trading = config.get('paper_trading', Config.PAPER_TRADING)
    
    def set_websocket_manager(self, websocket_manager):
        """Set WebSocket manager for trade broadcasting."""
        self.detailed_trade_logger = get_trade_logger(websocket_manager)
        
    async def request_confirmation(self, opportunity: ArbitrageOpportunity) -> bool:
        """Request manual confirmation for trade execution."""
        # Skip confirmation if auto-trading is enabled
        if self.auto_trading:
            self.logger.info(f"Auto-trading enabled - executing without confirmation")
            return True
            
        # Skip confirmation if manual confirmation is disabled
        if not self.config.get('enable_manual_confirmation', True):
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
        
        # Use global config for paper trading check
        is_paper_trading = Config.PAPER_TRADING
        mode_text = safe_unicode_text('🤖 AUTO-TRADING' if self.auto_trading else '🟡 PAPER TRADING (SIMULATION)' if is_paper_trading else '🔴 LIVE TRADING (REAL MONEY)')
        print(f"Trading Mode: {mode_text}")
        
        print("\nTrade Steps:")
        for i, step in enumerate(opportunity.steps, 1):
            print(f"  {i}. {step.side.upper()} {step.quantity:.6f} {step.symbol} at {step.price:.8f}")
        print("="*80)
        
        if not is_paper_trading:
            warning_text = safe_unicode_text("⚠️  WARNING: This will execute REAL trades with REAL money!")
            print(warning_text)
            print(safe_unicode_text("⚠️  Make sure you understand the risks before proceeding!"))
        
        while True:
            prompt = "Execute this trade? (y/n/q): " if is_paper_trading else "Execute REAL trade with REAL money? (y/n/q): "
            response = input(prompt).lower().strip()
            if response == 'y':
                return True
            elif response == 'n':
                return False
            elif response == 'q':
                print("Quitting...")
                exit(0)
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'q' to quit")
    
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute the triangular arbitrage trade."""
        start_time = datetime.now()
        trade_start_ms = time.time() * 1000
        trade_id = f"trade_{int(trade_start_ms)}_{uuid.uuid4().hex[:8]}"
        
        # Get the appropriate exchange
        exchange_id = getattr(opportunity, 'exchange', None)
        if not exchange_id:
            self.logger.error("No exchange specified for opportunity")
            return False
        
        exchange = self.exchange_manager.get_exchange(exchange_id)
        if not exchange:
            self.logger.error(f"Exchange {exchange_id} not available")
            return False
        
        try:
            # Request confirmation
            if not await self.request_confirmation(opportunity):
                opportunity.status = OpportunityStatus.EXPIRED
                self.logger.info("Trade execution declined by user")
                return False
            
            opportunity.status = OpportunityStatus.EXECUTING
            self.logger.info(f"Starting execution on {exchange_id}: {opportunity.triangle_path}")
            
            # Initialize trade log
            trade_log = TradeLog(
                trade_id=trade_id,
                timestamp=start_time,
                exchange=exchange_id,
                triangle_path=opportunity.triangle_path.split(' → '),
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
            
            # Log trade attempt
            execution_type = "AUTO" if self.auto_trading else "MANUAL"
            trading_mode = "PAPER" if Config.PAPER_TRADING else "LIVE"
            
            self.trade_logger.info(f"TRADE_ATTEMPT ({execution_type}): {opportunity.to_dict()}")
            self.logger.info(f"Starting {trading_mode} trade execution ({execution_type}): {opportunity.triangle_path}")
            
            # Execute each step
            execution_results = []
            current_balance = opportunity.initial_amount
            
            for i, step in enumerate(opportunity.steps):
                step_start_ms = time.time() * 1000
                try:
                    self.logger.info(f"Executing step {i+1} ({trading_mode}/{execution_type}): {step.side.upper()} {step.quantity:.6f} {step.symbol}")
                    
                    # Place market order
                    result = await exchange.place_market_order(
                        step.symbol, 
                        step.side, 
                        step.quantity
                    )
                    
                    step_end_ms = time.time() * 1000
                    step_duration_ms = step_end_ms - step_start_ms
                    execution_results.append(result)
                    
                    # Verify execution
                    if result.get('status') == 'failed':
                        raise Exception(f"Order failed: {result.get('error', 'Unknown error')}")
                    
                    if not result:
                        raise Exception("No response from exchange")
                    
                    if result.get('status') == 'closed':
                        actual_amount = float(result.get('filled', 0))
                        actual_price = float(result.get('average', step.price))
                        
                        # Calculate fees for this step
                        fees_paid = float(result.get('fee', {}).get('cost', 0))
                        if fees_paid == 0:
                            # Estimate fees if not provided by exchange
                            maker_fee, taker_fee = await exchange.get_trading_fees(step.symbol)
                            if Config.PAPER_TRADING:
                                # In paper trading, calculate fees on notional value
                                notional_value = step.quantity * step.price if step.side == 'sell' else step.quantity
                                fees_paid = notional_value * taker_fee
                            else:
                                # In live trading, fees should come from exchange response
                                fees_paid = (actual_amount * actual_price * taker_fee) if step.side == 'buy' else (step.quantity * actual_price * taker_fee)
                        
                        # Calculate slippage
                        expected_price = step.price
                        slippage_pct = abs((actual_price - expected_price) / expected_price) * 100
                        
                        # Log detailed step execution
                        step_log_msg = (
                            f"Step {i+1} completed ({trading_mode}/{execution_type}): "
                            f"Expected {step.expected_amount:.6f}, "
                            f"Actual: {actual_amount:.6f}, "
                            f"Price: {actual_price:.8f} (expected {expected_price:.8f}), "
                            f"Fees: {fees_paid:.6f}, "
                            f"Slippage: {slippage_pct:.4f}%, "
                            f"Duration: {step_duration_ms:.0f}ms"
                        )
                        
                        if Config.PAPER_TRADING:
                            self.logger.info(f"PAPER: {step_log_msg}")
                        else:
                            self.logger.info(f"LIVE: {step_log_msg}")
                        
                        # Create detailed step log
                        step_log = TradeStepLog(
                            step_number=i + 1,
                            symbol=step.symbol,
                            direction=TradeDirection.BUY if step.side == 'buy' else TradeDirection.SELL,
                            expected_price=expected_price,
                            actual_price=actual_price,
                            expected_quantity=step.quantity,
                            actual_quantity=actual_amount if step.side == 'sell' else step.quantity,
                            expected_amount_out=step.expected_amount,
                            actual_amount_out=actual_amount,
                            fees_paid=fees_paid,
                            execution_time_ms=step_duration_ms,
                            slippage_percentage=slippage_pct
                        )
                        
                        trade_log.steps.append(step_log)
                        trade_log.total_fees_paid += fees_paid
                        
                        current_balance = actual_amount
                    else:
                        raise Exception(f"Order not filled: {result}")
                        
                except Exception as e:
                    self.logger.error(f"Error executing step {i+1}: {e}")
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
            
            success_msg = (
                f"Arbitrage completed successfully on {exchange_id} ({trading_mode}/{execution_type})! "
                f"Actual profit: {actual_profit_percentage:.4f}% "
                f"({actual_profit:.6f} {opportunity.base_currency})"
            )
            
            if Config.PAPER_TRADING:
                self.logger.info(f"PAPER: {success_msg}")
            else:
                self.logger.info(f"LIVE: {success_msg}")
            
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
            trading_mode = "PAPER" if Config.PAPER_TRADING else "LIVE"
            self.logger.error(f"Arbitrage execution failed on {exchange_id} ({trading_mode}/{execution_type}): {e}")
            self.trade_logger.error(f"TRADE_FAILED ({trading_mode}/{execution_type}): {opportunity.to_dict()} | Error: {str(e)}")
            
            return False