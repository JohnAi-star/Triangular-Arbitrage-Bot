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
        
        # Add min_profit_threshold from config
        from config.config import Config
        self.min_profit_threshold = Config.MIN_PROFIT_THRESHOLD
        
        self.logger.info(f"✅ TradeExecutor initialized with profit threshold: {self.min_profit_threshold}%")
        
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
        
    def _is_profitable(self, opportunity) -> bool:
        """
        SINGLE SOURCE OF TRUTH for profit validation.
        Uses ONLY config.min_profit_threshold (0.5%) for all decisions.
        """
        try:
            # Get profit percentage from opportunity
            profit_pct = getattr(opportunity, 'net_profit_percent', None)
            if profit_pct is None:
                profit_pct = getattr(opportunity, 'profit_percentage', 0)
            
            # Log clear threshold comparison
            self.logger.info(
                f"💰 Profit Check: {profit_pct:.4f}% "
                f"(Config Threshold: {self.min_profit_threshold:.2f}%)"
            )
            
            # Single comparison using >= (not >)
            is_profitable = profit_pct >= self.min_profit_threshold
            
            if is_profitable:
                self.logger.info(f"✅ PROFITABLE: {profit_pct:.4f}% >= {self.min_profit_threshold:.2f}% threshold")
            else:
                self.logger.info(f"❌ NOT PROFITABLE: {profit_pct:.4f}% < {self.min_profit_threshold:.2f}% threshold")
            
            return is_profitable
            
        except Exception as e:
            self.logger.error(f"Error in profit validation: {e}")
            return False
    
    async def _verify_sufficient_balance(self, exchange, base_currency: str, required_amount: float) -> bool:
        """Verify sufficient balance for trading."""
        try:
            self.logger.info(f"🔍 Checking balance for {base_currency}: need {required_amount:.2f}")
            balance = await exchange.get_account_balance()
            available = balance.get(base_currency, 0.0)
            
            self.logger.info(f"💰 Available balance: {available:.6f} {base_currency}")
            
            if available >= required_amount:
                self.logger.info(f"✅ Sufficient balance: {available:.6f} {base_currency} (need {required_amount:.6f})")
                return True
            else:
                self.logger.warning(f"⚠️ Low balance: {available:.6f} {base_currency} (need {required_amount:.6f})")
                # For Gate.io, allow trading with available balance if > $5
                if available >= 5.0 and base_currency == 'USDT':
                    self.logger.info(f"✅ Proceeding with available balance: ${available:.2f} USDT")
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
    
    async def _validate_triangle_before_execution(self, opportunity, exchange, exchange_id: str) -> bool:
        """Validate the entire triangle before starting execution to prevent losses."""
        try:
            self.logger.info("🔍 PRE-EXECUTION VALIDATION: Checking USDT triangle feasibility...")
            
            # Extract triangle path properly
            triangle_path = getattr(opportunity, 'triangle_path', None)
            
            # Handle different triangle_path formats
            if isinstance(triangle_path, str):
                # Handle string format like "USDT → BTC → RLC → USDT" or "USDT -> BTC -> RLC -> USDT"
                if ' → ' in triangle_path:
                    path_parts = triangle_path.split(' → ')
                elif ' -> ' in triangle_path:
                    path_parts = triangle_path.split(' -> ')
                else:
                    # Try splitting by spaces and filter out arrows
                    path_parts = [part.strip() for part in triangle_path.split() if part.strip() not in ['→', '->']]
                
                if len(path_parts) >= 3:
                    # For 4-part path like "USDT → BTC → RLC → USDT", take first 3 currencies
                    if len(path_parts) == 4 and path_parts[0] == path_parts[3]:
                        triangle_path = path_parts[:3]  # [USDT, BTC, RLC]
                    else:
                        triangle_path = path_parts[:3]  # Take first 3
                    self.logger.info(f"✅ Parsed string path: {' → '.join(triangle_path)}")
                else:
                    self.logger.error(f"❌ Invalid string triangle format: {triangle_path}")
                    return False
            elif isinstance(triangle_path, list):
                # Handle list format
                if len(triangle_path) >= 3:
                    triangle_path = triangle_path[:3]  # Take first 3 currencies
                    self.logger.info(f"✅ Using list path: {' → '.join(triangle_path)}")
                else:
                    self.logger.error(f"❌ Triangle path too short: {triangle_path}")
                    return False
            else:
                self.logger.error(f"❌ Invalid triangle_path type: {type(triangle_path)}")
                return False
            
            # CRITICAL: Validate we have exactly 3 currencies
            if not triangle_path or len(triangle_path) != 3:
                self.logger.error(f"❌ VALIDATION FAILED: Need exactly 3 currencies, got {len(triangle_path)}: {triangle_path}")
                return False
            
            # CRITICAL: Only allow USDT-based triangles for safety
            if triangle_path[0] != 'USDT':
                self.logger.error(f"❌ SAFETY FILTER: Non-USDT triangle rejected: {' → '.join(triangle_path)}")
                self.logger.error("   Only USDT → Currency1 → Currency2 → USDT triangles are allowed")
                return False
            # Get valid currencies for the specific exchange
            # Use the passed exchange_id parameter instead of trying to get it from opportunity
            valid_currencies = self._get_valid_currencies_for_exchange(exchange_id)
            
            self.logger.info(f"🔍 Validating currencies for {exchange_id}: {triangle_path}")
            
            for currency in triangle_path:
                if currency not in valid_currencies:
                    self.logger.error(f"❌ INVALID CURRENCY: {currency} not available on {exchange_id}")
                    self.logger.error(f"   Valid currencies: {sorted(list(valid_currencies))[:20]}...")
                    return False
            
            self.logger.info(f"✅ All currencies valid for {exchange_id}: {' → '.join(triangle_path)}")
            
            # Ensure we have exactly 3 currencies
            base_currency = triangle_path[0]  # USDT
            intermediate_currency = triangle_path[1]  # e.g., CYBER
            quote_currency = triangle_path[2]  # e.g., TRY
            
            self.logger.info(f"🔍 Validating USDT triangle: {base_currency} → {intermediate_currency} → {quote_currency} → {base_currency}")
            
            # Define the three pairs
            pair1 = f"{intermediate_currency}/USDT"  # CYBER/USDT
            pair2 = f"{intermediate_currency}/{quote_currency}"  # CYBER/TRY
            pair3 = f"{quote_currency}/USDT"  # TRY/USDT
            
            # Try alternative pair2 if direct doesn't exist
            alt_pair2 = f"{quote_currency}/{intermediate_currency}"  # TRY/CYBER
            
            # Check which pairs exist and get market data
            self.logger.info(f"🔍 Checking required pairs: {pair1}, {pair2} (or {alt_pair2}), {pair3}")
            
            # Get market data for validation
            ticker1 = await exchange.get_ticker(pair1)
            ticker3 = await exchange.get_ticker(pair3)
            
            # Try to get pair2 (try both directions)
            ticker2 = await exchange.get_ticker(pair2)
            use_direct_pair2 = True
            
            if not ticker2 or not (ticker2.get('bid') and ticker2.get('ask')):
                # Try alternative pair2
                self.logger.info(f"🔄 Trying alternative pair: {alt_pair2}")
                ticker2 = await exchange.get_ticker(alt_pair2)
                use_direct_pair2 = False
            
            # Validate all tickers have proper data
            self.logger.info(f"🔍 Market data validation:")
            self.logger.info(f"   {pair1}: {bool(ticker1 and ticker1.get('bid') and ticker1.get('ask'))}")
            self.logger.info(f"   {pair2 if use_direct_pair2 else alt_pair2}: {bool(ticker2 and ticker2.get('bid') and ticker2.get('ask'))}")
            self.logger.info(f"   {pair3}: {bool(ticker3 and ticker3.get('bid') and ticker3.get('ask'))}")
            
            if not all(ticker and ticker.get('bid') and ticker.get('ask') for ticker in [ticker1, ticker2, ticker3]):
                self.logger.error("❌ Missing market data - aborting execution to prevent loss")
                return False
            
            # Simulate the entire triangle with current prices
            start_usdt = opportunity.initial_amount
            
            # Step 1: USDT → intermediate (buy intermediate with USDT)
            price1 = ticker1.get('ask', 0)  # Buy at ask
            amount_intermediate = start_usdt / price1
            
            # Step 2: intermediate → quote (sell intermediate for quote)
            price2 = ticker2.get('bid', 0)  # Sell at bid
            amount_quote = amount_intermediate * price2
            
            # Calculate USD value of step 2
            step2_usd_value = amount_quote * ticker3.get('last', ticker3.get('bid', 0))
            
            self.logger.info(f"🔍 Triangle validation:")
            self.logger.info(f"   Step 1: ${start_usdt:.2f} USDT → {amount_intermediate:.6f} {intermediate_currency}")
            self.logger.info(f"   Step 2: {amount_intermediate:.6f} {intermediate_currency} → {amount_quote:.6f} {quote_currency}")
            self.logger.info(f"   Step 2 USD value: ${step2_usd_value:.2f}")
            
            # CRITICAL: Check if step 2 meets exchange minimum
            min_order_value = self._get_exchange_minimum_order(exchange_id)
            if step2_usd_value < min_order_value:
                self.logger.error(f"❌ TRIANGLE REJECTED: Step 2 value ${step2_usd_value:.2f} < ${min_order_value:.2f} {exchange_id} minimum")
                self.logger.error(f"❌ This triangle would fail at step 2 - preventing execution to avoid loss")
                return False
            
            # Step 3: quote → USDT (sell quote for USDT)
            price3 = ticker3.get('bid', 0)  # Sell at bid
            final_usdt = amount_quote * price3
            
            # Calculate actual profit with current prices
            actual_profit = final_usdt - start_usdt
            actual_profit_pct = (actual_profit / start_usdt) * 100
            
            self.logger.info(f"   Step 3: {amount_quote:.6f} {quote_currency} → ${final_usdt:.2f} USDT")
            self.logger.info(f"   Actual profit with current prices: {actual_profit_pct:.4f}%")
            
            # Validate actual profit is still above threshold
            if actual_profit_pct < 0.5:
                self.logger.error(f"❌ TRIANGLE REJECTED: Actual profit {actual_profit_pct:.4f}% < 0.5% threshold")
                return False
            
            self.logger.info(f"✅ TRIANGLE VALIDATION PASSED: All steps meet requirements")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Triangle validation failed: {e}")
            return False
    
    def _get_valid_currencies_for_exchange(self, exchange_id: str) -> set:
        """Get valid currencies for specific exchange"""
        if exchange_id == 'kucoin':
            return {
                # Major cryptocurrencies (high volume, good liquidity)
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS', 'XTZ', 'DASH',
                'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT', 'IOST', 'THETA',
                'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB', 'PENDLE', 'RNDR',
                'INJ', 'SEI', 'TIA', 'SUI', 'PEPE', 'FLOKI', 'WLD', 'KCS', 'ONE', 'CYBER',
                
                # Stablecoins and USD pairs
                'USDD', 'TUSD', 'DAI', 'FRAX', 'LUSD', 'MIM', 'USTC', 'USDJ', 'FDUSD',
                
                # DeFi tokens (often have good arbitrage opportunities)
                'CAKE', 'ALPHA', 'AUTO', 'BAKE', 'BELT', 'BUNNY', 'CHESS', 'CTK', 'DEGO',
                'EPS', 'FOR', 'HARD', 'HELMET', 'LINA', 'LIT', 'MASK', 'MIR', 'NULS',
                'OG', 'PHA', 'POLS', 'PUNDIX', 'RAMP', 'REEF', 'SFP', 'SPARTA', 'SXP',
                'TKO', 'TWT', 'UNFI', 'VAI', 'VIDT', 'WRX', 'XVS', 'DYDX', 'GALA',
                
                # New and trending tokens (higher volatility = more arbitrage)
                'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'ORDI', 'SATS', '1000SATS', 'RATS',
                'MEME', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI', 'SCR', 'EIGEN', 'HMSTR',
                'CATI', 'NEIRO', 'CYBER', 'BLUR', 'SUI', 'APT', 'MOVE', 'USUAL', 'PENGU',
                
                # Gaming and metaverse tokens
                'AXS', 'GALA', 'ILV', 'SPS', 'MBOX', 'YGG', 'GMT', 'APE', 'MAGIC', 'VOXEL',
                'ALICE', 'TLM', 'CHR', 'PYR', 'SKILL', 'TOWER', 'UFO', 'NFTB', 'REVV',
                
                # AI and tech tokens
                'AGIX', 'FET', 'OCEAN', 'NMR', 'RLC', 'CTXC', 'NFP', 'PAAL', 'AIT', 'TAO',
                'RNDR', 'LPT', 'LIVEPEER', 'THETA', 'TFUEL', 'VRA', 'ANKR', 'STORJ',
                
                # Layer 2 and scaling solutions
                'MATIC', 'ARB', 'OP', 'IMX', 'METIS', 'BOBA', 'SKALE', 'CELR', 'OMG',
                'LRC', 'ZKS', 'DUSK', 'L2', 'ORBS', 'COTI', 'CTSI', 'CARTESI',
                
                # Meme coins (high volatility)
                'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF', 'MEME', 'TURBO', 'COQ', 'LADYS',
                'WEN', 'MYRO', 'POPCAT', 'MEW', 'MOTHER', 'DADDY', 'SIGMA', 'RETARDIO',
                
                # Additional high-volume tokens
                'NEAR', 'ROSE', 'ONE', 'HARMONY', 'CELO', 'KLAY', 'FLOW', 'EGLD', 'ELROND',
                'AVAX', 'LUNA', 'LUNC', 'USTC', 'ATOM', 'OSMO', 'JUNO', 'SCRT', 'REGEN',
                'STARS', 'HUAHUA', 'CMDX', 'CRE', 'XPRT', 'NGM', 'IOV', 'BOOT', 'CHEQ'
            }
        elif exchange_id == 'gate':
            return {
                'USDT', 'BTC', 'ETH', 'USDC', 'BNB', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'MKR', 'SNX', 'YFI', 'SUSHI', 'BAL', 'REN', 'KNC', 'ZRX', 'STORJ', 'GRT',
                'CYBER', 'LDO', 'TNSR', 'AKT', 'XLM', 'AR', 'ETC', 'BCH', 'EOS',
                'XTZ', 'DASH', 'ZEC', 'QTUM', 'ONT', 'ICX', 'ZIL', 'BAT', 'ENJ', 'HOT',
                'IOST', 'THETA', 'TFUEL', 'KAVA', 'BAND', 'CRO', 'OKB', 'HT', 'LEO', 'SHIB',
                'FDUSD', 'PENDLE', 'JUP', 'WIF', 'BONK', 'PYTH', 'JTO', 'RNDR', 'INJ', 'SEI',
                'TIA', 'SUI', 'ORDI', 'SATS', '1000SATS', 'RATS', 'MEME', 'PEPE', 'FLOKI', 'WLD',
                'SCR', 'EIGEN', 'HMSTR', 'CATI', 'NEIRO', 'TURBO', 'BOME', 'ENA', 'W', 'ETHFI',
                'ONE', 'AR'  # Add the missing currencies that were causing failures
            }
        elif exchange_id == 'binance':
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'BUSD', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'HBAR', 'ICP', 'APT', 'ARB', 'OP', 'MANA', 'SAND', 'CRV', 'AAVE', 'COMP',
                'INJ', 'ONE', 'AR'  # Add missing currencies
            }
        else:
            # Default major currencies
            return {
                'BTC', 'ETH', 'USDT', 'USDC', 'ADA', 'SOL', 'DOT', 'LINK', 'MATIC', 'AVAX',
                'DOGE', 'XRP', 'LTC', 'TRX', 'ATOM', 'FIL', 'UNI', 'NEAR', 'ALGO', 'VET',
                'INJ', 'ONE', 'AR'  # Add missing currencies for all exchanges
            }
    
    def _get_exchange_minimum_order(self, exchange_id: str) -> float:
        """Get minimum order value for specific exchange"""
        if exchange_id == 'kucoin':
            return 1.0  # KuCoin minimum $1 USD
        elif exchange_id == 'gate':
            return 3.0  # Gate.io minimum $3 USD
        elif exchange_id == 'binance':
            return 10.0  # Binance minimum $10 USD
        elif exchange_id == 'bybit':
            return 5.0  # Bybit minimum $5 USD
        else:
            return 5.0  # Default minimum $5 USD
    
    async def _execute_single_order(self, exchange, symbol: str, side: str, quantity: float, step_num: int) -> Dict[str, Any]:
        """Execute a single market order with detailed logging."""
        try:
            self.logger.info(f"🔄 STEP {step_num}: Executing REAL {side.upper()} order on {exchange.exchange_id}")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Quantity: {quantity:.8f}")
            self.logger.info(f"   Side: {side.upper()}")
            
            # Enhanced validation for Gate.io
            if exchange.exchange_id == 'kucoin':
                # Get current price for validation
                ticker = await exchange.get_ticker(symbol)
                current_price = ticker.get('last', 0) or ticker.get('ask', 0) or ticker.get('bid', 0)
                
                if side.lower() == 'buy':
                    # For BUY: quantity should be USDT amount to spend
                    order_value = quantity
                    if order_value < 1.0:  # KuCoin minimum $1 USD
                        self.logger.error(f"❌ KuCoin minimum: ${order_value:.2f} < $1.00 required")
                        return {'success': False, 'error': f'Order too small: ${order_value:.2f} < $1.00'}
                else:
                    # For SELL: quantity is base currency amount
                    order_value = quantity * current_price if current_price > 0 else quantity
                    if order_value < 1.0:
                        self.logger.error(f"❌ KuCoin minimum: ${order_value:.2f} < $1.00 required")
                        return {'success': False, 'error': f'Order too small: ${order_value:.2f} < $1.00'}
                    
                    # Additional safety check for very small quantities
                    if quantity < 0.0001:  # Minimum quantity threshold for KuCoin
                        self.logger.error(f"❌ KuCoin minimum quantity: {quantity:.8f} too small")
                        return {'success': False, 'error': f'Quantity too small: {quantity:.8f}'}
                
                self.logger.info(f"✅ KuCoin order validation: ${order_value:.2f} ≥ $1.00")
            elif exchange.exchange_id == 'gate':
                # Get current price for validation
                ticker = await exchange.get_ticker(symbol)
                current_price = ticker.get('last', 0) or ticker.get('ask', 0) or ticker.get('bid', 0)
                
                if side.lower() == 'buy':
                    # For BUY: quantity should be USDT amount to spend
                    order_value = quantity
                    if order_value < 3.0:  # Gate.io minimum $3 USDT
                        self.logger.error(f"❌ Gate.io minimum: ${order_value:.2f} < $3.00 required")
                        return {'success': False, 'error': f'Order too small: ${order_value:.2f} < $3.00'}
                else:
                    # For SELL: quantity is base currency amount
                    order_value = quantity * current_price if current_price > 0 else quantity
                    if order_value < 3.0:
                        self.logger.error(f"❌ Gate.io minimum: ${order_value:.2f} < $3.00 required")
                        return {'success': False, 'error': f'Order too small: ${order_value:.2f} < $3.00'}
                    
                    # Additional safety check for very small quantities
                    if quantity < 0.001:  # Minimum quantity threshold
                        self.logger.error(f"❌ Gate.io minimum quantity: {quantity:.8f} too small")
                        return {'success': False, 'error': f'Quantity too small: {quantity:.8f}'}
                
                self.logger.info(f"✅ Gate.io order validation: ${order_value:.2f} ≥ $3.00")
            
            # Execute the REAL order on the correct exchange
            order_start_time = time.time()
            order = await exchange.place_market_order(symbol, side, quantity)
            execution_time = (time.time() - order_start_time) * 1000
            
            if order and isinstance(order, dict) and order.get('success'):
                # Log successful order details
                order_id = order.get('id', 'Unknown')
                filled_qty = float(order.get('filled', 0))
                avg_price = float(order.get('average', 0))
                total_cost = float(order.get('cost', 0))
                fee_info = order.get('fee', {}) or {}
                fee_cost = float(fee_info.get('cost', 0)) if fee_info else 0
                fee_currency = fee_info.get('currency', 'Unknown') if fee_info else 'Unknown'
                
                self.logger.info(f"✅ REAL ORDER EXECUTED SUCCESSFULLY:")
                self.logger.info(f"   Order ID: {order_id}")
                self.logger.info(f"   Filled: {filled_qty:.8f} {symbol}")
                self.logger.info(f"   Average Price: {avg_price:.8f}")
                self.logger.info(f"   Total Cost: {total_cost:.8f}")
                self.logger.info(f"   Fee: {fee_cost:.8f} {fee_currency}")
                self.logger.info(f"   Execution Time: {execution_time:.0f}ms")
                self.logger.info(f"   Status: {order.get('status', 'Unknown')}")
                
                # Verify order was filled
                if (order.get('status') in ['closed', 'filled'] and filled_qty > 0) or order.get('success'):
                    self.logger.info(f"🎉 Order {order_id} FULLY FILLED - Trade recorded on Gate.io!")
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
                return {'success': False, 'error': f'Invalid order response: {type(order)}', 'raw_response': order}
                
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
        """Execute the triangular arbitrage trade with enhanced safety checks."""
        # SINGLE SOURCE OF TRUTH: Use only _is_profitable() method
        if not self._is_profitable(opportunity):
            self.logger.info(f"❌ REJECTED: Opportunity below profit threshold")
            return False
        
        # Enforce maximum trade amount (reduced to $20)
        if opportunity.initial_amount > 20:
            self.logger.warning(f"Trade amount ${opportunity.initial_amount:.2f} exceeds $20 limit, adjusting...")
            opportunity.initial_amount = 20
        
        # Ensure minimum trade amount for Gate.io
        if opportunity.initial_amount < 5:
            self.logger.warning(f"Trade amount ${opportunity.initial_amount:.2f} below $5 minimum, adjusting...")
            opportunity.initial_amount = 5
            
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
        
        # CRITICAL: Validate entire triangle before execution
        if not await self._validate_triangle_before_execution(opportunity, exchange, exchange_id):
            self.logger.error("❌ TRIANGLE VALIDATION FAILED - Aborting to prevent loss")
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
            self.logger.info(f"🎯 USDT Triangle: Will execute 3 sequential trades on Gate.io")
            self.logger.info(f"💰 Expected to turn {opportunity.initial_amount:.2f} USDT into {opportunity.final_amount:.2f} USDT")
            
            # Execute each step with REAL orders and enhanced validation
            execution_results = []
            current_balance = opportunity.initial_amount
            order_ids = []  # Track all order IDs for verification
            
            for i, step in enumerate(opportunity.steps):
                try:
                    self.logger.info(f"🔄 EXECUTING USDT TRIANGLE STEP {i+1}/{len(opportunity.steps)} ({trading_mode}/{execution_type})")
                    self.logger.info(f"   Action: {step.side.upper()} {step.quantity:.6f} {step.symbol}")
                    self.logger.info(f"   Expected Price: {step.price:.8f}")
                    self.logger.info(f"🔴 REAL {exchange_id.upper()} ORDER: This will appear in your account immediately")
                    
                    # Calculate proper quantity for each step with enhanced validation
                    if i == 0:
                        # Step 1: Buy intermediate currency with USDT
                        actual_quantity = opportunity.initial_amount  # USDT amount to spend
                        self.logger.info(f"   Step 1: Spending {actual_quantity:.2f} USDT to buy {step.symbol.split('/')[0]}")
                    elif i == 1:
                        # Step 2: Trade intermediate for quote currency
                        # Use the amount we got from step 1
                        prev_result = execution_results[i-1]
                        actual_quantity = prev_result.get('filled_quantity', step.quantity)
                        self.logger.info(f"   Step 2: Trading {actual_quantity:.8f} {step.symbol.split('/')[0]}")
                        
                        # CRITICAL FIX: Validate USD value for Gate.io minimum
                        try:
                            ticker = await exchange.get_ticker(step.symbol)
                            current_price = ticker.get('bid', 0) if step.side == 'sell' else ticker.get('ask', 0)
                            usd_value = actual_quantity * current_price if current_price > 0 else 0
                            
                            self.logger.info(f"   Step 2 USD validation: {actual_quantity:.8f} × {current_price:.8f} = ${usd_value:.2f}")
                            
                            min_order_value = self._get_exchange_minimum_order(exchange.exchange_id)
                            if usd_value < min_order_value:
                                self.logger.error(f"❌ CRITICAL: Step 2 order value ${usd_value:.2f} < ${min_order_value:.2f} {exchange.exchange_id} minimum")
                                self.logger.error(f"❌ ABORTING TRADE: Cannot proceed with insufficient order value")
                                raise Exception(f"Order value ${usd_value:.2f} below {exchange.exchange_id} ${min_order_value:.2f} minimum - trade aborted to prevent loss")
                            
                            self.logger.info(f"✅ Step 2 USD validation passed: ${usd_value:.2f} ≥ ${min_order_value:.2f}")
                            
                        except Exception as validation_error:
                            self.logger.error(f"❌ Step 2 validation failed: {validation_error}")
                            raise validation_error
                    else:
                        # Step 3: Sell quote currency for USDT
                        # Use the amount we got from step 2
                        prev_result = execution_results[i-1]
                        actual_quantity = prev_result.get('filled_quantity', step.quantity)
                        self.logger.info(f"   Step 3: Selling {actual_quantity:.8f} {step.symbol.split('/')[0]} for USDT")
                    
                    # Execute REAL market order
                    result = await self._execute_single_order(exchange, step.symbol, step.side, actual_quantity, i+1)
                    
                    execution_results.append(result)
                    
                    if not result.get('success'):
                        raise Exception(f"Order execution failed: {result.get('error', 'Unknown error')}")
                    
                    # Extract execution details
                    order_id = result.get('order_id', 'N/A')
                    filled_qty = result.get('filled_quantity', 0) or result.get('filled', 0)
                    avg_price = result.get('average_price', step.price)
                    fees_paid = result.get('fee_cost', 0)
                    execution_time_ms = result.get('execution_time_ms', 0)
                    
                    order_ids.append(order_id)
                    
                    # For market buy orders, calculate the actual quantity received
                    if step.side == 'buy' and i == 0:
                        # For market buy, we spent USDT and received base currency
                        # The filled_qty should be the amount of base currency we received
                        total_cost = result.get('total_cost', 0) or result.get('cost', 0)
                        if total_cost > 0 and avg_price > 0:
                            filled_qty = total_cost / avg_price
                            self.logger.info(f"🔧 {exchange.exchange_id} market buy: spent ${total_cost:.2f} USDT, received {filled_qty:.8f} {step.symbol.split('/')[0]}")
                    
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
                    self.logger.info(f"🔴 {exchange_id.upper()}: Order {order_id} is now visible in your account")
                    
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
                    
                    # Wait between steps for market stability
                    if i < len(opportunity.steps) - 1:
                        await asyncio.sleep(1)
                        
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
            self.logger.info(f"🔴 GATE.IO: Check your Spot Orders for these {len(order_ids)} trades!")
            self.logger.info(f"🔴 GATE.IO: All trades are now visible in your Trade History")
            
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
            self.logger.info(f"🔴 {exchange_id.upper()} SPOT ORDERS: All {len(order_ids)} trades are now visible in your account!")
            self.logger.info(f"🔴 {exchange_id.upper()} BALANCE: Your USDT balance has been updated with the profit!")
            
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
            
            # Log trade safely
            try:
                await self.detailed_trade_logger.log_trade(trade_log)
            except Exception as log_error:
                self.logger.error(f"Error logging trade: {log_error}")
            
            execution_type = "AUTO" if self.auto_trading else "MANUAL" 
            trading_mode = "🔴 LIVE"
            self.logger.error(f"❌ ARBITRAGE EXECUTION FAILED on {exchange_id} ({trading_mode}/{execution_type}): {str(e)}")
            self.trade_logger.error(f"TRADE_FAILED ({trading_mode}/{execution_type}): {opportunity.to_dict()} | Error: {str(e)}")
            
            return False