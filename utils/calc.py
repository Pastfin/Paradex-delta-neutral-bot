import numpy as np
import random
from decimal import Decimal, getcontext

from src.config.constants import logger
from src.paradex.market import get_pair_data
from utils.data import USER_CONFIG

getcontext().prec = 32


def calc_value_distribution(
    nominal_value: int,
    n_accounts_long: int,
    n_accounts_short: int,
    token: str,
    current_price: float,
    noise: float
) -> tuple:
    pair_data = get_pair_data(token)
    min_notional = int(pair_data["min_notional"])
    precision = Decimal(str(pair_data["order_size_increment"]))
    min_token_amount = calc_min_token_amount(min_notional, current_price, precision)

    max_token_amount = resize_amount(
        Decimal(str(nominal_value)) / Decimal(str(current_price)), precision
    )

    if max_token_amount < min_token_amount:
        logger.error(f"Order size is too low ({nominal_value} USD) for token: {token}")
        raise ValueError("Order size error")

    max_accounts_per_order = int(max_token_amount / min_token_amount)

    n_accounts_long = min(n_accounts_long, max_accounts_per_order)
    n_accounts_short = min(n_accounts_short, max_accounts_per_order)
    min_accounts_total = USER_CONFIG["accounts_per_trade"]["min"]

    while n_accounts_long + n_accounts_short < min_accounts_total:
        if n_accounts_long > n_accounts_short:
            n_accounts_long += 1
        elif n_accounts_short > n_accounts_long:
            n_accounts_short += 1
        else:
            if random.choice([True, False]):
                n_accounts_long += 1
            else:
                n_accounts_short += 1
        if n_accounts_long > max_accounts_per_order:
            n_accounts_long -= 1
            n_accounts_short += 1
        elif n_accounts_short > max_accounts_per_order:
            n_accounts_short -= 1
            n_accounts_long += 1

    if n_accounts_long + n_accounts_short < min_accounts_total:
        required_nominal = min_notional * min_accounts_total
        logger.warning(
            f"Nominal value {nominal_value} USD too low to support {min_accounts_total} accounts. "
            f"Minimum required: {required_nominal} USD"
        )
        raise ValueError(f"Nominal value too low for {min_accounts_total} accounts")

    avg_token_amount_long = max_token_amount / Decimal(n_accounts_long)
    avg_token_amount_short = max_token_amount / Decimal(n_accounts_short)

    noise_scale = Decimal(str(noise))

    noise_long = np.random.normal(
        loc=0.0,
        scale=float(avg_token_amount_long * noise_scale),
        size=n_accounts_long
    )
    distr_amount_long = [avg_token_amount_long + Decimal(str(n)) for n in noise_long]
    distr_amount_long = [resize_amount(x, precision) for x in distr_amount_long]
    distr_amount_long_corrected = correct_distribution(
        distr_amount_long, max_token_amount, min_token_amount, precision
    )

    noise_short = np.random.normal(
        loc=0.0,
        scale=float(avg_token_amount_short * noise_scale),
        size=n_accounts_short
    )
    distr_amount_short = [avg_token_amount_short + Decimal(str(n)) for n in noise_short]
    distr_amount_short = [resize_amount(x, precision) for x in distr_amount_short]
    distr_amount_short_corrected = correct_distribution(
        distr_amount_short, max_token_amount, min_token_amount, precision
    )

    logger.debug(
        f"\nToken: {token} | Nominal value: {nominal_value} USD | Price: {current_price}\n"
        f"Min notional: {min_notional} | Precision: {precision} | Min token amount: {min_token_amount}\n"
        f"Max token amount: {max_token_amount} | Max accounts per order: {max_accounts_per_order}\n"
        f"Accounts long: {n_accounts_long}, short: {n_accounts_short}\n"
        f"Avg long amount: {avg_token_amount_long}, avg short amount: {avg_token_amount_short}\n"
        f"Initial long sum: {sum(distr_amount_long):.8f}, Initial short sum: {sum(distr_amount_short):.8f}"
    )

    logger.debug(f"[LONG] Distribution: {[float(x) for x in distr_amount_long_corrected]}")
    logger.debug(
        f"Total long amount: {float(sum(distr_amount_long_corrected)):.4f} "
        f"vs max allowed: {float(max_token_amount):.4f}"
    )

    logger.debug(f"[SHORT] Distribution: {[float(x) for x in distr_amount_short_corrected]}")
    logger.debug(
        f"Total short amount: {float(sum(distr_amount_short_corrected)):.4f} "
        f"vs max allowed: {float(max_token_amount):.4f}"
    )

    return distr_amount_long_corrected, distr_amount_short_corrected


def correct_distribution(
    distribution: list,
    max_amount_allowed: Decimal,
    min_amount_allowed: Decimal,
    precision: Decimal
) -> list:
    for x in range(1_000_000):
        random.shuffle(distribution)
        for i in range(len(distribution)):
            amount = distribution[i]
            if amount < min_amount_allowed:
                distribution[i] = min_amount_allowed
            elif sum(distribution) > max_amount_allowed and amount > min_amount_allowed:
                distribution[i] -= precision
            elif sum(distribution) + precision <= max_amount_allowed:
                distribution[i] += precision
            distribution[i] = resize_amount(distribution[i], precision)

        if sum(distribution) == max_amount_allowed:
            logger.debug(f"Distribution corrected after {x} iterations")
            return distribution

    total = sum(distribution)
    logger.error(f"Failed to correct distribution: total={total} vs expected={max_amount_allowed}")
    raise ValueError("Cannot correct distribution: target sum not reached")


def calc_min_token_amount(
    min_notional: int,
    current_price: float,
    precision: Decimal
) -> Decimal:
    min_amount = Decimal(str(min_notional)) / Decimal(str(current_price))
    return resize_up_amount(min_amount, precision)


def resize_amount(
    amount: Decimal,
    precision: Decimal
) -> Decimal:
    return (amount // precision) * precision


def resize_up_amount(
    amount: Decimal,
    precision: Decimal
) -> Decimal:
    return ((amount + precision - Decimal("1E-32")) // precision) * precision