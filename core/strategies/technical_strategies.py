def stoch_rsi_plus_swing(df):
    """
    Entrée long : HL ou LL + croisement K > D
    Entrée short : HH ou LH + croisement K < D
    """
    signal = ""
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    k_prev = prev2["stoch_k"]
    d_prev = prev2["stoch_d"]
    k_curr = prev["stoch_k"]
    d_curr = prev["stoch_d"]
    swing = prev["swing_type"]

    is_cross_up = k_prev < d_prev and k_curr > d_curr
    is_cross_down = k_prev > d_prev and k_curr < d_curr

    if swing in ["LL", "HL"] and is_cross_up:
        signal = "buy"
    elif swing in ["HH", "LH"] and is_cross_down:
        signal = "sell"

    return signal, prev

#version de base

def bollinger_plus_divergence(df):

    signal = ""
    curr = df.iloc[-2]

    if curr["close"] < curr.get("bb_lower", 0) and curr.get("rsi_divergence") == "bullish":
        signal = "buy"
    elif curr["close"] > curr.get("bb_upper", 0) and curr.get("rsi_divergence") == "bearish":
        signal = "sell"

    return signal, curr


"""

#fonction en prenant en compte la meche => meilleur resultat
def bollinger_plus_divergence(df):
    signal = ""
    curr = df.iloc[-2]

    # Prend en compte les mèches (low/high)
    if curr["low"] < curr.get("bb_lower", 0) and curr.get("rsi_divergence") == "bullish":
        signal = "buy"
    elif curr["high"] > curr.get("bb_upper", 0) and curr.get("rsi_divergence") == "bearish":
        signal = "sell"

    return signal, curr
"""

#à tester demain
def bollinger_plus_divergence_flex(df, tolerance=1):
    signal = ""
    candle = None

    if len(df) < 6:
        return "", None

    for i in range(-5, -1):
        curr = df.iloc[i]

        touched_lower = curr["low"] < curr.get("bb_lower", 0)
        touched_upper = curr["high"] > curr.get("bb_upper", 0)

        has_bullish_div = any(
            df.iloc[j].get("rsi_divergence") == "bullish"
            for j in range(i - tolerance, i + tolerance + 1)
            if 0 <= j < len(df)
        )
        has_bearish_div = any(
            df.iloc[j].get("rsi_divergence") == "bearish"
            for j in range(i - tolerance, i + tolerance + 1)
            if 0 <= j < len(df)
        )

        if touched_lower and has_bullish_div:
            return "buy", curr
        elif touched_upper and has_bearish_div:
            return "sell", curr

    return "", None


#à tester demain
def bollinger_plus_divergence_flex_live(df, tolerance=1):
    if len(df) < 4:
        return "", None

    curr = df.iloc[-1]
    touched_lower = curr["low"] < curr.get("bb_lower", 0)
    touched_upper = curr["high"] > curr.get("bb_upper", 0)

    has_bullish_div = any(
        df.iloc[j].get("rsi_divergence") == "bullish"
        for j in range(len(df) - 1 - tolerance, len(df))
        if 0 <= j < len(df)
    )
    has_bearish_div = any(
        df.iloc[j].get("rsi_divergence") == "bearish"
        for j in range(len(df) - 1 - tolerance, len(df))
        if 0 <= j < len(df)
    )

    if touched_lower and has_bullish_div:
        return "buy", curr
    elif touched_upper and has_bearish_div:
        return "sell", curr

    return "", None


"""
def bollinger_plus_divergence(df):
    signal = ""
    candle = None

    for i in [-3, -2]:
        curr = df.iloc[i]
        if curr["close"] < curr.get("bb_lower", 0) and curr.get("rsi_divergence") == "bullish":
            signal = "buy"
            candle = curr
            break
        elif curr["close"] > curr.get("bb_upper", 0) and curr.get("rsi_divergence") == "bearish":
            signal = "sell"
            candle = curr
            break

    return signal, candle
"""

"""
def bollinger_plus_divergence(df, tolerance=2):
    signal = ""
    candle = None

    if len(df) < 6:
        return "", None

    for i in range(-5, -1):
        curr = df.iloc[i]

        # 1. Check touche bande via mèche
        touched_lower = curr["low"] < curr.get("bb_lower", 0)
        touched_upper = curr["high"] > curr.get("bb_upper", 0)

        # 2. Cherche divergence autour
        has_bullish_div = any(
            df.iloc[j].get("rsi_divergence") == "bullish"
            for j in range(i - tolerance, i + tolerance + 1)
            if 0 <= j < len(df)
        )
        has_bearish_div = any(
            df.iloc[j].get("rsi_divergence") == "bearish"
            for j in range(i - tolerance, i + tolerance + 1)
            if 0 <= j < len(df)
        )

        if touched_lower and has_bullish_div:
            return "buy", curr
        elif touched_upper and has_bearish_div:
            return "sell", curr

    return "", None
"""

# fonction de base qui marche mais sans bougie d'ecart pour les conditoins
""""
def bollinger_plus_swing(df):
    signal = ""
    candle = None

    for i in [-3, -2]:  # Regarde les 2 dernières bougies fermées
        curr = df.iloc[i]
        swing = curr.get("swing_type", "")
        low = df["low"].iloc[i]
        high = df["high"].iloc[i]

        if swing in ["LL", "HL"] and low < curr.get("bb_lower", 0):
            signal = "buy"
            candle = curr
            break
        elif swing in ["HH", "LH"] and high > curr.get("bb_upper", 0):
            signal = "sell"
            candle = curr
            break

    return signal, candle
"""


def bollinger_plus_swing(df):
    signal = ""
    candle = None

    if len(df) < 6:
        return "", None  # pas assez de bougies pour vérifier

    for i in range(-5, -1):
        curr = df.iloc[i]
        low = curr["low"]
        high = curr["high"]
        bb_lower = curr.get("bb_lower", 0)
        bb_upper = curr.get("bb_upper", 0)
        swing = curr.get("swing_type", "")

        # Cas 1 : touche → swing dans les 2 prochaines
        if low < bb_lower:
            for j in range(i + 1, i + 3):
                if j >= len(df):
                    continue
                swing_row = df.iloc[j]
                swing_type = swing_row.get("swing_type", "")
                if swing_type in ["LL", "HL"]:
                    return "buy", swing_row

        elif high > bb_upper:
            for j in range(i + 1, i + 3):
                if j >= len(df):
                    continue
                swing_row = df.iloc[j]
                swing_type = swing_row.get("swing_type", "")
                if swing_type in ["HH", "LH"]:
                    return "sell", swing_row

        # Cas 2 : swing → touche dans les 2 précédentes
        if swing in ["LL", "HL"]:
            for j in range(i - 2, i):
                if j < 0:
                    continue
                prev_row = df.iloc[j]
                if prev_row["low"] < prev_row.get("bb_lower", 0):
                    return "buy", curr

        elif swing in ["HH", "LH"]:
            for j in range(i - 2, i):
                if j < 0:
                    continue
                prev_row = df.iloc[j]
                if prev_row["high"] > prev_row.get("bb_upper", 0):
                    return "sell", curr

    return "", None


def stoch_rsi_plus_bollinger(df):
    """
    Entrée long : croisement K > D + mèche touche bb_lower (±1 bougie)
    Entrée short : croisement K < D + mèche touche bb_upper (±1 bougie)
    """
    signal = ""
    candle = None

    if len(df) < 6:
        return "", None

    # Cherche sur les 3 dernières bougies (pour couvrir les -3 à -1)
    for i in range(-5, -1):
        curr = df.iloc[i]
        prev = df.iloc[i - 1] if i - 1 >= 0 else None

        # === CROISEMENT
        k_prev = prev["stoch_k"] if prev is not None else None
        d_prev = prev["stoch_d"] if prev is not None else None
        k_curr = curr["stoch_k"]
        d_curr = curr["stoch_d"]

        is_cross_up = k_prev is not None and k_prev < d_prev and k_curr > d_curr
        is_cross_down = k_prev is not None and k_prev > d_prev and k_curr < d_curr

        # === PRIX TOUCHE BANDE via MÈCHE (sur bougie courante ou voisine)
        touched_lower = (
                curr["low"] < curr.get("bb_lower", 0)
                or (i - 1 >= 0 and df.iloc[i - 1]["low"] < df.iloc[i - 1].get("bb_lower", 0))
                or (i + 1 < len(df) and df.iloc[i + 1]["low"] < df.iloc[i + 1].get("bb_lower", 0))
        )
        touched_upper = (
                curr["high"] > curr.get("bb_upper", 0)
                or (i - 1 >= 0 and df.iloc[i - 1]["high"] > df.iloc[i - 1].get("bb_upper", 0))
                or (i + 1 < len(df) and df.iloc[i + 1]["high"] > df.iloc[i + 1].get("bb_upper", 0))
        )

        if is_cross_up and touched_lower:
            return "buy", curr
        elif is_cross_down and touched_upper:
            return "sell", curr

    return "", None


def recent_vwap_cross(df, direction="up", lookback=4):
    if len(df) < lookback:
        return False

    for i in range(-lookback, -1):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        if direction == "up":
            if prev["close"] < prev["vwap"] and curr["close"] > curr["vwap"]:
                return True
        elif direction == "down":
            if prev["close"] > prev["vwap"] and curr["close"] < curr["vwap"]:
                return True
    return False


def emperor_pivot_vwap_stoch(df):
    signal = ""
    candle = None

    if len(df) < 6:
        return signal, candle

    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    # --- Stoch RSI crossover
    k_prev = prev2["stoch_k"]
    d_prev = prev2["stoch_d"]
    k_curr = prev["stoch_k"]
    d_curr = prev["stoch_d"]
    stoch_cross = k_prev < d_prev and k_curr > d_curr

    # --- VWAP recent cross (dans les dernières 4 bougies)
    vwap_recent_cross = recent_vwap_cross(df, direction="up")

    # --- Pivot support (rebond) ou résistance cassée
    s1 = prev.get("s1")
    r1 = prev.get("r1")
    support_ok = s1 and prev["low"] <= s1 <= prev["close"]
    resistance_break = r1 and prev["open"] < r1 and prev["close"] > r1
    pivot_ok = support_ok or resistance_break

    if stoch_cross and vwap_recent_cross and pivot_ok:
        signal = "buy"
        candle = prev

    return signal, candle


def bollinger_plus_swing_live(df):
    current = df.iloc[-1]
    swing = current.get("swing_type", "")
    low = current.get("low", 0)
    high = current.get("high", 0)

    if swing in ["LL", "HL"] and low < current.get("bb_lower", 0):
        return "buy", current
    elif swing in ["HH", "LH"] and high > current.get("bb_upper", 0):
        return "sell", current
    return "", None


def stoch_rsi_plus_swing_live(df):
    if len(df) < 3:
        return "", None

    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    k_prev = prev2["stoch_k"]
    d_prev = prev2["stoch_d"]
    k_curr = prev["stoch_k"]
    d_curr = prev["stoch_d"]
    swing = prev["swing_type"]

    is_cross_up = k_prev < d_prev and k_curr > d_curr
    is_cross_down = k_prev > d_prev and k_curr < d_curr

    if (swing in ["LL", "HL"] and
            is_cross_up):
        return "buy", prev
    elif swing in ["HH", "LH"] and is_cross_down:
        return "sell", prev
    return "", None



def bollinger_plus_divergence_live(df):
    """Version améliorée pour temps réel avec tolérance temporelle"""
    if len(df) < 5:
        return "", None
    
    # Regarde les 3 dernières bougies fermées pour éviter les faux signaux de la bougie courante
    for i in range(-3, 0):  # -3, -2, -1 (dernières bougies fermées)
        try:
            current = df.iloc[i]
            
            # Vérification touche des bandes via mèches
            touched_lower = current["low"] < current.get("bb_lower", 0)
            touched_upper = current["high"] > current.get("bb_upper", 0)
            
            # Recherche divergence dans une fenêtre de ±2 bougies autour de la bougie courante
            tolerance = 2
            start_idx = max(0, len(df) + i - tolerance)
            end_idx = min(len(df), len(df) + i + tolerance + 1)
            
            has_bullish_div = False
            has_bearish_div = False
            
            # Cherche divergence dans la fenêtre de tolérance
            for j in range(start_idx, end_idx):
                if j < len(df):
                    div_type = df.iloc[j].get("rsi_divergence", "")
                    if div_type == "bullish":
                        has_bullish_div = True
                    elif div_type == "bearish":
                        has_bearish_div = True
            
            # Signal d'achat : touche bande basse + divergence haussière dans la zone
            if touched_lower and has_bullish_div:
                return "buy", current
            
            # Signal de vente : touche bande haute + divergence baissière dans la zone
            elif touched_upper and has_bearish_div:
                return "sell", current
                
        except (IndexError, KeyError):
            continue
    
    return "", None


def stoch_rsi_plus_bollinger_live(df):
    if len(df) < 4:
        return "", None

    curr = df.iloc[-2]
    prev = df.iloc[-3]

    k_prev = prev["stoch_k"]
    d_prev = prev["stoch_d"]
    k_curr = curr["stoch_k"]
    d_curr = curr["stoch_d"]

    is_cross_up = k_prev < d_prev and k_curr > d_curr
    is_cross_down = k_prev > d_prev and k_curr < d_curr

    touched_lower = (
            curr["low"] < curr.get("bb_lower", 0)
            or df.iloc[-3]["low"] < df.iloc[-3].get("bb_lower", 0)
    )
    touched_upper = (
            curr["high"] > curr.get("bb_upper", 0)
            or df.iloc[-3]["high"] > df.iloc[-3].get("bb_upper", 0)
    )

    if is_cross_up and touched_lower:
        return "buy", curr
    elif is_cross_down and touched_upper:
        return "sell", curr

    return "", None



def bollinger_plus_swing_rsi_enhanced(df):
    signal = ""
    candle = None

    if len(df) < 6:
        return "", None

    for i in range(-5, -1):
        curr = df.iloc[i]
        low = curr["low"]
        high = curr["high"]
        bb_lower = curr.get("bb_lower", 0)
        bb_upper = curr.get("bb_upper", 0)
        swing = curr.get("swing_type", "")
        rsi = curr.get("rsi", 50)
        div = curr.get("rsi_divergence", "")

        # --- Long : HL ou LL + touche + RSI < 35
        if swing in ["LL", "HL"] and low < bb_lower and rsi < 35:
            signal = "buy"
            candle = curr
            if div == "bullish":
                signal = "strong_buy"
            return signal, candle

        # --- Short : HH ou LH + touche + RSI > 65
        elif swing in ["HH", "LH"] and high > bb_upper and rsi > 65:
            signal = "sell"
            candle = curr
            if div == "bearish":
                signal = "strong_sell"
            return signal, candle

    return "", None



def bollinger_plus_divergence_trend_rsi(df):

    if len(df) < 6:
        return "", None

    df = df.copy()

    # Boucles sur les 5 dernières bougies fermées (de -5 à -1)
    for i in range(-5, -1):
        curr = df.iloc[i]

        if curr["low"] < curr.get("bb_lower", 0) and curr.get("rsi_divergence") == "bullish":
            # Check si croisement K > D dans une fenêtre autour de i
            for offset in [-1, 0, 1]:
                j = i + offset
                if j - 1 < 0 or j >= len(df):
                    continue
                k_prev = df.iloc[j - 1]["stoch_k"]
                d_prev = df.iloc[j - 1]["stoch_d"]
                k_curr = df.iloc[j]["stoch_k"]
                d_curr = df.iloc[j]["stoch_d"]
                if k_prev < d_prev and k_curr > d_curr:
                    return "buy", curr

        elif curr["high"] > curr.get("bb_upper", 0) and curr.get("rsi_divergence") == "bearish":
            # Check si croisement K < D dans une fenêtre autour de i
            for offset in [-1, 0, 1]:
                j = i + offset
                if j - 1 < 0 or j >= len(df):
                    continue
                k_prev = df.iloc[j - 1]["stoch_k"]
                d_prev = df.iloc[j - 1]["stoch_d"]
                k_curr = df.iloc[j]["stoch_k"]
                d_curr = df.iloc[j]["stoch_d"]
                if k_prev > d_prev and k_curr < d_curr:
                    return "sell", curr

    return "", None