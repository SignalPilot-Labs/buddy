import decimal

WORKING_PRECISION = 110
OUTPUT_DIGITS = 100


def arctan(x: decimal.Decimal) -> decimal.Decimal:
    """Compute arctan(x) via Taylor series: sum of (-1)^n * x^(2n+1) / (2n+1)."""
    threshold = decimal.Decimal(10) ** (-WORKING_PRECISION)
    result = x
    x_squared = x * x
    term = x
    n = 1
    while True:
        term *= -x_squared
        n += 2
        delta = term / n
        result += delta
        if abs(delta) < threshold:
            break
    return result


def compute_pi() -> decimal.Decimal:
    """Compute pi using Machin's formula: pi/4 = 4*arctan(1/5) - arctan(1/239)."""
    decimal.getcontext().prec = WORKING_PRECISION
    one = decimal.Decimal(1)
    pi = 4 * (4 * arctan(one / 5) - arctan(one / 239))
    return pi


def main() -> None:
    pi = compute_pi()
    pi_str = str(pi)
    dot_index = pi_str.index(".")
    integer_part = pi_str[:dot_index]
    decimal_part = pi_str[dot_index + 1 :]
    print(f"{integer_part}.{decimal_part[:OUTPUT_DIGITS]}")


if __name__ == "__main__":
    main()
