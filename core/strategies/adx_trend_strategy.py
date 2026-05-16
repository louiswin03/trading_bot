"""
ADX Trend Following Strategy - RANK 8 + Trailing SL
Optimized strategy with dynamic trailing stop loss

Entry Conditions:
- LONG: ADX > 30, DI+ > DI-, Price > EMA20 > EMA50, Volume > 1.8x
- SHORT: ADX > 30, DI- > DI+, Price < EMA20 < EMA50, Volume > 1.8x

Exit Conditions:
- TP: 4.0%
- Initial SL: 0.7%
- Trailing SL (STEP 2): 0.5%→BE, 1%→0.5%, 1.5%→1%, 2%→1.5%
- Signal Exit: ADX < 20 or price crosses EMA20
- Max Hold: 20 candles
"""

import pandas as pd
import numpy as np

# Strategy Parameters
ADX_THRESHOLD = 30
TP_PCT = 4.0
SL_PCT = 0.7
MAX_HOLD = 20
VOLUME_THRESHOLD = 1.8

# Trailing SL Steps: (gain_threshold_pct, new_sl_pct)
# When price reaches X% gain, move SL to Y%
TRAILING_SL_STEPS = [
    (0.5, 0),    # At 0.5% gain -> SL to break even (0%)
    (1.0, 0.5),  # At 1% gain -> SL to 0.5%
    (1.5, 1.0),  # At 1.5% gain -> SL to 1%
    (2.0, 1.5),  # At 2% gain -> SL to 1.5%
]

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
    """Calculate ADX and Directional Indicators"""
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    atr = calculate_atr(df, period)

    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()

    df['adx'] = adx
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di

    return df

def add_indicators(df):
    """Add all required indicators to dataframe"""
    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    return df

def adx_trend_strategy(df):
    """
    Main strategy function for backtesting (closed candles only)
    Returns: (signal, candle_data) or (None, None)
    """
    if len(df) < 55:
        return None, None

    # Use second to last candle (last closed candle)
    candle = df.iloc[-2]

    # Check LONG conditions
    bullish = (
        candle.get('adx', 0) > ADX_THRESHOLD and
        candle.get('plus_di', 0) > candle.get('minus_di', 0) and
        candle['close'] > candle['ema_20'] and
        candle['ema_20'] > candle['ema_50'] and
        candle.get('volume_ratio', 1) > VOLUME_THRESHOLD
    )

    # Check SHORT conditions
    bearish = (
        candle.get('adx', 0) > ADX_THRESHOLD and
        candle.get('minus_di', 0) > candle.get('plus_di', 0) and
        candle['close'] < candle['ema_20'] and
        candle['ema_20'] < candle['ema_50'] and
        candle.get('volume_ratio', 1) > VOLUME_THRESHOLD
    )

    if bullish:
        return 'BUY', candle
    elif bearish:
        return 'SELL', candle

    return None, None

def adx_trend_live(df):
    """
    Live signal detection (current forming candle)
    Returns: (signal, candle_data) or (None, None)
    """
    if len(df) < 55:
        return None, None

    # Use last candle (current forming)
    candle = df.iloc[-1]

    # Check LONG conditions
    bullish = (
        candle.get('adx', 0) > ADX_THRESHOLD and
        candle.get('plus_di', 0) > candle.get('minus_di', 0) and
        candle['close'] > candle['ema_20'] and
        candle['ema_20'] > candle['ema_50'] and
        candle.get('volume_ratio', 1) > VOLUME_THRESHOLD
    )

    # Check SHORT conditions
    bearish = (
        candle.get('adx', 0) > ADX_THRESHOLD and
        candle.get('minus_di', 0) > candle.get('plus_di', 0) and
        candle['close'] < candle['ema_20'] and
        candle['ema_20'] < candle['ema_50'] and
        candle.get('volume_ratio', 1) > VOLUME_THRESHOLD
    )

    if bullish:
        return 'BUY', candle
    elif bearish:
        return 'SELL', candle

    return None, None

def get_tp_sl_prices(entry_price, direction):
    """Calculate TP and initial SL prices"""
    if direction == 'BUY':
        tp = entry_price * (1 + TP_PCT / 100)
        sl = entry_price * (1 - SL_PCT / 100)
    else:  # SELL
        tp = entry_price * (1 - TP_PCT / 100)
        sl = entry_price * (1 + SL_PCT / 100)

    return tp, sl

def calculate_trailing_sl(entry_price, best_price, direction, current_sl):
    """
    Returns: (new_sl_price, triggered_steps)
      triggered_steps = list of (gain_threshold, sl_pct) for EVERY step
      crossed since current_sl, ascending. Empty list if none crossed.
    """
    if direction == 'BUY':
        gain_pct = ((best_price - entry_price) / entry_price) * 100
    else:
        gain_pct = ((entry_price - best_price) / entry_price) * 100

    triggered_steps = []
    new_sl = current_sl

    for gain_threshold, sl_pct in sorted(TRAILING_SL_STEPS):
        if gain_pct >= gain_threshold:
            if direction == 'BUY':
                potential_sl = entry_price * (1 + sl_pct / 100)
                if potential_sl > new_sl:
                    triggered_steps.append((gain_threshold, sl_pct))
                    new_sl = potential_sl
            else:
                potential_sl = entry_price * (1 - sl_pct / 100)
                if potential_sl < new_sl:
                    triggered_steps.append((gain_threshold, sl_pct))
                    new_sl = potential_sl

    return new_sl, triggered_steps

def get_current_sl_level(entry_price, best_price, direction):
    """
    Get the current trailing SL level description

    Returns: string describing current SL level (e.g., "Break Even", "0.5%", etc.)
    """
    if direction == 'BUY':
        gain_pct = ((best_price - entry_price) / entry_price) * 100
    else:
        gain_pct = ((entry_price - best_price) / entry_price) * 100

    current_level = f"-{SL_PCT}% (initial)"

    for gain_threshold, sl_pct in sorted(TRAILING_SL_STEPS, reverse=True):
        if gain_pct >= gain_threshold:
            if sl_pct == 0:
                current_level = "Break Even"
            else:
                current_level = f"+{sl_pct}%"
            break

    return current_level

def check_exit_conditions(current_candle, entry_price, direction, candles_held, best_price=None, current_sl=None):
    """
    Check if any exit condition is met

    Args:
        current_candle: Current candle data
        entry_price: Entry price
        direction: 'BUY' or 'SELL'
        candles_held: Number of candles held
        best_price: Best price reached (for trailing SL). If None, trailing SL is disabled.
        current_sl: Current SL price (for trailing SL). If None, uses initial SL.

    Returns: (should_exit, reason, exit_price)
    """
    tp, initial_sl = get_tp_sl_prices(entry_price, direction)

    # Use trailing SL if best_price is provided
    if best_price is not None and current_sl is not None:
        sl = current_sl
    else:
        sl = initial_sl

    if direction == 'BUY':
        # Take Profit
        if current_candle['high'] >= tp:
            return True, 'TP', tp

        # Stop Loss (initial or trailing)
        if current_candle['low'] <= sl:
            if sl > initial_sl:
                return True, 'Trailing SL', sl
            else:
                return True, 'SL', sl

        # Signal Exit (trend weakening)
        if current_candle.get('adx', 0) < 20 or current_candle['close'] < current_candle['ema_20']:
            return True, 'Signal Exit', current_candle['close']

    else:  # SELL
        # Take Profit
        if current_candle['low'] <= tp:
            return True, 'TP', tp

        # Stop Loss (initial or trailing)
        if current_candle['high'] >= sl:
            if sl < initial_sl:
                return True, 'Trailing SL', sl
            else:
                return True, 'SL', sl

        # Signal Exit (trend weakening)
        if current_candle.get('adx', 0) < 20 or current_candle['close'] > current_candle['ema_20']:
            return True, 'Signal Exit', current_candle['close']

    # Max Hold
    if candles_held >= MAX_HOLD:
        return True, 'Max Hold', current_candle['close']

    return False, None, None

def get_strategy_info():
    """Return strategy metadata"""
    return {
        'name': 'ADX Trend Following + Trailing SL',
        'version': 'RANK 8 v2',
        'timeframe': '4h',
        'parameters': {
            'adx_threshold': ADX_THRESHOLD,
            'tp_pct': TP_PCT,
            'sl_pct': SL_PCT,
            'max_hold': MAX_HOLD,
            'volume_threshold': VOLUME_THRESHOLD,
            'trailing_sl_steps': TRAILING_SL_STEPS
        },
        'backtest_stats': {
            'annual_return': 46.5,
            'max_drawdown': 7.79,
            'win_rate': 50.9,
            'profit_factor': 2.43,
            'total_trades': 593,
            'years_tested': 8,
            'all_years_positive': True
        }
    }
