"""
FINAL OPTIMIZED STRATEGY - RANK 8 v2 + Trailing SL - CORRECTED VERSION
Version avec correction du signal exit (prev_candle + exit au open)

Changements par rapport à la version originale:
- Signal exit utilise prev_candle (bougie fermée précédente) au lieu de current
- Sortie au current['open'] au lieu de current['close']
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime
from core.data_sources.market_data import get_ohlcv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Strategy Parameters - RANK 8 v2
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

# Trailing SL Steps: (gain_threshold_pct, new_sl_pct)
TRAILING_SL_STEPS = [
    (0.5, 0),    # At 0.5% gain -> SL to break even (0%)
    (1.0, 0.5),  # At 1% gain -> SL to 0.5%
    (1.5, 1.0),  # At 1.5% gain -> SL to 1%
    (2.0, 1.5),  # At 2% gain -> SL to 1.5%
]

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

def backtest(df, initial_capital=INITIAL_CAPITAL):
    """Run backtest with RANK 8 parameters - CORRECTED VERSION"""

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
    equity_curve = []

    for i in range(55, len(df) - 1):
        current = df.iloc[i]

        # Track equity curve
        equity_curve.append({
            'timestamp': pd.Timestamp(current['timestamp'], unit='ms'),
            'capital': capital,
            'drawdown': ((peak_capital - capital) / peak_capital) * 100 if peak_capital > 0 else 0
        })

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
                entry_fee = entry_price * quantity * BINANCE_FEE
                capital -= entry_fee

                if direction == 'long':
                    tp_price = entry_price * (1 + TP_PCT / 100)
                    sl_price = entry_price * (1 - SL_PCT / 100)
                else:
                    tp_price = entry_price * (1 - TP_PCT / 100)
                    sl_price = entry_price * (1 + SL_PCT / 100)

                # Initialize trailing SL tracking
                best_price = entry_price

        else:
            # CORRECTION: Utiliser prev_candle pour signal exit
            prev_candle = df.iloc[i - 1]
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

            # Check exit conditions
            initial_sl = entry_price * (1 - SL_PCT / 100) if direction == 'long' else entry_price * (1 + SL_PCT / 100)

            if direction == 'long':
                if current['high'] >= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['low'] <= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price > initial_sl else 'SL'
                # CORRECTION: Utiliser prev_candle et sortir au current['open']
                elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] < prev_candle['ema_20']:
                    exit_price = current['open']
                    exit_reason = 'Signal Exit'
            else:
                if current['low'] <= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['high'] >= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price < initial_sl else 'SL'
                # CORRECTION: Utiliser prev_candle et sortir au current['open']
                elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] > prev_candle['ema_20']:
                    exit_price = current['open']
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
                }
                trades.append(trade_record)

                in_trade = False

    return trades, capital, max_drawdown, pd.DataFrame(equity_curve)

def generate_html_report(df, trades, capital, max_dd, equity_df):
    """Generate comprehensive HTML report"""

    # Calculate statistics
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]

    total_pnl = sum(t['pnl'] for t in trades)
    total_return = ((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    years_span = (pd.to_datetime(df['timestamp'], unit='ms').max() -
                 pd.to_datetime(df['timestamp'], unit='ms').min()).days / 365.25
    annual_return = (((capital / INITIAL_CAPITAL) ** (1 / years_span)) - 1) * 100

    winrate = len(wins) / len(trades) * 100 if trades else 0
    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0

    # Create subplots
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=('Equity Curve', 'Drawdown', 'Price with Trades', 'Trade Distribution'),
        vertical_spacing=0.08,
        row_heights=[0.3, 0.2, 0.3, 0.2]
    )

    # 1. Equity Curve
    fig.add_trace(
        go.Scatter(x=equity_df['timestamp'], y=equity_df['capital'],
                  name='Capital', line=dict(color='blue', width=2)),
        row=1, col=1
    )

    # 2. Drawdown
    fig.add_trace(
        go.Scatter(x=equity_df['timestamp'], y=-equity_df['drawdown'],
                  name='Drawdown', fill='tozeroy',
                  line=dict(color='red', width=1)),
        row=2, col=1
    )

    # 3. Price with trades
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    fig.add_trace(
        go.Candlestick(x=df['date'], open=df['open'], high=df['high'],
                      low=df['low'], close=df['close'], name='Price'),
        row=3, col=1
    )

    # Add trade markers
    for trade in trades:
        color = 'green' if trade['pnl'] > 0 else 'red'
        fig.add_trace(
            go.Scatter(x=[trade['entry_time']], y=[trade['entry_price']],
                      mode='markers', marker=dict(color=color, size=8, symbol='triangle-up'),
                      showlegend=False),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(x=[trade['exit_time']], y=[trade['exit_price']],
                      mode='markers', marker=dict(color=color, size=8, symbol='triangle-down'),
                      showlegend=False),
            row=3, col=1
        )

    # 4. Trade distribution
    pnl_values = [t['pnl'] for t in trades]
    fig.add_trace(
        go.Histogram(x=pnl_values, name='Trade PnL',
                    marker=dict(color='blue'), nbinsx=30),
        row=4, col=1
    )

    fig.update_layout(height=1400, showlegend=True, title_text="RANK 8 v2 + Trailing SL - CORRECTED VERSION - Backtest Report")
    fig.update_xaxes(title_text="Date", row=4, col=1)
    fig.update_yaxes(title_text="Capital ($)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    fig.update_yaxes(title_text="Price ($)", row=3, col=1)
    fig.update_yaxes(title_text="Frequency", row=4, col=1)

    # Generate HTML
    html_content = f"""
    <html>
    <head>
        <title>Strategy RANK 8 - CORRECTED - Backtest Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #2c3e50; text-align: center; }}
            .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0; }}
            .stat-box {{ background: #ecf0f1; padding: 20px; border-radius: 8px; text-align: center; }}
            .stat-box h3 {{ margin: 0 0 10px 0; color: #34495e; font-size: 14px; }}
            .stat-box .value {{ font-size: 28px; font-weight: bold; color: #2c3e50; }}
            .positive {{ color: #27ae60; }}
            .negative {{ color: #e74c3c; }}
            .parameters {{ background: #e67e22; color: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .parameters h2 {{ margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #34495e; color: white; }}
            tr:hover {{ background: #f5f5f5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏆 RANK 8 - CORRECTED VERSION - Backtest Results</h1>

            <div class="parameters">
                <h2>Strategy Parameters (CORRECTED VERSION)</h2>
                <p><strong>Pair:</strong> {PAIR} | <strong>Timeframe:</strong> {INTERVAL}</p>
                <p><strong>ADX Threshold:</strong> {ADX_THRESHOLD} | <strong>TP:</strong> {TP_PCT}% | <strong>Initial SL:</strong> {SL_PCT}%</p>
                <p><strong>Trailing SL:</strong> +0.5%→BE, +1%→+0.5%, +1.5%→+1%, +2%→+1.5%</p>
                <p><strong>Max Hold:</strong> {MAX_HOLD} candles | <strong>Volume:</strong> {VOLUME_THRESHOLD}x</p>
                <p><strong>Period:</strong> {pd.to_datetime(df['timestamp'].min(), unit='ms').strftime('%Y-%m-%d')} to {pd.to_datetime(df['timestamp'].max(), unit='ms').strftime('%Y-%m-%d')}</p>
                <p style="margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 15px;">
                    <strong>⚠️ CORRECTIONS APPLIQUÉES:</strong><br>
                    • Signal exit utilise prev_candle (bougie précédente) au lieu de current<br>
                    • Sortie au current['open'] au lieu de current['close']
                </p>
            </div>

            <div class="stats">
                <div class="stat-box">
                    <h3>Initial Capital</h3>
                    <div class="value">${INITIAL_CAPITAL:,.0f}</div>
                </div>
                <div class="stat-box">
                    <h3>Final Capital</h3>
                    <div class="value positive">${capital:,.2f}</div>
                </div>
                <div class="stat-box">
                    <h3>Total Return</h3>
                    <div class="value positive">{total_return:.2f}%</div>
                </div>
                <div class="stat-box">
                    <h3>Annual Return</h3>
                    <div class="value positive">{annual_return:.2f}%</div>
                </div>
                <div class="stat-box">
                    <h3>Max Drawdown</h3>
                    <div class="value negative">{max_dd:.2f}%</div>
                </div>
                <div class="stat-box">
                    <h3>Total Trades</h3>
                    <div class="value">{len(trades)}</div>
                </div>
                <div class="stat-box">
                    <h3>Win Rate</h3>
                    <div class="value {'positive' if winrate > 50 else 'negative'}">{winrate:.1f}%</div>
                </div>
                <div class="stat-box">
                    <h3>Winning Trades</h3>
                    <div class="value positive">{len(wins)}</div>
                </div>
                <div class="stat-box">
                    <h3>Losing Trades</h3>
                    <div class="value negative">{len(losses)}</div>
                </div>
                <div class="stat-box">
                    <h3>Avg Win</h3>
                    <div class="value positive">${avg_win:.2f}</div>
                </div>
                <div class="stat-box">
                    <h3>Avg Loss</h3>
                    <div class="value negative">${avg_loss:.2f}</div>
                </div>
                <div class="stat-box">
                    <h3>Profit Factor</h3>
                    <div class="value">{abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0:.2f}</div>
                </div>
            </div>

            {fig.to_html(full_html=False, include_plotlyjs='cdn')}

            <h2>Last 20 Trades</h2>
            <table>
                <tr>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                    <th>Direction</th>
                    <th>Entry Price</th>
                    <th>Exit Price</th>
                    <th>PnL</th>
                    <th>PnL %</th>
                    <th>Exit Reason</th>
                </tr>
    """

    for trade in trades[-20:]:
        pnl_class = 'positive' if trade['pnl'] > 0 else 'negative'
        html_content += f"""
                <tr>
                    <td>{trade['entry_time'].strftime('%Y-%m-%d %H:%M')}</td>
                    <td>{trade['exit_time'].strftime('%Y-%m-%d %H:%M')}</td>
                    <td>{trade['direction'].upper()}</td>
                    <td>${trade['entry_price']:,.2f}</td>
                    <td>${trade['exit_price']:,.2f}</td>
                    <td class="{pnl_class}">${trade['pnl']:,.2f}</td>
                    <td class="{pnl_class}">{trade['pnl_pct']:.2f}%</td>
                    <td>{trade['exit_reason']}</td>
                </tr>
        """

    html_content += """
            </table>
        </div>
    </body>
    </html>
    """

    return html_content

def main():
    print("\n" + "="*100)
    print("RANK 8 v2 + TRAILING SL - CORRECTED VERSION - BACKTEST")
    print("="*100)
    print(f"\nParameters: ADX {ADX_THRESHOLD}, TP {TP_PCT}%, Initial SL {SL_PCT}%, Volume {VOLUME_THRESHOLD}x")
    print("Trailing SL: +0.5%->BE, +1%->+0.5%, +1.5%->+1%, +2%->+1.5%")
    print("\n[!] CORRECTIONS APPLIQUEES:")
    print("  - Signal exit utilise prev_candle au lieu de current")
    print("  - Sortie au current['open'] au lieu de current['close']")
    print("\nFetching data...")

    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")
    print("Running backtest...")

    trades, capital, max_dd, equity_df = backtest(df)

    print("\n" + "="*100)
    print("RESULTS - CORRECTED VERSION")
    print("="*100)
    print(f"Initial Capital:  ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Capital:    ${capital:,.2f}")
    print(f"Total Return:     {((capital - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100:.2f}%")
    print(f"Max Drawdown:     {max_dd:.2f}%")
    print(f"Total Trades:     {len(trades)}")
    print(f"Win Rate:         {len([t for t in trades if t['pnl'] > 0]) / len(trades) * 100:.1f}%")

    print("\nGenerating HTML report...")
    html_content = generate_html_report(df, trades, capital, max_dd, equity_df)

    output_file = "final_strategy_rank8_corrected_backtest.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Report saved to: {output_file}")
    print("="*100 + "\n")

if __name__ == "__main__":
    main()
