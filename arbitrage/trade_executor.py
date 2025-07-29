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

class TradeExecutor:
    """Executes triangular arbitrage trades across multiple exchanges."""
    
    def __init__(self, exchange_manager: MultiExchangeManager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.config = config
        self.logger = setup_logger('TradeExecutor')
        self.trade_logger = setup_trade_logger()
        self.detailed_trade_logger = get_trade_logger()
        self.auto_trading = config.get('auto_trading', False)
        self.paper_trading = config.get('paper_trading', True)
    
    def set_websocket_manager(self, websocket_manager):
        """Set WebSocket manager for trade broadcasting."""
        self.detailed_trade_logger = get_trade_logger(websocket_manager)
        
    async def request_confirmation(self, opportunity: ArbitrageOpportunity) -> bool:
        """Request manual confirmation for trade execution."""
        if self.auto_trading or not self.config.get('enable_manual_confirmation', True):
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
        print(f"Trading Mode: {'🟡 PAPER TRADING (SIMULATION)' if self.paper_trading else '🔴 LIVE TRADING (REAL MONEY)'}")
        print("\nTrade Steps:")
        for i, step in enumerate(opportunity.steps, 1):
            print(f"  {i}. {step.side.upper()} {step.quantity:.6f} {step.symbol} at {step.price:.8f}")
        print("="*80)
        
        if not self.paper_trading:
            print("⚠️  WARNING: This will execute REAL trades with REAL money!")
            print("⚠️  Make sure you understand the risks before proceeding!")
        
        while True:
            prompt = "Execute this trade? (y/n/q): " if self.paper_trading else "Execute REAL trade with REAL money? (y/n/q): "
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
            self.trade_logger.info(f"TRADE_ATTEMPT: {opportunity.to_dict()}")
            
            # Execute each step
            execution_results = []
            current_balance = opportunity.initial_amount
            
            for i, step in enumerate(opportunity.steps):
                step_start_ms = time.time() * 1000
                try:
                    self.logger.info(f"Executing step {i+1}: {step.side} {step.quantity} {step.symbol}")
                    
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
                    if result.get('status') == 'closed':
                        actual_amount = float(result.get('filled', 0))
                        actual_price = float(result.get('average', step.price))
                        
                        # Calculate fees for this step
                        fees_paid = float(result.get('fee', {}).get('cost', 0))
                        if fees_paid == 0:
                            # Estimate fees if not provided
                            maker_fee, taker_fee = await exchange.get_trading_fees(step.symbol)
                            fees_paid = step.quantity * taker_fee
                        
                        # Calculate slippage
                        expected_price = step.price
                        slippage_pct = abs((actual_price - expected_price) / expected_price) * 100
                        
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
                        
                        self.logger.info(
                            f"Step {i+1} completed: "
                            f"Expected {step.expected_amount:.6f}, "
                            f"Actual: {actual_amount:.6f}, "
                            f"Fees: {fees_paid:.6f}, "
                            f"Slippage: {slippage_pct:.4f}%, "
                            f"Duration: {step_duration_ms:.0f}ms"
                        )
                        
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
                    self.trade_logger.error(f"TRADE_FAILED: {opportunity.to_dict()} | Error: {str(e)}")
                    
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
            
            self.logger.info(
                f"Arbitrage completed successfully on {exchange_id}! "
                f"Actual profit: {actual_profit_percentage:.4f}% "
                f"({actual_profit:.6f} {opportunity.base_currency})"
            )
            
            # Log successful trade
            self.trade_logger.info(f"TRADE_SUCCESS: {opportunity.to_dict()}")
            
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
            
            self.logger.error(f"Arbitrage execution failed on {exchange_id}: {e}")
            self.trade_logger.error(f"TRADE_FAILED: {opportunity.to_dict()} | Error: {str(e)}")
            
            return False