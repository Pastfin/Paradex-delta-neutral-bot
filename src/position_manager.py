import random
import time
import pandas as pd
from typing import List, Dict, Any, Optional
import sys
import os

from starknet_py.net.account.account import Account

from src.config.constants import logger
from src.config.paths import DATA_DIR
from src.paradex.auth import get_account
from src.paradex.trade import open_position
from src.paradex.account import get_open_positions
from src.paradex.market import get_pair_data_by_symbol, get_pair_price
from src.accounts_monitor import update_accounts_info
from utils.data import update_state, get_user_state, USER_CONFIG
from utils.calc import calc_value_distribution
from utils.general import _retry_request


class TradingManager:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = USER_CONFIG
        self.df_accounts: pd.DataFrame = pd.DataFrame({})
        self.retries = self.config["retries"]

    def get_random_from_range(self, key: str) -> int:
        if key in self.config and isinstance(self.config[key], dict):
            min_val = self.config[key].get("min", 0)
            max_val = self.config[key].get("max", 0)
            return random.randint(min_val, max_val)
        raise ValueError(f"Invalid or missing config range for '{key}'")
    
    def select_market_data(self, df_markets: pd.DataFrame) -> Dict[str, Any]:
        max_attempts = len(df_markets)
        for attempt in range(max_attempts):
            random_idx = random.randint(0, len(df_markets) - 1)
            random_market = df_markets.iloc[random_idx]
            try:
                pair_data = get_pair_data_by_symbol(random_market["symbol"])
                if pair_data is not None:
                    logger.info(f"Successfully selected market: {random_market['symbol']}")
                    return pair_data
                else:
                    logger.warning(f"Market {random_market['symbol']} does not exist or data is unavailable")
            except Exception as e:
                logger.warning(f"Error selecting market {random_market['symbol']}: {str(e)}")
        logger.error("Failed to find an existing market after all attempts")
        raise ValueError("All markets are unavailable or do not exist")

    def start_trading(self) -> None:
        while True:
            df_markets = pd.read_excel(f"{DATA_DIR}/active_pairs.xlsx")
            if df_markets.empty:
                logger.warning("No markets found in active_pairs.xlsx. Stopping trading loop.")
                break
            
            pair_data = self.select_market_data(df_markets)

            accounts_per_trade = self.get_random_from_range("accounts_per_trade")
            n_accounts_long = accounts_per_trade // 2
            n_accounts_short = accounts_per_trade - n_accounts_long
            order_value = self.get_random_from_range("order_value_usd")
            order_duration = self.get_random_from_range("order_duration_min")

            max_order_value = self.get_max_order_value()
            order_value = min(order_value, max_order_value)

            token = pair_data["base_currency"]
            current_price = get_pair_price(token)

            long_distr, short_distr = calc_value_distribution(
                order_value * min(n_accounts_long, n_accounts_short),
                n_accounts_long,
                n_accounts_short,
                pair_data["base_currency"],
                current_price,
                self.config["orders_distribution_noise"]
            )

            logger.info(
                f"Starting trade | Market: {pair_data['symbol']} | "
                f"Long accounts: {len(long_distr)} | Short accounts: {len(short_distr)} | "
                f"Order: ${order_value} | Duration: {order_duration} min"
            )

            try:
                self.open_positions(long_distr, short_distr, pair_data["symbol"])
            except RuntimeError as e:
                logger.error(f"Aborting trading session: {e}")
                break

            logger.info(f"All positions are opened. Waiting {order_duration} minutes before closing...")
            logger.debug(f"Calling monitor_ltv with order_duration = {order_duration} (type: {type(order_duration)})")
            self.monitor_ltv(order_duration)
            self.close_all_positions()
            delay_between_cycles = self.get_random_from_range("delay_between_trading_cycles_min")
            logger.info(f"Waiting {delay_between_cycles} minutes before starting the next trading cycle...")
            time.sleep(delay_between_cycles * 60)

    def get_max_order_value(self) -> float:
        update_accounts_info()

        max_order_value = float(self.config["order_value_usd"]["max"])
        max_account_leverage = float(self.config["max_leverage"])

        self.df_accounts = pd.read_excel(f"{DATA_DIR}/accounts.xlsx")
        max_order_value_corrected = max_order_value

        for x in range(self.df_accounts.shape[0]):
            data = self.df_accounts.iloc[x]
            short_pk = str(data["private_key"])[:10]

            if not data.get("is_active", False):
                continue

            if data.get("position_market") and not pd.isnull(data["position_market"]):
                logger.error(f"[{short_pk}] Position already opened: {data['position_market']}. Stopping code..")
                raise ValueError("Opened positions are not allowed!")

            usdc_balance = float(data.get("USDC", 0.0))
            current_max_leverage = max_order_value / usdc_balance

            if current_max_leverage > max_account_leverage:
                corrected = usdc_balance * max_account_leverage
                if corrected < max_order_value_corrected:
                    max_order_value_corrected = corrected

        logger.debug(f"Max order value after checks: {round(max_order_value_corrected, 2)} $")
        return max_order_value_corrected

    def open_positions(self, long_dist: List[float], short_dist: List[float], market: str) -> None:
        df_accounts = self.df_accounts[self.df_accounts["is_active"] == True]

        n_long = len(long_dist)
        n_short = len(short_dist)
        n_total = n_long + n_short

        if n_total > len(df_accounts):
            raise ValueError(f"Not enough active accounts: need {n_total}, have {len(df_accounts)}")

        df_shuffled = df_accounts.sample(frac=1).reset_index(drop=True).iloc[:n_total]
        actions = ["long"] * n_long + ["short"] * n_short
        random.shuffle(actions)

        for i, action in enumerate(actions):
            data = df_shuffled.iloc[i]
            proxy = data["proxy"]
            account = get_account(data["address"], data["private_key"])
            pk = hex(account.signer.private_key)
            side = "BUY" if action == "long" else "SELL"
            size = str(long_dist.pop()) if action == "long" else str(short_dist.pop())

            success = False
            for attempt in range(1, self.retries + 1):
                try:
                    open_position(account, side, market, size, proxy)
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"[{pk[:10]}] Attempt {attempt}/{self.retries} to open {side} position failed: {e}")
                    time.sleep(1)

            if not success:
                logger.error(f"[{pk[:10]}] All {self.retries} attempts to open position failed. Aborting.")
                self.close_all_positions()
                raise RuntimeError(f"[{pk[:10]}] Unable to open position after {self.retries} attempts.")

            delay = self.get_random_from_range("delay_between_opening_orders_sec")
            logger.info(f"Waiting {round(delay, 1)} sec..")
            time.sleep(delay)

            last_position = self.get_last_position_info(account, proxy)
            try:
                liquidation_price = last_position.get("liquidation_price", 0)
            except:
                liquidation_price = 0
            update_state(pk, "position", "active")
            update_state(pk, "order_side", side)
            update_state(pk, "order_liq_price", liquidation_price)

    def close_all_positions(self) -> None:
        logger.info("Closing all open positions...")

        self.df_accounts = pd.read_excel(f"{DATA_DIR}/accounts.xlsx")
        df_active = self.df_accounts[self.df_accounts["is_active"] == True]
        df_active = df_active.sample(frac=1).reset_index(drop=True)

        for i in range(df_active.shape[0]):
            data = df_active.iloc[i]
            short_pk = str(data["private_key"])[:10]
            account = get_account(data["address"], data["private_key"])
            proxy = data["proxy"]
            pk = hex(account.signer.private_key)

            pos = self.get_last_position_info(account, proxy)

            if not pos:
                logger.info(f"[{short_pk}] All positions closed for this account")
                continue

            market = pos["market"]
            size = abs(float(pos["size"]))
            side = pos["side"].upper()
            close_side = "SELL" if side == "LONG" else "BUY"

            success = False
            for attempt in range(1, self.retries + 1):
                try:
                    open_position(account, close_side, market, str(size), proxy)
                    success = True
                    break
                except Exception as e:
                    logger.warning(f"[{short_pk}] Attempt {attempt}/{self.retries} to close {side} position failed: {e}")
                    time.sleep(1)

            if not success:
                logger.error(f"[{short_pk}] Failed to close {side} position after {self.retries} attempts.")
                continue

            delay = self.get_random_from_range("delay_between_opening_orders_sec")
            logger.info(f"[{short_pk}] Waiting {delay} sec before next...")
            update_state(pk, "position", "closed")
            time.sleep(delay)

    def get_last_position_info(self, account: Account, proxy: str) -> Optional[Dict[str, Any]]:
        position_data = _retry_request(get_open_positions, account, proxy)
        results = position_data.get("results", [])

        for pos in results:
            status = pos.get("status", "").upper()
            if status != "CLOSED":
                return pos

        return None

    def monitor_ltv(self, duration_min: int) -> None:
        logger.info("Starting LTV monitoring...")
        logger.debug(f"[monitor_ltv] duration_min argument = {duration_min} (type: {type(duration_min)})")

        end_time = time.time() + duration_min * 60
        logger.debug(f"monitor_ltv will end at {end_time} ({duration_min} min from now)")

        while time.time() < end_time:
            try:
                state: Dict[str, Dict[str, Any]] = get_user_state()

                for pk, info in state.items():
                    if info.get("position") != "active":
                        continue

                    side = info.get("order_side", "").upper()
                    liq_price = info.get("order_liq_price", 0.0)
                    last_order = info.get("last_order", {})
                    market = last_order.get("market", "")

                    if not market or "-" not in market:
                        continue

                    base_token = market.split("-")[0]
                    current_price = get_pair_price(base_token)

                    if isinstance(liq_price, str):
                        liq_price = float(liq_price) if liq_price.strip() else 0.0

                    if liq_price == 0 or current_price == 0:
                        logger.debug(f"[{pk[:10]}] Skipping LTV calc: liq={liq_price}, current={current_price}")
                        continue

                    if side == "SELL":
                        ltv = current_price / liq_price
                    elif side == "BUY":
                        ltv = liq_price / current_price
                    else:
                        continue

                    ltv *= 100
                    ltv_rounded = round(ltv, 1)

                    logger.debug(f"[{pk[:10]}] LTV = {ltv_rounded}% | Side: {side} | Market: {market}")

                    if ltv > self.config["max_position_ltv"]:
                        logger.info(f"[{pk[:10]}] LTV = {ltv_rounded}% | Side: {side} | Market: {market}")
                        logger.warning(f"[{pk[:10]}] Max LTV exceeded — closing all positions.")
                        self.close_all_positions()
                        os._exit(0)

            except Exception as e:
                logger.warning(f"Error monitoring liquidity: {e}. The process continues")

            wait_time = self.get_random_from_range("ltv_checks_sec")
            logger.debug(f"Next LTV check in {round(wait_time, 0)} seconds...")
            time.sleep(wait_time)

        logger.info("LTV monitoring finished — duration elapsed.")
