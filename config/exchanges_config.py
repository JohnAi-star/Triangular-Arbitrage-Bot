"""
Exchange configurations for multi-exchange arbitrage bot.
"""

SUPPORTED_EXCHANGES = {
    'binance': {
        'name': 'Binance',
        'class_name': 'binance',
        'fee_token': 'BNB',
        'fee_discount': 0.25,  # 25% discount with BNB
        'websocket_url': 'wss://stream.binance.com:9443/ws/',
        'zero_fee_pairs': [],
        'maker_fee': 0.001,
        'taker_fee': 0.001,
        'enabled': True
    },
    'bybit': {
        'name': 'Bybit',
        'class_name': 'bybit',
        'fee_token': 'BIT',
        'fee_discount': 0.10,
        'websocket_url': 'wss://stream.bybit.com/v5/public/spot',
        'zero_fee_pairs': [],
        'maker_fee': 0.001,
        'taker_fee': 0.001,
        'enabled': True
    },
    'kucoin': {
        'name': 'KuCoin',
        'class_name': 'kucoin',
        'fee_token': 'KCS',
        'fee_discount': 0.20,
        'websocket_url': 'wss://ws-api.kucoin.com/endpoint',
        'zero_fee_pairs': ['BTC/ETH', 'ETH/BTC'],  # Example zero-fee pairs
        'maker_fee': 0.001,
        'taker_fee': 0.001,
        'enabled': True
    },
    'coinbase': {
        'name': 'Coinbase Pro',
        'class_name': 'coinbasepro',
        'fee_token': None,
        'fee_discount': 0.0,
        'websocket_url': 'wss://ws-feed.pro.coinbase.com',
        'zero_fee_pairs': [],
        'maker_fee': 0.005,
        'taker_fee': 0.005,
        'enabled': True
    },
    'kraken': {
        'name': 'Kraken',
        'class_name': 'kraken',
        'fee_token': None,
        'fee_discount': 0.0,
        'websocket_url': 'wss://ws.kraken.com',
        'zero_fee_pairs': [],
        'maker_fee': 0.0016,
        'taker_fee': 0.0026,
        'enabled': True
    },
    'gate': {
        'name': 'Gate.io',
        'class_name': 'gateio',
        'fee_token': 'GT',
        'fee_discount': 0.15,
        'websocket_url': 'wss://api.gateio.ws/ws/v4/',
        'zero_fee_pairs': [],
        'maker_fee': 0.002,
        'taker_fee': 0.002,
        'enabled': True
    },
    'coinex': {
        'name': 'CoinEx',
        'class_name': 'coinex',
        'fee_token': 'CET',
        'fee_discount': 0.20,
        'websocket_url': 'wss://socket.coinex.com/',
        'zero_fee_pairs': [],
        'maker_fee': 0.002,
        'taker_fee': 0.002,
        'enabled': True
    },
    'htx': {
        'name': 'HTX (Huobi)',
        'class_name': 'htx',
        'fee_token': 'HT',
        'fee_discount': 0.20,
        'websocket_url': 'wss://api.huobi.pro/ws',
        'zero_fee_pairs': [],
        'maker_fee': 0.002,
        'taker_fee': 0.002,
        'enabled': True
    },
    'mexc': {
        'name': 'MEXC',
        'class_name': 'mexc',
        'fee_token': 'MX',
        'fee_discount': 0.20,
        'websocket_url': 'wss://wbs.mexc.com/ws',
        'zero_fee_pairs': [],
        'maker_fee': 0.002,
        'taker_fee': 0.002,
        'enabled': True
    },
    'poloniex': {
        'name': 'Poloniex',
        'class_name': 'poloniex',
        'fee_token': None,
        'fee_discount': 0.0,
        'websocket_url': 'wss://ws.poloniex.com/ws/public',
        'zero_fee_pairs': [],
        'maker_fee': 0.00125,
        'taker_fee': 0.00125,
        'enabled': True
    },
    'probit': {
        'name': 'ProBit Global',
        'class_name': 'probit',
        'fee_token': 'PROB',
        'fee_discount': 0.25,
        'websocket_url': 'wss://api.probit.com/api/exchange/v1/ws',
        'zero_fee_pairs': [],
        'maker_fee': 0.002,
        'taker_fee': 0.002,
        'enabled': True
    },
    'hitbtc': {
        'name': 'HitBTC',
        'class_name': 'hitbtc',
        'fee_token': None,
        'fee_discount': 0.0,
        'websocket_url': 'wss://api.hitbtc.com/api/3/ws/public',
        'zero_fee_pairs': [],
        'maker_fee': 0.001,
        'taker_fee': 0.002,
        'enabled': True
    }
}

# Priority currencies for triangle detection
PRIORITY_CURRENCIES = ['USDT', 'BTC', 'ETH', 'BNB', 'USDC', 'BUSD']

# Minimum liquidity requirements
MIN_LIQUIDITY_USD = 10000  # $10,000 minimum liquidity

# Maximum number of triangles to monitor per exchange
MAX_TRIANGLES_PER_EXCHANGE = 100