"""Compute pi to N fractional digits via the Chudnovsky algorithm.

Usage:
    python scripts/compute_pi.py --digits 1000
    python scripts/compute_pi.py -n 50

Output: one line "3.<digits>" followed by a newline. Pipe-friendly, no extra prose.
"""

import argparse
import sys
from decimal import Decimal, getcontext
from math import ceil

# Chudnovsky series constants (standard form).
CHUDNOVSKY_L0: int = 13591409
CHUDNOVSKY_L_STEP: int = 545140134
CHUDNOVSKY_C3: int = 640320**3  # = 262537412640768000; X_k = (-C3)^k
CHUDNOVSKY_C: int = 426880
CHUDNOVSKY_SQRT_ARG: int = 10005
CHUDNOVSKY_K_STEP_BASE: int = 6  # 6k coefficients in numerator recurrence

# Precision and convergence tuning.
GUARD_DIGITS: int = 10
DIGITS_PER_TERM: int = 14  # Chudnovsky converges ~14 decimal digits per term.
MIN_DIGITS: int = 1


def _terms_needed(digits: int) -> int:
    """Return the number of Chudnovsky terms required for the requested precision."""
    return ceil(digits / DIGITS_PER_TERM) + 1


def _chudnovsky_sum(terms: int, precision: int) -> Decimal:
    """Accumulate the Chudnovsky series and return the partial sum as a Decimal.

    Tracks M_k = (6k)! / ((3k)! * (k!)^3) as a rational (Mq_num / Mq_den) to keep
    all intermediate quantities as exact integers, avoiding floating-point drift.

    Recurrence: M_k / M_{k-1} = (6k)(6k-1)(6k-2)(6k-3)(6k-4)(6k-5)
                                  / ((3k)(3k-1)(3k-2) * k^3)
    """
    getcontext().prec = precision

    Mq_num: int = 1
    Mq_den: int = 1
    Lq: int = CHUDNOVSKY_L0
    Xq: int = 1
    partial_sum = Decimal(0)

    for k in range(terms):
        if k > 0:
            k6 = CHUDNOVSKY_K_STEP_BASE * k
            Mq_num *= k6 * (k6 - 1) * (k6 - 2) * (k6 - 3) * (k6 - 4) * (k6 - 5)
            Mq_den *= (3 * k) * (3 * k - 1) * (3 * k - 2) * k * k * k
            Lq += CHUDNOVSKY_L_STEP
            Xq *= -CHUDNOVSKY_C3
        partial_sum += Decimal(Mq_num * Lq) / Decimal(Mq_den * Xq)

    return partial_sum


def _truncate(value: Decimal, digits: int) -> str:
    """Return value formatted as '3.xxxx' truncated (not rounded) to `digits` fractional digits.

    Truncation via string slice avoids rounding the last digit, which would
    diverge from the canonical decimal expansion at boundaries.
    """
    full: str = str(value)
    dot_pos: int = full.index(".")
    end: int = dot_pos + 1 + digits
    return full[:end]


def compute_pi(digits: int) -> str:
    """Compute pi to `digits` fractional digits using the Chudnovsky algorithm.

    Returns a string of the form '3.14159...' with exactly `digits` fractional digits.
    """
    precision: int = digits + GUARD_DIGITS
    getcontext().prec = precision

    terms: int = _terms_needed(digits)
    partial_sum: Decimal = _chudnovsky_sum(terms, precision)

    sqrt_val: Decimal = Decimal(CHUDNOVSKY_SQRT_ARG).sqrt()
    pi: Decimal = Decimal(CHUDNOVSKY_C) * sqrt_val / partial_sum
    return _truncate(pi, digits)


def _parse_args(argv: list[str]) -> int:
    """Parse CLI arguments and return the requested digit count.

    Rejects values below MIN_DIGITS via parser.error (fail fast, single failure surface).
    """
    parser = argparse.ArgumentParser(
        description="Compute pi to N fractional digits using the Chudnovsky algorithm."
    )
    parser.add_argument(
        "--digits",
        "-n",
        type=int,
        required=True,
        metavar="N",
        help="Number of fractional digits to compute (must be >= 1).",
    )
    args = parser.parse_args(argv)
    if args.digits < MIN_DIGITS:
        parser.error(f"--digits must be >= {MIN_DIGITS}, got {args.digits}")
    return args.digits  # type: ignore[no-any-return]


def main(argv: list[str]) -> None:
    """Entry point: parse args, compute pi, print result."""
    digits: int = _parse_args(argv)
    result: str = compute_pi(digits)
    print(result)


if __name__ == "__main__":
    main(sys.argv[1:])
