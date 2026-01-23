"""
Compare ADX calculation: Simple MA vs Wilder's Smoothing (RMA)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from core.data_sources.market_data import get_ohlcv

PAIR = 'BTCUSDT'
INTERVAL = '4h'
LIMIT = 500

def wilder_smoothing(data, period):
    """
    Wilder's smoothing method (also called RMA or SMMA)
    First value: simple average of first N values
    Subsequent values: (previous_value * (N-1) + current_value) / N
    """
    result = pd.Series(index=data.index, dtype='float64')

    # First value: simple average
    result.iloc[period-1] = data.iloc[:period].mean()

    # Subsequent values: Wilder's smoothing
    for i in range(period, len(data)):
        result.iloc[i] = (result.iloc[i-1] * (period - 1) + data.iloc[i]) / period

    return result

def calculate_atr_simple(df, period=14):
    """Calculate ATR with Simple Moving Average (current method)"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()

def calculate_atr_wilder(df, period=14):
    """Calculate ATR with Wilder's Smoothing (TradingView method)"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return wilder_smoothing(true_range, period)

def calculate_adx_simple(df, period=14):
    """Calculate ADX with Simple Moving Average (current method)"""
    df = df.copy()

    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    atr = calculate_atr_simple(df, period)

    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()

    return adx, plus_di, minus_di

def calculate_adx_wilder(df, period=14):
    """Calculate ADX with Wilder's Smoothing (TradingView method)"""
    df = df.copy()

    high_diff = df['high'].diff()
    low_diff = -df['low'].diff()

    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

    atr = calculate_atr_wilder(df, period)

    # Smooth the directional movements with Wilder's method
    smoothed_plus_dm = wilder_smoothing(plus_dm, period)
    smoothed_minus_dm = wilder_smoothing(minus_dm, period)

    plus_di = 100 * (smoothed_plus_dm / atr)
    minus_di = 100 * (smoothed_minus_dm / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = wilder_smoothing(dx, period)

    return adx, plus_di, minus_di

def main():
    print("\n" + "="*100)
    print("COMPARAISON METHODES ADX : Simple MA vs Wilder's Smoothing")
    print("="*100)
    print(f"\nPaire: {PAIR} | Timeframe: {INTERVAL}")
    print("Fetching data...")

    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")
    print("\nCalculating ADX with both methods...")

    # Calculate with both methods
    adx_simple, di_plus_simple, di_minus_simple = calculate_adx_simple(df)
    adx_wilder, di_plus_wilder, di_minus_wilder = calculate_adx_wilder(df)

    # Add to dataframe
    df['adx_simple'] = adx_simple
    df['adx_wilder'] = adx_wilder
    df['di_plus_simple'] = di_plus_simple
    df['di_plus_wilder'] = di_plus_wilder
    df['di_minus_simple'] = di_minus_simple
    df['di_minus_wilder'] = di_minus_wilder
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Show last 20 candles comparison
    print("\n" + "="*100)
    print("COMPARAISON DES 20 DERNIERES BOUGIES")
    print("="*100)
    print(f"\n{'Date':<20} | {'ADX Simple':<12} | {'ADX Wilder':<12} | {'Difference':<12} | {'> 30?'}")
    print("-"*100)

    for i in range(-20, 0):
        row = df.iloc[i]
        date_str = row['timestamp_dt'].strftime('%Y-%m-%d %H:%M')
        adx_s = row['adx_simple']
        adx_w = row['adx_wilder']
        diff = adx_w - adx_s if not pd.isna(adx_w) and not pd.isna(adx_s) else 0

        simple_over_30 = 'OUI' if not pd.isna(adx_s) and adx_s > 30 else 'NON'
        wilder_over_30 = 'OUI' if not pd.isna(adx_w) and adx_w > 30 else 'NON'

        print(f"{date_str:<20} | {adx_s:>11.2f} | {adx_w:>11.2f} | {diff:>+11.2f} | S:{simple_over_30} W:{wilder_over_30}")

    # Statistics
    valid_data = df[df['adx_simple'].notna() & df['adx_wilder'].notna()]

    avg_simple = valid_data['adx_simple'].mean()
    avg_wilder = valid_data['adx_wilder'].mean()

    simple_over_30_count = (valid_data['adx_simple'] > 30).sum()
    wilder_over_30_count = (valid_data['adx_wilder'] > 30).sum()

    simple_over_30_pct = (simple_over_30_count / len(valid_data)) * 100
    wilder_over_30_pct = (wilder_over_30_count / len(valid_data)) * 100

    print("\n" + "="*100)
    print("STATISTIQUES GLOBALES")
    print("="*100)
    print(f"ADX Moyen (Simple MA):        {avg_simple:.2f}")
    print(f"ADX Moyen (Wilder):           {avg_wilder:.2f}")
    print(f"Difference moyenne:           {avg_wilder - avg_simple:+.2f}")
    print(f"\nBougies avec ADX > 30:")
    print(f"  Simple MA:  {simple_over_30_count} ({simple_over_30_pct:.1f}%)")
    print(f"  Wilder:     {wilder_over_30_count} ({wilder_over_30_pct:.1f}%)")
    print(f"  Difference: {wilder_over_30_count - simple_over_30_count:+d} bougies")

    print("\n" + "="*100)
    print("CONCLUSION")
    print("="*100)
    print("La methode de Wilder (utilisee par TradingView) donne des valeurs:")
    print(f"  - En moyenne {avg_wilder - avg_simple:.2f} points plus elevees")
    print(f"  - {wilder_over_30_count - simple_over_30_count} bougies de plus au-dessus de 30")
    print("\nC'est normal car le lissage de Wilder est moins reactif mais plus stable.")
    print("TradingView utilise la methode de Wilder par defaut.")
    print("\n" + "="*100)

    # Ask if user wants to update the strategy
    print("\nVoulez-vous mettre a jour la strategie pour utiliser la methode de Wilder?")
    print("ATTENTION: Cela changera les performances du backtest!")
    print("\nPour mettre a jour, executez: python update_adx_to_wilder.py")
    print("="*100 + "\n")

if __name__ == "__main__":
    main()
