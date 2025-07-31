#!/usr/bin/env python3
"""
Test script to verify REAL trading execution on Binance
This will execute a small test trade to verify everything works
"""

import asyncio
import os
from dotenv import load_dotenv
from exchanges.unified_exchange import UnifiedExchange
from utils.logger import setup_logger

load_dotenv()

async def test_real_trade_execution():
    logger = setup_logger('TestRealTrade')

    # Configuration
    config = {
        'exchange_id': 'binance',
        'api_key': os.getenv('BINANCE_API_KEY'),
        'api_secret': os.getenv('BINANCE_API_SECRET'),
        'sandbox': False,
        'paper_trading': False
    }

    if not config['api_key'] or not config['api_secret']:
        logger.error("❌ No API credentials found")
        return False

    try:
        logger.info("🚀 Testing REAL trade execution on Binance...")
        exchange = UnifiedExchange(config)

        if not await exchange.connect():
            logger.error("❌ Failed to connect to Binance")
            return False

        logger.info("💰 Checking account balance...")
        balance = await exchange.get_account_balance()
        available_balances = {k: v for k, v in balance.items() if v > 0}
        logger.info(f"Available balances: {available_balances}")

        test_currency = None
        test_amount = 0

        # Asset prioritization
        if balance.get('USDT', 0) >= 8:
            test_currency = 'USDT'
            test_amount = 8.1
        elif balance.get('USDC', 0) >= 5:
            test_currency = 'USDC'
            test_amount = min(5, balance.get('USDC', 0) * 0.1)
        elif balance.get('BTC', 0) >= 0.00005:
            test_currency = 'BTC'
            test_amount = min(0.00005, balance.get('BTC', 0) * 0.1)
        elif balance.get('ETH', 0) >= 0.002:
            test_currency = 'ETH'
            test_amount = min(0.002, balance.get('ETH', 0) * 0.1)
        elif balance.get('BNB', 0) >= 0.01:
            test_currency = 'BNB'
            test_amount = min(0.01, balance.get('BNB', 0) * 0.1)
        else:
            for currency, amount in available_balances.items():
                if amount > 0 and currency not in ['info', 'timestamp', 'datetime']:
                    test_currency = currency
                    test_amount = amount * 0.05
                    logger.info(f"Using available {currency} balance for testing")
                    break

            if not test_currency:
                logger.error("❌ No available balance for test trade")
                logger.info("   Please deposit some funds to test trading")
                return False

        logger.info(f"✅ Using {test_amount} {test_currency} for test trade")

        # Load markets safely
        if not hasattr(exchange, 'markets') or not exchange.markets:
            await exchange.exchange.load_markets()
        markets = exchange.exchange.markets

        # --- USDT trade test ---
        if test_currency == 'USDT':
            logger.info("🔄 Testing USDT -> BTC -> USDT cycle...")
            logger.info("Step 1: Buying BTC with USDT...")

            ticker = await exchange.get_ticker('BTC/USDT')
            btc_price = ticker.get('ask', 0)
            if btc_price <= 0:
                logger.error("❌ Invalid BTC/USDT ask price")
                await exchange.disconnect()
                return False

            min_btc_qty = markets['BTC/USDT']['limits']['amount']['min']
            btc_quantity = test_amount / btc_price
            if btc_quantity < min_btc_qty:
                logger.warning(f"⚠️ Quantity too low. Adjusting to minimum {min_btc_qty} BTC")
                btc_quantity = min_btc_qty

            buy_result = await exchange.place_market_order('BTC/USDT', 'buy', btc_quantity)
            if not buy_result.get('success'):
                logger.error(f"❌ Buy order failed: {buy_result.get('error')}")
                await exchange.disconnect()
                return False

            btc_received = float(buy_result.get('filled', 0))
            logger.info(f"✅ Bought {btc_received:.8f} BTC")

            await asyncio.sleep(2)

            logger.info("Step 2: Selling BTC back to USDT...")
            sell_result = await exchange.place_market_order('BTC/USDT', 'sell', btc_received)
            if not sell_result.get('success'):
                logger.error(f"❌ Sell order failed: {sell_result.get('error')}")
                await exchange.disconnect()
                return False

            usdt_received = float(sell_result.get('cost', 0))
            logger.info(f"✅ Sold BTC for {usdt_received:.2f} USDT")

            profit_loss = usdt_received - test_amount
            profit_pct = (profit_loss / test_amount) * 100

            logger.info("📊 TRADE RESULTS:")
            logger.info(f"   Initial: {test_amount:.2f} USDT")
            logger.info(f"   Final: {usdt_received:.2f} USDT")
            logger.info(f"   P&L: {profit_loss:.4f} USDT ({profit_pct:.4f}%)")

            if profit_loss > 0:
                logger.info("🎉 Test trade was profitable!")
            else:
                logger.info("📉 Test trade had a small loss (likely due to fees)")

        # --- Altcoin test cycles ---
        elif test_currency in ['BTC', 'ETH', 'BNB']:
            logger.info(f"🔄 Testing {test_currency} -> USDT -> {test_currency} cycle...")
            pair = f"{test_currency}/USDT"

            logger.info(f"Step 1: Selling {test_currency} for USDT...")
            sell_result = await exchange.place_market_order(pair, 'sell', test_amount)
            if not sell_result.get('success'):
                logger.error(f"❌ Sell order failed: {sell_result.get('error')}")
                await exchange.disconnect()
                return False

            usdt_received = float(sell_result.get('cost', 0))
            logger.info(f"✅ Sold {test_amount:.8f} {test_currency} for {usdt_received:.2f} USDT")

            await asyncio.sleep(2)

            logger.info(f"Step 2: Buying {test_currency} back with USDT...")
            ticker = await exchange.get_ticker(pair)
            crypto_price = ticker.get('ask', 0)
            if crypto_price <= 0:
                logger.error("❌ Invalid ask price")
                await exchange.disconnect()
                return False

            crypto_quantity = usdt_received / crypto_price
            min_qty = markets[pair]['limits']['amount']['min']
            if crypto_quantity < min_qty:
                logger.warning(f"⚠️ Quantity too low. Adjusting to minimum {min_qty}")
                crypto_quantity = min_qty

            buy_result = await exchange.place_market_order(pair, 'buy', crypto_quantity)
            if not buy_result.get('success'):
                logger.error(f"❌ Buy order failed: {buy_result.get('error')}")
                await exchange.disconnect()
                return False

            crypto_received = float(buy_result.get('filled', 0))
            logger.info(f"✅ Bought {crypto_received:.8f} {test_currency}")

            profit_loss = crypto_received - test_amount
            profit_pct = (profit_loss / test_amount) * 100

            logger.info("📊 TRADE RESULTS:")
            logger.info(f"   Initial: {test_amount:.8f} {test_currency}")
            logger.info(f"   Final: {crypto_received:.8f} {test_currency}")
            logger.info(f"   P&L: {profit_loss:.8f} ({profit_pct:.4f}%)")

        else:
            logger.info(f"🔄 Test currency {test_currency} not supported for full cycle. Skipping trade.")

        await exchange.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔺 Real Trade Execution Test")
    print("=" * 50)
    print("⚠️  WARNING: This will execute REAL trades with REAL money!")
    print("   Only a small amount (~$8) will be used for testing\n")

    response = input("Continue with REAL trade test? (y/n): ").lower().strip()
    if response != 'y':
        print("Test cancelled by user")
        exit(0)

    try:
        success = asyncio.run(test_real_trade_execution())
        if success:
            print("\n🎉 Real trade test completed successfully!")
        else:
            print("\n❌ Real trade test failed. Check the logs above.")
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
