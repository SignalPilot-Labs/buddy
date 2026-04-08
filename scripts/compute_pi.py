#!/usr/bin/env python3
"""Compute and print arbitrary-precision digits of pi using mpmath."""

import argparse

import mpmath

DEFAULT_DIGIT_COUNT: int = 100


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal places and return as a string."""
    mpmath.mp.dps = num_digits
    return mpmath.nstr(mpmath.pi, num_digits, strip_zeros=False)


def parse_args() -> int:
    """Parse CLI arguments and return the requested digit count."""
    parser = argparse.ArgumentParser(
        description="Compute arbitrary-precision digits of pi."
    )
    parser.add_argument(
        "digits",
        nargs="?",
        type=int,
        default=DEFAULT_DIGIT_COUNT,
        help=f"Number of digits to compute (default: {DEFAULT_DIGIT_COUNT})",
    )
    args = parser.parse_args()
    return int(args.digits)


def main() -> None:
    """Entry point: parse args, compute pi, print result."""
    num_digits = parse_args()
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
