"""
Backtesting engine for triangular arbitrage strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass

from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
from utils.logger import setup_logger

@dataclass
class BacktestResult:
    """Results from a backtest run."""
    total_trades: int
    successful_trades: int
    total_profit: float
    total_fees: float
    success_rate: float
    average_profit_per_trade: float
    max_drawdown: float
    sharpe_ratio: float
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float

class BacktestEngine:
    """Engine for backtesting triangular arbitrage strategies."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = setup_logger('BacktestEngine')
        self.historical_data = {}
        self.results = []
        
    async def load_historical_data(self, exchange_id: str, symbols: List[str], 
                                 start_date: datetime, end_date: datetime) -> bool:
        """Load historical price data for backtesting."""
        try:
            self.logger.info(f"Loading historical data for {exchange_id}: {len(symbols)} symbols")
            
            # In a real implementation, you would load actual historical data
            # For this example, we'll generate synthetic data
            self.historical_data[exchange_id] = self._generate_synthetic_data(
                symbols, start_date, end_date
            )
            
            self.logger.info(f"Loaded {len(self.historical_data[exchange_id])} data points")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading historical data: {e}")
            return False
    
    def _generate_synthetic_data(self, symbols: List[str], 
                               start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate synthetic historical data for testing."""
        # Create time series
        time_range = pd.date_range(start=start_date, end=end_date, freq='1min')
        
        data = []
        for timestamp in time_range:
            for symbol in symbols:
                # Generate realistic price movements
                base_price = self._get_base_price(symbol)
                volatility = 0.02  # 2% volatility
                
                # Random walk with mean reversion
                price_change = np.random.normal(0, volatility * base_price)
                bid = base_price + price_change
                ask = bid * (1 + np.random.uniform(0.0001, 0.001))  # Spread
                
                data.append({
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'bid': bid,
                    'ask': ask,
                    'volume': np.random.uniform(1000, 10000)
                })
        
        return pd.DataFrame(data)
    
    def _get_base_price(self, symbol: str) -> float:
        """Get base price for a symbol (simplified)."""
        base_prices = {
            'BTC/USDT': 45000,
            'ETH/USDT': 3000,
            'BTC/ETH': 15,
            'BNB/USDT': 300,
            'BNB/BTC': 0.0067,
            'ETH/BNB': 10
        }
        return base_prices.get(symbol, 100)
    
    async def run_backtest(self, exchange_id: str, start_date: datetime, 
                          end_date: datetime, initial_balance: float = 10000) -> BacktestResult:
        """Run a backtest for the specified period."""
        try:
            self.logger.info(f"Starting backtest for {exchange_id} from {start_date} to {end_date}")
            
            if exchange_id not in self.historical_data:
                self.logger.error(f"No historical data loaded for {exchange_id}")
                return None
            
            data = self.historical_data[exchange_id]
            
            # Initialize backtest state
            current_balance = initial_balance
            trades = []
            balance_history = []
            
            # Group data by timestamp
            grouped_data = data.groupby('timestamp')
            
            for timestamp, group in grouped_data:
                # Create price snapshot
                price_snapshot = {}
                for _, row in group.iterrows():
                    price_snapshot[row['symbol']] = {
                        'bid': row['bid'],
                        'ask': row['ask'],
                        'volume': row['volume']
                    }
                
                # Detect arbitrage opportunities
                opportunities = await self._detect_opportunities_from_snapshot(
                    price_snapshot, current_balance
                )
                
                # Execute profitable opportunities
                for opportunity in opportunities:
                    if opportunity.is_profitable and opportunity.net_profit > 0:
                        trade_result = self._simulate_trade_execution(opportunity)
                        trades.append({
                            'timestamp': timestamp,
                            'opportunity': opportunity,
                            'result': trade_result
                        })
                        
                        if trade_result['success']:
                            current_balance += trade_result['profit']
                
                balance_history.append({
                    'timestamp': timestamp,
                    'balance': current_balance
                })
            
            # Calculate backtest results
            result = self._calculate_backtest_results(
                trades, balance_history, initial_balance, start_date, end_date
            )
            
            self.logger.info(f"Backtest completed: {result.total_trades} trades, "
                           f"{result.success_rate:.2f}% success rate, "
                           f"${result.total_profit:.2f} profit")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error running backtest: {e}")
            return None
    
    async def _detect_opportunities_from_snapshot(self, price_snapshot: Dict[str, Dict], 
                                                balance: float) -> List[ArbitrageOpportunity]:
        """Detect arbitrage opportunities from a price snapshot."""
        opportunities = []
        
        # Define common triangles
        triangles = [
            ('BTC', 'ETH', 'USDT'),
            ('BTC', 'BNB', 'USDT'),
            ('ETH', 'BNB', 'USDT')
        ]
        
        for base, intermediate, quote in triangles:
            pair1 = f"{base}/{intermediate}"
            pair2 = f"{intermediate}/{quote}"
            pair3 = f"{base}/{quote}"
            
            if all(pair in price_snapshot for pair in [pair1, pair2, pair3]):
                opportunity = self._calculate_triangle_profit_from_snapshot(
                    price_snapshot, base, intermediate, quote, 
                    min(balance * 0.1, self.config.get('max_trade_amount', 100))
                )
                
                if opportunity:
                    opportunities.append(opportunity)
        
        return opportunities
    
    def _calculate_triangle_profit_from_snapshot(self, price_snapshot: Dict[str, Dict],
                                               base: str, intermediate: str, quote: str,
                                               initial_amount: float) -> Optional[ArbitrageOpportunity]:
        """Calculate triangle profit from price snapshot."""
        try:
            pair1 = f"{base}/{intermediate}"
            pair2 = f"{intermediate}/{quote}"
            pair3 = f"{base}/{quote}"
            
            price1 = price_snapshot[pair1]
            price2 = price_snapshot[pair2]
            price3 = price_snapshot[pair3]
            
            # Calculate arbitrage path
            amount_after_step1 = initial_amount * price1['bid']
            amount_after_step2 = amount_after_step1 * price2['bid']
            final_amount = amount_after_step2 / price3['ask']
            
            # Create trade steps
            steps = [
                TradeStep(pair1, 'sell', initial_amount, price1['bid'], amount_after_step1),
                TradeStep(pair2, 'sell', amount_after_step1, price2['bid'], amount_after_step2),
                TradeStep(pair3, 'buy', amount_after_step2, price3['ask'], final_amount)
            ]
            
            # Estimate fees and slippage
            estimated_fees = initial_amount * 0.003  # 0.3% total fees
            estimated_slippage = initial_amount * 0.001  # 0.1% slippage
            
            opportunity = ArbitrageOpportunity(
                base_currency=base,
                intermediate_currency=intermediate,
                quote_currency=quote,
                pair1=pair1,
                pair2=pair2,
                pair3=pair3,
                steps=steps,
                initial_amount=initial_amount,
                final_amount=final_amount,
                estimated_fees=estimated_fees,
                estimated_slippage=estimated_slippage
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error calculating triangle profit: {e}")
            return None
    
    def _simulate_trade_execution(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Simulate trade execution with realistic constraints."""
        try:
            # Simulate execution with some randomness
            execution_success_rate = 0.95  # 95% success rate
            slippage_factor = np.random.uniform(0.8, 1.2)  # ±20% slippage variation
            
            success = np.random.random() < execution_success_rate
            
            if success:
                actual_slippage = opportunity.estimated_slippage * slippage_factor
                actual_profit = opportunity.net_profit - actual_slippage
                
                return {
                    'success': True,
                    'profit': actual_profit,
                    'fees': opportunity.estimated_fees,
                    'slippage': actual_slippage
                }
            else:
                return {
                    'success': False,
                    'profit': -opportunity.estimated_fees,  # Lost fees
                    'fees': opportunity.estimated_fees,
                    'slippage': 0
                }
                
        except Exception as e:
            self.logger.error(f"Error simulating trade execution: {e}")
            return {'success': False, 'profit': 0, 'fees': 0, 'slippage': 0}
    
    def _calculate_backtest_results(self, trades: List[Dict], balance_history: List[Dict],
                                  initial_balance: float, start_date: datetime, 
                                  end_date: datetime) -> BacktestResult:
        """Calculate comprehensive backtest results."""
        try:
            total_trades = len(trades)
            successful_trades = sum(1 for trade in trades if trade['result']['success'])
            
            total_profit = sum(trade['result']['profit'] for trade in trades)
            total_fees = sum(trade['result']['fees'] for trade in trades)
            
            success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
            avg_profit_per_trade = total_profit / total_trades if total_trades > 0 else 0
            
            # Calculate max drawdown
            balances = [item['balance'] for item in balance_history]
            peak = initial_balance
            max_drawdown = 0
            
            for balance in balances:
                if balance > peak:
                    peak = balance
                drawdown = (peak - balance) / peak
                max_drawdown = max(max_drawdown, drawdown)
            
            # Calculate Sharpe ratio (simplified)
            if len(balances) > 1:
                returns = np.diff(balances) / balances[:-1]
                sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            final_balance = balances[-1] if balances else initial_balance
            
            return BacktestResult(
                total_trades=total_trades,
                successful_trades=successful_trades,
                total_profit=total_profit,
                total_fees=total_fees,
                success_rate=success_rate,
                average_profit_per_trade=avg_profit_per_trade,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                start_date=start_date,
                end_date=end_date,
                initial_balance=initial_balance,
                final_balance=final_balance
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating backtest results: {e}")
            return None