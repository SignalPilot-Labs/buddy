"""Compute arbitrary-precision digits of pi using Ramanujan's 1/pi series."""

import argparse
import sys
from decimal import ROUND_FLOOR, Decimal, getcontext
from math import factorial

DEFAULT_DIGITS: int = 100
GUARD_DIGITS: int = 20

# Ramanujan 1/pi series constants
RAMANUJAN_A: int = 1103
RAMANUJAN_B: int = 26390
RAMANUJAN_C: int = 396
RAMANUJAN_COEFF_NUM: int = 2
RAMANUJAN_COEFF_DENOM: int = 9801
RAMANUJAN_SQRT_ARG: int = 2

# Digits of convergence per Ramanujan term (~8)
RAMANUJAN_DIGITS_PER_TERM: int = 8


class PiComputer:
    """Computes pi to an arbitrary number of digits using Ramanujan's 1/pi series."""

    def __init__(self, num_digits: int) -> None:
        if num_digits < 1:
            raise ValueError(f"num_digits must be >= 1, got {num_digits}")
        self._num_digits = num_digits

    def compute(self) -> str:
        """Return pi as a string with the requested number of significant digits."""
        precision = self._num_digits + GUARD_DIGITS
        getcontext().prec = precision

        series_sum = self._ramanujan_series()
        sqrt_part = self._compute_sqrt(RAMANUJAN_SQRT_ARG)
        coeff = Decimal(RAMANUJAN_COEFF_NUM) * sqrt_part / Decimal(RAMANUJAN_COEFF_DENOM)
        pi = Decimal(1) / (coeff * series_sum)

        return self._format(pi)

    def _format(self, pi: Decimal) -> str:
        """Format pi to exactly num_digits significant digits as a string.

        Truncates (floor) rather than rounds to avoid last-digit inflation.
        Preserves trailing zeros (e.g. 50th digit of pi is 0).
        """
        if self._num_digits == 1:
            return str(int(pi))
        # num_digits - 1 digits after the decimal point (pi = 3.xxx...)
        decimal_places = self._num_digits - 1
        quantizer = Decimal("0." + "0" * decimal_places)
        truncated = pi.quantize(quantizer, rounding=ROUND_FLOOR)
        return str(truncated)

    def _ramanujan_series(self) -> Decimal:
        """Compute the Ramanujan 1/pi series sum iteratively.

        Returns sum_k [ (4k)! * (A + B*k) / ((k!)^4 * C^(4k)) ].
        """
        num_terms = self._num_digits // RAMANUJAN_DIGITS_PER_TERM + 2
        series_sum = Decimal(0)
        for k in range(num_terms):
            series_sum += self._term(k)
        return series_sum

    def _term(self, k: int) -> Decimal:
        """Compute a single term k of the Ramanujan series."""
        numerator = factorial(4 * k) * (RAMANUJAN_A + RAMANUJAN_B * k)
        denominator = (factorial(k) ** 4) * (RAMANUJAN_C ** (4 * k))
        return Decimal(numerator) / Decimal(denominator)

    def _compute_sqrt(self, value: int) -> Decimal:
        """Compute sqrt(value) using Decimal at full precision."""
        return Decimal(value).sqrt()


def parse_args(args: list[str]) -> int:
    """Parse CLI arguments and return the requested number of digits."""
    parser = argparse.ArgumentParser(
        description="Compute pi to N digits using Ramanujan's 1/pi series."
    )
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=DEFAULT_DIGITS,
        help=f"Number of digits to compute (default: {DEFAULT_DIGITS})",
    )
    parsed = parser.parse_args(args)
    num_digits: int = parsed.digits
    return num_digits


def main() -> None:
    """Entry point: parse args, compute pi, print result."""
    num_digits = parse_args(sys.argv[1:])
    computer = PiComputer(num_digits)
    result = computer.compute()
    print(result)


if __name__ == "__main__":
    main()
