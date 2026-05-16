"""
Trading Bot - With Position Tracking
Monitors entries AND exits, sends Telegram alerts for both
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import schedule
import json
import signal
from datetime import datetime
import pandas as pd

from core.data_sources.market_data import get_ohlcv
from core.strategies.adx_trend_strategy import (
    add_indicators, adx_trend_strategy, adx_trend_live,
    get_tp_sl_prices, check_exit_conditions, get_strategy_info,
    calculate_trailing_sl, get_current_sl_level, TRAILING_SL_STEPS
)
from telegram_bot import send_telegram_message
from core.database import TradingDatabase

# Configuration
PAIR = 'BTCUSDT'
INTERVAL = '4h'
CHECK_INTERVAL_MINUTES = 15
LIMIT = 200

POSITION_FILE = 'current_position.json'
BINANCE_FEE = 0.001  # 0.1% Binance fee per side

class PositionTracker:
    """Track current open position"""

    def __init__(self):
        self.position = None
        self.load_position()

    def load_position(self):
        """Load position from file"""
        try:
            with open(POSITION_FILE, 'r') as f:
                self.position = json.load(f)
                print(f"[LOAD] Position loaded: {self.position['direction']} at ${self.position['entry_price']}")
        except FileNotFoundError:
            self.position = None
            print("[INFO] No active position")
        except Exception as e:
            print(f"[ERROR] Failed to load position: {e}")
            self.position = None

    def save_position(self):
        """Save position to file"""
        try:
            with open(POSITION_FILE, 'w') as f:
                json.dump(self.position, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to save position: {e}")

    def open_position(self, signal, price, timestamp):
        """Open a new position"""
        tp, sl = get_tp_sl_prices(price, signal)

        self.position = {
            'direction': signal,
            'entry_price': price,
            'entry_time': timestamp.isoformat(),
            'tp_price': tp,
            'sl_price': sl,
            'initial_sl_price': sl,
            'best_price': price,
            'current_sl_level': 'initial',
            'candles_held': 0
        }
        self.save_position()

        print(f"\n{'='*100}")
        print(f"📌 POSITION OPENED")
        print(f"{'='*100}")
        print(f"Direction: {signal}")
        print(f"Entry: ${price:,.2f}")
        print(f"TP: ${tp:,.2f}")
        print(f"SL: ${sl:,.2f} (initial)")
        print(f"Trailing SL: Active - Steps at 0.5%, 1%, 1.5%, 2%")
        print(f"{'='*100}\n")

        return self.position

    def update_trailing_sl(self, current_high, current_low):
        """Update best_price + trailing SL. Returns list of crossed steps (may be empty)."""
        if not self.position:
            return []

        direction = self.position['direction']
        entry_price = self.position['entry_price']
        current_sl = self.position['sl_price']

        if direction == 'BUY':
            if current_high > self.position['best_price']:
                self.position['best_price'] = current_high
        else:
            if current_low < self.position['best_price']:
                self.position['best_price'] = current_low

        new_sl, triggered_steps = calculate_trailing_sl(
            entry_price, self.position['best_price'], direction, current_sl
        )

        if triggered_steps and new_sl != current_sl:
            self.position['sl_price'] = new_sl
            last_sl_pct = triggered_steps[-1][1]
            if last_sl_pct == 0:
                self.position['current_sl_level'] = 'break_even'
            else:
                self.position['current_sl_level'] = f"{last_sl_pct}%"
            self.save_position()

        return triggered_steps

    def close_position(self, exit_price, exit_reason):
        """Close current position. Includes Binance round-trip fees in PnL."""
        if not self.position:
            return None

        entry_price = self.position['entry_price']
        direction = self.position['direction']

        if direction == 'BUY':
            gross_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            gross_pct = ((entry_price - exit_price) / entry_price) * 100
        fee_pct = BINANCE_FEE * 100 * 2
        pnl_pct = gross_pct - fee_pct

        gross_per_unit = (exit_price - entry_price) if direction == 'BUY' else (entry_price - exit_price)
        fees_per_unit = (entry_price + exit_price) * BINANCE_FEE
        pnl_usd = gross_per_unit - fees_per_unit

        try:
            entry_dt = datetime.fromisoformat(self.position['entry_time'])
            duration_hours = (datetime.now() - entry_dt).total_seconds() / 3600
        except Exception:
            duration_hours = self.position['candles_held'] * 4

        result = {
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'gross_pct': gross_pct,
            'fee_pct': fee_pct,
            'pnl_usd': pnl_usd,
            'exit_reason': exit_reason,
            'candles_held': self.position['candles_held'],
            'duration_hours': duration_hours,
        }

        print(f"\n{'='*100}")
        print(f"POSITION CLOSED")
        print(f"{'='*100}")
        print(f"Direction: {direction}")
        print(f"Entry: ${entry_price:,.2f}")
        print(f"Exit: ${exit_price:,.2f}")
        print(f"PnL: {pnl_pct:+.2f}% (gross {gross_pct:+.2f}%, fees -{fee_pct:.2f}%)")
        print(f"USD/unit: ${pnl_usd:+,.2f}")
        print(f"Reason: {exit_reason}")
        print(f"Duration: {duration_hours:.1f}h ({self.position['candles_held']} closed candles)")
        print(f"{'='*100}\n")

        # Clear position
        self.position = None
        try:
            import os
            os.remove(POSITION_FILE)
        except:
            pass

        return result

    def has_position(self):
        """Check if there's an active position"""
        return self.position is not None

    def increment_candles(self):
        """Increment candles held counter"""
        if self.position:
            self.position['candles_held'] += 1
            self.save_position()


class TradingBotWithTracking:
    """Bot that tracks both entries and exits"""

    def __init__(self):
        self.pair = PAIR
        self.interval = INTERVAL
        self.db = TradingDatabase()
        self.tracker = PositionTracker()
        self.last_candle_time = None
        self.last_candle_timestamp = None  # Track last candle for proper counting

        strategy_info = get_strategy_info()
        print("\n" + "="*100)
        print("BOT WITH POSITION TRACKING - STARTING")
        print("="*100)
        print(f"Strategy: {strategy_info['name']} ({strategy_info['version']})")
        print(f"Pair: {self.pair}")
        print(f"Timeframe: {self.interval}")
        print(f"Check Interval: Every {CHECK_INTERVAL_MINUTES} minutes")
        print(f"\nFeatures:")
        print(f"  ✅ Entry signal detection")
        print(f"  ✅ Exit signal detection (TP/SL/Signal Exit/Max Hold)")
        print(f"  ✅ Telegram notifications for both")
        print(f"\nBacktest Performance:")
        print(f"  Annual Return: {strategy_info['backtest_stats']['annual_return']}%")
        print(f"  Max Drawdown: {strategy_info['backtest_stats']['max_drawdown']}%")
        print(f"  Win Rate: {strategy_info['backtest_stats']['win_rate']}%")
        print("="*100 + "\n")

        # Display current position if exists
        if self.tracker.has_position():
            pos = self.tracker.position
            print("[!] EXISTING POSITION DETECTED")
            print("="*100)
            print(f"Direction: {pos['direction']}")
            print(f"Entry Price: ${pos['entry_price']:,.2f}")
            print(f"Entry Time: {pos['entry_time']}")
            print(f"TP: ${pos['tp_price']:,.2f} (+4.0%)")
            sl_level = pos.get('current_sl_level', 'initial')
            if sl_level == 'break_even':
                sl_desc = "Break Even"
            elif sl_level == 'initial':
                sl_desc = "-0.7% (initial)"
            else:
                sl_desc = f"+{sl_level}"
            print(f"SL: ${pos['sl_price']:,.2f} ({sl_desc})")
            print(f"Best Price: ${pos.get('best_price', pos['entry_price']):,.2f}")
            print(f"Candles Held: {pos['candles_held']}")
            print("="*100)
            print("Bot will continue monitoring this position for exit conditions...")
            print("="*100 + "\n")
        else:
            print("[OK] No open position - Bot will scan for entry signals")
            print("="*100 + "\n")

        # Send startup notification
        if self.tracker.has_position():
            pos = self.tracker.position
            entry_time_str = pos['entry_time'][:16] if isinstance(pos['entry_time'], str) else str(pos['entry_time'])

            msg = f"""
🤖 BOT STARTED - Position Tracking Enabled

Pair: {self.pair}
Timeframe: {self.interval}

⚠️ EXISTING POSITION:
Direction: {pos['direction']}
Entry: ${pos['entry_price']:,.2f}
TP: ${pos['tp_price']:,.2f} (+4.0%)
SL: ${pos['sl_price']:,.2f} (-0.7%)
Opened: {entry_time_str}
Candles held: {pos['candles_held']}

Bot will monitor for exit conditions...
            """
        else:
            msg = f"""
🤖 BOT STARTED - Position Tracking Enabled

Pair: {self.pair}
Timeframe: {self.interval}
Status: NO POSITION

Features:
✅ Entry detection
✅ Exit detection (TP/SL/Signal)
✅ Real-time alerts

Bot monitoring 24/7...
            """
        send_telegram_message(msg)

    def check_exit_signal(self, df):
        """Exit check FIRST with pre-candle SL. Trailing notifs sent only if no exit."""
        if not self.tracker.has_position():
            return

        current_candle = df.iloc[-1]
        position = self.tracker.position
        sl_before_update = position['sl_price']
        best_before_update = position['best_price']

        # 1) Pessimistic exit check using SL valid BEFORE this candle.
        should_exit, reason, exit_price = check_exit_conditions(
            current_candle,
            position['entry_price'],
            position['direction'],
            position['candles_held'],
            best_price=best_before_update,
            current_sl=sl_before_update,
        )

        # 2) Compute trailing steps crossed by this candle (also updates in-memory SL).
        triggered_steps = self.tracker.update_trailing_sl(
            current_candle['high'], current_candle['low']
        )
        best_after = self.tracker.position['best_price']

        if should_exit:
            # Suppress trailing notifs that would contradict the exit.
            wick_warning = ""
            if triggered_steps and reason in ('SL', 'Trailing SL'):
                top = triggered_steps[-1]
                wick_warning = (
                    f"\n[!] Favorable wick to ${best_after:,.2f} (+{top[0]}% gain) "
                    f"in the same candle, but exit applied pessimistic prior SL."
                )

            result = self.tracker.close_position(exit_price, reason)
            if result:
                emoji = "✅" if result['pnl_pct'] > 0 else "❌"
                color = "GREEN" if result['pnl_pct'] > 0 else "RED"
                msg = (
                    f"\n{emoji} EXIT SIGNAL - {color}\n\n"
                    f"Pair: {self.pair}\n"
                    f"Direction: {result['direction']}\n\n"
                    f"Entry: ${result['entry_price']:,.2f}\n"
                    f"Exit: ${result['exit_price']:,.2f}\n\n"
                    f"PnL: {result['pnl_pct']:+.2f}% (gross {result['gross_pct']:+.2f}%, fees -{result['fee_pct']:.2f}%)\n"
                    f"USD/unit: ${result['pnl_usd']:+,.2f}\n\n"
                    f"Reason: {reason}\n"
                    f"Duration: {result['duration_hours']:.1f}h ({result['candles_held']} closed candles){wick_warning}\n\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                )
                send_telegram_message(msg)

                self.db.add_signal({
                    'pair': self.pair,
                    'signal': 'EXIT',
                    'strength': reason,
                    'strategy': 'ADX_TREND_RANK8',
                    'price': exit_price,
                    'composite_score': 0.0,
                    'technical_score': 0.0,
                    'sentiment_score': 0.0,
                    'onchain_score': 0.0,
                    'volume_score': 0.0,
                    'factors': {
                        'exit_reason': reason,
                        'pnl_pct': result['pnl_pct'],
                        'gross_pct': result['gross_pct'],
                        'fee_pct': result['fee_pct'],
                        'entry_price': result['entry_price'],
                        'duration_hours': result['duration_hours'],
                    }
                })
            return

        # No exit: send a notif for EACH trailing step crossed (no skipping intermediate steps).
        entry_price = position['entry_price']
        direction = position['direction']
        for step in triggered_steps:
            gain_pct, new_sl_pct = step
            if direction == 'BUY':
                sl_price_at_step = entry_price * (1 + new_sl_pct / 100)
            else:
                sl_price_at_step = entry_price * (1 - new_sl_pct / 100)
            sl_desc = "Break Even" if new_sl_pct == 0 else f"+{new_sl_pct}%"
            emoji = "🔒" if new_sl_pct == 0 else "📈"
            msg = (
                f"\n{emoji} TRAILING SL UPDATED\n\n"
                f"Pair: {self.pair}\n"
                f"Direction: {direction}\n\n"
                f"Trigger: +{gain_pct}% gain reached\n"
                f"New SL: ${sl_price_at_step:,.2f} ({sl_desc})\n\n"
                f"Entry: ${entry_price:,.2f}\n"
                f"Best: ${best_after:,.2f}\n"
                f"TP: ${position['tp_price']:,.2f}\n\n"
                f"Trade now protected at {sl_desc}!\n\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )
            send_telegram_message(msg)
            print(f"[TRAILING SL] Moved to {sl_desc} (${sl_price_at_step:,.2f})")


    def check_entry_signal(self, df):
        """Check for new entry signal"""
        if self.tracker.has_position():
            return  # Already in position

        signal, candle = adx_trend_strategy(df)

        if signal and candle is not None:
            signal_time = pd.Timestamp(candle['timestamp'], unit='ms')

            # Avoid duplicate on same candle
            if self.last_candle_time and signal_time == self.last_candle_time:
                return

            self.last_candle_time = signal_time

            # Open position
            price = candle['close']
            self.tracker.open_position(signal, price, signal_time)

            # Get details
            adx = candle.get('adx', 0)
            plus_di = candle.get('plus_di', 0)
            minus_di = candle.get('minus_di', 0)
            volume_ratio = candle.get('volume_ratio', 0)

            # Calculate TP/SL
            tp_price, sl_price = get_tp_sl_prices(price, signal)

            emoji = "🟢" if signal == 'BUY' else "🔴"

            # Send entry notification
            msg = f"""
{emoji} ENTRY SIGNAL - {signal}

Pair: {self.pair}
Price: ${price:,.2f}

Entry: ${price:,.2f}
TP: ${tp_price:,.2f} (+4.0%)
SL: ${sl_price:,.2f} (-0.7%)

Trailing SL Steps:
• +0.5% → BE
• +1% → +0.5%
• +1.5% → +1%
• +2% → +1.5%

Indicators:
• ADX: {adx:.1f}
• DI+: {plus_di:.1f} | DI-: {minus_di:.1f}
• Volume: {volume_ratio:.1f}x

⚠️ Position opened - Monitoring for exit

Time: {signal_time.strftime('%Y-%m-%d %H:%M')}
            """
            send_telegram_message(msg)

            # Save to database
            self.db.add_signal({
                'pair': self.pair,
                'signal': signal,
                'strength': 'STRONG',
                'strategy': 'ADX_TREND_RANK8',
                'price': price,
                'composite_score': 0.85,
                'technical_score': 0.85,
                'sentiment_score': 0.5,
                'onchain_score': 0.5,
                'volume_score': volume_ratio / 2.0,
                'factors': {
                    'adx': adx,
                    'plus_di': plus_di,
                    'minus_di': minus_di,
                    'volume_ratio': volume_ratio
                }
            })

    def check_signals(self):
        """Main check loop"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{timestamp}] Checking signals...")

            # Fetch data
            df = get_ohlcv(self.pair, interval=self.interval, limit_total=LIMIT)

            if df is None or len(df) < 55:
                print("[ERROR] Failed to fetch data")
                return

            # Add indicators
            df = add_indicators(df)

            # Check if in position
            if self.tracker.has_position():
                pos = self.tracker.position
                sl_level = pos.get('current_sl_level', 'initial')
                if sl_level == 'break_even':
                    sl_desc = "BE"
                elif sl_level == 'initial':
                    sl_desc = "-0.7%"
                else:
                    sl_desc = f"+{sl_level}"
                print(f"[POSITION] {pos['direction']} at ${pos['entry_price']:,.2f}")
                print(f"  Best: ${pos.get('best_price', pos['entry_price']):,.2f} | SL: ${pos['sl_price']:,.2f} ({sl_desc})")
                print(f"  Candles held: {pos['candles_held']}")

                # Increment candles ONLY when a new 4h candle closes
                current_candle_timestamp = df.iloc[-2]['timestamp']  # Last closed candle (already int64)

                if self.last_candle_timestamp is None:
                    # First check after bot start
                    self.last_candle_timestamp = current_candle_timestamp
                elif current_candle_timestamp > self.last_candle_timestamp:
                    # New candle has closed
                    self.tracker.increment_candles()
                    self.last_candle_timestamp = current_candle_timestamp
                    print(f"  [UPDATE] New candle closed, candles_held incremented to {self.tracker.position['candles_held']}")

                # Check exit conditions
                self.check_exit_signal(df)
            else:
                # Check for entry signal
                print("[NO POSITION] Scanning for entry...")
                self.check_entry_signal(df)

                # Also check live (forming) signal
                live_signal, live_candle = adx_trend_live(df)
                if live_signal and live_candle is not None:
                    print(f"[WATCH] Potential {live_signal} forming")

        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()

            # Send error notification
            msg = f"⚠️ BOT ERROR\n\n{str(e)}"
            send_telegram_message(msg)

    def shutdown(self, signum=None, frame=None):
        """Handle shutdown gracefully"""
        print("\n\n[SHUTDOWN] Bot stopped")

        status = "with OPEN position" if self.tracker.has_position() else "no position"
        msg = f"🛑 BOT STOPPED\n\nBot stopped {status}"
        send_telegram_message(msg)
        sys.exit(0)

    def run(self):
        """Main execution loop"""
        print(f"[READY] Bot running with position tracking...")
        print("[INFO] Press Ctrl+C to stop\n")

        # Handle SIGTERM (from systemd) and SIGINT (Ctrl+C)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        # Schedule checks
        schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(self.check_signals)

        # First check
        self.check_signals()

        # Loop
        while True:
            schedule.run_pending()
            time.sleep(10)


def main():
    bot = TradingBotWithTracking()
    bot.run()


if __name__ == "__main__":
    main()
