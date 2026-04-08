import argparse

import chudnovsky
import pi_constants


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=pi_constants.CLI_DESCRIPTION)
    parser.add_argument(
        "digits",
        type=int,
        nargs="?",
        default=pi_constants.DEFAULT_DIGIT_COUNT,
        help=pi_constants.CLI_DIGITS_HELP,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = chudnovsky.compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
