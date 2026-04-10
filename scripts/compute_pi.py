import argparse
import decimal
import math

DEFAULT_DIGITS: int = 100
PRECISION_GUARD_DIGITS: int = 15
RAMANUJAN_FACTOR: int = 9801
RAMANUJAN_CONSTANT: int = 1103
RAMANUJAN_LINEAR: int = 26390
RAMANUJAN_BASE: int = 396
RAMANUJAN_SQRT_ARG: int = 2
RAMANUJAN_SQRT_COEFF: int = 2
DIGITS_PER_TERM: float = 8.0


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal places using Ramanujan's series."""
    decimal.getcontext().prec = num_digits + PRECISION_GUARD_DIGITS

    num_terms: int = int(num_digits / DIGITS_PER_TERM) + 1
    series_sum: decimal.Decimal = decimal.Decimal(0)

    for k in range(num_terms):
        numerator = decimal.Decimal(math.factorial(4 * k)) * decimal.Decimal(
            RAMANUJAN_CONSTANT + RAMANUJAN_LINEAR * k
        )
        denominator = (
            decimal.Decimal(math.factorial(k) ** 4)
            * decimal.Decimal(RAMANUJAN_BASE ** (4 * k))
        )
        series_sum += numerator / denominator

    leading_coefficient = (
        decimal.Decimal(RAMANUJAN_SQRT_COEFF)
        * decimal.Decimal(RAMANUJAN_SQRT_ARG).sqrt()
        / decimal.Decimal(RAMANUJAN_FACTOR)
    )
    pi = decimal.Decimal(1) / (leading_coefficient * series_sum)

    return _truncate_to_digits(str(pi), num_digits)


def _truncate_to_digits(pi_str: str, num_digits: int) -> str:
    """Truncate pi string to num_digits significant decimal places."""
    dot_index = pi_str.find(".")
    if dot_index == -1:
        return pi_str[:num_digits]
    return pi_str[: dot_index + num_digits + 1]


def main() -> None:
    """Parse CLI arguments and print pi to the requested number of digits."""
    parser = argparse.ArgumentParser(
        description="Compute digits of pi using the Ramanujan algorithm."
    )
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=DEFAULT_DIGITS,
        help=f"Number of digits to compute (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    print(compute_pi(args.digits))


if __name__ == "__main__":
    main()
