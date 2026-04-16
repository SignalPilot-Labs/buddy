import argparse
from decimal import Decimal, getcontext

DEFAULT_DIGITS = 100
PROGRAM_DESCRIPTION = "Compute pi to an arbitrary number of decimal digits using Ramanujan's series."

RAMANUJAN_CONSTANT_FACTOR = 9801
RAMANUJAN_SQRT_INPUT = 8
RAMANUJAN_A = 1103
RAMANUJAN_B = 26390
RAMANUJAN_D = 396
RAMANUJAN_GUARD_DIGITS = 10


def compute_pi(num_digits: int) -> str:
    if num_digits < 1:
        raise ValueError(f"num_digits must be >= 1, got {num_digits}")

    precision = num_digits + RAMANUJAN_GUARD_DIGITS
    getcontext().prec = precision

    sum_term = _ramanujan_sum(precision)
    pi = Decimal(RAMANUJAN_CONSTANT_FACTOR) / (Decimal(RAMANUJAN_SQRT_INPUT).sqrt() * sum_term)

    pi_str = str(pi)
    # Format: "3.14159..." — keep "3." plus num_digits-1 fractional digits
    full_digits = pi_str.replace(".", "")
    truncated = full_digits[: num_digits + 1]  # +1 for the leading "3"
    return truncated[0] + "." + truncated[1:]


def _ramanujan_sum(precision: int) -> Decimal:
    # Number of terms needed: ~8 digits per term
    num_terms = precision // 8 + 2

    total = Decimal(0)
    for k in range(num_terms):
        numerator = _factorial(4 * k) * (RAMANUJAN_A + RAMANUJAN_B * k)
        denominator = _factorial(k) ** 4 * RAMANUJAN_D ** (4 * k)
        total += Decimal(numerator) / Decimal(denominator)

    return total


def _factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument(
        "digits",
        nargs="?",
        type=int,
        default=DEFAULT_DIGITS,
        help=f"Number of decimal digits of pi to compute (default: {DEFAULT_DIGITS})",
    )
    args = parser.parse_args()
    result = compute_pi(args.digits)
    print(result)


if __name__ == "__main__":
    main()
