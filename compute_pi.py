"""Standalone CLI script to compute arbitrary-precision digits of pi using mpmath."""

import argparse

import mpmath

DEFAULT_DIGITS: int = 1000
MIN_DIGITS: int = 1
DESCRIPTION: str = "Compute digits of pi"
GUARD_DIGITS: int = 5


def compute_pi(num_digits: int) -> str:
    """Return pi as a string with exactly num_digits digits after the decimal point."""
    mpmath.mp.dps = num_digits + GUARD_DIGITS
    raw: str = mpmath.nstr(mpmath.pi, num_digits + GUARD_DIGITS)
    integer_part, decimal_part = raw.split(".")
    return integer_part + "." + decimal_part[:num_digits]


def main() -> None:
    """Parse CLI arguments and print pi to the requested precision."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("digits", type=int, nargs="?", default=DEFAULT_DIGITS)
    args = parser.parse_args()
    print(compute_pi(args.digits))


if __name__ == "__main__":
    main()
