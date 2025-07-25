#!/usr/bin/env python3
"""
Setup script for Triangular Arbitrage Bot
Installs dependencies and validates the environment
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command):
    """Run a command and return success status."""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def install_dependencies():
    """Install required Python packages."""
    print("📦 Installing Python dependencies...")
    
    dependencies = [
        "ccxt>=4.1.0",
        "websockets>=12.0", 
        "python-dotenv>=1.0.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "aiofiles>=23.0.0",
        "colorlog>=6.7.0"
    ]
    
    # Upgrade pip first
    print("Upgrading pip...")
    success, output = run_command(f"{sys.executable} -m pip install --upgrade pip")
    if not success:
        print(f"⚠️  Warning: Could not upgrade pip: {output}")
    
    # Install each dependency
    for dep in dependencies:
        print(f"Installing {dep}...")
        success, output = run_command(f"{sys.executable} -m pip install {dep}")
        if not success:
            print(f"❌ Failed to install {dep}: {output}")
            return False
        else:
            print(f"✅ {dep} installed successfully")
    
    return True

def validate_installation():
    """Validate that all required modules can be imported."""
    print("\n🔍 Validating installation...")
    
    required_modules = [
        'ccxt',
        'websockets', 
        'dotenv',
        'numpy',
        'pandas',
        'aiofiles',
        'colorlog'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - FAILED: {e}")
            return False
    
    return True

def setup_environment():
    """Setup environment file if it doesn't exist."""
    print("\n📝 Setting up environment...")
    
    env_example = Path('.env.example')
    env_file = Path('.env')
    
    if env_example.exists() and not env_file.exists():
        try:
            env_file.write_text(env_example.read_text())
            print("✅ Created .env file from template")
            print("⚠️  Please edit .env with your Binance API credentials")
        except Exception as e:
            print(f"❌ Failed to create .env file: {e}")
            return False
    elif env_file.exists():
        print("✅ .env file already exists")
    else:
        print("⚠️  No .env.example found")
    
    return True

def create_directories():
    """Create necessary directories."""
    print("\n📁 Creating directories...")
    
    directories = ['logs', 'data']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created {directory}/ directory")
    
    return True

def main():
    """Main setup function."""
    print("🔺 Triangular Arbitrage Bot Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version.split()[0]} detected")
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Dependency installation failed")
        sys.exit(1)
    
    # Validate installation
    if not validate_installation():
        print("\n❌ Installation validation failed")
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        print("\n❌ Environment setup failed")
        sys.exit(1)
    
    # Create directories
    if not create_directories():
        print("\n❌ Directory creation failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Edit .env with your Binance API credentials")
    print("2. Set BINANCE_SANDBOX=true for testing")
    print("3. Run: python main.py")
    print("\nFor help, see README.md")

if __name__ == "__main__":
    main()