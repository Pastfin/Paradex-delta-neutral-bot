import requests
import pandas as pd

from src.config.constants import PARADEX_HTTP_URL, logger
from src.config.paths import DATA_DIR
from utils.general import _retry_request
from src.paradex.market import update_markets


def update_metrics():
    update_markets()
    
    response = _retry_request(requests.get, f"{PARADEX_HTTP_URL}/markets/summary?market=ALL")

    if response.status_code != 200:
        logger.error(f"Failed to fetch market data: {response.status_code} - {response.text}")
        raise ValueError("Failed to fetch market summary")

    data = response.json()
    results = data.get("results", [])

    for item in results:
        greeks = item.pop("greeks", {})
        for greek_key, greek_value in greeks.items():
            item[f"greek_{greek_key}"] = greek_value

    df = pd.DataFrame(results)
    df = df[df["symbol"].str.endswith("-PERP")]

    numeric_cols = [
        "mark_price", "delta", "last_traded_price", "bid", "ask",
        "volume_24h", "total_volume", "underlying_price",
        "open_interest", "funding_rate", "price_change_rate_24h",
        "future_funding_rate", "greek_delta", "greek_gamma", "greek_vega",
        "created_at", "mark_iv", "bid_iv", "ask_iv", "last_iv"
    ]
    numeric_cols_present = [col for col in numeric_cols if col in df.columns]

    df[numeric_cols_present] = df[numeric_cols_present].apply(pd.to_numeric, errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], unit="ms")

    needed_columns = [
        "symbol", "mark_price", "volume_24h", "total_volume",
        "created_at", "funding_rate", "price_change_rate_24h"
    ]

    df = df[needed_columns].sort_values(by="volume_24h", ascending=False).reset_index(drop=True)

    df["tier"] = pd.qcut(df["volume_24h"], q=5, labels=[5, 4, 3, 2, 1])

    df["tier"] = df["tier"].astype(int)

    logger.info(f"Market metrics updated successfully: active_pairs.xlsx {len(df)} rows")

    df.to_excel(DATA_DIR + "/active_pairs.xlsx", index=False)

    return df
