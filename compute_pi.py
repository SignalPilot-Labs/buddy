import sys

import mpmath

DEFAULT_DIGITS: int = 100
MIN_DIGITS: int = 1
USAGE_MESSAGE: str = "Usage: python compute_pi.py <number_of_digits>"


def parse_digit_count(args: list[str]) -> int:
    if len(args) != 1 or not args[0].isdigit() or int(args[0]) < MIN_DIGITS:
        print(USAGE_MESSAGE)
        sys.exit(1)
    return int(args[0])


def compute_pi(num_digits: int) -> str:
    mpmath.mp.dps = num_digits
    return mpmath.nstr(mpmath.pi, num_digits + 1)


def main() -> None:
    num_digits = parse_digit_count(sys.argv[1:])
    result = compute_pi(num_digits)
    print(result)


if __name__ == "__main__":
    main()
