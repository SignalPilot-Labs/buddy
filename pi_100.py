from decimal import Decimal, getcontext

PRECISION = 115
CONVERGENCE_THRESHOLD_EXP = -105
DECIMAL_PLACES = 100


def arctan(x: Decimal) -> Decimal:
    result = Decimal(0)
    power = x
    x_squared = x * x
    divisor = Decimal(1)
    sign = Decimal(1)
    threshold = Decimal(10) ** CONVERGENCE_THRESHOLD_EXP

    while True:
        term = sign * power / divisor
        result += term
        if abs(term) < threshold:
            break
        power *= x_squared
        divisor += Decimal(2)
        sign = -sign

    return result


def compute_pi() -> str:
    getcontext().prec = PRECISION
    pi = Decimal(4) * (
        Decimal(4) * arctan(Decimal(1) / Decimal(5))
        - arctan(Decimal(1) / Decimal(239))
    )
    pi_str = str(pi)
    dot_index = pi_str.index(".")
    return pi_str[: dot_index + 1 + DECIMAL_PLACES]


if __name__ == "__main__":
    print(compute_pi())
