import argparse

from scripts.pi.compute import PiComputer
from scripts.pi.constants import DEFAULT_DIGITS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute digits of pi using the Ramanujan series.")
    parser.add_argument("--digits", type=int, default=DEFAULT_DIGITS, help="Number of decimal digits to compute.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    computer = PiComputer()
    result = computer.compute(args.digits)
    print(result)


if __name__ == "__main__":
    main()
