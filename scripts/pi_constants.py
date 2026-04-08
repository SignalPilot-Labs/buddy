DEFAULT_DIGIT_COUNT: int = 100
GUARD_DIGITS: int = 10

# Chudnovsky algorithm constants
# pi = 1 / (12 * sum_k( (-1)^k * (6k)! * (13591409 + 545140134*k) / ((3k)! * (k!)^3 * 640320^(3k+3/2)) ))
CHUDNOVSKY_A: int = 13591409
CHUDNOVSKY_B: int = 545140134
CHUDNOVSKY_C: int = 640320
CHUDNOVSKY_C3_OVER_24: int = CHUDNOVSKY_C**3 // 24
CHUDNOVSKY_MULTIPLIER: int = 426880
CHUDNOVSKY_SQRT_VALUE: int = 10005
DIGITS_PER_TERM: int = 14

# CLI metadata
CLI_DESCRIPTION: str = "Compute digits of pi using the Chudnovsky algorithm"
CLI_DIGITS_HELP: str = "Number of decimal digits of pi to compute"
