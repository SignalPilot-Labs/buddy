#!/bin/bash
set -e

echo "Creating distribution search solution..."

cat > /app/find_distribution.py << 'PYEOF'
import math
import numpy as np
from scipy.optimize import fsolve

V = 150_000
TARGET = 10.0
LOG_V = math.log(V)
SAVE_PATH = "/app/dist.npy"
TOL = 1e-3

# Mathematical background:
#
# For uniform distribution U over V elements: U_i = 1/V
#
# KL(P||U) = sum(P_i * log(P_i/U_i)) = sum(P_i * log(P_i)) + log(V) = 10
#   => sum(P_i * log(P_i)) = TARGET - LOG_V (probability-weighted average log)
#
# KL(U||P) = sum(U_i * log(U_i/P_i)) = -log(V) - (1/V)*sum(log(P_i)) = 10
#   => sum(log(P_i)) = -V*(TARGET + LOG_V)  (uniform-average log)
#
# Key insight: with k ~ V/e^10 ≈ 6.8 heavy elements and the rest very tiny,
# both KL constraints can be satisfied simultaneously.
#
# Since k must be integer, we use a 3-level distribution:
#   k1=6 elements at probability ph  (heavy)
#   k2=1 element  at probability pm  (medium - handles the fractional part)
#   k3=V-7 elements at probability pl (light, very small)
#
# This gives 3 equations (normalization, KL_fwd=10, KL_bwd=10) in 3 unknowns (ph, pm, pl).


def system_3level(
    log_params: list[float],
    k1: int,
    k2: int,
    k3: int,
) -> list[float]:
    """Residuals for the 3-level distribution system."""
    log_ph, log_pm, log_pl = log_params
    ph = math.exp(log_ph)
    pm = math.exp(log_pm)
    pl = math.exp(log_pl)

    eq_norm = k1 * ph + k2 * pm + k3 * pl - 1.0
    eq_fwd = (
        k1 * ph * (log_ph + LOG_V)
        + k2 * pm * (log_pm + LOG_V)
        + k3 * pl * (log_pl + LOG_V)
        - TARGET
    )
    eq_bwd = (
        -LOG_V
        - (1.0 / V) * (k1 * log_ph + k2 * log_pm + k3 * log_pl)
        - TARGET
    )
    return [eq_norm, eq_fwd, eq_bwd]


def make_initial_guess(k1: int, k2: int, k3: int) -> list[float]:
    """Initial guess based on the continuous solution at k=V/e^TARGET."""
    # Continuous 2-level solution has k_cont = V/e^TARGET ≈ 6.804 heavy elements,
    # each with probability ph_cont ≈ e^TARGET / V.
    k_cont = V / math.exp(TARGET)
    ph_cont = math.exp(TARGET) / V

    # Discretize: k1 elements at ph_cont, k2 element at fraction*(ph_cont)
    fraction = k_cont - k1  # ≈ 0.804
    pm_init = fraction * ph_cont
    ph_init = ph_cont
    pl_init = math.exp(-(TARGET + LOG_V))

    # Clamp to valid range
    ph_init = max(ph_init, 1e-15)
    pm_init = max(pm_init, 1e-15)
    pl_init = max(pl_init, 1e-15)

    return [math.log(ph_init), math.log(pm_init), math.log(pl_init)]


def solve_3level(k1: int, k2: int, k3: int) -> tuple[float, float, float] | None:
    """Solve for (ph, pm, pl) satisfying the 3-level system."""
    x0 = make_initial_guess(k1, k2, k3)

    sol = fsolve(system_3level, x0, args=(k1, k2, k3), full_output=True)
    x, _info, ier, _msg = sol

    if ier != 1:
        return None

    log_ph, log_pm, log_pl = float(x[0]), float(x[1]), float(x[2])
    ph = math.exp(log_ph)
    pm = math.exp(log_pm)
    pl = math.exp(log_pl)

    if ph <= 0.0 or pm <= 0.0 or pl <= 0.0:
        return None
    if ph > 1.0 or pm > 1.0 or pl > 1.0:
        return None

    norm = k1 * ph + k2 * pm + k3 * pl
    if abs(norm - 1.0) > 1e-6:
        return None

    return ph, pm, pl


def compute_kl_divergences(
    ph: float, pm: float, pl: float, k1: int, k2: int, k3: int
) -> tuple[float, float]:
    """Compute both KL divergences for the 3-level distribution."""
    log_ph = math.log(ph)
    log_pm = math.log(pm)
    log_pl = math.log(pl)

    kl_fwd = (
        k1 * ph * (log_ph + LOG_V)
        + k2 * pm * (log_pm + LOG_V)
        + k3 * pl * (log_pl + LOG_V)
    )
    kl_bwd = -LOG_V - (1.0 / V) * (k1 * log_ph + k2 * log_pm + k3 * log_pl)

    return kl_fwd, kl_bwd


def build_distribution() -> np.ndarray:
    """Build the 3-level probability distribution array."""
    # Use k1=6 heavy, k2=1 medium, k3=V-7 light elements.
    # This discretizes the continuous solution at k≈6.804.
    k1 = 6
    k2 = 1
    k3 = V - k1 - k2

    result = solve_3level(k1, k2, k3)
    if result is None:
        raise RuntimeError(f"fsolve failed to converge for k1={k1}, k2={k2}, k3={k3}")

    ph, pm, pl = result
    kl_fwd, kl_bwd = compute_kl_divergences(ph, pm, pl, k1, k2, k3)

    print(f"3-level distribution: k1={k1}, k2={k2}, k3={k3}")
    print(f"  ph={ph:.8f}, pm={pm:.8f}, pl={pl:.3e}")
    print(f"  KL(P||U) = {kl_fwd:.6f} (target {TARGET})")
    print(f"  KL(U||P) = {kl_bwd:.6f} (target {TARGET})")

    if abs(kl_fwd - TARGET) > TOL or abs(kl_bwd - TARGET) > TOL:
        raise RuntimeError(
            f"Solution outside tolerance: KL_fwd={kl_fwd:.6f}, KL_bwd={kl_bwd:.6f}"
        )

    P = np.empty(V, dtype=np.float64)
    P[:k1] = ph
    P[k1 : k1 + k2] = pm
    P[k1 + k2 :] = pl
    P /= P.sum()

    return P


def verify(P: np.ndarray) -> None:
    """Verify the distribution meets all test requirements."""
    assert P.ndim == 1, f"Expected 1D array, got {P.ndim}D"
    assert P.size == V, f"Expected size {V}, got {P.size}"
    assert np.isfinite(P).all(), "Non-finite values in distribution"
    assert P.min() > 0.0, f"Non-positive values: min={P.min():.3e}"
    assert P.max() <= 1.0, f"Values > 1.0: max={P.max():.6f}"

    sum_p = float(P.sum())
    assert abs(sum_p - 1.0) < 1e-5, f"Sum={sum_p:.10f} too far from 1.0"

    P_norm = P / P.sum()
    kl_fwd = float(np.sum(P_norm * np.log(P_norm)) + math.log(P_norm.size))
    kl_bwd = float(-math.log(P_norm.size) - (1.0 / P_norm.size) * np.sum(np.log(P_norm)))

    assert abs(kl_fwd - TARGET) <= TOL, f"KL_fwd={kl_fwd:.6f} outside tolerance"
    assert abs(kl_bwd - TARGET) <= TOL, f"KL_bwd={kl_bwd:.6f} outside tolerance"

    print(f"Verification passed: KL_fwd={kl_fwd:.6f}, KL_bwd={kl_bwd:.6f}, sum={sum_p:.10f}")


def main() -> None:
    P = build_distribution()
    verify(P)
    np.save(SAVE_PATH, P)
    print(f"Saved distribution to {SAVE_PATH}")


if __name__ == "__main__":
    main()
PYEOF

echo "Running distribution finder..."
cd /app
python find_distribution.py

echo "Solution complete!"
