#!/usr/bin/env python3
"""Compute digits of pi using Ramanujan's 1914 series."""

import argparse
import sys
from decimal import Decimal, getcontext

# Constants for Ramanujan's 1914 series:
# 1/π = (2√2/9801) × Σ(k=0 to ∞) [(4k)!(1103 + 26390k)] / [(k!)^4 × 396^(4k)]
RAMANUJAN_CONSTANT_A = 1103
RAMANUJAN_CONSTANT_B = 26390
RAMANUJAN_CONSTANT_C = 396
RAMANUJAN_DENOMINATOR = 9801
RAMANUJAN_SQRT_MULTIPLIER = 2

# Extra precision digits to guard against rounding errors in intermediate steps
PRECISION_GUARD_DIGITS = 15

# Minimum number of digits allowed
MIN_DIGITS = 1


def compute_ramanujan_term(k: int) -> Decimal:
    """Compute the k-th term of the Ramanujan series numerator and denominator."""
    four_k = 4 * k
    four_k_factorial = factorial_decimal(four_k)
    k_factorial_fourth = factorial_decimal(k) ** 4
    linear = Decimal(RAMANUJAN_CONSTANT_A + RAMANUJAN_CONSTANT_B * k)
    power = Decimal(RAMANUJAN_CONSTANT_C) ** (4 * k)
    return (four_k_factorial * linear) / (k_factorial_fourth * power)


def factorial_decimal(n: int) -> Decimal:
    """Compute n! as a Decimal."""
    result = Decimal(1)
    for i in range(2, n + 1):
        result *= Decimal(i)
    return result


def compute_pi(num_digits: int) -> Decimal:
    """Compute pi to the requested number of decimal digits using Ramanujan's series."""
    working_precision = num_digits + PRECISION_GUARD_DIGITS
    getcontext().prec = working_precision

    # Number of series terms needed: each term contributes ~8 digits
    num_terms = num_digits // 8 + 2

    series_sum = Decimal(0)
    for k in range(num_terms):
        series_sum += compute_ramanujan_term(k)

    sqrt2 = Decimal(2).sqrt()
    factor = (Decimal(RAMANUJAN_SQRT_MULTIPLIER) * sqrt2) / Decimal(RAMANUJAN_DENOMINATOR)
    reciprocal_pi = factor * series_sum

    return Decimal(1) / reciprocal_pi


def format_pi(pi_value: Decimal, num_digits: int) -> str:
    """Format a Decimal pi value as a string with the requested number of digits after the decimal point."""
    pi_str = str(pi_value)
    # pi_str is like "3.14159..."
    dot_index = pi_str.index(".")
    integer_part = pi_str[:dot_index]
    fractional_part = pi_str[dot_index + 1 :]
    fractional_part = fractional_part[:num_digits]
    return f"{integer_part}.{fractional_part}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Compute digits of pi using Ramanujan's 1914 series.")
    parser.add_argument(
        "digits",
        type=int,
        help=f"Number of decimal digits to compute (minimum {MIN_DIGITS})",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    """Entry point: parse args, compute pi, and print result."""
    args = parse_args(argv)
    if args.digits < MIN_DIGITS:
        print(f"Error: digits must be at least {MIN_DIGITS}", file=sys.stderr)
        sys.exit(1)

    pi_value = compute_pi(args.digits)
    print(format_pi(pi_value, args.digits))


if __name__ == "__main__":
    main(sys.argv[1:])
