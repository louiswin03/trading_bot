"""
Setup Verification Script
Run this to verify everything is properly configured before launching the bot
"""

import sys
from pathlib import Path

def print_status(check_name, status, message=""):
    emoji = "✅" if status else "❌"
    print(f"{emoji} {check_name}")
    if message:
        print(f"   → {message}")

def main():
    print("\n" + "="*80)
    print("TRADING BOT - SETUP VERIFICATION")
    print("="*80 + "\n")

    all_good = True

    # 1. Check Python version
    print("1. Python Version:")
    if sys.version_info >= (3, 8):
        print_status("Python 3.8+", True, f"Version: {sys.version_info.major}.{sys.version_info.minor}")
    else:
        print_status("Python 3.8+", False, f"Your version: {sys.version_info.major}.{sys.version_info.minor}")
        all_good = False

    print()

    # 2. Check required files
    print("2. Required Files:")
    required_files = [
        'bot_with_position_tracking.py',
        'start_bot.bat',
        'telegram_bot.py',
        'core/strategies/adx_trend_strategy.py',
        'core/data_sources/market_data.py',
        'core/database.py'
    ]

    for file in required_files:
        file_path = Path(file)
        exists = file_path.exists()
        print_status(file, exists)
        if not exists:
            all_good = False

    print()

    # 3. Check dependencies
    print("3. Python Dependencies:")
    dependencies = [
        'pandas',
        'numpy',
        'schedule',
        'requests',
        'dotenv',
        'ccxt',
        'ta'
    ]

    for dep in dependencies:
        try:
            __import__(dep.replace('dotenv', 'python_dotenv').replace('python_', ''))
            print_status(dep, True)
        except ImportError:
            print_status(dep, False, f"Install with: pip install {dep}")
            all_good = False

    print()

    # 4. Check .env configuration
    print("4. Telegram Configuration:")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()

        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if token:
            print_status("TELEGRAM_BOT_TOKEN", True, "Found in .env")
        else:
            print_status("TELEGRAM_BOT_TOKEN", False, "Missing in .env")
            all_good = False

        if chat_id:
            print_status("TELEGRAM_CHAT_ID", True, "Found in .env")
        else:
            print_status("TELEGRAM_CHAT_ID", False, "Missing in .env")
            all_good = False
    except Exception as e:
        print_status(".env file", False, str(e))
        all_good = False

    print()

    # 5. Test Binance API connection
    print("5. Binance API Connection:")
    try:
        from core.data_sources.market_data import get_ohlcv
        df = get_ohlcv('BTCUSDT', '4h', 10)
        if df is not None and len(df) >= 10:
            print_status("Binance API", True, f"Fetched {len(df)} candles")
        else:
            print_status("Binance API", False, "Failed to fetch data")
            all_good = False
    except Exception as e:
        print_status("Binance API", False, str(e))
        all_good = False

    print()

    # 6. Test Telegram
    print("6. Telegram Bot:")
    try:
        from telegram_bot import send_telegram_message
        # Note: Won't actually send unless you uncomment the line below
        # send_telegram_message("🤖 Test message from setup verification")
        print_status("Telegram module", True, "Ready (test message not sent)")
    except Exception as e:
        print_status("Telegram module", False, str(e))
        all_good = False

    print()

    # 7. Test strategy
    print("7. Strategy:")
    try:
        from core.strategies.adx_trend_strategy import get_strategy_info, add_indicators
        info = get_strategy_info()
        print_status("Strategy loaded", True, f"{info['name']} {info['version']}")
        print(f"   → Annual Return: {info['backtest_stats']['annual_return']}%")
        print(f"   → Max Drawdown: {info['backtest_stats']['max_drawdown']}%")
        print(f"   → All Years Positive: {info['backtest_stats']['all_years_positive']}")
    except Exception as e:
        print_status("Strategy", False, str(e))
        all_good = False

    print()

    # Final verdict
    print("="*80)
    if all_good:
        print("✅ ALL CHECKS PASSED!")
        print("\nYou're ready to launch the bot!")
        print("→ Double-click 'start_bot.bat' to start")
    else:
        print("❌ SOME CHECKS FAILED")
        print("\nPlease fix the issues above before launching the bot.")
        print("\nCommon fixes:")
        print("  • Install missing packages: pip install pandas numpy schedule requests python-dotenv ccxt ta")
        print("  • Create .env file with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        print("  • Check your internet connection")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
