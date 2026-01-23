"""
Backtest comparison: Simple MA ADX vs Wilder ADX
Compare performance and check specific date
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from core.data_sources.market_data import get_ohlcv

PAIR = 'BTCUSDT'
INTERVAL = '4h'
LIMIT = 20000
BINANCE_FEE = 0.001
INITIAL_CAPITAL = 10000

ADX_THRESHOLD = 30
TP_PCT = 4.0
SL_PCT = 0.7
MAX_HOLD = 20
VOLUME_THRESHOLD = 1.8

TRAILING_SL_STEPS = [(0.5, 0), (1.0, 0.5), (1.5, 1.0), (2.0, 1.5)]

def wilder_smoothing(data, period):
    """Wilder's smoothing method (RMA/SMMA)"""
    result = pd.Series(index=data.index, dtype='float64')
    result.iloc[period-1] = data.iloc[:period].mean()
    for i in range(period, len(data)):
        result.iloc[i] = (result.iloc[i-1] * (period - 1) + data.iloc[i]) / period
    return result

def calculate_adx_simple(df, period=14):
    """Simple MA method (current)"""
    df = df.copy()

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(period).mean()

    # Directional Movement
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    # DI
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()

    df['adx'] = adx
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    return df

def calculate_adx_wilder(df, period=14):
    """Wilder method (TradingView)"""
    df = df.copy()

    # ATR with Wilder smoothing
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = wilder_smoothing(true_range, period)

    # Directional Movement
    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    # DI with Wilder smoothing
    smoothed_plus_dm = wilder_smoothing(plus_dm, period)
    smoothed_minus_dm = wilder_smoothing(minus_dm, period)
    plus_di = 100 * (smoothed_plus_dm / atr)
    minus_di = 100 * (smoothed_minus_dm / atr)

    # ADX with Wilder smoothing
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = wilder_smoothing(dx, period)

    df['adx'] = adx
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    return df

def backtest(df, adx_method='simple'):
    """Run backtest with specified ADX method"""

    if adx_method == 'simple':
        df = calculate_adx_simple(df)
    else:
        df = calculate_adx_wilder(df)

    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']

    trades = []
    capital = INITIAL_CAPITAL
    in_trade = False

    for i in range(55, len(df) - 1):
        if not in_trade:
            prev = df.iloc[i - 1]

            bullish = (prev.get('adx', 0) > ADX_THRESHOLD and
                      prev.get('plus_di', 0) > prev.get('minus_di', 0) and
                      prev['close'] > prev['ema_20'] and
                      prev['ema_20'] > prev['ema_50'] and
                      prev.get('volume_ratio', 1) > VOLUME_THRESHOLD)

            bearish = (prev.get('adx', 0) > ADX_THRESHOLD and
                      prev.get('minus_di', 0) > prev.get('plus_di', 0) and
                      prev['close'] < prev['ema_20'] and
                      prev['ema_20'] < prev['ema_50'] and
                      prev.get('volume_ratio', 1) > VOLUME_THRESHOLD)

            if bullish or bearish:
                in_trade = True
                entry_price = prev['close']
                entry_i = i - 1
                direction = 'long' if bullish else 'short'
                quantity = (capital * 0.98) / entry_price
                entry_fee = entry_price * quantity * BINANCE_FEE
                capital -= entry_fee

                if direction == 'long':
                    tp_price = entry_price * (1 + TP_PCT / 100)
                    sl_price = entry_price * (1 - SL_PCT / 100)
                else:
                    tp_price = entry_price * (1 - TP_PCT / 100)
                    sl_price = entry_price * (1 + SL_PCT / 100)

                best_price = entry_price

        else:
            current = df.iloc[i]
            exit_price = None
            exit_reason = None

            if direction == 'long':
                if current['high'] > best_price:
                    best_price = current['high']
                current_gain_pct = ((best_price - entry_price) / entry_price) * 100
            else:
                if current['low'] < best_price:
                    best_price = current['low']
                current_gain_pct = ((entry_price - best_price) / entry_price) * 100

            for gain_threshold, new_sl in TRAILING_SL_STEPS:
                if current_gain_pct >= gain_threshold:
                    if direction == 'long':
                        new_sl_price = entry_price * (1 + new_sl / 100)
                        if new_sl_price > sl_price:
                            sl_price = new_sl_price
                    else:
                        new_sl_price = entry_price * (1 - new_sl / 100)
                        if new_sl_price < sl_price:
                            sl_price = new_sl_price

            initial_sl = entry_price * (1 - SL_PCT / 100) if direction == 'long' else entry_price * (1 + SL_PCT / 100)

            if direction == 'long':
                if current['high'] >= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['low'] <= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price > initial_sl else 'SL'
                elif current.get('adx', 0) < 20 or current['close'] < current['ema_20']:
                    exit_price = current['close']
                    exit_reason = 'Signal Exit'
            else:
                if current['low'] <= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['high'] >= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price < initial_sl else 'SL'
                elif current.get('adx', 0) < 20 or current['close'] > current['ema_20']:
                    exit_price = current['close']
                    exit_reason = 'Signal Exit'

            if exit_price is None and (i - entry_i) >= MAX_HOLD:
                exit_price = current['close']
                exit_reason = 'Max Hold'

            if exit_price:
                if direction == 'long':
                    pnl_gross = (exit_price - entry_price) * quantity
                else:
                    pnl_gross = (entry_price - exit_price) * quantity

                exit_fee = exit_price * quantity * BINANCE_FEE
                pnl_net = pnl_gross - exit_fee
                capital += pnl_net

                trades.append({'pnl': float(pnl_net)})
                in_trade = False

    return trades, capital

def main():
    print("\n" + "="*100)
    print("BACKTEST COMPARISON: Simple MA ADX vs Wilder ADX")
    print("="*100)

    print(f"\nFetching data for {PAIR} {INTERVAL}...")
    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")

    # Check specific date first
    print("\n" + "="*100)
    print("VERIFICATION: 20 Novembre 2024 17:00")
    print("="*100)

    df_simple = calculate_adx_simple(df.copy())
    df_wilder = calculate_adx_wilder(df.copy())
    df_simple['timestamp_dt'] = pd.to_datetime(df_simple['timestamp'], unit='ms').dt.tz_localize(None)
    df_wilder['timestamp_dt'] = pd.to_datetime(df_wilder['timestamp'], unit='ms').dt.tz_localize(None)

    target = pd.to_datetime('2024-11-20 17:00').tz_localize(None)
    df_simple['diff'] = abs(df_simple['timestamp_dt'] - target)
    idx = df_simple['diff'].idxmin()

    row_simple = df_simple.iloc[idx]
    row_wilder = df_wilder.iloc[idx]

    print(f"\nDate: {row_simple['timestamp_dt']}")
    print(f"Prix: ${row_simple['close']:.2f}")
    print(f"\nADX Simple MA:  {row_simple['adx']:.2f}")
    print(f"ADX Wilder:     {row_wilder['adx']:.2f}")
    print(f"TradingView:    37.00 (selon vous)")
    print(f"\nDifference Simple vs TradingView: {row_simple['adx'] - 37:.2f}")
    print(f"Difference Wilder vs TradingView: {row_wilder['adx'] - 37:.2f}")

    if abs(row_wilder['adx'] - 37) < abs(row_simple['adx'] - 37):
        print("\n[OK] La methode de Wilder est PLUS PROCHE de TradingView!")
    else:
        print("\n[??] La methode Simple est plus proche... Verifier les parametres TradingView")

    # Backtest comparison
    print("\n" + "="*100)
    print("BACKTEST COMPARISON")
    print("="*100)

    print("\nBacktest avec Simple MA...")
    trades_simple, capital_simple = backtest(df.copy(), 'simple')

    print("Backtest avec Wilder...")
    trades_wilder, capital_wilder = backtest(df.copy(), 'wilder')

    wins_simple = len([t for t in trades_simple if t['pnl'] > 0])
    wins_wilder = len([t for t in trades_wilder if t['pnl'] > 0])

    return_simple = ((capital_simple - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    return_wilder = ((capital_wilder - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    winrate_simple = (wins_simple / len(trades_simple) * 100) if trades_simple else 0
    winrate_wilder = (wins_wilder / len(trades_wilder) * 100) if trades_wilder else 0

    print("\n" + "="*100)
    print("RESULTATS")
    print("="*100)

    print(f"\n{'Metrique':<25} | {'Simple MA':<20} | {'Wilder':<20} | {'Meilleur'}")
    print("-"*100)
    print(f"{'Capital Final':<25} | ${capital_simple:<19,.2f} | ${capital_wilder:<19,.2f} | {'Simple' if capital_simple > capital_wilder else 'Wilder'}")
    print(f"{'Rendement Total':<25} | {return_simple:<19.2f}% | {return_wilder:<19.2f}% | {'Simple' if return_simple > return_wilder else 'Wilder'}")
    print(f"{'Total Trades':<25} | {len(trades_simple):<20} | {len(trades_wilder):<20} | {'Simple' if len(trades_simple) > len(trades_wilder) else 'Wilder'}")
    print(f"{'Win Rate':<25} | {winrate_simple:<19.1f}% | {winrate_wilder:<19.1f}% | {'Simple' if winrate_simple > winrate_wilder else 'Wilder'}")

    print("\n" + "="*100)
    print("CONCLUSION")
    print("="*100)

    if capital_wilder > capital_simple:
        diff_pct = ((capital_wilder - capital_simple) / capital_simple) * 100
        print(f"\nLa methode de WILDER performe MIEUX: +{diff_pct:.2f}%")
        print(f"Capital final: ${capital_wilder:,.2f} vs ${capital_simple:,.2f}")
        print(f"\n[RECOMMANDATION] Utiliser la methode de Wilder (TradingView)")
    else:
        diff_pct = ((capital_simple - capital_wilder) / capital_wilder) * 100
        print(f"\nLa methode SIMPLE MA performe MIEUX: +{diff_pct:.2f}%")
        print(f"Capital final: ${capital_simple:,.2f} vs ${capital_wilder:,.2f}")
        print(f"\n[RECOMMANDATION] Garder la methode Simple MA (actuelle)")

    print("="*100 + "\n")

if __name__ == "__main__":
    main()
