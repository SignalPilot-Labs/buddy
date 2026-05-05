"""Tests for max_budget_usd validation in StartRequest.

max_budget_usd is a required field (no default). Omitting it must raise a
ValueError. Explicit 0.0 means unlimited and passes through unchanged.
An explicit positive value is preserved as-is regardless of env vars.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AGENT_INTERNAL_SECRET", "test-secret")
os.environ.setdefault("SANDBOX_INTERNAL_SECRET", "test-sandbox-secret")

with patch("docker.from_env", return_value=MagicMock()):
    from server import AgentServer

from utils.constants import ENV_KEY_GIT_TOKEN
from utils.models import ActiveRun
from utils.models_http import StartRequest


def _make_server() -> AgentServer:
    """Build an AgentServer instance without triggering DB + pool setup."""
    srv = AgentServer.__new__(AgentServer)
    srv._pool = MagicMock()
    return srv


def _make_active_run(run_id: str) -> ActiveRun:
    """Create a minimal ActiveRun for testing."""
    active = ActiveRun(run_id=run_id, status="running")
    active.run_id = run_id
    return active


class TestBudgetEnvFallback:
    """max_budget_usd is required; omitting it must raise ValueError."""

    def test_missing_budget_raises_validation_error(self) -> None:
        """Omitting max_budget_usd must raise a ValueError — the field is required."""
        with pytest.raises((ValueError, TypeError)):
            StartRequest.model_validate({
                "github_repo": "owner/repo",
                "prompt": "fix the bug",
                "env": {ENV_KEY_GIT_TOKEN: "ghp_test_token"},
            })

    def test_zero_budget_means_unlimited(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit 0.0 must pass through as unlimited, not trigger env fallback."""
        monkeypatch.setenv("MAX_BUDGET_USD", "25.0")

        srv = _make_server()
        active = _make_active_run("aaaaaaaa-0000-0000-0000-000000000011")
        body = StartRequest(
            github_repo="owner/repo",
            prompt="fix the bug",
            max_budget_usd=0.0,
            env={ENV_KEY_GIT_TOKEN: "ghp_test_token"},
        )

        _run_id, _repo, _task, budget = srv._validate_run_inputs(active, body)

        assert budget == 0.0, (
            f"Expected 0.0 (unlimited) but got {budget!r}"
        )

    def test_positive_budget_ignores_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit positive budget must override the env var."""
        monkeypatch.setenv("MAX_BUDGET_USD", "25.0")

        srv = _make_server()
        active = _make_active_run("aaaaaaaa-0000-0000-0000-000000000012")
        body = StartRequest(
            github_repo="owner/repo",
            prompt="fix the bug",
            max_budget_usd=10.0,
            env={ENV_KEY_GIT_TOKEN: "ghp_test_token"},
        )

        _run_id, _repo, _task, budget = srv._validate_run_inputs(active, body)

        assert budget == 10.0
