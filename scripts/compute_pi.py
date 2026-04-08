import argparse
import decimal
import sys

DEFAULT_DIGITS: int = 100
RAMANUJAN_COEFFICIENT_NUMERATOR: int = 2
RAMANUJAN_SQRT_BASE: int = 2
RAMANUJAN_COEFFICIENT_DENOMINATOR: int = 9801
RAMANUJAN_LINEAR_BASE: int = 1103
RAMANUJAN_LINEAR_STEP: int = 26390
RAMANUJAN_FACTORIAL_MULTIPLIER: int = 4
RAMANUJAN_DENOMINATOR_BASE: int = 396
RAMANUJAN_DIGITS_PER_TERM: int = 8
RAMANUJAN_DECIMAL_GUARD: int = 15
RAMANUJAN_INITIAL_TERM: int = 1
RAMANUJAN_SERIES_START: int = 0
FACTORIAL_STEP_OFFSET_FIRST: int = 1
FACTORIAL_STEP_OFFSET_SECOND: int = 2
FACTORIAL_STEP_OFFSET_THIRD: int = 3
PI_STRING_OFFSET: int = 1


def _num_terms(num_digits: int) -> int:
    return num_digits // RAMANUJAN_DIGITS_PER_TERM + RAMANUJAN_INITIAL_TERM


def _four_k_factorial_step(four_k_factorial: int, k: int) -> int:
    four_k = RAMANUJAN_FACTORIAL_MULTIPLIER * k
    step = (
        (four_k - RAMANUJAN_FACTORIAL_MULTIPLIER + FACTORIAL_STEP_OFFSET_FIRST)
        * (four_k - RAMANUJAN_FACTORIAL_MULTIPLIER + FACTORIAL_STEP_OFFSET_SECOND)
        * (four_k - RAMANUJAN_FACTORIAL_MULTIPLIER + FACTORIAL_STEP_OFFSET_THIRD)
        * four_k
    )
    return four_k_factorial * step


def _ramanujan_sum(num_digits: int) -> decimal.Decimal:
    terms = _num_terms(num_digits)
    series = decimal.Decimal(RAMANUJAN_SERIES_START)
    four_k_factorial = RAMANUJAN_INITIAL_TERM
    k_factorial = RAMANUJAN_INITIAL_TERM
    denominator_base_power = RAMANUJAN_INITIAL_TERM

    for k in range(RAMANUJAN_SERIES_START, terms):
        if k > RAMANUJAN_SERIES_START:
            four_k_factorial = _four_k_factorial_step(four_k_factorial, k)
            k_factorial *= k
            denominator_base_power *= RAMANUJAN_DENOMINATOR_BASE ** RAMANUJAN_FACTORIAL_MULTIPLIER

        linear = RAMANUJAN_LINEAR_BASE + RAMANUJAN_LINEAR_STEP * k
        numerator = decimal.Decimal(four_k_factorial * linear)
        denominator = decimal.Decimal(
            k_factorial ** RAMANUJAN_FACTORIAL_MULTIPLIER * denominator_base_power
        )
        series += numerator / denominator

    return series


def compute_pi(num_digits: int) -> str:
    decimal.getcontext().prec = num_digits + RAMANUJAN_DECIMAL_GUARD
    coefficient = (
        decimal.Decimal(RAMANUJAN_COEFFICIENT_NUMERATOR)
        * decimal.Decimal(RAMANUJAN_SQRT_BASE).sqrt()
        / decimal.Decimal(RAMANUJAN_COEFFICIENT_DENOMINATOR)
    )
    pi = decimal.Decimal(RAMANUJAN_INITIAL_TERM) / (coefficient * _ramanujan_sum(num_digits))
    pi_str = str(pi)
    truncated = pi_str[: num_digits + PI_STRING_OFFSET]
    return truncated.rstrip(".")


def parse_args(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compute digits of pi using Ramanujan algorithm")
    parser.add_argument("digits", type=int, help="Number of digits to compute (must be >= 1)")
    args = parser.parse_args(argv)
    if args.digits < 1:
        parser.error("digits must be >= 1")
    return int(args.digits)


def main() -> None:
    num_digits = parse_args(sys.argv[1:])
    pi_str = compute_pi(num_digits)
    print(pi_str)


if __name__ == "__main__":
    main()
