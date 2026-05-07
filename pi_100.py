#!/usr/bin/env python3
"""Compute the first 100 digits of pi using Machin's formula."""

from decimal import Decimal, getcontext

PRECISION = 110  # Extra precision to avoid rounding errors
DIGITS_TO_DISPLAY = 100


def arctan(x: Decimal, num_terms: int) -> Decimal:
    """Compute arctan(x) using Taylor series: arctan(x) = x - x^3/3 + x^5/5 - ..."""
    power = x
    result = power
    x_squared = x * x
    for i in range(1, num_terms):
        power *= -x_squared
        result += power / (2 * i + 1)
    return result


def compute_pi() -> Decimal:
    """Compute pi using Machin's formula: pi/4 = 4*arctan(1/5) - arctan(1/239)."""
    getcontext().prec = PRECISION
    one = Decimal(1)
    num_terms = 80  # Enough terms for 100+ digits
    pi_over_4 = 4 * arctan(one / 5, num_terms) - arctan(one / 239, num_terms)
    return 4 * pi_over_4


def main() -> None:
    pi = compute_pi()
    pi_str = str(pi)
    # Format: 3.14159... (100 digits total = 1 before decimal + 99 after)
    output = pi_str[: DIGITS_TO_DISPLAY + 1]  # +1 for decimal point
    print(output)


if __name__ == "__main__":
    main()
