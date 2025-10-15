import asyncio
import sys
sys.path.append('.')

from exchanges.unified_exchange import UnifiedExchange

async def test_prices():
    print("Testing price fetching...")
    
    # Test spot exchange
    spot_config = {
        'exchange_id': 'kucoin',
        'api_key': '68bc1a54df90c30001d12ad6',
        'api_secret': '2c9cbd48-fc16-4365-bf6c-3ee797b0e80f',
        'password': 'Nothing@12345',
        'sandbox': True,
    }
    
    spot_exchange = UnifiedExchange(spot_config)
    
    try:
        print("Testing spot BTC/USDT...")
        ticker = await spot_exchange.get_ticker('BTC/USDT')
        print(f"Spot Ticker: {ticker}")
        print(f"Spot BTC Price: ${ticker.get('last', 'N/A')}")
    except Exception as e:
        print(f"Spot error: {e}")
    
    # Test futures exchange  
    futures_config = {
        'exchange_id': 'kucoin',
        'api_key': '68bc1a54df90c30001d12ad6',
        'api_secret': '2c9cbd48-fc16-4365-bf6c-3ee797b0e80f',
        'password': 'Nothing@12345',
        'sandbox': True,
    }
    
    futures_exchange = UnifiedExchange(futures_config)
    
    try:
        print("\nTesting futures BTC/USDT...")
        ticker = await futures_exchange.get_ticker('BTC/USDT')
        print(f"Futures Ticker: {ticker}")
        print(f"Futures BTC Price: ${ticker.get('last', 'N/A')}")
    except Exception as e:
        print(f"Futures error: {e}")

if __name__ == "__main__":
    asyncio.run(test_prices())