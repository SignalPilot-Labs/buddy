"""Constants for the Chudnovsky pi computation algorithm."""

# Chudnovsky series coefficients
CHUDNOVSKY_C: int = 426880
CHUDNOVSKY_C_RADICAND: int = 10005
CHUDNOVSKY_K_COEFF: int = 545140134
CHUDNOVSKY_K_BASE: int = 13591409
CHUDNOVSKY_DIVISOR: int = -262537412640768000

# Extra guard digits to avoid rounding errors at the boundary
EXTRA_PRECISION_DIGITS: int = 50

# Validation limits
MIN_DIGITS: int = 1

# Exit codes
EXIT_CODE_INVALID_INPUT: int = 1
