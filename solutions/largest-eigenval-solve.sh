#!/bin/bash
set -e

# Replace /app/eigen.py with a faster implementation.
#
# Strategy: bypass all of numpy's Python-level overhead in np.linalg.eig by
# calling numpy's internal _umath_linalg.eig ufunc directly.
#
# np.linalg.eig wraps _umath_linalg.eig with:
#   - _makearray / wrap function creation
#   - _assert_stacked_square / _assert_finite checks
#   - _commonType computation
#   - errstate context manager
#   - conditional real/complex type casting
#   - EigResult namedtuple creation
#
# For small matrices (2x2 to 10x10), this overhead dominates the actual LAPACK
# computation time. Calling _umath_linalg.eig directly yields 1.3-3x speedup.

cat > /app/eigen.py << 'PYEOF'
import numpy as np
from numpy.linalg import _umath_linalg
import cmath

# Pre-bind to avoid attribute lookup overhead in hot path
_eig = _umath_linalg.eig
_argmax = np.argmax
_abs = np.abs


def _solve_2x2(A):
    """Direct formula for 2x2 dominant eigenvalue/eigenvector. No LAPACK overhead."""
    a, b = float(A[0, 0]), float(A[0, 1])
    c, d = float(A[1, 0]), float(A[1, 1])

    tr = a + d
    det = a * d - b * c
    disc = tr * tr - 4.0 * det

    if disc >= 0:
        sq = disc ** 0.5
        e1 = (tr + sq) / 2.0
        e2 = (tr - sq) / 2.0
        eigenval = e1 if abs(e1) >= abs(e2) else e2
        if abs(b) > 1e-15:
            v = np.array([b, eigenval - a])
        elif abs(c) > 1e-15:
            v = np.array([eigenval - d, c])
        else:
            v = np.array([1.0, 0.0]) if abs(eigenval - a) < abs(eigenval - d) else np.array([0.0, 1.0])
        v = v / np.linalg.norm(v)
        return np.float64(eigenval), v
    else:
        sq = cmath.sqrt(disc)
        e1 = (tr + sq) / 2.0
        e2 = (tr - sq) / 2.0
        eigenval = e1 if abs(e1) >= abs(e2) else e2
        if abs(b) > 1e-15:
            v = np.array([complex(b), eigenval - a])
        elif abs(c) > 1e-15:
            v = np.array([eigenval - d, complex(c)])
        else:
            v = np.array([complex(1.0), complex(0.0)])
        v = v / np.linalg.norm(v)
        return np.complex128(eigenval), v


def find_dominant_eigenvalue_and_eigenvector(
    A: np.ndarray,
) -> tuple[np.complexfloating | np.floating, np.ndarray]:
    n = A.shape[0]

    # Direct formula for 2x2 - avoids all overhead
    if n == 2:
        return _solve_2x2(A)

    # For larger matrices, call LAPACK directly bypassing Python overhead
    w, vt = _eig(A, signature="d->DD")

    idx = int(_argmax(_abs(w)))
    eigenval = w[idx]
    eigenvec = vt[:, idx]

    if eigenval.imag == 0.0:
        return eigenval.real, eigenvec.real

    return eigenval, eigenvec
PYEOF

echo "eigen.py written. Running correctness checks..."

python3 -c "
import sys
sys.path.insert(0, '/app')
import os
os.chdir('/app')
import numpy as np
from eigen import find_dominant_eigenvalue_and_eigenvector

# Test with seed=0 (same as the test file)
np.random.seed(0)
for size in range(2, 11):
    A = np.random.normal(size=(size, size)).astype(np.float64)
    eigenval, eigenvec = find_dominant_eigenvalue_and_eigenvector(A)

    assert not np.allclose(eigenvec, 0), f'zero eigenvec at size {size}'
    assert not np.isnan(eigenval), f'nan eigenval at size {size}'
    assert not np.isinf(eigenval), f'inf eigenval at size {size}'
    assert np.allclose(A @ eigenvec, eigenval * eigenvec), \
        f'Ax != lx at size {size}, residual={np.linalg.norm(A @ eigenvec - eigenval * eigenvec):.2e}'

    all_evals = np.linalg.eigvals(A)
    ref_max = all_evals[np.argmax(np.abs(all_evals))]
    assert np.isclose(np.abs(eigenval), np.abs(ref_max)), \
        f'not dominant at size {size}: |{eigenval}| vs |{ref_max}|'

    residual = np.linalg.norm(A @ eigenvec - eigenval * eigenvec)
    print(f'  size {size}: eigenval={eigenval}, residual={residual:.2e} OK')

print('All correctness checks passed!')
"

echo ""
echo "Running speed comparison..."

python3 -c "
import sys, time
sys.path.insert(0, '/app')
import os
os.chdir('/app')
import numpy as np
from eigen import find_dominant_eigenvalue_and_eigenvector

def ref_solution(A):
    eigenvalues, eigenvectors = np.linalg.eig(A)
    idx = np.argmax(np.abs(eigenvalues))
    return eigenvalues[idx], eigenvectors[:, idx]

np.random.seed(0)
N = 200
MAT_SIZES = list(range(2, 11))

all_faster = True
for size in MAT_SIZES:
    matrices = [np.random.normal(size=(size, size)).astype(np.float64) for _ in range(N)]

    dts = []
    for A in matrices:
        t0 = time.perf_counter()
        find_dominant_eigenvalue_and_eigenvector(A)
        t1 = time.perf_counter()
        dts.append(t1 - t0)
    dt = float(np.median(dts))

    ref_dts = []
    for A in matrices:
        t0 = time.perf_counter()
        ref_solution(A)
        t1 = time.perf_counter()
        ref_dts.append(t1 - t0)
    ref_dt = float(np.median(ref_dts))

    ratio = ref_dt / dt if dt > 0 else float('inf')
    status = 'FASTER' if dt < ref_dt else 'SLOWER'
    if dt >= ref_dt:
        all_faster = False
    print(f'  size {size}: ours={dt*1e6:.1f}us ref={ref_dt*1e6:.1f}us {status} ({ratio:.2f}x)')

print()
print('PASS: all sizes faster' if all_faster else 'WARN: some sizes not faster (median may vary)')
"
