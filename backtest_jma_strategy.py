import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def jurik_moving_average(series, length, phase):
    """
    Calcule la Jurik Moving Average (JMA) selon la logique Pine Script fournie.
    
    Logique Pine Script:
    beta = 0.45 * (length - 1) / (0.45 * (length - 1) + 2)
    alpha = math.pow(beta, phase)
    jma = (1 - alpha) * src + alpha * nz(jma[1])
    """
    # Conversion en numpy array pour performance
    src = series.values
    n = len(src)
    jma = np.zeros(n)
    
    # Calcul des coefficients constantes
    beta = 0.45 * (length - 1) / (0.45 * (length - 1) + 2)
    alpha = np.power(beta, phase)
    
    # Initialisation
    # On commence au premier index
    jma[0] = src[0]
    
    # Boucle de calcul
    # jma[i] = (1 - alpha) * src[i] + alpha * jma[i-1]
    one_minus_alpha = 1 - alpha
    
    for i in range(1, n):
        # Gestion des NaN dans la source (si le prix est NaN, on garde la valeur précédente ou NaN)
        if np.isnan(src[i]):
             jma[i] = jma[i-1]
        else:
             # Si jma[i-1] était NaN (début de série avec des NaNs), on initialise avec le prix actuel
             if np.isnan(jma[i-1]):
                 jma[i] = src[i]
             else:
                 jma[i] = one_minus_alpha * src[i] + alpha * jma[i-1]
                 
    return pd.Series(jma, index=series.index)

def run_backtest():
    print("--- Démarrage du Backtest JMA Strategy (Mode Simulation de Trades) ---")
    
    # 1. Téléchargement des données
    symbol = "BTC-USD"
    interval = "1h"
    download_period = "2y" # On télécharge 2 ans pour avoir de la marge (SMA warmup)
    backtest_days = 365
    
    print(f"Téléchargement des données pour {symbol} ({interval}, {download_period})...")
    df = yf.download(symbol, period=download_period, interval=interval, progress=False)
    
    if df.empty:
        print("Erreur: Aucune donnée téléchargée.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.dropna()
    print(f"Données brutes récupérées: {len(df)} bougies.")

    # 2. Calcul des indicateurs (sur l'ensemble des données pour avoir l'historique)
    jma_len = 9
    jma_phase = 0.15
    sma_period = 200

    print("Calcul des indicateurs...")
    df['SMA'] = df['Close'].rolling(window=sma_period).mean()
    df['JMA'] = jurik_moving_average(df['Close'], length=jma_len, phase=jma_phase)
    
    # Signaux bruts
    df['Long_Signal'] = (df['Close'] > df['JMA']) & (df['JMA'] > df['SMA'])
    df['Short_Signal'] = (df['Close'] < df['JMA']) & (df['JMA'] < df['SMA'])

    # TRONCATURE : On ne garde que les X derniers jours demandés pour le backtest
    # 1h = 24 bougies/jour
    cutoff_index = len(df) - (backtest_days * 24)
    if cutoff_index < 0:
        cutoff_index = 0
        
    df_backtest = df.iloc[cutoff_index:].copy()
    print(f"Période de Backtest : {len(df_backtest)} bougies ({df_backtest.index[0]} à {df_backtest.index[-1]})")
    
    # On travaille sur df_backtest désormais
    df = df_backtest # Remplacement pour la suite du script

    # 3. Boucle de Backtest (Event-Driven)
    print("Simulation des trades...")
    
    # Paramètres de gestion de position
    STOP_LOSS_PCT = 0.02  # 2%
    TAKE_PROFIT_PCT = 0.04 # 4%
    TRAILING_STOP_PCT = 0.015 # 1.5% Trailing SL
    FEES_PCT = 0.001 # 0.1% frais par ordre
    
    position = None # None, 'Long', 'Short'
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    entry_index = None
    entry_capital = 0.0 # capital bloqué dans le trade
    
    trades = []
    equity = [10000] # Capital initial fictif
    capital = 10000
    
    # On itère sur le DataFrame
    for currentRow in df.itertuples():
        
        # 1. Gestion des sorties (Si on est en position)
        if position == 'Long':
            exit_price = None
            reason = None
            
            # Vérifier SL
            if currentRow.Low <= sl_price:
                exit_price = sl_price
                reason = 'SL'
            # Vérifier TP
            elif currentRow.High >= tp_price:
                exit_price = tp_price
                reason = 'TP'
                
            if exit_price:
                gross_pnl_pct = (exit_price - entry_price) / entry_price
                gross_pnl_amount = entry_capital * gross_pnl_pct
                
                # Frais
                entry_fee = entry_capital * FEES_PCT
                exit_total_val = entry_capital + gross_pnl_amount
                exit_fee = exit_total_val * FEES_PCT
                total_fees = entry_fee + exit_fee
                
                net_pnl_amount = gross_pnl_amount - total_fees
                capital += net_pnl_amount
                
                trades.append({
                    'Type': 'Long',
                    'Entry_Time': entry_index,
                    'Entry_Price': entry_price,
                    'Exit_Time': currentRow.Index,
                    'Exit_Price': exit_price,
                    'Gross_PnL': gross_pnl_pct,
                    'Fees': total_fees,
                    'Net_PnL': net_pnl_amount,
                    'Capital_After': capital,
                    'Reason': reason
                })
                position = None
            
            # Trailing SL Update
            elif position == 'Long':
                new_sl = currentRow.High * (1 - TRAILING_STOP_PCT)
                if new_sl > sl_price:
                    sl_price = new_sl
                
        elif position == 'Short':
            exit_price = None
            reason = None
            
            # Vérifier SL
            if currentRow.High >= sl_price:
                exit_price = sl_price
                reason = 'SL'
            # Vérifier TP
            elif currentRow.Low <= tp_price:
                exit_price = tp_price
                reason = 'TP'
                
            if exit_price:
                # Short PnL: (Entry - Exit) / Entry
                gross_pnl_pct = (entry_price - exit_price) / entry_price
                gross_pnl_amount = entry_capital * gross_pnl_pct
                
                # Frais
                entry_fee = entry_capital * FEES_PCT
                # Pour le short, le montant "récupéré" est théorique (marge), mais les fees s'appliquent sur le volume notionnel
                # Notionnel Entrée = entry_capital
                # Notionnel Sortie = entry_capital * (entry_price / exit_price) ? 
                # Simplifions: Frais sur volume = Exit Value.
                # Exit Value (Notional) = entry_capital * (1 + gross_pnl_pct) ?? Non
                # Short: On vend 1 BTC à 10000. On rachete à 9000.
                # Fee entrée: 0.1% de 10000. Fee sortie: 0.1% de 9000.
                
                # Calculons le volume de sortie basé sur la variation de prix
                exit_notional = entry_capital * (exit_price / entry_price) # Ce qu'on débourse pour racheter
                # Mais le profit c'est Entry - Exit.
                # Fees Short exacts:
                # Fee 1 = Capital * FeePct
                # Fee 2 = (Capital / Entry * Exit) * FeePct (car on rachete la même quantité)
                
                entry_fee = entry_capital * FEES_PCT
                exit_fee = (entry_capital * (exit_price / entry_price)) * FEES_PCT
                total_fees = entry_fee + exit_fee
                
                net_pnl_amount = gross_pnl_amount - total_fees
                capital += net_pnl_amount
                
                trades.append({
                    'Type': 'Short',
                    'Entry_Time': entry_index,
                    'Entry_Price': entry_price,
                    'Exit_Time': currentRow.Index,
                    'Exit_Price': exit_price,
                    'Gross_PnL': gross_pnl_pct,
                    'Fees': total_fees,
                    'Net_PnL': net_pnl_amount,
                    'Capital_After': capital,
                    'Reason': reason
                })
                position = None
            
            # Trailing SL Update
            elif position == 'Short':
                new_sl = currentRow.Low * (1 + TRAILING_STOP_PCT)
                if new_sl < sl_price:
                    sl_price = new_sl

        # 2. Gestion des entrées (Si on n'est PAS en position)
        if position is None:
            if currentRow.Long_Signal:
                position = 'Long'
                entry_price = currentRow.Close
                entry_index = currentRow.Index
                entry_capital = capital # On réinvestit tout
                # Définition SL/TP
                sl_price = entry_price * (1 - STOP_LOSS_PCT)
                tp_price = entry_price * (1 + TAKE_PROFIT_PCT)
                
            elif currentRow.Short_Signal:
                position = 'Short'
                entry_price = currentRow.Close
                entry_index = currentRow.Index
                entry_capital = capital # On réinvestit tout
                # Définition SL/TP
                sl_price = entry_price * (1 + STOP_LOSS_PCT)
                tp_price = entry_price * (1 - TAKE_PROFIT_PCT)
        
        # Enregistrement Equity
        equity.append(capital)

    # Conversion des résultats en DataFrame
    df_trades = pd.DataFrame(trades)
    
    # 4. Rapport de Performance
    if df_trades.empty:
        print("Aucun trade effectué.")
    else:
        total_trades = len(df_trades)
        
        # Win Rate Technique (Avant Frais)
        win_trades_gross = len(df_trades[df_trades['Gross_PnL'] > 0])
        win_rate_gross = (win_trades_gross / total_trades) * 100
        
        # Win Rate Réel (Après Frais)
        win_trades_net = len(df_trades[df_trades['Net_PnL'] > 0])
        win_rate_net = (win_trades_net / total_trades) * 100
        
        total_return_pct = ((capital - 10000) / 10000) * 100
        total_fees = df_trades['Fees'].sum()
        
        print("\n=== RAPPORT DE PERFORMANCE ===")
        print(f"Capital Initial : 10,000 $")
        print(f"Capital Final   : {capital:.2f} $")
        print(f"Retour Total    : {total_return_pct:.2f}%")
        print(f"Total Frais     : {total_fees:.2f} $")
        print(f"Nombre de Trades: {total_trades}")
        print(f"Win Rate (Brut) : {win_rate_gross:.2f}%  (Victoires techniques hors frais)")
        print(f"Win Rate (Net)  : {win_rate_net:.2f}%  (Trades réellement rentables)")
        print(f"Meilleur PnL    : {df_trades['Net_PnL'].max():.2f} $")
        print(f"Pire PnL        : {df_trades['Net_PnL'].min():.2f} $")
        print("==============================\n")
        print(df_trades[['Type', 'Entry_Time', 'Gross_PnL', 'Fees', 'Net_PnL', 'Capital_After', 'Reason']].to_string())

    # 5. Visualisation
    print("Génération du graphique...")
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    
    # Plot Principal (Prix + Indicateurs)
    ax1.plot(df.index, df['Close'], label='Prix', color='white', alpha=0.3)
    ax1.plot(df.index, df['JMA'], label='JMA', color='#33ff57', linewidth=1.5)
    ax1.plot(df.index, df['SMA'], label='SMA 200', color='#3388ff', linewidth=1.5)
    
    # Plot des Trades
    if not df_trades.empty:
        # Entrées Longues
        longs = df_trades[df_trades['Type'] == 'Long']
        ax1.scatter(longs['Entry_Time'], longs['Entry_Price'], color='#00ff00', marker='^', s=100, label='Entrée Long', zorder=5)
        # Sorties Longues
        ax1.scatter(longs['Exit_Time'], longs['Exit_Price'], color='#ccffcc', marker='x', s=50, zorder=5)
        
        # Entrées Courtes
        shorts = df_trades[df_trades['Type'] == 'Short']
        ax1.scatter(shorts['Entry_Time'], shorts['Entry_Price'], color='#ff3333', marker='v', s=100, label='Entrée Short', zorder=5)
        # Sorties Courtes
        ax1.scatter(shorts['Exit_Time'], shorts['Exit_Price'], color='#ffcccc', marker='x', s=50, zorder=5)

    ax1.set_title(f'Stratégie JMA + SMA (Trades Simulation) - SL {STOP_LOSS_PCT*100}% / TP {TAKE_PROFIT_PCT*100}% / Trailing SL {TRAILING_STOP_PCT*100}%')
    ax1.set_ylabel('Prix (USD)')
    ax1.legend()
    ax1.grid(True, alpha=0.1)
    
    # Plot Equity Curve
    # Alignement de l'equity avec l'index du dataframe
    # equity est une liste de longueur len(df) + 1 ou len(df). On a append à chaque step.
    # On va prendre les N derniers points correspondant au DF
    equity_series = pd.Series(equity[1:], index=df.index) # equity[0] est l'initial
    
    ax2.plot(equity_series.index, equity_series, color='gold', linewidth=2, label='Capital (Equity)')
    ax2.set_ylabel('Capital ($)')
    ax2.set_xlabel('Date')
    ax2.legend()
    ax2.grid(True, alpha=0.1)
    
    plt.tight_layout()
    output_file = "jma_strategy_backtest_trades.png"
    plt.savefig(output_file, dpi=150)
    print(f"Graphique sauvegardé sous : {output_file}")
    
    # Export CSV des trades
    df_trades.to_csv("jma_trades_list.csv")
    print("Liste des trades sauvegardée sous : jma_trades_list.csv")

if __name__ == "__main__":
    try:
        run_backtest()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
