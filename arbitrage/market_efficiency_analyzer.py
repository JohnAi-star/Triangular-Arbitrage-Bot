#!/usr/bin/env python3
"""
Market Efficiency Analyzer
Analyzes why arbitrage opportunities are rare and suggests optimal trading times
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
import statistics
from dataclasses import dataclass

@dataclass
class MarketAnalysis:
    """Market efficiency analysis results"""
    exchange: str
    total_pairs_analyzed: int
    average_spread: float
    volatility_score: float
    liquidity_score: float
    arbitrage_potential: str
    best_trading_times: List[str]
    recommended_pairs: List[str]

class MarketEfficiencyAnalyzer:
    """Analyzes market conditions to find optimal arbitrage opportunities"""
    
    def __init__(self, exchange_manager):
        self.exchange_manager = exchange_manager
        self.logger = logging.getLogger('MarketAnalyzer')
        
    async def analyze_market_conditions(self) -> List[MarketAnalysis]:
        """Analyze current market conditions for arbitrage potential"""
        analyses = []
        
        for exchange_name, exchange in self.exchange_manager.exchanges.items():
            try:
                analysis = await self._analyze_exchange_efficiency(exchange_name, exchange)
                analyses.append(analysis)
                
                self.logger.info(f"📊 {exchange_name.upper()} Market Analysis:")
                self.logger.info(f"   Average Spread: {analysis.average_spread:.4f}%")
                self.logger.info(f"   Volatility Score: {analysis.volatility_score:.2f}/10")
                self.logger.info(f"   Liquidity Score: {analysis.liquidity_score:.2f}/10")
                self.logger.info(f"   Arbitrage Potential: {analysis.arbitrage_potential}")
                self.logger.info(f"   Best Times: {', '.join(analysis.best_trading_times)}")
                self.logger.info(f"   Recommended Pairs: {', '.join(analysis.recommended_pairs[:5])}")
                
            except Exception as e:
                self.logger.error(f"Error analyzing {exchange_name}: {e}")
        
        return analyses
    
    async def _analyze_exchange_efficiency(self, exchange_name: str, exchange) -> MarketAnalysis:
        """Analyze efficiency of a specific exchange"""
        try:
            # Get ticker data
            tickers = await exchange.fetch_tickers()
            
            if not tickers:
                return MarketAnalysis(
                    exchange=exchange_name,
                    total_pairs_analyzed=0,
                    average_spread=0.0,
                    volatility_score=0.0,
                    liquidity_score=0.0,
                    arbitrage_potential="Unknown",
                    best_trading_times=[],
                    recommended_pairs=[]
                )
            
            # Analyze spreads
            spreads = []
            volumes = []
            price_changes = []
            major_pairs = []
            
            for symbol, ticker in tickers.items():
                try:
                    bid = float(ticker.get('bid', 0))
                    ask = float(ticker.get('ask', 0))
                    volume = float(ticker.get('baseVolume', 0))
                    change = float(ticker.get('percentage', 0))
                    
                    if bid > 0 and ask > 0 and bid < ask:
                        spread = (ask - bid) / bid * 100
                        spreads.append(spread)
                        volumes.append(volume)
                        price_changes.append(abs(change))
                        
                        # Identify major pairs for arbitrage
                        if any(major in symbol for major in ['USDT', 'BTC', 'ETH', 'BNB']):
                            if volume > 1000:  # Good volume
                                major_pairs.append((symbol, spread, volume))
                                
                except (ValueError, TypeError):
                    continue
            
            # Calculate metrics
            avg_spread = statistics.mean(spreads) if spreads else 0
            volatility = statistics.mean(price_changes) if price_changes else 0
            avg_volume = statistics.mean(volumes) if volumes else 0
            
            # Score the market (0-10 scale)
            volatility_score = min(volatility / 2, 10)  # Higher volatility = more arbitrage
            liquidity_score = min(avg_volume / 10000, 10)  # Higher volume = better execution
            
            # Determine arbitrage potential
            if avg_spread > 0.5 and volatility_score > 3:
                potential = "HIGH - Good spreads and volatility"
            elif avg_spread > 0.3 and volatility_score > 2:
                potential = "MEDIUM - Moderate conditions"
            elif avg_spread > 0.1:
                potential = "LOW - Tight spreads, limited opportunities"
            else:
                potential = "VERY LOW - Highly efficient market"
            
            # Recommend best trading times (based on volatility patterns)
            best_times = self._get_optimal_trading_times(volatility_score)
            
            # Sort major pairs by arbitrage potential (high spread + high volume)
            major_pairs.sort(key=lambda x: x[1] * (x[2] / 10000), reverse=True)
            recommended_pairs = [pair[0] for pair in major_pairs[:10]]
            
            return MarketAnalysis(
                exchange=exchange_name,
                total_pairs_analyzed=len(spreads),
                average_spread=avg_spread,
                volatility_score=volatility_score,
                liquidity_score=liquidity_score,
                arbitrage_potential=potential,
                best_trading_times=best_times,
                recommended_pairs=recommended_pairs
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing {exchange_name}: {e}")
            return MarketAnalysis(
                exchange=exchange_name,
                total_pairs_analyzed=0,
                average_spread=0.0,
                volatility_score=0.0,
                liquidity_score=0.0,
                arbitrage_potential="Error",
                best_trading_times=[],
                recommended_pairs=[]
            )
    
    def _get_optimal_trading_times(self, volatility_score: float) -> List[str]:
        """Get optimal trading times based on market volatility"""
        if volatility_score >= 5:
            return ["Now", "High volatility period"]
        elif volatility_score >= 3:
            return ["Market open/close", "News events", "Weekend volatility"]
        else:
            return ["Major news events", "Market crashes", "Pump/dump periods"]
    
    async def suggest_profitable_strategies(self) -> Dict[str, Any]:
        """Suggest alternative profitable strategies when arbitrage is limited"""
        return {
            "strategies": [
                {
                    "name": "Grid Trading",
                    "description": "Profit from price oscillations in ranging markets",
                    "profit_potential": "0.5-2% per day",
                    "risk": "Medium",
                    "suitable_for": "Sideways markets"
                },
                {
                    "name": "DCA (Dollar Cost Averaging)",
                    "description": "Regular purchases to average down costs",
                    "profit_potential": "Long-term growth",
                    "risk": "Low",
                    "suitable_for": "Bull markets"
                },
                {
                    "name": "Momentum Trading",
                    "description": "Follow strong price trends",
                    "profit_potential": "2-10% per trade",
                    "risk": "High",
                    "suitable_for": "Trending markets"
                },
                {
                    "name": "Cross-Exchange Arbitrage",
                    "description": "Price differences between exchanges",
                    "profit_potential": "0.2-1% per trade",
                    "risk": "Medium",
                    "suitable_for": "Multiple exchange accounts"
                }
            ],
            "current_market_advice": "Modern exchanges are highly efficient. Consider alternative strategies or wait for high volatility periods."
        }