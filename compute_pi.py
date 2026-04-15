import argparse
import sys

import mpmath

MIN_DIGITS: int = 1
DEFAULT_DIGITS: int = 100


def compute_pi(num_digits: int) -> str:
    mpmath.mp.dps = num_digits + 1
    raw = mpmath.nstr(mpmath.mp.pi, num_digits)
    return raw.rstrip("0").rstrip(".")


def parse_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compute digits of pi using mpmath.")
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=DEFAULT_DIGITS,
        help="Number of digits of pi to print.",
    )
    args = parser.parse_args(argv)
    if args.digits < MIN_DIGITS:
        print(f"Error: digits must be >= {MIN_DIGITS}", file=sys.stderr)
        sys.exit(1)
    return args.digits


def main() -> None:
    num_digits = parse_args(sys.argv[1:])
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
