"""
Enhanced trade logging system with comprehensive tracking for both triangular and spot-futures arbitrage.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from models.trade_log import TradeLog, TradeStepLog, TradeStatus, TradeDirection
from utils.logger import setup_logger

class TradeLogger:
    """Enhanced trade logger with detailed tracking and WebSocket broadcasting for all trade types."""
    
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
        """Log a completed triangular arbitrage trade with full details."""
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
    
    async def log_spot_futures_trade(self, trade_data: dict):
        """Log spot-futures arbitrage trade opening"""
        try:
            log_entry = {
                'type': 'spot_futures_open',
                'position_id': trade_data['position_id'],
                'symbol': trade_data['symbol'],
                'direction': trade_data['direction'],
                'amount': trade_data['amount'],
                'entry_spread': trade_data['entry_spread'],
                'timestamp': trade_data.get('timestamp', datetime.now().isoformat()),
                'spot_order': trade_data.get('spot_order'),
                'futures_order': trade_data.get('futures_order'),
                'status': 'open'
            }
            
            self.logger.info(f"📊 SPOT-FUTURES OPEN: {trade_data['position_id']} | "
                           f"{trade_data['symbol']} | {trade_data['direction']} | "
                           f"Spread: {trade_data['entry_spread']:.4f}% | "
                           f"Amount: ${trade_data['amount']:.2f}")
            
            # Save to detailed trades
            await self._save_spot_futures_log(log_entry)
            
            # Broadcast via WebSocket
            await self._broadcast_spot_futures_update('position_opened', log_entry)
                
        except Exception as e:
            self.logger.error(f"Error logging spot-futures trade: {e}")

    async def log_spot_futures_close(self, close_data: dict):
        """Log spot-futures position closure"""
        try:
            log_entry = {
                'type': 'spot_futures_close',
                'position_id': close_data['position_id'],
                'exit_spread': close_data['exit_spread'],
                'pnl_percentage': close_data.get('pnl_percentage', 0),
                'pnl_amount': close_data.get('pnl_amount', 0),
                'timestamp': datetime.now().isoformat(),
                'spot_close': close_data.get('spot_close'),
                'futures_close': close_data.get('futures_close'),
                'status': 'closed'
            }
            
            pnl_percentage = close_data.get('pnl_percentage', 0)
            pnl_amount = close_data.get('pnl_amount', 0)
            status_emoji = "✅" if pnl_amount > 0 else "❌"
            
            self.logger.info(f"📊 SPOT-FUTURES CLOSE: {close_data['position_id']} | "
                           f"PnL: {pnl_percentage:.4f}% | "
                           f"Amount: ${pnl_amount:.4f} {status_emoji}")
            
            # Save to detailed trades
            await self._save_spot_futures_log(log_entry)
            
            # Broadcast via WebSocket
            await self._broadcast_spot_futures_update('position_closed', log_entry)
                
        except Exception as e:
            self.logger.error(f"Error logging spot-futures close: {e}")

    async def _save_spot_futures_log(self, log_entry: dict):
        """Save spot-futures log to file"""
        try:
            log_file = Path('logs/spot_futures_trades.json')
            
            # Load existing logs
            existing_logs = []
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)
            
            # Add new log
            existing_logs.append(log_entry)
            
            # Keep only last 500 entries
            if len(existing_logs) > 500:
                existing_logs = existing_logs[-500:]
            
            # Save back to file
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving spot-futures log: {e}")

    async def _broadcast_trade_update(self, trade_log: TradeLog):
        """Broadcast triangular arbitrage trade update via WebSocket."""
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                await self.websocket_manager.broadcast('trade_executed', {
                    'type': 'trade_log',
                    'data': trade_log.to_dict()
                })
                self.logger.debug(f"Broadcasted triangular trade {trade_log.trade_id} via WebSocket")
            except Exception as e:
                self.logger.error(f"Error broadcasting trade update: {e}")

    async def _broadcast_spot_futures_update(self, update_type: str, data: dict):
        """Broadcast spot-futures update via WebSocket."""
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                await self.websocket_manager.broadcast('spot_futures_update', {
                    'type': update_type,
                    'data': data
                })
                self.logger.debug(f"Broadcasted spot-futures {update_type} via WebSocket")
            except Exception as e:
                self.logger.error(f"Error broadcasting spot-futures update: {e}")
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent triangular arbitrage trades for UI display."""
        recent_trades = self.trade_logs[-limit:] if self.trade_logs else []
        return [trade.to_dict() for trade in reversed(recent_trades)]
    
    def get_recent_spot_futures_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent spot-futures trades for UI display."""
        try:
            log_file = Path('logs/spot_futures_trades.json')
            if not log_file.exists():
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_trades = json.load(f)
            
            # Return most recent trades first
            return list(reversed(all_trades[-limit:]))
            
        except Exception as e:
            self.logger.error(f"Error getting recent spot-futures trades: {e}")
            return []
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive triangular arbitrage trade statistics."""
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

    def get_spot_futures_statistics(self) -> Dict[str, Any]:
        """Get spot-futures trading statistics"""
        try:
            log_file = Path('logs/spot_futures_trades.json')
            if not log_file.exists():
                return {
                    'total_trades': 0,
                    'profitable_trades': 0,
                    'total_pnl': 0.0,
                    'win_rate': 0.0,
                    'avg_profit': 0.0,
                    'total_fees_estimated': 0.0
                }
            
            with open(log_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            
            closed_trades = [t for t in trades if t.get('type') == 'spot_futures_close']
            profitable_trades = [t for t in closed_trades if t.get('pnl_amount', 0) > 0]
            
            total_pnl = sum(t.get('pnl_amount', 0) for t in closed_trades)
            total_fees_estimated = len(closed_trades) * 0.12  # Estimated $0.12 per trade
            win_rate = (len(profitable_trades) / len(closed_trades)) * 100 if closed_trades else 0
            
            return {
                'total_trades': len(closed_trades),
                'profitable_trades': len(profitable_trades),
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'avg_profit': total_pnl / len(closed_trades) if closed_trades else 0,
                'total_fees_estimated': total_fees_estimated
            }
            
        except Exception as e:
            self.logger.error(f"Error getting spot-futures statistics: {e}")
            return {
                'total_trades': 0,
                'profitable_trades': 0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'total_fees_estimated': 0.0
            }

    def get_combined_statistics(self) -> Dict[str, Any]:
        """Get combined statistics for both triangular and spot-futures arbitrage"""
        triangular_stats = self.get_trade_statistics()
        spot_futures_stats = self.get_spot_futures_statistics()
        
        total_profit = triangular_stats['total_profit'] + spot_futures_stats['total_pnl']
        total_trades = triangular_stats['total_trades'] + spot_futures_stats['total_trades']
        total_fees = triangular_stats['total_fees'] + spot_futures_stats['total_fees_estimated']
        
        return {
            'combined': {
                'total_profit': total_profit,
                'total_trades': total_trades,
                'total_fees': total_fees,
                'net_profit': total_profit - total_fees
            },
            'triangular_arbitrage': triangular_stats,
            'spot_futures_arbitrage': spot_futures_stats
        }

    def get_active_spot_futures_positions(self) -> List[Dict[str, Any]]:
        """Get currently active spot-futures positions"""
        try:
            log_file = Path('logs/spot_futures_trades.json')
            if not log_file.exists():
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_trades = json.load(f)
            
            # Filter for open positions
            open_positions = [
                trade for trade in all_trades 
                if trade.get('type') == 'spot_futures_open' 
                and trade.get('status') == 'open'
            ]
            
            # Check if they have been closed
            closed_positions = {
                trade['position_id'] for trade in all_trades 
                if trade.get('type') == 'spot_futures_close'
            }
            
            # Return only positions that haven't been closed
            active_positions = [
                pos for pos in open_positions 
                if pos['position_id'] not in closed_positions
            ]
            
            return active_positions
            
        except Exception as e:
            self.logger.error(f"Error getting active spot-futures positions: {e}")
            return []

    async def log_arbitrage_opportunity(self, opportunity_data: dict):
        """Log arbitrage opportunity detection (for both triangular and spot-futures)"""
        try:
            log_entry = {
                'type': 'arbitrage_opportunity',
                'strategy': opportunity_data.get('strategy', 'unknown'),
                'symbol': opportunity_data.get('symbol', 'unknown'),
                'profit_percentage': opportunity_data.get('profit_percentage', 0),
                'timestamp': datetime.now().isoformat(),
                'details': opportunity_data.get('details', {})
            }
            
            self.logger.info(f"🎯 ARBITRAGE OPPORTUNITY: {opportunity_data.get('strategy', 'unknown')} | "
                           f"{opportunity_data.get('symbol', 'unknown')} | "
                           f"Profit: {opportunity_data.get('profit_percentage', 0):.4f}%")
            
            # Save to opportunity log
            await self._save_opportunity_log(log_entry)
            
            # Broadcast via WebSocket
            if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
                await self.websocket_manager.broadcast('arbitrage_opportunity', {
                    'type': 'opportunity_detected',
                    'data': log_entry
                })
                
        except Exception as e:
            self.logger.error(f"Error logging arbitrage opportunity: {e}")

    async def _save_opportunity_log(self, log_entry: dict):
        """Save arbitrage opportunity log to file"""
        try:
            log_file = Path('logs/arbitrage_opportunities.json')
            
            # Load existing logs
            existing_logs = []
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    existing_logs = json.load(f)
            
            # Add new log
            existing_logs.append(log_entry)
            
            # Keep only last 1000 entries
            if len(existing_logs) > 1000:
                existing_logs = existing_logs[-1000:]
            
            # Save back to file
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving opportunity log: {e}")

    def get_recent_opportunities(self, limit: int = 20, strategy: str = None) -> List[Dict[str, Any]]:
        """Get recent arbitrage opportunities"""
        try:
            log_file = Path('logs/arbitrage_opportunities.json')
            if not log_file.exists():
                return []
            
            with open(log_file, 'r', encoding='utf-8') as f:
                all_opportunities = json.load(f)
            
            # Filter by strategy if specified
            if strategy:
                filtered_opportunities = [
                    opp for opp in all_opportunities 
                    if opp.get('strategy') == strategy
                ]
            else:
                filtered_opportunities = all_opportunities
            
            # Return most recent first
            return list(reversed(filtered_opportunities[-limit:]))
            
        except Exception as e:
            self.logger.error(f"Error getting recent opportunities: {e}")
            return []

    def cleanup_old_logs(self, days_old: int = 30):
        """Clean up log files older than specified days"""
        try:
            log_dir = Path('logs')
            current_time = datetime.now().timestamp()
            
            for log_file in log_dir.glob('*.json'):
                # Check if file is older than specified days
                if log_file.stat().st_mtime < current_time - (days_old * 86400):
                    log_file.unlink()
                    self.logger.info(f"Cleaned up old log file: {log_file}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {e}")

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