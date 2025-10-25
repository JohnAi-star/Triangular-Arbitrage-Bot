from dataclasses import dataclass
from typing import Optional
from enum import Enum
import time

class ArbitrageDirection(Enum):
    FUTURES_PREMIUM = "futures_premium"  # Futures price > Spot price
    SPOT_PREMIUM = "spot_premium"        # Spot price > Futures price

@dataclass
class SpotFuturesOpportunity:
    symbol: str
    spot_price: float
    futures_price: float
    spread_percentage: float
    direction: ArbitrageDirection
    min_profit_threshold: float = 0.5
    is_tradeable: bool = False
    timestamp: float = None
    
    def __post_init__(self):
        self.timestamp = self.timestamp or time.time()
        self.is_tradeable = abs(self.spread_percentage) >= self.min_profit_threshold
        
    @property
    def profit_percentage(self) -> float:
        return abs(self.spread_percentage) - self.estimated_fees
    
    @property
    def estimated_fees(self) -> float:
        # KuCoin Spot fees (0.1%) + Futures fees (0.06%) = 0.16%
        return 0.16
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'spot_price': self.spot_price,
            'futures_price': self.futures_price,
            'spread_percentage': round(self.spread_percentage, 4),
            'direction': self.direction.value,
            'profit_percentage': round(self.profit_percentage, 4),
            'is_tradeable': self.is_tradeable,
            'min_profit_threshold': self.min_profit_threshold,
            'timestamp': self.timestamp
        }
    
    def __str__(self):
        status = "💰 TRADEABLE" if self.is_tradeable else "⏳ Monitoring"
        return (f"{status} {self.symbol}: Spot=${self.spot_price:.2f} | "
                f"Futures=${self.futures_price:.2f} | "
                f"Spread={self.spread_percentage:.4f}% | "
                f"Est. Profit={self.profit_percentage:.4f}%")