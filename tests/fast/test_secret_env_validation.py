"""Regression tests: secret env vars must fail fast when missing or empty.

Covers:
- dashboard/backend/utils.py raises on missing AGENT_INTERNAL_SECRET (Finding #1)
- dashboard/backend/utils.py raises on empty AGENT_INTERNAL_SECRET (Finding #1)
- docker-compose.yml contains no weak hardcoded default secrets (Finding #1)
"""

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Set before importing so the module-level guard passes during collection.
os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret-for-collection")

import dashboard.backend.utils as utils_module  # noqa: E402


class TestSecretEnvValidation:
    """Secret environment variables must cause fast failures when missing or empty."""

    def teardown_method(self) -> None:
        """Restore utils module to a valid state after each test."""
        os.environ["AGENT_INTERNAL_SECRET"] = "test-secret-restore"
        importlib.reload(utils_module)

    def test_dashboard_missing_agent_secret_raises(self) -> None:
        """KeyError when AGENT_INTERNAL_SECRET is absent from env."""
        env_without_secret = {k: v for k, v in os.environ.items() if k != "AGENT_INTERNAL_SECRET"}
        with patch.dict(os.environ, env_without_secret, clear=True):
            with pytest.raises(KeyError):
                importlib.reload(utils_module)

    def test_dashboard_empty_agent_secret_raises(self) -> None:
        """RuntimeError when AGENT_INTERNAL_SECRET is set but empty."""
        with patch.dict(os.environ, {"AGENT_INTERNAL_SECRET": ""}, clear=False):
            with pytest.raises(RuntimeError, match="AGENT_INTERNAL_SECRET is empty"):
                importlib.reload(utils_module)

    def test_docker_compose_no_weak_defaults(self) -> None:
        """docker-compose.yml must not contain hardcoded weak default secrets."""
        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        content = compose_path.read_text()
        assert "autofyn-dev-secret" not in content, (
            "docker-compose.yml still contains weak default 'autofyn-dev-secret'"
        )
        assert "autofyn-dev-sandbox-secret" not in content, (
            "docker-compose.yml still contains weak default 'autofyn-dev-sandbox-secret'"
        )
