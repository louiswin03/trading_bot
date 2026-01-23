"""
TRADE REPLAY VIEWER
Interface interactive pour visualiser chaque trade du backtest en mode replay
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

def backtest_with_details(df, initial_capital=INITIAL_CAPITAL):
    """Run backtest and capture detailed information for each trade"""

    df = df.copy()
    df = calculate_adx(df)
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')

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

                # Capture entry conditions
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

            # Update best price for trailing SL
            if direction == 'long':
                if current['high'] > best_price:
                    best_price = current['high']
                current_gain_pct = ((best_price - entry_price) / entry_price) * 100
            else:
                if current['low'] < best_price:
                    best_price = current['low']
                current_gain_pct = ((entry_price - best_price) / entry_price) * 100

            # Apply trailing SL
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

                # Capture exit conditions
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

def generate_interactive_viewer(df, trades):
    """Generate interactive HTML viewer with replay mode"""

    # Prepare trades data for JavaScript
    trades_json = json.dumps(trades, default=str, indent=2)

    # Create color-coded trade markers
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] <= 0]

    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade Replay Viewer - {PAIR} {INTERVAL}</title>
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

        .badge-tp {{
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }}

        .badge-sl {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}

        .badge-exit {{
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

        .no-trade {{
            text-align: center;
            padding: 40px 20px;
            color: #6b7280;
        }}

        .no-trade-icon {{
            font-size: 48px;
            margin-bottom: 10px;
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
            <h1>📊 Trade Replay Viewer</h1>
            <div class="subtitle">{PAIR} • {INTERVAL} • {len(trades)} Trades • +{((trades[-1]['capital_after'] - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):.1f}% Total Return</div>
        </div>

        <div class="sidebar">
            <div id="trade-details">
                <div class="no-trade">
                    <div class="no-trade-icon">🎬</div>
                    <div>Utilisez les controles ci-dessous pour naviguer entre les trades</div>
                </div>
            </div>

            <div class="trade-info">
                <h3>📈 Statistiques Globales</h3>
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
        </div>

        <div class="chart-container">
            <div id="chart"></div>
        </div>

        <div class="controls">
            <div class="controls-left">
                <button class="btn" id="prevBtn" onclick="previousTrade()">◀ Precedent</button>
                <button class="btn" id="nextBtn" onclick="nextTrade()">Suivant ▶</button>
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
                <button class="btn btn-success" onclick="filterWinningTrades()">✓ Gagnants</button>
                <button class="btn btn-danger" onclick="filterLosingTrades()">✗ Perdants</button>
                <button class="btn" onclick="showAllTrades()">Tous</button>
            </div>
        </div>
    </div>

    <script>
        const trades = {trades_json};
        const dfData = {df.to_json(orient='records', date_format='iso')};

        let currentTradeIndex = 0;
        let filteredTrades = trades;

        // Initialize chart
        function initChart() {{
            const trace1 = {{
                x: dfData.map(d => d.timestamp_dt),
                open: dfData.map(d => d.open),
                high: dfData.map(d => d.high),
                low: dfData.map(d => d.low),
                close: dfData.map(d => d.close),
                type: 'candlestick',
                name: 'Price',
                increasing: {{line: {{color: '#10b981'}}}},
                decreasing: {{line: {{color: '#ef4444'}}}}
            }};

            const layout = {{
                paper_bgcolor: '#0f1729',
                plot_bgcolor: '#0f1729',
                font: {{color: '#e0e0e0'}},
                xaxis: {{
                    gridcolor: '#1a1f3a',
                    showgrid: true
                }},
                yaxis: {{
                    gridcolor: '#1a1f3a',
                    showgrid: true
                }},
                margin: {{l: 50, r: 50, t: 30, b: 40}},
                showlegend: false,
                dragmode: 'pan'
            }};

            const config = {{
                scrollZoom: true,
                displayModeBar: true,
                displaylogo: false
            }};

            Plotly.newPlot('chart', [trace1], layout, config);
        }}

        function showTrade(index) {{
            if (index < 0 || index >= filteredTrades.length) return;

            currentTradeIndex = index;
            const trade = filteredTrades[index];

            // Update slider
            document.getElementById('tradeSlider').value = index + 1;
            document.getElementById('progressText').textContent = `Trade ${{index + 1}} / ${{filteredTrades.length}}`;

            // Update buttons
            document.getElementById('prevBtn').disabled = index === 0;
            document.getElementById('nextBtn').disabled = index === filteredTrades.length - 1;

            // Update trade details
            updateTradeDetails(trade);

            // Update chart with trade markers
            updateChart(trade);
        }}

        function updateTradeDetails(trade) {{
            const isProfitable = trade.pnl > 0;
            const profitClass = isProfitable ? 'positive' : 'negative';
            const directionBadge = trade.direction === 'long' ? 'badge-long' : 'badge-short';
            const exitBadge = trade.exit_reason === 'TP' ? 'badge-tp' : (trade.exit_reason === 'SL' || trade.exit_reason === 'Trailing SL' ? 'badge-sl' : 'badge-exit');

            document.getElementById('trade-details').innerHTML = `
                <div class="trade-info">
                    <h3>🎯 Trade #${{trade.trade_id}}</h3>
                    <div class="info-row">
                        <span class="info-label">Direction</span>
                        <span class="info-value"><span class="badge ${{directionBadge}}">${{trade.direction}}</span></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Entree</span>
                        <span class="info-value">${{new Date(trade.entry_time).toLocaleString('fr-FR')}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Sortie</span>
                        <span class="info-value">${{new Date(trade.exit_time).toLocaleString('fr-FR')}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Duree</span>
                        <span class="info-value">${{trade.duration_hours}}h (${{Math.floor(trade.duration_hours/24)}}j ${{trade.duration_hours%24}}h)</span>
                    </div>
                </div>

                <div class="trade-info">
                    <h3>💰 Resultat</h3>
                    <div class="info-row">
                        <span class="info-label">Prix Entree</span>
                        <span class="info-value">${{trade.entry_price.toFixed(2)}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Prix Sortie</span>
                        <span class="info-value">${{trade.exit_price.toFixed(2)}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">PnL</span>
                        <span class="info-value ${{profitClass}}">${{trade.pnl >= 0 ? '+' : ''}}$${{trade.pnl.toFixed(2)}} (${{trade.pnl_pct >= 0 ? '+' : ''}}${{trade.pnl_pct.toFixed(2)}}%)</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Raison Sortie</span>
                        <span class="info-value"><span class="badge ${{exitBadge}}">${{trade.exit_reason}}</span></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Capital Apres</span>
                        <span class="info-value positive">$${{trade.capital_after.toFixed(2)}}</span>
                    </div>
                </div>

                <div class="trade-info">
                    <h3>📊 Indicateurs Entree</h3>
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
                    <div class="info-row" style="margin-top: 10px;">
                        <span class="info-label">EMA 20</span>
                        <span class="info-value">$${{trade.entry_conditions.ema_20.toFixed(2)}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">EMA 50</span>
                        <span class="info-value">$${{trade.entry_conditions.ema_50.toFixed(2)}}</span>
                    </div>
                </div>
            `;
        }}

        function updateChart(trade) {{
            // Get data around the trade (show context)
            const startIdx = Math.max(0, trade.entry_index - 50);
            const endIdx = Math.min(dfData.length - 1, trade.exit_index + 50);
            const visibleData = dfData.slice(startIdx, endIdx);

            const trace1 = {{
                x: visibleData.map(d => d.timestamp_dt),
                open: visibleData.map(d => d.open),
                high: visibleData.map(d => d.high),
                low: visibleData.map(d => d.low),
                close: visibleData.map(d => d.close),
                type: 'candlestick',
                name: 'Price',
                increasing: {{line: {{color: '#10b981'}}}},
                decreasing: {{line: {{color: '#ef4444'}}}}
            }};

            // Entry marker
            const entryTrace = {{
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
                textfont: {{color: 'white', size: 10}},
                name: 'Entry',
                showlegend: false
            }};

            // Exit marker
            const exitTrace = {{
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
                textfont: {{color: 'white', size: 10}},
                name: 'Exit',
                showlegend: false
            }};

            // TP/SL lines
            const tpLine = {{
                x: [trade.entry_time, trade.exit_time],
                y: [trade.tp_price, trade.tp_price],
                mode: 'lines',
                line: {{color: '#10b981', width: 1, dash: 'dash'}},
                name: 'TP',
                showlegend: false
            }};

            const slLine = {{
                x: [trade.entry_time, trade.exit_time],
                y: [trade.sl_price, trade.sl_price],
                mode: 'lines',
                line: {{color: '#ef4444', width: 1, dash: 'dash'}},
                name: 'SL',
                showlegend: false
            }};

            const layout = {{
                paper_bgcolor: '#0f1729',
                plot_bgcolor: '#0f1729',
                font: {{color: '#e0e0e0'}},
                xaxis: {{
                    gridcolor: '#1a1f3a',
                    showgrid: true,
                    range: [visibleData[0].timestamp_dt, visibleData[visibleData.length - 1].timestamp_dt]
                }},
                yaxis: {{
                    gridcolor: '#1a1f3a',
                    showgrid: true
                }},
                margin: {{l: 50, r: 50, t: 30, b: 40}},
                showlegend: false,
                dragmode: 'pan'
            }};

            const config = {{
                scrollZoom: true,
                displayModeBar: true,
                displaylogo: false
            }};

            Plotly.react('chart', [trace1, entryTrace, exitTrace, tpLine, slLine], layout, config);
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

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') previousTrade();
            if (e.key === 'ArrowRight') nextTrade();
        }});

        // Initialize
        initChart();
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
    print("TRADE REPLAY VIEWER - Generation")
    print("="*80)
    print(f"\nPair: {PAIR} | Timeframe: {INTERVAL}")
    print("Fetching data...")

    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)

    if df is None:
        print("Error fetching data")
        return

    print(f"Data fetched: {len(df)} candles")
    print("Running backtest with detailed trade capture...")

    trades, df = backtest_with_details(df)

    print(f"Trades captured: {len(trades)}")
    print("Generating interactive viewer...")

    html_content = generate_interactive_viewer(df, trades)

    output_file = "trade_replay_viewer.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n[OK] Trade Replay Viewer generated: {output_file}")
    print("\nFeatures:")
    print("  - Navigate with Previous/Next buttons or Arrow keys")
    print("  - Use slider to jump to any trade")
    print("  - Filter winning/losing trades")
    print("  - See all indicators at entry/exit")
    print("  - Visual TP/SL lines on chart")
    print("  - Zoom and pan on chart")
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
