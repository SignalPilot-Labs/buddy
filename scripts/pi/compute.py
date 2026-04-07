import decimal

from scripts.pi.constants import (
    DIGITS_PER_TERM,
    GUARD_DIGITS,
    RAMANUJAN_BASE,
    RAMANUJAN_CONSTANT,
    RAMANUJAN_INITIAL_TERM,
    RAMANUJAN_LINEAR_TERM,
    RAMANUJAN_SQRT_MULTIPLIER,
)


class PiComputer:
    def compute(self, num_digits: int) -> str:
        precision = num_digits + GUARD_DIGITS
        decimal.getcontext().prec = precision

        num_terms = num_digits // DIGITS_PER_TERM + 1
        series_sum = self._ramanujan_sum(num_terms)

        two = decimal.Decimal(RAMANUJAN_SQRT_MULTIPLIER)
        constant = decimal.Decimal(RAMANUJAN_CONSTANT)
        prefactor = two * two.sqrt() / constant
        pi = decimal.Decimal(1) / (prefactor * series_sum)

        return self._format_pi(pi, num_digits)

    def _ramanujan_sum(self, num_terms: int) -> decimal.Decimal:
        total = decimal.Decimal(0)
        term = decimal.Decimal(1)
        for k in range(num_terms):
            linear = decimal.Decimal(RAMANUJAN_INITIAL_TERM + RAMANUJAN_LINEAR_TERM * k)
            total += term * linear
            if k + 1 < num_terms:
                term = self._advance_term(term, k + 1)
        return total

    def _advance_term(self, prev_term: decimal.Decimal, k: int) -> decimal.Decimal:
        numerator = self._four_consecutive(k)
        base = decimal.Decimal(RAMANUJAN_BASE)
        denominator = decimal.Decimal(k) ** 4 * base ** 4
        return prev_term * numerator / denominator

    def _four_consecutive(self, k: int) -> decimal.Decimal:
        four_k = 4 * k
        return decimal.Decimal(
            (four_k - 3) * (four_k - 2) * (four_k - 1) * four_k
        )

    def _format_pi(self, pi: decimal.Decimal, num_digits: int) -> str:
        pi_str = str(pi)
        dot_index = pi_str.index(".")
        end = dot_index + 1 + num_digits
        return pi_str[:end]
