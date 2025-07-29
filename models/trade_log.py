import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
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

class TradeStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class TradeDirection(Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class TradeStepLog:
    """Detailed log for each step in a triangular arbitrage trade."""
    step_number: int
    symbol: str
    direction: TradeDirection
    expected_price: float
    actual_price: float
    expected_quantity: float
    actual_quantity: float
    expected_amount_out: float
    actual_amount_out: float
    fees_paid: float
    execution_time_ms: float
    slippage_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_number': self.step_number,
            'symbol': self.symbol,
            'direction': self.direction.value,
            'expected_price': self.expected_price,
            'actual_price': self.actual_price,
            'expected_quantity': self.expected_quantity,
            'actual_quantity': self.actual_quantity,
            'expected_amount_out': self.expected_amount_out,
            'actual_amount_out': self.actual_amount_out,
            'fees_paid': self.fees_paid,
            'execution_time_ms': self.execution_time_ms,
            'slippage_percentage': self.slippage_percentage
        }

@dataclass
class TradeLog:
    """Comprehensive log for a complete triangular arbitrage trade."""
    trade_id: str
    timestamp: datetime
    exchange: str
    triangle_path: List[str]
    status: TradeStatus
    
    # Entry/Exit amounts
    initial_amount: float
    final_amount: float
    base_currency: str
    
    # Expected vs Actual
    expected_profit_amount: float
    expected_profit_percentage: float
    actual_profit_amount: float
    actual_profit_percentage: float
    
    # Fees and costs
    total_fees_paid: float
    total_slippage: float
    net_pnl: float
    
    # Timing
    total_duration_ms: float
    
    # Detailed steps
    steps: List[TradeStepLog] = field(default_factory=list)
    
    # Error information (if failed)
    error_message: Optional[str] = None
    failed_at_step: Optional[int] = None
    
    def __post_init__(self):
        """Calculate derived values."""
        if self.final_amount > 0 and self.initial_amount > 0:
            self.actual_profit_amount = self.final_amount - self.initial_amount
            self.actual_profit_percentage = (self.actual_profit_amount / self.initial_amount) * 100
            self.net_pnl = self.actual_profit_amount - self.total_fees_paid - self.total_slippage
    
    @property
    def is_profitable(self) -> bool:
        """Check if the trade was profitable."""
        return self.net_pnl > 0
    
    @property
    def success_rate_display(self) -> str:
        """Display success rate as emoji."""
        if self.status == TradeStatus.SUCCESS:
            return safe_unicode_text("✅")
        elif self.status == TradeStatus.FAILED:
            return safe_unicode_text("❌")
        else:
            return safe_unicode_text("🔁")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp.isoformat(),
            'exchange': self.exchange,
            'triangle_path': self.triangle_path,
            'status': self.status.value,
            'status_emoji': self.success_rate_display,
            
            # Entry/Exit
            'initial_amount': self.initial_amount,
            'final_amount': self.final_amount,
            'base_currency': self.base_currency,
            
            # Expected vs Actual
            'expected_profit_amount': self.expected_profit_amount,
            'expected_profit_percentage': self.expected_profit_percentage,
            'actual_profit_amount': self.actual_profit_amount,
            'actual_profit_percentage': self.actual_profit_percentage,
            
            # Fees and costs
            'total_fees_paid': self.total_fees_paid,
            'total_slippage': self.total_slippage,
            'net_pnl': self.net_pnl,
            
            # Timing
            'total_duration_ms': self.total_duration_ms,
            
            # Steps
            'steps': [step.to_dict() for step in self.steps],
            
            # Error info
            'error_message': self.error_message,
            'failed_at_step': self.failed_at_step
        }
    
    def to_log_string(self) -> str:
        """Convert to formatted log string."""
        status_emoji = self.success_rate_display
        profit_sign = "+" if self.net_pnl >= 0 else ""
        arrow = safe_unicode_text("→")
        
        return (
            f"{status_emoji} TRADE {self.trade_id} | "
            f"{self.exchange} | "
            f"{f' {arrow} '.join(self.triangle_path)} | "
            f"IN: {self.initial_amount:.6f} {self.base_currency} | "
            f"OUT: {self.final_amount:.6f} {self.base_currency} | "
            f"PnL: {profit_sign}{self.net_pnl:.6f} {self.base_currency} "
            f"({profit_sign}{self.actual_profit_percentage:.4f}%) | "
            f"Fees: {self.total_fees_paid:.6f} | "
            f"Duration: {self.total_duration_ms:.0f}ms"
        )