import json
from pathlib import Path
import requests

from src.config.paths import FUTURE_PAIRS_PATH, DATA_DIR
from src.config.constants import PARADEX_HTTP_URL, logger
from utils.data import load_json


def _load_pairs(path: Path) -> list:
    try:
        data = load_json(path)
        return data.get("results", [])
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to load pairs data from {path}") from exc


def _find_pair_by_key(key: str, value: str) -> dict:
    pairs = _load_pairs(Path(FUTURE_PAIRS_PATH))
    value_upper = value.upper()
    for pair in pairs:
        if pair.get(key, "").upper() == value_upper:
            return pair
    raise ValueError(f"{key.capitalize()} '{value}' not found in futures pairs")


def get_pair_data(token: str) -> dict:
    return _find_pair_by_key("base_currency", token)


def get_pair_data_by_symbol(symbol: str) -> dict:
    return _find_pair_by_key("symbol", symbol)


def get_pair_price(token: str) -> float:
    pair = get_pair_data(token)
    symbol = pair["symbol"]

    response = requests.get(f"{PARADEX_HTTP_URL}/bbo/{symbol}")
    if response.status_code != 200:
        logger.error(f"Error receiving token price: {response.text}")
        raise ValueError("Error receiving token price")

    data = response.json()
    try:
        bid = float(data["bid"])
        ask = float(data["ask"])
    except (KeyError, ValueError, TypeError) as exc:
        logger.error(f"Invalid price data format: {data}")
        raise ValueError("Failed to parse bid/ask price") from exc

    return (bid + ask) / 2


def update_markets():
    logger.info("Futures pairs information update has started")

    response = requests.get(f"{PARADEX_HTTP_URL}/markets")
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.error(f"Error fetching current futures pairs: {response.text}")
        raise exc

    data = response.json()
    filtered_results = [
        item for item in data.get("results", [])
        if item.get("symbol", "").endswith("-PERP")
    ]

    file_path = Path(DATA_DIR) / "pairs.json"
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump({"results": filtered_results}, file, ensure_ascii=False, indent=2)

    logger.success("Information on futures pairs has been updated")
