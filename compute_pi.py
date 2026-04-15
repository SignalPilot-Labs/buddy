import argparse
from decimal import Decimal, getcontext

CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_C3_OVER_24: int = 640320**3 // 24
CHUDNOVSKY_K_FACTOR: int = 6
CHUDNOVSKY_M_FACTOR: int = 3
CHUDNOVSKY_LINEAR: int = 545140134
CHUDNOVSKY_CONSTANT: int = 13591409
CHUDNOVSKY_DIGITS_PER_TERM: int = 14
DEFAULT_DIGITS: int = 100
DECIMAL_EXTRA_GUARD: int = 10
MIN_DIGITS: int = 1
CLI_DESCRIPTION: str = "Compute digits of pi"
CLI_ARG_HELP: str = "Number of digits of pi to compute"


def binary_split(a: int, b: int) -> tuple[int, int, int]:
    if b == a + 1:
        k = a
        if k == 0:
            p = 1
            q = 1
            t = CHUDNOVSKY_CONSTANT
        else:
            p = (
                (CHUDNOVSKY_K_FACTOR * k - 5)
                * (2 * k - 1)
                * (CHUDNOVSKY_K_FACTOR * k - 1)
            )
            q = k**3 * CHUDNOVSKY_C3_OVER_24
            t = p * (CHUDNOVSKY_CONSTANT + CHUDNOVSKY_LINEAR * k)
            if k % 2 == 1:
                t = -t
        return p, q, t

    m = (a + b) // 2
    p_am, q_am, t_am = binary_split(a, m)
    p_mb, q_mb, t_mb = binary_split(m, b)

    p = p_am * p_mb
    q = q_am * q_mb
    t = t_am * q_mb + p_am * t_mb
    return p, q, t


def compute_pi(num_digits: int) -> str:
    precision = num_digits + DECIMAL_EXTRA_GUARD
    getcontext().prec = precision

    num_terms = num_digits // CHUDNOVSKY_DIGITS_PER_TERM + 1
    _, q, t = binary_split(0, num_terms)

    sqrt_c = Decimal(CHUDNOVSKY_C**3).sqrt()
    pi_value = Decimal(q) * sqrt_c / (Decimal(12) * Decimal(t))

    pi_str = str(pi_value)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + 1 + num_digits]


def main() -> None:
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    parser.add_argument("num_digits", type=int, help=CLI_ARG_HELP)
    args = parser.parse_args()

    if args.num_digits < MIN_DIGITS:
        parser.error(f"num_digits must be >= {MIN_DIGITS}")

    print(compute_pi(args.num_digits))


if __name__ == "__main__":
    main()
