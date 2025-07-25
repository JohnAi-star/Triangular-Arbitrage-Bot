@echo off
echo Installing Triangular Arbitrage Bot Dependencies...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

echo Installing required packages...
pip install --upgrade pip
pip install ccxt>=4.1.0
pip install websockets>=12.0
pip install python-dotenv>=1.0.0
pip install numpy>=1.24.0
pip install pandas>=2.0.0
pip install aiofiles>=23.0.0
pip install colorlog>=6.7.0
pip install customtkinter>=5.2.0
pip install matplotlib>=3.7.0
pip install seaborn>=0.12.0
pip install Pillow>=10.0.0
pip install requests>=2.31.0
pip install python-dateutil>=2.8.0

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some packages
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

echo.
echo ✅ All dependencies installed successfully!
echo.
echo Next steps:
echo 1. Copy .env.example to .env
echo 2. Edit .env with your Binance API credentials
echo 3. Run GUI: python main_gui.py
echo    Or CLI: python main.py
echo.
pause