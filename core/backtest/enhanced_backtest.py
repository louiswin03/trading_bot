"""
Enhanced backtesting engine with position sizing and advanced risk management
"""
import pandas as pd
from typing import Dict, List, Callable, Optional
from datetime import datetime
import numpy as np


class EnhancedBacktest:
    """
    Advanced backtesting engine with:
    - Position sizing based on risk percentage
    - Trailing stop loss
    - Multiple exit strategies
    - Detailed trade analytics
    """

    def __init__(self,
                 initial_capital: float = 10000,
                 risk_per_trade: float = 1.0,
                 tp_ratio: float = 0.025,
                 sl_margin: float = 0.00025,
                 max_hold: int = 10,
                 use_trailing_stop: bool = True,
                 trailing_stop_pct: float = 0.015):
        """
        Args:
            initial_capital: Starting capital in USDT
            risk_per_trade: Risk per trade as % of capital
            tp_ratio: Take profit ratio (default 2.5%)
            sl_margin: Stop loss margin
            max_hold: Maximum candles to hold position
            use_trailing_stop: Enable trailing stop
            trailing_stop_pct: Trailing stop percentage
        """
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.tp_ratio = tp_ratio
        self.sl_margin = sl_margin
        self.max_hold = max_hold
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct

    def run_backtest(self, df: pd.DataFrame, strategy_func: Callable,
                     signal_engine: Optional[object] = None) -> Dict:
        """
        Run backtest with enhanced features

        Args:
            df: DataFrame with OHLCV data and indicators
            strategy_func: Strategy function that returns (signal, candle)
            signal_engine: Optional SignalEngine for multi-factor scoring

        Returns:
            dict: Detailed backtest results
        """
        trades = []
        capital = self.initial_capital
        peak_capital = self.initial_capital
        max_drawdown = 0

        in_trade = False
        entry_price = 0
        entry_index = 0
        side = ""
        tp = 0
        sl = 0
        trailing_stop = 0
        quantity = 0
        max_profit_in_trade = 0
        max_drawdown_in_trade = 0

        for i in range(3, len(df) - 1):
            sub_df = df.iloc[:i + 1]
            signal, candle = strategy_func(sub_df)

            # Get current price data
            current_candle = df.iloc[i]
            current_price = current_candle['close']
            current_high = current_candle['high']
            current_low = current_candle['low']

            if not in_trade:
                # Entry logic
                if signal in ["buy", "sell", "strong_buy", "strong_sell"] and candle is not None:
                    in_trade = True
                    entry_price = candle["close"]
                    entry_index = i
                    side = 'buy' if 'buy' in signal.lower() else 'sell'

                    # Calculate position size based on risk
                    risk_amount = capital * (self.risk_per_trade / 100)

                    # Calculate stop loss (optimized: 1 candle lookback)
                    lookback = df.iloc[i - 1:i]
                    if side == "buy":
                        lowest_low = lookback["low"].min()
                        sl = lowest_low * (1 - self.sl_margin)
                        tp = entry_price * (1 + self.tp_ratio)
                        risk_per_coin = entry_price - sl
                    else:  # sell
                        highest_high = lookback["high"].max()
                        sl = highest_high * (1 + self.sl_margin)
                        tp = entry_price * (1 - self.tp_ratio)
                        risk_per_coin = sl - entry_price

                    # Position sizing: risk_amount / risk_per_coin
                    if risk_per_coin > 0:
                        quantity = risk_amount / risk_per_coin
                        # Limit position to available capital
                        max_quantity = capital / entry_price
                        quantity = min(quantity, max_quantity)
                    else:
                        quantity = capital * 0.01 / entry_price  # 1% of capital

                    # Initialize trailing stop
                    trailing_stop = sl
                    max_profit_in_trade = 0
                    max_drawdown_in_trade = 0

            else:
                # Exit logic
                hit_tp = False
                hit_sl = False
                exit_price = None
                reason = ""

                # Calculate current P&L
                if side == "buy":
                    current_pnl_pct = (current_price - entry_price) / entry_price * 100
                else:
                    current_pnl_pct = (entry_price - current_price) / entry_price * 100

                # Track max profit/drawdown in trade
                max_profit_in_trade = max(max_profit_in_trade, current_pnl_pct)
                max_drawdown_in_trade = min(max_drawdown_in_trade, current_pnl_pct)

                # Update trailing stop
                if self.use_trailing_stop and side == "buy":
                    if current_high > entry_price * (1 + self.trailing_stop_pct):
                        new_trailing = current_high * (1 - self.trailing_stop_pct)
                        trailing_stop = max(trailing_stop, new_trailing)
                elif self.use_trailing_stop and side == "sell":
                    if current_low < entry_price * (1 - self.trailing_stop_pct):
                        new_trailing = current_low * (1 + self.trailing_stop_pct)
                        trailing_stop = min(trailing_stop, new_trailing)

                # Check exits
                if side == "buy":
                    if current_high >= tp:
                        hit_tp = True
                        exit_price = tp
                        reason = "tp"
                    elif current_low <= trailing_stop:
                        hit_sl = True
                        exit_price = trailing_stop
                        reason = "trailing_sl" if trailing_stop > sl else "sl"
                elif side == "sell":
                    if current_low <= tp:
                        hit_tp = True
                        exit_price = tp
                        reason = "tp"
                    elif current_high >= trailing_stop:
                        hit_sl = True
                        exit_price = trailing_stop
                        reason = "trailing_sl" if trailing_stop < sl else "sl"

                # Timeout exit
                if not reason and (i - entry_index >= self.max_hold):
                    reason = "timeout"
                    exit_price = current_price

                # Execute exit
                if reason:
                    pnl = (exit_price - entry_price) * quantity
                    if side == "sell":
                        pnl = -pnl

                    pnl_pct = (pnl / (entry_price * quantity)) * 100

                    # Update capital
                    capital += pnl
                    peak_capital = max(peak_capital, capital)

                    # Calculate drawdown
                    drawdown = ((peak_capital - capital) / peak_capital) * 100
                    max_drawdown = max(max_drawdown, drawdown)

                    trades.append({
                        "entry": df.iloc[entry_index]["timestamp"],
                        "exit": current_candle["timestamp"],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "side": side,
                        "quantity": quantity,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "reason": reason,
                        "tp_level": tp,
                        "sl_level": sl,
                        "trailing_stop": trailing_stop if self.use_trailing_stop else None,
                        "max_profit": max_profit_in_trade,
                        "max_drawdown_in_trade": max_drawdown_in_trade,
                        "hold_time": i - entry_index,
                        "capital_after": capital
                    })

                    in_trade = False

        # Calculate statistics
        stats = self._calculate_statistics(trades, capital)

        return {
            'trades': trades,
            'statistics': stats,
            'initial_capital': self.initial_capital,
            'final_capital': capital,
            'max_drawdown': max_drawdown
        }

    def _calculate_statistics(self, trades: List[Dict], final_capital: float) -> Dict:
        """Calculate detailed backtest statistics"""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'winrate': 0,
                'total_return': 0,
                'total_return_pct': 0
            }

        total_trades = len(trades)
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(t['pnl'] for t in trades)
        total_return_pct = ((final_capital - self.initial_capital) / self.initial_capital) * 100

        avg_pnl = total_pnl / total_trades
        avg_win = sum(t['pnl'] for t in wins) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t['pnl'] for t in losses) / losing_trades if losing_trades > 0 else 0

        avg_win_pct = sum(t['pnl_pct'] for t in wins) / winning_trades if winning_trades > 0 else 0
        avg_loss_pct = sum(t['pnl_pct'] for t in losses) / losing_trades if losing_trades > 0 else 0

        # Profit factor
        total_win_amount = sum(t['pnl'] for t in wins)
        total_loss_amount = abs(sum(t['pnl'] for t in losses))
        profit_factor = total_win_amount / total_loss_amount if total_loss_amount > 0 else float('inf')

        # Expectancy
        expectancy = (winrate / 100 * avg_win) + ((1 - winrate / 100) * avg_loss)

        # Average hold time
        avg_hold_time = sum(t['hold_time'] for t in trades) / total_trades

        # Sharpe ratio (simplified)
        returns = [t['pnl_pct'] for t in trades]
        sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'winrate': winrate,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'avg_hold_time': avg_hold_time,
            'sharpe_ratio': sharpe_ratio,
            'best_trade': max(trades, key=lambda x: x['pnl']),
            'worst_trade': min(trades, key=lambda x: x['pnl']),
            'max_consecutive_wins': self._max_consecutive(wins, trades),
            'max_consecutive_losses': self._max_consecutive(losses, trades)
        }

    def _max_consecutive(self, target_trades: List, all_trades: List) -> int:
        """Calculate maximum consecutive wins or losses"""
        if not target_trades or not all_trades:
            return 0

        max_consecutive = 0
        current_consecutive = 0

        for trade in all_trades:
            if trade in target_trades:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def print_results(self, results: Dict):
        """Print formatted backtest results"""
        stats = results['statistics']

        print("\n" + "=" * 70)
        print("                    BACKTEST RESULTS")
        print("=" * 70)
        print(f"\nCAPITAL CAPITAL")
        print(f"   Initial: ${results['initial_capital']:,.2f}")
        print(f"   Final:   ${results['final_capital']:,.2f}")
        print(f"   Return:  {stats['total_return_pct']:+.2f}% (${stats['total_pnl']:+,.2f})")
        print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")

        print(f"\nTRADES TRADES")
        print(f"   Total: {stats['total_trades']}")
        print(f"   Wins:  {stats['winning_trades']} ({stats['winrate']:.2f}%)")
        print(f"   Losses: {stats['losing_trades']}")

        print(f"\nPERFORMANCE PERFORMANCE")
        print(f"   Avg Win:  ${stats['avg_win']:,.2f} ({stats['avg_win_pct']:+.2f}%)")
        print(f"   Avg Loss: ${stats['avg_loss']:,.2f} ({stats['avg_loss_pct']:+.2f}%)")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Expectancy: ${stats['expectancy']:,.2f}")
        print(f"   Sharpe Ratio: {stats['sharpe_ratio']:.2f}")
        print(f"   Avg Hold Time: {stats['avg_hold_time']:.1f} candles")

        print(f"\nBEST/WORST BEST/WORST")
        print(f"   Best Trade:  ${stats['best_trade']['pnl']:+,.2f} ({stats['best_trade']['pnl_pct']:+.2f}%)")
        print(f"   Worst Trade: ${stats['worst_trade']['pnl']:+,.2f} ({stats['worst_trade']['pnl_pct']:+.2f}%)")

        print(f"\nSTREAKS STREAKS")
        print(f"   Max Consecutive Wins: {stats['max_consecutive_wins']}")
        print(f"   Max Consecutive Losses: {stats['max_consecutive_losses']}")

        print("\n" + "=" * 70)
