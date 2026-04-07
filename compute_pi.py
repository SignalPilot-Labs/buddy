import argparse
import decimal

DEFAULT_DIGIT_COUNT: int = 1000
PROGRAM_DESCRIPTION: str = "Compute digits of pi"
GUARD_DIGITS: int = 10

# Ramanujan series constants
RAMANUJAN_SCALE_NUMERATOR: int = 2
RAMANUJAN_SQRT_ARG: int = 2
RAMANUJAN_DENOMINATOR: int = 9801
RAMANUJAN_A: int = 1103
RAMANUJAN_B: int = 26390
RAMANUJAN_C: int = 396
RAMANUJAN_DIGITS_PER_TERM: int = 8
RAMANUJAN_GUARD_TERMS: int = 2
RAMANUJAN_FACTORIAL_MULTIPLIER: int = 4


def _ramanujan_sum(num_digits: int) -> decimal.Decimal:
    """Compute the Ramanujan series sum for the requested precision."""
    terms = num_digits // RAMANUJAN_DIGITS_PER_TERM + RAMANUJAN_GUARD_TERMS
    total = decimal.Decimal(0)
    for k in range(terms):
        numerator = decimal.Decimal(_factorial(RAMANUJAN_FACTORIAL_MULTIPLIER * k)) * (RAMANUJAN_A + RAMANUJAN_B * k)
        denominator = (
            decimal.Decimal(_factorial(k)) ** RAMANUJAN_FACTORIAL_MULTIPLIER
            * decimal.Decimal(RAMANUJAN_C) ** (RAMANUJAN_FACTORIAL_MULTIPLIER * k)
        )
        total += decimal.Decimal(numerator) / decimal.Decimal(denominator)
    return total


def _factorial(n: int) -> int:
    """Compute n! iteratively."""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits significant digits using the Ramanujan algorithm."""
    decimal.getcontext().prec = num_digits + GUARD_DIGITS
    series_sum = _ramanujan_sum(num_digits)
    scale = (
        decimal.Decimal(RAMANUJAN_SCALE_NUMERATOR)
        * decimal.Decimal(RAMANUJAN_SQRT_ARG).sqrt()
        / decimal.Decimal(RAMANUJAN_DENOMINATOR)
    )
    one_over_pi = scale * series_sum
    pi_val = decimal.Decimal(1) / one_over_pi
    pi_str = str(pi_val)
    # pi_str is "3.14159..." — keep "3." plus num_digits-1 more digits = num_digits+1 chars
    dot_index = pi_str.index(".")
    full_digits = pi_str.replace(".", "")
    truncated = full_digits[:num_digits]
    return truncated[: dot_index] + "." + truncated[dot_index:]


def parse_args() -> int:
    """Parse command-line arguments and return the requested digit count."""
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument(
        "--digits",
        type=int,
        default=DEFAULT_DIGIT_COUNT,
        help=f"Number of digits of pi to compute (default: {DEFAULT_DIGIT_COUNT})",
    )
    args = parser.parse_args()
    return int(args.digits)


def main() -> None:
    """Entry point: parse args, compute pi, print result."""
    num_digits = parse_args()
    pi_str = compute_pi(num_digits)
    print(pi_str)


if __name__ == "__main__":
    main()
