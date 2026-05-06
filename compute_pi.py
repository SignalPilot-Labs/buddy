"""Compute digits of pi using the Chudnovsky algorithm."""

import sys
from decimal import Decimal, getcontext

# Chudnovsky algorithm constants
CHUDNOVSKY_C = 426880
CHUDNOVSKY_K_FACTOR = 10005
CHUDNOVSKY_A = 13591409
CHUDNOVSKY_B = 545140134
CHUDNOVSKY_C3 = 640320 ** 3

# Argument parsing limits
MIN_DIGITS = 1
MAX_DIGITS = 1_000_000
EXIT_CODE_INVALID_INPUT = 1

# Extra precision buffer to avoid rounding errors in final digits
PRECISION_BUFFER = 50


def binary_split(a: int, b: int) -> tuple[int, int, int]:
    """Recursive binary split for the Chudnovsky series.

    Returns (P, Q, T) for the range [a, b) using the identity:
      Pab = Pa * Pb
      Qab = Qa * Qb
      Tab = Tb * Pa + Qb * Ta (with sign adjustment at each level)
    """
    if b - a == 1:
        if a == 0:
            pab = 1
            qab = 1
        else:
            # Each step contributes 6 numerator factors (6a-5..6a) and 3 denominator
            # factors (3a-2)(3a-1)(3a) plus a^3*C3. After cancellation the net
            # numerator per step is 8*(6a-5)*(6a-3)*(6a-1).
            pab = 8 * (6 * a - 5) * (6 * a - 3) * (6 * a - 1)
            qab = a * a * a * CHUDNOVSKY_C3
        tab = pab * (CHUDNOVSKY_A + CHUDNOVSKY_B * a)
        if a % 2 == 1:
            tab = -tab
        return pab, qab, tab

    mid = (a + b) // 2
    p_left, q_left, t_left = binary_split(a, mid)
    p_right, q_right, t_right = binary_split(mid, b)

    pab = p_left * p_right
    qab = q_left * q_right
    tab = t_right * p_left + q_right * t_left
    return pab, qab, tab


def compute_chudnovsky_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal places using the Chudnovsky algorithm.

    Sets decimal context precision to num_digits + PRECISION_BUFFER to ensure
    the requested digits are correct after rounding.
    """
    getcontext().prec = num_digits + PRECISION_BUFFER

    # Number of terms needed: ~14.18 digits per term
    num_terms = num_digits // 14 + 2

    _, q_total, t_total = binary_split(0, num_terms)

    sqrt_term = Decimal(CHUDNOVSKY_C * CHUDNOVSKY_C * CHUDNOVSKY_K_FACTOR)
    pi = (sqrt_term.sqrt() * Decimal(q_total)) / Decimal(t_total)

    # Format with exactly num_digits decimal places: "3." + num_digits chars
    pi_str = str(pi)
    # Remove the "3." prefix, take num_digits digits, then reconstruct
    dot_index = pi_str.index(".")
    integer_part = pi_str[:dot_index]
    fractional_part = pi_str[dot_index + 1:]
    truncated_fraction = fractional_part[:num_digits]
    return f"{integer_part}.{truncated_fraction}"


def validate_digits(value: str) -> int:
    """Parse and validate the digit count argument.

    Raises SystemExit with EXIT_CODE_INVALID_INPUT on any invalid input.
    Valid inputs are integers in the range [MIN_DIGITS, MAX_DIGITS].
    """
    if not value.lstrip("-").isdigit():
        print(
            f"Error: '{value}' is not a valid integer.",
            file=sys.stderr,
        )
        sys.exit(EXIT_CODE_INVALID_INPUT)

    num_digits = int(value)

    if num_digits < MIN_DIGITS:
        print(
            f"Error: digit count must be at least {MIN_DIGITS}, got {num_digits}.",
            file=sys.stderr,
        )
        sys.exit(EXIT_CODE_INVALID_INPUT)

    if num_digits > MAX_DIGITS:
        print(
            f"Error: digit count must be at most {MAX_DIGITS}, got {num_digits}.",
            file=sys.stderr,
        )
        sys.exit(EXIT_CODE_INVALID_INPUT)

    return num_digits


def main() -> None:
    """Entry point: parse arguments, compute pi, print result."""
    if len(sys.argv) != 2:
        print(
            f"Usage: {sys.argv[0]} <num_digits>",
            file=sys.stderr,
        )
        print(
            f"  num_digits: integer in [{MIN_DIGITS}, {MAX_DIGITS}]",
            file=sys.stderr,
        )
        sys.exit(EXIT_CODE_INVALID_INPUT)

    num_digits = validate_digits(sys.argv[1])
    pi_str = compute_chudnovsky_pi(num_digits)
    print(pi_str)


if __name__ == "__main__":
    main()
