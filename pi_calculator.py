from decimal import Decimal, getcontext

CHUDNOVSKY_A: int = 13591409
CHUDNOVSKY_B: int = 545140134
CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_C3_OVER_24: int = 640320**3 // 24
CHUDNOVSKY_DIGITS_PER_TERM: int = 14
CHUDNOVSKY_MULTIPLIER: int = 426880
CHUDNOVSKY_SQRT_ARG: int = 10005

NUM_DIGITS: int = 100
DECIMAL_PRECISION: int = 110


def compute_pi(num_digits: int) -> Decimal:
    getcontext().prec = DECIMAL_PRECISION

    num_terms = num_digits // CHUDNOVSKY_DIGITS_PER_TERM + 1

    # Iterative binary splitting: accumulate sum without recomputing factorials.
    # Each term update multiplies by the ratio (6k-5)(2k-1)(6k-1) / (k^3 * C3/24)
    # and flips sign.
    total_sum = Decimal(CHUDNOVSKY_A)
    # Numerator and denominator of the running term (kept as integers for precision)
    num: int = 1
    den: int = 1

    for k in range(1, num_terms + 1):
        num *= (6 * k - 5) * (2 * k - 1) * (6 * k - 1)
        den *= k**3 * CHUDNOVSKY_C3_OVER_24
        term_value = Decimal(num) / Decimal(den) * Decimal(CHUDNOVSKY_A + CHUDNOVSKY_B * k)
        if k % 2 == 0:
            total_sum += term_value
        else:
            total_sum -= term_value

    sqrt_val = Decimal(CHUDNOVSKY_SQRT_ARG).sqrt()
    pi = Decimal(CHUDNOVSKY_MULTIPLIER) * sqrt_val / total_sum
    return pi


def format_pi(pi_value: Decimal, num_digits: int) -> str:
    # Convert to string and slice: "3." + num_digits digits = num_digits + 2 chars total
    pi_str = str(pi_value)
    # "3" + "." + num_digits fractional digits
    return pi_str[: num_digits + 2]


def main() -> None:
    pi = compute_pi(NUM_DIGITS)
    print(format_pi(pi, NUM_DIGITS))


if __name__ == "__main__":
    main()
