import argparse

from scripts.pi.compute import compute_pi
from scripts.pi.constants import DEFAULT_DIGITS


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute N digits of pi using the Chudnovsky algorithm.")
    parser.add_argument(
        "--digits",
        type=int,
        default=DEFAULT_DIGITS,
        help=f"Number of decimal digits after the point (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
