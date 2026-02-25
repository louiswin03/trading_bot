import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pandas_ta as ta # Je vais utiliser pandas_ta pour simplifier les calculs techniques si disponible, sinon standard.
# Allons-y en standard pandas/numpy pour ne pas dépendre de lib externe non installée.

def calculate_indicators(df):
    # 1. Moving Averages (Trend Filter)
    df['SMA_Fast'] = df['Close'].rolling(window=21).mean()
    df['SMA_Slow'] = df['Close'].rolling(window=55).mean()
    
    # 2. Volume Analysis (VSA)
    # ma0 = ta.sma(volume, 30)
    # ma2 = ma0 * 1.5
    df['Vol_SMA'] = df['Volume'].rolling(window=30).mean()
    df['Vol_Condition'] = df['Volume'] > (df['Vol_SMA'] * 1.5)
    
    # 3. Candle Colors & Sizes
    # Green = 1, Red = -1
    # Close > Open
    df['Is_Green'] = df['Close'] > df['Open']
    df['Is_Red'] = df['Close'] < df['Open']
    
    df['Body_Size'] = (df['Close'] - df['Open']).abs()
    
    # 4. Engulfing Pattern
    # Bullish Engulfing: Current Green, Prev Red, Current Body > Prev Body
    # Shift(1) = Previous candle
    df['Prev_Is_Red'] = df['Is_Red'].shift(1)
    df['Prev_Is_Green'] = df['Is_Green'].shift(1)
    df['Prev_Body_Size'] = df['Body_Size'].shift(1)
    
    # Bullish Engulfing Logic
    df['Bullish_Engulfing'] = (
        (df['Is_Green']) & 
        (df['Prev_Is_Red']) & 
        (df['Body_Size'] > df['Prev_Body_Size'])
    )
    
    # Bearish Engulfing Logic
    df['Bearish_Engulfing'] = (
        (df['Is_Red']) & 
        (df['Prev_Is_Green']) & 
        (df['Body_Size'] > df['Prev_Body_Size'])
    )
    
    # 5. 3 Line Strike Pattern
    # Bearish 3LS: 3 Green candles followed by Bearish Engulfing
    # Indices: Current=0 (Bear Engulf), 1=Green, 2=Green, 3=Green
    # Note: Bearish Engulfing a déjà vérifié que Prev (1) est Green.
    # Donc on doit juste vérifier que shift(2) et shift(3) sont Green.
    
    df['Bearish_3LS'] = (
        df['Bearish_Engulfing'] &
        df['Is_Green'].shift(2) &
        df['Is_Green'].shift(3)
    )
    
    # Bullish 3LS: 3 Red candles followed by Bullish Engulfing
    # Bullish Engulfing vérifie déjà que Prev (1) est Red.
    # On vérifie shift(2) et shift(3) Red.
    df['Bullish_3LS'] = (
        df['Bullish_Engulfing'] &
        df['Is_Red'].shift(2) &
        df['Is_Red'].shift(3)
    )
    
    return df

def run_backtest():
    print("--- Démarrage du Backtest 3 Line Strike (3LS) ---")
    
    # 1. Téléchargement des données
    symbol = "BTC-USD"
    interval = "1h"
    download_period = "2y"
    backtest_days = 365
    fees_pct = 0.001 # 0.1%
    
    print(f"Téléchargement des données pour {symbol} ({interval}, {download_period})...")
    df = yf.download(symbol, period=download_period, interval=interval, progress=False)
    
    if df.empty:
        print("Erreur: Pas de données.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df = df.dropna()
    print(f"Bougies récupérées: {len(df)}")
    
    # 2. Calcul des indicateurs
    print("Calcul des indicateurs...")
    df = calculate_indicators(df)
    
    # 3. Troncature pour Backtest
    cutoff_idx = len(df) - (backtest_days * 24)
    if cutoff_idx < 0: cutoff_idx = 0
    df = df.iloc[cutoff_idx:].copy()
    
    # 4. Boucle de Backtest
    print(f"Simulation sur {len(df)} bougies...")
    
    capital = 10000
    equity = [capital]
    trades = []
    position = None 
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_index = None
    entry_capital = 0.0
    
    # Paramètres Risk Management (inspirés du script)
    # Le script utilise Risk/Reward = 1.0 par défaut.
    # SL = Low - buffer (Long)
    # TP = Close + (Close - SL) * 1.0
    RISK_REWARD = 1.0 
    
    for currentRow in df.itertuples():
        
        # --- Gestion Sorties ---
        if position == 'Long':
            exit_price = None
            reason = None
            
            if currentRow.Low <= sl_price:
                exit_price = sl_price
                reason = 'SL'
            elif currentRow.High >= tp_price:
                exit_price = tp_price
                reason = 'TP'
                
            if exit_price:
                gross_pnl_pct = (exit_price - entry_price) / entry_price
                gross_amt = entry_capital * gross_pnl_pct
                
                # Fees
                entry_fee = entry_capital * fees_pct
                exit_val = entry_capital + gross_amt
                exit_fee = exit_val * fees_pct
                total_fees = entry_fee + exit_fee
                
                net_pnl = gross_amt - total_fees
                capital += net_pnl
                
                trades.append({
                    'Type': 'Long',
                    'Time': currentRow.Index,
                    'Entry': entry_price,
                    'Exit': exit_price,
                    'Net_PnL': net_pnl,
                    'Reason': reason,
                    'Fees': total_fees
                })
                position = None
                
        elif position == 'Short':
            exit_price = None
            reason = None
            
            if currentRow.High >= sl_price:
                exit_price = sl_price
                reason = 'SL'
            elif currentRow.Low <= tp_price:
                exit_price = tp_price
                reason = 'TP'
                
            if exit_price:
                gross_pnl_pct = (entry_price - exit_price) / entry_price
                gross_amt = entry_capital * gross_pnl_pct
                
                # Fees
                entry_fee = entry_capital * fees_pct
                # Approx exit fee on notionnel
                exit_val_notional = entry_capital * (exit_price/entry_price)
                exit_fee = exit_val_notional * fees_pct
                total_fees = entry_fee + exit_fee
                
                net_pnl = gross_amt - total_fees
                capital += net_pnl
                
                trades.append({
                    'Type': 'Short',
                    'Time': currentRow.Index,
                    'Entry': entry_price,
                    'Exit': exit_price,
                    'Net_PnL': net_pnl,
                    'Reason': reason,
                    'Fees': total_fees
                })
                position = None

        # --- Gestion Entrées ---
        if position is None:
            # Condition Long: 3LS Bull + Vol + Trend (Fast > Slow)
            if currentRow.Bullish_3LS and currentRow.Vol_Condition and (currentRow.SMA_Fast > currentRow.SMA_Slow):
                position = 'Long'
                entry_price = currentRow.Close
                entry_index = currentRow.Index
                entry_capital = capital
                
                # SL au Low de la bougie
                # Ajout d'un petit buffer ? Le script dit "stopTickSize".
                # Disons 0.2% de buffer pour éviter le bruit immédiat
                buffer = entry_price * 0.002 
                sl_price = currentRow.Low - buffer
                
                risk = entry_price - sl_price
                tp_price = entry_price + (risk * RISK_REWARD)
            
            # Condition Short: 3LS Bear + Vol + Trend (Fast < Slow)
            elif currentRow.Bearish_3LS and currentRow.Vol_Condition and (currentRow.SMA_Fast < currentRow.SMA_Slow):
                position = 'Short'
                entry_price = currentRow.Close
                entry_index = currentRow.Index
                entry_capital = capital
                
                buffer = entry_price * 0.002
                sl_price = currentRow.High + buffer
                
                risk = sl_price - entry_price
                tp_price = entry_price - (risk * RISK_REWARD)
        
        equity.append(capital)

    # 5. Rapport
    df_trades = pd.DataFrame(trades)
    
    if df_trades.empty:
        print("Aucun trade.")
    else:
        total = len(df_trades)
        wins = len(df_trades[df_trades['Net_PnL'] > 0])
        wr = (wins/total)*100
        ret = ((capital - 10000)/10000)*100
        
        print("\n=== RAPPORT 3LS ===")
        print(f"Final: {capital:.2f} $")
        print(f"Return: {ret:.2f}%")
        print(f"Trades: {total}")
        print(f"Win Rate: {wr:.2f}%")
        print(f"Fees Paid: {df_trades['Fees'].sum():.2f} $")
        
        print(df_trades.tail().to_string())

    # 6. Plot Simple
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12,8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    
    ax1.plot(df.index, df['Close'], color='white', alpha=0.5, label='Price')
    ax1.plot(df.index, df['SMA_Fast'], color='green', alpha=0.5, label='Fast MA')
    ax1.plot(df.index, df['SMA_Slow'], color='red', alpha=0.5, label='Slow MA')
    
    if not df_trades.empty:
        longs = df_trades[df_trades['Type']=='Long']
        shorts = df_trades[df_trades['Type']=='Short']
        
        ax1.scatter(longs['Time'], longs['Entry'], marker='^', color='lime', s=80, zorder=5)
        ax1.scatter(shorts['Time'], shorts['Entry'], marker='v', color='red', s=80, zorder=5)
    
    ax1.set_title(f'Stratégie 3 Line Strike (3LS) - R:R {RISK_REWARD}')
    ax1.legend()
    
    ax2.plot(df.index, equity[1:], color='gold', label='Equity')
    ax2.legend()
    
    plt.savefig('backtest_3ls.png')
    print("Graphique: backtest_3ls.png")

if __name__ == "__main__":
    run_backtest()
