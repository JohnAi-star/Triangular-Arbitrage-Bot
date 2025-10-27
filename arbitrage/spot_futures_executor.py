import asyncio
import logging
import uuid
from typing import Dict, Optional, List
from models.spot_futures_opportunity import SpotFuturesOpportunity, ArbitrageDirection
from models.spot_futures_position import SpotFuturesPosition, PositionStatus

class SpotFuturesExecutor:
    def __init__(self, spot_exchange, futures_exchange, trade_logger=None):
        self.spot_exchange = spot_exchange
        self.futures_exchange = futures_exchange
        self.trade_logger = trade_logger
        self.logger = logging.getLogger(__name__)
        self.active_positions: Dict[str, SpotFuturesPosition] = {}
        
        # Risk management
        self.max_position_size = 100.0  # Maximum USDT per position
        self.max_open_positions = 3     # Maximum concurrent positions
        self.cooldown_period = 30       # Seconds between trades on same symbol
        
        # Track recent trades for cooldown
        self.recent_trades: Dict[str, float] = {}
        
    def _can_trade_symbol(self, symbol: str) -> bool:
        """Check if we can trade this symbol (cooldown period)"""
        if symbol not in self.recent_trades:
            return True
            
        last_trade_time = self.recent_trades[symbol]
        return (asyncio.get_event_loop().time() - last_trade_time) > self.cooldown_period
    
    def _record_trade(self, symbol: str):
        """Record trade for cooldown tracking"""
        self.recent_trades[symbol] = asyncio.get_event_loop().time()
        
        # Clean old entries
        current_time = asyncio.get_event_loop().time()
        self.recent_trades = {
            sym: time for sym, time in self.recent_trades.items() 
            if current_time - time < 300  # Keep only last 5 minutes
        }
    
    async def execute_arbitrage(self, opportunity: SpotFuturesOpportunity, amount: float) -> Dict:
        """Execute spot-futures arbitrage trade with risk checks"""
        try:
            # Risk management checks
            if not self._can_trade_symbol(opportunity.symbol):
                self.logger.warning(f"⏳ Cooldown active for {opportunity.symbol}, skipping trade")
                return {'error': 'cooldown_active'}
            
            if len(self.active_positions) >= self.max_open_positions:
                self.logger.warning(f"📊 Max positions reached ({self.max_open_positions}), skipping trade")
                return {'error': 'max_positions_reached'}
            
            if amount > self.max_position_size:
                self.logger.warning(f"💰 Amount ${amount} exceeds max ${self.max_position_size}, adjusting")
                amount = self.max_position_size
            
            self.logger.info(f"🚀 Executing arbitrage: {opportunity.symbol} "
                           f"({opportunity.direction.value}) - Spread: {opportunity.spread_percentage:.4f}%")
            
            # Set leverage for futures (1x for safety)
            await self.futures_exchange.set_leverage(opportunity.symbol, leverage=1)
            
            # Execute based on direction
            if opportunity.direction == ArbitrageDirection.FUTURES_PREMIUM:
                result = await self._execute_futures_premium(opportunity, amount)
            else:
                result = await self._execute_spot_premium(opportunity, amount)
            
            # Record trade for cooldown
            if 'position_id' in result:
                self._record_trade(opportunity.symbol)
                
            return result
                
        except Exception as e:
            self.logger.error(f"Error executing arbitrage: {e}")
            raise
    
    async def _execute_futures_premium(self, opportunity: SpotFuturesOpportunity, amount_usdt: float) -> Dict:
        """Execute when futures price is higher than spot - Buy Spot + Sell Futures

        Args:
            amount_usdt: Amount in USDT to trade (e.g., $20)
        """
        symbol = opportunity.symbol
        base_currency = symbol.split('-')[0]

        # Convert USDT amount to coin quantity
        coin_quantity = amount_usdt / opportunity.spot_price

        self.logger.info("📈 FUTURES PREMIUM STRATEGY: Buy Spot + Sell Futures")
        self.logger.info(f"  Trade Amount: ${amount_usdt:.2f} USDT = {coin_quantity:.6f} {base_currency}")
        self.logger.info(f"  Spot Price: ${opportunity.spot_price:.2f} | Futures Price: ${opportunity.futures_price:.2f}")

        try:
            # Check balances before trading
            spot_balance_usdt = await self.spot_exchange.get_balance('USDT')
            futures_balance_usdt = await self.futures_exchange.get_futures_balance('USDT')

            # Calculate required amounts
            required_spot_usdt = amount_usdt
            required_futures_margin = amount_usdt * 0.1  # 10% margin for 1x leverage

            self.logger.info(f"💰 Balance Check:")
            self.logger.info(f"   Spot USDT: ${spot_balance_usdt:.2f} (need ${required_spot_usdt:.2f})")
            self.logger.info(f"   Futures Margin: ${futures_balance_usdt:.2f} (need ${required_futures_margin:.2f})")

            if spot_balance_usdt < required_spot_usdt:
                self.logger.error(f"❌ Insufficient SPOT balance: have ${spot_balance_usdt:.2f}, need ${required_spot_usdt:.2f}")
                self.logger.error(f"   Transfer funds to your SPOT (Trading) account on KuCoin")
                return {'error': 'insufficient_spot_balance', 'required': required_spot_usdt, 'available': spot_balance_usdt}

            if futures_balance_usdt < required_futures_margin:
                self.logger.error(f"❌ Insufficient FUTURES margin: have ${futures_balance_usdt:.2f}, need ${required_futures_margin:.2f}")
                self.logger.error(f"   Transfer funds to your FUTURES account on KuCoin")
                return {'error': 'insufficient_futures_margin', 'required': required_futures_margin, 'available': futures_balance_usdt}

            # Execute trades concurrently for speed
            self.logger.info(f"🚀 Executing trade: {coin_quantity:.6f} {base_currency}")

            spot_task = self.spot_exchange.create_order(
                symbol=f"{base_currency}/USDT",
                side="buy",
                order_type="market",
                quantity=coin_quantity
            )

            futures_task = self.futures_exchange.create_futures_order(
                symbol=symbol,
                side="sell",
                order_type="market",
                size=coin_quantity,
                leverage=1
            )
            
            spot_result, futures_result = await asyncio.gather(spot_task, futures_task)
            
            # Verify executions
            if 'error' in spot_result or 'error' in futures_result:
                error_msg = f"Trade execution failed - Spot: {spot_result.get('error')}, Futures: {futures_result.get('error')}"
                self.logger.error(error_msg)
                return {'error': 'execution_failed', 'details': error_msg}
            
            # Store position information
            position_id = f"sf_{uuid.uuid4().hex[:8]}"
            position = SpotFuturesPosition(
                position_id=position_id,
                symbol=symbol,
                direction='futures_premium',
                spot_order_id=spot_result.get('orderId'),
                futures_order_id=futures_result.get('data', {}).get('orderId'),
                spot_quantity=coin_quantity,
                futures_quantity=coin_quantity,
                entry_spread=opportunity.spread_percentage,
                entry_time=asyncio.get_event_loop().time()
            )
            
            self.active_positions[position_id] = position
            
            # Log the trade
            if self.trade_logger:
                await self.trade_logger.log_spot_futures_trade({
                    'position_id': position_id,
                    'symbol': symbol,
                    'direction': 'futures_premium',
                    'amount_usdt': amount_usdt,
                    'coin_quantity': coin_quantity,
                    'entry_spread': opportunity.spread_percentage,
                    'spot_order': spot_result,
                    'futures_order': futures_result,
                    'timestamp': asyncio.get_event_loop().time()
                })
            
            self.logger.info(f"✅ FUTURES PREMIUM position opened: {position_id}")
            
            return {
                'position_id': position_id,
                'spot_result': spot_result,
                'futures_result': futures_result,
                'entry_spread': opportunity.spread_percentage,
                'strategy': 'futures_premium',
                'amount_usdt': amount_usdt,
                'coin_quantity': coin_quantity
            }
            
        except Exception as e:
            self.logger.error(f"Error in futures premium execution: {e}")
            return {'error': str(e)}
    
    async def _execute_spot_premium(self, opportunity: SpotFuturesOpportunity, amount_usdt: float) -> Dict:
        """Execute when spot price is higher than futures - Sell Spot + Buy Futures

        Args:
            amount_usdt: Amount in USDT to trade (e.g., $20)
        """
        symbol = opportunity.symbol
        base_currency = symbol.split('-')[0]

        # Convert USDT amount to coin quantity
        coin_quantity = amount_usdt / opportunity.spot_price

        self.logger.info("📉 SPOT PREMIUM STRATEGY: Sell Spot + Buy Futures")
        self.logger.info(f"  Trade Amount: ${amount_usdt:.2f} USDT = {coin_quantity:.6f} {base_currency}")
        self.logger.info(f"  Spot Price: ${opportunity.spot_price:.2f} | Futures Price: ${opportunity.futures_price:.2f}")

        try:
            # Check balances before trading
            spot_balance_asset = await self.spot_exchange.get_balance(base_currency)
            futures_balance_usdt = await self.futures_exchange.get_futures_balance('USDT')

            # Calculate required amounts
            required_futures_margin = amount_usdt * 0.1  # 10% margin for 1x leverage

            self.logger.info(f"💰 Balance Check:")
            self.logger.info(f"   Spot {base_currency}: {spot_balance_asset:.6f} (need {coin_quantity:.6f})")
            self.logger.info(f"   Futures Margin: ${futures_balance_usdt:.2f} (need ${required_futures_margin:.2f})")

            if spot_balance_asset < coin_quantity:
                self.logger.error(f"❌ Insufficient {base_currency} to sell on spot: have {spot_balance_asset:.6f}, need {coin_quantity:.6f}")
                return {'error': 'insufficient_spot_balance'}

            if futures_balance_usdt < required_futures_margin:
                self.logger.error(f"❌ Insufficient FUTURES margin: have ${futures_balance_usdt:.2f}, need ${required_futures_margin:.2f}")
                self.logger.error(f"   Transfer funds to your FUTURES account on KuCoin")
                return {'error': 'insufficient_futures_margin', 'required': required_futures_margin, 'available': futures_balance_usdt}

            # Execute trades concurrently
            self.logger.info(f"🚀 Executing trade: {coin_quantity:.6f} {base_currency}")

            spot_task = self.spot_exchange.create_order(
                symbol=f"{base_currency}/USDT",
                side="sell",
                order_type="market",
                quantity=coin_quantity
            )

            futures_task = self.futures_exchange.create_futures_order(
                symbol=symbol,
                side="buy",
                order_type="market",
                size=coin_quantity,
                leverage=1
            )
            
            spot_result, futures_result = await asyncio.gather(spot_task, futures_task)
            
            # Verify executions
            if 'error' in spot_result or 'error' in futures_result:
                error_msg = f"Trade execution failed - Spot: {spot_result.get('error')}, Futures: {futures_result.get('error')}"
                self.logger.error(error_msg)
                return {'error': 'execution_failed', 'details': error_msg}
            
            # Store position information
            position_id = f"sf_{uuid.uuid4().hex[:8]}"
            position = SpotFuturesPosition(
                position_id=position_id,
                symbol=symbol,
                direction='spot_premium',
                spot_order_id=spot_result.get('orderId'),
                futures_order_id=futures_result.get('data', {}).get('orderId'),
                spot_quantity=coin_quantity,
                futures_quantity=coin_quantity,
                entry_spread=opportunity.spread_percentage,
                entry_time=asyncio.get_event_loop().time()
            )
            
            self.active_positions[position_id] = position
            
            # Log the trade
            if self.trade_logger:
                await self.trade_logger.log_spot_futures_trade({
                    'position_id': position_id,
                    'symbol': symbol,
                    'direction': 'spot_premium',
                    'amount_usdt': amount_usdt,
                    'coin_quantity': coin_quantity,
                    'entry_spread': opportunity.spread_percentage,
                    'spot_order': spot_result,
                    'futures_order': futures_result,
                    'timestamp': asyncio.get_event_loop().time()
                })
            
            self.logger.info(f"✅ SPOT PREMIUM position opened: {position_id}")
            
            return {
                'position_id': position_id,
                'spot_result': spot_result,
                'futures_result': futures_result,
                'entry_spread': opportunity.spread_percentage,
                'strategy': 'spot_premium',
                'amount_usdt': amount_usdt,
                'coin_quantity': coin_quantity
            }
            
        except Exception as e:
            self.logger.error(f"Error in spot premium execution: {e}")
            return {'error': str(e)}
    
    async def close_position(self, position_id: str) -> Dict:
        """Close arbitrage position with improved error handling"""
        if position_id not in self.active_positions:
            return {'error': 'position_not_found'}
        
        position = self.active_positions[position_id]
        symbol = position.symbol
        
        try:
            self.logger.info(f"🔚 Closing position {position_id} for {symbol}")
            
            # Get current prices for PnL calculation
            current_spot = await self.spot_exchange.get_ticker(symbol.replace('-', '/'))
            current_futures = await self.futures_exchange.get_futures_ticker(symbol)
            
            if not current_spot or not current_futures:
                self.logger.error("Failed to get current prices for PnL calculation")
                return {'error': 'price_fetch_failed'}
            
            spot_price = float(current_spot['price'])
            futures_price = float(current_futures['data']['price'])
            current_spread = ((futures_price - spot_price) / spot_price) * 100
            
            # Close futures position
            futures_close = await self.futures_exchange.close_futures_position(symbol)
            
            # Close spot position
            base_currency = symbol.split('-')[0]
            if position.direction == 'futures_premium':
                # We bought spot initially, now sell it
                spot_close = await self.spot_exchange.create_order(
                    symbol=f"{base_currency}/USDT",
                    side="sell",
                    order_type="market",
                    quantity=position.spot_quantity
                )
            else:
                # We sold spot initially, now buy it back
                spot_close = await self.spot_exchange.create_order(
                    symbol=f"{base_currency}/USDT",
                    side="buy",
                    order_type="market",
                    quantity=position.spot_quantity
                )
            
            # Update position status and calculate PnL
            position.close(current_spread)
            
            # Log closure
            if self.trade_logger:
                await self.trade_logger.log_spot_futures_close({
                    'position_id': position_id,
                    'exit_spread': current_spread,
                    'pnl_percentage': position.pnl_percentage,
                    'pnl_amount': position.pnl_amount,
                    'spot_close': spot_close,
                    'futures_close': futures_close
                })
            
            # Remove from active positions
            del self.active_positions[position_id]
            
            self.logger.info(f"✅ Position {position_id} closed | PnL: {position.pnl_percentage:.4f}% (${position.pnl_amount:.4f})")
            
            return {
                'position_id': position_id,
                'futures_close': futures_close,
                'spot_close': spot_close,
                'exit_spread': current_spread,
                'pnl_percentage': position.pnl_percentage,
                'pnl_amount': position.pnl_amount,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Error closing position {position_id}: {e}")
            position.status = PositionStatus.ERROR
            return {'error': str(e), 'position_id': position_id}
    
    def get_active_positions(self) -> List[Dict]:
        """Get all active positions with current PnL"""
        positions = []
        for position_id, position in self.active_positions.items():
            pos_data = position.to_dict()
            
            # Add real-time PnL if available
            if position.current_spread is not None:
                pos_data['current_pnl_percentage'] = position.pnl_percentage
                pos_data['current_pnl_amount'] = position.pnl_amount
            
            positions.append(pos_data)
        
        return positions
    
    def get_position_stats(self) -> Dict:
        """Get statistics about current positions"""
        active_positions = self.get_active_positions()
        open_positions = [p for p in active_positions if p['status'] == 'open']
        
        total_pnl = sum(p.get('current_pnl_amount', 0) for p in open_positions)
        avg_pnl = total_pnl / len(open_positions) if open_positions else 0
        
        return {
            'total_positions': len(active_positions),
            'open_positions': len(open_positions),
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_positions': self.max_open_positions
        }