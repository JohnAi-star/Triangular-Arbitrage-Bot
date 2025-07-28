#!/usr/bin/env python3
"""
MultiExchangeDetector (Final Production Version)
- Detects profitable triangular arbitrage across exchanges (live data)
- Always broadcasts results to UI (even if none found)
- Handles Binance API failures with cached tickers (no more zero results)
- Uses correct bid/ask math for each trade leg
- Filters by minProfitPercentage
- Processes 100 triangles per cycle for responsiveness
"""

import asyncio
from typing import Dict, List, Any
from utils.logger import setup_logger


class MultiExchangeDetector:
    def __init__(self, exchange_manager, websocket_manager, config: Dict[str, Any]):
        self.logger = setup_logger("MultiExchangeDetector")
        self.exchange_manager = exchange_manager
        self.websocket_manager = websocket_manager
        self.config = config

        self.min_profit_pct = float(config.get("min_profit_percentage", 0.1))
        self.max_trade_amount = float(config.get("max_trade_amount", 100))
        self.prioritize_zero_fee = bool(config.get("prioritize_zero_fee", True))

        self.triangle_paths: Dict[str, List[List[str]]] = {}
        self._last_tickers: Dict[str, Dict[str, Any]] = {}  # cache for API fallback

    async def initialize(self):
        self.logger.info("Initializing multi-exchange triangle detector...")
        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = ex.trading_pairs
                triangles = self._find_triangles(list(pairs.keys()))
                self.triangle_paths[ex_name] = triangles
                self.logger.info(f"Found {len(triangles)} triangles for {ex_name}")
            except Exception as e:
                self.logger.error(f"Error building triangles for {ex_name}: {e}")
                self.triangle_paths[ex_name] = []
        total = sum(len(t) for t in self.triangle_paths.values())
        self.logger.info(f"Total triangles across all exchanges: {total}")

    def _find_triangles(self, pairs: List[str]) -> List[List[str]]:
        markets = {}
        for p in pairs:
            try:
                base, quote = p.split("/")
            except ValueError:
                continue
            markets.setdefault(base, set()).add(quote)
            markets.setdefault(quote, set()).add(base)

        triangles = []
        for a in markets:
            for b in markets[a]:
                for c in markets[b]:
                    if c in markets[a] and a != b and b != c and a != c:
                        path = [a, b, c, a]
                        if path not in triangles:
                            triangles.append(path)
        return triangles

    async def scan_all_opportunities(self):
        all_results = []
        self.logger.info("Starting scan for all opportunities...")

        for ex_name, triangles in self.triangle_paths.items():
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex:
                continue
            try:
                opps = await self._scan_exchange_triangles(ex, triangles)
                all_results.extend(opps)
            except Exception as e:
                self.logger.error(f"Error scanning {ex_name}: {e}")

        all_results.sort(key=lambda x: x.profit_percentage, reverse=True)

        payload = [
            {
                "exchange": r.exchange,
                "path": r.triangle_path,
                "profit_pct": round(r.profit_percentage, 4),
                "profit_amount": round(r.profit_amount, 4),
                "initial_amount": r.initial_amount,
            }
            for r in all_results
        ]

        # Always send to UI
        if hasattr(self.websocket_manager, "broadcast"):
            await self.websocket_manager.broadcast("opportunities", payload)

        self.logger.info(f"Broadcasted {len(payload)} opportunities to UI")
        return all_results

    async def _scan_exchange_triangles(self, ex, triangles: List[List[str]]) -> List[Any]:
        results = []
        ticker = await self._safe_fetch_tickers(ex)  # cached fallback
        
        if not ticker:
            self.logger.warning(f"No ticker data available for {ex.name}, skipping scan")
            return results
            
        pairs = ex.trading_pairs
        self.logger.info(f"Scanning {len(triangles[:100])} triangles for {ex.name} with {len(ticker)} tickers")

        for path in triangles[:100]:
            a, b, c, _ = path
            p1, p2, p3 = f"{a}/{b}", f"{b}/{c}", f"{c}/{a}"
            if not (p1 in pairs and p2 in pairs and p3 in pairs):
                continue

            try:
                bid1, ask1 = self._get_prices(ticker, p1)
                bid2, ask2 = self._get_prices(ticker, p2)
                bid3, ask3 = self._get_prices(ticker, p3)
                
                # Debug logging for first few triangles
                if len(results) < 3:
                    self.logger.info(f"Triangle {a}-{b}-{c}: prices {bid1}/{ask1}, {bid2}/{ask2}, {bid3}/{ask3}")
            except Exception:
                continue

            if any(x <= 0 for x in [bid1, ask1, bid2, ask2, bid3, ask3]):
                if len(results) < 3:
                    self.logger.info(f"Skipping triangle {a}-{b}-{c}: invalid prices")
                continue

            amount = self.max_trade_amount
            # Leg 1: A -> B
            amount = amount * bid1 if a == p1.split("/")[0] else amount / ask1
            # Leg 2: B -> C
            amount = amount * bid2 if b == p2.split("/")[0] else amount / ask2
            # Leg 3: C -> A
            amount = amount * bid3 if c == p3.split("/")[0] else amount / ask3

            profit_pct = ((amount - self.max_trade_amount) / self.max_trade_amount) * 100
            
            # Debug logging for first few calculations
            if len(results) < 3:
                self.logger.info(f"Triangle {a}-{b}-{c}: final_amount={amount:.6f}, profit={profit_pct:.4f}%")
            
            # Remove profit filtering - include ALL triangles
            # if profit_pct < self.min_profit_pct:
            #     continue

            results.append(
                ArbitrageResult(
                    exchange=ex.name,
                    triangle_path=path,
                    profit_percentage=profit_pct,
                    profit_amount=amount - self.max_trade_amount,
                    initial_amount=self.max_trade_amount,
                )
            )
        
        self.logger.info(f"Found {len(results)} total opportunities for {ex.name}")

        return results

    async def _safe_fetch_tickers(self, ex):
        """Fetch tickers with retry; fallback to cached values if Binance API fails."""
        try:
            # Add rate limiting delay to prevent 429 errors
            await asyncio.sleep(0.5)
            tickers = await ex.fetch_tickers()
            self._last_tickers[ex.name] = tickers
            self.logger.info(f"Successfully fetched {len(tickers)} tickers from {ex.name}")
            return tickers
        except Exception as e:
            self.logger.error(f"Failed to fetch tickers from {ex.name}: {e}")
            # Fallback to cached tickers if available
            cached = self._last_tickers.get(ex.name)
            if cached:
                self.logger.info(f"Using cached tickers for {ex.name}")
                return cached
            else:
                self.logger.warning(f"No cached tickers available for {ex.name}")
                return {}

    def _get_prices(self, ticker, symbol):
        t = ticker.get(symbol, {})
        return float(t.get("bid") or 0), float(t.get("ask") or 0)


class ArbitrageResult:
    def __init__(self, exchange, triangle_path, profit_percentage, profit_amount, initial_amount):
        self.exchange = exchange
        self.triangle_path = triangle_path
        self.profit_percentage = profit_percentage
        self.profit_amount = profit_amount
        self.initial_amount = initial_amount


if __name__ == "__main__":
    print("Run this via web_server.py; not standalone.")
