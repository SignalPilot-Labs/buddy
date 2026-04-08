#!/bin/bash
set -e

# Write the optimized C extension
cat > /app/portfolio_optimized.c << 'EOF'
/*
 * High-performance portfolio calculations using C extension
 * Implements: portfolio_risk = sqrt(x^T * S * x), portfolio_return = x^T * r
 *
 * NOTE: -ffast-math is intentionally NOT used to preserve IEEE 754 exact
 * semantics matching the Python baseline within 1e-10 tolerance.
 */

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <math.h>
#include <stdlib.h>

static PyObject* portfolio_risk_c(PyObject *self, PyObject *args) {
    PyArrayObject *weights_array, *cov_array;

    if (!PyArg_ParseTuple(args, "O!O!", &PyArray_Type, &weights_array,
                                       &PyArray_Type, &cov_array))
        return NULL;

    /* Ensure contiguous double arrays */
    PyArrayObject *weights = (PyArrayObject *)PyArray_FROM_OTF(
        (PyObject *)weights_array, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY);
    PyArrayObject *cov = (PyArrayObject *)PyArray_FROM_OTF(
        (PyObject *)cov_array, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY);

    if (!weights || !cov) {
        Py_XDECREF(weights);
        Py_XDECREF(cov);
        return NULL;
    }

    npy_intp n = PyArray_DIM(weights, 0);
    double *w = (double *)PyArray_DATA(weights);
    double *S = (double *)PyArray_DATA(cov);

    /* Compute x^T * S * x using row-major layout of S
     * Loop order matches Python baseline: outer i, inner j accumulate row_dot
     * Sequential accumulation matches Python float arithmetic. */
    double risk_squared = 0.0;
    for (npy_intp i = 0; i < n; i++) {
        double row_dot = 0.0;
        const double *S_row = S + i * n;
        for (npy_intp j = 0; j < n; j++) {
            row_dot += S_row[j] * w[j];
        }
        risk_squared += w[i] * row_dot;
    }

    Py_DECREF(weights);
    Py_DECREF(cov);

    return PyFloat_FromDouble(sqrt(risk_squared));
}

static PyObject* portfolio_return_c(PyObject *self, PyObject *args) {
    PyArrayObject *weights_array, *returns_array;

    if (!PyArg_ParseTuple(args, "O!O!", &PyArray_Type, &weights_array,
                                       &PyArray_Type, &returns_array))
        return NULL;

    PyArrayObject *weights = (PyArrayObject *)PyArray_FROM_OTF(
        (PyObject *)weights_array, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY);
    PyArrayObject *returns = (PyArrayObject *)PyArray_FROM_OTF(
        (PyObject *)returns_array, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY);

    if (!weights || !returns) {
        Py_XDECREF(weights);
        Py_XDECREF(returns);
        return NULL;
    }

    npy_intp n = PyArray_DIM(weights, 0);
    double *w = (double *)PyArray_DATA(weights);
    double *r = (double *)PyArray_DATA(returns);

    double total_return = 0.0;
    for (npy_intp i = 0; i < n; i++) {
        total_return += w[i] * r[i];
    }

    Py_DECREF(weights);
    Py_DECREF(returns);

    return PyFloat_FromDouble(total_return);
}

static PyMethodDef module_methods[] = {
    {"portfolio_risk_c", portfolio_risk_c, METH_VARARGS, "Calculate portfolio risk"},
    {"portfolio_return_c", portfolio_return_c, METH_VARARGS, "Calculate portfolio return"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "portfolio_optimized_c",
    "Optimized portfolio calculations",
    -1,
    module_methods
};

PyMODINIT_FUNC PyInit_portfolio_optimized_c(void) {
    if (import_array() < 0) {
        return NULL;
    }
    return PyModule_Create(&moduledef);
}
EOF

# Write the Python wrapper
cat > /app/portfolio_optimized.py << 'EOF'
"""
Python wrapper for portfolio optimization C extension.
"""

import numpy as np
import portfolio_optimized_c


def portfolio_risk_c(weights, cov_matrix):
    """
    Calculate portfolio risk using C extension: sqrt(x^T * S * x)

    Args:
        weights: Portfolio weights (1D array or list)
        cov_matrix: Covariance matrix (2D array or list of lists)
    Returns:
        Portfolio risk (scalar float)
    """
    w = np.asarray(weights, dtype=np.float64)
    S = np.asarray(cov_matrix, dtype=np.float64)
    return portfolio_optimized_c.portfolio_risk_c(w, S)


def portfolio_return_c(weights, expected_returns):
    """
    Calculate expected portfolio return using C extension: weights^T * returns

    Args:
        weights: Portfolio weights (1D array or list)
        expected_returns: Expected returns (1D array or list)
    Returns:
        Expected return (scalar float)
    """
    w = np.asarray(weights, dtype=np.float64)
    r = np.asarray(expected_returns, dtype=np.float64)
    return portfolio_optimized_c.portfolio_return_c(w, r)


__all__ = ['portfolio_risk_c', 'portfolio_return_c']
EOF

# Write setup.py without -ffast-math to preserve IEEE 754 semantics
# and match Python baseline results within 1e-10 tolerance
cat > /app/setup.py << 'EOF'
import numpy
from setuptools import Extension, setup

module = Extension('portfolio_optimized_c',
                   sources=['portfolio_optimized.c'],
                   include_dirs=[numpy.get_include()],
                   extra_compile_args=['-O2', '-fno-tree-vectorize'])

setup(name='portfolio_optimized',
      ext_modules=[module])
EOF

# Build the C extension in /app
cd /app
python3 setup.py build_ext --inplace

echo "Build complete."
