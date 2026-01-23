"""
Configuration management with environment variables
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Binance API
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# External Data APIs (Free only!)
BITQUERY_API_KEY = os.getenv('BITQUERY_API_KEY', '')  # Free on-chain data

# Trading Parameters
DEFAULT_PAIR = os.getenv('DEFAULT_PAIR', 'BTCUSDT')
DEFAULT_INTERVAL = os.getenv('DEFAULT_INTERVAL', '15m')
RISK_PERCENTAGE = float(os.getenv('RISK_PERCENTAGE', '1.0'))
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '100'))

# Database
DB_PATH = BASE_DIR / os.getenv('DB_PATH', 'data/trading_bot.db')

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = BASE_DIR / os.getenv('LOG_FILE', 'logs/trading_bot.log')

# API Endpoints (Free only!)
FEAR_GREED_API = "https://api.alternative.me/fng/"
BITQUERY_API = "https://graphql.bitquery.io"
BINANCE_API = "https://api.binance.com/api/v3"

# Backtest Configuration (OPTIMIZED for RSI+BB+Volume - Validated on 5.79 years)
# Strategy: Mean Reversion with RSI < 35, Bollinger Band touch, Volume > 2x
# Performance: +469% total, +81% annual, 37% winrate, 1.50 PF, 1.62 Sharpe
BACKTEST_TP_RATIO = 0.02  # 2.0% take profit
BACKTEST_SL_MARGIN = 0.0001  # 0.01% stop loss margin (tight, based on swing)
BACKTEST_MAX_HOLD = 5  # 5 candles max hold (OPTIMIZED - exits fast for mean reversion)
BACKTEST_INITIAL_CAPITAL = 10000  # Starting capital in USDT

# Trading Strategy Weights (for multi-factor scoring)
WEIGHTS = {
    'technical': 0.60,      # Technical indicators (60%)
    'sentiment': 0.30,      # Fear & Greed sentiment (30%)
    'onchain': 0.0,         # On-chain metrics (0% - Bitquery key issues)
    'volume': 0.10          # Volume analysis (10%)
}

# Signal Thresholds
SIGNAL_THRESHOLD_BUY = 0.65   # Score > 0.65 = BUY signal
SIGNAL_THRESHOLD_SELL = 0.35  # Score < 0.35 = SELL signal
STRONG_SIGNAL_THRESHOLD = 0.80  # Score > 0.80 = STRONG signal

# Data Collection Settings
DATA_CACHE_DURATION = 300  # Cache external data for 5 minutes
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def validate_config():
    """Validate that all required configuration is present"""
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set in .env")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID not set in .env")

    if errors:
        print("⚠️  Configuration warnings:")
        for error in errors:
            print(f"  - {error}")
        print("\nℹ️  Copy .env.example to .env and fill in your credentials")

    return len(errors) == 0

# Create necessary directories
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
