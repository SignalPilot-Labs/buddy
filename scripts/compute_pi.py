import argparse
import math
from decimal import Decimal, getcontext

from constants import (
    DEFAULT_DIGIT_COUNT,
    DIGITS_PER_TERM,
    EXTRA_PRECISION_DIGITS,
    RAMANUJAN_BASE,
    RAMANUJAN_DIVISOR,
    RAMANUJAN_LINEAR,
    RAMANUJAN_POWER_BASE,
    RAMANUJAN_SQRT_COEFF,
    SCRIPT_DESCRIPTION,
)


def _compute_sum(num_terms: int) -> Decimal:
    total = Decimal(0)
    for k in range(num_terms):
        factorial_4k = Decimal(math.factorial(4 * k))
        factorial_k = Decimal(math.factorial(k))
        power_base_4k = Decimal(RAMANUJAN_POWER_BASE) ** (4 * k)

        numerator = factorial_4k * (RAMANUJAN_BASE + RAMANUJAN_LINEAR * k)
        denominator = factorial_k ** 4 * power_base_4k
        total += numerator / denominator

    return total


def compute_pi(num_digits: int) -> str:
    precision = num_digits + EXTRA_PRECISION_DIGITS
    getcontext().prec = precision

    num_terms = num_digits // DIGITS_PER_TERM + 2
    series_sum = _compute_sum(num_terms)

    sqrt2 = Decimal(2).sqrt()
    prefactor = Decimal(RAMANUJAN_SQRT_COEFF) * sqrt2 / Decimal(RAMANUJAN_DIVISOR)
    inverse_pi = prefactor * series_sum
    pi = Decimal(1) / inverse_pi

    pi_str = str(pi)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + 1 + num_digits]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument(
        "--digits",
        type=int,
        default=DEFAULT_DIGIT_COUNT,
        help=f"Number of decimal digits to compute (default: {DEFAULT_DIGIT_COUNT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
