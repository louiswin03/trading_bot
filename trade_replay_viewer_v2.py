"""
TRADE REPLAY VIEWER V2
Interface interactive avec TOUS les indicateurs et signaux potentiels
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
import json

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

def detect_all_potential_signals(df):
    """Detect ALL potential signals, even when already in trade"""

    potential_signals = []

    for i in range(55, len(df)):
        row = df.iloc[i]

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

        if bullish or bearish:
            potential_signals.append({
                'index': i,
                'timestamp': row['timestamp_dt'],
                'price': float(row['close']),
                'direction': 'long' if bullish else 'short',
                'adx': float(row.get('adx', 0)),
                'plus_di': float(row.get('plus_di', 0)),
                'minus_di': float(row.get('minus_di', 0)),
                'volume_ratio': float(row.get('volume_ratio', 0))
            })

    return potential_signals

def backtest_with_details(df, initial_capital=INITIAL_CAPITAL):
    """Run backtest and capture detailed information for each trade"""

    df = df.copy()
    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    # Add 1 hour for European timezone (UTC+1)
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms') + pd.Timedelta(hours=1)

    trades = []
    capital = initial_capital
    in_trade = False

    for i in range(55, len(df) - 1):
        current = df.iloc[i]

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
                entry_i = i - 1
                entry_time = prev['timestamp_dt']
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

                best_price = entry_price

                entry_conditions = {
                    'adx': float(prev.get('adx', 0)),
                    'plus_di': float(prev.get('plus_di', 0)),
                    'minus_di': float(prev.get('minus_di', 0)),
                    'ema_20': float(prev['ema_20']),
                    'ema_50': float(prev['ema_50']),
                    'volume_ratio': float(prev.get('volume_ratio', 0)),
                    'price': float(prev['close'])
                }

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

                exit_conditions = {
                    'adx': float(current.get('adx', 0)),
                    'plus_di': float(current.get('plus_di', 0)),
                    'minus_di': float(current.get('minus_di', 0)),
                    'ema_20': float(current['ema_20']),
                    'ema_50': float(current['ema_50']),
                    'price': float(current['close'])
                }

                trade_record = {
                    'trade_id': len(trades) + 1,
                    'entry_time': entry_time,
                    'exit_time': current['timestamp_dt'],
                    'entry_index': entry_i,
                    'exit_index': i,
                    'direction': direction,
                    'entry_price': float(entry_price),
                    'exit_price': float(exit_price),
                    'tp_price': float(tp_price),
                    'sl_price': float(sl_price),
                    'quantity': float(quantity),
                    'pnl': float(pnl_net),
                    'pnl_pct': float((pnl_net / (entry_price * quantity)) * 100),
                    'exit_reason': exit_reason,
                    'capital_after': float(capital),
                    'entry_conditions': entry_conditions,
                    'exit_conditions': exit_conditions,
                    'duration_hours': int((i - entry_i) * 4),
                    'max_gain_pct': float(current_gain_pct)
                }
                trades.append(trade_record)

                in_trade = False

    return trades, df

def generate_interactive_viewer_v2(df, trades, potential_signals):
    """Generate enhanced viewer with indicators"""

    trades_json = json.dumps(trades, default=str, indent=2)
    signals_json = json.dumps(potential_signals, default=str, indent=2)

    # Convert df to simplified format for JavaScript
    df_simple = df[['timestamp_dt', 'open', 'high', 'low', 'close', 'volume',
                    'adx', 'plus_di', 'minus_di', 'ema_20', 'ema_50', 'volume_ratio']].copy()
    df_json = df_simple.to_json(orient='records', date_format='iso')

    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]

    # Count missed signals (signals that happened during trades)
    trade_indices = set()
    for t in trades:
        for i in range(t['entry_index'], t['exit_index'] + 1):
            trade_indices.add(i)

    missed_signals = [s for s in potential_signals if s['index'] in trade_indices]
    taken_signals = [s for s in potential_signals if s['index'] not in trade_indices]

    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade Replay Viewer V2 - {PAIR} {INTERVAL}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            overflow: hidden;
        }}

        .container {{
            display: grid;
            grid-template-columns: 350px 1fr;
            grid-template-rows: auto 1fr 80px;
            height: 100vh;
            gap: 0;
        }}

        .header {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}

        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 5px;
        }}

        .header .subtitle {{
            font-size: 14px;
            opacity: 0.9;
        }}

        .sidebar {{
            background: #1a1f3a;
            padding: 20px;
            overflow-y: auto;
            border-right: 1px solid #2a2f4a;
        }}

        .chart-container {{
            background: #0f1729;
            position: relative;
            overflow: hidden;
        }}

        #chart {{
            width: 100%;
            height: 100%;
        }}

        .controls {{
            grid-column: 1 / -1;
            background: #1a1f3a;
            padding: 15px 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-top: 1px solid #2a2f4a;
            gap: 20px;
        }}

        .controls-left {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .controls-center {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}

        .btn {{
            padding: 10px 20px;
            background: #667eea;
            border: none;
            border-radius: 6px;
            color: white;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
            font-weight: 500;
        }}

        .btn:hover {{
            background: #5568d3;
            transform: translateY(-1px);
        }}

        .btn:disabled {{
            background: #3a3f5a;
            cursor: not-allowed;
            transform: none;
        }}

        .btn-success {{
            background: #10b981;
        }}

        .btn-success:hover {{
            background: #059669;
        }}

        .btn-danger {{
            background: #ef4444;
        }}

        .btn-danger:hover {{
            background: #dc2626;
        }}

        .slider-container {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .slider {{
            flex: 1;
            -webkit-appearance: none;
            height: 6px;
            border-radius: 3px;
            background: #2a2f4a;
            outline: none;
        }}

        .slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .slider::-webkit-slider-thumb:hover {{
            background: #5568d3;
            transform: scale(1.2);
        }}

        .trade-info {{
            background: #252a42;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}

        .trade-info h3 {{
            font-size: 16px;
            margin-bottom: 12px;
            color: #667eea;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #2a2f4a;
            font-size: 13px;
        }}

        .info-row:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            color: #9ca3af;
        }}

        .info-value {{
            font-weight: 600;
        }}

        .positive {{
            color: #10b981;
        }}

        .negative {{
            color: #ef4444;
        }}

        .neutral {{
            color: #6b7280;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-long {{
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }}

        .badge-short {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}

        .badge-tp, .badge-sl, .badge-exit {{
            background: rgba(251, 191, 36, 0.2);
            color: #fbbf24;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
        }}

        .stat-box {{
            background: #1a1f3a;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
        }}

        .stat-label {{
            font-size: 11px;
            color: #9ca3af;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}

        .stat-value {{
            font-size: 18px;
            font-weight: 700;
        }}

        .progress-text {{
            font-size: 12px;
            color: #9ca3af;
            text-align: center;
        }}

        .warning-box {{
            background: rgba(251, 191, 36, 0.1);
            border-left: 4px solid #fbbf24;
            padding: 12px;
            border-radius: 4px;
            margin-top: 15px;
            font-size: 12px;
            color: #fbbf24;
        }}

        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: #1a1f3a;
        }}

        ::-webkit-scrollbar-thumb {{
            background: #2a2f4a;
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: #3a3f5a;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Trade Replay Viewer V2 (avec indicateurs)</h1>
            <div class="subtitle">{PAIR} • {INTERVAL} • {len(trades)} Trades • {len(potential_signals)} Signaux Potentiels • {len(missed_signals)} Rates</div>
        </div>

        <div class="sidebar">
            <div id="trade-details"></div>

            <div class="trade-info">
                <h3>Statistiques Globales</h3>
                <div class="info-row">
                    <span class="info-label">Total Trades</span>
                    <span class="info-value">{len(trades)}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Gagnants</span>
                    <span class="info-value positive">{len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Perdants</span>
                    <span class="info-value negative">{len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Capital Final</span>
                    <span class="info-value positive">${trades[-1]['capital_after']:,.0f}</span>
                </div>
            </div>

            <div class="trade-info">
                <h3>Analyse Signaux</h3>
                <div class="info-row">
                    <span class="info-label">Signaux Potentiels</span>
                    <span class="info-value">{len(potential_signals)}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Signaux Pris</span>
                    <span class="info-value positive">{len(taken_signals)}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Signaux Rates</span>
                    <span class="info-value neutral">{len(missed_signals)}</span>
                </div>
                <div class="warning-box">
                    Les signaux rates sont ceux qui apparaissent pendant qu'on est deja en position
                </div>
            </div>
        </div>

        <div class="chart-container">
            <div id="chart"></div>
        </div>

        <div class="controls">
            <div class="controls-left">
                <button class="btn" id="prevBtn" onclick="previousTrade()">Precedent</button>
                <button class="btn" id="nextBtn" onclick="nextTrade()">Suivant</button>
            </div>

            <div class="controls-center">
                <div class="slider-container">
                    <span style="font-size: 12px; color: #9ca3af;">Trade 1</span>
                    <input type="range" min="1" max="{len(trades)}" value="1" class="slider" id="tradeSlider" oninput="goToTrade(this.value)">
                    <span style="font-size: 12px; color: #9ca3af;">Trade {len(trades)}</span>
                </div>
                <div class="progress-text" id="progressText">Trade 1 / {len(trades)}</div>
            </div>

            <div class="controls-left">
                <button class="btn btn-success" onclick="filterWinningTrades()">Gagnants</button>
                <button class="btn btn-danger" onclick="filterLosingTrades()">Perdants</button>
                <button class="btn" onclick="showAllTrades()">Tous</button>
                <input type="date" id="dateSearch" class="btn" style="padding: 8px;" onchange="searchByDate(this.value)">
            </div>
        </div>
    </div>

    <script>
        const trades = {trades_json};
        const dfData = {df_json};
        const potentialSignals = {signals_json};

        let currentTradeIndex = 0;
        let filteredTrades = trades;

        function showTrade(index) {{
            if (index < 0 || index >= filteredTrades.length) return;

            currentTradeIndex = index;
            const trade = filteredTrades[index];

            document.getElementById('tradeSlider').value = index + 1;
            document.getElementById('progressText').textContent = `Trade ${{index + 1}} / ${{filteredTrades.length}}`;

            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === filteredTrades.length - 1;

            updateTradeDetails(trade);
            updateChart(trade);
        }}

        function updateTradeDetails(trade) {{
            const isProfitable = trade.pnl > 0;
            const profitClass = isProfitable ? 'positive' : 'negative';
            const directionBadge = trade.direction === 'long' ? 'badge-long' : 'badge-short';

            document.getElementById('trade-details').innerHTML = `
                <div class="trade-info">
                    <h3>Trade #${{trade.trade_id}}</h3>
                    <div class="info-row">
                        <span class="info-label">Direction</span>
                        <span class="info-value"><span class="badge ${{directionBadge}}">${{trade.direction}}</span></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Entree</span>
                        <span class="info-value">${{new Date(trade.entry_time).toLocaleString('fr-FR', {{
                            year: 'numeric', month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit'
                        }})}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Sortie</span>
                        <span class="info-value">${{new Date(trade.exit_time).toLocaleString('fr-FR', {{
                            year: 'numeric', month: '2-digit', day: '2-digit',
                            hour: '2-digit', minute: '2-digit'
                        }})}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Prix Entree</span>
                        <span class="info-value">$${{trade.entry_price.toFixed(2)}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Prix Sortie</span>
                        <span class="info-value">$${{trade.exit_price.toFixed(2)}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">PnL</span>
                        <span class="info-value ${{profitClass}}">${{trade.pnl >= 0 ? '+' : ''}}$${{trade.pnl.toFixed(2)}} (${{trade.pnl_pct >= 0 ? '+' : ''}}${{trade.pnl_pct.toFixed(2)}}%)</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Raison Sortie</span>
                        <span class="info-value">${{trade.exit_reason}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Duree</span>
                        <span class="info-value">${{trade.duration_hours}}h (${{Math.floor(trade.duration_hours/24)}}j ${{trade.duration_hours%24}}h)</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Capital Apres</span>
                        <span class="info-value positive">$${{trade.capital_after.toFixed(2)}}</span>
                    </div>
                </div>

                <div class="trade-info">
                    <h3>Indicateurs Entree</h3>
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-label">ADX</div>
                            <div class="stat-value">${{trade.entry_conditions.adx.toFixed(1)}}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">Volume</div>
                            <div class="stat-value">${{trade.entry_conditions.volume_ratio.toFixed(2)}}x</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">DI+</div>
                            <div class="stat-value positive">${{trade.entry_conditions.plus_di.toFixed(1)}}</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-label">DI-</div>
                            <div class="stat-value negative">${{trade.entry_conditions.minus_di.toFixed(1)}}</div>
                        </div>
                    </div>
                </div>
            `;
        }}

        function updateChart(trade) {{
            const startIdx = Math.max(0, trade.entry_index - 100);
            const endIdx = Math.min(dfData.length - 1, trade.exit_index + 50);
            const visibleData = dfData.slice(startIdx, endIdx);

            // Create subplots
            const traces = [];

            // Subplot 1: Price + EMAs
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                open: visibleData.map(d => d.open),
                high: visibleData.map(d => d.high),
                low: visibleData.map(d => d.low),
                close: visibleData.map(d => d.close),
                type: 'candlestick',
                name: 'Price',
                xaxis: 'x',
                yaxis: 'y',
                increasing: {{line: {{color: '#10b981'}}}},
                decreasing: {{line: {{color: '#ef4444'}}}}
            }});

            // EMA 20
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.ema_20),
                type: 'scatter',
                mode: 'lines',
                name: 'EMA 20',
                line: {{color: '#3b82f6', width: 1.5}},
                xaxis: 'x',
                yaxis: 'y'
            }});

            // EMA 50
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.ema_50),
                type: 'scatter',
                mode: 'lines',
                name: 'EMA 50',
                line: {{color: '#f59e0b', width: 1.5}},
                xaxis: 'x',
                yaxis: 'y'
            }});

            // Entry marker
            traces.push({{
                x: [trade.entry_time],
                y: [trade.entry_price],
                mode: 'markers+text',
                marker: {{
                    color: trade.direction === 'long' ? '#10b981' : '#ef4444',
                    size: 15,
                    symbol: 'triangle-up'
                }},
                text: ['ENTRY'],
                textposition: 'top center',
                name: 'Entry',
                xaxis: 'x',
                yaxis: 'y'
            }});

            // Exit marker
            traces.push({{
                x: [trade.exit_time],
                y: [trade.exit_price],
                mode: 'markers+text',
                marker: {{
                    color: trade.pnl > 0 ? '#10b981' : '#ef4444',
                    size: 15,
                    symbol: 'triangle-down'
                }},
                text: ['EXIT'],
                textposition: 'bottom center',
                name: 'Exit',
                xaxis: 'x',
                yaxis: 'y'
            }});

            // Subplot 2: ADX + DI+ + DI-
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.adx),
                type: 'scatter',
                mode: 'lines',
                name: 'ADX',
                line: {{color: '#8b5cf6', width: 2}},
                xaxis: 'x2',
                yaxis: 'y2',
                showlegend: false
            }});

            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.plus_di),
                type: 'scatter',
                mode: 'lines',
                name: 'DI+',
                line: {{color: '#10b981', width: 1.5}},
                xaxis: 'x2',
                yaxis: 'y2',
                showlegend: false
            }});

            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.minus_di),
                type: 'scatter',
                mode: 'lines',
                name: 'DI-',
                line: {{color: '#ef4444', width: 1.5}},
                xaxis: 'x2',
                yaxis: 'y2',
                showlegend: false
            }});

            // ADX threshold line
            traces.push({{
                x: [visibleData[0].timestamp_dt, visibleData[visibleData.length - 1].timestamp_dt],
                y: [30, 30],
                type: 'scatter',
                mode: 'lines',
                name: 'ADX Threshold',
                line: {{color: '#6b7280', width: 1, dash: 'dash'}},
                xaxis: 'x2',
                yaxis: 'y2',
                showlegend: false
            }});

            // Subplot 3: Volume
            const volumeColors = visibleData.map(d => d.close >= d.open ? '#10b981' : '#ef4444');
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: visibleData.map(d => d.volume),
                type: 'bar',
                name: 'Volume',
                marker: {{color: volumeColors, opacity: 0.5}},
                xaxis: 'x3',
                yaxis: 'y3',
                showlegend: false
            }});

            // Volume ratio threshold
            const volumeThreshold = visibleData.map(d => d.volume / d.volume_ratio * {VOLUME_THRESHOLD});
            traces.push({{
                x: visibleData.map(d => d.timestamp_dt),
                y: volumeThreshold,
                type: 'scatter',
                mode: 'lines',
                name: 'Vol Threshold',
                line: {{color: '#fbbf24', width: 1, dash: 'dash'}},
                xaxis: 'x3',
                yaxis: 'y3',
                showlegend: false
            }});

            const layout = {{
                paper_bgcolor: '#0f1729',
                plot_bgcolor: '#0f1729',
                font: {{color: '#e0e0e0', size: 11}},
                margin: {{l: 60, r: 30, t: 30, b: 40}},
                showlegend: false,
                xaxis: {{
                    gridcolor: '#1a1f3a',
                    showticklabels: false,
                    anchor: 'y',
                    rangeslider: {{visible: false}}
                }},
                yaxis: {{
                    title: 'Prix',
                    gridcolor: '#1a1f3a',
                    domain: [0.50, 1],
                    anchor: 'x'
                }},
                xaxis2: {{
                    gridcolor: '#1a1f3a',
                    showticklabels: false,
                    anchor: 'y2',
                    rangeslider: {{visible: false}}
                }},
                yaxis2: {{
                    title: 'ADX/DI',
                    gridcolor: '#1a1f3a',
                    domain: [0.25, 0.45],
                    anchor: 'x2'
                }},
                xaxis3: {{
                    gridcolor: '#1a1f3a',
                    anchor: 'y3',
                    rangeslider: {{visible: false}}
                }},
                yaxis3: {{
                    title: 'Volume',
                    gridcolor: '#1a1f3a',
                    domain: [0, 0.20],
                    anchor: 'x3'
                }},
                dragmode: 'pan'
            }};

            const config = {{
                scrollZoom: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            }};

            Plotly.react('chart', traces, layout, config);
        }}

        function nextTrade() {{
            if (currentTradeIndex < filteredTrades.length - 1) {{
                showTrade(currentTradeIndex + 1);
            }}
        }}

        function previousTrade() {{
            if (currentTradeIndex > 0) {{
                showTrade(currentTradeIndex - 1);
            }}
        }}

        function goToTrade(value) {{
            showTrade(parseInt(value) - 1);
        }}

        function filterWinningTrades() {{
            filteredTrades = trades.filter(t => t.pnl > 0);
            currentTradeIndex = 0;
            document.getElementById('tradeSlider').max = filteredTrades.length;
            showTrade(0);
        }}

        function filterLosingTrades() {{
            filteredTrades = trades.filter(t => t.pnl <= 0);
            currentTradeIndex = 0;
            document.getElementById('tradeSlider').max = filteredTrades.length;
            showTrade(0);
        }}

        function showAllTrades() {{
            filteredTrades = trades;
            currentTradeIndex = 0;
            document.getElementById('tradeSlider').max = filteredTrades.length;
            showTrade(0);
        }}

        function searchByDate(dateStr) {{
            if (!dateStr) return;

            const searchDate = new Date(dateStr);

            // Find trade closest to this date
            let closestIndex = 0;
            let minDiff = Math.abs(new Date(filteredTrades[0].entry_time) - searchDate);

            for (let i = 1; i < filteredTrades.length; i++) {{
                const diff = Math.abs(new Date(filteredTrades[i].entry_time) - searchDate);
                if (diff < minDiff) {{
                    minDiff = diff;
                    closestIndex = i;
                }}
            }}

            showTrade(closestIndex);

            // Show info about this date
            const trade = filteredTrades[closestIndex];
            const entryDate = new Date(trade.entry_time);

            if (Math.abs(entryDate - searchDate) > 7 * 24 * 60 * 60 * 1000) {{
                alert(`Aucun trade trouve exactement a cette date.\\nTrade le plus proche: ${{entryDate.toLocaleDateString('fr-FR')}}`);
            }}
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') previousTrade();
            if (e.key === 'ArrowRight') nextTrade();
        }});

        if (trades.length > 0) {{
            showTrade(0);
        }}
    </script>
</body>
</html>
    """

    return html_content

def main():
    print("\n" + "="*80)
    print("TRADE REPLAY VIEWER V2 - Generation (avec indicateurs)")
    print("="*80)
    print(f"\nPair: {PAIR} | Timeframe: {INTERVAL}")
    print("Fetching data...")

    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")
    print("Running backtest...")

    trades, df = backtest_with_details(df)

    print("Detecting all potential signals...")
    potential_signals = detect_all_potential_signals(df)

    print(f"Trades: {len(trades)}")
    print(f"Potential signals: {len(potential_signals)}")

    # Calculate missed signals
    trade_indices = set()
    for t in trades:
        for i in range(t['entry_index'], t['exit_index'] + 1):
            trade_indices.add(i)

    missed_signals = [s for s in potential_signals if s['index'] in trade_indices]
    print(f"Missed signals (during trades): {len(missed_signals)}")

    print("Generating interactive viewer with indicators...")

    html_content = generate_interactive_viewer_v2(df, trades, potential_signals)

    output_file = "trade_replay_viewer_v2.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n[OK] Enhanced Trade Replay Viewer generated: {output_file}")
    print("\nNew features:")
    print("  - Price chart with EMA 20 and EMA 50")
    print("  - ADX + DI+ + DI- on separate subplot")
    print("  - Volume chart with threshold line")
    print("  - Shows ALL potential signals (even missed ones)")
    print("  - Explains why some signals don't trigger trades")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
