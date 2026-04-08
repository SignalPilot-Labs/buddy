#!/bin/bash
set -e

# Solution for model-extraction-relu-logits challenge.
#
# Approach: Critical-point sweeping + second-order finite differences.
#
# For f(x) = A2 * relu(A1*x + b1) + b2, the function is piecewise-linear.
# Boundaries between linear regions are hyperplanes defined by each row of A1.
# We sweep along random lines through input space looking for "kinks" (points
# where the function is not linear), then recover the weight ratios at each
# kink via second-order directional derivatives.

cat << 'PYEOF' > /app/steal.py
import sys
import numpy as np
sys.path.insert(0, '/app')
from forward import forward

INPUT_DIM = 10
SWEEP_LOW = -1e3
SWEEP_HIGH = 1e3
LINEAR_TOL_SCALE = 1e-5
FINE_EPS = 1e-5
FINE_EPS2_RATIO = 3
SIGN_CHECK_TOL = 1e-4
CLUSTER_SCALE_TOL = 1e-4
GRAD_SMALL_TOL = 1e-4
MIN_CLUSTER_HITS = 3
MAX_CLUSTER_HITS = 80
LINEARITY_CHECK_EPS = 1e-4


def basis_vector(i: int, dim: int = INPUT_DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[i] = 1.0
    return v


def query(x: np.ndarray) -> float:
    return float(forward(x.reshape(1, -1)))


def second_deriv_along(point: np.ndarray, direction: np.ndarray, eps: float, eps2: float) -> float:
    """
    Unsigned second directional derivative via symmetric finite differences.
    Approximates |A2_k * w_i * w_j| at a kink where neuron k switches.
    """
    mask = np.array([1.0, -1.0, 1.0, -1.0])
    pts = np.array([
        point + direction * (eps - eps2),
        point + direction * eps,
        point - direction * (eps - eps2),
        point - direction * eps,
    ])
    vals = np.array([query(p) for p in pts])
    return float(np.dot(vals, mask) / eps)


def recover_weight_ratios(point: np.ndarray) -> np.ndarray:
    """
    At a critical point, recover the weight row (up to an overall scale)
    using second-order finite differences along each basis direction.

    The second derivative of f along e_i at a kink caused by neuron k is
    proportional to (A1[k, i])^2, so we get |w_i| from sqrt, then
    determine signs by checking cross-terms.
    """
    eps = FINE_EPS
    eps2 = eps / FINE_EPS2_RATIO
    dims = list(range(INPUT_DIM))

    unsigned_vals = []
    for i in dims:
        val = second_deriv_along(point, basis_vector(i), eps, eps2)
        unsigned_vals.append(val)

    ref_idx = 0
    signed_vals = [unsigned_vals[0]]

    for i in range(1, INPUT_DIM):
        cross_dir = (basis_vector(ref_idx) + basis_vector(i)) / 2.0
        cross_val = second_deriv_along(point, cross_dir, eps, eps2)

        pos_err = abs(abs(unsigned_vals[ref_idx] + unsigned_vals[i]) / 2.0 - abs(cross_val))
        neg_err = abs(abs(unsigned_vals[ref_idx] - unsigned_vals[i]) / 2.0 - abs(cross_val))

        if pos_err <= neg_err:
            signed_vals.append(unsigned_vals[i])
        else:
            signed_vals.append(-unsigned_vals[i])

    return np.array(signed_vals, dtype=np.float64)


def is_linear(f_low: float, f_mid: float, f_high: float, interval: float) -> bool:
    deviation = abs(f_mid - (f_high + f_low) / 2.0)
    threshold = LINEAR_TOL_SCALE * (interval ** 0.5)
    return deviation < threshold


def find_single_kink(
    offset: np.ndarray,
    direction: np.ndarray,
    low: float,
    high: float,
    cache: dict,
) -> list[float]:
    """
    Recursively bisect [low, high] to find scalar t values where f(offset + t*direction)
    has a kink (ReLU boundary crossing). Returns list of scalar t values.
    """
    results: list[float] = []

    def memo(t: float) -> float:
        if t not in cache:
            cache[t] = query(offset + direction * t)
        return cache[t]

    def search(lo: float, hi: float) -> None:
        mid = (lo + hi) / 2.0
        f_lo = memo(lo)
        f_hi = memo(hi)
        f_mid = memo(mid)

        interval = hi - lo

        if is_linear(f_lo, f_mid, f_hi, interval):
            return
        if interval < 1e-8:
            return

        q1 = (lo + mid) * 0.5
        q3 = (hi + mid) * 0.5
        f_q1 = memo(q1)
        f_q3 = memo(q3)

        m1 = (f_q1 - f_lo) / (q1 - lo)
        m2 = (f_q3 - f_hi) / (q3 - hi)

        if m1 == m2:
            search(lo, mid)
            search(mid, hi)
            return

        alpha = (f_hi - f_lo - interval * m2) / (interval * m1 - interval * m2)
        t_kink = lo + (f_hi - f_lo - interval * m2) / (m1 - m2)
        h_kink = f_lo + m1 * (f_hi - f_lo - interval * m2) / (m1 - m2)

        within_range = 0.25 + 1e-5 < alpha < 0.75 - 1e-5
        if not within_range:
            search(lo, mid)
            search(mid, hi)
            return

        real_h = memo(t_kink)
        height_matches = abs(real_h - h_kink) < LINEAR_TOL_SCALE * 100

        if not height_matches:
            search(lo, mid)
            search(mid, hi)
            return

        grad_left = (memo(t_kink - LINEARITY_CHECK_EPS) - real_h) / (-LINEARITY_CHECK_EPS)
        grad_right = (memo(t_kink + LINEARITY_CHECK_EPS) - real_h) / LINEARITY_CHECK_EPS

        sides_linear = (
            abs(grad_left - m1) <= LINEAR_TOL_SCALE * 10
            and abs(grad_right - m2) <= LINEAR_TOL_SCALE * 10
        )

        if not sides_linear:
            search(lo, mid)
            search(mid, hi)
            return

        results.append(t_kink)

    search(low, high)
    return results


def sweep_critical_points(std: float = 1.0):
    """
    Infinite generator yielding critical points in input space.
    Each point lies on a ReLU boundary hyperplane.
    """
    while True:
        scale = np.random.uniform(std / 10.0, std)
        offset = np.random.normal(0.0, scale, size=INPUT_DIM)
        direction = np.random.normal(0.0, 1.0, size=INPUT_DIM)
        cache: dict[float, float] = {}
        t_values = find_single_kink(offset, direction, SWEEP_LOW, SWEEP_HIGH, cache)
        for t in t_values:
            yield offset + direction * t


def same_hyperplane(row_a: np.ndarray, row_b: np.ndarray, tol: float = CLUSTER_SCALE_TOL) -> bool:
    """
    Two weight rows define the same hyperplane iff one is a scalar multiple of the other.
    """
    safe_mask = np.abs(row_b) > 1e-10
    if not np.any(safe_mask):
        return False
    ratios = row_a[safe_mask] / row_b[safe_mask]
    return bool(np.all(np.abs(ratios - np.mean(ratios)) < tol))


def extract_weight_matrix() -> np.ndarray:
    """
    Sweep for critical points, recover weight ratios, cluster by hyperplane,
    and return the recovered A1 matrix.
    """
    clusters: dict[tuple, int] = {}
    cluster_reps: list[np.ndarray] = []

    for point in sweep_critical_points():
        ratios = recover_weight_ratios(point)

        if np.all(np.abs(ratios) < GRAD_SMALL_TOL):
            continue

        matched = False
        for idx, rep in enumerate(cluster_reps):
            if same_hyperplane(rep, ratios):
                key = tuple(rep)
                clusters[key] += 1
                matched = True
                break

        if not matched:
            key = tuple(ratios)
            cluster_reps.append(ratios)
            clusters[key] = 1

        hit_counts = list(clusters.values())
        if len(hit_counts) > 0 and max(hit_counts) >= MAX_CLUSTER_HITS:
            break

    if len(clusters) == 0:
        raise RuntimeError("No critical points found")

    threshold = max(MIN_CLUSTER_HITS, np.mean(list(clusters.values())) - 2.0 * np.std(list(clusters.values())))
    selected = [
        np.array(key)
        for key, count in clusters.items()
        if count >= threshold
    ]

    if len(selected) == 0:
        selected = [np.array(k) for k in clusters.keys()]

    return np.array(selected)


def main() -> None:
    np.random.seed(42)
    A1_recovered = extract_weight_matrix()
    np.save('/app/stolen_A1.npy', A1_recovered)
    print(f"Recovered {A1_recovered.shape[0]} rows of A1 (expected ~30)")


if __name__ == '__main__':
    main()
PYEOF

echo "steal.py written to /app/steal.py"
