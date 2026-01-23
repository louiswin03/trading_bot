"""
Pair-specific optimized settings
Each pair has its own optimal TP/SL/Hold configuration based on backtesting
"""

# ==========================================
# PAIR-SPECIFIC CONFIGURATIONS
# ==========================================

PAIR_CONFIGS = {
    "BTCUSDT": {
        "name": "Bitcoin - Optimized Config",
        "tp_ratio": 0.015,          # 1.5% Take Profit (OPTIMIZED - was 2.0%)
        "sl_margin": 0.0001,        # 0.01% margin
        "sl_lookback": 3,           # 3 candles lookback (more stable)
        "max_hold": 5,              # 5 candles max hold
        "risk_per_trade": 1.0,      # 1% risk per trade

        # Strategy parameters (OPTIMIZED)
        "rsi_oversold": 40,         # RSI oversold threshold (was 35)
        "rsi_overbought": 60,       # RSI overbought threshold (was 65)
        "bb_period": 20,            # Bollinger Bands period
        "bb_std": 1.5,              # BB standard deviation (was 2.0)
        "bb_touch_mode": "wicks",   # Use wicks (low/high) for BB touch detection

        # Performance (5.7 years backtest - 50k candles)
        "expected_annual_return": 55.8,    # 55.8%/year (+31% vs old config!)
        "expected_winrate": 38.1,          # 38.1% (+2.2pp improvement)
        "expected_sharpe": 1.88,           # Excellent Sharpe
        "expected_max_dd": 7.5,            # 7.5% (slightly better)
        "expected_profit_factor": 1.59,

        "notes": "Optimized BTC config - RSI 40/60, BB(20,1.5), TP 1.5% gives +31% better returns with same DD"
    },

    "ETHUSDT": {
        "name": "Ethereum - Conservative Config",
        "tp_ratio": 0.015,          # 1.5% Take Profit
        "sl_margin": 0.0001,        # 0.01% margin
        "sl_lookback": 1,           # 1 candle lookback
        "max_hold": 5,              # 5 candles max hold
        "risk_per_trade": 1.0,      # 1% risk per trade

        # Strategy parameters (CURRENT BEST)
        "rsi_oversold": 35,         # RSI oversold threshold
        "rsi_overbought": 65,       # RSI overbought threshold
        "bb_period": 20,            # Bollinger Bands period
        "bb_std": 2.0,              # BB standard deviation
        "bb_touch_mode": "wicks",   # Use wicks (low/high) for BB touch detection

        # Performance (5.7 years backtest - 50k candles)
        "expected_annual_return": 50.6,    # 50.6%/year
        "expected_winrate": 41.0,          # 41% - Excellent
        "expected_sharpe": 2.05,           # Excellent Sharpe
        "expected_max_dd": 8.6,            # Very low DD
        "expected_profit_factor": 1.47,

        "notes": "Best ETH config - Already optimal with excellent WR (41%) and Sharpe (2.05)"
    },

    "SOLUSDT": {
        "name": "Solana - High Performance Config",
        "tp_ratio": 0.015,          # 1.5% Take Profit
        "sl_margin": 0.0001,        # 0.01% margin
        "sl_lookback": 1,           # 1 candle lookback
        "max_hold": 5,              # 5 candles max hold
        "risk_per_trade": 1.0,      # 1% risk per trade

        # Strategy parameters (CURRENT BEST)
        "rsi_oversold": 35,         # RSI oversold threshold
        "rsi_overbought": 65,       # RSI overbought threshold
        "bb_period": 20,            # Bollinger Bands period
        "bb_std": 2.0,              # BB standard deviation
        "bb_touch_mode": "wicks",   # Use wicks (low/high) for BB touch detection

        # Performance (5.2 years backtest - 50k candles)
        "expected_annual_return": 80.6,    # 80.6%/year - Excellent!
        "expected_winrate": 47.4,          # 47.4% - Best WR
        "expected_sharpe": 2.75,           # Best Sharpe overall!
        "expected_max_dd": 10.0,           # Very good DD
        "expected_profit_factor": 1.61,    # Best PF

        "notes": "Best SOL config - Excellent return (80.6%/y) with best WR (47.4%) and Sharpe (2.75)"
    }
}

# Default config for unknown pairs
DEFAULT_CONFIG = {
    "name": "Universal Config",
    "tp_ratio": 0.02,
    "sl_margin": 0.0001,
    "sl_lookback": 1,
    "max_hold": 5,
    "risk_per_trade": 1.0,
    "notes": "Universal config - Works well across all pairs"
}


def get_pair_config(pair: str) -> dict:
    """
    Get optimized configuration for a specific pair

    Args:
        pair: Trading pair (e.g., "BTCUSDT")

    Returns:
        dict: Configuration dictionary
    """
    return PAIR_CONFIGS.get(pair, DEFAULT_CONFIG)


def print_pair_config(pair: str):
    """Print configuration details for a pair"""
    config = get_pair_config(pair)

    print(f"\n{'='*80}")
    print(f"Configuration for {pair}")
    print(f"{'='*80}")
    print(f"\nName: {config['name']}")
    print(f"\nParameters:")
    print(f"  Take Profit:     {config['tp_ratio']*100:.1f}%")
    print(f"  SL Margin:       {config['sl_margin']*100:.2f}%")
    print(f"  SL Lookback:     {config['sl_lookback']} candle(s)")
    print(f"  Max Hold:        {config['max_hold']} candles")
    print(f"  Risk per Trade:  {config['risk_per_trade']:.1f}%")

    print(f"\nExpected Performance (from backtest):")
    print(f"  Annual Return:   {config.get('expected_annual_return', 'N/A')}%/year")
    print(f"  Winrate:         {config.get('expected_winrate', 'N/A')}%")
    print(f"  Sharpe Ratio:    {config.get('expected_sharpe', 'N/A')}")
    print(f"  Max Drawdown:    {config.get('expected_max_dd', 'N/A')}%")
    print(f"  Profit Factor:   {config.get('expected_profit_factor', 'N/A')}")

    print(f"\nNotes: {config['notes']}")
    print(f"{'='*80}\n")


def print_all_configs():
    """Print all pair configurations"""
    print("\n" + "="*80)
    print("ALL OPTIMIZED PAIR CONFIGURATIONS")
    print("="*80)

    for pair in PAIR_CONFIGS.keys():
        print_pair_config(pair)


if __name__ == "__main__":
    # Demo: print all configs
    print_all_configs()
