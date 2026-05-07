#!/usr/bin/env python3
"""Compute the first 100 digits of pi using Ramanujan's series."""

from decimal import Decimal, getcontext

PRECISION = 120  # Extra precision for intermediate calculations
DIGITS_TO_DISPLAY = 100
RAMANUJAN_CONSTANT = 9801  # Denominator of leading factor
RAMANUJAN_LINEAR = 26390   # Coefficient of k in numerator
RAMANUJAN_BASE = 1103      # Constant term in numerator
RAMANUJAN_POWER_BASE = 396  # Base for 396^(4k)
NUM_TERMS = 15  # Each term adds ~8 digits; 15 terms > 100 digits


def factorial(n: int) -> int:
    """Compute n! iteratively."""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def compute_pi() -> Decimal:
    """Compute pi using Ramanujan's series: 1/pi = (2*sqrt(2)/9801) * sum."""
    getcontext().prec = PRECISION
    sqrt_2 = Decimal(2).sqrt()
    leading = (Decimal(2) * sqrt_2) / Decimal(RAMANUJAN_CONSTANT)
    sum_result = Decimal(0)
    for k in range(NUM_TERMS):
        numerator = factorial(4 * k) * (RAMANUJAN_BASE + RAMANUJAN_LINEAR * k)
        denominator = (factorial(k) ** 4) * (RAMANUJAN_POWER_BASE ** (4 * k))
        sum_result += Decimal(numerator) / Decimal(denominator)
    return Decimal(1) / (leading * sum_result)


def main() -> None:
    pi = compute_pi()
    pi_str = str(pi)
    # Format: 3.14159... (100 digits total = 1 before decimal + 99 after)
    output = pi_str[: DIGITS_TO_DISPLAY + 1]  # +1 for decimal point
    print(output)


if __name__ == "__main__":
    main()
