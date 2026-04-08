import argparse
import decimal
import math

from scripts.pi_constants import (
    A_LINEAR,
    A_NUMERATOR,
    B_CUBIC,
    C,
    C_SQRT_RADICAND,
    DEFAULT_DIGITS,
    DIGITS_PER_TERM,
    EXTRA_PRECISION_DIGITS,
)


def _chudnovsky_sum(num_terms: int) -> tuple[int, int]:
    """Return (numerator, denominator) of the Chudnovsky series partial sum."""
    numerator_sum = 0
    denominator_sum = 1
    for k in range(num_terms):
        six_k_fact = math.factorial(6 * k)
        three_k_fact = math.factorial(3 * k)
        k_fact_cubed = math.factorial(k) ** 3
        linear_term = A_NUMERATOR + A_LINEAR * k
        sign = 1 if k % 2 == 0 else -1
        term_num = sign * six_k_fact * linear_term
        term_den = three_k_fact * k_fact_cubed * (B_CUBIC**k)
        numerator_sum = numerator_sum * term_den + term_num * denominator_sum
        denominator_sum = denominator_sum * term_den
    return numerator_sum, denominator_sum


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal digits using the Chudnovsky algorithm."""
    precision = num_digits + EXTRA_PRECISION_DIGITS
    decimal.getcontext().prec = precision

    num_terms = math.ceil(num_digits / DIGITS_PER_TERM) + 1
    series_num, series_den = _chudnovsky_sum(num_terms)

    d_series_num = decimal.Decimal(series_num)
    d_series_den = decimal.Decimal(series_den)
    d_c = decimal.Decimal(C)
    d_sqrt = decimal.Decimal(C_SQRT_RADICAND).sqrt()

    # pi = (C * sqrt(C_SQRT_RADICAND) * series_den) / series_num
    pi_value = (d_c * d_sqrt * d_series_den) / d_series_num

    pi_str = str(pi_value)
    # Format: "3.14159..." — keep "3." plus num_digits digits
    dot_index = pi_str.index(".")
    full_digits = pi_str[: dot_index + 1 + num_digits]
    return full_digits


def parse_args() -> int:
    """Parse CLI arguments and return the requested digit count."""
    parser = argparse.ArgumentParser(
        description="Compute digits of pi using the Chudnovsky algorithm.",
        usage="python -m scripts.pi [digits]",
    )
    parser.add_argument(
        "digits",
        nargs="?",
        type=int,
        default=DEFAULT_DIGITS,
        help=f"Number of digits to compute (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    return int(args.digits)


if __name__ == "__main__":
    requested_digits = parse_args()
    result = compute_pi(requested_digits)
    print(result)
