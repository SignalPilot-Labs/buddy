import argparse
import decimal
import math

# Chudnovsky algorithm constants
CHUDNOVSKY_A = 13591409
CHUDNOVSKY_B = 545140134
CHUDNOVSKY_C = 640320
CHUDNOVSKY_C_EXPONENT = 3
CHUDNOVSKY_PREFACTOR = 12
ALTERNATING_SIGN_BASE = -1
DIGITS_PER_TERM = 14
GUARD_DIGITS = 10


def compute_pi(num_digits: int) -> str:
    precision = num_digits + GUARD_DIGITS
    decimal.getcontext().prec = precision

    num_terms = num_digits // DIGITS_PER_TERM + 1

    series_sum = decimal.Decimal(0)

    for k in range(num_terms):
        six_k_fact = math.factorial(6 * k)
        three_k_fact = math.factorial(3 * k)
        k_fact = math.factorial(k)

        numerator = decimal.Decimal(six_k_fact) * decimal.Decimal(CHUDNOVSKY_A + CHUDNOVSKY_B * k)
        denominator = decimal.Decimal(three_k_fact) * decimal.Decimal(k_fact ** CHUDNOVSKY_C_EXPONENT) * decimal.Decimal(CHUDNOVSKY_C) ** (CHUDNOVSKY_C_EXPONENT * k)
        sign = decimal.Decimal(ALTERNATING_SIGN_BASE) ** k
        series_sum += sign * numerator / denominator

    sqrt_c3 = (decimal.Decimal(CHUDNOVSKY_C) ** CHUDNOVSKY_C_EXPONENT).sqrt()
    pi = sqrt_c3 / (decimal.Decimal(CHUDNOVSKY_PREFACTOR) * series_sum)

    pi_str = str(pi)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + 1 + num_digits]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute N digits of pi using the Chudnovsky algorithm.")
    parser.add_argument("digits", type=int, nargs="?", default=None, help="Number of digits to compute (positive integer).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.digits is None:
        raise SystemExit("Error: number of digits argument is required.")
    if args.digits <= 0:
        raise SystemExit(f"Error: number of digits must be a positive integer, got {args.digits}.")
    print(compute_pi(args.digits))


if __name__ == "__main__":
    main()
