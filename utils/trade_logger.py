"""
Enhanced trade logging system with comprehensive tracking.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from models.trade_log import TradeLog, TradeStepLog, TradeStatus, TradeDirection
from utils.logger import setup_logger

class TradeLogger:
    """Enhanced trade logger with detailed tracking and WebSocket broadcasting."""
    
    def __init__(self, websocket_manager=None):
        self.logger = setup_logger('TradeLogger')
        self.websocket_manager = websocket_manager
        self.trade_logs: List[TradeLog] = []
        
        # Ensure logs directory exists
        Path('logs').mkdir(exist_ok=True)
        
        # Load existing trade logs
        self._load_existing_logs()
    
    def _load_existing_logs(self):
        """Load existing trade logs from file."""
        try:
            log_file = Path('logs/detailed_trades.json')
            if log_file.exists():
                with open(log_file, 'r') as f:
                    data = json.load(f)
                    # Keep only the last 1000 trades to prevent memory issues
                    self.trade_logs = data[-1000:]
                self.logger.info(f"Loaded {len(self.trade_logs)} existing trade logs")
        except Exception as e:
            self.logger.error(f"Error loading existing trade logs: {e}")
            self.trade_logs = []
    
    def _save_logs(self):
        """Save trade logs to file."""
        try:
            log_file = Path('logs/detailed_trades.json')
            with open(log_file, 'w', encoding='utf-8') as f:
                # Convert trade logs to dict format safely
                trade_data = []
                for log in self.trade_logs:
                    if hasattr(log, 'to_dict'):
                        trade_data.append(log.to_dict())
                    elif isinstance(log, dict):
                        trade_data.append(log)
                    else:
                        # Convert object to dict manually
                        trade_data.append({
                            'trade_id': getattr(log, 'trade_id', 'unknown'),
                            'timestamp': getattr(log, 'timestamp', datetime.now()).isoformat() if hasattr(getattr(log, 'timestamp', None), 'isoformat') else str(getattr(log, 'timestamp', datetime.now())),
                            'exchange': getattr(log, 'exchange', 'unknown'),
                            'status': getattr(log, 'status', 'unknown'),
                            'net_pnl': getattr(log, 'net_pnl', 0.0)
                        })
                json.dump(trade_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving trade logs: {e}")
    
    async def log_trade(self, trade_log: TradeLog):
        """Log a completed trade with full details."""
        try:
            # Add to memory
            self.trade_logs.append(trade_log)
            
            # Keep only last 1000 trades in memory
            if len(self.trade_logs) > 1000:
                self.trade_logs = self.trade_logs[-1000:]
            
            # Log to console
            self.logger.info(trade_log.to_log_string())
            
            # Save to file
            self._save_logs()
            
            # Broadcast via WebSocket
            await self._broadcast_trade_update(trade_log)
            
            # Log detailed steps
            for step in trade_log.steps:
                self.logger.debug(f"  Step {step.step_number}: {step.direction.value.upper()} "
                                f"{step.actual_quantity:.6f} {step.symbol} at {step.actual_price:.8f} "
                                f"(expected {step.expected_price:.8f}) | "
                                f"Fees: {step.fees_paid:.6f} | "
                                f"Slippage: {step.slippage_percentage:.4f}% | "
                                f"Duration: {step.execution_time_ms:.0f}ms")
            
        except Exception as e:
            self.logger.error(f"Error logging trade: {e}")
    
    async def _broadcast_trade_update(self, trade_log: TradeLog):
        """Broadcast trade update via WebSocket."""
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                await self.websocket_manager.broadcast('trade_executed', {
                    'type': 'trade_log',
                    'data': trade_log.to_dict()
                })
                self.logger.debug(f"Broadcasted trade {trade_log.trade_id} via WebSocket")
            except Exception as e:
                self.logger.error(f"Error broadcasting trade update: {e}")
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trades for UI display."""
        recent_trades = self.trade_logs[-limit:] if self.trade_logs else []
        return [trade.to_dict() for trade in reversed(recent_trades)]
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive trade statistics."""
        if not self.trade_logs:
            return {
                'total_trades': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'success_rate': 0.0,
                'total_profit': 0.0,
                'total_fees': 0.0,
                'average_duration_ms': 0.0,
                'best_trade': None,
                'worst_trade': None
            }
        
        successful_trades = [t for t in self.trade_logs if t.status == TradeStatus.SUCCESS]
        failed_trades = [t for t in self.trade_logs if t.status == TradeStatus.FAILED]
        
        total_profit = sum(t.net_pnl for t in self.trade_logs)
        total_fees = sum(t.total_fees_paid for t in self.trade_logs)
        avg_duration = sum(t.total_duration_ms for t in self.trade_logs) / len(self.trade_logs)
        
        # Find best and worst trades
        profitable_trades = [t for t in self.trade_logs if t.net_pnl > 0]
        loss_trades = [t for t in self.trade_logs if t.net_pnl < 0]
        
        best_trade = max(profitable_trades, key=lambda t: t.net_pnl) if profitable_trades else None
        worst_trade = min(loss_trades, key=lambda t: t.net_pnl) if loss_trades else None
        
        return {
            'total_trades': len(self.trade_logs),
            'successful_trades': len(successful_trades),
            'failed_trades': len(failed_trades),
            'success_rate': (len(successful_trades) / len(self.trade_logs)) * 100,
            'total_profit': total_profit,
            'total_fees': total_fees,
            'average_duration_ms': avg_duration,
            'best_trade': best_trade.to_dict() if best_trade else None,
            'worst_trade': worst_trade.to_dict() if worst_trade else None
        }

# Global trade logger instance
_trade_logger_instance = None

def get_trade_logger(websocket_manager=None) -> TradeLogger:
    """Get or create the global trade logger instance."""
    global _trade_logger_instance
    if _trade_logger_instance is None:
        _trade_logger_instance = TradeLogger(websocket_manager)
        print(f"✅ TradeLogger initialized with WebSocket manager: {websocket_manager is not None}")
    elif websocket_manager and not _trade_logger_instance.websocket_manager:
        _trade_logger_instance.websocket_manager = websocket_manager
        print(f"✅ TradeLogger WebSocket manager updated: {websocket_manager is not None}")
    return _trade_logger_instance