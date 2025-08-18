import time
from typing import List, Dict, Any, Set, Tuple
from models.arbitrage_opportunity import ArbitrageOpportunity, TradeStep
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

class TriangleDetector:
    """Detects triangular arbitrage opportunities in near real-time."""

    def __init__(self, exchange: UnifiedExchange, config: Dict[str, Any]):
        self.exchange = exchange
        self.config = config
        self.logger = setup_logger('TriangleDetector')
        self.price_cache: Dict[str, Dict[str, float]] = {}
        self.require_usdt_anchor: bool = bool(self.config.get('require_usdt_anchor', True))
        self.max_triangles: int = int(self.config.get('max_triangles', 500))
        self.triangles: List[Tuple[str, str, str]] = []
        self._last_scan_time = 0
        self.scan_interval = self.config.get('scan_interval_ms', 100) / 1000  # default 100ms per cycle

    async def initialize(self) -> None:
        """Initialize detector by discovering trading pairs and building triangle list."""
        self.logger.info("Initializing triangle detector...")
        trading_pairs = await self.exchange.get_trading_pairs()
        self.triangles = self._find_triangles(trading_pairs)
        self.logger.info(f"Found {len(self.triangles)} valid triangular paths for {self.exchange.exchange_id}")

    def _find_triangles(self, pairs: List[str]) -> List[Tuple[str, str, str]]:
        """Build triangular combinations anchored to USDT and capped by config."""
        triangles: List[Tuple[str, str, str]] = []
        pair_map: Set[str] = set()
        usdt_coins: Set[str] = set()

        # Normalize and index pairs, collect USDT-quoted/base coins
        for pair in pairs:
            if '/' not in pair:
                continue
            base, quote = pair.split('/')
            norm = f"{base}/{quote}"
            rev = f"{quote}/{base}"
            pair_map.add(norm)
            pair_map.add(rev)
            if base == 'USDT' and quote != 'USDT':
                usdt_coins.add(quote)
            elif quote == 'USDT' and base != 'USDT':
                usdt_coins.add(base)

        # If not requiring USDT anchor, fallback to legacy (but still cap)
        if not getattr(self, 'require_usdt_anchor', True):
            currencies: Set[str] = set()
            for p in pairs:
                if '/' in p:
                    a, b = p.split('/')
                    currencies.update([a, b])
            for base in currencies:
                for mid in currencies:
                    if mid == base:
                        continue
                    for quote in currencies:
                        if quote in (base, mid):
                            continue
                        if (f"{base}/{mid}" in pair_map and
                            f"{mid}/{quote}" in pair_map and
                            f"{base}/{quote}" in pair_map):
                            triangles.append((base, mid, quote))
                            if len(triangles) >= getattr(self, 'max_triangles', 500):
                                return triangles
            return triangles

        # USDT-anchored triangles: USDT -> CoinA -> CoinB -> USDT
        coins = sorted(usdt_coins)
        # Build unique pairs (CoinA, CoinB) without duplicates
        for i in range(len(coins)):
            for j in range(i + 1, len(coins)):
                a = coins[i]
                b = coins[j]
                # Check cross-market exists between A and B
                if f"{a}/{b}" in pair_map or f"{b}/{a}" in pair_map:
                    triangles.append(('USDT', a, b))
                    if len(triangles) >= getattr(self, 'max_triangles', 500):
                        return triangles
        return triangles

    async def update_prices(self, price_data: Dict[str, Any]) -> None:
        """Update local price cache (called from websocket feed)."""
        if not price_data or 'data' not in price_data:
            return
        data = price_data['data']
        raw_symbol = data.get('s', '').upper()
        if not raw_symbol:
            return

        formatted_symbol = self._format_symbol(raw_symbol)
        try:
            bid = float(data.get('b', 0))
            ask = float(data.get('a', 0))
            if bid > 0 and ask > 0:
                self.price_cache[formatted_symbol] = {
                    'bid': bid,
                    'ask': ask,
                    'timestamp': data.get('E', int(time.time() * 1000))
                }
        except Exception:
            return

    def _format_symbol(self, symbol: str) -> str:
        """Convert raw symbol (e.g., BTCUSDT) to normalized pair (BTC/USDT)."""
        common_quotes = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
        for quote in common_quotes:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"
        return symbol

    async def scan_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Scan through all prebuilt triangles and detect profitable opportunities.
        Runs every `scan_interval` seconds (default 100ms).
        """
        now = time.time()
        if now - self._last_scan_time < self.scan_interval:
            return []  # Avoid overloading CPU with too many scans
        self._last_scan_time = now

        results: List[ArbitrageOpportunity] = []
        trade_amount = self.config.get('max_trade_amount', 100)
        min_profit = self.config.get('min_profit_percentage', 0.1)  # percent

        for base, mid, quote in self.triangles:
            try:
                opp = await self._calculate_triangle_profit(base, mid, quote, trade_amount)
                if opp and hasattr(opp, 'is_profitable') and hasattr(opp, 'profit_percentage'):
                    if opp.is_profitable and opp.profit_percentage >= min_profit:
                        results.append(opp)
            except Exception as e:
                self.logger.error(f"Error evaluating triangle {base}-{mid}-{quote}: {e}")
                continue

        return results

    async def _calculate_triangle_profit(
        self,
        base: str,
        mid: str,
        quote: str,
        initial_amount: float
    ) -> ArbitrageOpportunity:
        """Evaluate a single triangle path for profitability."""
        pair1, pair2, pair3 = f"{base}/{mid}", f"{mid}/{quote}", f"{base}/{quote}"

        p1, p2, p3 = self.price_cache.get(pair1), self.price_cache.get(pair2), self.price_cache.get(pair3)
        if not (p1 and p2 and p3):
            return None  # missing data

        if p1['bid'] <= 0 or p2['bid'] <= 0 or p3['ask'] <= 0:
            return None  # avoid division by zero or stale entries

        # Simulate trade path: BASE -> MID -> QUOTE -> BASE
        amount1 = initial_amount * p1['bid']  # sell BASE for MID
        step1 = TradeStep(pair1, 'sell', initial_amount, p1['bid'], amount1)

        amount2 = amount1 * p2['bid']  # sell MID for QUOTE
        step2 = TradeStep(pair2, 'sell', amount1, p2['bid'], amount2)

        final_amount = amount2 / p3['ask']  # buy BASE with QUOTE
        step3 = TradeStep(pair3, 'buy', amount2, p3['ask'], final_amount)

        _, taker_fee = await self.exchange.get_trading_fees(pair1)
        total_fees = (
            initial_amount * taker_fee +
            amount1 * taker_fee +
            amount2 * taker_fee
        )

        slippage_pct = self.config.get('max_slippage_percentage', 0.05) / 100
        est_slippage = initial_amount * slippage_pct

        opp = ArbitrageOpportunity(
            base_currency=base,
            intermediate_currency=mid,
            quote_currency=quote,
            pair1=pair1,
            pair2=pair2,
            pair3=pair3,
            steps=[step1, step2, step3],
            initial_amount=initial_amount,
            final_amount=final_amount,
            estimated_fees=total_fees,
            estimated_slippage=est_slippage
        )

        return opp
