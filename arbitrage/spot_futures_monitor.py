import asyncio
import logging
from typing import Dict, List, Optional
from models.spot_futures_position import SpotFuturesPosition, PositionStatus

class SpotFuturesMonitor:
    """Monitors active spot-futures positions for exit conditions"""
    
    def __init__(self, detector, executor, trade_logger):
        self.detector = detector
        self.executor = executor
        self.trade_logger = trade_logger
        self.logger = logging.getLogger(__name__)
        self.is_monitoring = False
        
        # Exit conditions
        self.target_profit = 0.3  # Close when we reach 0.3% profit
        self.stop_loss = 1.0      # Close if spread moves against us by 1%
        self.max_duration = 300   # Close after 5 minutes max
        
    async def start_monitoring(self):
        """Start monitoring active positions"""
        self.is_monitoring = True
        self.logger.info("🔄 Starting spot-futures position monitoring")
        
        while self.is_monitoring:
            try:
                await self._check_positions()
                await asyncio.sleep(2)  # Check every 2 seconds
            except Exception as e:
                self.logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(5)
    
    async def _check_positions(self):
        """Check all active positions for exit conditions"""
        active_positions = self.executor.get_active_positions()
        
        for position_data in active_positions:
            if position_data['status'] != 'open':
                continue
                
            position_id = position_data['position_id']
            symbol = position_data['symbol']
            
            try:
                # Get current spread
                current_spot = await self.detector.get_spot_price(symbol)
                current_futures = await self.detector.get_futures_price(symbol)
                
                if current_spot is None or current_futures is None:
                    continue
                
                current_spread = ((current_futures - current_spot) / current_spot) * 100
                
                # Update position with current spread
                if position_id in self.executor.active_positions:
                    position = self.executor.active_positions[position_id]
                    position.update_spread(current_spread)
                
                # Check exit conditions
                should_close = await self._check_exit_conditions(position_data, current_spread)
                
                if should_close:
                    self.logger.info(f"🎯 Closing position {position_id} - Exit condition met")
                    await self.executor.close_position(position_id)
                    
            except Exception as e:
                self.logger.error(f"Error checking position {position_id}: {e}")
    
    async def _check_exit_conditions(self, position: Dict, current_spread: float) -> bool:
        """Check if position should be closed"""
        position_id = position['position_id']
        entry_spread = position['entry_spread']
        direction = position['direction']
        
        if direction == 'futures_premium':
            # For futures premium: profit when spread decreases
            spread_change = entry_spread - current_spread
            
            # Take profit
            if spread_change >= self.target_profit:
                self.logger.info(f"✅ TP hit for {position_id}: {spread_change:.4f}%")
                return True
            
            # Stop loss (spread increased against us)
            if current_spread - entry_spread >= self.stop_loss:
                self.logger.info(f"🛑 SL hit for {position_id}: spread increased to {current_spread:.4f}%")
                return True
                
        else:  # spot_premium
            # For spot premium: profit when negative spread becomes less negative
            spread_change = abs(entry_spread) - abs(current_spread)
            
            # Take profit
            if spread_change >= self.target_profit:
                self.logger.info(f"✅ TP hit for {position_id}: {spread_change:.4f}%")
                return True
            
            # Stop loss (spread became more negative against us)
            if abs(current_spread) - abs(entry_spread) >= self.stop_loss:
                self.logger.info(f"🛑 SL hit for {position_id}: spread decreased to {current_spread:.4f}%")
                return True
        
        # Time-based exit
        position_duration = asyncio.get_event_loop().time() - position['entry_time']
        if position_duration > self.max_duration:
            self.logger.info(f"⏰ Time exit for {position_id}: {position_duration:.0f}s")
            return True
        
        return False
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_monitoring = False
        self.logger.info("🛑 Stopped spot-futures position monitoring")