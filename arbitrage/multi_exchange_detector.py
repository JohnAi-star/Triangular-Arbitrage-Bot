#!/usr/bin/env python3
"""
MultiExchangeDetector (Adjusted for Testing)
Detects triangular arbitrage opportunities across multiple exchanges.
Now:
- min_profit_pct lowered to 0.01% (shows even tiny profits for testing)
- Scans 1000 triangles per cycle (instead of 100)
"""

import asyncio
import math
from typing import Dict, List, Any
from utils.logger import setup_logger


class MultiExchangeDetector:
    def __init__(self, exchange_manager, config: Dict[str, Any]):
        self.logger = setup_logger("MultiExchangeDetector")
        self.exchange_manager = exchange_manager
        self.config = config

        # Config defaults (overridden here for testing visibility)
        self.min_profit_pct = float(config.get("min_profit_percentage", 0.01))  # lowered from 0.1%
        self.max_trade_amount = float(config.get("max_trade_amount", 100))
        self.prioritize_zero_fee = bool(config.get("prioritize_zero_fee", True))

        # Triangle storage
        self.triangle_paths: Dict[str, List[List[str]]] = {}

    async def initialize(self):
        """Precompute all triangle paths for each exchange."""
        self.logger.info("Initializing multi-exchange triangle detector...")

        for ex_name, ex in self.exchange_manager.exchanges.items():
            try:
                pairs = ex.trading_pairs
                triangles = self._find_triangles(list(pairs))
                self.triangle_paths[ex_name] = triangles
                self.logger.info(f"Found {len(triangles)} triangles for {ex_name}")
            except Exception as e:
                self.logger.error(f"Error building triangles for {ex_name}: {e}")
                self.triangle_paths[ex_name] = []

        total = sum(len(t) for t in self.triangle_paths.values())
        self.logger.info(f"Total triangles across all exchanges: {total}")

    def _find_triangles(self, pairs: List[str]) -> List[List[str]]:
        """Find all possible triangular arbitrage paths."""
        markets = {}
        for p in pairs:
            try:
                base, quote = p.split("/")
                markets.setdefault(base, set()).add(quote)
                markets.setdefault(quote, set()).add(base)
            except Exception:
                continue

        triangles = []
        for a in markets:
            for b in markets[a]:
                for c in markets[b]:
                    if c in markets[a] and a != b and b != c and a != c:
                        path = [a, b, c, a]
                        if path not in triangles:
                            triangles.append(path)
        return triangles

    async def scan_all_opportunities(self) -> List[Any]:
        """Scan all exchanges for profitable triangular arbitrage."""
        results = []
        self.logger.info("Starting scan for all opportunities...")

        for ex_name, triangles in self.triangle_paths.items():
            ex = self.exchange_manager.exchanges.get(ex_name)
            if not ex:
                continue

            try:
                opps = await self._scan_exchange_triangles(ex, triangles)
                results.extend(opps)
            except Exception as e:
                self.logger.error(f"Error scanning {ex_name}: {e}")

        return results

    async def _scan_exchange_triangles(self, ex, triangles: List[List[str]]) -> List[Any]:
        results = []
        ticker = await ex.fetch_tickers()
        pairs = ex.trading_pairs

        # Now scan first 1000 triangles per cycle (instead of 100)
        for path in triangles[:1000]:
            a, b, c, _ = path
            p1, p2, p3 = f"{a}/{b}", f"{b}/{c}", f"{c}/{a}"

            # Ensure all pairs exist (no inverted pairs)
            if not (p1 in pairs and p2 in pairs and p3 in pairs):
                continue

            try:
                price1 = float(ticker.get(p1, {}).get("bid") or 0)
                price2 = float(ticker.get(p2, {}).get("bid") or 0)
                price3 = float(ticker.get(p3, {}).get("bid") or 0)
            except Exception:
                continue

            # Skip invalid or zero prices
            if price1 <= 0 or price2 <= 0 or price3 <= 0:
                continue

            # Calculate profit percentage (strict mode)
            start_amount = self.max_trade_amount
            final_amount = start_amount * price1 * price2 * price3
            profit_pct = ((final_amount - start_amount) / start_amount) * 100

            # Skip if below threshold
            if profit_pct < self.min_profit_pct:
                continue

            profit_amt = final_amount - start_amount

            # Store valid result
            results.append(
                ArbitrageResult(
                    exchange=ex.name,
                    triangle_path=path,
                    profit_percentage=profit_pct,
                    profit_amount=profit_amt,
                    initial_amount=start_amount,
                )
            )

        return results


class ArbitrageResult:
    """Container for a single arbitrage opportunity."""
    def __init__(self, exchange, triangle_path, profit_percentage, profit_amount, initial_amount):
        self.exchange = exchange
        self.triangle_path = triangle_path
        self.profit_percentage = profit_percentage
        self.profit_amount = profit_amount
        self.initial_amount = initial_amount


if __name__ == "__main__":
    # Test run only
    print("Run this via web_server.py; not standalone.")
