"""Path setup for sandbox tests.

The root pyproject.toml puts both `autofyn/` and `sandbox/` on sys.path.
Both contain a `session/` package, and `autofyn/` wins by position.

This conftest inserts `sandbox/` at the front of sys.path and evicts any
cached `session` module so sandbox imports resolve correctly.

NOTE: sandbox tests must run in a separate pytest invocation from
`tests/fast/` to avoid module cache collisions. Run with:
    pytest tests/sandbox/
"""

import sys
from pathlib import Path

_SANDBOX_ROOT = str(Path(__file__).resolve().parent.parent.parent / "sandbox")

for key in list(sys.modules):
    if key == "session" or key.startswith("session."):
        del sys.modules[key]

sys.path.insert(0, _SANDBOX_ROOT)
