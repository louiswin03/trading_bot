"""
FINAL OPTIMIZED STRATEGY - RSI + Bollinger Bands + Volume

Validated on 5.79 years of BTCUSDT 1h data (50,000 candles)

Performance:
- Total Return: +469.66%
- Annual Return: +81.16%
- Winrate: 37.08%
- Profit Factor: 1.50
- Sharpe Ratio: 1.62
- Trades: 1,567 (22.6/month)

Strategy Type: Mean Reversion
Logic: Buy oversold + volume spike, Sell overbought + volume spike
Exit: Fast exit (5 candles max) to capture quick reversions

NEW: Fear & Greed Index Integration (Optional)
- Can apply F&G filter with multiple modes: contrarian, momentum, hybrid, extreme_only
- Filter can block trades or adjust confidence based on market sentiment
"""
from typing import Optional, Literal
from core.data_sources.fear_greed_filter import FearGreedFilter


# Global F&G filter instance (initialized when needed)
_fg_filter: Optional[FearGreedFilter] = None


def rsi_bb_volume_optimized(df, fg_mode: Optional[str] = None, fg_filter_type: str = "soft"):
    """
    RSI + Bollinger Bands + Volume > 2x (OPTIMIZED)

    Entry Conditions:
    - BUY: RSI < 35 + Price touches BB lower + Volume > 2x average
    - SELL: RSI > 65 + Price touches BB upper + Volume > 2x average

    Exit Conditions (handled by backtest engine):
    - Take Profit: 2.0%
    - Stop Loss: 0.01% (tight, based on swing low/high)
    - Max Hold: 5 candles (fast exit for mean reversion)

    Args:
        df: DataFrame with OHLCV data and indicators (rsi, bb_lower, bb_upper, volume_ratio)
        fg_mode: Fear & Greed filter mode ('contrarian', 'momentum', 'hybrid', 'extreme_only', 'disabled', or None)
        fg_filter_type: 'hard' (block trades) or 'soft' (add metadata only)

    Returns:
        tuple: (signal, candle, fg_metadata) where signal is 'buy', 'sell', or ''
               fg_metadata contains F&G filter information if fg_mode is set
    """
    global _fg_filter

    # Initialize F&G filter if mode is specified
    fg_metadata = None
    if fg_mode and fg_mode != "disabled":
        if _fg_filter is None or _fg_filter.mode != fg_mode:
            _fg_filter = FearGreedFilter(mode=fg_mode)

    if len(df) < 2:
        return "", None, fg_metadata

    # Use previous closed candle (not current)
    prev = df.iloc[-2]

    # Get indicators
    rsi = prev.get('rsi', 50)
    price_low = prev['low']
    price_high = prev['high']
    bb_lower = prev.get('bb_lower', 0)
    bb_upper = prev.get('bb_upper', float('inf'))
    volume_ratio = prev.get('volume_ratio', 1)

    # Entry logic: All conditions must be met
    # BUY: Oversold (RSI < 35) + Touches BB lower + High volume (>2x)
    oversold = rsi < 35 and price_low < bb_lower and volume_ratio > 2.0

    # SELL: Overbought (RSI > 65) + Touches BB upper + High volume (>2x)
    overbought = rsi > 65 and price_high > bb_upper and volume_ratio > 2.0

    # Determine technical signal
    if oversold:
        signal = "buy"
    elif overbought:
        signal = "sell"
    else:
        signal = ""

    # Apply Fear & Greed filter if enabled
    if signal and fg_mode and fg_mode != "disabled" and _fg_filter:
        fg_check = _fg_filter.should_allow_trade(signal)
        fg_metadata = {
            'fg_value': fg_check['fg_value'],
            'fg_signal': fg_check['fg_signal'],
            'fg_mode': fg_mode,
            'fg_allowed': fg_check['allowed'],
            'fg_reason': fg_check['reason'],
            'fg_confidence': fg_check['fg_confidence']
        }

        if fg_filter_type == "hard" and not fg_check['allowed']:
            # Hard filter: Block trade completely
            return "", None, fg_metadata

    if signal:
        return signal, prev, fg_metadata

    return "", None, fg_metadata


def rsi_bb_volume_optimized_wrapper(df):
    """
    Wrapper for backward compatibility with existing code
    Returns only (signal, candle) without fg_metadata
    """
    signal, candle, _ = rsi_bb_volume_optimized(df, fg_mode=None)
    return signal, candle


def rsi_bb_volume_live(df, fg_mode: Optional[str] = None, fg_filter_type: str = "soft"):
    """
    Live version - checks current candle (unconfirmed signal)
    Use this for real-time monitoring, but trade on confirmed signals only
    """
    global _fg_filter

    # Initialize F&G filter if mode is specified
    fg_metadata = None
    if fg_mode and fg_mode != "disabled":
        if _fg_filter is None or _fg_filter.mode != fg_mode:
            _fg_filter = FearGreedFilter(mode=fg_mode)

    if len(df) < 1:
        return "", None, fg_metadata

    current = df.iloc[-1]

    rsi = current.get('rsi', 50)
    price_low = current['low']
    price_high = current['high']
    bb_lower = current.get('bb_lower', 0)
    bb_upper = current.get('bb_upper', float('inf'))
    volume_ratio = current.get('volume_ratio', 1)

    oversold = rsi < 35 and price_low < bb_lower and volume_ratio > 2.0
    overbought = rsi > 65 and price_high > bb_upper and volume_ratio > 2.0

    # Determine signal
    if oversold:
        signal = "buy"
    elif overbought:
        signal = "sell"
    else:
        signal = ""

    # Apply Fear & Greed filter if enabled
    if signal and fg_mode and fg_mode != "disabled" and _fg_filter:
        fg_check = _fg_filter.should_allow_trade(signal)
        fg_metadata = {
            'fg_value': fg_check['fg_value'],
            'fg_signal': fg_check['fg_signal'],
            'fg_mode': fg_mode,
            'fg_allowed': fg_check['allowed'],
            'fg_reason': fg_check['reason'],
            'fg_confidence': fg_check['fg_confidence']
        }

        if fg_filter_type == "hard" and not fg_check['allowed']:
            return "", None, fg_metadata

    if signal:
        return signal, current, fg_metadata

    return "", None, fg_metadata


def rsi_bb_volume_live_wrapper(df):
    """Wrapper for backward compatibility"""
    signal, candle, _ = rsi_bb_volume_live(df, fg_mode=None)
    return signal, candle


# Alias for backward compatibility
rsi_bb_volume = rsi_bb_volume_optimized_wrapper
