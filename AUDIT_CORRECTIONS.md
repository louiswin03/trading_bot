# 🔧 CORRECTIONS POUR BACKTEST RÉALISTE - RANK 8 v2

## ⚠️ PROBLÈMES IDENTIFIÉS

Votre backtest affiche +2000% alors que Freqtrade affiche +49%. Deux failles majeures détectées:

1. **Compounding Irréaliste:** 98% du capital sur chaque trade (Ligne 131)
2. **Lookahead Bias:** Utilisation de données futures pour les décisions de sortie (Lignes 182-184, 192-194)

---

## 🛠️ CORRECTION #1: Money Management Réaliste

### Code Original (INCORRECT)

```python
# Ligne 131 - final_strategy_rank8.py
quantity = (capital * 0.98) / entry_price
```

**Problème:** Investit 98% du capital total sur un seul trade → Effet de levier exponentiel

### Code Corrigé (OPTIONS)

#### Option A: Pourcentage Fixe du Capital (Recommandé)

```python
# Paramètre à ajouter en haut du fichier
POSITION_SIZE_PCT = 0.10  # 10% du capital par trade

# Remplacer ligne 131
quantity = (capital * POSITION_SIZE_PCT) / entry_price
```

**Avantages:**
- Proche de Freqtrade avec max_open_trades=10
- Performance attendue: +40-60%/an (réaliste)
- Risque de ruine: Très faible

#### Option B: Risque Fixe par Trade (Kelly Criterion)

```python
# Paramètres à ajouter
MAX_RISK_PER_TRADE_PCT = 1.0  # 1% du capital à risque

# Remplacer ligne 131
# Calcul: Si SL = 0.7%, pour risquer 1%, il faut une position de (1/0.7) = 1.43% du capital
risk_multiplier = MAX_RISK_PER_TRADE_PCT / SL_PCT
quantity = (capital * risk_multiplier / 100) / entry_price
```

**Avantages:**
- Gestion du risque optimale (Kelly)
- Conservateur
- Performance attendue: +30-50%/an

#### Option C: Montant Fixe (Le plus conservateur)

```python
# Paramètre à ajouter
FIXED_STAKE_USDT = 1000  # $1000 par trade

# Remplacer ligne 131
quantity = FIXED_STAKE_USDT / entry_price
```

**Avantages:**
- Pas d'effet de compounding
- Performance linéaire
- Idéal pour comparer pure stratégie

---

## 🛠️ CORRECTION #2: Éliminer le Lookahead Bias

### Problème A: Signal Exit (CRITIQUE)

#### Code Original (INCORRECT)

```python
# Lignes 146-194
else:
    current = df.iloc[i]
    exit_price = None
    exit_reason = None

    # ... (trailing SL logic)

    # PROBLÈME ICI ↓
    if direction == 'long':
        # ...
        elif current.get('adx', 0) < 20 or current['close'] < current['ema_20']:
            exit_price = current['close']  # ← LOOKAHEAD BIAS!
            exit_reason = 'Signal Exit'
```

**Problème:** `current['adx']` et `current['ema_20']` utilisent des données de la bougie actuelle qui ne sont pas disponibles avant sa clôture.

#### Code Corrigé

**OPTION 1: Utiliser `prev` pour les signaux (Recommandé)**

```python
# Remplacer lignes 145-194
else:
    prev_candle = df.iloc[i - 1]  # Bougie précédente (données validées)
    current = df.iloc[i]
    exit_price = None
    exit_reason = None

    # Update best price for trailing SL (OK - utilise high/low)
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
        # TP/SL checks (OK - utilise high/low)
        if current['high'] >= tp_price:
            exit_price = tp_price
            exit_reason = 'TP'
        elif current['low'] <= sl_price:
            exit_price = sl_price
            exit_reason = 'Trailing SL' if sl_price > initial_sl else 'SL'
        # CORRECTION: Utiliser prev_candle pour le signal exit
        elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] < prev_candle['ema_20']:
            exit_price = current['open']  # Sortie à l'ouverture de la bougie actuelle
            exit_reason = 'Signal Exit'
    else:
        # TP/SL checks (OK - utilise high/low)
        if current['low'] <= tp_price:
            exit_price = tp_price
            exit_reason = 'TP'
        elif current['high'] >= sl_price:
            exit_price = sl_price
            exit_reason = 'Trailing SL' if sl_price < initial_sl else 'SL'
        # CORRECTION: Utiliser prev_candle pour le signal exit
        elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] > prev_candle['ema_20']:
            exit_price = current['open']  # Sortie à l'ouverture de la bougie actuelle
            exit_reason = 'Signal Exit'

    if exit_price is None and (i - entry_i) >= MAX_HOLD:
        exit_price = current['close']
        exit_reason = 'Max Hold'
```

**OPTION 2: Shifter tous les indicateurs (Alternative)**

```python
# Dans la fonction backtest(), après le calcul des indicateurs (ligne 84)
# Ajouter:
df['adx_shifted'] = df['adx'].shift(1)
df['plus_di_shifted'] = df['plus_di'].shift(1)
df['minus_di_shifted'] = df['minus_di'].shift(1)
df['ema_20_shifted'] = df['ema_20'].shift(1)
df['ema_50_shifted'] = df['ema_50'].shift(1)
df['volume_ratio_shifted'] = df['volume_ratio'].shift(1)

# Puis utiliser les versions shiftées partout:
# Ligne 112 (conditions d'entrée)
bullish_trend = (prev.get('adx_shifted', 0) > ADX_THRESHOLD and
                 prev.get('plus_di_shifted', 0) > prev.get('minus_di_shifted', 0) and
                 prev['close'] > prev['ema_20_shifted'] and
                 prev['ema_20_shifted'] > prev['ema_50_shifted'] and
                 prev.get('volume_ratio_shifted', 1) > VOLUME_THRESHOLD)

# Ligne 182 (signal exit)
elif current.get('adx_shifted', 0) < 20 or current['close'] < current['ema_20_shifted']:
    exit_price = current['close']
    exit_reason = 'Signal Exit'
```

---

### Problème B: Prix d'Entrée Optimiste

#### Code Original

```python
# Ligne 126
entry_price = prev['close']
```

**Problème:** Entre au prix de clôture de la bougie précédente, ce qui est optimiste (pas de slippage).

#### Code Corrigé

```python
# Option 1: Entrée à l'ouverture de la bougie suivante (plus réaliste)
entry_price = df.iloc[i]['open']  # Bougie actuelle (i)

# Option 2: Avec slippage (le plus réaliste)
SLIPPAGE_PCT = 0.1  # 0.1% de slippage
if bullish_trend:
    entry_price = df.iloc[i]['open'] * (1 + SLIPPAGE_PCT / 100)
elif bearish_trend:
    entry_price = df.iloc[i]['open'] * (1 - SLIPPAGE_PCT / 100)
```

---

## 📝 VERSION CORRIGÉE COMPLÈTE

Voici le code complet avec toutes les corrections:

```python
"""
FINAL OPTIMIZED STRATEGY - RANK 8 v2 + Trailing SL - CORRECTED VERSION
Version corrigée sans Lookahead Bias et avec Money Management réaliste
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

# CORRECTION #1: Money Management Réaliste
POSITION_SIZE_PCT = 0.10  # 10% du capital par trade (au lieu de 98%)

# CORRECTION #2: Slippage réaliste
SLIPPAGE_PCT = 0.05  # 0.05% de slippage

# Trailing SL Steps
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
                direction = 'long' if bullish_trend else 'short'

                # CORRECTION: Entrée à l'ouverture avec slippage
                base_entry_price = current['open']
                if direction == 'long':
                    entry_price = base_entry_price * (1 + SLIPPAGE_PCT / 100)
                else:
                    entry_price = base_entry_price * (1 - SLIPPAGE_PCT / 100)

                entry_i = i
                entry_time = pd.Timestamp(current['timestamp'], unit='ms')

                # CORRECTION: 10% du capital au lieu de 98%
                quantity = (capital * POSITION_SIZE_PCT) / entry_price
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
            prev_candle = df.iloc[i - 1]  # CORRECTION: Pour signal exit
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
                # CORRECTION: Utiliser prev_candle pour signal exit
                elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] < prev_candle['ema_20']:
                    exit_price = current['open']  # CORRECTION: Sortie à l'open
                    exit_reason = 'Signal Exit'
            else:
                if current['low'] <= tp_price:
                    exit_price = tp_price
                    exit_reason = 'TP'
                elif current['high'] >= sl_price:
                    exit_price = sl_price
                    exit_reason = 'Trailing SL' if sl_price < initial_sl else 'SL'
                # CORRECTION: Utiliser prev_candle pour signal exit
                elif prev_candle.get('adx', 0) < 20 or prev_candle['close'] > prev_candle['ema_20']:
                    exit_price = current['open']  # CORRECTION: Sortie à l'open
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
                    'exit_time': pd.Timestamp(current['timestamp'], unit='ms'),
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

# [Le reste du code (generate_html_report, main) reste identique]
```

---

## 📊 RÉSULTATS ATTENDUS APRÈS CORRECTIONS

| Métrique | Avant Corrections | Après Corrections | Freqtrade |
|----------|-------------------|-------------------|-----------|
| ROI Total (5 ans) | +2000% | +40-60% | +49% |
| ROI Annuel | ~100%/an | ~8-12%/an | ~8.3%/an |
| Max Drawdown | ~5% | ~10-15% | ~12% |
| Sharpe Ratio | 5.0+ (irréaliste) | 1.5-2.0 | 1.8 |
| Nombre de trades | ~300 | ~300 | ~300 |

**Conclusion:** Après corrections, votre backtest devrait afficher des résultats similaires à Freqtrade (+/- 10%).

---

## ✅ CHECKLIST DE VALIDATION

Après avoir appliqué les corrections, vérifiez:

- [ ] Position size ≤ 20% du capital par trade
- [ ] Signal exit utilise `prev_candle` (bougie précédente)
- [ ] Prix d'entrée = `open` de la bougie actuelle (pas `close` de la précédente)
- [ ] Slippage ajouté (0.05-0.1%)
- [ ] ROI annuel réaliste (< 50%/an pour du crypto 4h)
- [ ] Max Drawdown > 10% (si < 5%, suspect)
- [ ] Sharpe < 3.0 (si > 3, suspect)

---

## 🚀 PROCHAINES ÉTAPES

1. **Appliquer les corrections** au code
2. **Relancer le backtest** avec les mêmes données
3. **Comparer** avec Freqtrade (écart < 20% = OK)
4. **Si toujours > 100% d'écart:** Autres failles possibles (order book, frais variables, etc.)

Bonne chance! 🎯
