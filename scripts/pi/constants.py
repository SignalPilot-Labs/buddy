DEFAULT_DIGITS: int = 100

# Chudnovsky series constants
# pi = C * sqrt(C) / (12 * S)
# where S = sum_{k=0}^{inf} (-1)^k * (6k)! * (13591409 + 545140134*k) / ((3k)! * (k!)^3 * 640320^(3k))

CHUDNOVSKY_A: int = 13591409
CHUDNOVSKY_B: int = 545140134
CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_C3_OVER_24: int = CHUDNOVSKY_C**3 // 24

# Each term of the series contributes approximately this many decimal digits
DIGITS_PER_TERM: float = 14.181647462725477
