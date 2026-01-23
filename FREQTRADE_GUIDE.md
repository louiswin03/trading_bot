# Guide d'Adaptation de votre Stratégie RANK 8 pour Freqtrade

## 📋 Table des Matières
1. [Vue d'ensemble de la stratégie](#vue-densemble)
2. [Installation de Freqtrade](#installation)
3. [Configuration](#configuration)
4. [Backtesting](#backtesting)
5. [Dry-run (simulation)](#dry-run)
6. [Live Trading](#live-trading)
7. [Différences clés avec votre bot actuel](#différences)

---

## 🎯 Vue d'ensemble

Votre stratégie **RANK 8 v2** a été adaptée pour Freqtrade avec toutes ses caractéristiques :

### Caractéristiques Préservées
- ✅ ADX Threshold à 30
- ✅ EMA 20 et EMA 50
- ✅ Volume Ratio > 1.8x
- ✅ Take Profit à 4%
- ✅ Stop Loss initial à 0.7%
- ✅ Trailing SL dynamique (0.5%→BE, 1%→0.5%, 1.5%→1%, 2%→1.5%)
- ✅ Max Hold de 20 candles
- ✅ Signal Exit (ADX<20 ou croisement EMA20)
- ✅ Support LONG et SHORT

### Fichier de Stratégie
`freqtrade_strategy_rank8.py`

---

## 🔧 Installation

### 1. Installer Freqtrade

```bash
# Cloner Freqtrade
git clone https://github.com/freqtrade/freqtrade.git
cd freqtrade

# Installer avec Docker (recommandé)
docker-compose up -d

# OU installer avec pip (alternative)
pip install -e .
```

### 2. Créer la structure de configuration

```bash
# Créer le dossier pour les stratégies utilisateur
mkdir -p user_data/strategies

# Copier votre stratégie
cp ../trading_bot/freqtrade_strategy_rank8.py user_data/strategies/
```

---

## ⚙️ Configuration

### 1. Créer le fichier de configuration

Créez `config.json` dans le dossier `freqtrade/`:

```json
{
    "trading_mode": "futures",
    "margin_mode": "isolated",

    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.98,

    "dry_run": true,
    "dry_run_wallet": 10000,

    "timeframe": "4h",

    "max_open_trades": 1,

    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1,
        "check_depth_of_market": {
            "enabled": false,
            "bids_to_ask_delta": 1
        }
    },

    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },

    "exchange": {
        "name": "binance",
        "key": "",
        "secret": "",
        "ccxt_config": {
            "enableRateLimit": true
        },
        "ccxt_async_config": {
            "enableRateLimit": true
        },
        "pair_whitelist": [
            "BTC/USDT:USDT"
        ],
        "pair_blacklist": []
    },

    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ],

    "telegram": {
        "enabled": false,
        "token": "",
        "chat_id": ""
    },

    "api_server": {
        "enabled": true,
        "listen_ip_address": "0.0.0.0",
        "listen_port": 8080,
        "verbosity": "error",
        "enable_openapi": false,
        "jwt_secret_key": "changeme",
        "CORS_origins": [],
        "username": "freqtrader",
        "password": "changeme"
    },

    "bot_name": "rank8_bot",
    "initial_state": "running",
    "force_entry_enable": false,
    "internals": {
        "process_throttle_secs": 5
    }
}
```

### 2. Configuration pour Binance Futures

**IMPORTANT pour les SHORTS:** Vous devez utiliser le mode Futures pour pouvoir shorter.

```json
{
    "trading_mode": "futures",
    "margin_mode": "isolated",
    "exchange": {
        "name": "binance",
        "pair_whitelist": [
            "BTC/USDT:USDT"  // Format pour futures
        ]
    }
}
```

### 3. Configuration pour Spot (LONG seulement)

Si vous voulez seulement du LONG (pas de shorts):

```json
{
    "trading_mode": "spot",
    "exchange": {
        "name": "binance",
        "pair_whitelist": [
            "BTC/USDT"  // Format pour spot
        ]
    }
}
```

Et dans la stratégie, mettez:
```python
can_short = False
```

---

## 📊 Backtesting

### 1. Télécharger les données historiques

```bash
# Télécharger 2 ans de données en 4h pour BTC/USDT
freqtrade download-data \
    --exchange binance \
    --pairs BTC/USDT:USDT \
    --timeframes 4h \
    --days 730 \
    --trading-mode futures
```

### 2. Lancer le backtest

```bash
# Backtest de base
freqtrade backtesting \
    --strategy Rank8Strategy \
    --timeframe 4h \
    --timerange 20220101-20251208

# Backtest avec breakdown détaillé
freqtrade backtesting \
    --strategy Rank8Strategy \
    --timeframe 4h \
    --timerange 20220101-20251208 \
    --breakdown month
```

### 3. Analyser les résultats

Le backtest affichera:
- Total Profit
- Win Rate
- Max Drawdown
- Sharpe Ratio
- Nombre de trades
- Durée moyenne des trades

**Attendu (basé sur votre backtest actuel):**
- ROI annuel: ~50-80%
- Win Rate: ~40-45%
- Max Drawdown: <10%

---

## 🧪 Dry-run (Simulation)

### 1. Configurer le dry-run

Dans `config.json`:
```json
{
    "dry_run": true,
    "dry_run_wallet": 10000
}
```

### 2. Lancer le bot en simulation

```bash
freqtrade trade --strategy Rank8Strategy --config config.json
```

Le bot va:
- Se connecter à Binance pour les prix en temps réel
- Simuler les trades (pas d'argent réel)
- Afficher les signaux d'entrée/sortie
- Tracker les performances

### 3. Surveiller avec FreqUI

Accédez à l'interface web: `http://localhost:8080`

Credentials par défaut:
- Username: `freqtrader`
- Password: `changeme`

---

## 🚀 Live Trading (ARGENT RÉEL)

### ⚠️ ATTENTION - Checklist avant de lancer

- [ ] Backtest réussi avec bons résultats
- [ ] Dry-run testé pendant au moins 1 semaine
- [ ] API Keys Binance créées avec:
  - [ ] Trading activé
  - [ ] Futures activé (si shorts)
  - [ ] IP whitelisting (recommandé)
- [ ] Capital de départ approprié (minimum $1000 recommandé)
- [ ] Telegram configuré pour notifications
- [ ] Vous comprenez les risques

### 1. Créer les API Keys Binance

1. Allez sur Binance > API Management
2. Créez une nouvelle API Key
3. Activez:
   - Enable Spot & Margin Trading
   - Enable Futures (si shorts)
4. (Recommandé) Whitelist votre IP
5. Copiez la Key et le Secret

### 2. Configuration Live

Créez `config_live.json`:

```json
{
    "dry_run": false,  // ⚠️ LIVE MODE

    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.98,

    "exchange": {
        "name": "binance",
        "key": "VOTRE_API_KEY",
        "secret": "VOTRE_API_SECRET"
    },

    "telegram": {
        "enabled": true,
        "token": "VOTRE_TELEGRAM_BOT_TOKEN",
        "chat_id": "VOTRE_CHAT_ID"
    }
}
```

### 3. Lancer en LIVE

```bash
# ⚠️ ARGENT RÉEL - Vérifiez 3 fois avant de lancer!
freqtrade trade --strategy Rank8Strategy --config config_live.json
```

### 4. Surveillance

- Surveillez via FreqUI: `http://localhost:8080`
- Surveillez via Telegram (notifications)
- Vérifiez régulièrement les logs
- Gardez un œil sur le drawdown

---

## 🔄 Différences avec votre Bot Actuel

### Similitudes
- ✅ Même logique de stratégie (ADX + EMA + Volume)
- ✅ Mêmes indicateurs
- ✅ Mêmes conditions d'entrée/sortie
- ✅ Trailing SL identique
- ✅ TP/SL identiques

### Différences

| Aspect | Votre Bot | Freqtrade |
|--------|-----------|-----------|
| **Exécution** | Script Python manuel | Bot automatique continu |
| **Backtesting** | Script séparé | Intégré avec commande |
| **Interface** | HTML reports | FreqUI web interface |
| **Gestion positions** | Manuelle dans le code | Gérée automatiquement |
| **Notifications** | (À implémenter) | Telegram intégré |
| **Monitoring** | Logs Python | FreqUI + Telegram + Logs |
| **Optimisation** | Manuelle | Hyperopt intégré |

### Avantages de Freqtrade

1. **Automatisation complète**: Le bot tourne 24/7
2. **Interface web**: Visualisation en temps réel
3. **Backtesting avancé**: Analyse détaillée, breakdown par période
4. **Hyperopt**: Optimisation automatique des paramètres
5. **Community**: Grande communauté, support, plugins
6. **Sécurité**: Gestion des erreurs, reconnexion auto
7. **Multi-exchange**: Binance, Kraken, FTX, etc.

### Points d'attention

1. **Frais**: Vérifiez que les frais Binance (0.1%) sont bien configurés
2. **Slippage**: Freqtrade gère le slippage automatiquement
3. **Timing**: Votre bot vérifie les signaux à chaque candle close, Freqtrade aussi
4. **Trailing SL**: Implémenté via `custom_stoploss()`, testé en backtest

---

## 📈 Optimisation (Hyperopt)

Pour trouver les meilleurs paramètres:

```bash
freqtrade hyperopt \
    --strategy Rank8Strategy \
    --hyperopt-loss SharpeHyperOptLoss \
    --epochs 100 \
    --timeframe 4h \
    --timerange 20220101-20241201 \
    --spaces buy
```

Cela testera automatiquement différentes valeurs pour:
- `adx_threshold` (25-35)
- `volume_threshold` (1.5-2.5)

**Note:** Vos paramètres actuels (ADX=30, Volume=1.8) sont déjà optimisés, donc hyperopt est optionnel.

---

## 🆘 Troubleshooting

### Problème: "Strategy not found"
```bash
# Vérifier que la stratégie est dans le bon dossier
ls user_data/strategies/freqtrade_strategy_rank8.py

# Lister les stratégies disponibles
freqtrade list-strategies
```

### Problème: "Insufficient data"
```bash
# Télécharger plus de données
freqtrade download-data --pairs BTC/USDT:USDT --days 365
```

### Problème: "No trades in backtest"
- Vérifiez les seuils (ADX, volume)
- Vérifiez la timerange (période avec peu de volatilité?)
- Affichez les signaux: `--enable-protections`

### Problème: API errors
- Vérifiez les API keys
- Vérifiez les permissions (Futures activé?)
- Vérifiez l'IP whitelist

---

## 📚 Ressources

- **Documentation Freqtrade**: https://www.freqtrade.io/en/stable/
- **Stratégies exemples**: https://github.com/freqtrade/freqtrade-strategies
- **Discord Freqtrade**: https://discord.gg/freqtrade
- **Votre stratégie actuelle**: `final_strategy_rank8.py`

---

## ✅ Checklist Complète

### Phase 1: Préparation
- [ ] Freqtrade installé
- [ ] Stratégie copiée dans `user_data/strategies/`
- [ ] Config créée

### Phase 2: Backtesting
- [ ] Données téléchargées (2+ ans)
- [ ] Backtest lancé et analysé
- [ ] Résultats satisfaisants (ROI, Win Rate, DD)

### Phase 3: Dry-run
- [ ] Config dry-run créée
- [ ] Bot lancé en simulation
- [ ] Testé pendant 1+ semaine
- [ ] Résultats cohérents avec backtest

### Phase 4: Live (Optionnel)
- [ ] API Keys créées sur Binance
- [ ] IP Whitelisting activé
- [ ] Telegram configuré
- [ ] Config live créée
- [ ] Capital déposé
- [ ] **Triple vérification avant de lancer**
- [ ] Bot lancé en LIVE
- [ ] Surveillance active

---

## 🎓 Prochaines Étapes Recommandées

1. **Installer Freqtrade** (1h)
2. **Backtest sur 2 ans** (30 min)
3. **Analyser les résultats** vs votre backtest actuel
4. **Dry-run pendant 1 semaine** (0 risque)
5. **Si satisfait → Live avec petit capital** ($500-1000)
6. **Scale up progressivement** si profitable

---

**Bonne chance avec Freqtrade! 🚀**
