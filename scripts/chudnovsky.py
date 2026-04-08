import decimal

import pi_constants


def _binary_split(a: int, b: int) -> tuple[int, int, int]:
    """Recursively compute (Pab, Qab, Tab) for the Chudnovsky binary splitting."""
    if b == a + 1:
        if a == 0:
            pab = 1
            qab = 1
        else:
            pab = (6 * a - 5) * (2 * a - 1) * (6 * a - 1)
            qab = a * a * a * pi_constants.CHUDNOVSKY_C3_OVER_24
        tab = pab * (pi_constants.CHUDNOVSKY_A + pi_constants.CHUDNOVSKY_B * a)
        if a % 2 == 1:
            tab = -tab
        return pab, qab, tab

    mid = (a + b) // 2
    p_am, q_am, t_am = _binary_split(a, mid)
    p_mb, q_mb, t_mb = _binary_split(mid, b)

    pab = p_am * p_mb
    qab = q_am * q_mb
    tab = q_mb * t_am + p_am * t_mb
    return pab, qab, tab


def _num_terms(num_digits: int) -> int:
    """Estimate number of Chudnovsky series terms needed for the given digit count."""
    # Each term contributes ~14.18 digits of precision
    return num_digits // pi_constants.DIGITS_PER_TERM + 1


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits decimal digits using the Chudnovsky algorithm."""
    precision = num_digits + pi_constants.GUARD_DIGITS
    decimal.getcontext().prec = precision

    n = _num_terms(num_digits)
    _, q, t = _binary_split(0, n)

    # pi = (426880 * sqrt(10005) * Q) / T
    sqrt_c = decimal.Decimal(pi_constants.CHUDNOVSKY_SQRT_VALUE).sqrt()
    pi_value = (decimal.Decimal(pi_constants.CHUDNOVSKY_MULTIPLIER) * sqrt_c * decimal.Decimal(q)) / decimal.Decimal(t)

    pi_str = str(pi_value)

    # Truncate to "3." + num_digits-1 fractional digits = num_digits significant digits total
    # pi_str looks like "3.14159265..."
    dot_index = pi_str.index(".")
    full_digits_needed = dot_index + 1 + (num_digits - 1)
    return pi_str[:full_digits_needed]
