"""
Analyse une date specifique pour comprendre pourquoi il n'y a pas eu de signal
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from datetime import datetime
from core.data_sources.market_data import get_ohlcv

# Strategy Parameters
PAIR = 'BTCUSDT'
INTERVAL = '4h'
LIMIT = 20000

ADX_THRESHOLD = 30
TP_PCT = 4.0
SL_PCT = 0.7
MAX_HOLD = 20
VOLUME_THRESHOLD = 1.8

def calculate_atr(df, period=14):
    """Calculate ATR"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
    """Calculate ADX"""
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

def analyze_date(df, target_date_str):
    """Analyze a specific date"""

    df = df.copy()
    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Parse target date (make it timezone-naive to match df)
    target_date = pd.to_datetime(target_date_str).tz_localize(None)

    # Find candles around this date
    df['timestamp_dt'] = pd.to_datetime(df['timestamp_dt']).dt.tz_localize(None)
    df['date_diff'] = abs(df['timestamp_dt'] - target_date)
    closest_idx = df['date_diff'].idxmin()

    # Show candles around this date (before and after)
    start_idx = max(0, closest_idx - 5)
    end_idx = min(len(df), closest_idx + 6)

    print("\n" + "="*100)
    print(f"ANALYSE DE LA DATE : {target_date_str}")
    print("="*100)

    for i in range(start_idx, end_idx):
        row = df.iloc[i]
        is_target = i == closest_idx

        # Check if conditions are met
        bullish = (row.get('adx', 0) > ADX_THRESHOLD and
                  row.get('plus_di', 0) > row.get('minus_di', 0) and
                  row['close'] > row['ema_20'] and
                  row['ema_20'] > row['ema_50'] and
                  row.get('volume_ratio', 1) > VOLUME_THRESHOLD)

        bearish = (row.get('adx', 0) > ADX_THRESHOLD and
                  row.get('minus_di', 0) > row.get('plus_di', 0) and
                  row['close'] < row['ema_20'] and
                  row['ema_20'] < row['ema_50'] and
                  row.get('volume_ratio', 1) > VOLUME_THRESHOLD)

        signal = "LONG" if bullish else ("SHORT" if bearish else "AUCUN")

        marker = " >>> CIBLE <<<" if is_target else ""

        print(f"\n{'-'*100}")
        print(f"Date: {row['timestamp_dt'].strftime('%Y-%m-%d %H:%M')} {marker}")
        print(f"Signal: {signal}")
        print(f"\nPrix:")
        print(f"  Open:   ${row['open']:.2f}")
        print(f"  High:   ${row['high']:.2f}")
        print(f"  Low:    ${row['low']:.2f}")
        print(f"  Close:  ${row['close']:.2f}")
        print(f"\nIndicateurs:")
        print(f"  ADX:        {row.get('adx', 0):.2f} (seuil: {ADX_THRESHOLD}) {'[OK]' if row.get('adx', 0) > ADX_THRESHOLD else '[NON]'}")
        print(f"  DI+:        {row.get('plus_di', 0):.2f}")
        print(f"  DI-:        {row.get('minus_di', 0):.2f}")
        print(f"  DI+ > DI-:  {'[OK]' if row.get('plus_di', 0) > row.get('minus_di', 0) else '[NON]'}")
        print(f"  DI- > DI+:  {'[OK]' if row.get('minus_di', 0) > row.get('plus_di', 0) else '[NON]'}")
        print(f"  EMA 20:     ${row['ema_20']:.2f}")
        print(f"  EMA 50:     ${row['ema_50']:.2f}")
        print(f"  EMA20 > EMA50: {'[OK]' if row['ema_20'] > row['ema_50'] else '[NON]'}")
        print(f"  Prix > EMA20:  {'[OK]' if row['close'] > row['ema_20'] else '[NON]'}")
        print(f"  Prix < EMA20:  {'[OK]' if row['close'] < row['ema_20'] else '[NON]'}")
        print(f"\nVolume:")
        print(f"  Volume:     {row['volume']:.0f}")
        print(f"  Vol MA(20): {row['volume_ma']:.0f}")
        print(f"  Ratio:      {row.get('volume_ratio', 0):.2f}x (seuil: {VOLUME_THRESHOLD}x) {'[OK]' if row.get('volume_ratio', 0) > VOLUME_THRESHOLD else '[NON]'}")

        if is_target:
            print(f"\n{'='*100}")
            print("VERIFICATION DES CONDITIONS POUR LONG:")
            print(f"{'='*100}")
            print(f"1. ADX > 30:          {row.get('adx', 0):.2f} > 30 = {'[OK]' if row.get('adx', 0) > ADX_THRESHOLD else '[NON]'}")
            print(f"2. DI+ > DI-:         {row.get('plus_di', 0):.2f} > {row.get('minus_di', 0):.2f} = {'[OK]' if row.get('plus_di', 0) > row.get('minus_di', 0) else '[NON]'}")
            print(f"3. Prix > EMA20:      {row['close']:.2f} > {row['ema_20']:.2f} = {'[OK]' if row['close'] > row['ema_20'] else '[NON]'}")
            print(f"4. EMA20 > EMA50:     {row['ema_20']:.2f} > {row['ema_50']:.2f} = {'[OK]' if row['ema_20'] > row['ema_50'] else '[NON]'}")
            print(f"5. Volume > 1.8x:     {row.get('volume_ratio', 0):.2f} > 1.8 = {'[OK]' if row.get('volume_ratio', 0) > VOLUME_THRESHOLD else '[NON]'}")

            print(f"\n{'='*100}")
            print("VERIFICATION DES CONDITIONS POUR SHORT:")
            print(f"{'='*100}")
            print(f"1. ADX > 30:          {row.get('adx', 0):.2f} > 30 = {'[OK]' if row.get('adx', 0) > ADX_THRESHOLD else '[NON]'}")
            print(f"2. DI- > DI+:         {row.get('minus_di', 0):.2f} > {row.get('plus_di', 0):.2f} = {'[OK]' if row.get('minus_di', 0) > row.get('plus_di', 0) else '[NON]'}")
            print(f"3. Prix < EMA20:      {row['close']:.2f} < {row['ema_20']:.2f} = {'[OK]' if row['close'] < row['ema_20'] else '[NON]'}")
            print(f"4. EMA20 < EMA50:     {row['ema_20']:.2f} < {row['ema_50']:.2f} = {'[OK]' if row['ema_20'] < row['ema_50'] else '[NON]'}")
            print(f"5. Volume > 1.8x:     {row.get('volume_ratio', 0):.2f} > 1.8 = {'[OK]' if row.get('volume_ratio', 0) > VOLUME_THRESHOLD else '[NON]'}")

            if bullish:
                print(f"\n{'='*100}")
                print("RESULTAT: TOUTES LES CONDITIONS LONG SONT REMPLIES ! Signal LONG")
                print(f"{'='*100}")
            elif bearish:
                print(f"\n{'='*100}")
                print("RESULTAT: TOUTES LES CONDITIONS SHORT SONT REMPLIES ! Signal SHORT")
                print(f"{'='*100}")
            else:
                print(f"\n{'='*100}")
                print("RESULTAT: Les conditions ne sont PAS toutes remplies. AUCUN SIGNAL.")
                print(f"{'='*100}")

    print("\n" + "="*100)
    print("NOTE IMPORTANTE:")
    print("="*100)
    print("Le bot utilise la bougie CLOSE (precedente) pour generer les signaux.")
    print("Donc si tu regardes une bougie en formation, elle ne generera un signal")
    print("que quand elle sera fermee (dans 4h pour du 4h timeframe).")
    print("="*100 + "\n")

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyze_date.py YYYY-MM-DD")
        print("Exemple: python analyze_date.py 2024-11-20")
        sys.exit(1)

    target_date = sys.argv[1]

    print("\n" + "="*100)
    print("ANALYSE DE DATE - STRATEGIE ADX TREND")
    print("="*100)
    print(f"\nPaire: {PAIR} | Timeframe: {INTERVAL}")
    print("Fetching data...")

    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")

    analyze_date(df, target_date)

if __name__ == "__main__":
    main()
