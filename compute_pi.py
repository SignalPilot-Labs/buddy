"""Compute pi using the Leibniz formula."""

NUM_TERMS = 1000


def compute_pi(num_terms: int) -> float:
    """Compute pi using the Leibniz formula: pi/4 = sum of (-1)^k / (2k+1)."""
    total = sum((-1) ** k / (2 * k + 1) for k in range(num_terms))
    return total * 4


if __name__ == "__main__":
    pi = compute_pi(NUM_TERMS)
    print(pi)
