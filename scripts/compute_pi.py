#!/usr/bin/env python3
"""Compute the first 100 digits of pi using the Chudnovsky algorithm."""

from decimal import Decimal, getcontext

DIGITS = 100
PRECISION = DIGITS + 10


def factorial(n: int) -> int:
    """Compute factorial of n."""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def compute_pi(num_digits: int) -> Decimal:
    """Compute pi to the specified number of digits using Chudnovsky algorithm."""
    getcontext().prec = num_digits + 20

    c = 426880 * Decimal(10005).sqrt()
    k_sum = Decimal(0)

    for k in range(num_digits):
        numerator = factorial(6 * k) * (13591409 + 545140134 * k)
        denominator = factorial(3 * k) * (factorial(k) ** 3) * (-262537412640768000) ** k
        k_sum += Decimal(numerator) / Decimal(denominator)

        if k > 0 and abs(Decimal(numerator) / Decimal(denominator)) < Decimal(10) ** (-(num_digits + 10)):
            break

    pi = c / k_sum
    return pi


def main() -> None:
    """Main entry point."""
    pi = compute_pi(DIGITS)
    pi_str = str(pi)[:DIGITS + 2]
    print(f"First {DIGITS} digits of pi:")
    print(pi_str)


if __name__ == "__main__":
    main()
