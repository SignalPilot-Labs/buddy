import decimal
import math

from scripts.pi.constants import CHUDNOVSKY_A
from scripts.pi.constants import CHUDNOVSKY_B
from scripts.pi.constants import CHUDNOVSKY_C
from scripts.pi.constants import CHUDNOVSKY_C3_OVER_24
from scripts.pi.constants import DIGITS_PER_TERM


def _binary_split(a: int, b: int) -> tuple[int, int, int]:
    """Recursive binary splitting for the Chudnovsky series.

    Returns (P, Q, T) for the partial sum over terms [a, b).
    P, Q, T are integers; the partial sum equals T/Q.
    """
    if b - a == 1:
        return _base_case(a)
    mid = (a + b) // 2
    p_left, q_left, t_left = _binary_split(a, mid)
    p_right, q_right, t_right = _binary_split(mid, b)
    return _merge(p_left, q_left, t_left, p_right, q_right, t_right)


def _base_case(k: int) -> tuple[int, int, int]:
    """Compute the single-term (P, Q, T) for term k."""
    if k == 0:
        p_k = 1
        q_k = 1
        t_k = CHUDNOVSKY_A
    else:
        p_k = (6 * k - 5) * (2 * k - 1) * (6 * k - 1)
        q_k = k * k * k * CHUDNOVSKY_C3_OVER_24
        t_k = p_k * (CHUDNOVSKY_A + CHUDNOVSKY_B * k)
        if k % 2 == 1:
            t_k = -t_k
    return p_k, q_k, t_k


def _merge(
    p_left: int,
    q_left: int,
    t_left: int,
    p_right: int,
    q_right: int,
    t_right: int,
) -> tuple[int, int, int]:
    """Merge two (P, Q, T) halves."""
    p_merged = p_left * p_right
    q_merged = q_left * q_right
    t_merged = q_right * t_left + p_left * t_right
    return p_merged, q_merged, t_merged


def compute_pi(num_digits: int) -> str:
    """Compute pi to num_digits digits after the decimal point.

    Returns a string like "3.14159..." with exactly num_digits digits after '.'.
    Raises ValueError if num_digits < 1.
    """
    if num_digits < 1:
        raise ValueError(f"num_digits must be >= 1, got {num_digits}")

    # Set precision high enough to avoid rounding errors
    precision = num_digits + 10
    decimal.getcontext().prec = precision

    num_terms = math.ceil(num_digits / DIGITS_PER_TERM) + 1
    _, q_total, t_total = _binary_split(0, num_terms)

    # pi = C * sqrt(C) / (12 * (T/Q))
    # pi = Q * C * sqrt(C) / (12 * T)
    c = decimal.Decimal(CHUDNOVSKY_C)
    sqrt_c = c.sqrt()
    pi = decimal.Decimal(q_total) * c * sqrt_c / (12 * decimal.Decimal(t_total))

    # Format: "3." followed by exactly num_digits fractional digits
    pi_str = str(pi)
    dot_index = pi_str.index(".")
    integer_part = pi_str[:dot_index]
    frac_part = pi_str[dot_index + 1 :]
    frac_part = frac_part[:num_digits].ljust(num_digits, "0")
    return f"{integer_part}.{frac_part}"
