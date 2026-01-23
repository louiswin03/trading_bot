import pandas as pd

# =========================
# 1. RSI (Wilder)
# =========================
def compute_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


# =========================
# 2. Stochastic RSI
# =========================
def compute_stoch_rsi(df, rsi_length=14, stoch_length=14, smooth_k=3, smooth_d=3):
    df = compute_rsi(df, period=rsi_length)
    rsi = df["rsi"]

    lowest_rsi = rsi.rolling(stoch_length).min()
    highest_rsi = rsi.rolling(stoch_length).max()

    stoch_rsi = (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
    k = stoch_rsi.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()

    df["stoch_k"] = k * 100
    df["stoch_d"] = d * 100

    return df


# =========================
# 3. Bandes de Bollinger
# =========================
def compute_bollinger_bands(df, length=20, mult=2.0, ma_type="SMA"):
    df = df.copy()

    if ma_type == "SMA":
        df["bb_basis"] = df["close"].rolling(length).mean()
    elif ma_type == "EMA":
        df["bb_basis"] = df["close"].ewm(span=length, adjust=False).mean()
    elif ma_type == "WMA":
        weights = pd.Series(range(1, length + 1))
        df["bb_basis"] = df["close"].rolling(length).apply(lambda x: (weights * x).sum() / weights.sum(), raw=True)
    elif ma_type in ["SMMA", "RMA"]:
        df["bb_basis"] = df["close"].ewm(alpha=1/length, adjust=False).mean()
    else:
        raise ValueError("Unsupported MA type")

    df["bb_std"] = df["close"].rolling(length).std()
    df["bb_upper"] = df["bb_basis"] + mult * df["bb_std"]
    df["bb_lower"] = df["bb_basis"] - mult * df["bb_std"]
    return df


# =========================
# 4. Divergences RSI
# =========================



#divergence de base
#marche pas mal mais vérifie seulement avec 1 seule précédente bougie sur les lookback renseignées
#spread correspond au nombre de bougies max précédentes qu'on va regarder ( à changer dans main attention)

"""
def detect_rsi_divergence(df, rsi_col="rsi", lookback=20, spread=5):
    df = df.copy()
    df["rsi_divergence"] = ""

    for i in range(lookback, len(df)):
        rsi_now = df[rsi_col].iloc[i]
        price_now_low = df["low"].iloc[i]
        price_now_high = df["high"].iloc[i]

        # cherche précédent bas significatif
        low_idx = df["low"].iloc[i - spread:i].idxmin()
        price_prev_low = df["low"].loc[low_idx]
        rsi_prev_low = df[rsi_col].loc[low_idx]

        # === BULLISH
        if price_now_low < price_prev_low and rsi_now > rsi_prev_low:
            df.at[i, "rsi_divergence"] = "bullish"

        # cherche précédent haut significatif
        high_idx = df["high"].iloc[i - spread:i].idxmax()
        price_prev_high = df["high"].loc[high_idx]
        rsi_prev_high = df[rsi_col].loc[high_idx]

        # === BEARISH
        if price_now_high > price_prev_high and rsi_now < rsi_prev_high:
            df.at[i, "rsi_divergence"] = "bearish"

    return df
"""



#code pour prendre meche ou non avec use_close
#use_close =false veut dire qu'on prend les meches en compte
#use_close =false veut direqu'on prend que leprix decloture en comtpe

#on compare avec toutes les bougies dans lookback et pa juste 1 seule. Il faut changer lookback dans main
def detect_rsi_divergence(df, rsi_col="rsi", lookback=30, use_close=False):


    df = df.copy()
    df["rsi_divergence"] = ""

    for i in range(lookback, len(df)):
        rsi_now = df[rsi_col].iloc[i]

        price_now_low = df["close"].iloc[i] if use_close else df["low"].iloc[i]
        price_now_high = df["close"].iloc[i] if use_close else df["high"].iloc[i]

        # === Bullish divergence ===
        for j in range(i - lookback, i):
            price_past = df["close"].iloc[j] if use_close else df["low"].iloc[j]
            rsi_past = df[rsi_col].iloc[j]

            if price_now_low < price_past and rsi_now > rsi_past:
                df.at[i, "rsi_divergence"] = "bullish"
                break

        # === Bearish divergence ===
        for j in range(i - lookback, i):
            price_past = df["close"].iloc[j] if use_close else df["high"].iloc[j]
            rsi_past = df[rsi_col].iloc[j]

            if price_now_high > price_past and rsi_now < rsi_past:
                df.at[i, "rsi_divergence"] = "bearish"
                break

    return df




"""




#test pour un ecart minimum entre les valeurs du rsi
def detect_rsi_divergence(df, rsi_col="rsi", lookback=30, rsi_diff_min=10, use_close=False):
    df = df.copy()
    df["rsi_divergence"] = ""

    for i in range(lookback, len(df)):
        rsi_now = df[rsi_col].iloc[i]
        price_now_low = df["close"].iloc[i] if use_close else df["low"].iloc[i]
        price_now_high = df["close"].iloc[i] if use_close else df["high"].iloc[i]

        # === Bullish divergence ===
        for j in range(i - lookback, i):
            price_past = df["close"].iloc[j] if use_close else df["low"].iloc[j]
            rsi_past = df[rsi_col].iloc[j]

            if price_now_low < price_past and (rsi_now - rsi_past) >= rsi_diff_min:
                df.at[i, "rsi_divergence"] = "bullish"
                break

        # === Bearish divergence ===
        for j in range(i - lookback, i):
            price_past = df["close"].iloc[j] if use_close else df["high"].iloc[j]
            rsi_past = df[rsi_col].iloc[j]

            if price_now_high > price_past and (rsi_past - rsi_now) >= rsi_diff_min:
                df.at[i, "rsi_divergence"] = "bearish"
                break

    return df
"""




"""

def detect_rsi_divergence(df, lookback=30, left=3, rsi_col="rsi", tolerance=2):

   # Détection de divergence RSI (avec tolérance de timing et prise en compte des mèches)
   # Résultat stocké dans colonne 'rsi_divergence'

    df = df.copy()
    df["rsi_divergence"] = ""

    def is_pivot_low(series, i, l):
        if i - l < 0:
            return False
        return series[i] == min(series[i - l:i + 1])

    def is_pivot_high(series, i, l):
        if i - l < 0:
            return False
        return series[i] == max(series[i - l:i + 1])

    for i in range(left, len(df)):
        for j in range(i - lookback, i - left):  # on regarde dans le passé, mais pas trop près
            if j <= left:
                continue

            # === BULLISH
            if is_pivot_low(df[rsi_col], j, left) and is_pivot_low(df[rsi_col], i, left):
                price1 = df["low"].iloc[j]
                price2 = df["low"].iloc[i]
                rsi1 = df[rsi_col].iloc[j]
                rsi2 = df[rsi_col].iloc[i]

                if price2 < price1 and rsi2 > rsi1:
                    # Marquer non seulement sur i, mais aussi i-1 à i+tolerance
                    for k in range(i - tolerance, i + tolerance + 1):
                        if 0 <= k < len(df):
                            df.at[k, "rsi_divergence"] = "bullish"
                    break

            # === BEARISH
            if is_pivot_high(df[rsi_col], j, left) and is_pivot_high(df[rsi_col], i, left):
                price1 = df["high"].iloc[j]
                price2 = df["high"].iloc[i]
                rsi1 = df[rsi_col].iloc[j]
                rsi2 = df[rsi_col].iloc[i]

                if price2 > price1 and rsi2 < rsi1:
                    for k in range(i - tolerance, i + tolerance + 1):
                        if 0 <= k < len(df):
                            df.at[k, "rsi_divergence"] = "bearish"
                    break

    return df

"""



# =========================
# 5. Swings + Patterns (LuxAlgo style)
# =========================



def detect_lux_patterns(df: pd.DataFrame, length: int = 21) -> pd.DataFrame:
    df = df.copy()
    df["pattern"] = ""
    df["swing"] = ""
    df["swing_type"] = ""

    o = df["open"]
    h = df["high"]
    l = df["low"]
    c = df["close"]
    d = (c - o).abs()

    df["pivot_high"] = h == h.rolling(window=2 * length + 1, center=True).max()
    df["pivot_low"] = l == l.rolling(window=2 * length + 1, center=True).min()

    previous_ph = None
    previous_pl = None

    for i in range(length, len(df) - length):  # On évite d'aller trop loin pour les pivots
        body = abs(c.iloc[i] - o.iloc[i])
        open_ = o.iloc[i]
        close_ = c.iloc[i]
        high = h.iloc[i]
        low = l.iloc[i]

        # === Swing High
        if df["pivot_high"].iloc[i]:
            if previous_ph is not None:
                swing_type = "HH" if high > previous_ph else "LH"
            else:
                swing_type = "HH"

            df.at[i, "swing"] = "High"
            df.at[i, "swing_type"] = swing_type
            previous_ph = high

            # Candle patterns
            if min(open_, close_) - low > body and high - max(open_, close_) < body:
                df.at[i, "pattern"] = "Hanging Man"
            elif high - max(open_, close_) > body and min(open_, close_) - low < body:
                df.at[i, "pattern"] = "Shooting Star"

        # === Swing Low
        elif df["pivot_low"].iloc[i]:
            if previous_pl is not None:
                swing_type = "LL" if low < previous_pl else "HL"
            else:
                swing_type = "LL"

            df.at[i, "swing"] = "Low"
            df.at[i, "swing_type"] = swing_type
            previous_pl = low

            if min(open_, close_) - low > body and high - max(open_, close_) < body:
                df.at[i, "pattern"] = "Hammer"
            elif high - max(open_, close_) > body and min(open_, close_) - low < body:
                df.at[i, "pattern"] = "Inverted Hammer"

        # === Engulfing (peuvent apparaître sans swing)
        if i > 0:
            if (c.iloc[i] > o.iloc[i] and c.iloc[i-1] < o.iloc[i-1] and
                    c.iloc[i] > o.iloc[i-1] and o.iloc[i] < c.iloc[i-1]):
                df.at[i, "pattern"] += ("Bullish Engulfing" if df.at[i, "pattern"] == "" else ", Bullish Engulfing")
            elif (c.iloc[i] < o.iloc[i] and c.iloc[i-1] > o.iloc[i-1] and
                  c.iloc[i] < o.iloc[i-1] and o.iloc[i] > c.iloc[i-1]):
                df.at[i, "pattern"] += ("Bearish Engulfing" if df.at[i, "pattern"] == "" else ", Bearish Engulfing")

    return df



def compute_vwap(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date

    df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
    df["tp_x_vol"] = df["typical_price"] * df["volume"]

    # Réinitialise VWAP chaque jour
    df["cum_vol"] = df.groupby("date")["volume"].cumsum()
    df["cum_tp_vol"] = df.groupby("date")["tp_x_vol"].cumsum()

    df["vwap"] = df["cum_tp_vol"] / df["cum_vol"]
    df.drop(columns=["date", "typical_price", "tp_x_vol", "cum_vol", "cum_tp_vol"], inplace=True)
    return df



def compute_fibonacci_pivots(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date

    # Regrouper par jour
    daily = df.groupby("date").agg({
        "high": "max",
        "low": "min",
        "close": "last"
    }).reset_index()

    # Calcul des pivots Fibonacci
    pivots = []
    for _, row in daily.iterrows():
        high = row["high"]
        low = row["low"]
        close = row["close"]
        pivot = (high + low + close) / 3
        r1 = pivot + 0.382 * (high - low)
        r2 = pivot + 0.618 * (high - low)
        r3 = pivot + 1.000 * (high - low)
        s1 = pivot - 0.382 * (high - low)
        s2 = pivot - 0.618 * (high - low)
        s3 = pivot - 1.000 * (high - low)
        pivots.append({
            "date": row["date"],
            "pivot": pivot,
            "r1": r1, "r2": r2, "r3": r3,
            "s1": s1, "s2": s2, "s3": s3
        })

    pivots_df = pd.DataFrame(pivots)

    # Fusionner avec le dataframe original (valeurs du jour précédent étendues à toutes les bougies du jour suivant)
    df = df.merge(pivots_df, on="date", how="left")

    df = df.ffill()


    return df.drop(columns=["date"])



def detect_swing_real_time(df, left=3):
    df = df.copy()
    df["swing"] = ""
    df["swing_type"] = ""

    last_low = None
    last_high = None

    for i in range(left, len(df)):
        lows = df["low"].iloc[i - left:i + 1]
        highs = df["high"].iloc[i - left:i + 1]

        if df["low"].iloc[i] == lows.min():
            if last_low is not None:
                swing_type = "LL" if df["low"].iloc[i] < last_low else "HL"
            else:
                swing_type = "LL"
            df.at[i, "swing"] = "Low"
            df.at[i, "swing_type"] = swing_type
            last_low = df["low"].iloc[i]

        elif df["high"].iloc[i] == highs.max():
            if last_high is not None:
                swing_type = "HH" if df["high"].iloc[i] > last_high else "LH"
            else:
                swing_type = "HH"
            df.at[i, "swing"] = "High"
            df.at[i, "swing_type"] = swing_type
            last_high = df["high"].iloc[i]

    return df
