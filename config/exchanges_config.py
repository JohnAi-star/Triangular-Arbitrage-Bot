"""
Exchange configurations for multi-exchange arbitrage bot with accurate fees and URLs (2025 Updated Version).
"""

SUPPORTED_EXCHANGES = {
    'binance': {
        'name': 'Binance',
        'class_name': 'binance',
        'api_url': 'https://api.binance.com',
        'websocket_url': 'wss://stream.binance.com:9443/ws',
        'ticker_endpoint': '/api/v3/ticker/price',
        'exchange_info_endpoint': '/api/v3/exchangeInfo',
        'fee_token': 'BNB',
        'fee_discount': 0.25,  # 25% discount with BNB
        'zero_fee_pairs': ['BTC/USDT', 'ETH/USDT'],  
        'maker_fee': 0.0010,   # 0.10%
        'taker_fee': 0.0010,   # 0.10%
        'maker_fee_with_token': 0.00075,  
        'taker_fee_with_token': 0.00075,
        'enabled': True,
        'requires_passphrase': False
    },
    'bybit': {
        'name': 'Bybit',
        'class_name': 'bybit',
        'api_url': 'https://api.bybit.com',
        'websocket_url': 'wss://stream.bybit.com/v5/public/spot',
        'ticker_endpoint': '/v5/market/tickers',
        'exchange_info_endpoint': '/v5/market/instruments-info',
        'fee_token': 'BIT',
        'fee_discount': 0.10,  
        'zero_fee_pairs': [],
        'maker_fee': 0.0010,   
        'taker_fee': 0.0010,   
        'maker_fee_with_token': 0.0009,  
        'taker_fee_with_token': 0.0009,
        'enabled': True,
        'requires_passphrase': False
    },
    'kucoin': {
        'name': 'KuCoin',
        'class_name': 'kucoin',
        'api_url': 'https://api.kucoin.com',
        'websocket_url': 'wss://ws-api-spot.kucoin.com',
        'ticker_endpoint': '/api/v1/market/allTickers',
        'exchange_info_endpoint': '/api/v1/symbols',
        'fee_token': 'KCS',
        'fee_discount': 0.20,  # 20% discount for KCS holders
        'zero_fee_pairs': ['BTC/USDT', 'ETH/USDT', 'KCS/USDT'],  # KuCoin zero-fee pairs
        'maker_fee': 0.0010,  # 0.10%
        'taker_fee': 0.0010,  # 0.10%
        'maker_fee_with_token': 0.0008,  # 0.08% with KCS
        'taker_fee_with_token': 0.0008,  # 0.08% with KCS for both maker and taker
        'enabled': True,
        'requires_passphrase': True,
        'timeout': 15,  # Increased timeout for KuCoin
        'rate_limit': 1000  # KuCoin rate limit
    },
    'coinbase': {
        'name': 'Coinbase Advanced',
        'class_name': 'coinbasepro',
        'api_url': 'https://api.exchange.coinbase.com',
        'websocket_url': 'wss://ws-feed.exchange.coinbase.com',
        'ticker_endpoint': '/products/ticker',
        'exchange_info_endpoint': '/products',
        'fee_token': None,
        'fee_discount': 0.0,
        'zero_fee_pairs': [],
        'maker_fee': 0.0040,   # 0.40% (volume-based, conservative base)
        'taker_fee': 0.0060,   # 0.60%
        'maker_fee_with_token': 0.0040,
        'taker_fee_with_token': 0.0060,
        'enabled': True,
        'requires_passphrase': True
    },
    'kraken': {
        'name': 'Kraken',
        'class_name': 'kraken',
        'api_url': 'https://api.kraken.com',
        'websocket_url': 'wss://ws.kraken.com',
        'ticker_endpoint': '/0/public/Ticker',
        'exchange_info_endpoint': '/0/public/AssetPairs',
        'fee_token': None,
        'fee_discount': 0.0,
        'zero_fee_pairs': [],
        'maker_fee': 0.0016,   
        'taker_fee': 0.0026,   
        'maker_fee_with_token': 0.0016,
        'taker_fee_with_token': 0.0026,
        'enabled': True,
        'requires_passphrase': False
    },
    'gate': {
        'name': 'Gate.io',
        'class_name': 'gate',
        'api_url': 'https://api.gateio.ws',
        'websocket_url': 'wss://api.gateio.ws/ws/v4/',
        'ticker_endpoint': '/api/v4/spot/tickers',
        'exchange_info_endpoint': '/api/v4/spot/currency_pairs',
        'fee_token': 'GT',
        'fee_discount': 0.55,  
        'zero_fee_pairs': [],
        'maker_fee': 0.0020,   
        'taker_fee': 0.0020,   
        'maker_fee_with_token': 0.0009,  
        'taker_fee_with_token': 0.0009,  
        'enabled': True,
        'requires_passphrase': False
    },
    'coinex': {
        'name': 'CoinEx',
        'class_name': 'coinex',
        'api_url': 'https://api.coinex.com',
        'websocket_url': 'wss://socket.coinex.com/',
        'ticker_endpoint': '/v1/market/ticker/all',
        'exchange_info_endpoint': '/v1/market/info',
        'fee_token': 'CET',
        'fee_discount': 0.10,  
        'zero_fee_pairs': [],
        'maker_fee': 0.0020,   
        'taker_fee': 0.0020,   
        'maker_fee_with_token': 0.0018,  
        'taker_fee_with_token': 0.0018,  
        'enabled': True,
        'requires_passphrase': False
    },
    'htx': {
        'name': 'HTX (Huobi)',
        'class_name': 'htx',
        'api_url': 'https://api.htx.com',
        'websocket_url': 'wss://api-aws.htx.com/ws',
        'ticker_endpoint': '/market/tickers',
        'exchange_info_endpoint': '/v2/settings/common/symbols',
        'fee_token': 'HT',
        'fee_discount': 0.20,  
        'zero_fee_pairs': [],
        'maker_fee': 0.0020,   
        'taker_fee': 0.0020,   
        'maker_fee_with_token': 0.0016,  
        'taker_fee_with_token': 0.0016,  
        'enabled': True,
        'requires_passphrase': False
    },
    'mexc': {
        'name': 'MEXC',
        'class_name': 'mexc',
        'api_url': 'https://api.mexc.com',
        'websocket_url': 'wss://wbs.mexc.com/ws',
        'ticker_endpoint': '/api/v3/ticker/24hr',
        'exchange_info_endpoint': '/api/v3/exchangeInfo',
        'fee_token': 'MX',
        'fee_discount': 0.10,  
        'zero_fee_pairs': ['BTC/USDT', 'ETH/USDT'],
        'maker_fee': 0.0000,   
        'taker_fee': 0.0010,   
        'maker_fee_with_token': 0.0000,
        'taker_fee_with_token': 0.0009,  
        'enabled': True,
        'requires_passphrase': False
    },
    'poloniex': {
        'name': 'Poloniex',
        'class_name': 'poloniex',
        'api_url': 'https://api.poloniex.com',
        'websocket_url': 'wss://ws.poloniex.com/ws/public',
        'ticker_endpoint': '/markets/ticker24h',
        'exchange_info_endpoint': '/markets',
        'fee_token': None,
        'fee_discount': 0.0,
        'zero_fee_pairs': [],
        'maker_fee': 0.00145,  
        'taker_fee': 0.00155,  
        'maker_fee_with_token': 0.00145,
        'taker_fee_with_token': 0.00155,
        'enabled': True,
        'requires_passphrase': False
    },
    'probit': {
        'name': 'ProBit Global',
        'class_name': 'probit',
        'api_url': 'https://api.probit.com',
        'websocket_url': 'wss://api.probit.com/api/exchange/v1/ws',
        'ticker_endpoint': '/api/exchange/v1/ticker',
        'exchange_info_endpoint': '/api/exchange/v1/market',
        'fee_token': 'PROB',
        'fee_discount': 0.20,  
        'zero_fee_pairs': [],
        'maker_fee': 0.0020,   
        'taker_fee': 0.0020,   
        'maker_fee_with_token': 0.0016,  
        'taker_fee_with_token': 0.0016,  
        'enabled': True,
        'requires_passphrase': False
    },
    'hitbtc': {
        'name': 'HitBTC',
        'class_name': 'hitbtc',
        'api_url': 'https://api.hitbtc.com',
        'websocket_url': 'wss://api.hitbtc.com/api/3/ws/public',
        'ticker_endpoint': '/api/3/public/ticker',
        'exchange_info_endpoint': '/api/3/public/symbol',
        'fee_token': None,
        'fee_discount': 0.0,
        'zero_fee_pairs': [],
        'maker_fee': 0.0009,   
        'taker_fee': 0.0025,   
        'maker_fee_with_token': 0.0009,
        'taker_fee_with_token': 0.0025,
        'enabled': True,
        'requires_passphrase': False
    }
}

# Priority currencies for triangle detection
PRIORITY_CURRENCIES = ['USDT', 'BTC', 'ETH', 'BNB', 'USDC', 'BUSD', 'SOL', 'XRP']

# Minimum liquidity requirements (USD)
MIN_LIQUIDITY_USD = 10000  

# Maximum number of triangles to monitor per exchange
MAX_TRIANGLES_PER_EXCHANGE = 100
