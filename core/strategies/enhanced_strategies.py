"""
Stratégies améliorées pour le trading en temps réel
Versions optimisées pour capturer plus de signaux valides
"""

def bollinger_plus_divergence_enhanced(df):
    """
    Version améliorée pour signaux CONFIRMÉS (bougies clôturées)
    Utilisée pour les signaux principaux, pas les alertes précoces
    """
    if len(df) < 8:
        return "", None
    
    # Regarde les 5 dernières bougies FERMÉES (évite la bougie courante)
    for i in range(-6, -1):  # -6, -5, -4, -3, -2 (bougies fermées)
        try:
            current = df.iloc[i]
            
            # Vérification touche des bandes via mèches
            touched_lower = current["low"] < current.get("bb_lower", 0)
            touched_upper = current["high"] > current.get("bb_upper", 0)
            
            if not (touched_lower or touched_upper):
                continue
            
            # Recherche divergence dans une fenêtre élargie de ±3 bougies
            tolerance = 3
            start_idx = max(0, len(df) + i - tolerance)
            end_idx = min(len(df), len(df) + i + tolerance + 1)
            
            has_bullish_div = False
            has_bearish_div = False
            div_strength = 0  # Compteur de force de la divergence
            
            # Cherche divergence dans la fenêtre de tolérance
            for j in range(start_idx, end_idx):
                if j < len(df) and j != len(df) - 1:  # Évite la bougie courante
                    div_type = df.iloc[j].get("rsi_divergence", "")
                    if div_type == "bullish":
                        has_bullish_div = True
                        div_strength += 1
                    elif div_type == "bearish":
                        has_bearish_div = True
                        div_strength += 1
            
            # Confirmation supplémentaire : RSI dans la zone appropriée
            rsi = current.get("rsi", 50)
            
            if touched_lower and has_bullish_div:
                # Pour un signal d'achat, RSI doit être oversold (< 45 pour plus de flexibilité)
                rsi_confirmation = rsi < 45
                
                # Confirmation par momentum (prix des 3 dernières bougies)
                momentum_confirmation = True
                if i >= -len(df) + 3:
                    recent_closes = [df.iloc[k]["close"] for k in range(i-2, i+1) if k >= 0]
                    if len(recent_closes) >= 2:
                        # Prix commence à remonter ou se stabilise
                        momentum_confirmation = recent_closes[-1] >= recent_closes[0] * 0.998  # 0.2% de tolérance
                
                # Signal d'achat avec scoring
                if rsi_confirmation and momentum_confirmation and div_strength >= 1:
                    signal_strength = "buy"
                    if div_strength >= 2 and rsi < 35:
                        signal_strength = "strong_buy"
                    return signal_strength, current
                    
            elif touched_upper and has_bearish_div:
                # Pour un signal de vente, RSI doit être overbought (> 55 pour plus de flexibilité)
                rsi_confirmation = rsi > 55
                
                # Confirmation par momentum
                momentum_confirmation = True
                if i >= -len(df) + 3:
                    recent_closes = [df.iloc[k]["close"] for k in range(i-2, i+1) if k >= 0]
                    if len(recent_closes) >= 2:
                        # Prix commence à baisser ou se stabilise
                        momentum_confirmation = recent_closes[-1] <= recent_closes[0] * 1.002  # 0.2% de tolérance
                
                # Signal de vente avec scoring
                if rsi_confirmation and momentum_confirmation and div_strength >= 1:
                    signal_strength = "sell"
                    if div_strength >= 2 and rsi > 65:
                        signal_strength = "strong_sell"
                    return signal_strength, current
                    
        except (IndexError, KeyError):
            continue
    
    return "", None



def bollinger_plus_divergence_live_enhanced(df):
    """
    Version ultra-améliorée pour temps réel avec:
    - Tolérance temporelle élargie
    - Confirmation par volume
    - Système de scoring des signaux
    - Protection contre les faux signaux
    """
    if len(df) < 8:
        return "", None
    
    # Regarde les 5 dernières bougies fermées pour plus de robustesse
    for i in range(-5, 0):  # -5, -4, -3, -2, -1
        try:
            current = df.iloc[i]
            
            # Vérification touche des bandes via mèches
            touched_lower = current["low"] < current.get("bb_lower", 0)
            touched_upper = current["high"] > current.get("bb_upper", 0)
            
            if not (touched_lower or touched_upper):
                continue
            
            # Recherche divergence dans une fenêtre élargie de ±3 bougies
            tolerance = 3
            start_idx = max(0, len(df) + i - tolerance)
            end_idx = min(len(df), len(df) + i + tolerance + 1)
            
            has_bullish_div = False
            has_bearish_div = False
            div_strength = 0  # Compteur de force de la divergence
            
            # Cherche divergence dans la fenêtre de tolérance
            for j in range(start_idx, end_idx):
                if j < len(df):
                    div_type = df.iloc[j].get("rsi_divergence", "")
                    if div_type == "bullish":
                        has_bullish_div = True
                        div_strength += 1
                    elif div_type == "bearish":
                        has_bearish_div = True
                        div_strength += 1
            
            # Confirmation supplémentaire : RSI dans la zone appropriée
            rsi = current.get("rsi", 50)
            rsi_confirmation = False
            
            if touched_lower and has_bullish_div:
                # Pour un signal d'achat, RSI doit être oversold (< 40)
                rsi_confirmation = rsi < 40
                
                # Confirmation par volume (si disponible)
                volume_confirmation = True
                if "volume" in current:
                    # Volume actuel supérieur à la moyenne des 5 dernières bougies
                    recent_volumes = [df.iloc[k].get("volume", 0) for k in range(i-4, i+1) if k >= 0]
                    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 1
                    volume_confirmation = current.get("volume", 0) > avg_volume * 1.2
                
                # Signal d'achat avec scoring
                if rsi_confirmation and volume_confirmation and div_strength >= 1:
                    signal_strength = "buy"
                    if div_strength >= 2 and rsi < 30:
                        signal_strength = "strong_buy"
                    return signal_strength, current
                    
            elif touched_upper and has_bearish_div:
                # Pour un signal de vente, RSI doit être overbought (> 60)
                rsi_confirmation = rsi > 60
                
                # Confirmation par volume
                volume_confirmation = True
                if "volume" in current:
                    recent_volumes = [df.iloc[k].get("volume", 0) for k in range(i-4, i+1) if k >= 0]
                    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 1
                    volume_confirmation = current.get("volume", 0) > avg_volume * 1.2
                
                # Signal de vente avec scoring
                if rsi_confirmation and volume_confirmation and div_strength >= 1:
                    signal_strength = "sell"
                    if div_strength >= 2 and rsi > 70:
                        signal_strength = "strong_sell"
                    return signal_strength, current
                    
        except (IndexError, KeyError):
            continue
    
    return "", None


def bollinger_plus_divergence_live_flexible(df):
    """
    Version flexible qui capture plus de signaux en relâchant certaines contraintes
    """
    if len(df) < 6:
        return "", None
    
    # Regarde les 4 dernières bougies fermées
    for i in range(-4, 0):
        try:
            current = df.iloc[i]
            
            # Vérification touche des bandes (plus permissive)
            bb_lower = current.get("bb_lower", 0)
            bb_upper = current.get("bb_upper", 0)
            
            # Touche proche de la bande (dans les 0.5% de la bande)
            price_range = abs(bb_upper - bb_lower)
            tolerance_band = price_range * 0.005  # 0.5% de tolérance
            
            near_lower = current["low"] <= bb_lower + tolerance_band
            near_upper = current["high"] >= bb_upper - tolerance_band
            
            if not (near_lower or near_upper):
                continue
            
            # Recherche divergence dans une fenêtre de ±2 bougies
            tolerance = 2
            start_idx = max(0, len(df) + i - tolerance)
            end_idx = min(len(df), len(df) + i + tolerance + 1)
            
            has_bullish_div = False
            has_bearish_div = False
            
            for j in range(start_idx, end_idx):
                if j < len(df):
                    div_type = df.iloc[j].get("rsi_divergence", "")
                    if div_type == "bullish":
                        has_bullish_div = True
                    elif div_type == "bearish":
                        has_bearish_div = True
            
            # Signaux plus permissifs
            if near_lower and has_bullish_div:
                return "buy", current
            elif near_upper and has_bearish_div:
                return "sell", current
                
        except (IndexError, KeyError):
            continue
    
    return "", None


def bollinger_plus_divergence_live_momentum(df):
    """
    Version qui ajoute la confirmation par momentum/tendance
    """
    if len(df) < 7:
        return "", None
    
    for i in range(-4, 0):
        try:
            current = df.iloc[i]
            
            # Vérification touche des bandes
            touched_lower = current["low"] < current.get("bb_lower", 0)
            touched_upper = current["high"] > current.get("bb_upper", 0)
            
            if not (touched_lower or touched_upper):
                continue
            
            # Recherche divergence
            tolerance = 2
            start_idx = max(0, len(df) + i - tolerance)
            end_idx = min(len(df), len(df) + i + tolerance + 1)
            
            has_bullish_div = False
            has_bearish_div = False
            
            for j in range(start_idx, end_idx):
                if j < len(df):
                    div_type = df.iloc[j].get("rsi_divergence", "")
                    if div_type == "bullish":
                        has_bullish_div = True
                    elif div_type == "bearish":
                        has_bearish_div = True
            
            # Confirmation par momentum (prix des 3 dernières bougies)
            if touched_lower and has_bullish_div:
                # Vérifie si le prix commence à remonter
                recent_closes = [df.iloc[k]["close"] for k in range(i-2, i+1) if k >= 0]
                if len(recent_closes) >= 2:
                    momentum_up = recent_closes[-1] > recent_closes[0]  # Prix en hausse sur la période
                    if momentum_up:
                        return "buy", current
                        
            elif touched_upper and has_bearish_div:
                # Vérifie si le prix commence à baisser
                recent_closes = [df.iloc[k]["close"] for k in range(i-2, i+1) if k >= 0]
                if len(recent_closes) >= 2:
                    momentum_down = recent_closes[-1] < recent_closes[0]  # Prix en baisse sur la période
                    if momentum_down:
                        return "sell", current
                        
        except (IndexError, KeyError):
            continue
    
    return "", None
