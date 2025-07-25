#!/bin/bash

echo "Installing Triangular Arbitrage Bot Dependencies..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ from your package manager"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not available"
    echo "Please install pip3"
    exit 1
fi

echo "Installing required packages..."
pip3 install --upgrade pip
pip3 install ccxt>=4.1.0
pip3 install websockets>=12.0
pip3 install python-dotenv>=1.0.0
pip3 install numpy>=1.24.0
pip3 install pandas>=2.0.0
pip3 install aiofiles>=23.0.0
pip3 install colorlog>=6.7.0

if [ $? -eq 0 ]; then
    echo
    echo "✅ All dependencies installed successfully!"
    echo
    echo "Next steps:"
    echo "1. Copy .env.example to .env"
    echo "2. Edit .env with your Binance API credentials"
    echo "3. Run: python3 main.py"
    echo
else
    echo
    echo "ERROR: Failed to install some packages"
    echo "Please check your internet connection and try again"
    exit 1
fi