import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
from enum import Enum

def safe_unicode_text(text: str) -> str:
    """Convert Unicode symbols to Windows-safe equivalents."""
    if sys.platform.startswith('win'):
        # Replace Unicode symbols with ASCII equivalents for Windows
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
            '🔺': '[BOT]'
        }
        for unicode_char, ascii_equiv in replacements.items():
            text = text.replace(unicode_char, ascii_equiv)
    return text

class OpportunityStatus(Enum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

@dataclass
class TradeStep:
    """Represents a single step in the triangular arbitrage."""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    expected_amount: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'expected_amount': self.expected_amount
        }

@dataclass
class ArbitrageOpportunity:
    """Represents a triangular arbitrage opportunity."""
    base_currency: str
    intermediate_currency: str
    quote_currency: str
    
    # Trading pairs involved
    pair1: str  # BASE/INTERMEDIATE
    pair2: str  # INTERMEDIATE/QUOTE
    pair3: str  # BASE/QUOTE
    
    # Trade steps
    steps: List[TradeStep] = field(default_factory=list)
    
    # Profitability analysis
    initial_amount: float = 10.0  # Default minimum for Gate.io
    final_amount: float = 0.0
    profit_percentage: float = 0.0
    profit_amount: float = 0.0
    
    # Fees and costs
    estimated_fees: float = 0.0
    estimated_slippage: float = 0.0
    net_profit: float = 0.0
    
    # Metadata
    detected_at: datetime = field(default_factory=datetime.now)
    status: OpportunityStatus = OpportunityStatus.DETECTED
    execution_time: float = 0.0
    
    # Add triangle_path as a mutable field instead of property
    _triangle_path: str = ""
    
    @property
    def triangle_path(self) -> str:
        """Return the triangle path as a string."""
        if self._triangle_path:
            return self._triangle_path
        arrow = safe_unicode_text("→")
        return f"{self.base_currency} {arrow} {self.intermediate_currency} {arrow} {self.quote_currency} {arrow} {self.base_currency}"
    
    @triangle_path.setter
    def triangle_path(self, value: str) -> None:
        """Set the triangle path."""
        self._triangle_path = value
    
    def __post_init__(self):
        """Calculate derived values after initialization."""
        if self.final_amount > 0 and self.initial_amount > 0:
            self.profit_amount = self.final_amount - self.initial_amount
            self.profit_percentage = (self.profit_amount / self.initial_amount) * 100
            self.net_profit = self.profit_amount - self.estimated_fees - self.estimated_slippage
    
    @property
    def is_profitable(self) -> bool:
        """Check if the opportunity is profitable after all costs."""
        return self.net_profit > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert opportunity to dictionary for logging/serialization."""
        return {
            'triangle_path': self.triangle_path,
            'pairs': [self.pair1, self.pair2, self.pair3],
            'initial_amount': self.initial_amount,
            'final_amount': self.final_amount,
            'profit_percentage': round(self.profit_percentage, 6),
            'profit_amount': round(self.profit_amount, 6),
            'net_profit': round(self.net_profit, 6),
            'estimated_fees': round(self.estimated_fees, 6),
            'estimated_slippage': round(self.estimated_slippage, 6),
            'steps': [step.to_dict() for step in self.steps],
            'detected_at': self.detected_at.isoformat(),
            'status': self.status.value,
            'execution_time': self.execution_time
        }
    
    def __str__(self) -> str:
        return (f"Arbitrage: {self.triangle_path} | "
                f"Profit: {self.profit_percentage:.4f}% "
                f"({self.profit_amount:.6f} {self.base_currency}) | "
                f"Net: {self.net_profit:.6f} {self.base_currency}")