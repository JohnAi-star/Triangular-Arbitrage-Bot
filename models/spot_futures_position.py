from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum
import time

class PositionStatus(Enum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"

@dataclass
class SpotFuturesPosition:
    position_id: str
    symbol: str
    direction: str  # 'futures_premium' or 'spot_premium'
    spot_order_id: Optional[str]
    futures_order_id: Optional[str]
    spot_quantity: float
    futures_quantity: float
    entry_spread: float
    entry_time: float
    current_spread: Optional[float] = None
    exit_spread: Optional[float] = None
    exit_time: Optional[float] = None
    status: PositionStatus = PositionStatus.OPEN
    pnl_percentage: Optional[float] = None
    pnl_amount: Optional[float] = None
    
    def __post_init__(self):
        self.entry_time = self.entry_time or time.time()
    
    def update_spread(self, current_spread: float):
        self.current_spread = current_spread
        
        # Calculate unrealized PnL based on spread change
        if self.direction == 'futures_premium':
            # Profit increases as futures premium decreases
            spread_change = self.entry_spread - current_spread
        else:
            # Profit increases as spot premium decreases  
            spread_change = abs(self.entry_spread) - abs(current_spread)
            
        self.pnl_percentage = spread_change - 0.0012  # Estimated fees
        self.pnl_amount = self.spot_quantity * (self.pnl_percentage / 100)
    
    def close(self, exit_spread: float):
        self.exit_spread = exit_spread
        self.exit_time = time.time()
        self.status = PositionStatus.CLOSED
        self.update_spread(exit_spread)
    
    def to_dict(self):
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_spread': round(self.entry_spread, 4),
            'current_spread': round(self.current_spread, 4) if self.current_spread else None,
            'exit_spread': round(self.exit_spread, 4) if self.exit_spread else None,
            'status': self.status.value,
            'pnl_percentage': round(self.pnl_percentage, 4) if self.pnl_percentage else None,
            'pnl_amount': round(self.pnl_amount, 4) if self.pnl_amount else None,
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'duration': (self.exit_time or time.time()) - self.entry_time
        }