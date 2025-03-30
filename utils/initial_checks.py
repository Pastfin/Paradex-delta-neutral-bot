import requests
import pandas as pd

from src.accounts_monitor import update_accounts_info
from src.config.paths import DATA_DIR
from src.config.constants import logger
from utils.data import USER_CONFIG
from utils.proxy import convert_proxy_to_dict


def check_config() -> None:
    config = USER_CONFIG

    range_keys = [
        "order_value_usd",
        "accounts_per_trade",
        "order_duration_min",
        "delay_between_trading_cycles_min",
        "delay_between_opening_orders_sec",
        "ltv_checks_sec",
    ]

    for key in range_keys:
        if key not in config:
            raise ValueError(f"Missing config section: '{key}'")

        section = config[key]

        if not isinstance(section, dict):
            raise TypeError(f"'{key}' must be a dictionary with 'min' and 'max'")

        min_val = section.get("min")
        max_val = section.get("max")

        if min_val is None or max_val is None:
            raise ValueError(f"'{key}' must contain both 'min' and 'max' keys")

        if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
            raise TypeError(f"'min' and 'max' in '{key}' must be numeric")

        if min_val > max_val:
            raise ValueError(f"In '{key}', 'min' cannot be greater than 'max'")

    if "max_leverage" not in config or not isinstance(config["max_leverage"], (int, float)):
        raise ValueError("Missing or invalid 'max_leverage'")

    if config["max_leverage"] <= 0:
        raise ValueError("'max_leverage' must be greater than 0")

    if "max_position_ltv" not in config or not isinstance(config["max_position_ltv"], (int, float)):
        raise ValueError("Missing or invalid 'max_position_ltv'")

    if not 0 < config["max_position_ltv"] <= 100:
        raise ValueError("'max_position_ltv' must be between 0 and 100")

    if "orders_distribution_noise" not in config or not isinstance(config["orders_distribution_noise"], (int, float)):
        raise ValueError("Missing or invalid 'orders_distribution_noise'")

    if config["orders_distribution_noise"] < 0:
        raise ValueError("'orders_distribution_noise' must be non-negative")

    if "retries" not in config or not isinstance(config["retries"], int):
        raise ValueError("Missing or invalid 'retries'")

    if config["retries"] < 0:
        raise ValueError("'retries' must be >= 0")

    if "debug_level" not in config or not isinstance(config["debug_level"], str):
        raise ValueError("Missing or invalid 'debug_level'")

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if config["debug_level"].upper() not in valid_levels:
        raise ValueError(f"Invalid debug level '{config['debug_level']}'. Must be one of {valid_levels}")

    logger.success("✅ Config check passed.")


def check_accounts() -> None:
    df = pd.read_excel(DATA_DIR + "/accounts.xlsx")

    required_columns = ["USDC", "is_active", "position_market", "proxy"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing '{col}' column in accounts.xlsx")

    if not df["is_active"].dropna().apply(lambda x: isinstance(x, bool)).all():
        raise ValueError("Column 'is_active' must contain only boolean values (True/False)")

    order_value_max = USER_CONFIG["order_value_usd"]["max"]
    order_value_min = USER_CONFIG["order_value_usd"]["min"]
    max_leverage = USER_CONFIG["max_leverage"]

    for i, row in df.iterrows():
        if row.get("is_active") is not True:
            continue

        short_pk = str(row.get("private_key", ""))[:10]

        proxy = row.get("proxy", "")
        if pd.isna(proxy) or str(proxy).strip() == "":
            raise ValueError(f"[{short_pk}] Proxy is missing or empty")
        check_proxy(proxy)

        position_market = row.get("position_market")
        if pd.notna(position_market) and str(position_market).strip() != "":
            raise ValueError(
                f"[{short_pk}] Account has an open position on market: '{position_market}'. "
                f"Close all positions before proceeding."
            )

        usdc_balance = row.get("USDC", 0)
        max_order = usdc_balance * max_leverage
        min_balance = order_value_min / max_leverage

        if max_order < order_value_min:
            raise ValueError(
                f"[{short_pk}] USDC balance too low (${usdc_balance:.2f}). "
                f"Minimum required is ${round(min_balance, 2)}"
            )

        actual_leverage = order_value_max / usdc_balance
        if actual_leverage > max_leverage:
            raise ValueError(
                f"[{short_pk}] Max leverage exceeded. "
                f"Config allows max {max_leverage}, but calculated {actual_leverage:.2f} "
                f"with balance ${usdc_balance:.2f} and order value ${order_value_max}"
            )

    logger.success("✅ Accounts check passed.")


def check_proxy(proxy_str: str) -> None:
    try:
        response = requests.get(
            "https://example.com",
            proxies=convert_proxy_to_dict(proxy_str),
            timeout=5
        )
        if response.status_code != 200:
            raise ValueError(f"Proxy returned status code {response.status_code}")
    except Exception as e:
        raise ValueError(f"Invalid or unreachable proxy '{proxy_str}': {e}")


def start():
    logger.info("Starting initial checks")
    update_accounts_info()
    check_config()
    check_accounts()
