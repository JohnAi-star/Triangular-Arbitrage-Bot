"""
Trade executor for triangular arbitrage opportunities with dynamic market analysis.
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from models.arbitrage_opportunity import ArbitrageOpportunity, OpportunityStatus
from models.trade_log import TradeLog, TradeStepLog, TradeStatus, TradeDirection
from utils.logger import setup_logger
from utils.trade_logger import get_trade_logger

class TradeExecutor:
    """Executes triangular arbitrage trades with dynamic market analysis and adaptive timing."""
    
    def __init__(self, exchange_manager, config: Dict[str, Any]):
        self.exchange_manager = exchange_manager
        self.config = config
        self.logger = setup_logger('TradeExecutor')
        self.trade_logger = get_trade_logger()
        self.websocket_manager = None
        
        # Trading configuration
        self.auto_trading = config.get('auto_trading', False)
        self.paper_trading = False  # ALWAYS LIVE TRADING
        self.enable_manual_confirmation = config.get('enable_manual_confirmation', False)
        self.min_profit_threshold = config.get('min_profit_threshold', 0.4)
        
        # Dynamic execution settings
        self.use_dynamic_execution = True
        self.dynamic_monitoring_enabled = True
        self.adaptive_waiting_enabled = True
        
        # Execution tracking
        self.active_trades = {}
        self.trade_history = []
        
        self.logger.info(f"🚀 TradeExecutor initialized")
        self.logger.info(f"   Auto Trading: {self.auto_trading}")
        self.logger.info(f"   Paper Trading: {self.paper_trading}")
        self.logger.info(f"   Min Profit Threshold: {self.min_profit_threshold}%")
        self.logger.info(f"   Dynamic Execution: {self.use_dynamic_execution}")
        self.logger.info(f"   Adaptive Waiting: {self.adaptive_waiting_enabled}")
    
    def set_websocket_manager(self, websocket_manager):
        """Set WebSocket manager for real-time updates"""
        self.websocket_manager = websocket_manager
        if self.trade_logger:
            self.trade_logger.websocket_manager = websocket_manager
        self.logger.info("✅ WebSocket manager set for trade executor")
    
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute triangular arbitrage with dynamic market analysis."""
        trade_id = f"trade_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Get exchange instance
            exchange_name = getattr(opportunity, 'exchange', 'kucoin')
            exchange = self.exchange_manager.get_exchange(exchange_name)
            
            if not exchange:
                self.logger.error(f"❌ Exchange {exchange_name} not available")
                return False
            
            # Store exchange reference for dynamic analysis
            self.exchange = exchange
            
            # Validate opportunity
            if not self._validate_opportunity(opportunity):
                return False
            
            # Check if another trade is running (sequential execution)
            if self.active_trades:
                self.logger.warning(f"🔄 SEQUENTIAL MODE: Trade {trade_id} waiting (another trade in progress)")
                return False
            
            # Mark trade as active
            self.active_trades[trade_id] = {
                'opportunity': opportunity,
                'start_time': time.time(),
                'status': 'executing'
            }
            
            self.logger.info(f"🔄 SEQUENTIAL MODE: Trade {trade_id} executing (no concurrent trades)")
            
            # Log trade attempt
            await self._log_trade_attempt(opportunity, trade_id)
            
            # Disable WebSocket during execution for maximum speed
            if self.websocket_manager and hasattr(self.websocket_manager, 'running'):
                self.logger.info("🚀 DYNAMIC MODE: Disabling WebSocket for maximum speed")
                self.websocket_manager.running = False
            
            # Execute with dynamic strategy
            success = await self._execute_dynamic_triangle_trade(opportunity, trade_id, exchange)
            
            # Re-enable WebSocket after execution
            if self.websocket_manager and hasattr(self.websocket_manager, 'running'):
                self.websocket_manager.running = True
                self.logger.info("🔄 WebSocket re-enabled after trade execution")
            
            # Remove from active trades
            if trade_id in self.active_trades:
                del self.active_trades[trade_id]
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Critical error in arbitrage execution: {e}")
            
            # Cleanup
            if trade_id in self.active_trades:
                del self.active_trades[trade_id]
            
            # Re-enable WebSocket on error
            if self.websocket_manager and hasattr(self.websocket_manager, 'running'):
                self.websocket_manager.running = True
                self.logger.info("🔄 WebSocket re-enabled after error")
            
            return False
    
    async def _execute_dynamic_triangle_trade(self, opportunity: ArbitrageOpportunity, trade_id: str, exchange) -> bool:
        """Execute triangular arbitrage with dynamic 2-step strategy."""
        try:
            self.logger.info(f"⚡ DYNAMIC 2-STEP EXECUTION: {exchange.exchange_id} {opportunity.triangle_path}")
            
            # Extract triangle components
            triangle_path = self._parse_triangle_path(opportunity.triangle_path)
            if len(triangle_path) < 3:
                self.logger.error(f"❌ Invalid triangle path: {opportunity.triangle_path}")
                return False
            
            base_currency = triangle_path[0]      # USDT
            intermediate_currency = triangle_path[1]  # e.g., TWT
            quote_currency = triangle_path[2]     # e.g., BTC
            
            # Validate USDT triangle
            if base_currency != 'USDT':
                self.logger.error(f"❌ Only USDT triangles supported: {triangle_path}")
                return False
            
            self.logger.info(f"🔧 2-STEP EXECUTION: {base_currency} → {intermediate_currency} → {quote_currency} → {base_currency}")
            
            # Get initial balance
            initial_balance = await exchange.get_account_balance()
            initial_usdt = initial_balance.get('USDT', 0)
            
            # Trade amounts
            trade_amount = min(20.0, opportunity.initial_amount)  # Max $20 for safety
            
            # CRITICAL FIX: Validate and correct pair directions for KuCoin
            step1_pair, step2_pair, step3_pair = await self._get_correct_pair_directions(
                exchange, base_currency, intermediate_currency, quote_currency
            )
            
            if not all([step1_pair, step2_pair, step3_pair]):
                self.logger.error(f"❌ Cannot find valid trading pairs for triangle")
                return False
            
            self.logger.info(f"✅ Validated pairs: {step1_pair}, {step2_pair}, {step3_pair}")
            
            step1_filled = 0.0
            step2_received = 0.0
            step2_cost = 0.0
            
            # Step 1: USDT → Intermediate Currency (e.g., USDT → TWT)
            self.logger.info(f"🔧 Step 1: Spending {trade_amount:.2f} USDT to buy {intermediate_currency}")
            
            step1_result = await exchange.place_market_order(
                f"{intermediate_currency}/USDT", 'buy', trade_amount
            )
            
            if not step1_result.get('success'):
                self.logger.error(f"❌ Step 1 failed: {step1_result.get('error', 'Unknown error')}")
                await self._log_failed_trade(opportunity, trade_id, 1, step1_result.get('error', 'Step 1 failed'))
                return False
            
            step1_filled = float(step1_result.get('filled', 0))
            pair1 = step1_pair
            step1_duration = time.time() - self.active_trades[trade_id]['start_time']
            
            self.logger.info(f"✅ Step 1: Received {step1_filled:.8f} {intermediate_currency}")
            self.logger.info(f"⚡ Step 1 completed in {step1_duration*1000:.0f}ms")
            
            if step1_filled <= 0:
                self.logger.error(f"❌ Step 1: No {intermediate_currency} received")
                await self._log_failed_trade(opportunity, trade_id, 1, "No intermediate currency received")
                return False
            
            # Brief pause between steps
            await asyncio.sleep(0.1)
            
            # Execute Step 2
            step2_start = time.time()
            pair2 = step2_pair
            step2_side = await self._get_step2_side(exchange, step2_pair, intermediate_currency, quote_currency)

            # CRITICAL FIX: Calculate correct amount based on trade direction
            if step2_side == 'sell':
                # SELL: We're selling intermediate currency, amount is in intermediate
                amount_intermediate = step1_filled
                self.logger.info(f"🔧 Step 2: Selling {step1_filled:.8f} {intermediate_currency} for {quote_currency}")
                self.logger.info(f"⚡ Step 2: SELL {pair2} (amount in {intermediate_currency})")
            else:
                # BUY: We're buying the base of the pair with our intermediate currency
                # For RLC/BTC pair, we want to BUY RLC using our BTC
                # Amount needs to be in BTC (quote currency of the pair)
                amount_intermediate = step1_filled
                self.logger.info(f"🔧 Step 2: Using {step1_filled:.8f} {intermediate_currency} to buy {quote_currency}")
                self.logger.info(f"⚡ Step 2: BUY {pair2} (spending {intermediate_currency})")

            step2_result = await exchange.place_market_order(step2_pair, step2_side, amount_intermediate)
            
            if not step2_result.get('success'):
                self.logger.error(f"❌ Step 2 failed: {step2_result.get('error', 'Unknown error')}")
                await self._log_failed_trade(opportunity, trade_id, 2, step2_result.get('error', 'Step 2 failed'))
                return False
            
            # CRITICAL FIX: Use the ACTUAL amount received from Step 2
            step2_received = float(step2_result.get('filled', 0))
            step2_cost = float(step2_result.get('cost', 0))
            
            # CRITICAL FIX: For KuCoin, 'filled' returns the INPUT amount (LRC), 'cost' returns OUTPUT amount (BTC)
            if exchange.exchange_id == 'kucoin':
                # KuCoin: 'cost' field contains the BTC amount we received
                actual_quote_amount = step2_cost
                self.logger.info(f"🔧 KuCoin Step 2 amounts: filled={step2_received:.8f} {intermediate_currency}, cost={step2_cost:.8f} {quote_currency}")
            else:
                # Other exchanges: use filled amount
                actual_quote_amount = step2_received if step2_received > 0 else step2_cost
            
            step2_duration = time.time() - step2_start
            
            self.logger.info(f"✅ Step 2: Sold {step1_filled:.8f} {intermediate_currency}, received {actual_quote_amount:.8f} {quote_currency}")
            self.logger.info(f"⚡ Step 2 completed in {step2_duration*1000:.0f}ms")
            
            if actual_quote_amount <= 0:
                self.logger.error(f"❌ Step 2: No {quote_currency} received")
                await self._log_failed_trade(opportunity, trade_id, 2, f"No {quote_currency} received")
                return False
            
            # CRITICAL: Validate the BTC amount is realistic
            if quote_currency == 'BTC' and actual_quote_amount > 0.01:
                self.logger.error(f"❌ CRITICAL: Unrealistic BTC amount: {actual_quote_amount:.8f} BTC")
                self.logger.error(f"   This would be worth ${actual_quote_amount * 115000:.2f} USD!")
                self.logger.error(f"   Expected range: 0.0001-0.001 BTC for $20 trade")
                await self._log_failed_trade(opportunity, trade_id, 2, f"Unrealistic {quote_currency} amount: {actual_quote_amount}")
                return False
            
            # Dynamic Market Analysis for Step 3 timing
            self.logger.info("🧠 DYNAMIC MONITORING: Analyzing market trend for adaptive waiting strategy")
            
            try:
                # CRITICAL FIX: Check if opportunity has high profit potential
                expected_profit_pct = getattr(opportunity, 'profit_percentage', 0)
                
                if expected_profit_pct >= 0.8:  # High profit opportunities (≥0.8%)
                    self.logger.info(f"🚀 HIGH PROFIT OPPORTUNITY: {expected_profit_pct:.4f}% - EXECUTING IMMEDIATELY!")
                    self.logger.info("⚡ INSTANT EXECUTION: No waiting - capturing profit before price moves")
                    
                    # Execute Step 3 immediately for high-profit opportunities
                    step3_success = await self._execute_step3_immediate(
                        exchange, quote_currency, base_currency, actual_quote_amount, trade_id, opportunity
                    )
                    
                    if step3_success:
                        await self._log_successful_trade(opportunity, trade_id, trade_amount)
                        return True
                    else:
                        await self._log_failed_trade(opportunity, trade_id, 3, "Step 3 execution failed")
                        return False
                
                elif expected_profit_pct >= 0.5:  # Medium profit opportunities (0.5-0.8%)
                    self.logger.info(f"💎 MEDIUM PROFIT OPPORTUNITY: {expected_profit_pct:.4f}% - FAST EXECUTION!")
                    self.logger.info("⚡ FAST MODE: 2-minute maximum wait to secure profits")
                    
                    # Fast execution with minimal waiting
                    waiting_params = {
                        'trend': 'FAST_PROFIT',
                        'wait_time': 120.0,  # 2 minutes maximum
                        'profit_target': 0.08,  # +0.08% quick target
                        'stop_loss': -0.15,     # -0.15% tight stop
                        'confidence': 0.9,
                        'pair_type': 'fast_execution'
                    }
                    
                    step3_success = await self._execute_step3_with_adaptive_waiting(
                        exchange, quote_currency, base_currency, actual_quote_amount, 
                        waiting_params, trade_id
                    )
                    
                    if step3_success:
                        await self._log_successful_trade(opportunity, trade_id, trade_amount)
                        return True
                    else:
                        await self._log_failed_trade(opportunity, trade_id, 3, "Step 3 execution failed")
                        return False
                
                else:  # Lower profit opportunities (0.4-0.5%)
                    # Get dynamic waiting parameters with null safety
                    waiting_params = await self._get_dynamic_waiting_params_safe(exchange, quote_currency, base_currency)
                    
                    if waiting_params:
                        market_trend = waiting_params['trend']
                        wait_time = waiting_params['wait_time']
                        profit_target = waiting_params['profit_target']
                        stop_loss = waiting_params['stop_loss']
                        
                        self.logger.info(f"🎯 DYNAMIC STRATEGY: {market_trend} market detected")
                        self.logger.info(f"   Wait Time: {wait_time}s")
                        self.logger.info(f"   Profit Target: +{profit_target:.2f}%")
                        self.logger.info(f"   Stop Loss: {stop_loss:.2f}%")
                        
                        # Execute Step 3 with adaptive waiting
                        step3_success = await self._execute_step3_with_adaptive_waiting(
                            exchange, quote_currency, base_currency, actual_quote_amount, 
                            waiting_params, trade_id
                        )
                        
                        if step3_success:
                            await self._log_successful_trade(opportunity, trade_id, trade_amount)
                            return True
                        else:
                            await self._log_failed_trade(opportunity, trade_id, 3, "Step 3 execution failed")
                            return False
                    else:
                        # Fallback to immediate execution
                        self.logger.warning("⚠️ Dynamic analysis failed, executing Step 3 immediately")
                        return await self._execute_step3_immediate(
                            exchange, quote_currency, base_currency, actual_quote_amount, trade_id, opportunity
                        )
                    
            except Exception as dynamic_error:
                self.logger.error(f"❌ Dynamic analysis error: {dynamic_error}")
                self.logger.info("🔄 Falling back to immediate Step 3 execution")
                
                return await self._execute_step3_immediate(
                    exchange, quote_currency, base_currency, actual_quote_amount, trade_id, opportunity
                )
                
        except Exception as e:
            self.logger.error(f"❌ Critical error in dynamic triangle trade: {e}")
            await self._log_failed_trade(opportunity, trade_id, 0, str(e))
            return False
    
    async def _get_correct_pair_directions(self, exchange, base: str, intermediate: str, quote: str) -> tuple:
        """Get correct trading pair directions for the exchange"""
        try:
            # Get available trading pairs
            trading_pairs = await exchange.get_trading_pairs()
            
            # Step 1: USDT → intermediate (always buy intermediate with USDT)
            step1_options = [f"{intermediate}/USDT", f"USDT/{intermediate}"]
            step1_pair = None
            for option in step1_options:
                if option in trading_pairs:
                    step1_pair = option
                    break
            
            # Step 2: intermediate → quote (can be either direction)
            step2_options = [f"{intermediate}/{quote}", f"{quote}/{intermediate}"]
            step2_pair = None
            for option in step2_options:
                if option in trading_pairs:
                    step2_pair = option
                    break
            
            # Step 3: quote → USDT (always sell quote for USDT)
            step3_options = [f"{quote}/USDT", f"USDT/{quote}"]
            step3_pair = None
            for option in step3_options:
                if option in trading_pairs:
                    step3_pair = option
                    break
            
            self.logger.info(f"🔍 Pair validation for {exchange.exchange_id}:")
            self.logger.info(f"   Step 1: {step1_pair} (from {step1_options})")
            self.logger.info(f"   Step 2: {step2_pair} (from {step2_options})")
            self.logger.info(f"   Step 3: {step3_pair} (from {step3_options})")
            
            return step1_pair, step2_pair, step3_pair
            
        except Exception as e:
            self.logger.error(f"Error getting correct pair directions: {e}")
            return None, None, None
    
    async def _get_step2_side(self, exchange, pair: str, intermediate: str, quote: str) -> str:
        """Determine the correct side (buy/sell) for Step 2

        Step 2: We have INTERMEDIATE currency, need to get QUOTE currency

        Examples:
        - USDT → BTC → RLC: We have BTC, need RLC
          - If pair is RLC/BTC: BUY RLC with BTC
          - If pair is BTC/RLC: SELL BTC for RLC

        - USDT → SCRT → BTC: We have SCRT, need BTC
          - If pair is BTC/SCRT: BUY BTC with SCRT
          - If pair is SCRT/BTC: SELL SCRT for BTC
        """
        try:
            # Split the pair to understand structure
            base, quote_part = pair.split('/')

            # We HAVE intermediate, we NEED quote
            # If intermediate is BASE of pair: We SELL intermediate for quote_part
            # If intermediate is QUOTE of pair: We BUY base with intermediate

            if base == intermediate:
                # Pair is INTERMEDIATE/QUOTE (e.g., BTC/RLC)
                # We have BTC (intermediate), selling it for RLC (quote)
                return 'sell'
            elif quote_part == intermediate:
                # Pair is QUOTE/INTERMEDIATE (e.g., RLC/BTC)
                # We have BTC (intermediate), buying RLC (quote) with it
                return 'buy'
            else:
                # Fallback - should not happen
                self.logger.warning(f"⚠️ Unexpected pair structure: {pair}, intermediate={intermediate}, quote={quote}")
                return 'sell'

        except Exception as e:
            self.logger.error(f"Error determining step2 side: {e}")
            return 'sell'
    
    async def _get_dynamic_waiting_params_safe(self, exchange, quote_currency: str, base_currency: str) -> Optional[Dict[str, Any]]:
        """Safely get dynamic waiting parameters with null checking and fallback."""
        try:
            # Check if exchange exists
            if not exchange:
                self.logger.warning("⚠️ Exchange object is None, using fallback parameters")
                return self._get_fallback_dynamic_params()
            
            # Check if exchange has the dynamic method
            if hasattr(exchange, 'get_dynamic_waiting_params'):
                try:
                    return await exchange.get_dynamic_waiting_params(quote_currency, base_currency)
                except Exception as e:
                    self.logger.warning(f"⚠️ Exchange dynamic method failed: {e}")
                    return self._get_fallback_dynamic_params()
            else:
                # Exchange doesn't have dynamic method, create our own analysis
                return await self._create_dynamic_params_from_market_data(exchange, quote_currency, base_currency)
                
        except Exception as e:
            self.logger.error(f"❌ Error getting dynamic waiting params: {e}")
            return self._get_fallback_dynamic_params()
    
    def _get_fallback_dynamic_params(self) -> Dict[str, Any]:
        """Get fallback dynamic parameters when analysis fails."""
        return {
            'trend': 'UNKNOWN',
            'wait_time': 60.0,   # 1 minute (very fast fallback)
            'profit_target': 0.05,  # +0.05% very quick target
            'stop_loss': -0.10,     # -0.10% very tight stop loss
            'confidence': 0.5
        }
    
    async def _create_dynamic_params_from_market_data(self, exchange, quote_currency: str, base_currency: str) -> Dict[str, Any]:
        """Create dynamic parameters from current market data."""
        try:
            # Get pair-specific optimization
            pair_symbol = f"{quote_currency}/{base_currency}"
            is_stablecoin_pair = self._is_stablecoin_pair(pair_symbol)
            
            # Get current ticker for trend analysis
            ticker = await exchange.get_ticker(pair_symbol)
            
            if ticker and ticker.get('last'):
                current_price = float(ticker['last'])
                
                # Simple trend analysis based on bid/ask spread
                bid = float(ticker.get('bid', 0))
                ask = float(ticker.get('ask', 0))
                
                if bid > 0 and ask > 0:
                    spread = (ask - bid) / bid * 100
                    
                    if spread < 0.05:  # Tight spread = bullish market
                        if is_stablecoin_pair:
                            # Stablecoin pairs: faster execution with smaller targets
                            return {
                                'trend': 'BULLISH_STABLE',
                                'wait_time': 300.0,  # 5 minutes for stablecoins (faster)
                                'profit_target': 0.08,  # +0.08% target (very achievable)
                                'stop_loss': -0.12,     # -0.12% very tight stop loss
                                'confidence': 0.9,
                                'pair_type': 'stablecoin'
                            }
                        else:
                            # Regular pairs: optimized bullish strategy
                            return {
                                'trend': 'BULLISH',
                                'wait_time': 360.0,  # 6 minutes (much faster)
                                'profit_target': 0.10,  # +0.10% target (very achievable)
                                'stop_loss': -0.15,     # -0.15% tight stop loss
                                'confidence': 0.85,
                                'pair_type': 'volatile'
                            }
                    elif spread > 0.2:  # Wide spread = volatile/bearish market
                        if is_stablecoin_pair:
                            # Stablecoin pairs: quick exit in volatile conditions
                            return {
                                'trend': 'BEARISH_STABLE',
                                'wait_time': 60.0,    # 1 minute (very fast exit)
                                'profit_target': 0.04,  # +0.04% very quick target
                                'stop_loss': -0.08,     # -0.08% very tight stop loss
                                'confidence': 0.7,
                                'pair_type': 'stablecoin'
                            }
                        else:
                            # Regular pairs: quick execution in volatile markets
                            return {
                                'trend': 'BEARISH',
                                'wait_time': 90.0,    # 1.5 minutes (fast exit)
                                'profit_target': 0.06,  # +0.06% quick target
                                'stop_loss': -0.15,     # -0.15% tight stop loss
                                'confidence': 0.75,
                                'pair_type': 'volatile'
                            }
                    else:  # Medium spread = sideways market
                        if is_stablecoin_pair:
                            # Stablecoin pairs: moderate strategy
                            return {
                                'trend': 'SIDEWAYS_STABLE',
                                'wait_time': 240.0,  # 4 minutes (faster)
                                'profit_target': 0.06,  # +0.06% target (very achievable)
                                'stop_loss': -0.10,     # -0.10% very tight stop loss
                                'confidence': 0.8,
                                'pair_type': 'stablecoin'
                            }
                        else:
                            # Regular pairs: balanced sideways strategy
                            return {
                                'trend': 'SIDEWAYS',
                                'wait_time': 300.0,  # 5 minutes (faster)
                                'profit_target': 0.08,  # +0.08% target (very achievable)
                                'stop_loss': -0.12,     # -0.12% very tight stop loss
                                'confidence': 0.75,
                                'pair_type': 'volatile'
                            }
            
            # Fallback if no market data
            return self._get_fallback_dynamic_params()
            
        except Exception as e:
            self.logger.error(f"❌ Error creating dynamic params from market data: {e}")
            return self._get_fallback_dynamic_params()
    
    def _is_stablecoin_pair(self, pair_symbol: str) -> bool:
        """Check if pair involves stablecoins for optimized handling."""
        stablecoins = {'USDT', 'USDC', 'BUSD', 'TUSD', 'DAI', 'FDUSD', 'USDD'}
        try:
            base, quote = pair_symbol.split('/')
            return base in stablecoins and quote in stablecoins
        except:
            return False
    
    async def _execute_step3_with_adaptive_waiting(self, exchange, quote_currency: str, base_currency: str, 
                                                 quote_amount: float, waiting_params: Dict[str, Any], trade_id: str) -> bool:
        """Execute Step 3 with adaptive waiting based on market conditions."""
        try:
            pair_symbol = f"{quote_currency}/{base_currency}"
            trend = waiting_params['trend']
            wait_time = waiting_params['wait_time']
            profit_target = waiting_params['profit_target']
            stop_loss = waiting_params['stop_loss']
            pair_type = waiting_params.get('pair_type', 'volatile')
            
            self.logger.info(f"🎯 PROFIT-OPTIMIZED ADAPTIVE WAITING: {trend} strategy for {wait_time}s ({pair_type} pair)")
            
            # Get initial price for monitoring
            initial_ticker = await exchange.get_ticker(pair_symbol)
            if not initial_ticker or not initial_ticker.get('last'):
                self.logger.warning("⚠️ Cannot get initial price, executing immediately")
                return await self._execute_step3_immediate_with_amount(exchange, quote_currency, base_currency, quote_amount, trade_id)
            
            initial_price = float(initial_ticker['last'])
            target_price = initial_price * (1 + profit_target / 100)
            stop_price = initial_price * (1 + stop_loss / 100)
            
            # CRITICAL FIX: Correct trailing stop initialization
            trailing_stop_enabled = False
            trailing_stop_price = stop_price  # Start with regular stop loss
            best_price_seen = initial_price
            
            self.logger.info(f"📊 Starting ULTRA-FAST adaptive wait: Initial price {initial_price:.8f}")
            self.logger.info(f"   Target price: {target_price:.8f} (+{profit_target:.2f}%)")
            self.logger.info(f"   Stop price: {stop_price:.8f} ({stop_loss:.2f}%)")
            self.logger.info(f"   Pair type: {pair_type}")
            self.logger.info(f"   Trailing stop: Enabled after +0.05% move (ultra-fast)")
            
            # Adaptive waiting loop
            wait_start = time.time()
            check_interval = 1.0  # Check every 1 second (ultra-fast monitoring)
            last_log_time = 0
            
            while time.time() - wait_start < wait_time:
                try:
                    # Get current price
                    current_ticker = await exchange.get_ticker(pair_symbol)
                    if current_ticker and current_ticker.get('last'):
                        current_price = float(current_ticker['last'])
                        
                        # Update best price seen for trailing stop
                        if current_price > best_price_seen:
                            best_price_seen = current_price
                            
                            # CRITICAL FIX: Enable trailing stop after +0.05% move
                            if not trailing_stop_enabled and current_price >= initial_price * 1.0005:  # +0.05%
                                trailing_stop_enabled = True
                                # CRITICAL FIX: Trail stop should be BELOW best price
                                trailing_stop_price = best_price_seen * 0.9992  # Trail 0.08% below best price
                                self.logger.info(f"🔒 ULTRA-FAST TRAILING STOP ENABLED: {trailing_stop_price:.8f} (0.08% below best {best_price_seen:.8f})")
                            
                            # CRITICAL FIX: Update trailing stop to always be 0.08% below best price
                            elif trailing_stop_enabled:
                                new_trailing_stop = best_price_seen * 0.9992  # Always 0.08% below best
                                if new_trailing_stop > trailing_stop_price:  # Only move stop up, never down
                                    trailing_stop_price = new_trailing_stop
                                    self.logger.info(f"🔒 ULTRA-FAST TRAILING STOP UPDATED: {trailing_stop_price:.8f}")
                        
                        # Check profit target reached
                        if current_price >= target_price:
                            price_change = (current_price - initial_price) / initial_price * 100
                            self.logger.info(f"🎯 ULTRA-FAST PROFIT TARGET ACHIEVED: {current_price:.8f} ≥ {target_price:.8f} (+{price_change:.3f}%)")
                            break
                        
                        # CRITICAL FIX: Check trailing stop triggered (if enabled)
                        if trailing_stop_enabled and current_price <= trailing_stop_price:
                            price_change = (current_price - initial_price) / initial_price * 100
                            best_change = (best_price_seen - initial_price) / initial_price * 100
                            self.logger.info(f"🔒 ULTRA-FAST TRAILING STOP TRIGGERED: {current_price:.8f} ≤ {trailing_stop_price:.8f}")
                            self.logger.info(f"   Best was: {best_price_seen:.8f} (+{best_change:.3f}%), Locked: {price_change:.3f}%")
                            break
                        
                        # Check regular stop loss triggered
                        elif current_price <= stop_price:
                            price_change = (current_price - initial_price) / initial_price * 100
                            self.logger.warning(f"🛑 ULTRA-FAST LOSS PROTECTION: {current_price:.8f} ≤ {stop_price:.8f} ({price_change:.3f}%)")
                            break
                        
                        # Log progress every 30 seconds (ultra-fast updates)
                        elapsed = time.time() - wait_start
                        if elapsed - last_log_time >= 30:
                            price_change = (current_price - initial_price) / initial_price * 100
                            best_change = (best_price_seen - initial_price) / initial_price * 100
                            self.logger.info(f"⏰ ULTRA-FAST PROFIT-SEEKING Wait... {elapsed:.0f}s | Price: {current_price:.8f} ({price_change:+.3f}%) | Best: {best_price_seen:.8f} (+{best_change:.3f}%)")
                            if trailing_stop_enabled:
                                self.logger.info(f"   🔒 Ultra-fast trailing stop: {trailing_stop_price:.8f}")
                            last_log_time = elapsed
                    
                    await asyncio.sleep(check_interval)
                    
                except Exception as monitor_error:
                    self.logger.warning(f"⚠️ Monitoring error: {monitor_error}")
                    await asyncio.sleep(check_interval)
            
            elapsed_time = time.time() - wait_start
            final_price_change = (best_price_seen - initial_price) / initial_price * 100 if best_price_seen > initial_price else 0
            self.logger.info(f"⏰ ULTRA-FAST adaptive waiting completed after {elapsed_time:.1f}s")
            self.logger.info(f"   📊 Best price seen: {best_price_seen:.8f} (+{final_price_change:.3f}%)")
            if trailing_stop_enabled:
                self.logger.info(f"   🔒 Final ultra-fast trailing stop: {trailing_stop_price:.8f}")
            
            # Execute Step 3 with the CORRECT amount
            return await self._execute_step3_immediate_with_amount(exchange, quote_currency, base_currency, quote_amount, trade_id)
            
        except Exception as e:
            self.logger.error(f"❌ Error in adaptive waiting: {e}")
            return await self._execute_step3_immediate_with_amount(exchange, quote_currency, base_currency, quote_amount, trade_id)
    
    async def _execute_step3_immediate_with_amount(self, exchange, quote_currency: str, base_currency: str, 
                                                 quote_amount: float, trade_id: str) -> bool:
        """Execute Step 3 immediately with the correct amount."""
        try:
            pair_symbol = f"{quote_currency}/{base_currency}"
            
            # CRITICAL FIX: Use the ACTUAL quote amount received from Step 2
            self.logger.info(f"⚡ ULTRA-FAST Step 3: Selling {quote_amount:.8f} {quote_currency} for {base_currency}")
            
            # Validate amount is realistic
            if quote_currency == 'BTC' and quote_amount > 0.01:
                self.logger.error(f"❌ CRITICAL: Trying to sell unrealistic BTC amount: {quote_amount:.8f}")
                self.logger.error(f"   This would be worth ${quote_amount * 115000:.2f} USD!")
                return False
            
            # Get current market price for better execution timing
            current_ticker = await exchange.get_ticker(pair_symbol)
            if current_ticker and current_ticker.get('bid'):
                current_bid = float(current_ticker['bid'])
                self.logger.info(f"📊 ULTRA-FAST market bid: {current_bid:.8f} (executing immediately)")
            
            step3_result = await exchange.place_market_order(pair_symbol, 'sell', quote_amount)
            
            if not step3_result.get('success'):
                self.logger.error(f"❌ Step 3 failed: {step3_result.get('error', 'Unknown error')}")
                return False
            
            final_usdt = float(step3_result.get('cost', 0))
            self.logger.info(f"✅ ULTRA-FAST Step 3: Received {final_usdt:.8f} {base_currency}")
            
            # Calculate actual profit
            trade_amount = 20.0  # Original trade amount
            actual_profit = final_usdt - trade_amount
            actual_profit_pct = (actual_profit / trade_amount) * 100
            
            self.logger.info(f"💰 ULTRA-FAST DYNAMIC TRADE RESULT:")
            self.logger.info(f"   Initial: {trade_amount:.2f} USDT")
            self.logger.info(f"   Final: {final_usdt:.2f} USDT")
            self.logger.info(f"   Actual Profit: {actual_profit:.6f} USDT ({actual_profit_pct:.4f}%)")
            
            # Success criteria: Ultra-tight tolerance for profitability
            success_threshold = -0.15  # Accept up to -0.15% loss (ultra-tight)
            is_successful = actual_profit_pct > success_threshold
            
            if is_successful:
                if actual_profit > 0:
                    self.logger.info(f"🎉 ULTRA-FAST PROFIT ACHIEVED: +{actual_profit:.6f} USDT (+{actual_profit_pct:.4f}%)")
                else:
                    self.logger.info(f"✅ ULTRA-CONTROLLED LOSS: {actual_profit:.6f} USDT ({actual_profit_pct:.4f}%) - within ultra-tight tolerance")
            else:
                self.logger.warning(f"⚠️ LOSS EXCEEDS ULTRA-TIGHT TOLERANCE: {actual_profit:.6f} USDT ({actual_profit_pct:.4f}%) - exceeds -0.15%")
            
            return is_successful
            
        except Exception as e:
            self.logger.error(f"❌ Error in Step 3 execution: {e}")
            return False
    
    async def _execute_step3_immediate(self, exchange, quote_currency: str, base_currency: str, 
                                     quote_amount: float, trade_id: str, opportunity: ArbitrageOpportunity) -> bool:
        """Execute Step 3 immediately without adaptive waiting."""
        return await self._execute_step3_immediate_with_amount(exchange, quote_currency, base_currency, quote_amount, trade_id)
    
    def _parse_triangle_path(self, triangle_path: str) -> List[str]:
        """Parse triangle path string into currency list."""
        try:
            if isinstance(triangle_path, list):
                return triangle_path[:3]
            
            if isinstance(triangle_path, str):
                # Handle different arrow formats
                if ' → ' in triangle_path:
                    parts = triangle_path.split(' → ')
                elif ' -> ' in triangle_path:
                    parts = triangle_path.split(' -> ')
                else:
                    # Try to extract currencies from string
                    parts = [part.strip() for part in triangle_path.split() if part.strip() not in ['→', '->']]
                
                # For 4-part paths (USDT → TWT → BTC → USDT), take first 3
                if len(parts) >= 3:
                    if len(parts) == 4 and parts[0] == parts[3]:
                        return parts[:3]  # [USDT, TWT, BTC]
                    else:
                        return parts[:3]
                else:
                    return parts
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error parsing triangle path: {e}")
            return []
    
    def _validate_opportunity(self, opportunity: ArbitrageOpportunity) -> bool:
        """Validate arbitrage opportunity before execution."""
        try:
            # Check profit threshold
            profit_pct = getattr(opportunity, 'profit_percentage', 0)
            if profit_pct < self.min_profit_threshold:
                self.logger.warning(f"⚠️ Opportunity below threshold: {profit_pct:.4f}% < {self.min_profit_threshold}%")
                return False
            
            # Check trade amount
            trade_amount = getattr(opportunity, 'initial_amount', 0)
            if trade_amount <= 0 or trade_amount > 20:
                self.logger.warning(f"⚠️ Invalid trade amount: ${trade_amount}")
                return False
            
            # Check triangle path
            triangle_path = getattr(opportunity, 'triangle_path', '')
            if not triangle_path:
                self.logger.warning("⚠️ No triangle path specified")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating opportunity: {e}")
            return False
    
    async def _log_trade_attempt(self, opportunity: ArbitrageOpportunity, trade_id: str):
        """Log trade attempt details."""
        try:
            trade_data = {
                'triangle_path': getattr(opportunity, 'triangle_path', 'Unknown'),
                'pairs': [getattr(step, 'symbol', 'Unknown') for step in getattr(opportunity, 'steps', [])],
                'initial_amount': getattr(opportunity, 'initial_amount', 0),
                'final_amount': getattr(opportunity, 'final_amount', 0),
                'profit_percentage': round(getattr(opportunity, 'profit_percentage', 0), 6),
                'profit_amount': round(getattr(opportunity, 'profit_amount', 0), 6),
                'net_profit': round(getattr(opportunity, 'net_profit', 0), 6),
                'estimated_fees': round(getattr(opportunity, 'estimated_fees', 0), 6),
                'estimated_slippage': round(getattr(opportunity, 'estimated_slippage', 0), 6),
                'steps': [step.to_dict() for step in getattr(opportunity, 'steps', [])],
                'detected_at': getattr(opportunity, 'detected_at', datetime.now()).isoformat(),
                'status': 'executing',
                'execution_time': 0.0,
                'execution_mode': 'DYNAMIC_2-STEP'
            }
            
            self.logger.info(f"TRADE_ATTEMPT (AUTO): {trade_data}")
            
        except Exception as e:
            self.logger.error(f"Error logging trade attempt: {e}")
    
    async def _log_successful_trade(self, opportunity: ArbitrageOpportunity, trade_id: str, final_amount: float):
        """Log successful trade completion."""
        try:
            if self.trade_logger:
                # Create detailed trade log
                trade_log = TradeLog(
                    trade_id=trade_id,
                    timestamp=datetime.now(),
                    exchange=getattr(opportunity, 'exchange', 'kucoin'),
                    triangle_path=self._parse_triangle_path(getattr(opportunity, 'triangle_path', '')),
                    status=TradeStatus.SUCCESS,
                    initial_amount=getattr(opportunity, 'initial_amount', 0),
                    final_amount=final_amount,
                    base_currency='USDT',
                    expected_profit_amount=getattr(opportunity, 'profit_amount', 0),
                    expected_profit_percentage=getattr(opportunity, 'profit_percentage', 0),
                    actual_profit_amount=final_amount - getattr(opportunity, 'initial_amount', 0),
                    actual_profit_percentage=((final_amount - getattr(opportunity, 'initial_amount', 0)) / getattr(opportunity, 'initial_amount', 1)) * 100,
                    total_fees_paid=getattr(opportunity, 'estimated_fees', 0),
                    total_slippage=getattr(opportunity, 'estimated_slippage', 0),
                    net_pnl=final_amount - getattr(opportunity, 'initial_amount', 0) - getattr(opportunity, 'estimated_fees', 0),
                    total_duration_ms=(time.time() - self.active_trades[trade_id]['start_time']) * 1000,
                    steps=[]
                )
                
                await self.trade_logger.log_trade(trade_log)
            
        except Exception as e:
            self.logger.error(f"Error logging successful trade: {e}")
    
    async def _log_failed_trade(self, opportunity: ArbitrageOpportunity, trade_id: str, failed_step: int, error_message: str):
        """Log failed trade with detailed information."""
        try:
            if self.trade_logger:
                # Create detailed trade log for failure
                trade_log = TradeLog(
                    trade_id=trade_id,
                    timestamp=datetime.now(),
                    exchange=getattr(opportunity, 'exchange', 'kucoin'),
                    triangle_path=self._parse_triangle_path(getattr(opportunity, 'triangle_path', '')),
                    status=TradeStatus.FAILED,
                    initial_amount=getattr(opportunity, 'initial_amount', 0),
                    final_amount=0.0,
                    base_currency='USDT',
                    expected_profit_amount=getattr(opportunity, 'profit_amount', 0),
                    expected_profit_percentage=getattr(opportunity, 'profit_percentage', 0),
                    actual_profit_amount=0.0,
                    actual_profit_percentage=0.0,
                    total_fees_paid=getattr(opportunity, 'estimated_fees', 0),
                    total_slippage=0.0,
                    net_pnl=-getattr(opportunity, 'estimated_fees', 0),
                    total_duration_ms=(time.time() - self.active_trades[trade_id]['start_time']) * 1000,
                    steps=[],
                    error_message=error_message,
                    failed_at_step=failed_step
                )
                
                await self.trade_logger.log_trade(trade_log)
            
            # Also log to main logger
            trade_data = {
                'triangle_path': getattr(opportunity, 'triangle_path', 'Unknown'),
                'pairs': [getattr(step, 'symbol', 'Unknown') for step in getattr(opportunity, 'steps', [])],
                'initial_amount': getattr(opportunity, 'initial_amount', 0),
                'final_amount': getattr(opportunity, 'final_amount', 0),
                'profit_percentage': round(getattr(opportunity, 'profit_percentage', 0), 6),
                'profit_amount': round(getattr(opportunity, 'profit_amount', 0), 6),
                'net_profit': round(getattr(opportunity, 'net_profit', 0), 6),
                'estimated_fees': round(getattr(opportunity, 'estimated_fees', 0), 6),
                'estimated_slippage': round(getattr(opportunity, 'estimated_slippage', 0), 6),
                'steps': [step.to_dict() for step in getattr(opportunity, 'steps', [])],
                'detected_at': getattr(opportunity, 'detected_at', datetime.now()).isoformat(),
                'status': 'failed',
                'execution_time': (time.time() - self.active_trades[trade_id]['start_time']) * 1000,
                'execution_mode': 'DYNAMIC_2-STEP'
            }
            
            self.logger.error(f"TRADE_FAILED (🔴 LIVE USDT TRIANGLE/AUTO): {trade_data} | Error: {error_message}")
            
        except Exception as e:
            self.logger.error(f"Error logging failed trade: {e}")
    
    async def execute_standard_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute standard 3-step arbitrage (fallback method)."""
        try:
            exchange_name = getattr(opportunity, 'exchange', 'kucoin')
            exchange = self.exchange_manager.get_exchange(exchange_name)
            
            if not exchange:
                self.logger.error(f"❌ Exchange {exchange_name} not available")
                return False
            
            self.logger.info(f"🔧 STANDARD EXECUTION: {opportunity.triangle_path}")
            
            # Execute all 3 steps sequentially
            for i, step in enumerate(opportunity.steps, 1):
                self.logger.info(f"🔧 Step {i}: {step.side.upper()} {step.quantity:.8f} {step.symbol}")
                
                result = await exchange.place_market_order(step.symbol, step.side, step.quantity)
                
                if not result.get('success'):
                    self.logger.error(f"❌ Step {i} failed: {result.get('error', 'Unknown error')}")
                    return False
                
                self.logger.info(f"✅ Step {i} completed")
                
                # Brief pause between steps
                if i < len(opportunity.steps):
                    await asyncio.sleep(0.5)
            
            self.logger.info("🎉 STANDARD ARBITRAGE COMPLETED")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error in standard arbitrage execution: {e}")
            return False
    
    async def execute_paper_trade(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute paper trade simulation."""
        try:
            self.logger.info(f"📝 PAPER TRADE: {opportunity.triangle_path}")
            self.logger.info(f"   Expected Profit: {opportunity.profit_percentage:.4f}% (${opportunity.profit_amount:.2f})")
            
            # Simulate execution time
            await asyncio.sleep(2)
            
            # Simulate success/failure (95% success rate)
            import random
            success = random.random() < 0.95
            
            if success:
                self.logger.info("✅ PAPER TRADE SUCCESSFUL (simulated)")
                return True
            else:
                self.logger.warning("❌ PAPER TRADE FAILED (simulated)")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in paper trade: {e}")
            return False
    
    def get_active_trades(self) -> Dict[str, Any]:
        """Get currently active trades."""
        return self.active_trades.copy()
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get trade execution history."""
        return self.trade_history.copy()
    
    async def cancel_all_trades(self) -> bool:
        """Cancel all active trades (emergency stop)."""
        try:
            self.logger.warning("🛑 EMERGENCY STOP: Cancelling all active trades")
            
            for trade_id in list(self.active_trades.keys()):
                try:
                    # Mark trade as cancelled
                    self.active_trades[trade_id]['status'] = 'cancelled'
                    self.logger.info(f"🛑 Cancelled trade {trade_id}")
                except Exception as e:
                    self.logger.error(f"Error cancelling trade {trade_id}: {e}")
            
            # Clear active trades
            self.active_trades.clear()
            
            self.logger.info("✅ All trades cancelled")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling trades: {e}")
            return False
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update executor configuration."""
        try:
            self.config.update(new_config)
            
            # Update key settings
            self.auto_trading = self.config.get('auto_trading', self.auto_trading)
            self.paper_trading = self.config.get('paper_trading', self.paper_trading)
            self.min_profit_threshold = self.config.get('min_profit_threshold', self.min_profit_threshold)
            
            self.logger.info(f"✅ Configuration updated: {new_config}")
            
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get executor statistics."""
        try:
            total_trades = len(self.trade_history)
            successful_trades = len([t for t in self.trade_history if t.get('success', False)])
            
            return {
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'success_rate': (successful_trades / total_trades * 100) if total_trades > 0 else 0,
                'active_trades': len(self.active_trades),
                'auto_trading': self.auto_trading,
                'paper_trading': self.paper_trading,
                'min_profit_threshold': self.min_profit_threshold
            }
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}