import argparse
from decimal import Decimal, getcontext

RAMANUJAN_CONSTANT = 1103
RAMANUJAN_LINEAR_MULTIPLIER = 26390
RAMANUJAN_BASE = 396
RAMANUJAN_PREFACTOR_NUMERATOR = 2
RAMANUJAN_PREFACTOR_DENOMINATOR = 9801
RAMANUJAN_DIGITS_PER_TERM = 8
DECIMAL_GUARD_DIGITS = 15


def parse_args() -> int:
    parser = argparse.ArgumentParser(description="Compute digits of pi using the Ramanujan series.")
    parser.add_argument("num_digits", type=int, help="Number of decimal places of pi to compute")
    args = parser.parse_args()
    if args.num_digits < 1:
        raise SystemExit("num_digits must be >= 1")
    return int(args.num_digits)


def compute_pi(num_decimal_places: int) -> str:
    getcontext().prec = num_decimal_places + DECIMAL_GUARD_DIGITS + 1

    num_terms = num_decimal_places // RAMANUJAN_DIGITS_PER_TERM + 1

    product_term = Decimal(1)
    total_sum = Decimal(RAMANUJAN_CONSTANT)

    for k in range(1, num_terms + 1):
        four_k = 4 * k
        numerator = four_k * (four_k - 1) * (four_k - 2) * (four_k - 3)
        denominator = k**4 * RAMANUJAN_BASE**4
        product_term = product_term * Decimal(numerator) / Decimal(denominator)
        linear = Decimal(RAMANUJAN_CONSTANT + RAMANUJAN_LINEAR_MULTIPLIER * k)
        total_sum += linear * product_term

    prefactor = Decimal(RAMANUJAN_PREFACTOR_NUMERATOR) * Decimal(2).sqrt() / Decimal(RAMANUJAN_PREFACTOR_DENOMINATOR)
    pi = Decimal(1) / (prefactor * total_sum)

    pi_str = str(pi)
    dot_pos = pi_str.index(".")
    return pi_str[: dot_pos + 1 + num_decimal_places]


def main() -> None:
    num_digits = parse_args()
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
