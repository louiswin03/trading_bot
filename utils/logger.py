"""
Professional logging system for the trading bot
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logger(name: str = 'TradingBot', log_file: Path = None, level: str = 'INFO'):
    """
    Setup logger with console and file handlers

    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )

    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (colored output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (rotating)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


class TradingLogger:
    """Specialized logger for trading operations"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def trade_signal(self, signal_type: str, pair: str, price: float,
                     strategy: str, confidence: float = None, **kwargs):
        """Log a trading signal"""
        msg = f" {signal_type.upper()} SIGNAL | {pair} @ {price:.2f} | Strategy: {strategy}"
        if confidence:
            msg += f" | Confidence: {confidence:.2%}"
        if kwargs:
            msg += f" | {kwargs}"

        if signal_type.lower() in ['buy', 'long']:
            self.logger.info(f"[BUY] {msg}")
        elif signal_type.lower() in ['sell', 'short']:
            self.logger.info(f"[SELL] {msg}")
        else:
            self.logger.info(msg)

    def trade_executed(self, side: str, pair: str, quantity: float,
                       price: float, order_id: str = None):
        """Log a trade execution"""
        msg = f"[OK] TRADE EXECUTED | {side.upper()} {quantity} {pair} @ {price:.2f}"
        if order_id:
            msg += f" | Order ID: {order_id}"
        self.logger.info(msg)

    def trade_closed(self, side: str, pair: str, entry_price: float,
                     exit_price: float, pnl: float, pnl_pct: float, reason: str):
        """Log a trade closure"""
        emoji = "💚" if pnl > 0 else "❌"
        msg = (f"{emoji} TRADE CLOSED | {side.upper()} {pair} | "
               f"Entry: {entry_price:.2f} → Exit: {exit_price:.2f} | "
               f"PnL: {pnl:+.2f} ({pnl_pct:+.2f}%) | Reason: {reason}")

        if pnl > 0:
            self.logger.info(msg)
        else:
            self.logger.warning(msg)

    def data_fetched(self, source: str, data_type: str, success: bool = True):
        """Log data fetching"""
        status = "✓" if success else "✗"
        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"{status} Data fetched: {source} - {data_type}")

    def error(self, error_type: str, message: str, exception: Exception = None):
        """Log an error"""
        msg = f"❌ ERROR | {error_type}: {message}"
        if exception:
            self.logger.error(msg, exc_info=True)
        else:
            self.logger.error(msg)

    def backtest_summary(self, total_trades: int, wins: int, losses: int,
                        winrate: float, total_pnl: float, max_drawdown: float = None):
        """Log backtest summary"""
        msg = (f"\n{'='*60}\n"
               f"[DATA] BACKTEST SUMMARY\n"
               f"{'='*60}\n"
               f"Total Trades: {total_trades}\n"
               f"Wins: {wins} | Losses: {losses}\n"
               f"Winrate: {winrate:.2f}%\n"
               f"Total PnL: {total_pnl:+.2f}%")

        if max_drawdown is not None:
            msg += f"\nMax Drawdown: {max_drawdown:.2f}%"

        msg += f"\n{'='*60}"
        self.logger.info(msg)
