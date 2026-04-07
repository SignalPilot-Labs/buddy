import argparse
import decimal

from constants import (
    DEFAULT_DIGITS,
    GUARD_DIGITS,
    RAMANUJAN_BASE,
    RAMANUJAN_DIGITS_PER_TERM,
    RAMANUJAN_LINEAR_BASE,
    RAMANUJAN_LINEAR_STEP,
    RAMANUJAN_PREFACTOR_DENOM,
    RAMANUJAN_SQRT_FACTOR,
)


def compute_pi(num_digits: int) -> str:
    decimal.getcontext().prec = num_digits + GUARD_DIGITS

    base_power_4 = decimal.Decimal(RAMANUJAN_BASE ** 4)
    total = decimal.Decimal(RAMANUJAN_LINEAR_BASE)
    term_factor = decimal.Decimal(1)
    num_terms = num_digits // RAMANUJAN_DIGITS_PER_TERM + 2

    for k in range(1, num_terms):
        four_k = 4 * k
        numerator_update = (
            decimal.Decimal(four_k * (four_k - 1) * (four_k - 2) * (four_k - 3))
        )
        denominator_update = decimal.Decimal(k) ** 4 * base_power_4
        term_factor *= numerator_update / denominator_update
        linear_part = decimal.Decimal(
            RAMANUJAN_LINEAR_BASE + RAMANUJAN_LINEAR_STEP * k
        )
        total += term_factor * linear_part

    prefactor = (
        decimal.Decimal(RAMANUJAN_SQRT_FACTOR).sqrt()
        * decimal.Decimal(2)
        / decimal.Decimal(RAMANUJAN_PREFACTOR_DENOM)
    )
    pi = 1 / (prefactor * total)
    pi_str = str(pi)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + 1 + num_digits]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute digits of pi")
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=DEFAULT_DIGITS,
        help="Number of decimal digits to compute",
    )
    args = parser.parse_args()
    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
