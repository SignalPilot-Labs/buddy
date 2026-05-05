"""Regression test for the max_budget_usd falsy-check bug in server.py.

Previously `body.max_budget_usd or float(os.environ.get(...))` treated 0.0 as
falsy and silently overrode the user's explicit "unlimited" request with the
env-var default.  The fix drops the `or` entirely and trusts the model value.
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
    active = ActiveRun(run_id=run_id, status="running")
    active.run_id = run_id
    return active


class TestServerBudgetExtraction:
    """_extract_start_params must preserve max_budget_usd=0.0 (unlimited)."""

    def test_zero_budget_not_overridden_by_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """max_budget_usd=0.0 must come through as 0.0, not the env-var default."""
        monkeypatch.setenv("MAX_BUDGET_USD", "50.0")

        srv = _make_server()
        active = _make_active_run("aaaaaaaa-0000-0000-0000-000000000001")
        body = StartRequest(
            github_repo="owner/repo",
            prompt="fix the bug",
            max_budget_usd=0.0,
            env={ENV_KEY_GIT_TOKEN: "ghp_test_token"},
        )

        _run_id, _repo, _task, budget = srv._validate_run_inputs(active, body)

        assert budget == 0.0, (
            f"Expected 0.0 (unlimited) but got {budget!r} — "
            "the env-var default was incorrectly substituted"
        )

    def test_positive_budget_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A positive max_budget_usd must pass through unchanged."""
        monkeypatch.setenv("MAX_BUDGET_USD", "50.0")

        srv = _make_server()
        active = _make_active_run("aaaaaaaa-0000-0000-0000-000000000002")
        body = StartRequest(
            github_repo="owner/repo",
            prompt="fix the bug",
            max_budget_usd=10.0,
            env={ENV_KEY_GIT_TOKEN: "ghp_test_token"},
        )

        _run_id, _repo, _task, budget = srv._validate_run_inputs(active, body)

        assert budget == 10.0
