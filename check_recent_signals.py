"""
Script pour vérifier pourquoi pas de signaux depuis le 21 novembre
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime
from core.data_sources.market_data import get_ohlcv

# Strategy Parameters
PAIR = 'BTCUSDT'
INTERVAL = '4h'
LIMIT = 500  # Dernières 500 bougies (environ 3 mois)

ADX_THRESHOLD = 30
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

def main():
    print("\n" + "="*100)
    print("ANALYSE DES SIGNAUX RECENTS - Pourquoi pas de trades depuis le 21 novembre ?")
    print("="*100)

    print("\nFetching recent data...")
    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")

    # Calculate indicators
    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']

    # Convert timestamp
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Analyser les 50 dernières bougies
    print("\n" + "="*100)
    print("DERNIÈRES 20 BOUGIES (depuis le 21 novembre)")
    print("="*100)
    print("\nFormat: Date | Close | ADX | +DI | -DI | EMA20 | EMA50 | Vol Ratio | Signal ?")
    print("-"*100)

    recent = df.tail(20)

    for idx, row in recent.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d %H:%M')
        close = row['close']
        adx = row.get('adx', 0)
        plus_di = row.get('plus_di', 0)
        minus_di = row.get('minus_di', 0)
        ema_20 = row['ema_20']
        ema_50 = row['ema_50']
        vol_ratio = row.get('volume_ratio', 0)

        # Check conditions
        bullish = (adx > ADX_THRESHOLD and
                  plus_di > minus_di and
                  close > ema_20 and
                  ema_20 > ema_50 and
                  vol_ratio > VOLUME_THRESHOLD)

        bearish = (adx > ADX_THRESHOLD and
                  minus_di > plus_di and
                  close < ema_20 and
                  ema_20 < ema_50 and
                  vol_ratio > VOLUME_THRESHOLD)

        signal = ""
        if bullish:
            signal = "LONG !!!"
        elif bearish:
            signal = "SHORT !!!"
        else:
            # Identify which condition is failing
            failing = []
            if adx <= ADX_THRESHOLD:
                failing.append(f"ADX={adx:.1f}<{ADX_THRESHOLD}")
            if vol_ratio <= VOLUME_THRESHOLD:
                failing.append(f"Vol={vol_ratio:.2f}<{VOLUME_THRESHOLD}")
            if close > ema_20 and ema_20 > ema_50:
                if plus_di <= minus_di:
                    failing.append("+DI<-DI")
            elif close < ema_20 and ema_20 < ema_50:
                if minus_di <= plus_di:
                    failing.append("-DI<+DI")
            else:
                failing.append("EMA alignment")
            signal = "NO (" + ", ".join(failing[:2]) + ")"

        print(f"{date_str} | ${close:>8,.0f} | ADX:{adx:>5.1f} | +DI:{plus_di:>5.1f} | -DI:{minus_di:>5.1f} | " +
              f"EMA20:${ema_20:>8,.0f} | EMA50:${ema_50:>8,.0f} | Vol:{vol_ratio:>4.2f} | {signal}")

    # Summary
    print("\n" + "="*100)
    print("RESUME")
    print("="*100)

    last = df.iloc[-1]
    print(f"\nDERNIERE BOUGIE : {last['date'].strftime('%Y-%m-%d %H:%M')}")
    print(f"Prix BTC : ${last['close']:,.2f}")
    print(f"ADX : {last.get('adx', 0):.2f} (seuil: {ADX_THRESHOLD})")
    print(f"+DI : {last.get('plus_di', 0):.2f}")
    print(f"-DI : {last.get('minus_di', 0):.2f}")
    print(f"Volume Ratio : {last.get('volume_ratio', 0):.2f}x (seuil: {VOLUME_THRESHOLD}x)")
    print(f"EMA 20 : ${last['ema_20']:,.2f}")
    print(f"EMA 50 : ${last['ema_50']:,.2f}")
    print(f"Close vs EMA20 : {'Au dessus' if last['close'] > last['ema_20'] else 'En dessous'}")
    print(f"EMA20 vs EMA50 : {'Au dessus' if last['ema_20'] > last['ema_50'] else 'En dessous'}")

    # Count signals in last 50 candles
    signals_count = 0
    for idx, row in df.tail(50).iterrows():
        bullish = (row.get('adx', 0) > ADX_THRESHOLD and
                  row.get('plus_di', 0) > row.get('minus_di', 0) and
                  row['close'] > row['ema_20'] and
                  row['ema_20'] > row['ema_50'] and
                  row.get('volume_ratio', 0) > VOLUME_THRESHOLD)

        bearish = (row.get('adx', 0) > ADX_THRESHOLD and
                  row.get('minus_di', 0) > row.get('plus_di', 0) and
                  row['close'] < row['ema_20'] and
                  row['ema_20'] < row['ema_50'] and
                  row.get('volume_ratio', 0) > VOLUME_THRESHOLD)

        if bullish or bearish:
            signals_count += 1

    print(f"\nSignaux dans les 50 dernières bougies : {signals_count}")
    print(f"Cela représente environ {50*4} heures = {50*4/24:.1f} jours")

    print("\n" + "="*100 + "\n")

if __name__ == "__main__":
    main()
