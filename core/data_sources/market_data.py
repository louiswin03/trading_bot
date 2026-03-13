# data.py
import requests
import pandas as pd
import time


BINANCE_URLS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
]


def get_ohlcv(symbol="BTCUSDT", interval="15m", limit_total=50000):
    max_limit = 1000
    df_list = []
    end_time = None
    working_url = None
    for url in BINANCE_URLS:
        try:
            test_params = {"symbol": symbol, "interval": interval, "limit": 1}
            resp = requests.get(url, params=test_params, timeout=10)
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                working_url = url
                print(f"[DATA] Using endpoint: {url}")
                break
        except Exception:
            continue
    if not working_url:
        raise ConnectionError("Cannot reach any Binance data endpoint.")
    while limit_total > 0:
        fetch_limit = min(max_limit, limit_total)
        params = {"symbol": symbol, "interval": interval, "limit": fetch_limit}
        if end_time:
            params["endTime"] = end_time
        response = requests.get(working_url, params=params, timeout=30)
        data = response.json()
        if not data or isinstance(data, dict):
            print("Fin de recuperation ou erreur Binance:", data)
            break
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "_1", "_2", "_3", "_4", "_5", "_6"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df_list.insert(0, df)
        end_time = data[0][0] - 1
        limit_total -= fetch_limit
        time.sleep(0.25)
    final_df = pd.concat(df_list, ignore_index=True)
    final_df["timestamp"] = final_df["timestamp"].dt.tz_localize("UTC").dt.tz_convert("Europe/Paris")
    return final_df
