DEFAULT_DIGITS: int = 100

# Extra guard digits to ensure accuracy of the final result
EXTRA_PRECISION_DIGITS: int = 10

# Digits of pi produced per term of the Chudnovsky series (log10(151931373056000))
DIGITS_PER_TERM: float = 14.1816474627254776555

# Chudnovsky series constant: 426880 * sqrt(10005)
C: int = 426880

# Radicand for the sqrt in the Chudnovsky formula
C_SQRT_RADICAND: int = 10005

# Numerator seed for the linear factorial term (Pochhammer rising factorial base)
A_NUMERATOR: int = 13591409

# Linear increment per term for the numerator of the rational series
A_LINEAR: int = 545140134

# Cubic increment per term for the denominator of the rational series
B_CUBIC: int = 262537412640768000
