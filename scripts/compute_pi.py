#!/usr/bin/env python3
"""Compute an arbitrary number of digits of pi using the Chudnovsky algorithm."""

import argparse
import decimal

DEFAULT_DIGITS: int = 100
CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_C_CUBED: int = CHUDNOVSKY_C**3
CHUDNOVSKY_LINEAR: int = 13591409
CHUDNOVSKY_LINEAR_STEP: int = 545140134
CHUDNOVSKY_SCALE: int = 426880
CHUDNOVSKY_SQRT_BASE: int = 10005
CHUDNOVSKY_DIGITS_PER_ITER: int = 14
DECIMAL_GUARD_DIGITS: int = 10


def _chudnovsky_m_ratio(k: int) -> decimal.Decimal:
    """Compute the multiplier ratio M_k / M_{k-1} for the Chudnovsky series.

    The multinomial term M_k / M_{k-1} = (6k)! / ((3k)! * (k!)^3) evaluated as
    a rolling ratio, which avoids computing large factorials directly.
    """
    numerator: int = (6 * k - 5) * (6 * k - 4) * (6 * k - 3) * (6 * k - 2) * (6 * k - 1) * (6 * k)
    denominator: int = (3 * k - 2) * (3 * k - 1) * (3 * k) * k * k * k
    return decimal.Decimal(numerator) / decimal.Decimal(denominator)


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal places using the iterative Chudnovsky series.

    The series converges at approximately 14 digits per iteration.
    Returns pi as a string truncated to num_digits decimal places.
    """
    decimal.getcontext().prec = num_digits + DECIMAL_GUARD_DIGITS

    num_iterations: int = num_digits // CHUDNOVSKY_DIGITS_PER_ITER + 1

    m: decimal.Decimal = decimal.Decimal(1)
    x: decimal.Decimal = decimal.Decimal(1)
    series_sum: decimal.Decimal = decimal.Decimal(CHUDNOVSKY_LINEAR)

    for k in range(1, num_iterations):
        m *= _chudnovsky_m_ratio(k)
        x *= decimal.Decimal(-CHUDNOVSKY_C_CUBED)
        linear_term: decimal.Decimal = decimal.Decimal(CHUDNOVSKY_LINEAR + CHUDNOVSKY_LINEAR_STEP * k)
        series_sum += m * linear_term / x

    scale: decimal.Decimal = decimal.Decimal(CHUDNOVSKY_SCALE) * decimal.Decimal(CHUDNOVSKY_SQRT_BASE).sqrt()
    pi: decimal.Decimal = scale / series_sum

    pi_str: str = str(pi)
    dot_index: int = pi_str.index(".")
    truncated: str = pi_str[: dot_index + 1 + num_digits]
    return truncated


def parse_args() -> int:
    """Parse CLI arguments and return the requested digit count."""
    parser = argparse.ArgumentParser(
        description="Compute and print an arbitrary number of digits of pi."
    )
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=DEFAULT_DIGITS,
        help=f"Number of decimal digits of pi to compute (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    return int(args.digits)


def main() -> None:
    """Entry point: parse arguments, compute pi, and print the result."""
    num_digits: int = parse_args()
    pi_str: str = compute_pi(num_digits)
    print(pi_str)


if __name__ == "__main__":
    main()
