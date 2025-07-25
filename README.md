# Multi-Exchange Triangular Arbitrage Bot with GUI

A production-ready, GUI-driven Python bot for detecting and executing triangular arbitrage opportunities across multiple cryptocurrency exchanges with advanced profit optimization and risk management.

## 🚀 Features

### Core Functionality
- **Multi-Exchange Support**: Binance, Bybit, KuCoin, Coinbase Pro, Kraken, Gate.io, CoinEx, HTX, MEXC, Poloniex, ProBit Global, HitBTC
- **Real-time Detection**: WebSocket-based price monitoring across all exchanges
- **GUI Interface**: Professional desktop application with real-time opportunity display
- **Smart Profit Optimization**: Prioritizes zero-fee pairs and fee token discounts
- **Advanced Filtering**: Only executes trades with positive net profit after all costs

### Trading Modes
- **Manual Trading**: Review and approve each trade individually
- **Auto Trading**: Fully automated execution of profitable opportunities
- **Paper Trading**: Risk-free simulation mode for testing strategies
- **Backtesting**: Historical data analysis for strategy optimization

### Risk Management
- **Liquidity Checks**: Ensures sufficient market depth before execution
- **Slippage Protection**: Conservative slippage estimation and limits
- **Position Sizing**: Configurable maximum trade amounts and position limits
- **Fee Optimization**: Automatic use of native fee tokens (BNB, KCS, etc.)

### User Interface
- **Real-time Opportunities**: Live display of all detected arbitrage opportunities
- **Exchange Selection**: Choose which exchanges to monitor and trade on
- **Trading History**: Complete log of all executed trades with performance metrics
- **Statistics Dashboard**: Success rates, profit tracking, and performance analytics
- **Detailed Analysis**: In-depth opportunity analysis with step-by-step breakdowns

## 📋 Requirements

- Python 3.8+
- Exchange accounts with API access (optional for paper trading)
- Minimum 0.1% profit threshold (configurable)
- Native fee token balances for reduced trading fees (recommended)

## 🛠️ Installation

### Option 1: Automatic Setup (Recommended)

**Windows**:
```bash
# Run the installation script
install.bat
```

**Linux/Mac**:
```bash
# Make script executable and run
chmod +x install.sh
./install.sh
```

**Cross-platform Python setup**:
```bash
python setup.py
```

### Option 2: Manual Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Configure Exchange Credentials** (edit .env file):
   ```env
   # Example for Binance
   BINANCE_API_KEY=your_binance_api_key_here
   BINANCE_API_SECRET=your_binance_api_secret_here
   BINANCE_SANDBOX=true
   
   # Add credentials for other exchanges as needed
   BYBIT_API_KEY=your_bybit_api_key_here
   BYBIT_API_SECRET=your_bybit_api_secret_here
   
   # Trading settings
   MIN_PROFIT_PERCENTAGE=0.1
   MAX_TRADE_AMOUNT=100
   PAPER_TRADING=true
   AUTO_TRADING_MODE=false
   ```

## 🏃 Quick Start

### 0. Install Dependencies
```bash
# Windows
install.bat

# Linux/Mac  
./install.sh

# Or use Python setup
python setup.py
```

### 1. Start the GUI Application
```bash
python main_gui.py
```

### 2. Configure Exchanges
- Select which exchanges to monitor using the checkboxes
- The bot will automatically detect available API credentials
- Start with paper trading mode for safe testing

### 3. Start Trading
- Click "Start Bot" to begin scanning for opportunities
- Review detected opportunities in the main display
- Use manual mode to approve trades individually
- Switch to auto mode for fully automated trading

### 4. Monitor Performance
- View real-time statistics in the dashboard
- Check trading history for detailed trade records
- Analyze opportunity details with double-click

## 🖥️ GUI Interface Guide

### Main Window Components

1. **Control Panel** (Top)
   - Exchange selection checkboxes
   - Start/Stop bot controls
   - Trading mode toggles (Auto/Manual, Paper/Live)
   - Configuration settings (min profit, max trade amount)

2. **Opportunities Display** (Center-Left)
   - Real-time list of detected arbitrage opportunities
   - Sortable columns: Exchange, Triangle Path, Profit %, Amount
   - Color-coded profitability indicators
   - Double-click for detailed analysis

3. **Trading Panel** (Right)
   - Trading history log
   - Manual execution controls
   - Trade confirmation dialogs

4. **Statistics Dashboard** (Bottom)
   - Opportunities found counter
   - Trades executed counter
   - Total profit tracking
   - Success rate percentage
   - Active exchanges count

### Using the Interface

1. **Starting the Bot**:
   - Select desired exchanges
   - Configure trading parameters
   - Choose trading mode (paper/live, manual/auto)
   - Click "Start Bot"

2. **Reviewing Opportunities**:
   - Opportunities appear in real-time
   - Green rows = profitable, red rows = unprofitable
   - Double-click any row for detailed analysis
   - Use "Execute Selected" for manual trading

3. **Monitoring Performance**:
   - Statistics update automatically
   - Trading history shows all activity
   - Status bar shows current bot state

## 🔧 Advanced Configuration

### Exchange-Specific Settings

Each exchange can be configured with specific parameters in `config/exchanges_config.py`:

```python
'kucoin': {
    'name': 'KuCoin',
    'fee_token': 'KCS',
    'fee_discount': 0.20,  # 20% discount with KCS
    'zero_fee_pairs': ['BTC/ETH', 'ETH/BTC'],  # Zero-fee trading pairs
    'maker_fee': 0.001,
    'taker_fee': 0.001,
    'enabled': True
}
```

### Trading Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_PROFIT_PERCENTAGE` | 0.1 | Minimum profit threshold (%) |
| `MAX_TRADE_AMOUNT` | 100 | Maximum trade size per opportunity |
| `MAX_POSITION_SIZE_USD` | 1000 | Maximum total position size |
| `USE_FEE_TOKENS` | true | Use native tokens for fee discounts |
| `PRIORITIZE_ZERO_FEE` | true | Prioritize zero-fee trading pairs |
| `AUTO_TRADING_MODE` | false | Enable fully automated trading |
| `PAPER_TRADING` | true | Enable risk-free simulation mode |

### GUI Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GUI_UPDATE_INTERVAL` | 1000 | GUI refresh rate (milliseconds) |
| `MAX_OPPORTUNITIES_DISPLAY` | 50 | Maximum opportunities shown |

## 🧪 Backtesting

The bot includes a comprehensive backtesting engine:

```bash
# Run backtest from GUI
# Or use the backtesting module directly
python -c "
from backtesting.backtest_engine import BacktestEngine
from datetime import datetime, timedelta
import asyncio

async def run_backtest():
    engine = BacktestEngine({'min_profit_percentage': 0.1})
    
    # Load historical data
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    await engine.load_historical_data('binance', ['BTC/USDT', 'ETH/USDT', 'BTC/ETH'], start_date, end_date)
    
    # Run backtest
    result = await engine.run_backtest('binance', start_date, end_date, 10000)
    print(f'Total Profit: ${result.total_profit:.2f}')
    print(f'Success Rate: {result.success_rate:.2f}%')

asyncio.run(run_backtest())
"
```

## 🔄 Paper Trading vs Live Trading

### Paper Trading Mode (Default)
- Risk-free simulation using real market data
- No actual trades executed
- Perfect for testing strategies and configurations
- Simulated balances and trade execution
- All features available except real money

### Live Trading Mode
- Requires valid API credentials for each exchange
- Executes real trades with real money
- All profits and losses are real
- Requires careful risk management
- Start with small amounts for testing

## 📊 Profit Optimization Features

### Zero-Fee Pair Prioritization
The bot automatically identifies and prioritizes trading pairs with zero fees:
- KuCoin: BTC/ETH, ETH/BTC (example)
- Binance: Various promotional pairs
- Other exchanges: Exchange-specific zero-fee pairs

### Fee Token Optimization
Automatic detection and usage of native fee tokens:
- **Binance**: BNB (25% discount)
- **KuCoin**: KCS (20% discount)
- **Bybit**: BIT (10% discount)
- **Gate.io**: GT (15% discount)
- **CoinEx**: CET (20% discount)

### Liquidity Filtering
- Minimum liquidity requirements ($10,000 default)
- Volume-based opportunity filtering
- Market depth analysis before execution

### Smart Opportunity Ranking
Opportunities are ranked by:
1. Net profit after all fees and slippage
2. Zero-fee pair availability
3. Liquidity and volume
4. Historical success rate
5. Exchange reliability

## 📁 Project Structure

```
triangular-arbitrage-bot/
├── config/
│   ├── config.py                    # Main configuration
│   └── exchanges_config.py          # Exchange-specific settings
├── exchanges/
│   ├── base_exchange.py             # Abstract exchange interface
│   ├── unified_exchange.py          # Unified exchange wrapper
│   └── multi_exchange_manager.py    # Multi-exchange coordinator
├── arbitrage/
│   ├── multi_exchange_detector.py   # Multi-exchange opportunity detection
│   └── trade_executor.py            # Trade execution engine
├── gui/
│   └── main_window.py               # Main GUI application
├── backtesting/
│   └── backtest_engine.py           # Backtesting framework
├── models/
│   └── arbitrage_opportunity.py     # Data models
├── utils/
│   └── logger.py                    # Logging utilities
├── logs/                            # Log files (auto-created)
├── main_gui.py                      # GUI entry point
├── main.py                          # CLI entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
└── README.md                        # This file
```

## 🔒 Security and Risk Management

### API Security
1. **Permissions**: Only enable spot trading permissions
2. **IP Restrictions**: Limit API access to your server/computer IP
3. **Sandbox Testing**: Always test with sandbox/testnet first
4. **Key Rotation**: Regularly rotate API keys

### Trading Risk Management
1. **Position Limits**: Set appropriate maximum trade amounts
2. **Paper Trading**: Test thoroughly before live trading
3. **Gradual Scaling**: Start with small amounts
4. **Stop Losses**: Monitor and set maximum loss limits
5. **Diversification**: Don't put all funds in arbitrage

### Technical Security
1. **Environment Variables**: Never hardcode API keys
2. **Secure Storage**: Keep .env files secure and private
3. **Network Security**: Use secure networks and VPNs
4. **Regular Updates**: Keep dependencies updated

## 📈 Performance Optimization

### Speed Optimization
1. **WebSocket Streams**: Real-time price updates
2. **Async Processing**: Concurrent opportunity detection
3. **Caching**: Intelligent price and volume caching
4. **Connection Pooling**: Efficient API connection management

### Profit Optimization
1. **Fee Minimization**: Automatic fee token usage
2. **Zero-Fee Prioritization**: Target zero-fee pairs first
3. **Slippage Reduction**: Conservative slippage estimates
4. **Opportunity Ranking**: Focus on highest-profit opportunities

### Resource Management
1. **Memory Efficiency**: Optimized data structures
2. **CPU Usage**: Efficient algorithms and caching
3. **Network Usage**: Rate limit compliance
4. **Storage**: Rotating logs and data cleanup

## 🐛 Troubleshooting

### Common Issues

**GUI Won't Start**:
```bash
# Check dependencies
pip install -r requirements.txt

# Check Python version (3.8+ required)
python --version
```

**No Opportunities Found**:
- Lower `MIN_PROFIT_PERCENTAGE` for testing
- Check exchange connections in GUI
- Verify API credentials and permissions
- Ensure sufficient market volatility

**Connection Errors**:
- Verify API credentials in .env file
- Check internet connection
- Confirm exchange API status
- Review IP restrictions on API keys

**Performance Issues**:
- Reduce number of monitored exchanges
- Increase `GUI_UPDATE_INTERVAL`
- Limit `MAX_OPPORTUNITIES_DISPLAY`
- Check system resources (CPU, memory)

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set debug logging level
export LOG_LEVEL=DEBUG
python main_gui.py
```

### Log Files

Check log files for detailed error information:
- `logs/gui.log` - GUI application logs
- `logs/multiexchangemanager.log` - Exchange connection logs
- `logs/multiexchangedetector.log` - Opportunity detection logs
- `logs/tradeexecutor.log` - Trade execution logs
- `logs/trades.log` - Detailed trade records

## 📊 How It Works

### Triangular Arbitrage Process

1. **Triangle Detection**: Scans all trading pairs to find valid triangular combinations (e.g., BTC → ETH → USDT → BTC)

2. **Opportunity Calculation**: For each triangle:
   - Calculates potential profit path
   - Factors in trading fees (with BNB discount if available)
   - Estimates slippage impact
   - Computes net profit

3. **Filtering**: Only considers opportunities with:
   - Net profit > 0 after all costs
   - Profit percentage ≥ minimum threshold
   - Sufficient liquidity in order books

4. **Execution**: If profitable and confirmed:
   - Places three sequential market orders
   - Monitors execution in real-time
   - Logs results for analysis

### Example Triangle Path
```
Initial: 1 BTC
Step 1: BTC → ETH (sell BTC, get ETH)
Step 2: ETH → USDT (sell ETH, get USDT) 
Step 3: USDT → BTC (buy BTC with USDT)
Result: 1.002 BTC (0.2% profit)
```

### Multi-Exchange Arbitrage Process

1. **Exchange Connection**: Connect to multiple exchanges simultaneously
2. **Price Aggregation**: Collect real-time prices from all connected exchanges
3. **Triangle Detection**: Identify all possible triangular paths on each exchange
4. **Profit Calculation**: Calculate net profit for each opportunity including:
   - Trading fees (with fee token discounts)
   - Estimated slippage
   - Liquidity requirements
5. **Opportunity Ranking**: Sort by profitability and other factors
6. **Execution**: Execute trades manually or automatically based on settings

### Zero-Fee Optimization

The bot prioritizes opportunities involving zero-fee trading pairs:
- **Detection**: Automatically identifies zero-fee pairs per exchange
- **Prioritization**: Ranks zero-fee opportunities higher
- **Profit Maximization**: Focuses on pairs with no trading fees
- **Dynamic Updates**: Adapts to changing fee structures

## 🎯 Advanced Features

### Inter-Exchange Arbitrage (Phase 2 Ready)

The architecture is designed for easy expansion to inter-exchange arbitrage:
- **Multi-Exchange Framework**: Already supports multiple exchanges
- **Unified Interface**: Consistent API across all exchanges
- **Cross-Exchange Detection**: Framework ready for cross-exchange opportunities
- **Simultaneous Execution**: Capable of executing trades across exchanges

### Machine Learning Integration (Future)
- **Opportunity Prediction**: ML models for predicting profitable opportunities
- **Slippage Estimation**: AI-powered slippage prediction
- **Market Timing**: Optimal execution timing algorithms
- **Risk Assessment**: ML-based risk scoring

### Advanced Order Types (Future)
- **Limit Orders**: More precise execution pricing
- **Stop Losses**: Automatic risk management
- **Iceberg Orders**: Large order execution with minimal market impact
- **Time-Weighted Orders**: Spread execution over time

## 📞 Support and Community

### Getting Help
1. **Documentation**: Check this README and code comments
2. **Logs**: Review log files for detailed error information
3. **Configuration**: Verify all settings in .env file
4. **Testing**: Use paper trading mode for safe testing

### Contributing
1. **Bug Reports**: Submit detailed bug reports with logs
2. **Feature Requests**: Suggest new features and improvements
3. **Code Contributions**: Submit pull requests with improvements
4. **Documentation**: Help improve documentation and guides

### Best Practices
1. **Start Small**: Begin with paper trading and small amounts
2. **Monitor Closely**: Watch the bot's performance regularly
3. **Stay Updated**: Keep the bot and dependencies updated
4. **Risk Management**: Never risk more than you can afford to lose
5. **Compliance**: Ensure compliance with local regulations

## ⚖️ Legal and Risk Disclaimers

### Important Warnings
- **High Risk**: Cryptocurrency trading involves substantial risk
- **No Guarantees**: Past performance does not guarantee future results
- **Market Risk**: Crypto markets are highly volatile and unpredictable
- **Technical Risk**: Software bugs or failures can cause losses
- **Regulatory Risk**: Regulations may change affecting trading

### User Responsibilities
- **Due Diligence**: Research and understand the risks
- **Compliance**: Follow all applicable laws and regulations
- **Risk Management**: Only trade with funds you can afford to lose
- **Monitoring**: Actively monitor the bot's performance
- **Security**: Secure your API keys and trading accounts

### Disclaimer
This software is provided for educational and research purposes. Users are solely responsible for:
- All trading decisions and their consequences
- Compliance with local financial regulations
- Understanding tax implications of trading activities
- Managing their own risk exposure
- Ensuring proper regulatory compliance

The developers are not responsible for any financial losses or legal issues arising from the use of this software.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Happy Trading! 📈🤖**

*Built with ❤️ for the crypto arbitrage community*

### Key Metrics
- Opportunities detected per hour
- Trade execution success rate
- Average profit per trade
- Fee optimization effectiveness

### Real-time Status
The bot provides real-time status updates including:
- Current account balances
- Opportunities found vs executed
- WebSocket connection status
- System performance metrics

## 🔒 Security Best Practices

1. **API Permissions**: Only enable spot trading permissions
2. **IP Restrictions**: Limit API access to your server's IP
3. **Sandbox Testing**: Always test thoroughly before live trading
4. **Position Limits**: Set appropriate `MAX_TRADE_AMOUNT`
5. **Monitoring**: Regularly review log files and trading activity

## 🎯 Phase 2 Roadmap (Inter-Exchange Arbitrage)

The current architecture is designed to easily support inter-exchange arbitrage:

1. **Exchange Abstraction**: `BaseExchange` interface allows multiple exchange connections
2. **Opportunity Models**: Extensible to support cross-exchange opportunities  
3. **Execution Engine**: Can be enhanced for simultaneous multi-exchange trading
4. **Risk Management**: Framework ready for cross-exchange position management

### Planned Enhancements
- Multiple exchange connections (Coinbase, Kraken, etc.)
- Cross-exchange opportunity detection
- Advanced position management
- Automated rebalancing
- Enhanced risk controls

## 🐛 Troubleshooting

### Common Issues

**Connection Errors**:
```bash
# Check API credentials
python -c "from exchanges.binance_exchange import BinanceExchange; import asyncio; asyncio.run(BinanceExchange({'api_key': 'test', 'api_secret': 'test'}).connect())"
```

**No Opportunities Found**:
- Lower `MIN_PROFIT_PERCENTAGE` temporarily for testing
- Check market volatility (low volatility = fewer opportunities)  
- Verify WebSocket data is being received

**WebSocket Disconnections**:
- Check network stability
- Review `WEBSOCKET_RECONNECT_ATTEMPTS` setting
- Monitor exchange rate limits

### Performance Tuning

1. **Scan Frequency**: Adjust sleep time in `_scan_loop()`
2. **Symbol Filtering**: Limit WebSocket symbols for better performance  
3. **Memory Usage**: Monitor price cache size for long-running sessions
4. **Order Size**: Optimize `MAX_TRADE_AMOUNT` based on market liquidity

## 📞 Support

- Check logs in the `logs/` directory for detailed error information
- Review configuration settings in `.env` file
- Test with sandbox mode before live trading
- Monitor exchange status pages for service disruptions

## ⚖️ Legal Notice

This software is for educational and research purposes. Users are responsible for:
- Complying with local financial regulations
- Understanding tax implications of trading activities  
- Managing their own risk exposure
- Ensuring proper regulatory compliance

Trading cryptocurrencies involves substantial risk and may not be suitable for all users.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Happy Trading! 📈🤖**