"""Compute N digits of pi using the Chudnovsky algorithm."""

import math
import sys
from decimal import Decimal, getcontext

from scripts.constants import (
    CHUDNOVSKY_C,
    CHUDNOVSKY_C_RADICAND,
    CHUDNOVSKY_DIVISOR,
    CHUDNOVSKY_K_BASE,
    CHUDNOVSKY_K_COEFF,
    EXIT_CODE_INVALID_INPUT,
    EXTRA_PRECISION_DIGITS,
    MIN_DIGITS,
)


def compute_chudnovsky_term(k: int) -> Decimal:
    """Compute the k-th term of the Chudnovsky series."""
    numerator = Decimal(math.factorial(6 * k)) * (
        CHUDNOVSKY_K_BASE + CHUDNOVSKY_K_COEFF * k
    )
    denominator = (
        Decimal(math.factorial(3 * k))
        * Decimal(math.factorial(k)) ** 3
        * Decimal(CHUDNOVSKY_DIVISOR) ** k
    )
    return numerator / denominator


def compute_pi(num_digits: int, extra_precision: int) -> str:
    """Compute pi to num_digits decimal places using the Chudnovsky algorithm.

    Returns a string of the form "3.14159..." with exactly num_digits digits
    after the decimal point.
    """
    precision = num_digits + extra_precision
    getcontext().prec = precision

    threshold = Decimal(10) ** (-precision)

    series_sum = Decimal(0)
    k = 0
    while True:
        term = compute_chudnovsky_term(k)
        series_sum += term
        if abs(term) < threshold:
            break
        k += 1

    sqrt_term = Decimal(CHUDNOVSKY_C) * Decimal(CHUDNOVSKY_C_RADICAND).sqrt()
    pi_value = sqrt_term / series_sum

    pi_str = str(pi_value)
    dot_index = pi_str.index(".")
    available_decimal = len(pi_str) - dot_index - 1
    if available_decimal >= num_digits:
        return pi_str[: dot_index + 1 + num_digits]
    return pi_str


def parse_args(args: list[str]) -> int:
    """Parse CLI arguments. Returns requested digit count.

    Raises ValueError on invalid input (non-integer, zero, negative).
    """
    if len(args) != 1:
        raise ValueError(f"Expected exactly one argument, got {len(args)}")

    raw = args[0]
    if not raw.lstrip("-").isdigit():
        raise ValueError(f"Invalid digit count: {raw!r} is not an integer")

    digits = int(raw)
    if digits < MIN_DIGITS:
        raise ValueError(
            f"Invalid digit count: {digits} is less than minimum {MIN_DIGITS}"
        )
    return digits


def main() -> None:
    """Entry point: parse args, compute pi, print result."""
    try:
        num_digits = parse_args(sys.argv[1:])
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(EXIT_CODE_INVALID_INPUT)

    result = compute_pi(num_digits, EXTRA_PRECISION_DIGITS)
    print(result)


if __name__ == "__main__":
    main()
