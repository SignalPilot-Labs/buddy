import argparse
import decimal

from scripts.pi_constants import (
    DEFAULT_DIGITS,
    RAMANUJAN_BASE,
    RAMANUJAN_COEFFICIENT_DENOMINATOR,
    RAMANUJAN_COEFFICIENT_NUMERATOR,
    RAMANUJAN_CONSTANT_TERM,
    RAMANUJAN_LINEAR_TERM,
)

_EXTRA_PRECISION: int = 50
_CONVERGENCE_BUFFER: int = 10


def _set_precision(num_digits: int) -> None:
    decimal.getcontext().prec = num_digits + _EXTRA_PRECISION


def _factorial_ratio_4k(k: int) -> int:
    """Return (4k)! / (4(k-1))! = product of integers from 4k-3 to 4k."""
    result = 1
    start = 4 * (k - 1) + 1
    for i in range(start, 4 * k + 1):
        result *= i
    return result


def _compute_series_sum(num_digits: int) -> decimal.Decimal:
    """Sum the Ramanujan series: sum_k ((4k)! * (1103 + 26390k)) / ((k!)^4 * 396^(4k))."""
    threshold = decimal.Decimal(10) ** (-(num_digits + _CONVERGENCE_BUFFER))
    base_power_4 = RAMANUJAN_BASE ** 4
    total = decimal.Decimal(0)
    k = 0
    factorial_4k: int = 1
    factorial_k: int = 1
    power_base: int = 1

    while True:
        numerator = factorial_4k * (RAMANUJAN_CONSTANT_TERM + RAMANUJAN_LINEAR_TERM * k)
        denominator = (factorial_k ** 4) * power_base
        term = decimal.Decimal(numerator) / decimal.Decimal(denominator)
        total += term
        if term < threshold:
            break
        k += 1
        factorial_4k *= _factorial_ratio_4k(k)
        factorial_k *= k
        power_base *= base_power_4

    return total


def compute_pi(num_digits: int) -> str:
    """Compute pi to the specified number of decimal digits."""
    _set_precision(num_digits)
    series_sum = _compute_series_sum(num_digits)
    sqrt_2 = decimal.Decimal(2).sqrt()
    coefficient = decimal.Decimal(RAMANUJAN_COEFFICIENT_NUMERATOR) * sqrt_2 / decimal.Decimal(RAMANUJAN_COEFFICIENT_DENOMINATOR)
    pi_value = decimal.Decimal(1) / (coefficient * series_sum)
    pi_str = str(pi_value)
    dot_index = pi_str.index(".")
    integer_part = pi_str[:dot_index]
    decimal_part = pi_str[dot_index + 1:]
    return f"{integer_part}.{decimal_part[:num_digits]}"


def main() -> None:
    """Parse args and print computed pi."""
    parser = argparse.ArgumentParser(
        description="Compute digits of pi using Ramanujan's series."
    )
    parser.add_argument(
        "digits",
        nargs="?",
        type=int,
        default=DEFAULT_DIGITS,
        help=f"Number of decimal digits to compute (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
