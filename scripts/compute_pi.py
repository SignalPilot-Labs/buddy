"""Compute digits of pi using Ramanujan's 1914 series.

Formula:
    1/pi = (2*sqrt(2)/9801) * sum_{k=0}^inf (4k)! * (1103 + 26390*k) / ((k!)^4 * 396^(4k))
"""

import argparse
import sys
from decimal import Decimal, getcontext

from scripts.constants import (
    EXTRA_PRECISION_DIGITS,
    RAMANUJAN_CONSTANT_TERM,
    RAMANUJAN_DENOMINATOR_BASE,
    RAMANUJAN_EXTRA_TERMS,
    RAMANUJAN_LINEAR_COEFFICIENT,
    RAMANUJAN_SERIES_BASE,
)


def _ramanujan_sum(num_digits: int) -> Decimal:
    """Compute the Ramanujan series partial sum with sufficient terms for num_digits."""
    total = Decimal(0)
    # Each term contributes ~8 digits; add extra terms for safety
    num_terms = num_digits // 8 + RAMANUJAN_EXTRA_TERMS

    factorial_4k = 1  # (4k)!
    factorial_k = 1   # (k!)^4 — tracked as k! then raised to 4th power per term
    power_396 = 1     # 396^(4k)

    for k in range(num_terms):
        if k == 0:
            numerator = Decimal(RAMANUJAN_CONSTANT_TERM)
            denominator = Decimal(1)
        else:
            # Update (4k)! incrementally: multiply by (4k-3)(4k-2)(4k-1)(4k)
            four_k = 4 * k
            factorial_4k *= (four_k - 3) * (four_k - 2) * (four_k - 1) * four_k
            # Update (k!)^4 incrementally
            factorial_k *= k
            # Update 396^(4k) = 396^(4*(k-1)) * 396^4
            power_396 *= RAMANUJAN_SERIES_BASE ** 4

            numerator = Decimal(factorial_4k) * Decimal(
                RAMANUJAN_CONSTANT_TERM + RAMANUJAN_LINEAR_COEFFICIENT * k
            )
            denominator = Decimal(factorial_k ** 4) * Decimal(power_396)

        total += numerator / denominator

    return total


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal places using Ramanujan's 1914 series.

    Raises ValueError if num_digits < 1.
    Returns a string of the form "3.14159..." with exactly num_digits digits after the dot.
    """
    if num_digits < 1:
        raise ValueError(f"num_digits must be at least 1, got {num_digits}")

    precision = num_digits + EXTRA_PRECISION_DIGITS
    getcontext().prec = precision

    series_sum = _ramanujan_sum(num_digits)

    # 1/pi = (2*sqrt(2)/9801) * series_sum
    # => pi = 9801 / (2*sqrt(2)*series_sum)
    two_sqrt2 = 2 * Decimal(2).sqrt()
    pi = Decimal(RAMANUJAN_DENOMINATOR_BASE) / (two_sqrt2 * series_sum)

    # Format: "3." + num_digits decimal digits
    # quantize to num_digits places then convert to string
    pi_str = str(pi)

    # pi_str looks like "3.14159265..." — slice to keep exactly num_digits decimals
    dot_index = pi_str.index(".")
    end_index = dot_index + 1 + num_digits
    return pi_str[:end_index]


def parse_args(argv: list[str]) -> int:
    """Parse CLI arguments and return the requested digit count."""
    parser = argparse.ArgumentParser(
        description="Compute digits of pi using Ramanujan's 1914 series."
    )
    parser.add_argument(
        "digits",
        type=int,
        help="Number of decimal digits of pi to compute",
    )
    args = parser.parse_args(argv)
    return int(args.digits)


def main() -> None:
    """Entry point: parse args, compute pi, print result."""
    num_digits = parse_args(sys.argv[1:])
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
