from starknet_py.net.account.account import Account
import requests

from src.paradex.auth import get_jwt_token
from src.config.constants import PARADEX_HTTP_URL, logger
from utils.proxy import convert_proxy_to_dict


def get_auth_headers(account: Account, proxy_str: str) -> dict:
    jwt = get_jwt_token(account, proxy_str)
    return {
        "authorization": f"Bearer {jwt}"
    }


def get_balance(account: Account, proxy_str: str):
    headers = get_auth_headers(account, proxy_str)
    response = requests.get(
        f"{PARADEX_HTTP_URL}/balance",
        headers=headers,
        proxies=convert_proxy_to_dict(proxy_str),
    )

    if response.status_code != 200:
        logger.error(f"Error receiving balance: {response.text}")
        raise ValueError("Error receiving balance")

    return response.json()


def get_open_positions(account: Account, proxy_str: str):
    headers = get_auth_headers(account, proxy_str)
    response = requests.get(
        f"{PARADEX_HTTP_URL}/positions",
        headers=headers,
        proxies=convert_proxy_to_dict(proxy_str),
    )

    if response.status_code != 200:
        logger.error(f"Error receiving open positions: {response.text}")
        raise ValueError("Error receiving open positions")

    return response.json()


def get_liquidation_price(account: Account, proxy_str: str):
    headers = get_auth_headers(account, proxy_str)
    response = requests.get(
        f"{PARADEX_HTTP_URL}/liquidation_price",
        headers=headers,
        proxies=convert_proxy_to_dict(proxy_str),
    )

    if response.status_code != 200:
        logger.error(f"Error receiving liquidation price: {response.text}")
        raise ValueError("Error receiving liquidation price")

    return response.json()
