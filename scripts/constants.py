DEFAULT_DIGIT_COUNT: int = 100
SCRIPT_DESCRIPTION: str = "Compute digits of pi using the Ramanujan series"

# Ramanujan series: 1/pi = (2*sqrt(2)/9801) * sum_{k=0}^{inf} ((4k)! * (1103 + 26390*k)) / ((k!)^4 * 396^(4k))
RAMANUJAN_SQRT_COEFF: int = 2
RAMANUJAN_DIVISOR: int = 9801
RAMANUJAN_BASE: int = 1103
RAMANUJAN_LINEAR: int = 26390
RAMANUJAN_POWER_BASE: int = 396
EXTRA_PRECISION_DIGITS: int = 10
DIGITS_PER_TERM: int = 8
