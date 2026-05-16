"""
FINAL OPTIMIZED STRATEGY - RANK 8 v2 + Trailing SL - CORRECTED VERSION
Full metrics edition: Sharpe, Sortino, Calmar, Recovery Factor,
Volatility, Max DD Duration, Average DD, Worst Monthly Loss,
Max Consecutive Losses, Expectancy, Best/Worst Trade, Time in Market,
Turnover, Regime Sharpe, Alpha/Beta vs BTC, Fees included.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from core.data_sources.market_data import get_ohlcv
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PAIR = "BTCUSDT"
INTERVAL = "4h"
LIMIT = 20000
BINANCE_FEE = 0.001
SLIPPAGE_PCT = 0.0005  # 5 bps per side
TOTAL_FRICTION = BINANCE_FEE + SLIPPAGE_PCT
INITIAL_CAPITAL = 10_000
ADX_THRESHOLD = 30
TP_PCT = 4.0
SL_PCT = 0.7
MAX_HOLD = 20
VOLUME_THRESHOLD = 1.8
CANDLES_PER_YEAR = 365.25 * 6
TRADING_DAYS_PER_YEAR = 365.25
TRAILING_SL_STEPS = [(0.5,0.0),(1.0,0.5),(1.5,1.0),(2.0,1.5)]
BULL_THRESHOLD = 0.20
BEAR_THRESHOLD = -0.20

# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def calculate_atr(df, period=14):
    hl  = df["high"] - df["low"]
    hc  = (df["high"] - df["close"].shift()).abs()
    lc  = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calculate_adx(df, period=14):
    hd  =  df["high"].diff()
    ld  = -df["low"].diff()
    pdm = hd.where((hd > ld) & (hd > 0), 0)
    mdm = ld.where((ld > hd) & (ld > 0), 0)
    atr = calculate_atr(df, period)
    pdi = 100 * (pdm.rolling(period).mean() / atr)
    mdi = 100 * (mdm.rolling(period).mean() / atr)
    dx  = 100 * (pdi - mdi).abs() / (pdi + mdi)
    adx = dx.rolling(period).mean()
    df  = df.copy()
    df["adx"], df["plus_di"], df["minus_di"] = adx, pdi, mdi
    return df


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------

def backtest(df, initial_capital=INITIAL_CAPITAL):
    df = calculate_adx(df).copy()
    df["ema_20"]       = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_50"]       = df["close"].ewm(span=50, adjust=False).mean()
    df["volume_ma"]    = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]

    trades, equity_curve = [], []
    capital      = initial_capital
    in_trade     = False
    peak_capital = initial_capital
    max_drawdown = 0.0
    direction = entry_price = entry_i = entry_time = None
    tp_price  = sl_price = best_price = quantity = None

    for i in range(55, len(df) - 1):
        current = df.iloc[i]
        ts      = current["timestamp"]

        dd_pct = (peak_capital - capital) / peak_capital * 100 if peak_capital > 0 else 0.0
        equity_curve.append({"timestamp": ts, "capital": capital, "drawdown": dd_pct})
        if capital > peak_capital:
            peak_capital = capital
        cur_dd = (peak_capital - capital) / peak_capital * 100 if peak_capital > 0 else 0.0
        if cur_dd > max_drawdown:
            max_drawdown = cur_dd

        if not in_trade:
            prev    = df.iloc[i - 1]
            bullish = (
                prev.get("adx", 0)          > ADX_THRESHOLD and
                prev.get("plus_di", 0)      > prev.get("minus_di", 0) and
                prev["close"]               > prev["ema_20"] and
                prev["ema_20"]              > prev["ema_50"] and
                prev.get("volume_ratio", 1) > VOLUME_THRESHOLD
            )
            bearish = (
                prev.get("adx", 0)          > ADX_THRESHOLD and
                prev.get("minus_di", 0)     > prev.get("plus_di", 0) and
                prev["close"]               < prev["ema_20"] and
                prev["ema_20"]              < prev["ema_50"] and
                prev.get("volume_ratio", 1) > VOLUME_THRESHOLD
            )
            if bullish or bearish:
                in_trade    = True
                direction   = "long" if bullish else "short"
                entry_price = prev["close"]
                entry_i     = i
                entry_time  = prev["timestamp"]
                quantity    = (capital * 0.98) / entry_price
                capital    -= entry_price * quantity * TOTAL_FRICTION
                if direction == "long":
                    tp_price = entry_price * (1 + TP_PCT / 100)
                    sl_price = entry_price * (1 - SL_PCT / 100)
                else:
                    tp_price = entry_price * (1 - TP_PCT / 100)
                    sl_price = entry_price * (1 + SL_PCT / 100)
                best_price = entry_price
        else:
            prev_c     = df.iloc[i - 1]
            exit_price = exit_reason = None
            init_sl    = (entry_price * (1 - SL_PCT/100) if direction == "long"
                          else entry_price * (1 + SL_PCT/100))

            if direction == "long":
                if current["high"] > best_price: best_price = current["high"]
                gain_pct = (best_price - entry_price) / entry_price * 100
            else:
                if current["low"] < best_price: best_price = current["low"]
                gain_pct = (entry_price - best_price) / entry_price * 100

            for thr, nsl_pct in TRAILING_SL_STEPS:
                if gain_pct >= thr:
                    if direction == "long":
                        p = entry_price * (1 + nsl_pct/100)
                        if p > sl_price: sl_price = p
                    else:
                        p = entry_price * (1 - nsl_pct/100)
                        if p < sl_price: sl_price = p

            if direction == "long":
                if current["high"] >= tp_price:
                    exit_price, exit_reason = tp_price, "TP"
                elif current["low"] <= sl_price:
                    exit_price  = sl_price
                    exit_reason = "Trailing SL" if sl_price > init_sl else "SL"
                elif prev_c.get("adx", 0) < 20 or prev_c["close"] < prev_c["ema_20"]:
                    exit_price, exit_reason = current["open"], "Signal Exit"
            else:
                if current["low"] <= tp_price:
                    exit_price, exit_reason = tp_price, "TP"
                elif current["high"] >= sl_price:
                    exit_price  = sl_price
                    exit_reason = "Trailing SL" if sl_price < init_sl else "SL"
                elif prev_c.get("adx", 0) < 20 or prev_c["close"] > prev_c["ema_20"]:
                    exit_price, exit_reason = current["open"], "Signal Exit"

            if exit_price is None and (i - entry_i) >= MAX_HOLD:
                exit_price, exit_reason = current["close"], "Max Hold"

            if exit_price is not None:
                pg = ((exit_price - entry_price) if direction == "long"
                      else (entry_price - exit_price)) * quantity
                pn = pg - exit_price * quantity * TOTAL_FRICTION
                capital += pn
                trades.append({
                    "entry_time":   entry_time,
                    "exit_time":    current["timestamp"],
                    "direction":    direction,
                    "entry_price":  entry_price,
                    "exit_price":   exit_price,
                    "quantity":     quantity,
                    "pnl":          pn,
                    "pnl_pct":      pn / (entry_price * quantity) * 100,
                    "exit_reason":  exit_reason,
                    "hold_candles": i - entry_i,
                })
                in_trade = False

    return trades, capital, max_drawdown, pd.DataFrame(equity_curve)


# ===========================================================================
# Metrics, Buy & Hold baseline, HTML report, runner
# Added: Sharpe/Sortino/Calmar/Recovery; Vol/MaxDD-Duration/AvgDD/WorstMonth/MaxConsecLosses;
#        Expectancy/Best-Worst/TimeInMarket/Turnover; Regime Sharpe; Alpha/Beta vs B&H BTC.
# ===========================================================================
import math

def compute_buy_hold(df, initial_capital=INITIAL_CAPITAL):
    """Returns DataFrame with timestamp, capital (B&H BTC starting at initial_capital)."""
    sub = df.iloc[55:].reset_index(drop=True).copy()
    base = sub["close"].iloc[0]
    sub["capital"] = (sub["close"] / base) * initial_capital
    return sub[["timestamp", "capital"]]


def classify_regime(df, lookback_candles=540):
    """Classify each candle as bull/bear/sideways from rolling BTC return."""
    roll_ret = df["close"].pct_change(lookback_candles)
    regimes = pd.Series("sideways", index=df.index, dtype=object)
    regimes[roll_ret > BULL_THRESHOLD] = "bull"
    regimes[roll_ret < BEAR_THRESHOLD] = "bear"
    return regimes


def _annualized_sharpe(returns, periods_per_year):
    r = pd.Series(returns).dropna()
    if len(r) < 2:
        return 0.0
    s = r.std(ddof=1)
    return float((r.mean() / s) * math.sqrt(periods_per_year)) if s > 0 else 0.0


def compute_metrics(trades, capital, max_drawdown, equity_df, df,
                    initial_capital=INITIAL_CAPITAL):
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame(
        columns=["pnl", "pnl_pct", "hold_candles", "entry_time", "exit_time"]
    )
    eq = equity_df["capital"].astype(float).reset_index(drop=True)
    ts = pd.to_datetime(equity_df["timestamp"]).reset_index(drop=True)
    ret = eq.pct_change().dropna()

    ann = CANDLES_PER_YEAR
    years = len(ret) / ann if ann else 0
    total_return = capital / initial_capital - 1
    cagr = (capital / initial_capital) ** (1 / years) - 1 if years > 0 else 0.0

    # --- Risk-adjusted ---
    sharpe = _annualized_sharpe(ret, ann)
    downside = ret[ret < 0]
    dstd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    sortino = float((ret.mean() / dstd) * math.sqrt(ann)) if dstd > 0 else 0.0
    calmar = (cagr / (max_drawdown / 100)) if max_drawdown > 0 else 0.0
    peak = eq.cummax()
    dd_abs = float((peak - eq).max()) if len(eq) else 0.0
    net_profit = capital - initial_capital
    recovery_factor = net_profit / dd_abs if dd_abs > 0 else 0.0

    # --- Risk ---
    vol_ann = float(ret.std(ddof=1) * math.sqrt(ann)) if len(ret) > 1 else 0.0

    is_dd = eq < peak
    dd_periods, cur = [], None
    for i, v in enumerate(is_dd):
        if v and cur is None:
            cur = i
        elif (not v) and cur is not None:
            dd_periods.append(i - cur)
            cur = None
    if cur is not None:
        dd_periods.append(len(is_dd) - cur)
    max_dd_dur_candles = max(dd_periods) if dd_periods else 0
    max_dd_dur_days = max_dd_dur_candles / 6.0

    dd_pcts = ((peak - eq) / peak * 100).replace([float("inf"), -float("inf")], 0).fillna(0)
    pos_dd = dd_pcts[dd_pcts > 0]
    avg_dd = float(pos_dd.mean()) if len(pos_dd) else 0.0

    eq_ts = pd.DataFrame({"capital": eq.values}, index=pd.to_datetime(ts.values))
    monthly_last = eq_ts["capital"].resample("ME").last().dropna()
    monthly_ret = monthly_last.pct_change().dropna()
    worst_monthly = float(monthly_ret.min() * 100) if len(monthly_ret) else 0.0

    max_consec_losses, cur_streak = 0, 0
    if "pnl" in trades_df:
        for p in trades_df["pnl"]:
            if p < 0:
                cur_streak += 1
                max_consec_losses = max(max_consec_losses, cur_streak)
            else:
                cur_streak = 0

    # --- Trade stats ---
    n_trades = len(trades_df)
    wins = trades_df[trades_df["pnl"] > 0] if n_trades else trades_df
    losses = trades_df[trades_df["pnl"] <= 0] if n_trades else trades_df
    win_rate = len(wins) / n_trades if n_trades else 0.0
    avg_win = float(wins["pnl_pct"].mean()) if len(wins) else 0.0
    avg_loss = float(losses["pnl_pct"].mean()) if len(losses) else 0.0
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss
    best_trade = float(trades_df["pnl_pct"].max()) if n_trades else 0.0
    worst_trade = float(trades_df["pnl_pct"].min()) if n_trades else 0.0
    total_hold = float(trades_df["hold_candles"].sum()) if n_trades else 0.0
    time_in_market = (total_hold / max(len(df) - 55, 1)) * 100
    turnover = n_trades / years if years > 0 else 0.0

    # --- Robustesse ---
    regimes = classify_regime(df).iloc[55:].reset_index(drop=True)
    # Align: equity_df rows correspond to i in range(55, len(df)-1) -> regimes index 0..len-2-55
    n_align = min(len(regimes), len(eq))
    reg_aligned = regimes.iloc[:n_align].reset_index(drop=True)
    ret_aligned = pd.Series(eq.values[:n_align]).pct_change()
    by_regime = {}
    for label in ["bull", "bear", "sideways"]:
        mask = (reg_aligned == label).values
        r_sub = ret_aligned[mask].dropna()
        by_regime[label] = {
            "sharpe": _annualized_sharpe(r_sub, ann),
            "n_periods": int(mask.sum()),
            "pct_of_time": float(mask.mean() * 100),
        }

    # Alpha/Beta vs Buy & Hold BTC
    bh = compute_buy_hold(df, initial_capital)
    bh_ret = bh["capital"].pct_change().dropna().reset_index(drop=True)
    strat_ret = pd.Series(eq.values).pct_change().dropna().reset_index(drop=True)
    n = min(len(bh_ret), len(strat_ret))
    if n > 2:
        x, y = bh_ret.iloc[:n].values, strat_ret.iloc[:n].values
        var_x = x.var(ddof=1)
        beta = float(((x - x.mean()) * (y - y.mean())).sum() / (var_x * (n - 1))) if var_x > 0 else 0.0
        alpha_periodic = float(y.mean() - beta * x.mean())
        alpha_ann = alpha_periodic * ann
    else:
        beta, alpha_ann = 0.0, 0.0

    bh_final = float(bh["capital"].iloc[-1]) if len(bh) else initial_capital
    bh_return_pct = (bh_final / initial_capital - 1) * 100

    return {
        "years": years,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "final_capital": capital,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "recovery_factor": recovery_factor,
        "volatility_ann_pct": vol_ann * 100,
        "max_drawdown_pct": max_drawdown,
        "max_dd_duration_days": max_dd_dur_days,
        "max_dd_duration_candles": max_dd_dur_candles,
        "avg_drawdown_pct": avg_dd,
        "worst_monthly_loss_pct": worst_monthly,
        "max_consecutive_losses": max_consec_losses,
        "total_trades": n_trades,
        "win_rate_pct": win_rate * 100,
        "expectancy_pct": expectancy,
        "best_trade_pct": best_trade,
        "worst_trade_pct": worst_trade,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "time_in_market_pct": time_in_market,
        "turnover_per_year": turnover,
        "regime_sharpe": by_regime,
        "alpha_annualized_pct": alpha_ann * 100,
        "beta": beta,
        "buy_hold_return_pct": bh_return_pct,
        "fees_pct_per_side": BINANCE_FEE * 100,
        "slippage_pct_per_side": SLIPPAGE_PCT * 100,
    }


def _fmt(x, dp=2, suffix=""):
    try:
        return f"{x:,.{dp}f}{suffix}"
    except Exception:
        return str(x)


def generate_html(metrics, equity_df, trades, df, output_path):
    bh = compute_buy_hold(df)
    eq_ts = pd.to_datetime(equity_df["timestamp"])
    peak = equity_df["capital"].astype(float).cummax()
    dd = (peak - equity_df["capital"]) / peak * 100

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=("Equity Curve (Strategy vs Buy & Hold BTC)", "Drawdown (%)"),
    )
    fig.add_trace(go.Scatter(x=eq_ts, y=equity_df["capital"], name="Strategy",
                             line=dict(color="#16a34a", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=pd.to_datetime(bh["timestamp"]), y=bh["capital"],
                             name="Buy & Hold BTC",
                             line=dict(color="#9ca3af", width=1, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=eq_ts, y=-dd, name="Drawdown",
                             fill="tozeroy", line=dict(color="#dc2626", width=1)),
                  row=2, col=1)
    fig.update_layout(height=700, template="plotly_white",
                      title="Final Strategy RANK 8 - Backtest Report",
                      legend=dict(orientation="h", y=1.05))
    chart_html = fig.to_html(include_plotlyjs="cdn", full_html=False)

    m = metrics
    rg = m["regime_sharpe"]

    def row(label, value, hint=""):
        return f'<tr><td>{label}</td><td class="v">{value}</td><td class="hint">{hint}</td></tr>'

    sections = f"""
    <h2>Risk-adjusted returns</h2>
    <table>
      {row("Sharpe Ratio (annualised)", _fmt(m["sharpe"], 2))}
      {row("Sortino Ratio (annualised)", _fmt(m["sortino"], 2))}
      {row("Calmar Ratio", _fmt(m["calmar"], 2), "CAGR / MaxDD")}
      {row("Recovery Factor", _fmt(m["recovery_factor"], 2), "Net profit / Max DD ($)")}
    </table>

    <h2>Risk</h2>
    <table>
      {row("Volatility (annualised)", _fmt(m["volatility_ann_pct"], 2, "%"))}
      {row("Max Drawdown", _fmt(m["max_drawdown_pct"], 2, "%"))}
      {row("Max DD Duration", f'{_fmt(m["max_dd_duration_days"], 1)} days ({m["max_dd_duration_candles"]} candles)')}
      {row("Average Drawdown", _fmt(m["avg_drawdown_pct"], 2, "%"))}
      {row("Worst Monthly Loss", _fmt(m["worst_monthly_loss_pct"], 2, "%"))}
      {row("Max Consecutive Losses", m["max_consecutive_losses"])}
    </table>

    <h2>Trade statistics</h2>
    <table>
      {row("Total Trades", m["total_trades"])}
      {row("Win Rate", _fmt(m["win_rate_pct"], 1, "%"))}
      {row("Expectancy / Trade", _fmt(m["expectancy_pct"], 3, "%"))}
      {row("Best Trade", _fmt(m["best_trade_pct"], 2, "%"))}
      {row("Worst Trade", _fmt(m["worst_trade_pct"], 2, "%"))}
      {row("Avg Win / Avg Loss", f'{_fmt(m["avg_win_pct"], 2, "%")} / {_fmt(m["avg_loss_pct"], 2, "%")}')}
      {row("Time in Market", _fmt(m["time_in_market_pct"], 1, "%"))}
      {row("Turnover", _fmt(m["turnover_per_year"], 1, " trades/year"))}
    </table>

    <h2>Robustness</h2>
    <table>
      {row("Sharpe (Bull regime)", f'{_fmt(rg["bull"]["sharpe"], 2)}', f'{_fmt(rg["bull"]["pct_of_time"], 1, "%")} of time')}
      {row("Sharpe (Bear regime)", f'{_fmt(rg["bear"]["sharpe"], 2)}', f'{_fmt(rg["bear"]["pct_of_time"], 1, "%")} of time')}
      {row("Sharpe (Sideways)", f'{_fmt(rg["sideways"]["sharpe"], 2)}', f'{_fmt(rg["sideways"]["pct_of_time"], 1, "%")} of time')}
      {row("Alpha vs B&amp;H BTC (annualised)", _fmt(m["alpha_annualized_pct"], 2, "%"))}
      {row("Beta vs B&amp;H BTC", _fmt(m["beta"], 3))}
      {row("Buy &amp; Hold BTC return (period)", _fmt(m["buy_hold_return_pct"], 2, "%"))}
      {row("Fees included", f'{_fmt(m["fees_pct_per_side"], 2, "%")} per side (Binance)')}
      {row("Slippage included", f'{_fmt(m["slippage_pct_per_side"], 2, "%")} per side')}
    </table>

    <h2>Summary</h2>
    <table>
      {row("Period", _fmt(m["years"], 2, " years"))}
      {row("Total Return", _fmt(m["total_return_pct"], 2, "%"))}
      {row("CAGR", _fmt(m["cagr_pct"], 2, "%"))}
      {row("Final Capital", f'${_fmt(m["final_capital"], 0)}')}
    </table>
    """

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>RANK 8 Backtest Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif;
          max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #111; }}
  h1 {{ border-bottom: 2px solid #16a34a; padding-bottom: 8px; }}
  h2 {{ color: #16a34a; margin-top: 28px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }}
  td.v {{ text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }}
  td.hint {{ color: #6b7280; font-size: 12px; width: 220px; }}
  .footer {{ color: #6b7280; font-size: 12px; margin-top: 24px; }}
</style></head><body>
<h1>RANK 8 - Backtest Report</h1>
<p class="footer">Pair: {PAIR} - Interval: {INTERVAL} - Fees: {BINANCE_FEE*100:.2f}%/side - Slippage: {SLIPPAGE_PCT*100:.2f}%/side - Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
{chart_html}
{sections}
<p class="footer">Slippage and Binance fees are applied on entry AND exit in the backtest engine (TOTAL_FRICTION = BINANCE_FEE + SLIPPAGE_PCT).</p>
</body></html>"""
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def main():
    print(f"Fetching {PAIR} {INTERVAL} data (limit={LIMIT})...")
    df = get_ohlcv(PAIR, interval=INTERVAL, limit_total=LIMIT)
    if df is None or len(df) < 100:
        raise SystemExit("No data fetched")
    print(f"Got {len(df)} candles from {df.iloc[0]['timestamp']} to {df.iloc[-1]['timestamp']}")
    trades, capital, max_dd, equity_df = backtest(df)
    print(f"Backtest done: {len(trades)} trades, final ${capital:,.2f}, max DD {max_dd:.2f}%")
    metrics = compute_metrics(trades, capital, max_dd, equity_df, df)
    out = generate_html(metrics, equity_df, trades, df,
                        "final_strategy_rank8_corrected_backtest.html")
    print(f"HTML written: {out}")
    print("\n--- Headline metrics ---")
    for k in ("years", "total_return_pct", "cagr_pct", "sharpe", "sortino",
              "calmar", "recovery_factor", "max_drawdown_pct",
              "max_dd_duration_days", "worst_monthly_loss_pct",
              "expectancy_pct", "time_in_market_pct", "turnover_per_year",
              "alpha_annualized_pct", "beta", "buy_hold_return_pct"):
        print(f"  {k}: {metrics[k]:.4f}" if isinstance(metrics[k], float) else f"  {k}: {metrics[k]}")
    print("\n--- Regime Sharpe ---")
    for label, info in metrics["regime_sharpe"].items():
        print(f"  {label:10s} sharpe={info['sharpe']:.2f}  pct_time={info['pct_of_time']:.1f}%  n={info['n_periods']}")


if __name__ == "__main__":
    main()
