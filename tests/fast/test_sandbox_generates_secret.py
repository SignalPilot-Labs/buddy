"""Regression test: sandbox generates its own secret when env var is absent.

Verifies _load_sandbox_secret() behaviour for both code paths:
  - When SANDBOX_INTERNAL_SECRET env var is set (local Docker path): returns it.
  - When SANDBOX_INTERNAL_SECRET env var is absent (remote path): generates
    a 64-char hex secret using secrets.token_hex(32).
"""

import os


class TestSandboxGeneratesSecret:
    """_load_sandbox_secret generates a secure secret for remote sandboxes."""

    def setup_method(self) -> None:
        """Capture original env state before each test."""
        self._original = os.environ.get("SANDBOX_INTERNAL_SECRET")

    def teardown_method(self) -> None:
        """Restore original env state after each test."""
        if self._original is None:
            os.environ.pop("SANDBOX_INTERNAL_SECRET", None)
        else:
            os.environ["SANDBOX_INTERNAL_SECRET"] = self._original

    def test_generates_64_char_hex_when_env_absent(self) -> None:
        """Without env var, generates a 64-char hex secret (256 bits)."""
        os.environ.pop("SANDBOX_INTERNAL_SECRET", None)

        from sandbox.server import _load_sandbox_secret

        secret = _load_sandbox_secret()

        assert len(secret) == 64, f"Expected 64 hex chars, got {len(secret)}"
        assert all(c in "0123456789abcdef" for c in secret), (
            f"Expected lowercase hex, got: {secret!r}"
        )

    def test_returns_env_var_when_set(self) -> None:
        """With env var set, returns the env var value (local Docker path)."""
        expected = "my-docker-compose-secret-value"
        os.environ["SANDBOX_INTERNAL_SECRET"] = expected

        from sandbox.server import _load_sandbox_secret

        result = _load_sandbox_secret()

        assert result == expected

    def test_env_var_consumed_after_read(self) -> None:
        """Env var is popped (consumed) after being read — not left in environment."""
        os.environ["SANDBOX_INTERNAL_SECRET"] = "consumed-secret"

        from sandbox.server import _load_sandbox_secret

        _load_sandbox_secret()

        assert "SANDBOX_INTERNAL_SECRET" not in os.environ

    def test_two_calls_generate_different_secrets(self) -> None:
        """Two calls without env var produce distinct secrets (not deterministic)."""
        os.environ.pop("SANDBOX_INTERNAL_SECRET", None)

        from sandbox.server import _load_sandbox_secret

        secret1 = _load_sandbox_secret()
        secret2 = _load_sandbox_secret()

        assert secret1 != secret2, "Two generated secrets should differ"
