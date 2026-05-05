import decimal
import math

PI_DIGITS = 100
PRECISION_BUFFER = 15
CONVERGENCE_BUFFER = 5
CHUDNOVSKY_C = 640320
CHUDNOVSKY_K1 = 13591409
CHUDNOVSKY_K2 = 545140134
CHUDNOVSKY_SQRT_COEFF = 426880
CHUDNOVSKY_SQRT_BASE = 10005

# CHUDNOVSKY_C^3 = 640320^3, precomputed for efficiency
CHUDNOVSKY_C3 = CHUDNOVSKY_C ** 3


def factorial(n: int) -> int:
    return math.factorial(n)


def compute_pi(precision: int) -> decimal.Decimal:
    """Compute pi using the Chudnovsky algorithm to the given number of digits."""
    decimal.getcontext().prec = precision + PRECISION_BUFFER

    convergence_threshold = decimal.Decimal(10) ** -(precision + CONVERGENCE_BUFFER)

    # Chudnovsky: 1/pi = 12 * sum_k [ (-1)^k (6k)! (K1 + K2*k) ] / [ (3k)! (k!)^3 C^(3k+3/2) ]
    # Rewritten: pi = C^(1/2) * sum_denom / (12 * sum_numer)
    # where C^(1/2) = 640320^(1/2) * C (via standard reformulation)
    #
    # Use the standard Chudnovsky summation directly:
    #   sum_k a_k  where a_k = (-1)^k (6k)! (K1 + K2*k) / ((3k)! (k!)^3 (C^3/24)^k)
    # and pi = sqrt(C^3 / 12) / (C * sum)  -- but let's use the clean form:
    #
    #   pi = 426880 * sqrt(10005) / S
    #   S  = sum_k (-1)^k (6k)! (K1 + K2*k) / ((3k)! (k!)^3 C^(3k))
    #
    # Note: C^3 / 24 per term factored out; the sqrt(10005) handles remaining constants.

    series_sum = decimal.Decimal(0)
    c3_power = decimal.Decimal(1)  # tracks (C^3)^k = C^(3k)
    c3_dec = decimal.Decimal(CHUDNOVSKY_C3)

    k = 0
    while True:
        num_int = ((-1) ** k) * factorial(6 * k) * (CHUDNOVSKY_K1 + CHUDNOVSKY_K2 * k)
        den_int = factorial(3 * k) * (factorial(k) ** 3)

        term = decimal.Decimal(num_int) / (decimal.Decimal(den_int) * c3_power)
        series_sum += term

        if abs(term) < convergence_threshold:
            break

        k += 1
        c3_power *= c3_dec

    # Final formula: pi = CHUDNOVSKY_SQRT_COEFF * sqrt(CHUDNOVSKY_SQRT_BASE) / series_sum
    constant = decimal.Decimal(CHUDNOVSKY_SQRT_COEFF) * decimal.Decimal(CHUDNOVSKY_SQRT_BASE).sqrt()
    return constant / series_sum


def format_pi(pi_value: decimal.Decimal, digits: int) -> str:
    """Format pi to exactly `digits` significant digits (1 before decimal + digits-1 after)."""
    decimal_places = digits - 1
    quantize_exp = decimal.Decimal(10) ** -decimal_places
    truncated = pi_value.quantize(quantize_exp, rounding=decimal.ROUND_FLOOR)
    return str(truncated)


def main() -> None:
    pi = compute_pi(PI_DIGITS)
    output = format_pi(pi, PI_DIGITS)
    print(output)


if __name__ == "__main__":
    main()
