import math
from decimal import Decimal, getcontext, ROUND_DOWN

PRECISION = 120
ITERATIONS = 15
RAMANUJAN_CONSTANT = Decimal(9801)
RAMANUJAN_LINEAR = Decimal(1103)
RAMANUJAN_SLOPE = Decimal(26390)
RAMANUJAN_BASE = Decimal(396)
OUTPUT_DIGITS = 100


def compute_pi() -> str:
    getcontext().prec = PRECISION

    sqrt2 = Decimal(2).sqrt()
    series_sum = Decimal(0)

    for k in range(ITERATIONS):
        numerator = Decimal(math.factorial(4 * k)) * (RAMANUJAN_LINEAR + RAMANUJAN_SLOPE * k)
        denominator = Decimal(math.factorial(k) ** 4) * (RAMANUJAN_BASE ** (4 * k))
        series_sum += numerator / denominator

    pi = RAMANUJAN_CONSTANT / (Decimal(2) * sqrt2 * series_sum)

    quantizer = Decimal(10) ** (-OUTPUT_DIGITS)
    pi_truncated = pi.quantize(quantizer, rounding=ROUND_DOWN)

    return str(pi_truncated)


if __name__ == "__main__":
    print(compute_pi())
