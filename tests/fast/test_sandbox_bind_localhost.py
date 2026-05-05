"""Regression test: Sandbox must bind to 127.0.0.1 by default.

Binding to 0.0.0.0 exposes the sandbox HTTP API to other users on
shared HPC compute nodes. This is HIGH severity in shared environments.
"""

import importlib
import os
from unittest.mock import patch


class TestSandboxBindLocalhost:
    """Sandbox must bind to 127.0.0.1 by default for security."""

    def setup_method(self) -> None:
        import sandbox.constants
        self._original_host: str = sandbox.constants.SANDBOX_HOST

    def teardown_method(self) -> None:
        import sandbox.constants
        sandbox.constants.SANDBOX_HOST = self._original_host

    def test_sandbox_host_default_is_localhost(self) -> None:
        """SANDBOX_HOST defaults to 127.0.0.1, not 0.0.0.0."""
        with patch.dict(os.environ, {}, clear=True):
            import sandbox.constants
            importlib.reload(sandbox.constants)
            assert sandbox.constants.SANDBOX_HOST == "127.0.0.1", (
                "Sandbox must bind to 127.0.0.1 by default - "
                "0.0.0.0 exposes API to other users on shared HPC nodes"
            )

    def test_sandbox_host_can_be_overridden(self) -> None:
        """AF_SANDBOX_BIND_HOST env var allows override for legacy clusters."""
        with patch.dict(os.environ, {"AF_SANDBOX_BIND_HOST": "0.0.0.0"}):
            import sandbox.constants
            importlib.reload(sandbox.constants)
            assert sandbox.constants.SANDBOX_HOST == "0.0.0.0"
