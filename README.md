# Trading Bot - ADX Trend Strategy (Rank 8)

Bot de trading automatique utilisant la stratégie ADX Trend optimisée.

## 📊 Performances

- **Total Return** : 1340% (sur 8 ans)
- **Annual Return** : 38.3%
- **Max Drawdown** : 13%
- **Win Rate** : 31.7%
- **Profit Factor** : 1.82

*Période testée : 2017-2025 (8 ans) | Paire : BTCUSDT | Timeframe : 4h*

## 🚀 Démarrage Rapide

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

1. Éditer `config/settings.py`
2. Ajouter tes clés API Binance
3. Configurer Telegram (optionnel)

### Lancement

```bash
start_bot.bat
```

OU

```bash
python bot_with_position_tracking.py
```

## 📁 Fichiers Principaux

### Code
- `bot_with_position_tracking.py` - Bot principal
- `final_strategy_rank8.py` - Stratégie ADX optimisée
- `telegram_bot.py` - Notifications Telegram
- `verify_setup.py` - Vérification de la config

### Configuration
- `config/settings.py` - Paramètres généraux
- `requirements.txt` - Dépendances Python
- `start_bot.bat` - Script de lancement

### Documentation
- `STRATEGIE_ACTIVE.txt` - Détails de la stratégie
- `COMMENT_CA_MARCHE.md` - Fonctionnement du bot
- `QUICK_START.md` - Guide de démarrage
- `final_strategy_rank8_backtest.html` - Rapport de performance

## 🎯 Stratégie

### Paramètres
- **ADX Threshold** : 30
- **Take Profit** : 4.0%
- **Stop Loss** : 0.7%
- **Max Hold** : 20 bougies (80h)
- **Volume Threshold** : 1.8x

### Conditions d'Entrée LONG
- ADX > 30
- DI+ > DI-
- Prix > EMA20
- EMA20 > EMA50
- Volume > 1.8x moyenne

### Conditions d'Entrée SHORT
- ADX > 30
- DI- > DI+
- Prix < EMA20
- EMA20 < EMA50
- Volume > 1.8x moyenne

### Conditions de Sortie
1. Take Profit atteint (±4%)
2. Stop Loss touché (±0.7%)
3. Signal Exit (ADX < 20 OU croisement EMA20)
4. Max Hold (20 bougies)

## 📈 Indicateurs Utilisés

- **ADX** : Mesure la force de la tendance
- **DI+/DI-** : Direction de la tendance
- **EMA 20/50** : Moyennes mobiles exponentielles
- **Volume Ratio** : Volume relatif sur 20 périodes

## ⚙️ Configuration du Bot

### Modes Disponibles
- **Mode automatique** (par défaut) : Trade sans intervention
- **Mode paper trading** : Test sans risque

### Gestion des Positions
- Position sizing : 1% du capital par trade
- Une seule position à la fois
- Suivi en temps réel avec Telegram

## 📊 Rapports et Monitoring

### Rapport de Backtest
Ouvrir `final_strategy_rank8_backtest.html` dans un navigateur pour voir :
- Courbe d'équité
- Liste des trades
- Statistiques détaillées
- Analyse par année

### Notifications Telegram
Le bot envoie des notifications pour :
- Ouverture de position
- Clôture de position
- Take Profit / Stop Loss atteints
- Erreurs et alertes

## 🛡️ Sécurité

- ✅ Frais Binance inclus dans les backtests (0.1%)
- ✅ Stop Loss strict sur chaque trade
- ✅ Max Drawdown limité à 13%
- ✅ Une seule position à la fois
- ✅ Gestion du risque : 1% par trade

## 📝 Notes Importantes

1. **Timeframe** : Le bot trade en 4h (une bougie = 4 heures)
2. **Frais** : Tous les résultats incluent les frais Binance
3. **Capital** : Backtests basés sur $10,000 initial
4. **Fear & Greed** : NON utilisé (dégrade les performances)

## ❓ FAQ

**Q : Combien de temps pour un trade ?**
R : Entre quelques heures et 80h maximum (20 bougies de 4h)

**Q : Combien de trades par mois ?**
R : Environ 5-7 trades/mois en moyenne (539 trades sur 8 ans = ~5.6/mois)

**Q : Quel capital minimum ?**
R : Au moins $1000 recommandé pour une bonne gestion du risque

**Q : Le bot fonctionne 24/7 ?**
R : Oui, mais vérifie uniquement à chaque nouvelle bougie 4h

**Q : Que faire en cas d'erreur ?**
R : Vérifie `verify_setup.py` et consulte les logs Telegram

## 🔧 Maintenance

### Vérification du Setup
```bash
python verify_setup.py
```

### Mise à Jour des Dépendances
```bash
pip install -r requirements.txt --upgrade
```

## 📞 Support

Pour toute question, consulte :
1. `STRATEGIE_ACTIVE.txt` - Détails de la stratégie
2. `COMMENT_CA_MARCHE.md` - Fonctionnement technique
3. `QUICK_START.md` - Guide pas à pas

---

**Dernière mise à jour** : 2025-11-10
**Stratégie** : ADX Trend Rank 8
**Performance** : 1340% sur 8 ans (38.3% annuel)
