import argparse
import sys

import mpmath

DEFAULT_DIGITS: int = 100
MIN_DIGITS: int = 1
GUARD_DIGITS: int = 5
DESCRIPTION: str = "Compute digits of pi"


def compute_pi(num_digits: int) -> str:
    mpmath.mp.dps = num_digits + GUARD_DIGITS
    pi_str: str = mpmath.nstr(mpmath.pi, num_digits + 1, strip_zeros=False)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + num_digits + 1]


def parse_args(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("digits", type=int, help="Number of decimal digits of pi to compute")
    args = parser.parse_args(argv)
    if args.digits < MIN_DIGITS:
        parser.error(f"digits must be >= {MIN_DIGITS}")
    return int(args.digits)


def main() -> None:
    num_digits = parse_args(sys.argv[1:])
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
