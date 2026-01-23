# data.py
import requests
import pandas as pd
import time


def get_ohlcv(symbol="BTCUSDT", interval="15m", limit_total=50000):
    import requests
    import pandas as pd
    import time

    url = "https://api.binance.com/api/v3/klines"
    max_limit = 1000
    df_list = []
    end_time = None

    while limit_total > 0:
        fetch_limit = min(max_limit, limit_total)
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": fetch_limit,
        }

        if end_time:
            params["endTime"] = end_time

        response = requests.get(url, params=params)
        data = response.json()

        if not data or "code" in data:
            print("Fin de récupération ou erreur Binance:", data)
            break

        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "_1", "_2", "_3", "_4", "_5", "_6"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)

        df_list.insert(0, df)

        end_time = data[0][0] - 1  # on recule dans le passé
        limit_total -= fetch_limit

        time.sleep(0.25)

    final_df = pd.concat(df_list, ignore_index=True)
    final_df["timestamp"] = final_df["timestamp"].dt.tz_localize("UTC").dt.tz_convert("Europe/Paris")
    return final_df