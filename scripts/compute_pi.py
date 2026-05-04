import decimal
import math
import sys
from decimal import Decimal

RAMANUJAN_COEFFICIENT_NUMERATOR = 2
RAMANUJAN_COEFFICIENT_DENOM = 9801
RAMANUJAN_SQRT_ARG = 2
RAMANUJAN_LINEAR_BASE = 1103
RAMANUJAN_LINEAR_FACTOR = 26390
RAMANUJAN_DENOM_BASE = 396
EXTRA_PRECISION_DIGITS = 10
MIN_DIGITS = 1


def _ramanujan_series_sum(precision: int) -> Decimal:
    series_sum = Decimal(0)
    k = 0
    while True:
        numerator = Decimal(math.factorial(4 * k)) * Decimal(
            RAMANUJAN_LINEAR_BASE + RAMANUJAN_LINEAR_FACTOR * k
        )
        denominator = (
            Decimal(math.factorial(k) ** 4)
            * Decimal(RAMANUJAN_DENOM_BASE) ** (4 * k)
        )
        term = numerator / denominator
        series_sum += term
        if k > 0 and abs(term) < Decimal(10) ** (-precision):
            break
        k += 1
    return series_sum


def compute_pi_ramanujan(num_digits: int) -> Decimal:
    precision = num_digits + EXTRA_PRECISION_DIGITS
    decimal.getcontext().prec = precision
    series_sum = _ramanujan_series_sum(precision)
    coefficient = (
        Decimal(RAMANUJAN_COEFFICIENT_NUMERATOR)
        * Decimal(RAMANUJAN_SQRT_ARG).sqrt()
        / Decimal(RAMANUJAN_COEFFICIENT_DENOM)
    )
    pi = Decimal(1) / (coefficient * series_sum)
    return pi


def format_pi(pi_value: Decimal, num_digits: int) -> str:
    with decimal.localcontext() as ctx:
        ctx.prec = num_digits + EXTRA_PRECISION_DIGITS
        quantize_str = "0." + "0" * num_digits
        rounded = pi_value.quantize(Decimal(quantize_str), rounding=decimal.ROUND_FLOOR)
    return str(rounded)


def parse_args(args: list[str]) -> int:
    if len(args) != 1:
        print("Usage: compute_pi.py <num_digits>", file=sys.stderr)
        raise SystemExit(1)

    try:
        num_digits = int(args[0])
    except ValueError:
        print(f"Error: num_digits must be an integer, got {args[0]!r}", file=sys.stderr)
        raise SystemExit(1)

    if num_digits < MIN_DIGITS:
        print(f"Error: num_digits must be >= {MIN_DIGITS}, got {num_digits}", file=sys.stderr)
        raise SystemExit(1)

    return num_digits


def main() -> None:
    num_digits = parse_args(sys.argv[1:])
    pi_value = compute_pi_ramanujan(num_digits)
    print(format_pi(pi_value, num_digits))


if __name__ == "__main__":
    main()
