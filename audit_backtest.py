"""
Script d'audit complet pour vérifier la crédibilité du backtest
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
LIMIT = 20000
BINANCE_FEE = 0.001
INITIAL_CAPITAL = 10000

ADX_THRESHOLD = 30
TP_PCT = 4.0
SL_PCT = 0.7
MAX_HOLD = 20
VOLUME_THRESHOLD = 1.8

TRAILING_SL_STEPS = [
    (0.5, 0),
    (1.0, 0.5),
    (1.5, 1.0),
    (2.0, 1.5),
]

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
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

def backtest_with_audit(df, initial_capital=INITIAL_CAPITAL):
    """Run backtest with detailed audit"""

    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']

    trades = []
    capital = initial_capital
    in_trade = False
    peak_capital = initial_capital
    max_drawdown = 0

    # Audit variables
    tp_sl_both_touched = 0  # Compteur pour bug critique
    lookahead_bias_detected = 0  # Compteur pour lookahead bias
    position_sizes = []  # Track position sizes

    for i in range(55, len(df) - 1):
        current = df.iloc[i]

        if capital > peak_capital:
            peak_capital = capital
        current_dd = ((peak_capital - capital) / peak_capital) * 100
        if current_dd > max_drawdown:
            max_drawdown = current_dd

        if not in_trade:
            prev = df.iloc[i - 1]

            bullish_trend = (prev.get('adx', 0) > ADX_THRESHOLD and
                           prev.get('plus_di', 0) > prev.get('minus_di', 0) and
                           prev['close'] > prev['ema_20'] and
                           prev['ema_20'] > prev['ema_50'] and
                           prev.get('volume_ratio', 1) > VOLUME_THRESHOLD)

            bearish_trend = (prev.get('adx', 0) > ADX_THRESHOLD and
                           prev.get('minus_di', 0) > prev.get('plus_di', 0) and
                           prev['close'] < prev['ema_20'] and
                           prev['ema_20'] < prev['ema_50'] and
                           prev.get('volume_ratio', 1) > VOLUME_THRESHOLD)

            if bullish_trend or bearish_trend:
                in_trade = True
                entry_price = prev['close']
                entry_i = i
                entry_time = pd.Timestamp(df.iloc[i - 1]['timestamp'], unit='ms')
                direction = 'long' if bullish_trend else 'short'

                quantity = (capital * 0.98) / entry_price
                position_value = entry_price * quantity
                position_size_pct = (position_value / capital) * 100
                position_sizes.append(position_size_pct)

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

            # Update best price for trailing SL
            if direction == 'long':
                if current['high'] > best_price:
                    best_price = current['high']
                current_gain_pct = ((best_price - entry_price) / entry_price) * 100
            else:
                if current['low'] < best_price:
                    best_price = current['low']
                current_gain_pct = ((entry_price - best_price) / entry_price) * 100

            # Apply trailing SL logic
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

            # AUDIT: Vérifier si TP ET SL sont touchés dans la même bougie
            if direction == 'long':
                tp_touched = current['high'] >= tp_price
                sl_touched = current['low'] <= sl_price

                if tp_touched and sl_touched:
                    tp_sl_both_touched += 1

                if current['high'] >= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['low'] <= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price > initial_sl else 'SL'
                elif current.get('adx', 0) < 20 or current['close'] < current['ema_20']:
                    # AUDIT: Lookahead bias detected!
                    lookahead_bias_detected += 1
                    exit_price = current['close']
                    exit_reason = 'Signal Exit'
            else:
                tp_touched = current['low'] <= tp_price
                sl_touched = current['high'] >= sl_price

                if tp_touched and sl_touched:
                    tp_sl_both_touched += 1

                if current['low'] <= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['high'] >= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price < initial_sl else 'SL'
                elif current.get('adx', 0) < 20 or current['close'] > current['ema_20']:
                    # AUDIT: Lookahead bias detected!
                    lookahead_bias_detected += 1
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

                trade_record = {
                    'entry_time': entry_time,
                    'exit_time': pd.Timestamp(df.iloc[i]['timestamp'], unit='ms'),
                    'direction': direction,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl_net,
                    'pnl_pct': (pnl_net / (entry_price * quantity)) * 100,
                    'exit_reason': exit_reason,
                    'capital_after': capital,
                    'hold_time': i - entry_i,
                }
                trades.append(trade_record)

                in_trade = False

    return trades, capital, max_drawdown, tp_sl_both_touched, lookahead_bias_detected, position_sizes

def main():
    print("\n" + "="*100)
    print("AUDIT COMPLET DU BACKTEST - VERIFICATION DE CREDIBILITE")
    print("="*100)

    print("\nFetching data...")
    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")

    years_span = (pd.to_datetime(df['timestamp'], unit='ms').max() -
                 pd.to_datetime(df['timestamp'], unit='ms').min()).days / 365.25
    print(f"Period: {years_span:.2f} years")
    print("\nRunning backtest with audit...")

    trades, capital, max_dd, tp_sl_both, lookahead_bias_count, position_sizes = backtest_with_audit(df)

    # Analyse
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]

    print("\n" + "="*100)
    print("1. RESULTATS GLOBAUX")
    print("="*100)
    print(f"Initial Capital:   ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital:     ${capital:,.2f}")
    print(f"Total Return:      {((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100:.2f}%")
    annual_return = (((capital / INITIAL_CAPITAL) ** (1 / years_span)) - 1) * 100
    print(f"Annual Return:     {annual_return:.2f}%")
    print(f"Max Drawdown:      {max_dd:.2f}%")
    print(f"Total Trades:      {len(trades)}")
    print(f"Win Rate:          {len(wins) / len(trades) * 100:.1f}%")

    # Calculate Sharpe Ratio
    returns = []
    for i in range(1, len(trades)):
        prev_capital = trades[i-1]['capital_after']
        curr_capital = trades[i]['capital_after']
        ret = (curr_capital - prev_capital) / prev_capital
        returns.append(ret)

    if len(returns) > 0:
        sharpe = (np.mean(returns) * np.sqrt(252)) / (np.std(returns) if np.std(returns) > 0 else 1)
        print(f"Sharpe Ratio:      {sharpe:.2f}")

    print("\n" + "="*100)
    print("2. DISTRIBUTION DES EXIT REASONS")
    print("="*100)

    exit_reasons = {}
    for t in trades:
        reason = t['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = 0
        exit_reasons[reason] += 1

    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(trades) * 100
        print(f"{reason:15s}: {count:4d} trades ({pct:5.1f}%)")

    print("\n" + "="*100)
    print("3. BUG CRITIQUE: TP ET SL TOUCHES DANS LA MEME BOUGIE")
    print("="*100)
    print(f"Nombre de fois: {tp_sl_both} sur {len(trades)} trades ({tp_sl_both/len(trades)*100:.2f}%)")
    if tp_sl_both > 0:
        print("[!] ATTENTION: Le backtest assume toujours que le TP est touche en premier.")
        print("   En realite, ca pourrait etre le SL selon l'ordre des mouvements.")
        print(f"   Impact potentiel: {tp_sl_both} trades pourraient etre des pertes au lieu de gains.")
    else:
        print("[OK] TP et SL ne sont jamais touches dans la meme bougie.")

    print("\n" + "="*100)
    print("4. LOOKAHEAD BIAS - UTILISATION DE DONNEES FUTURES")
    print("="*100)
    print(f"Nombre de Signal Exits: {lookahead_bias_count} sur {len(trades)} trades ({lookahead_bias_count/len(trades)*100:.2f}%)")
    if lookahead_bias_count > 0:
        print("[!] CRITIQUE: Le backtest utilise les donnees de la bougie actuelle (ADX, EMA, close)")
        print("   pour prendre des decisions de sortie. Ces donnees ne sont disponibles")
        print("   qu'a la cloture de la bougie!")
        print(f"   Impact: {lookahead_bias_count} trades ont ete sortis avec des informations du futur.")
        print("   SOLUTION: Utiliser prev_candle au lieu de current pour les signal exits.")
    else:
        print("[OK] Aucun lookahead bias detecte dans les signal exits.")

    print("\n" + "="*100)
    print("5. POSITION SIZE - MONEY MANAGEMENT")
    print("="*100)
    if len(position_sizes) > 0:
        avg_position_size = np.mean(position_sizes)
        max_position_size = np.max(position_sizes)
        min_position_size = np.min(position_sizes)
        print(f"Position Size moyenne:  {avg_position_size:.2f}% du capital")
        print(f"Position Size max:      {max_position_size:.2f}% du capital")
        print(f"Position Size min:      {min_position_size:.2f}% du capital")

        if avg_position_size > 20:
            print(f"[!] CRITIQUE: Position size moyenne de {avg_position_size:.2f}% est EXCESSIVE!")
            print("   Freqtrade avec max_open_trades=10 utilise ~10% par trade.")
            print("   Position size actuelle cree un effet de compounding irrealiste.")
            print(f"   Impact: Gains multiplies par ~{avg_position_size/10:.1f}x artificiellement.")
            print("   SOLUTION: Utiliser POSITION_SIZE_PCT = 0.10 (10% du capital).")
        elif avg_position_size > 10:
            print(f"[!] Position size moyenne de {avg_position_size:.2f}% est elevee mais acceptable.")
        else:
            print(f"[OK] Position size moyenne de {avg_position_size:.2f}% est realiste.")

    print("\n" + "="*100)
    print("6. PRIX D'ENTREE - REALISME")
    print("="*100)
    print("Prix d'entree actuel: Close de la bougie precedente (prev['close'])")
    print("[!] ATTENTION: C'est optimiste car:")
    print("   1. Pas de slippage simule")
    print("   2. En realite, l'ordre est execute a l'ouverture de la bougie suivante")
    print("   SOLUTION: Utiliser current['open'] avec slippage de 0.05-0.1%")

    print("\n" + "="*100)
    print("7. SEQUENCES DE GAINS/PERTES")
    print("="*100)

    max_win_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    current_loss_streak = 0

    for t in trades:
        if t['pnl'] > 0:
            current_win_streak += 1
            current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        else:
            current_loss_streak += 1
            current_win_streak = 0
            max_loss_streak = max(max_loss_streak, current_loss_streak)

    print(f"Max Win Streak:    {max_win_streak} trades consecutifs")
    print(f"Max Loss Streak:   {max_loss_streak} trades consecutifs")

    if max_win_streak > 15:
        print("[!] SUSPECT: Sequence de gains inhabituellement longue")
    if max_loss_streak > 15:
        print("[!] SUSPECT: Sequence de pertes inhabituellement longue")

    print("\n" + "="*100)
    print("8. STATISTIQUES DES TRADES")
    print("="*100)

    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
    biggest_win = max([t['pnl'] for t in trades])
    biggest_loss = min([t['pnl'] for t in trades])

    print(f"Avg Win:           ${avg_win:.2f}")
    print(f"Avg Loss:          ${avg_loss:.2f}")
    print(f"Biggest Win:       ${biggest_win:.2f}")
    print(f"Biggest Loss:      ${biggest_loss:.2f}")
    print(f"Profit Factor:     {abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0:.2f}")

    # Hold time
    avg_hold = np.mean([t['hold_time'] for t in trades])
    print(f"Avg Hold Time:     {avg_hold:.1f} candles ({avg_hold * 4:.1f} hours)")

    print("\n" + "="*100)
    print("9. CREDIBILITE - ANALYSE FINALE")
    print("="*100)

    issues = []
    critical_issues = []

    # Check 0: Lookahead bias (CRITIQUE)
    if lookahead_bias_count > 0:
        critical_issues.append(f"[!] LOOKAHEAD BIAS: {lookahead_bias_count} trades ({lookahead_bias_count/len(trades)*100:.1f}%) utilisent des donnees futures")

    # Check 0b: Position size excessive (CRITIQUE)
    if len(position_sizes) > 0:
        avg_pos_size = np.mean(position_sizes)
        if avg_pos_size > 20:
            critical_issues.append(f"[!] POSITION SIZE EXCESSIVE: {avg_pos_size:.1f}% du capital (devrait etre ~10%)")

    # Check 1: Drawdown trop faible
    if max_dd < 5 and ((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) > 5:
        issues.append("[!] Drawdown tres faible (" + f"{max_dd:.2f}%" + ") pour un gain de +" + f"{((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100:.0f}% (suspect)")

    # Check 2: Win rate trop elevé
    winrate = len(wins) / len(trades) * 100
    if winrate > 70:
        issues.append(f"[!] Win rate tres eleve ({winrate:.1f}%) - suspect pour du trading")

    # Check 3: Sharpe ratio trop élevé
    if len(returns) > 0 and sharpe > 4:
        issues.append(f"[!] Sharpe Ratio tres eleve ({sharpe:.2f}) - inhabituel")

    # Check 4: TP vs SL both touched
    if tp_sl_both > len(trades) * 0.05:
        issues.append(f"[!] TP et SL touches dans meme bougie trop souvent ({tp_sl_both/len(trades)*100:.1f}%)")

    # Check 5: Profit factor trop élevé
    pf = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0
    if pf > 3:
        issues.append(f"[!] Profit Factor tres eleve ({pf:.2f}) - inhabituel")

    if len(critical_issues) == 0 and len(issues) == 0:
        print("[OK] CREDIBLE: Aucun probleme majeur detecte")
        print("   Les resultats semblent realistes pour cette strategie.")
    else:
        if len(critical_issues) > 0:
            print("[!] PROBLEMES CRITIQUES (invalident les resultats):")
            for issue in critical_issues:
                print(f"   {issue}")
            print()

        if len(issues) > 0:
            print("[!] PROBLEMES SUSPECTS (a verifier):")
            for issue in issues:
                print(f"   {issue}")

    print("\n" + "="*100)
    print("10. PIRES TRADES (Top 10 pertes)")
    print("="*100)

    worst_trades = sorted(trades, key=lambda x: x['pnl'])[:10]
    for i, t in enumerate(worst_trades, 1):
        print(f"{i:2d}. {t['entry_time'].strftime('%Y-%m-%d %H:%M')} | {t['direction']:5s} | " +
              f"PnL: ${t['pnl']:>8,.2f} | Exit: {t['exit_reason']}")

    print("\n" + "="*100)
    print("11. MEILLEURS TRADES (Top 10 gains)")
    print("="*100)

    best_trades = sorted(trades, key=lambda x: x['pnl'], reverse=True)[:10]
    for i, t in enumerate(best_trades, 1):
        print(f"{i:2d}. {t['entry_time'].strftime('%Y-%m-%d %H:%M')} | {t['direction']:5s} | " +
              f"PnL: ${t['pnl']:>8,.2f} | Exit: {t['exit_reason']}")

    print("\n" + "="*100 + "\n")

if __name__ == "__main__":
    main()
