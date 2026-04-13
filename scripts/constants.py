"""Constants for the Ramanujan pi computation script."""

# Ramanujan 1914 series: 1/pi = (2*sqrt(2)/9801) * sum_{k=0}^inf (4k)! * (1103 + 26390*k) / ((k!)^4 * 396^(4k))
RAMANUJAN_DENOMINATOR_BASE: int = 9801
RAMANUJAN_LINEAR_COEFFICIENT: int = 26390
RAMANUJAN_CONSTANT_TERM: int = 1103
RAMANUJAN_SERIES_BASE: int = 396

# Extra terms beyond the digits/8 estimate to ensure convergence
RAMANUJAN_EXTRA_TERMS: int = 2

# Extra guard digits to avoid rounding error on the last printed digit
EXTRA_PRECISION_DIGITS: int = 10
