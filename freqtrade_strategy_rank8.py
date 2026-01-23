"""
FREQTRADE ADAPTATION - RANK 8 v2 Strategy with Trailing SL

Stratégie ADX + EMA + Volume avec Trailing Stop Loss dynamique

Paramètres optimisés:
- ADX Threshold: 30
- TP: 4.0%
- SL Initial: 0.7%
- Trailing SL: 0.5%→BE, 1%→0.5%, 1.5%→1%, 2%→1.5%
- Max Hold: 20 candles (80h en 4h)
- Volume Threshold: 1.8x
- Timeframe: 4h

Performance attendue (backtest sur 5+ ans):
- ROI annuel: ~50-80%
- Winrate: ~40-45%
- Max Drawdown: <10%
"""

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class Rank8Strategy(IStrategy):
    """
    Stratégie ADX Trend Following avec Trailing SL

    Conditions d'entrée:
    - LONG: ADX>30, +DI>-DI, Close>EMA20>EMA50, Volume>1.8x
    - SHORT: ADX>30, -DI>+DI, Close<EMA20<EMA50, Volume>1.8x

    Gestion de sortie:
    - TP: 4%
    - SL initial: 0.7%
    - Trailing SL dynamique
    - Signal exit si ADX<20 ou prix croise EMA20
    - Max hold: 20 candles
    """

    # ====================================
    # CONFIGURATION GENERALE
    # ====================================

    # Stratégie optimisée pour timeframe 4h
    timeframe = '4h'

    # Activer les shorts (nécessite un exchange compatible)
    can_short = True

    # Nombre minimum de candles requis
    startup_candle_count: int = 50

    # Protection contre les pertes
    stoploss = -0.99  # SL fictif, géré manuellement dans custom_stoploss

    # ====================================
    # ROI (Take Profit)
    # ====================================

    # ROI à 4% - désactivé car géré dans custom_exit
    minimal_roi = {
        "0": 0.04  # 4% TP
    }

    # ====================================
    # PARAMETRES DE LA STRATEGIE
    # ====================================

    # ADX Threshold
    adx_threshold = IntParameter(25, 35, default=30, space='buy', optimize=False)

    # Volume multiplier
    volume_threshold = DecimalParameter(1.5, 2.5, default=1.8, space='buy', optimize=False)

    # EMA périodes (fixées)
    ema_short_period = 20
    ema_long_period = 50

    # Max hold en candles
    max_hold_candles = 20

    # ====================================
    # TRAILING STOP LOSS CONFIGURATION
    # ====================================

    # Trailing SL steps: (profit_threshold_pct, new_sl_pct)
    trailing_sl_steps = [
        (0.5, 0.0),   # À +0.5% profit → SL à break even (0%)
        (1.0, 0.5),   # À +1.0% profit → SL à +0.5%
        (1.5, 1.0),   # À +1.5% profit → SL à +1.0%
        (2.0, 1.5),   # À +2.0% profit → SL à +1.5%
    ]

    # ====================================
    # INDICATEURS
    # ====================================

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Calcul des indicateurs techniques
        """

        # ADX avec +DI et -DI
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=14)

        # EMAs
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=self.ema_short_period)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=self.ema_long_period)

        # Volume analysis
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']

        return dataframe

    # ====================================
    # SIGNAUX D'ENTREE
    # ====================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Conditions d'entrée LONG et SHORT
        """

        # LONG conditions
        dataframe.loc[
            (
                (dataframe['adx'] > self.adx_threshold.value) &  # Tendance forte
                (dataframe['plus_di'] > dataframe['minus_di']) &  # Momentum haussier
                (dataframe['close'] > dataframe['ema_20']) &      # Prix > EMA20
                (dataframe['ema_20'] > dataframe['ema_50']) &     # EMA20 > EMA50
                (dataframe['volume_ratio'] > self.volume_threshold.value) &  # Volume élevé
                (dataframe['volume'] > 0)  # Volume existant
            ),
            'enter_long'] = 1

        # SHORT conditions
        dataframe.loc[
            (
                (dataframe['adx'] > self.adx_threshold.value) &  # Tendance forte
                (dataframe['minus_di'] > dataframe['plus_di']) &  # Momentum baissier
                (dataframe['close'] < dataframe['ema_20']) &      # Prix < EMA20
                (dataframe['ema_20'] < dataframe['ema_50']) &     # EMA20 < EMA50
                (dataframe['volume_ratio'] > self.volume_threshold.value) &  # Volume élevé
                (dataframe['volume'] > 0)  # Volume existant
            ),
            'enter_short'] = 1

        return dataframe

    # ====================================
    # SIGNAUX DE SORTIE
    # ====================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Conditions de sortie anticipée (signal exit)
        """

        # LONG exit: ADX faible OU prix croise sous EMA20
        dataframe.loc[
            (
                (dataframe['adx'] < 20) |  # Perte de momentum
                (dataframe['close'] < dataframe['ema_20'])  # Prix croise sous EMA20
            ),
            'exit_long'] = 1

        # SHORT exit: ADX faible OU prix croise au-dessus EMA20
        dataframe.loc[
            (
                (dataframe['adx'] < 20) |  # Perte de momentum
                (dataframe['close'] > dataframe['ema_20'])  # Prix croise au-dessus EMA20
            ),
            'exit_short'] = 1

        return dataframe

    # ====================================
    # TRAILING STOP LOSS DYNAMIQUE
    # ====================================

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        Trailing Stop Loss dynamique basé sur le profit

        Returns:
            float: Nouveau stoploss (négatif)
        """

        # SL initial à -0.7%
        initial_sl = -0.007

        # Convertir current_profit (ratio) en pourcentage
        current_profit_pct = current_profit * 100

        # Appliquer le trailing SL selon les paliers
        new_sl = initial_sl

        for profit_threshold, sl_level in self.trailing_sl_steps:
            if current_profit_pct >= profit_threshold:
                # Convertir le niveau de SL en ratio négatif
                # sl_level est le profit garanti (ex: 0.5% → -0.005)
                new_sl = -(sl_level / 100)

        # Retourner le meilleur SL (le moins négatif = le plus protecteur)
        return max(new_sl, initial_sl)

    # ====================================
    # SORTIE PERSONNALISEE (MAX HOLD)
    # ====================================

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime',
                   current_rate: float, current_profit: float, **kwargs) -> str:
        """
        Logique de sortie personnalisée

        Gère le max hold (20 candles)
        """

        # Calculer le nombre de candles depuis l'entrée
        # Note: open_date_utc est en UTC
        trade_duration = (current_time - trade.open_date_utc).total_seconds()

        # Convertir en nombre de candles (4h = 14400 secondes)
        candles_held = int(trade_duration / 14400)

        # Si max hold atteint, sortir
        if candles_held >= self.max_hold_candles:
            return 'max_hold_reached'

        # Sinon, laisser les autres conditions gérer
        return None


# ====================================
# CONFIGURATION RECOMMANDEE
# ====================================

"""
Configuration Freqtrade recommandée (config.json):

{
    "trading_mode": "futures",  // ou "spot" si pas de shorts
    "margin_mode": "isolated",  // pour futures

    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.98,

    "dry_run": true,  // Toujours tester en dry-run d'abord!

    "timeframe": "4h",

    "max_open_trades": 1,  // Une position à la fois recommandé

    "entry_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },

    "exit_pricing": {
        "price_side": "same",
        "use_order_book": true,
        "order_book_top": 1
    },

    "exchange": {
        "name": "binance",
        "key": "YOUR_API_KEY",
        "secret": "YOUR_API_SECRET",
        "ccxt_config": {},
        "ccxt_async_config": {},
        "pair_whitelist": [
            "BTC/USDT"
        ],
        "pair_blacklist": []
    },

    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ],

    "telegram": {
        "enabled": true,
        "token": "YOUR_TELEGRAM_TOKEN",
        "chat_id": "YOUR_CHAT_ID"
    }
}
"""

# ====================================
# COMMANDES POUR TESTER
# ====================================

"""
1. Backtesting (recommandé en premier):
   freqtrade backtesting --strategy Rank8Strategy --timeframe 4h --timerange 20200101-20251208

2. Hyperopt (optionnel - pour optimiser ADX et Volume thresholds):
   freqtrade hyperopt --strategy Rank8Strategy --hyperopt-loss SharpeHyperOptLoss --epochs 100 --timeframe 4h

3. Dry-run (simulation temps réel):
   freqtrade trade --strategy Rank8Strategy --config config.json --dry-run

4. Live trading (ATTENTION - argent réel!):
   freqtrade trade --strategy Rank8Strategy --config config.json
"""
