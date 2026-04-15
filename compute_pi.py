import argparse
import sys
from decimal import Decimal, getcontext
from math import factorial

CHUDNOVSKY_A: int = 13591409
CHUDNOVSKY_B: int = 545140134
CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_MULTIPLIER: int = 12
DIGITS_PER_TERM: int = 14
GUARD_DIGITS: int = 20


def compute_pi(num_digits: int) -> str:
    precision = num_digits + GUARD_DIGITS
    getcontext().prec = precision

    num_terms = num_digits // DIGITS_PER_TERM + 1
    total: Decimal = Decimal(0)

    for k in range(num_terms):
        numerator = Decimal((-1) ** k * factorial(6 * k) * (CHUDNOVSKY_A + CHUDNOVSKY_B * k))
        denominator = Decimal(factorial(3 * k) * factorial(k) ** 3 * CHUDNOVSKY_C ** (3 * k))
        total += numerator / denominator

    # 1/pi = (12 / 640320^(3/2)) * sum
    # 640320^(3/2) = 640320 * sqrt(640320)
    c_decimal: Decimal = Decimal(CHUDNOVSKY_C)
    c_three_halves: Decimal = c_decimal * c_decimal.sqrt()
    pi_inverse: Decimal = Decimal(CHUDNOVSKY_MULTIPLIER) / c_three_halves * total
    pi: Decimal = Decimal(1) / pi_inverse

    pi_str = str(pi)
    dot_index = pi_str.index(".")
    available_decimals = len(pi_str) - dot_index - 1
    if available_decimals >= num_digits:
        return pi_str[: dot_index + 1 + num_digits]
    return pi_str


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute N digits of pi using the Chudnovsky algorithm.")
    parser.add_argument("digits", type=int, help="Number of decimal digits to compute.")
    args = parser.parse_args()

    if args.digits < 1:
        print("Error: digits must be at least 1.", file=sys.stderr)
        sys.exit(1)

    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
